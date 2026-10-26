"""Pot-limit raise bounds for Omaha and other pot-limit variants."""

from __future__ import annotations


def pot_limit_max_raise(pot: int, amount_to_call: int) -> int:
    """Return the maximum street bet-to target: pot + twice the call.

    ``pot`` is the current pot before the acting player's decision and includes
    all chips already committed on the street. The returned value is the
    player's total bet-to target for that street, before stack capping.
    """
    _validate_chips("pot", pot)
    _validate_chips("amount_to_call", amount_to_call)
    return pot + 2 * amount_to_call


class PotLimitBetSizer:
    """Calculate a legal pot-size raise-to target, capped by the player's stack."""

    @staticmethod
    def maximum_raise_to(
        pot: int,
        amount_to_call: int,
        *,
        player_current_bet: int = 0,
        player_stack: int | None = None,
    ) -> int:
        _validate_chips("player_current_bet", player_current_bet)
        maximum = pot_limit_max_raise(pot, amount_to_call)
        if player_stack is not None:
            _validate_chips("player_stack", player_stack)
            maximum = min(maximum, player_current_bet + player_stack)
        return maximum


def _validate_chips(label: str, amount: int) -> None:
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
