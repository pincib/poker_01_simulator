"""Tests for positional ranges, board texture, sizing, and AI decisions."""

import unittest
from dataclasses import replace

from backend.brain.ai_agent import OpponentAI, OpponentProfile, plo_starting_hand_score
from backend.brain.board_texture import BoardTextureClassifier, SuitPattern
from backend.brain.bet_sizing import BetSizer, SizingOption
from backend.brain.ranges import get_opening_range
from backend.engine.card import Card
from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player, Position
from backend.engine.rules import GameRules


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class OpponentAITests(unittest.TestCase):
    def test_plo_preflop_score_rewards_coordinated_nut_potential(self) -> None:
        premium = plo_starting_hand_score(cards("As", "Ah", "Ks", "Qh"))
        weak = plo_starting_hand_score(cards("7c", "2d", "Jc", "4h"))
        self.assertGreater(premium, weak)
        with self.assertRaises(ValueError):
            plo_starting_hand_score(cards("As", "Ah", "Ks"))

    def test_plo_decision_is_seed_reproducible_and_within_backend_bounds(self) -> None:
        state = GameState.new_hand(
            (Player("p0", "P0", 120), Player("p1", "P1", 120), Player("p2", "P2", 120)),
            1, 2, deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )
        actor = state.current_player
        first = OpponentAI("aggressive", equity_iterations=4).decide(state, actor.id, seed=92)
        repeated = OpponentAI("aggressive", equity_iterations=4).decide(state, actor.id, seed=92)
        self.assertEqual(first, repeated)
        self.assertIn(first.action, state.legal_actions())
        if first.action in (ActionType.BET, ActionType.RAISE):
            self.assertLessEqual(first.amount, state.betting_bounds(actor.id)["maximum_raise_to"])

    def test_plo_postflop_decision_uses_ranges_and_records_an_explanation(self) -> None:
        state = GameState.new_hand(
            tuple(Player(f"p{i}", f"P{i}", 120) for i in range(3)),
            1, 2, deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )
        while state.street is Street.PREFLOP:
            actor = state.current_player
            action = ActionType.CALL if ActionType.CALL in state.legal_actions() else ActionType.CHECK
            state = state.apply_action(actor.id, action)
        actor = state.current_player
        decision = OpponentAI("balanced", equity_iterations=3, seed=17).decide(state, actor.id, seed=18)
        self.assertIn(decision.action, state.legal_actions())
        self.assertGreater(decision.range_size, 0)
        self.assertIn("equity", decision.reason.lower())
        self.assertEqual(decision.seed, 18)

    def test_plo_profile_bots_complete_a_hand_without_illegal_actions(self) -> None:
        state = GameState.new_hand(
            tuple(Player(f"p{i}", f"P{i}", 36) for i in range(3)),
            1, 2, deck=Deck(shuffle=False), rules=GameRules.pot_limit_omaha(),
        )
        bots = {player.id: OpponentAI(profile, equity_iterations=3, seed=i + 1)
                for i, (player, profile) in enumerate(zip(state.players, ("tight", "aggressive", "calling_station")))}
        action_count = 0
        while not state.hand_complete:
            actor = state.current_player
            self.assertIsNotNone(actor, "unfinished hand must have a next actor")
            decision = bots[actor.id].decide(state, actor.id)
            self.assertIn(decision.action, state.legal_actions())
            if decision.action in (ActionType.BET, ActionType.RAISE):
                self.assertLessEqual(decision.amount, state.betting_bounds(actor.id)["maximum_raise_to"])
            state = state.apply_action(actor.id, decision.action, decision.amount)
            action_count += 1
            self.assertLess(action_count, 100, "bot hand must not deadlock")
        self.assertGreater(action_count, 0)
        self.assertEqual(sum(amount for _, amount in state.payouts), sum(p.total_contributed for p in state.players))

    def test_positional_ranges_hit_the_roadmap_opening_percentages(self) -> None:
        expected = {
            Position.UNDER_THE_GUN: 15,
            Position.HIJACK: 19,
            Position.CUTOFF: 27,
            Position.BUTTON: 45,
            Position.SMALL_BLIND: 38,
        }
        for position, percentage in expected.items():
            with self.subTest(position=position):
                starting_range = get_opening_range(position)
                self.assertAlmostEqual(starting_range.actual_percentage, percentage)
                self.assertEqual(len(starting_range.matrix), 13)
                self.assertTrue(all(len(row) == 13 for row in starting_range.matrix))

    def test_action_filter_tightens_an_opening_range(self) -> None:
        starting_range = get_opening_range(Position.BUTTON)
        raised_range = starting_range.filtered_by_action(ActionType.RAISE)

        self.assertLess(raised_range.combo_count, starting_range.combo_count)
        self.assertTrue(raised_range.contains(cards("As", "Ah")))

    def test_board_texture_identifies_dry_rainbow_and_wet_connected_boards(self) -> None:
        dry = BoardTextureClassifier.classify(cards("As", "7d", "2c"))
        wet = BoardTextureClassifier.classify(cards("9h", "8h", "7d"))

        self.assertTrue(dry.dry)
        self.assertEqual(dry.suit_pattern, SuitPattern.RAINBOW)
        self.assertTrue(dry.has_high_card)
        self.assertTrue(wet.wet)
        self.assertEqual(wet.suit_pattern, SuitPattern.TWO_TONE)
        self.assertTrue(wet.low_connected)

    def test_bet_sizing_uses_one_third_on_dry_and_two_thirds_on_wet(self) -> None:
        dry = BoardTextureClassifier.classify(cards("As", "7d", "2c"))
        wet = BoardTextureClassifier.classify(cards("9h", "8h", "7d"))
        dry_size = BetSizer.recommend(
            pot=100, remaining_stack=500, big_blind=2, street=Street.FLOP, texture=dry
        )
        wet_size = BetSizer.recommend(
            pot=100, remaining_stack=500, big_blind=2, street=Street.FLOP, texture=wet
        )

        self.assertEqual((dry_size.option, dry_size.bet_to), (SizingOption.SMALL_CBET, 33))
        self.assertEqual((wet_size.option, wet_size.bet_to), (SizingOption.STANDARD, 66))

    def test_river_polarized_sizing_recommends_all_in(self) -> None:
        texture = BoardTextureClassifier.classify(cards("As", "Kd", "7c", "4h", "2s"))
        sizing = BetSizer.recommend(
            pot=100,
            remaining_stack=80,
            big_blind=2,
            street=Street.RIVER,
            texture=texture,
            player_current_bet=10,
            polarized=True,
        )

        self.assertEqual(sizing.option, SizingOption.ALL_IN)
        self.assertEqual(sizing.bet_to, 90)

    def test_profiles_have_requested_names_and_nit_folds_a_trash_utg_hand(self) -> None:
        self.assertEqual(
            [profile.display_name for profile in OpponentProfile],
            ["Nitty Norman", "Calling Kevin", "Aggro Alex", "Balanced Blair"],
        )
        state = GameState.new_hand(
            tuple(Player(f"p{i}", f"Player {i}", 100) for i in range(6)),
            5,
            10,
            deck=Deck(shuffle=False),
        )
        players = tuple(
            player.with_hole_cards(cards("2c", "7d")) if player.id == state.current_player_id else player
            for player in state.players
        )
        state = replace(state, players=players)
        actor = state.current_player
        self.assertEqual(actor.position, Position.UNDER_THE_GUN)

        decision = OpponentAI("Nitty Norman", seed=2).decide(state, actor.id)

        self.assertEqual(decision.action, ActionType.FOLD)
        self.assertIn(decision.action, state.legal_actions())

    def test_all_profiles_return_an_action_accepted_by_the_game_state(self) -> None:
        players = (Player("hero", "Hero", 100), Player("bot", "Bot", 100))
        state = GameState.new_hand(players, 5, 10, deck=Deck(shuffle=False))
        state = state.apply_action("hero", ActionType.CALL)
        state = state.apply_action("bot", ActionType.CHECK)
        self.assertEqual(state.street, Street.FLOP)
        actor = state.current_player

        for profile in OpponentProfile:
            with self.subTest(profile=profile):
                decision = OpponentAI(profile, equity_iterations=24, seed=11).decide(state, actor.id)
                self.assertIn(decision.action, state.legal_actions())
                state.apply_action(actor.id, decision.action, decision.amount)


if __name__ == "__main__":
    unittest.main()
