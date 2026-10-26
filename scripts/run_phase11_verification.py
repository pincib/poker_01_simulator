"""Reproducible PLO functional, self-play, and performance audit (roadmap 11)."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path
import sys
import time

# Allow invocation as ``python scripts/run_phase11_verification.py`` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.brain.equity import EquityCalculator
from backend.engine.card import Card
from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player
from backend.engine.rules import GameRules, GameVariant
from backend.simulation.self_play import SelfPlaySimulator


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


def benchmark_showdown() -> float:
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
        if actor_id is None:
            raise RuntimeError("Showdown fixture lost its action actor.")
        legal = state.legal_actions()
        action = ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL
        if action not in legal:
            raise RuntimeError(f"Unexpected action set in showdown fixture: {legal!r}.")
        state = state.apply_action(actor_id, action)
        actions += 1
        if actions > 100:
            raise RuntimeError("Showdown fixture exceeded its action bound.")
    started = time.perf_counter()
    settled = state.resolve_showdown()
    elapsed = time.perf_counter() - started
    contributions = sum(player.total_contributed for player in settled.players)
    if not settled.hand_complete or sum(amount for _, amount in settled.payouts) != contributions:
        raise RuntimeError("Showdown failed terminal-state or chip-conservation audit.")
    if not settled.winning_hands or any(len(used) != 5 for _, used in settled.winning_hands):
        raise RuntimeError("Showdown did not record five-card Omaha winning hands.")
    return elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-hands", type=int, default=2_000)
    parser.add_argument("--iterations", type=int, default=10_000)
    args = parser.parse_args()
    if args.max_hands < 100 or args.iterations < 1_000:
        parser.error("--max-hands must be >=100 and --iterations must be >=1000")

    print(f"Environment: {platform.platform()} | Python {platform.python_version()}")
    matchup = (
        cards("As", "Ah", "Kd", "Qc"),
        cards("Ks", "Kh", "Jd", "Tc"),
        cards("2c", "3d", "4h"),
    )
    equity_started = time.perf_counter()
    equity = EquityCalculator.calculate(*matchup, iterations=args.iterations, seed=2001)
    equity_elapsed = time.perf_counter() - equity_started
    if args.iterations == 10_000 and abs(equity.equity_percentage - 93.5) > 2.0:
        raise RuntimeError(f"Known PLO matchup outside tolerance: {equity.equity_percentage:.2f}%.")
    print(
        f"PLO equity: {equity.equity_percentage:.2f}% over {equity.iterations:,} rollouts "
        f"in {equity_elapsed:.3f}s (seed=2001)"
    )
    showdown_elapsed = benchmark_showdown()
    if showdown_elapsed >= 0.25:
        raise RuntimeError(f"PLO showdown exceeded 0.25s: {showdown_elapsed:.3f}s.")
    print(f"Six-player PLO showdown: {showdown_elapsed:.4f}s (seed=3117, payouts conserved)")

    tiers = sorted({min(100, args.max_hands), min(500, args.max_hands), args.max_hands})
    previous = None
    for count in tiers:
        started = time.perf_counter()
        result = SelfPlaySimulator(
            seed=20261026,
            variant=GameVariant.POT_LIMIT_OMAHA,
            player_count=6,
            starting_stack=200,
            small_blind=1,
            big_blind=2,
        ).run(hands=count)
        elapsed = time.perf_counter() - started
        if not result.chips_conserved or result.deadlocks or result.rake_collected:
            raise RuntimeError(f"Self-play accounting/deadlock audit failed at {count} hands.")
        if result.showdowns + result.hands_won_by_fold != result.hands:
            raise RuntimeError(f"Unclassified hand endings at {count} hands.")
        if previous is not None and (
            result.ties < previous.ties
            or result.all_in_hands < previous.all_in_hands
            or result.fold_actions < previous.fold_actions
        ):
            raise RuntimeError("Seeded self-play prefix counters were not monotonic.")
        print(
            f"Self-play {count:>5,}: hands={result.hands}, showdowns={result.showdowns}, "
            f"ties={result.ties}, all-in hands/events={result.all_in_hands}/{result.all_in_events}, "
            f"fold actions={result.fold_actions}, fold wins={result.hands_won_by_fold}, "
            f"max actions={result.max_actions_in_a_hand}, rake={result.rake_collected}, "
            f"chips conserved={result.chips_conserved}, deadlocks={result.deadlocks}, "
            f"elapsed={elapsed:.3f}s"
        )
        previous = result

    assert previous is not None
    if not previous.ties or not previous.all_in_hands or not previous.fold_actions:
        raise RuntimeError("Largest seeded run did not exercise ties, all-ins, and folds.")
    print("Phase 11 verification: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
