"""Seedable Monte Carlo equity for Hold'em and four-card PLO."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator

_FULL_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)


@dataclass(frozen=True, slots=True)
class EquityResult:
    """Win, tie, and loss frequencies plus expected share of the pot."""

    win_percentage: float
    tie_percentage: float
    loss_percentage: float
    iterations: int
    equity_share_override: float | None = None

    @property
    def equity_percentage(self) -> float:
        """Expected pot share, dividing each tie equally among its winners."""
        if self.equity_share_override is not None:
            return self.equity_share_override
        return self.win_percentage + self.tie_percentage / 2


class EquityCalculator:
    """Estimate heads-up or multiway equity for two-card or four-card hands."""

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
        hero = _validate_hole(hero_hole, "Hero hole cards")
        community = _validate_board(board)
        _validate_iterations(iterations)
        if villain_hole is not None and villain_range is not None:
            raise ValueError("Provide either a villain hand or a villain range, not both.")
        _validate_unique(hero, community, message="Hero and board cards must all be distinct.")
        hole_count = len(hero)
        known = set(hero + community)

        fixed_villain = _validate_cards(villain_hole, hole_count, "Villain hole cards") if villain_hole is not None else None
        if fixed_villain is not None:
            _validate_unique(hero, community, fixed_villain, message="Hero, villain, and board cards must all be distinct.")
            known.update(fixed_villain)
        if len(hero) + len(fixed_villain or ()) + 5 > 52:
            raise ValueError("Known hands and a complete board exceed the deck capacity.")

        legal_range: tuple[tuple[Card, ...], ...] | None = None
        if villain_range is not None:
            legal_range = _legal_range(villain_range, hole_count, known, "Villain range")

        rng = random.Random(seed)
        needed_board = 5 - len(community)
        wins = ties = losses = 0
        equity_total = 0.0
        for _ in range(iterations):
            if fixed_villain is not None:
                villain = fixed_villain
            elif legal_range is not None:
                villain = rng.choice(legal_range)
            else:
                villain = tuple(rng.sample([card for card in _FULL_DECK if card not in known], hole_count))
            blocked = known.union(villain)
            runout = rng.sample([card for card in _FULL_DECK if card not in blocked], needed_board)
            final_board = community + tuple(runout)
            hero_rank = _rank(hero, final_board)
            villain_rank = _rank(villain, final_board)
            if hero_rank < villain_rank:
                wins += 1
                equity_total += 1.0
            elif hero_rank == villain_rank:
                ties += 1
                equity_total += 0.5
            else:
                losses += 1

        return _result(wins, ties, losses, equity_total, iterations)

    @staticmethod
    def calculate_multiway(
        hero_hole: Sequence[Card],
        opponent_ranges: Sequence[Sequence[Sequence[Card]] | None],
        board: Sequence[Card] = (),
        *,
        iterations: int = 1_000,
        seed: int | None = None,
    ) -> EquityResult:
        """Estimate hero share versus independent ranges with collision-free deals.

        Each concrete opponent combo must use the same two- or four-card hand
        size as Hero. Use ``None`` for a uniform random opponent hand.
        """
        hero = _validate_hole(hero_hole, "Hero hole cards")
        community = _validate_board(board)
        _validate_iterations(iterations)
        _validate_unique(hero, community, message="Hero and board cards must all be distinct.")
        if not opponent_ranges:
            raise ValueError("At least one opponent range is required.")

        hole_count = len(hero)
        if len(hero) + len(opponent_ranges) * hole_count + 5 > 52:
            raise ValueError("The requested players and complete board exceed the deck capacity.")
        known = set(hero + community)
        legal_ranges: list[tuple[tuple[Card, ...], ...] | None] = []
        for index, opponent_range in enumerate(opponent_ranges, start=1):
            legal_ranges.append(
                None if opponent_range is None else
                _legal_range(opponent_range, hole_count, known, f"Opponent {index} range")
            )

        rng = random.Random(seed)
        needed_board = 5 - len(community)
        wins = ties = losses = 0
        equity_total = 0.0
        for _ in range(iterations):
            villains = _sample_opponents(legal_ranges, known, hole_count, rng)
            blocked = known.union(card for hand in villains for card in hand)
            runout = rng.sample([card for card in _FULL_DECK if card not in blocked], needed_board)
            final_board = community + tuple(runout)
            hero_rank = _rank(hero, final_board)
            ranks = [_rank(hand, final_board) for hand in villains]
            best = min((hero_rank, *ranks))
            winner_count = int(hero_rank == best) + sum(rank == best for rank in ranks)
            if hero_rank != best:
                losses += 1
            elif winner_count == 1:
                wins += 1
                equity_total += 1.0
            else:
                ties += 1
                equity_total += 1.0 / winner_count

        return _result(wins, ties, losses, equity_total, iterations)


def _rank(hole: Sequence[Card], board: Sequence[Card]) -> int:
    if len(hole) == 4:
        return HandEvaluator.evaluate_plo(hole, board)
    if len(board) < 3:
        # A preflop Hold'em deal has no legal five-card evaluation yet; complete
        # a private board per rollout before ranking via the standard evaluator.
        raise ValueError("Hold'em hand ranking requires at least three board cards.")
    if len(board) == 3:
        # On the flop a five-card hand is not complete; pad by separately
        # completed random board cards at the caller, so do not use this path.
        raise ValueError("Hold'em flop ranking requires turn and river cards.")
    return HandEvaluator.evaluate_7(tuple(hole) + tuple(board))


def _result(wins: int, ties: int, losses: int, equity_total: float, iterations: int) -> EquityResult:
    scale = 100.0 / iterations
    return EquityResult(wins * scale, ties * scale, losses * scale, iterations, equity_total * scale)


def _validate_iterations(iterations: int) -> None:
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations <= 0:
        raise ValueError("Iterations must be a positive integer.")


def _validate_hole(cards: Sequence[Card], label: str) -> tuple[Card, ...]:
    result = tuple(cards)
    if len(result) not in (2, 4):
        raise ValueError(f"{label} must contain exactly two or four cards.")
    return _validate_cards(result, len(result), label)


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


def _validate_unique(*groups: Sequence[Card], message: str) -> None:
    cards = tuple(card for group in groups for card in group)
    if len(cards) != len(set(cards)):
        raise ValueError(message)


def _legal_range(
    candidates: Sequence[Sequence[Card]], hole_count: int, blocked: set[Card], label: str,
) -> tuple[tuple[Card, ...], ...]:
    legal = []
    for combo in candidates:
        hand = _validate_cards(combo, hole_count, f"Each {label.lower()} hand")
        if not blocked.intersection(hand):
            legal.append(hand)
    if not legal:
        raise ValueError(f"{label} has no hands remaining after card removal.")
    return tuple(legal)


def _sample_opponents(
    ranges: Sequence[tuple[tuple[Card, ...], ...] | None],
    known: set[Card],
    hole_count: int,
    rng: random.Random,
) -> tuple[tuple[Card, ...], ...]:
    chosen: list[tuple[Card, ...] | None] = [None] * len(ranges)
    order = sorted((i for i, value in enumerate(ranges) if value is not None), key=lambda i: len(ranges[i] or ()))

    def assign(position: int, used: set[Card]) -> bool:
        if position == len(order):
            for index, candidate_range in enumerate(ranges):
                if candidate_range is None:
                    available = [card for card in _FULL_DECK if card not in used]
                    if len(available) < hole_count:
                        return False
                    hand = tuple(rng.sample(available, hole_count))
                    chosen[index] = hand
                    used.update(hand)
            return True
        index = order[position]
        options = [hand for hand in ranges[index] or () if not used.intersection(hand)]
        rng.shuffle(options)
        for hand in options:
            chosen[index] = hand
            if assign(position + 1, used.union(hand)):
                return True
        chosen[index] = None
        return False

    if not assign(0, set(known)):
        raise ValueError("Opponent ranges have no mutually compatible hand combinations.")
    return tuple(hand for hand in chosen if hand is not None)


def calculate_equity(
    hero_hole: Sequence[Card], villain_hole: Sequence[Card] | None = None,
    board: Sequence[Card] = (), **kwargs: object,
) -> EquityResult:
    """Convenience function mirroring :meth:`EquityCalculator.calculate`."""
    return EquityCalculator.calculate(hero_hole, villain_hole, board, **kwargs)
