"""Training-table regressions for coach feedback and completed-hand reveals."""

import unittest
from unittest.mock import patch

from backend.brain.coach import SessionTracker
from backend.engine.deck import Deck
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player
from backend.engine.training_table import TrainingTable


def players(count: int) -> tuple[Player, ...]:
    names = ("You", "Aggro Alex", "Nitty Norman", "Calling Kevin", "Balanced Blair", "Aggro Alex")
    return tuple(Player("hero" if seat == 0 else f"bot-{seat}", names[seat], 200) for seat in range(count))


def finish_uncontested_showdown(state: GameState) -> GameState:
    while state.street is not Street.SHOWDOWN:
        actor = state.current_player
        assert actor is not None
        legal = state.legal_actions()
        action = ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL
        state = state.apply_action(actor.id, action)
    rankings = {
        player.id: HandEvaluator.evaluate_7(player.hole_cards + state.community_cards)
        for player in state.players
        if player.is_active
    }
    return state.resolve_showdown()


class TrainingTableTests(unittest.TestCase):
    def test_live_coach_snapshot_is_attached_to_a_heads_up_decision(self) -> None:
        table = TrainingTable(SessionTracker())
        table._state = GameState.new_hand(players(2), 1, 2, button_index=0, deck=Deck(seed=17))
        table._hand_number = 1

        result = table.snapshot()

        self.assertEqual(result["current_player_id"], "hero")
        self.assertEqual(result["coach_context"], "current_decision")
        self.assertIsNotNone(result["coach"])
        self.assertIn("equity_percentage", result["coach"])

    def test_live_coach_estimates_equity_against_multiple_active_opponents(self) -> None:
        table = TrainingTable(SessionTracker())
        table._state = GameState.new_hand(players(3), 1, 2, button_index=0, deck=Deck(seed=29))
        table._hand_number = 1

        result = table.snapshot()

        self.assertEqual(result["current_player_id"], "hero")
        self.assertTrue(result["multiway"])
        self.assertEqual(result["coach_context"], "current_decision")
        self.assertIsNotNone(result["coach"])
        self.assertIn("multiway", result["coach"]["equity_source"])

    def test_fold_win_reveals_only_surviving_opponent_and_reports_real_street(self) -> None:
        table = TrainingTable(SessionTracker())
        state = GameState.new_hand(players(3), 1, 2, button_index=0, deck=Deck(seed=23))
        while state.street is not Street.FLOP:
            actor = state.current_player
            assert actor is not None
            legal = state.legal_actions()
            action = ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL
            state = state.apply_action(actor.id, action)
        state = state.apply_action("bot-1", ActionType.FOLD)
        state = state.apply_action("bot-2", ActionType.CHECK)
        state = state.apply_action("hero", ActionType.FOLD)
        table._state = state
        table._hand_number = 1

        result = table.snapshot()
        seats = {seat["id"]: seat for seat in result["seats"]}

        self.assertTrue(result["hand_complete"])
        self.assertEqual(result["street"], "flop")
        self.assertEqual(len(result["board"]), 3)
        self.assertEqual(len(seats["bot-2"]["hole_cards"]), 2)
        self.assertFalse(seats["bot-2"]["cards_hidden"])
        self.assertEqual(seats["bot-1"]["hole_cards"], [])
        self.assertTrue(seats["bot-1"]["cards_hidden"])

    def test_last_decision_coach_survives_fold_settlement(self) -> None:
        table = TrainingTable(SessionTracker())
        table._state = GameState.new_hand(players(2), 1, 2, button_index=0, deck=Deck(seed=31))
        table._hand_number = 1

        result = table.act("fold")

        self.assertEqual(result["coach_context"], "last_decision")
        self.assertIsNotNone(result["coach"])
        self.assertTrue(result["hand_complete"])

    def test_coach_analysis_error_does_not_block_a_legal_action(self) -> None:
        table = TrainingTable(SessionTracker())
        table._state = GameState.new_hand(players(2), 1, 2, button_index=0, deck=Deck(seed=37))
        table._hand_number = 1

        with patch.object(table, "_coach_for", side_effect=ValueError("No modeled range.")):
            result = table.act("call")

        self.assertTrue(any(
            action.player_id == "hero" and action.action is ActionType.CALL
            for action in table._state.action_history
        ))
        self.assertTrue(result["started"])

    def test_showdown_reveals_all_remaining_hands(self) -> None:
        table = TrainingTable(SessionTracker())
        state = GameState.new_hand(players(2), 1, 2, button_index=0, deck=Deck(seed=43))
        table._state = finish_uncontested_showdown(state)
        table._hand_number = 1

        seats = {seat["id"]: seat for seat in table.snapshot()["seats"]}

        self.assertEqual(len(seats["bot-1"]["hole_cards"]), 2)
        self.assertFalse(seats["bot-1"]["cards_hidden"])


if __name__ == "__main__":
    unittest.main()
