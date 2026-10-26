"""Pot-relative bet-size recommendations for the opponent profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from backend.engine.game_state import Street
from backend.brain.board_texture import BoardTexture


class SizingOption(str, Enum):
    SMALL_CBET = "small_cbet"
    STANDARD = "standard"
    POLARIZED_OVERBET = "polarized_overbet"
    ALL_IN = "all_in"


@dataclass(frozen=True, slots=True)
class SizingRecommendation:
    option: SizingOption
    bet_to: int
    pot_fraction: float


class BetSizer:
    """Recommend a legal target bet, respecting the player's table-stakes cap."""

    @staticmethod
    def recommend(
        *,
        pot: int,
        remaining_stack: int,
        big_blind: int,
        street: Street,
        texture: BoardTexture,
        current_bet: int = 0,
        player_current_bet: int = 0,
        amount_to_call: int = 0,
        minimum_raise_size: int | None = None,
        polarized: bool = False,
    ) -> SizingRecommendation:
        for label, value in (
            ("Pot", pot), ("Remaining stack", remaining_stack), ("Big blind", big_blind),
            ("Current bet", current_bet), ("Player current bet", player_current_bet),
            ("Amount to call", amount_to_call),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{label} must be a non-negative integer.")
        if big_blind == 0:
            raise ValueError("Big blind must be greater than zero.")
        minimum_raise = minimum_raise_size if minimum_raise_size is not None else big_blind
        if not isinstance(minimum_raise, int) or isinstance(minimum_raise, bool) or minimum_raise <= 0:
            raise ValueError("Minimum raise size must be a positive integer.")
        street = Street(street)
        max_bet_to = player_current_bet + remaining_stack

        if street is Street.RIVER and polarized:
            fraction = 1.5
            pot_after_call = pot + amount_to_call
            target = (
                current_bet + round(pot_after_call * fraction)
                if amount_to_call > 0
                else player_current_bet + round(pot * fraction)
            )
            if target >= max_bet_to:
                return SizingRecommendation(SizingOption.ALL_IN, max_bet_to, fraction)
            return SizingRecommendation(SizingOption.POLARIZED_OVERBET, target, fraction)

        if street is Street.RIVER:
            fraction = 0.66 if texture.wet else 0.5
            option = SizingOption.STANDARD
        elif texture.dry:
            fraction = 0.33
            option = SizingOption.SMALL_CBET
        else:
            fraction = 0.66
            option = SizingOption.STANDARD

        if amount_to_call > 0:
            raise_increment = max(minimum_raise, round((pot + amount_to_call) * fraction))
            bet_to = current_bet + raise_increment
        else:
            bet_to = max(big_blind, round(pot * fraction))
        bet_to = min(bet_to, max_bet_to)
        if bet_to == max_bet_to and remaining_stack > 0:
            option = SizingOption.ALL_IN
        return SizingRecommendation(option, bet_to, fraction)


def recommend_bet_size(**kwargs: object) -> SizingRecommendation:
    """Convenience function for :meth:`BetSizer.recommend`."""
    return BetSizer.recommend(**kwargs)
