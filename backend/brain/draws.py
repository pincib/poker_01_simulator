"""Flush/straight draw outs and opponent-aware dirty-out estimates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Sequence

from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator

_FULL_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)
_STRAIGHT_WINDOWS = tuple(frozenset(range(low, low + 5)) for low in range(1, 11))


class StraightDrawType(str, Enum):
    NONE = "none"
    OPEN_ENDED = "open_ended"
    GUTSHOT = "gutshot"
    DOUBLE_GUTSHOT = "double_gutshot"


@dataclass(frozen=True, slots=True)
class DrawAnalysis:
    flush_draw: bool
    straight_draw: StraightDrawType
    flush_outs: tuple[Card, ...]
    straight_outs: tuple[Card, ...]
    outs: tuple[Card, ...]
    clean_outs: tuple[Card, ...]
    dirty_outs: tuple[Card, ...]

    @property
    def out_count(self) -> int:
        return len(self.outs)


class DrawDetector:
    """Identify one-card flush/straight draws and known-opponent dirty outs.

    An out is marked dirty when it improves a listed flush/straight draw but
    leaves Hero behind the specified opponent on the next-card board. Without
    known opponent cards, candidate outs are treated as provisionally clean.
    """

    @staticmethod
    def analyze(
        hero_hole: Sequence[Card],
        board: Sequence[Card],
        villain_hole: Sequence[Card] | None = None,
    ) -> DrawAnalysis:
        hero = _validate_hand(hero_hole, "Hero hole cards")
        community = tuple(board)
        if len(community) not in (3, 4, 5):
            raise ValueError("Draw analysis requires a flop, turn, or river board.")
        if any(not isinstance(card, Card) for card in community):
            raise TypeError("Board must contain Card instances.")
        villain = _validate_hand(villain_hole, "Villain hole cards") if villain_hole is not None else ()
        known = hero + community + villain
        if len(set(known)) != len(known):
            raise ValueError("Hero, villain, and board cards must all be distinct.")

        if len(community) == 5:
            return DrawAnalysis(False, StraightDrawType.NONE, (), (), (), (), ())

        known_set = set(known)
        available = tuple(card for card in _FULL_DECK if card not in known_set)
        combined = hero + community
        flush_suit = next((suit for suit in Suit if sum(card.suit is suit for card in combined) == 4), None)
        flush_outs = tuple(card for card in available if card.suit is flush_suit) if flush_suit else ()

        ranks = {int(card.rank) for card in combined}
        normalized_ranks = set(ranks)
        if 14 in normalized_ranks:
            normalized_ranks.add(1)
        straight_out_ranks: set[int] = set()
        already_straight_or_better = _best_rank(combined) <= 1609
        if not already_straight_or_better:
            for window in _STRAIGHT_WINDOWS:
                missing = window - normalized_ranks
                if len(missing) == 1:
                    straight_out_ranks.update(14 if rank == 1 else rank for rank in missing)
        straight_outs = tuple(card for card in available if int(card.rank) in straight_out_ranks)
        straight_type = _classify_straight_draw(normalized_ranks, straight_out_ranks)
        flush_set = set(flush_outs)
        straight_set = set(straight_outs)
        outs = tuple(card for card in available if card in flush_set or card in straight_set)

        dirty_outs: tuple[Card, ...] = ()
        if villain:
            dirty_outs = tuple(
                card for card in outs
                if _best_rank(hero + community + (card,)) > _best_rank(villain + community + (card,))
            )
        dirty_set = set(dirty_outs)
        clean_outs = tuple(card for card in outs if card not in dirty_set)
        return DrawAnalysis(
            flush_draw=bool(flush_outs),
            straight_draw=straight_type,
            flush_outs=flush_outs,
            straight_outs=straight_outs,
            outs=outs,
            clean_outs=clean_outs,
            dirty_outs=dirty_outs,
        )


def analyze_draws(
    hero_hole: Sequence[Card],
    board: Sequence[Card],
    villain_hole: Sequence[Card] | None = None,
) -> DrawAnalysis:
    """Convenience function for :meth:`DrawDetector.analyze`."""
    return DrawDetector.analyze(hero_hole, board, villain_hole)


def _validate_hand(cards: Sequence[Card] | None, label: str) -> tuple[Card, ...]:
    if cards is None:
        raise ValueError(f"{label} are required.")
    hand = tuple(cards)
    if len(hand) != 2:
        raise ValueError(f"{label} must contain exactly two cards.")
    if any(not isinstance(card, Card) for card in hand):
        raise TypeError(f"{label} must contain Card instances.")
    if len(set(hand)) != len(hand):
        raise ValueError(f"{label} must be distinct.")
    return hand


def _best_rank(cards: Sequence[Card]) -> int:
    return min(HandEvaluator.evaluate_5(combo) for combo in combinations(cards, 5))


def _classify_straight_draw(ranks: set[int], out_ranks: set[int]) -> StraightDrawType:
    for start in range(2, 12):
        run = set(range(start, start + 4))
        low_end, high_end = start - 1, start + 4
        low_rank = 14 if low_end == 1 else low_end
        if run <= ranks and low_rank in out_ranks and high_end <= 14 and high_end in out_ranks:
            return StraightDrawType.OPEN_ENDED
    if len(out_ranks) >= 2:
        return StraightDrawType.DOUBLE_GUTSHOT
    if out_ranks:
        return StraightDrawType.GUTSHOT
    return StraightDrawType.NONE
