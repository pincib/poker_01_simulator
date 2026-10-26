"""Card primitives for the standard 52-card poker deck."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class Suit(str, Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"

    @property
    def symbol(self) -> str:
        return {
            Suit.CLUBS: "♣",
            Suit.DIAMONDS: "♦",
            Suit.HEARTS: "♥",
            Suit.SPADES: "♠",
        }[self]

    @property
    def bitmask(self) -> int:
        return {
            Suit.CLUBS: 0x8000,
            Suit.DIAMONDS: 0x4000,
            Suit.HEARTS: 0x2000,
            Suit.SPADES: 0x1000,
        }[self]


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def code(self) -> str:
        return {**{value: str(value) for value in range(2, 10)}, 10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}[self.value]

    @property
    def prime(self) -> int:
        return (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)[self.value - 2]


@dataclass(frozen=True, slots=True)
class Card:
    """A playing card, represented by its rank and suit."""

    rank: Rank
    suit: Suit
    _bitwise: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rank", Rank(self.rank))
        object.__setattr__(self, "suit", Suit(self.suit))
        rank_index = int(self.rank) - 2
        encoded = (
            self.rank.prime
            | (rank_index << 8)
            | self.suit.bitmask
            | (1 << (rank_index + 16))
        )
        object.__setattr__(self, "_bitwise", encoded)

    @classmethod
    def from_code(cls, code: str) -> Card:
        """Parse a two-character code such as ``As``, ``Td`` or ``2c``."""
        if not isinstance(code, str) or len(code) != 2:
            raise ValueError("Card code must contain a rank and suit, for example 'As'.")
        rank_codes = {str(value): value for value in range(2, 10)}
        rank_codes.update({"T": 10, "J": 11, "Q": 12, "K": 13, "A": 14})
        try:
            return cls(Rank(rank_codes[code[0].upper()]), Suit(code[1].lower()))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid card code: {code!r}.") from exc

    @property
    def code(self) -> str:
        return f"{self.rank.code}{self.suit.value}"

    @property
    def bitwise(self) -> int:
        """Return the 32-bit Cactus Kev card encoding used by the evaluator."""
        return self._bitwise

    def __str__(self) -> str:
        return self.code
