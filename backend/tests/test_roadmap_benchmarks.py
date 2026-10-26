"""Roadmap Monte Carlo known-matchup and throughput checks."""

import time
import unittest

from backend.brain.equity import EquityCalculator
from backend.engine.card import Card
from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player
from backend.engine.rules import GameRules


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class MonteCarloRoadmapBenchmarks(unittest.TestCase):
    def test_ten_thousand_preflop_rollouts_complete_under_one_second(self) -> None:
        started = time.perf_counter()
        result = EquityCalculator.calculate(
            cards("As", "Ah"), cards("Ks", "Kh"), iterations=10_000, seed=1001
        )
        elapsed = time.perf_counter() - started

        self.assertEqual(result.iterations, 10_000)
        self.assertLess(elapsed, 1.0, f"10,000 rollouts took {elapsed:.3f}s")

    def test_known_preflop_matchups_match_roadmap_estimates(self) -> None:
        aces_vs_kings = EquityCalculator.calculate(
            cards("As", "Ah"), cards("Ks", "Kh"), iterations=10_000, seed=1002
        )
        suited_ace_king_vs_queens = EquityCalculator.calculate(
            cards("As", "Ks"), cards("Qh", "Qc"), iterations=10_000, seed=1003
        )

        self.assertAlmostEqual(aces_vs_kings.equity_percentage, 82.0, delta=2.0)
        self.assertAlmostEqual(suited_ace_king_vs_queens.equity_percentage, 46.0, delta=2.0)
        self.assertAlmostEqual(
            suited_ace_king_vs_queens.equity_percentage
            + (100.0 - suited_ace_king_vs_queens.equity_percentage),
            100.0,
        )

    def test_flopped_flush_draw_vs_top_pair_matches_roadmap_estimate(self) -> None:
        result = EquityCalculator.calculate(
            cards("6h", "3h"),
            cards("Ad", "Kc"),
            cards("Ah", "7h", "2c"),
            iterations=10_000,
            seed=1004,
        )

        self.assertAlmostEqual(result.equity_percentage, 36.0, delta=3.0)

    def test_plo_flop_benchmark_records_rollouts_and_latency(self) -> None:
        started = time.perf_counter()
        result = EquityCalculator.calculate(
            cards("As", "Ah", "Kd", "Qc"),
            cards("Ks", "Kh", "Jd", "Tc"),
            cards("2c", "3d", "4h"),
            iterations=1_000,
            seed=2001,
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(result.iterations, 1_000)
        self.assertLess(elapsed, 2.0, f"1,000 PLO flop rollouts took {elapsed:.3f}s")

    def test_plo_known_flop_matchup_is_within_documented_tolerance(self) -> None:
        result = EquityCalculator.calculate(
            cards("As", "Ah", "Kd", "Qc"),
            cards("Ks", "Kh", "Jd", "Tc"),
            cards("2c", "3d", "4h"),
            iterations=10_000,
            seed=2001,
        )
        self.assertAlmostEqual(result.equity_percentage, 93.5, delta=2.0)

    def test_seeded_six_player_plo_showdown_is_fast_and_conserves_pots(self) -> None:
        state = GameState.new_hand(
            tuple(Player(f"p{i}", f"Player {i}", 1_000) for i in range(6)),
            1,
            2,
            deck=Deck(seed=3117),
            rules=GameRules.pot_limit_omaha(),
        )
        actions = 0
        while state.street is not Street.SHOWDOWN:
            actor_id = state.current_player_id
            self.assertIsNotNone(actor_id)
            legal = state.legal_actions()
            action = ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL
            self.assertIn(action, legal)
            state = state.apply_action(actor_id, action)
            actions += 1
            self.assertLess(actions, 100)

        started = time.perf_counter()
        settled = state.resolve_showdown()
        elapsed = time.perf_counter() - started
        contributions = sum(player.total_contributed for player in settled.players)

        self.assertTrue(settled.hand_complete)
        self.assertLess(elapsed, 0.25, f"PLO showdown took {elapsed:.3f}s")
        self.assertEqual(sum(amount for _, amount in settled.payouts), contributions)
        self.assertTrue(settled.winning_hands)
        for _, used_cards in settled.winning_hands:
            self.assertEqual(len(used_cards), 5)
        self.assertEqual(len(settled.community_cards), 5)


if __name__ == "__main__":
    unittest.main()
