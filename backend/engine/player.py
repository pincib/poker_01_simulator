"""Player state and table positions for Texas Hold'em."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from backend.engine.card import Card


class Position(str, Enum):
    """Common positions at a six-handed Hold'em table."""

    SMALL_BLIND = "SB"
    BIG_BLIND = "BB"
    UNDER_THE_GUN = "UTG"
    HIJACK = "HJ"
    CUTOFF = "CO"
    BUTTON = "BTN"


@dataclass(frozen=True, slots=True)
class Player:
    """Immutable per-hand state for Hold'em or Omaha; chips are whole units."""

    id: str
    name: str
    stack: int
    current_bet: int = 0
    hole_cards: tuple[Card, ...] = field(default_factory=tuple)
    is_active: bool = True
    is_all_in: bool = False
    position: Position | None = None
    total_contributed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Player id must be a non-empty string.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Player name must be a non-empty string.")
        self._validate_chips("stack", self.stack)
        self._validate_chips("current_bet", self.current_bet)
        self._validate_chips("total_contributed", self.total_contributed)
        if self.current_bet > self.total_contributed and self.total_contributed == 0:
            object.__setattr__(self, "total_contributed", self.current_bet)
        object.__setattr__(self, "hole_cards", tuple(self.hole_cards))
        if len(self.hole_cards) not in (0, 2, 4):
            raise ValueError("A player must have zero, two, or four hole cards.")
        if any(not isinstance(card, Card) for card in self.hole_cards):
            raise TypeError("Hole cards must contain Card instances.")
        if len(set(self.hole_cards)) != len(self.hole_cards):
            raise ValueError("A player's hole cards must be distinct.")
        if self.position is not None:
            object.__setattr__(self, "position", Position(self.position))
        if self.is_all_in and self.stack != 0:
            raise ValueError("An all-in player must have no chips remaining.")
        if self.stack == 0 and self.is_active:
            object.__setattr__(self, "is_all_in", True)
        if self.current_bet > self.total_contributed:
            raise ValueError("The current street bet cannot exceed total hand contributions.")

    @staticmethod
    def _validate_chips(field_name: str, amount: int) -> None:
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError(f"{field_name} must be a non-negative integer.")

    def commit(self, amount: int) -> Player:
        """Return a new player state with chips committed to this hand."""
        self._validate_chips("amount", amount)
        if not self.is_active or self.is_all_in:
            raise ValueError("Inactive or all-in players cannot commit chips.")
        if amount > self.stack:
            raise ValueError("A player cannot commit more chips than their stack.")
        remaining = self.stack - amount
        return replace(
            self,
            stack=remaining,
            current_bet=self.current_bet + amount,
            total_contributed=self.total_contributed + amount,
            is_all_in=remaining == 0,
        )

    def refund(self, amount: int) -> Player:
        """Return uncalled chips to the stack without changing other contributions."""
        self._validate_chips("amount", amount)
        if amount > self.current_bet or amount > self.total_contributed:
            raise ValueError("A refund cannot exceed the player's committed chips.")
        remaining = self.stack + amount
        return replace(
            self,
            stack=remaining,
            current_bet=self.current_bet - amount,
            total_contributed=self.total_contributed - amount,
            is_all_in=False if remaining else self.is_all_in,
        )

    def receive(self, amount: int) -> Player:
        """Return a new player state after receiving chips from a pot."""
        self._validate_chips("amount", amount)
        return replace(self, stack=self.stack + amount, is_all_in=False)

    def with_hole_cards(self, cards: tuple[Card, ...]) -> Player:
        """Return a copy with a validated Hold'em or Omaha private hand."""
        return replace(self, hole_cards=tuple(cards))

    def reset_bet(self) -> Player:
        """Return a copy with the street bet cleared for a new street."""
        return replace(self, current_bet=0)

    def fold(self) -> Player:
        """Return a folded copy while retaining cards for hand history."""
        if self.is_all_in:
            raise ValueError("An all-in player cannot fold.")
        if not self.is_active:
            raise ValueError("A folded player cannot fold again.")
        return replace(self, is_active=False)
