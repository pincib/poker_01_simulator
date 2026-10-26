"""Run the roadmap's deterministic equity benchmarks and 50k-hand self-play."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

# Make ``python scripts/run_phase7_verification.py`` work from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.brain.equity import EquityCalculator
from backend.engine.card import Card
from backend.simulation.self_play import SelfPlaySimulator


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands", type=int, default=50_000, help="Self-play hands (default: 50000).")
    parser.add_argument("--iterations", type=int, default=10_000, help="Monte Carlo samples per matchup.")
    parser.add_argument("--skip-self-play", action="store_true", help="Run only the equity benchmarks.")
    args = parser.parse_args()
    if args.hands <= 0 or args.iterations <= 0:
        parser.error("--hands and --iterations must be positive.")

    scenarios = (
        ("AA vs KK preflop", cards("As", "Ah"), cards("Ks", "Kh"), (), 82.0, 2.0),
        ("AKs vs QQ preflop", cards("As", "Ks"), cards("Qh", "Qc"), (), 46.0, 2.0),
        (
            "Flush draw vs top pair on flop",
            cards("6h", "3h"),
            cards("Ad", "Kc"),
            cards("Ah", "7h", "2c"),
            36.0,
            3.0,
        ),
    )
    benchmark_elapsed = None
    for index, (label, hero, villain, board, target, tolerance) in enumerate(scenarios):
        started = time.perf_counter()
        result = EquityCalculator.calculate(
            hero,
            villain,
            board,
            iterations=args.iterations,
            seed=1001 + index,
        )
        elapsed = time.perf_counter() - started
        if result.iterations != args.iterations or abs(result.equity_percentage - target) > tolerance:
            raise SystemExit(
                f"FAIL {label}: got {result.equity_percentage:.2f}% equity, expected "
                f"{target:.1f}% ± {tolerance:.1f}%"
            )
        if index == 0:
            benchmark_elapsed = elapsed
        print(f"PASS {label}: {result.equity_percentage:.2f}% equity ({elapsed:.3f}s)")

    assert benchmark_elapsed is not None
    if args.iterations == 10_000 and benchmark_elapsed >= 1.0:
        raise SystemExit(f"FAIL 10,000-rollout benchmark took {benchmark_elapsed:.3f}s (limit: 1.000s)")

    if not args.skip_self_play:
        started = time.perf_counter()
        result = SelfPlaySimulator(seed=20261026).run(args.hands)
        elapsed = time.perf_counter() - started
        if not result.chips_conserved:
            raise SystemExit("FAIL self-play: chips plus collected rake do not balance")
        if args.hands == 50_000 and result.rake_collected <= 0:
            raise SystemExit("FAIL self-play: expected rake was not collected")
        print(
            f"PASS self-play: {result.hands:,} hands, {result.actions:,} actions, "
            f"{result.showdowns:,} runouts, {result.hands_won_by_fold:,} fold wins; "
            f"rake={result.rake_collected:,}, chips conserved, max actions/hand="
            f"{result.max_actions_in_a_hand} ({elapsed:.2f}s)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
