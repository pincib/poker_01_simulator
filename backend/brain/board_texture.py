"""Board texture labels for postflop betting decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Sequence

from backend.engine.card import Card


class SuitPattern(str, Enum):
    RAINBOW = "rainbow"
    TWO_TONE = "two_tone"
    MONOTONE = "monotone"
    FOUR_FLUSH = "four_flush"


@dataclass(frozen=True, slots=True)
class BoardTexture:
    wet: bool
    suit_pattern: SuitPattern
    has_high_card: bool
    high_card_count: int
    low_connected: bool
    paired: bool
    connectivity: int
    wetness_score: int

    @property
    def dry(self) -> bool:
        return not self.wet


class BoardTextureClassifier:
    """Classify draw density, suit layout, high cards, and low connectivity."""

    @staticmethod
    def classify(board: Sequence[Card]) -> BoardTexture:
        cards = tuple(board)
        if len(cards) not in (3, 4, 5):
            raise ValueError("Board texture requires a flop, turn, or river board.")
        if any(not isinstance(card, Card) for card in cards):
            raise TypeError("Board texture requires Card instances.")
        if len(set(cards)) != len(cards):
            raise ValueError("Board cards must be distinct.")

        rank_counts: dict[int, int] = {}
        suit_counts: dict[object, int] = {}
        for card in cards:
            rank_counts[int(card.rank)] = rank_counts.get(int(card.rank), 0) + 1
            suit_counts[card.suit] = suit_counts.get(card.suit, 0) + 1
        max_suit_count = max(suit_counts.values())
        if max_suit_count >= 4:
            suit_pattern = SuitPattern.FOUR_FLUSH
        elif max_suit_count == 3:
            suit_pattern = SuitPattern.MONOTONE
        elif max_suit_count == 2:
            suit_pattern = SuitPattern.TWO_TONE
        else:
            suit_pattern = SuitPattern.RAINBOW

        ranks = set(rank_counts)
        normalized = set(ranks)
        if 14 in normalized:
            normalized.add(1)
        connectivity = sum(
            1 for left, right in combinations(sorted(normalized), 2)
            if right - left <= 2
        )
        low_ranks = sorted(rank for rank in normalized if rank <= 9)
        low_connected = any(
            len(window) >= 3 and window[-1] - window[0] <= 4
            for size in range(3, len(low_ranks) + 1)
            for window in (low_ranks[index : index + size] for index in range(len(low_ranks) - size + 1))
        )
        high_count = sum(1 for rank in ranks if rank >= 11)
        paired = len(ranks) < len(cards)
        suit_wetness = {
            SuitPattern.RAINBOW: 0,
            SuitPattern.TWO_TONE: 1,
            SuitPattern.MONOTONE: 2,
            SuitPattern.FOUR_FLUSH: 2,
        }[suit_pattern]
        wetness = connectivity + suit_wetness - (2 if paired else 0)
        return BoardTexture(
            wet=wetness >= 3,
            suit_pattern=suit_pattern,
            has_high_card=high_count > 0,
            high_card_count=high_count,
            low_connected=low_connected,
            paired=paired,
            connectivity=connectivity,
            wetness_score=wetness,
        )


def classify_board(board: Sequence[Card]) -> BoardTexture:
    """Convenience function for :meth:`BoardTextureClassifier.classify`."""
    return BoardTextureClassifier.classify(board)
