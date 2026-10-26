"""Pot odds and break-even equity calculations."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PotOdds:
    call_amount: float
    pot_before_call: float
    required_equity_percentage: float


class PotOddsCalculator:
    """Calculate the equity needed for a call to break even immediately."""

    @staticmethod
    def calculate(call_amount: float, pot_before_call: float) -> PotOdds:
        call = _non_negative_amount("Call amount", call_amount)
        pot = _non_negative_amount("Pot before call", pot_before_call)
        total_after_call = pot + call
        required_equity = 0.0 if total_after_call == 0 else call / total_after_call * 100
        return PotOdds(call, pot, required_equity)


def calculate_pot_odds(call_amount: float, pot_before_call: float) -> float:
    """Return break-even call equity as a percentage from 0 to 100."""
    return PotOddsCalculator.calculate(call_amount, pot_before_call).required_equity_percentage


def _non_negative_amount(label: str, amount: float) -> float:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not isfinite(amount) or amount < 0:
        raise ValueError(f"{label} must be a non-negative number.")
    return float(amount)
