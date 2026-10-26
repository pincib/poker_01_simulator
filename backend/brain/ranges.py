"""Six-max preflop opening ranges and action-conditioned range helpers."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from types import MappingProxyType
from typing import Mapping, Sequence

from backend.engine.card import Card, Rank, Suit
from backend.engine.player import Position

_RANKS_DESC = tuple(range(int(Rank.ACE), int(Rank.TWO) - 1, -1))
_RANK_CODES = {rank: Rank(rank).code for rank in _RANKS_DESC}
_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)
_POSITIONS = {
    Position.UNDER_THE_GUN: 0.15,
    Position.HIJACK: 0.19,
    Position.CUTOFF: 0.27,
    Position.BUTTON: 0.45,
    Position.SMALL_BLIND: 0.38,
    # The BB is a blind-defence range rather than an opening range. Its broad
    # baseline allows the AI to make a reasonable decision if it is first to act.
    Position.BIG_BLIND: 0.45,
}


def _class_keys() -> tuple[str, ...]:
    keys = []
    for first_index, high in enumerate(_RANKS_DESC):
        for low in _RANKS_DESC[first_index:]:
            if high == low:
                keys.append(f"{_RANK_CODES[high]}{_RANK_CODES[low]}")
            else:
                keys.extend((f"{_RANK_CODES[high]}{_RANK_CODES[low]}s", f"{_RANK_CODES[high]}{_RANK_CODES[low]}o"))
    return tuple(keys)


_CLASS_KEYS = _class_keys()


def _combo_count(hand_class: str) -> int:
    return 6 if len(hand_class) == 2 else (4 if hand_class.endswith("s") else 12)


def _class_score(hand_class: str) -> float:
    high = next(rank for rank, code in _RANK_CODES.items() if code == hand_class[0])
    low = next(rank for rank, code in _RANK_CODES.items() if code == hand_class[1])
    if high == low:
        return 45 + high * 3.2
    gap = high - low - 1
    suited = hand_class.endswith("s")
    score = high * 2.45 + low * 1.05 + (3.6 if suited else 0)
    if gap == 0:
        score += 2.4
    elif gap == 1:
        score += 1.4
    elif gap >= 3:
        score -= (gap - 2) * 1.4
    if high == 14 and low >= 10:
        score += 2.0
    if high <= 9 and gap <= 2 and suited:
        score += 1.0
    return score


@dataclass(frozen=True, slots=True)
class PreflopRange:
    position: Position
    frequencies: Mapping[str, float]
    target_percentage: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", Position(self.position))
        copied = dict(self.frequencies)
        if any(key not in _CLASS_KEYS for key in copied):
            raise ValueError("Range contains an unknown starting-hand class.")
        if any(not 0 <= frequency <= 1 for frequency in copied.values()):
            raise ValueError("Hand-class frequencies must be between 0 and 1.")
        object.__setattr__(self, "frequencies", MappingProxyType(copied))

    @property
    def combo_count(self) -> float:
        return sum(_combo_count(key) * frequency for key, frequency in self.frequencies.items())

    @property
    def actual_percentage(self) -> float:
        return self.combo_count / 1326 * 100

    @property
    def matrix(self) -> tuple[tuple[float, ...], ...]:
        """13x13 matrix: pairs on diagonal, suited above, offsuit below."""
        matrix = []
        for row, high in enumerate(_RANKS_DESC):
            values = []
            for column, low in enumerate(_RANKS_DESC):
                key = f"{_RANK_CODES[high]}{_RANK_CODES[low]}" if row == column else (
                    f"{_RANK_CODES[high]}{_RANK_CODES[low]}s" if row < column
                    else f"{_RANK_CODES[low]}{_RANK_CODES[high]}o"
                )
                values.append(self.frequencies.get(key, 0.0))
            matrix.append(tuple(values))
        return tuple(matrix)

    def frequency_for(self, hole_cards: Sequence[Card]) -> float:
        hand_class = starting_hand_class(hole_cards)
        return self.frequencies.get(hand_class, 0.0)

    def contains(self, hole_cards: Sequence[Card]) -> bool:
        return self.frequency_for(hole_cards) > 0

    def to_combos(self, blocked_cards: Sequence[Card] = ()) -> tuple[tuple[Card, Card], ...]:
        """Expand included classes into concrete combos, removing known blockers."""
        blocked = set(blocked_cards)
        combos_by_class: dict[str, list[tuple[Card, Card]]] = {}
        for first, second in combinations(_DECK, 2):
            if first in blocked or second in blocked:
                continue
            key = starting_hand_class((first, second))
            if self.frequencies.get(key, 0) > 0:
                combos_by_class.setdefault(key, []).append((first, second))
        combos: list[tuple[Card, Card]] = []
        for key, class_combos in combos_by_class.items():
            frequency = self.frequencies[key]
            take = min(len(class_combos), round(len(class_combos) * frequency))
            combos.extend(class_combos[:take])
        return tuple(combos)

    def filtered_by_action(self, action: object) -> PreflopRange:
        """Apply a transparent heuristic filter based on the latest action."""
        action_value = getattr(action, "value", action)
        action_value = str(action_value).lower()
        strength_by_action = {
            "raise": 0.68,
            "bet": 0.72,
            "all_in": 0.55,
            "call": 0.88,
            "check": 1.0,
        }
        fraction = strength_by_action.get(action_value)
        if fraction is None:
            return self
        existing_count = self.combo_count
        return _range_by_combo_count(
            self.position,
            self.frequencies,
            existing_count * fraction,
            self.target_percentage,
        )


def starting_hand_class(hole_cards: Sequence[Card]) -> str:
    """Return a standard class such as ``AKs``, ``AKo``, or ``QQ``."""
    cards = tuple(hole_cards)
    if len(cards) != 2 or any(not isinstance(card, Card) for card in cards):
        raise ValueError("Starting-hand classification requires two Card instances.")
    if cards[0] == cards[1]:
        raise ValueError("A starting hand cannot contain duplicate cards.")
    high, low = sorted((int(card.rank) for card in cards), reverse=True)
    first, second = _RANK_CODES[high], _RANK_CODES[low]
    if high == low:
        return first + second
    return first + second + ("s" if cards[0].suit is cards[1].suit else "o")


def get_opening_range(position: Position | str, target_percentage: float | None = None) -> PreflopRange:
    """Build the standard six-max positional opening matrix.

    Class frequencies are filled strongest-first to hit the target combo
    percentage exactly; the marginal class is mixed at a partial frequency.
    """
    position = Position(position)
    target = _POSITIONS[position] if target_percentage is None else target_percentage / 100
    if not 0 < target <= 1:
        raise ValueError("Target opening percentage must be greater than 0 and at most 100.")
    return _range_by_combo_count(position, {}, target * 1326, target * 100)


def _range_by_combo_count(
    position: Position,
    source_frequencies: Mapping[str, float],
    target_combos: float,
    target_percentage: float,
) -> PreflopRange:
    candidates = [key for key in _CLASS_KEYS if source_frequencies.get(key, 0) > 0]
    if not source_frequencies:
        candidates = list(_CLASS_KEYS)
    candidates.sort(key=lambda key: (_class_score(key), key), reverse=True)
    frequencies: dict[str, float] = {}
    remaining = target_combos
    for key in candidates:
        if remaining <= 0:
            break
        base_frequency = source_frequencies.get(key, 1.0)
        available_combos = _combo_count(key) * base_frequency
        fraction = min(base_frequency, remaining / _combo_count(key))
        frequencies[key] = fraction
        remaining -= min(available_combos, remaining)
    target = target_percentage if target_percentage <= 1 else target_percentage / 100
    return PreflopRange(position, frequencies, target * 100)


OPENING_RANGES: Mapping[Position, PreflopRange] = MappingProxyType({
    position: get_opening_range(position) for position in _POSITIONS
})
