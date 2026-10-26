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
    equity_share_override: float | None = None

    @property
    def equity_percentage(self) -> float:
        """Expected share of the pot, counting each tie as half a win."""
        if self.equity_share_override is not None:
            return self.equity_share_override
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

    @staticmethod
    def calculate_multiway(
        hero_hole: Sequence[Card],
        opponent_ranges: Sequence[Sequence[Sequence[Card]]],
        board: Sequence[Card] = (),
        *,
        iterations: int = 1_000,
        seed: int | None = None,
    ) -> EquityResult:
        """Estimate hero's pot share against two or more independent hand ranges.

        Opponent combinations are sampled without card collisions. Ties split
        the equity by the number of tied players rather than treating every tie
        as a heads-up half share.
        """
        hero = _validate_cards(hero_hole, 2, "Hero hole cards")
        community = _validate_board(board)
        if len(set(hero + community)) != len(hero) + len(community):
            raise ValueError("Hero and board cards must all be distinct.")
        if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations <= 0:
            raise ValueError("Iterations must be a positive integer.")
        if len(opponent_ranges) < 2:
            raise ValueError("Multiway equity requires at least two opponent ranges.")

        known = set(hero + community)
        legal_ranges: list[tuple[tuple[Card, Card], ...]] = []
        for index, candidate_range in enumerate(opponent_ranges, start=1):
            candidates: list[tuple[Card, Card]] = []
            for combo in candidate_range:
                hand = _validate_cards(combo, 2, f"Opponent {index} range hand")
                if not known.intersection(hand):
                    candidates.append((hand[0], hand[1]))
            if not candidates:
                raise ValueError(f"Opponent {index} range has no hands after removing known cards.")
            legal_ranges.append(tuple(candidates))

        rng = random.Random(seed)
        needed_board = 5 - len(community)
        wins = ties = losses = 0
        equity_total = 0.0
        for _ in range(iterations):
            villain_hands = _sample_distinct_opponent_hands(legal_ranges, known, rng)
            used = known.union(card for hand in villain_hands for card in hand)
            available = [card for card in _FULL_DECK if card not in used]
            runout = rng.sample(available, needed_board)
            final_board = community + tuple(runout)
            hero_rank = HandEvaluator.evaluate_7(hero + final_board)
            ranks = [HandEvaluator.evaluate_7(hand + final_board) for hand in villain_hands]
            best_rank = min((hero_rank, *ranks))
            winners = 1 if hero_rank == best_rank else 0
            winners += sum(rank == best_rank for rank in ranks)
            if hero_rank != best_rank:
                losses += 1
            elif winners == 1:
                wins += 1
                equity_total += 1.0
            else:
                ties += 1
                equity_total += 1.0 / winners

        scale = 100.0 / iterations
        return EquityResult(
            wins * scale,
            ties * scale,
            losses * scale,
            iterations,
            equity_total * scale,
        )


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


def _sample_distinct_opponent_hands(
    candidate_ranges: Sequence[Sequence[tuple[Card, Card]]],
    known_cards: set[Card],
    rng: random.Random,
) -> tuple[tuple[Card, Card], ...]:
    """Backtrack through sampled ranges until all private cards are distinct."""
    order = sorted(range(len(candidate_ranges)), key=lambda index: len(candidate_ranges[index]))
    chosen: list[tuple[Card, Card] | None] = [None] * len(candidate_ranges)

    def choose(position: int, used: set[Card]) -> bool:
        if position == len(order):
            return True
        range_index = order[position]
        candidates = [hand for hand in candidate_ranges[range_index] if not used.intersection(hand)]
        rng.shuffle(candidates)
        for hand in candidates:
            chosen[range_index] = hand
            if choose(position + 1, used.union(hand)):
                return True
        chosen[range_index] = None
        return False

    if not choose(0, set(known_cards)):
        raise ValueError("Opponent ranges have no mutually compatible hand combinations.")
    return tuple(hand for hand in chosen if hand is not None)


def calculate_equity(
    hero_hole: Sequence[Card],
    villain_hole: Sequence[Card] | None = None,
    board: Sequence[Card] = (),
    **kwargs: object,
) -> EquityResult:
    """Convenience function mirroring :meth:`EquityCalculator.calculate`."""
    return EquityCalculator.calculate(hero_hole, villain_hole, board, **kwargs)
