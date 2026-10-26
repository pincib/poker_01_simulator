"""State-machine tests for blinds, betting actions, and all-in runouts."""

import unittest

from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player


class GameStateTests(unittest.TestCase):
    def make_players(self, stacks: tuple[int, ...]) -> tuple[Player, ...]:
        return tuple(Player(f"p{index}", f"Player {index}", stack) for index, stack in enumerate(stacks))

    def test_posts_blinds_and_deals_two_cards_without_mutating_inputs(self) -> None:
        players = self.make_players((100, 100, 100))
        state = GameState.new_hand(players, 5, 10, deck=Deck(shuffle=False))

        self.assertEqual(state.street, Street.PREFLOP)
        self.assertEqual(state.current_player_id, "p0")
        self.assertEqual([player.stack for player in state.players], [100, 95, 90])
        self.assertEqual([player.current_bet for player in state.players], [0, 5, 10])
        self.assertTrue(all(len(player.hole_cards) == 2 for player in state.players))
        self.assertEqual([player.position.value for player in state.players], ["BTN", "SB", "BB"])
        self.assertEqual([player.stack for player in players], [100, 100, 100])

    def test_short_stacks_run_to_showdown_and_award_main_and_side_pots(self) -> None:
        state = GameState.new_hand(self.make_players((20, 45, 100)), 5, 10, deck=Deck(shuffle=False))
        initial_snapshot = state

        state = state.apply_action("p0", ActionType.ALL_IN)
        state = state.apply_action("p1", ActionType.CALL)
        state = state.apply_action("p2", ActionType.CALL)
        self.assertEqual(state.street, Street.FLOP)

        state = state.apply_action("p1", ActionType.ALL_IN)
        state = state.apply_action("p2", ActionType.CALL)

        self.assertEqual(state.street, Street.SHOWDOWN)
        self.assertFalse(state.hand_complete)
        self.assertEqual(state.pot, 110)
        self.assertEqual(len(state.community_cards), 5)
        settled = state.resolve_showdown({"p0": 1, "p1": 2, "p2": 3})

        self.assertEqual(dict(settled.payouts), {"p0": 60, "p1": 50})
        self.assertEqual([player.stack for player in settled.players], [60, 50, 55])
        self.assertEqual(sum(player.stack for player in settled.players), 165)
        self.assertEqual(initial_snapshot.street, Street.PREFLOP)
        self.assertEqual(initial_snapshot.pot, 15)
        self.assertEqual([player.stack for player in initial_snapshot.players], [20, 40, 90])

    def test_fold_awards_current_pot_and_completes_hand(self) -> None:
        state = GameState.new_hand(self.make_players((100, 100)), 5, 10, deck=Deck(shuffle=False))
        finished = state.apply_action("p0", ActionType.FOLD)

        self.assertTrue(finished.hand_complete)
        self.assertEqual(finished.winners, ("p1",))
        self.assertEqual(dict(finished.payouts), {"p1": 15})
        self.assertEqual([player.stack for player in finished.players], [95, 105])
        self.assertEqual(finished.legal_actions(), ())

    def test_rejects_bet_below_one_big_blind(self) -> None:
        state = GameState.new_hand(self.make_players((100, 100)), 5, 10, deck=Deck(shuffle=False))
        state = state.apply_action("p0", ActionType.CALL)
        state = state.apply_action("p1", ActionType.CHECK)
        self.assertEqual(state.street, Street.FLOP)

        with self.assertRaisesRegex(ValueError, "minimum bet"):
            state.apply_action("p1", ActionType.BET, 5)

    def test_six_max_hand_accepts_calls_checks_bets_raises_and_folds(self) -> None:
        state = GameState.new_hand(self.make_players((200,) * 6), 5, 10, deck=Deck(shuffle=False))
        for player_id, action, amount in (
            ("p3", ActionType.CALL, None),
            ("p4", ActionType.RAISE, 30),
            ("p5", ActionType.CALL, None),
            ("p0", ActionType.CALL, None),
            ("p1", ActionType.CALL, None),
            ("p2", ActionType.CALL, None),
            ("p3", ActionType.CALL, None),
        ):
            state = state.apply_action(player_id, action, amount)

        self.assertEqual(state.street, Street.FLOP)
        for player_id, action, amount in (
            ("p1", ActionType.CHECK, None),
            ("p2", ActionType.BET, 30),
            ("p3", ActionType.FOLD, None),
            ("p4", ActionType.CALL, None),
            ("p5", ActionType.RAISE, 90),
            ("p0", ActionType.CALL, None),
            ("p1", ActionType.FOLD, None),
            ("p2", ActionType.CALL, None),
            ("p4", ActionType.CALL, None),
        ):
            state = state.apply_action(player_id, action, amount)

        for street in (Street.TURN, Street.RIVER):
            self.assertEqual(state.street, street)
            for player_id in ("p2", "p4", "p5", "p0"):
                state = state.apply_action(player_id, ActionType.CHECK)

        self.assertEqual(state.street, Street.SHOWDOWN)
        action_types = {record.action for record in state.action_history}
        self.assertTrue({ActionType.CALL, ActionType.CHECK, ActionType.BET, ActionType.RAISE, ActionType.FOLD} <= action_types)
        self.assertEqual(len(state.community_cards), 5)


if __name__ == "__main__":
    unittest.main()
