"""State-machine tests for blinds, betting actions, and all-in runouts."""

import unittest
from dataclasses import replace

from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player
from backend.engine.rules import GameRules, GameVariant
from backend.engine.card import Card


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
        self.assertEqual(state.rules.variant, GameVariant.TEXAS_HOLDEM)

    def test_plo_deals_four_cards_per_player_and_records_variant(self) -> None:
        state = GameState.new_hand(
            self.make_players((100, 100, 100)), 1, 2,
            deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )

        self.assertEqual(state.rules.variant, GameVariant.POT_LIMIT_OMAHA)
        self.assertTrue(all(len(player.hole_cards) == 4 for player in state.players))
        self.assertEqual(state.deck_cursor, 12)
        acted = state.apply_action(state.current_player_id, ActionType.CALL)
        self.assertEqual(acted.action_history[-1].variant, GameVariant.POT_LIMIT_OMAHA)

    def test_variant_rules_validate_seat_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 2 and 6"):
            GameState.new_hand(self.make_players((100,)), 1, 2, rules=GameRules.pot_limit_omaha())

    def test_plo_preflop_raise_is_capped_by_pot_and_backend_reports_bounds(self) -> None:
        state = GameState.new_hand(
            self.make_players((100, 100, 100)), 1, 2,
            deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )
        self.assertEqual(state.betting_bounds(), {
            "amount_to_call": 2, "minimum_raise_to": 4, "maximum_raise_to": 7, "all_in_to": 100,
        })
        with self.assertRaisesRegex(ValueError, "pot-limit maximum"):
            state.apply_action("p0", ActionType.RAISE, 8)
        state = state.apply_action("p0", ActionType.RAISE, 7)
        self.assertEqual(state.player_by_id("p0").current_bet, 7)
        self.assertEqual(state.current_player_id, "p1")
        self.assertEqual(state.betting_bounds()["maximum_raise_to"], 22)

    def test_plo_pot_limit_bounds_are_recomputed_after_flop_and_capped_by_stack(self) -> None:
        state = GameState.new_hand(
            self.make_players((40, 40)), 1, 2,
            deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )
        state = state.apply_action("p0", ActionType.CALL)
        state = state.apply_action("p1", ActionType.CHECK)
        self.assertEqual(state.street, Street.FLOP)
        self.assertEqual(state.betting_bounds()["maximum_raise_to"], 4)
        state = state.apply_action("p1", ActionType.BET, 4)
        self.assertEqual(state.betting_bounds()["maximum_raise_to"], 16)
        with self.assertRaisesRegex(ValueError, "pot-limit maximum"):
            state.apply_action("p0", ActionType.RAISE, 17)

    def test_plo_short_call_and_short_all_in_raise_respect_pot_and_stack(self) -> None:
        state = GameState.new_hand(
            self.make_players((5, 8, 8)), 1, 2,
            deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )
        state = state.apply_action("p0", ActionType.CALL)
        self.assertEqual(state.player_by_id("p0").stack, 3)
        self.assertEqual(state.current_player_id, "p1")
        self.assertEqual(state.betting_bounds()["amount_to_call"], 1)
        self.assertEqual(state.betting_bounds()["all_in_to"], 8)
        self.assertEqual(state.betting_bounds()["maximum_raise_to"], 7)
        with self.assertRaisesRegex(ValueError, "pot-limit maximum"):
            state.apply_action("p1", ActionType.RAISE, 8)
        state = state.apply_action("p1", ActionType.RAISE, 7)
        self.assertEqual(state.current_player_id, "p2")
        self.assertIn(ActionType.CALL, state.legal_actions())

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
        settled = state.resolve_showdown()

        self.assertEqual(sum(dict(settled.payouts).values()), 110)
        self.assertEqual(sum(player.stack for player in settled.players), 165)
        self.assertEqual(initial_snapshot.street, Street.PREFLOP)
        self.assertEqual(initial_snapshot.pot, 15)
        self.assertEqual([player.stack for player in initial_snapshot.players], [20, 40, 90])

    def test_plo_showdown_rejects_board_only_trap_and_records_exact_used_cards(self) -> None:
        state = GameState.new_hand(
            self.make_players((20, 20)), 1, 2, deck=Deck(shuffle=False),
            rules=GameRules.pot_limit_omaha(),
        )
        plo_players = state.players
        board = tuple(state.deck_order[8:13])
        deck = state.deck_order
        dealt = {card for player in plo_players for card in player.hole_cards} | set(board)
        burns = tuple(card for card in deck if card not in dealt)[: 20 - len(dealt)]
        state = replace(state, street=Street.SHOWDOWN, community_cards=board,
                        current_player_id=None, pending_action_ids=(), deck_order=deck, deck_cursor=20,
                        burned_cards=burns)
        rankings, used = state.evaluate_showdown_hands()
        for player_id, cards_used in used.items():
            self.assertEqual(len(cards_used), 5)
            self.assertEqual(sum(card in state.player_by_id(player_id).hole_cards for card in cards_used), 2)
            self.assertEqual(sum(card in board for card in cards_used), 3)
            self.assertNotEqual(set(cards_used), set(board))

    def test_plo_showdown_splits_tie_and_awards_main_and_side_pots_conservatively(self) -> None:
        players = (
            Player("short", "Short", 0, 10, tuple(Card.from_code(c) for c in ("2c", "4d", "6h", "9c")), True, True, total_contributed=10),
            Player("mid", "Mid", 0, 20, tuple(Card.from_code(c) for c in ("2d", "4c", "6s", "9h")), True, True, total_contributed=20),
            Player("deep", "Deep", 10, 20, tuple(Card.from_code(c) for c in ("2s", "5d", "7s", "4h")), True, False, total_contributed=20),
        )
        board = tuple(Card.from_code(code) for code in ("As", "Kd", "Qh", "8c", "3s"))
        deck = tuple(reversed(Deck(shuffle=False).cards))
        dealt = {card for player in players for card in player.hole_cards} | set(board)
        burns = tuple(card for card in deck if card not in dealt)[: 20 - len(dealt)]
        state = GameState(
            players=players, rules=GameRules.pot_limit_omaha(), button_index=0,
            small_blind=1, big_blind=2, street=Street.SHOWDOWN, community_cards=board,
            current_player_id=None, pending_action_ids=(), last_full_raise_size=2,
            deck_order=deck, deck_cursor=20, burned_cards=burns,
        )
        settled = state.resolve_showdown()
        self.assertEqual(dict(settled.payouts), {"short": 15, "mid": 35})
        self.assertEqual(sum(dict(settled.payouts).values()), state.pot)
        self.assertEqual([award.amount for award in settled.pot_awards], [30, 20])
        self.assertEqual([award.winner_ids for award in settled.pot_awards], [("short", "mid"), ("mid",)])
        self.assertEqual(dict(settled.showdown_ranks)["short"], dict(settled.showdown_ranks)["mid"])
        self.assertEqual(sum(player.stack for player in settled.players), sum(player.stack for player in state.players) + state.pot)

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
