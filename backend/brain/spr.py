"""Stack-to-pot ratio calculations for postflop decisions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class StackToPotRatio:
    effective_stack: float
    flop_pot: float
    value: float


class SPRCalculator:
    """Calculate SPR using the effective stack between Hero and one opponent."""

    @staticmethod
    def calculate(player_stack: float, opponent_stack: float, flop_pot: float) -> StackToPotRatio:
        hero = _non_negative_amount("Player stack", player_stack)
        villain = _non_negative_amount("Opponent stack", opponent_stack)
        pot = _non_negative_amount("Flop pot", flop_pot)
        if pot == 0:
            raise ValueError("Flop pot must be greater than zero to calculate SPR.")
        effective = min(hero, villain)
        return StackToPotRatio(effective, pot, effective / pot)


def calculate_spr(player_stack: float, opponent_stack: float, flop_pot: float) -> float:
    """Return the effective-stack-to-flop-pot ratio."""
    return SPRCalculator.calculate(player_stack, opponent_stack, flop_pot).value


def _non_negative_amount(label: str, amount: float) -> float:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not isfinite(amount) or amount < 0:
        raise ValueError(f"{label} must be a non-negative number.")
    return float(amount)
