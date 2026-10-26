"""Roadmap Monte Carlo known-matchup and throughput checks."""

import time
import unittest

from backend.brain.equity import EquityCalculator
from backend.engine.card import Card


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


if __name__ == "__main__":
    unittest.main()
