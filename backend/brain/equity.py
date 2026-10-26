"""Monte Carlo equity calculations for two-player Texas Hold'em."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator

_FULL_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)


@dataclass(frozen=True, slots=True)
class EquityResult:
    """Win, tie, and loss frequencies from a Monte Carlo estimate."""

    win_percentage: float
    tie_percentage: float
    loss_percentage: float
    iterations: int

    @property
    def equity_percentage(self) -> float:
        """Expected share of the pot, counting each tie as half a win."""
        return self.win_percentage + self.tie_percentage / 2


class EquityCalculator:
    """Estimate Hero's showdown equity against a hand or uniform hand range."""

    @staticmethod
    def calculate(
        hero_hole: Sequence[Card],
        villain_hole: Sequence[Card] | None = None,
        board: Sequence[Card] = (),
        *,
        villain_range: Sequence[Sequence[Card]] | None = None,
        iterations: int = 10_000,
        seed: int | None = None,
    ) -> EquityResult:
        hero = _validate_cards(hero_hole, 2, "Hero hole cards")
        community = _validate_board(board)
        if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations <= 0:
            raise ValueError("Iterations must be a positive integer.")
        if villain_hole is not None and villain_range is not None:
            raise ValueError("Provide either a villain hand or a villain range, not both.")

        if len(set(hero + community)) != len(hero) + len(community):
            raise ValueError("Hero and board cards must all be distinct.")
        fixed_villain = _validate_cards(villain_hole, 2, "Villain hole cards") if villain_hole is not None else None
        known = set(hero + community + (fixed_villain or ()))
        if len(known) != len(hero) + len(community) + len(fixed_villain or ()):
            raise ValueError("Hero, villain, and board cards must all be distinct.")

        legal_range: tuple[tuple[Card, Card], ...] | None = None
        if villain_range is not None:
            candidates: list[tuple[Card, Card]] = []
            for combo in villain_range:
                hand = _validate_cards(combo, 2, "Each villain range hand")
                if len(set(hand) & known) == 0:
                    candidates.append((hand[0], hand[1]))
            if not candidates:
                raise ValueError("Villain range has no hands remaining after card removal.")
            legal_range = tuple(candidates)

        rng = random.Random(seed)
        available = [card for card in _FULL_DECK if card not in known]
        needed_board = 5 - len(community)
        wins = ties = losses = 0

        for _ in range(iterations):
            if fixed_villain is not None:
                villain = fixed_villain
                remaining = [card for card in available if card not in villain]
                runout = rng.sample(remaining, needed_board)
            elif legal_range is not None:
                villain = rng.choice(legal_range)
                remaining = [card for card in available if card not in villain]
                runout = rng.sample(remaining, needed_board)
            else:
                drawn = rng.sample(available, 2 + needed_board)
                villain = (drawn[0], drawn[1])
                runout = drawn[2:]

            final_board = community + tuple(runout)
            hero_rank = HandEvaluator.evaluate_7(hero + final_board)
            villain_rank = HandEvaluator.evaluate_7(villain + final_board)
            if hero_rank < villain_rank:
                wins += 1
            elif hero_rank == villain_rank:
                ties += 1
            else:
                losses += 1

        scale = 100.0 / iterations
        return EquityResult(wins * scale, ties * scale, losses * scale, iterations)


def _validate_cards(cards: Sequence[Card] | None, count: int, label: str) -> tuple[Card, ...]:
    if cards is None:
        raise ValueError(f"{label} are required.")
    result = tuple(cards)
    if len(result) != count:
        raise ValueError(f"{label} must contain exactly {count} cards.")
    if any(not isinstance(card, Card) for card in result):
        raise TypeError(f"{label} must contain Card instances.")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must be distinct.")
    return result


def _validate_board(board: Sequence[Card]) -> tuple[Card, ...]:
    result = tuple(board)
    if len(result) not in (0, 3, 4, 5):
        raise ValueError("Board must contain 0, 3, 4, or 5 community cards.")
    if any(not isinstance(card, Card) for card in result):
        raise TypeError("Board must contain Card instances.")
    if len(set(result)) != len(result):
        raise ValueError("Board cards must be distinct.")
    return result


def calculate_equity(
    hero_hole: Sequence[Card],
    villain_hole: Sequence[Card] | None = None,
    board: Sequence[Card] = (),
    **kwargs: object,
) -> EquityResult:
    """Convenience function mirroring :meth:`EquityCalculator.calculate`."""
    return EquityCalculator.calculate(hero_hole, villain_hole, board, **kwargs)
