"""A standard deck with cryptographically secure shuffling."""

from __future__ import annotations

import random

from backend.engine.card import Card, Rank, Suit


class Deck:
    """Mutable draw pile containing each standard playing card exactly once."""

    def __init__(self, *, shuffle: bool = True, seed: int | None = None) -> None:
        """Create a deck; an explicit seed makes simulations reproducible."""
        self._random = random.SystemRandom() if seed is None else random.Random(seed)
        self._cards: list[Card] = []
        self.reset(shuffle=shuffle)

    @property
    def cards(self) -> tuple[Card, ...]:
        """Cards remaining in the draw pile, from the next card to the last."""
        return tuple(self._cards)

    @property
    def remaining(self) -> int:
        return len(self._cards)

    def shuffle(self) -> None:
        """Shuffle the remaining cards using ``SystemRandom``'s secure RNG."""
        self._random.shuffle(self._cards)

    def draw(self) -> Card:
        """Remove and return the next card, raising ``IndexError`` when empty."""
        if not self._cards:
            raise IndexError("Cannot draw from an empty deck.")
        return self._cards.pop()

    def deal(self, count: int) -> tuple[Card, ...]:
        """Draw ``count`` cards as a tuple; fail without drawing if unavailable."""
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("Card count must be a non-negative integer.")
        if count > self.remaining:
            raise ValueError(f"Cannot deal {count} cards; only {self.remaining} remain.")
        return tuple(self.draw() for _ in range(count))

    def reset(self, *, shuffle: bool = True) -> None:
        """Restore all 52 cards and shuffle unless ``shuffle=False``."""
        self._cards = [Card(rank, suit) for suit in Suit for rank in Rank]
        if shuffle:
            self.shuffle()
