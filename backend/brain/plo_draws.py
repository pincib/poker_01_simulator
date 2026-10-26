"""One-card Omaha wrap draw outs, respecting the exact-two-hole-card rule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator

_FULL_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)


@dataclass(frozen=True, slots=True)
class OmahaWrapAnalysis:
    """Distinct next cards that make an Omaha straight, with optional blockers."""

    straight_outs: tuple[Card, ...]
    clean_outs: tuple[Card, ...]
    dirty_outs: tuple[Card, ...]
    is_wrap: bool

    @property
    def out_count(self) -> int:
        return len(self.straight_outs)


class OmahaWrapDetector:
    """Count next-card straight completions; 9+ distinct outs is a wrap draw."""

    @staticmethod
    def analyze(
        hole_4: Sequence[Card],
        board: Sequence[Card],
        villain_hole_4: Sequence[Card] | None = None,
    ) -> OmahaWrapAnalysis:
        hero = _validate_hand(hole_4, "Hero hole cards")
        community = tuple(board)
        if len(community) not in (3, 4, 5):
            raise ValueError("Omaha wrap analysis requires a flop, turn, or river board.")
        if any(not isinstance(card, Card) for card in community):
            raise TypeError("Board must contain Card instances.")
        villain = _validate_hand(villain_hole_4, "Villain hole cards") if villain_hole_4 is not None else ()
        known = hero + community + villain
        if len(set(known)) != len(known):
            raise ValueError("Hero, villain, and board cards must all be distinct.")
        if len(community) == 5:
            return OmahaWrapAnalysis((), (), (), False)

        if HandEvaluator.has_plo_straight(hero, community):
            return OmahaWrapAnalysis((), (), (), False)

        blocked = set(known)
        outs = tuple(
            card
            for card in _FULL_DECK
            if card not in blocked
            and HandEvaluator.has_plo_straight(hero, community + (card,))
        )
        dirty: tuple[Card, ...] = ()
        if villain:
            dirty = tuple(
                card
                for card in outs
                if HandEvaluator.evaluate_plo(hero, community + (card,))
                > HandEvaluator.evaluate_plo(villain, community + (card,))
            )
        dirty_set = set(dirty)
        clean = tuple(card for card in outs if card not in dirty_set)
        return OmahaWrapAnalysis(outs, clean, dirty, len(outs) >= 9)


def detect_omaha_wrap(
    hole_4: Sequence[Card],
    board: Sequence[Card],
    villain_hole_4: Sequence[Card] | None = None,
) -> OmahaWrapAnalysis:
    """Convenience function for :meth:`OmahaWrapDetector.analyze`."""
    return OmahaWrapDetector.analyze(hole_4, board, villain_hole_4)


def _validate_hand(cards: Sequence[Card] | None, label: str) -> tuple[Card, ...]:
    if cards is None:
        raise ValueError(f"{label} are required.")
    hand = tuple(cards)
    if len(hand) != 4:
        raise ValueError(f"{label} must contain exactly four cards.")
    if any(not isinstance(card, Card) for card in hand):
        raise TypeError(f"{label} must contain Card instances.")
    if len(set(hand)) != 4:
        raise ValueError(f"{label} must be distinct.")
    return hand


