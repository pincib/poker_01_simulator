"""Game-variant rules kept separate from players and game flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GameVariant(str, Enum):
    TEXAS_HOLDEM = "texas_holdem"
    POT_LIMIT_OMAHA = "pot_limit_omaha"


class BettingStructure(str, Enum):
    NO_LIMIT = "no_limit"
    POT_LIMIT = "pot_limit"


@dataclass(frozen=True, slots=True)
class GameRules:
    """Immutable rules configuration for a supported poker variant."""

    variant: GameVariant
    betting_structure: BettingStructure
    hole_card_count: int
    min_players: int = 2
    max_players: int = 6

    def __post_init__(self) -> None:
        object.__setattr__(self, "variant", GameVariant(self.variant))
        object.__setattr__(self, "betting_structure", BettingStructure(self.betting_structure))
        if self.hole_card_count not in (2, 4):
            raise ValueError("Supported variants use two or four hole cards.")
        if self.min_players < 2 or self.max_players < self.min_players or self.max_players > 10:
            raise ValueError("Player limits must satisfy 2 <= min <= max <= 10.")
        if self.variant is GameVariant.TEXAS_HOLDEM and (
            self.hole_card_count != 2 or self.betting_structure is not BettingStructure.NO_LIMIT
        ):
            raise ValueError("Texas Hold'em uses two hole cards and no-limit betting.")
        if self.variant is GameVariant.POT_LIMIT_OMAHA and (
            self.hole_card_count != 4 or self.betting_structure is not BettingStructure.POT_LIMIT
        ):
            raise ValueError("Pot-Limit Omaha uses four hole cards and pot-limit betting.")

    @classmethod
    def texas_holdem(cls) -> GameRules:
        return cls(GameVariant.TEXAS_HOLDEM, BettingStructure.NO_LIMIT, hole_card_count=2)

    @classmethod
    def pot_limit_omaha(cls) -> GameRules:
        return cls(GameVariant.POT_LIMIT_OMAHA, BettingStructure.POT_LIMIT, hole_card_count=4)
