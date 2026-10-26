"""Contribution-layer side pots, uncalled refunds, and split-pot payouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from backend.engine.player import Player


@dataclass(frozen=True, slots=True)
class Pot:
    label: str
    amount: int
    eligible_player_ids: tuple[str, ...]
    refund_to: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligible_player_ids", tuple(self.eligible_player_ids))
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("Pot label must be a non-empty string.")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool) or self.amount < 0:
            raise ValueError("Pot amount must be a non-negative integer.")
        if len(self.eligible_player_ids) != len(set(self.eligible_player_ids)):
            raise ValueError("A player cannot appear twice in a pot's eligible list.")


@dataclass(frozen=True, slots=True)
class PotAward:
    """Auditable settlement for one contribution layer."""

    label: str
    amount: int
    eligible_player_ids: tuple[str, ...]
    winner_ids: tuple[str, ...]
    payouts: tuple[tuple[str, int], ...]
    refund_to: str | None = None


class PotManager:
    """Build pots from hand contributions and divide them at showdown.

    Folded players still contribute chips, but cannot win. A contribution
    layer funded by exactly one player is returned as an uncalled bet.
    """

    @staticmethod
    def build_side_pots(players: Sequence[Player]) -> tuple[Pot, ...]:
        ids = [player.id for player in players]
        if len(ids) != len(set(ids)):
            raise ValueError("Player ids must be unique when building pots.")
        levels = sorted({p.total_contributed for p in players if p.total_contributed > 0})
        if not levels:
            return ()

        pots: list[Pot] = []
        previous = 0
        side_number = 1
        dead_chips = 0
        for level in levels:
            contributors = [p for p in players if p.total_contributed >= level]
            amount = (level - previous) * len(contributors)
            eligible = tuple(p.id for p in contributors if p.is_active)
            previous = level
            if not eligible:
                dead_chips += amount
                continue
            if len(contributors) == 1:
                pots.append(Pot("Uncalled return", amount, eligible, refund_to=eligible[0]))
                continue
            label = "Main Pot" if not any(p.refund_to is None for p in pots) else f"Side Pot {side_number}"
            if label != "Main Pot":
                side_number += 1
            pots.append(Pot(label, amount, eligible))

        if dead_chips:
            contestable = next((i for i, pot in enumerate(pots) if pot.refund_to is None), None)
            if contestable is None:
                eligible = tuple(p.id for p in players if p.is_active)
                if not eligible:
                    raise ValueError("Dead chips cannot be awarded without an active player.")
                pots.insert(0, Pot("Main Pot", dead_chips, eligible))
            else:
                pot = pots[contestable]
                pots[contestable] = Pot(pot.label, pot.amount + dead_chips, pot.eligible_player_ids)
        return tuple(pots)

    @staticmethod
    def total(pots: Sequence[Pot]) -> int:
        return sum(pot.amount for pot in pots)

    @staticmethod
    def award(
        pots: Sequence[Pot],
        hand_rankings: Mapping[str, object],
        players: Sequence[Player],
        button_index: int,
    ) -> dict[str, int]:
        """Return each player's payout; smaller evaluator ranks are stronger."""
        if not players:
            raise ValueError("Cannot award a pot without players.")
        if not 0 <= button_index < len(players):
            raise ValueError("Button index is outside the table.")
        player_ids = {player.id for player in players}
        payouts = {player.id: 0 for player in players}
        seat_order = [p.id for p in players]
        odd_chip_order = seat_order[button_index + 1 :] + seat_order[: button_index + 1]

        for pot in pots:
            if pot.amount < 0:
                raise ValueError("Pot amount cannot be negative.")
            if pot.refund_to is not None:
                if pot.refund_to not in player_ids:
                    raise ValueError("Refund recipient is not seated at this table.")
                payouts[pot.refund_to] += pot.amount
                continue
            eligible = pot.eligible_player_ids
            if not eligible:
                raise ValueError(f"{pot.label} has no eligible players.")
            missing = [player_id for player_id in eligible if player_id not in hand_rankings]
            if missing:
                raise ValueError(f"Missing showdown rank for eligible player(s): {', '.join(missing)}.")
            best_rank = min(hand_rankings[player_id] for player_id in eligible)
            winners = {player_id for player_id in eligible if hand_rankings[player_id] == best_rank}
            share, odd_chips = divmod(pot.amount, len(winners))
            for winner in winners:
                payouts[winner] += share
            for winner in odd_chip_order:
                if odd_chips == 0:
                    break
                if winner in winners:
                    payouts[winner] += 1
                    odd_chips -= 1
        return payouts

    @staticmethod
    def award_with_details(
        pots: Sequence[Pot],
        hand_rankings: Mapping[str, object],
        players: Sequence[Player],
        button_index: int,
    ) -> tuple[dict[str, int], tuple[PotAward, ...]]:
        """Award every layer and preserve its winners and per-player shares."""
        total_payouts = {player.id: 0 for player in players}
        awards: list[PotAward] = []
        seat_order = [player.id for player in players]
        odd_chip_order = seat_order[button_index + 1 :] + seat_order[: button_index + 1]
        for pot in pots:
            if pot.refund_to is not None:
                shares = {pot.refund_to: pot.amount}
                winners = (pot.refund_to,)
            else:
                if not pot.eligible_player_ids:
                    raise ValueError(f"{pot.label} has no eligible players.")
                missing = [player_id for player_id in pot.eligible_player_ids if player_id not in hand_rankings]
                if missing:
                    raise ValueError(f"Missing showdown rank for eligible player(s): {', '.join(missing)}.")
                best_rank = min(hand_rankings[player_id] for player_id in pot.eligible_player_ids)
                winners = tuple(player_id for player_id in pot.eligible_player_ids if hand_rankings[player_id] == best_rank)
                share, odd_chips = divmod(pot.amount, len(winners))
                shares = {player_id: share for player_id in winners}
                for player_id in odd_chip_order:
                    if odd_chips == 0:
                        break
                    if player_id in shares:
                        shares[player_id] += 1
                        odd_chips -= 1
            for player_id, amount in shares.items():
                total_payouts[player_id] += amount
            awards.append(PotAward(
                label=pot.label,
                amount=pot.amount,
                eligible_player_ids=pot.eligible_player_ids,
                winner_ids=winners,
                payouts=tuple((player_id, shares[player_id]) for player_id in seat_order if player_id in shares),
                refund_to=pot.refund_to,
            ))
        return total_payouts, tuple(awards)
