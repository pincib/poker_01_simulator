"""Cactus Kev-style lookup evaluator for five- and seven-card Hold'em hands.

Scores follow the classic 1..7462 ordering: lower is stronger. The tables are
generated once from rank equivalence classes, then each five-card evaluation
uses either a prime-product lookup or a suited-rank-mask lookup.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations, combinations_with_replacement
from math import prod
from typing import Iterable, Sequence

from backend.engine.card import Card, Rank

_RANKS = tuple(range(int(Rank.TWO), int(Rank.ACE) + 1))
_STRAIGHT_SETS = {
    frozenset(range(high - 4, high + 1)): high for high in range(6, 15)
}
_STRAIGHT_SETS[frozenset((14, 2, 3, 4, 5))] = 5
_PRIMES = {rank: Rank(rank).prime for rank in _RANKS}
_RANK_NAMES = {
    2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
    8: "Eight", 9: "Nine", 10: "Ten", 11: "Jack", 12: "Queen",
    13: "King", 14: "Ace",
}
_PLURAL_RANK_NAMES = {
    2: "Twos", 3: "Threes", 4: "Fours", 5: "Fives", 6: "Sixes",
    7: "Sevens", 8: "Eights", 9: "Nines", 10: "Tens", 11: "Jacks",
    12: "Queens", 13: "Kings", 14: "Aces",
}

# Categories are ordered strongest to weakest. Each tie-break tuple is also
# ordered strongest first, so sorting these signatures creates classic Kev ranks.
_CATEGORY_NAMES = (
    "Straight Flush", "Four of a Kind", "Full House", "Flush", "Straight",
    "Three of a Kind", "Two Pair", "One Pair", "High Card",
)


def _rank_signature(ranks: Iterable[int], *, flush: bool = False) -> tuple[int, tuple[int, ...]]:
    counts = Counter(ranks)
    distinct = sorted(counts, reverse=True)
    straight_high = _STRAIGHT_SETS.get(frozenset(distinct)) if len(distinct) == 5 else None

    if flush and straight_high is not None:
        return 0, (straight_high,)
    if 4 in counts.values():
        quad = next(rank for rank, count in counts.items() if count == 4)
        kicker = next(rank for rank, count in counts.items() if count == 1)
        return 1, (quad, kicker)
    if sorted(counts.values()) == [2, 3]:
        trip = next(rank for rank, count in counts.items() if count == 3)
        pair = next(rank for rank, count in counts.items() if count == 2)
        return 2, (trip, pair)
    if flush:
        return 3, tuple(distinct)
    if straight_high is not None:
        return 4, (straight_high,)
    if 3 in counts.values():
        trip = next(rank for rank, count in counts.items() if count == 3)
        kickers = tuple(sorted((rank for rank, count in counts.items() if count == 1), reverse=True))
        return 5, (trip, *kickers)
    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if len(pairs) == 2:
        kicker = next(rank for rank, count in counts.items() if count == 1)
        return 6, (pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = tuple(sorted((rank for rank, count in counts.items() if count == 1), reverse=True))
        return 7, (pair, *kickers)
    return 8, tuple(distinct)


def _build_lookup_tables() -> tuple[dict[int, int], dict[int, int], dict[tuple[int, tuple[int, ...]], int]]:
    signatures: set[tuple[int, tuple[int, ...]]] = set()
    rank_multisets = []
    for ranks in combinations_with_replacement(_RANKS, 5):
        if max(Counter(ranks).values()) > 4:
            continue
        rank_multisets.append(ranks)
        signatures.add(_rank_signature(ranks))

    flush_rank_masks: dict[int, tuple[int, ...]] = {}
    for ranks in combinations(_RANKS, 5):
        rank_mask = sum(1 << (rank + 14) for rank in ranks)
        flush_rank_masks[rank_mask] = ranks
        signatures.add(_rank_signature(ranks, flush=True))

    ordered = sorted(signatures, key=lambda signature: (signature[0], tuple(-rank for rank in signature[1])))
    if len(ordered) != 7462:
        raise RuntimeError(f"Evaluator table generation produced {len(ordered)} ranks, expected 7462.")
    scores = {signature: index for index, signature in enumerate(ordered, start=1)}

    prime_product_lookup = {
        prod(_PRIMES[rank] for rank in ranks): scores[_rank_signature(ranks)]
        for ranks in rank_multisets
    }
    flush_lookup = {
        rank_mask: scores[_rank_signature(ranks, flush=True)]
        for rank_mask, ranks in flush_rank_masks.items()
    }
    return prime_product_lookup, flush_lookup, scores


_NON_FLUSH_LOOKUP, _FLUSH_LOOKUP, _SIGNATURE_TO_SCORE = _build_lookup_tables()


def _straight_high(ranks: set[int]) -> int | None:
    if 14 in ranks:
        ranks = ranks | {1}
    return next((high for high in range(14, 4, -1) if set(range(high - 4, high + 1)) <= ranks), None)


def _evaluate_7_unchecked(hand: Sequence[Card]) -> int:
    """Rank seven cards directly, avoiding all 21 five-card subsets."""
    counts = Counter(int(card.rank) for card in hand)
    ranks = set(counts)

    suit_ranks: dict[int, set[int]] = {}
    for card in hand:
        suit_ranks.setdefault(card.bitwise & 0xF000, set()).add(int(card.rank))
    for suited in suit_ranks.values():
        if len(suited) >= 5:
            straight_high = _straight_high(suited)
            if straight_high is not None:
                return _SIGNATURE_TO_SCORE[(0, (straight_high,))]

    quads = [rank for rank, count in counts.items() if count == 4]
    if quads:
        quad = max(quads)
        kicker = max(rank for rank in ranks if rank != quad)
        return _SIGNATURE_TO_SCORE[(1, (quad, kicker))]

    trips = sorted((rank for rank, count in counts.items() if count >= 3), reverse=True)
    pairs = sorted((rank for rank, count in counts.items() if count >= 2), reverse=True)
    if trips:
        trip = trips[0]
        pair = next((rank for rank in pairs if rank != trip), None)
        if pair is not None:
            return _SIGNATURE_TO_SCORE[(2, (trip, pair))]

    flushes = [suited for suited in suit_ranks.values() if len(suited) >= 5]
    if flushes:
        top_five = max(tuple(sorted(suited, reverse=True)[:5]) for suited in flushes)
        return _SIGNATURE_TO_SCORE[(3, top_five)]

    straight_high = _straight_high(ranks)
    if straight_high is not None:
        return _SIGNATURE_TO_SCORE[(4, (straight_high,))]

    if trips:
        trip = trips[0]
        kickers = tuple(sorted((rank for rank in ranks if rank != trip), reverse=True)[:2])
        return _SIGNATURE_TO_SCORE[(5, (trip, *kickers))]

    if len(pairs) >= 2:
        high_pair, low_pair = pairs[:2]
        kicker = max(rank for rank in ranks if rank not in (high_pair, low_pair))
        return _SIGNATURE_TO_SCORE[(6, (high_pair, low_pair, kicker))]

    if pairs:
        pair = pairs[0]
        kickers = tuple(sorted((rank for rank in ranks if rank != pair), reverse=True)[:3])
        return _SIGNATURE_TO_SCORE[(7, (pair, *kickers))]

    high_cards = tuple(sorted(ranks, reverse=True)[:5])
    return _SIGNATURE_TO_SCORE[(8, high_cards)]


def _validated_cards(cards: Sequence[Card], expected_count: int) -> tuple[Card, ...]:
    result = tuple(cards)
    if len(result) != expected_count:
        raise ValueError(f"Expected exactly {expected_count} cards, received {len(result)}.")
    if any(not isinstance(card, Card) for card in result):
        raise TypeError("Hand evaluation requires Card instances.")
    if len({card.bitwise for card in result}) != len(result):
        raise ValueError("A hand cannot contain duplicate cards.")
    return result


def _evaluate_5_unchecked(hand: Sequence[Card]) -> int:
    first = hand[0].bitwise
    suit_mask = first & 0xF000
    is_flush = True
    rank_mask = first & 0x1FFF0000
    prime_product = first & 0x3F
    for card in hand[1:]:
        encoded = card.bitwise
        if encoded & 0xF000 != suit_mask:
            is_flush = False
        rank_mask |= encoded & 0x1FFF0000
        prime_product *= encoded & 0x3F
    if is_flush:
        return _FLUSH_LOOKUP[rank_mask]
    return _NON_FLUSH_LOOKUP[prime_product]


class HandEvaluator:
    """Fast ranking and human-readable descriptions for standard poker hands."""

    @staticmethod
    def evaluate_5(cards: Sequence[Card]) -> int:
        """Return a classic Cactus Kev rank from 1 (best) to 7462 (worst)."""
        hand = _validated_cards(cards, 5)
        return _evaluate_5_unchecked(hand)

    @classmethod
    def evaluate_7(cls, cards: Sequence[Card]) -> int:
        """Return the best five-card rank from seven cards using direct rank masks."""
        hand = _validated_cards(cards, 7)
        return _evaluate_7_unchecked(hand)

    @staticmethod
    def evaluate_plo(hole_4: Sequence[Card], board_5: Sequence[Card]) -> int:
        """Evaluate Omaha using exactly two of four hole cards and three board cards.

        Flop, turn, and river boards are accepted so the same evaluator can power
        showdown, equity, and draw analysis. A complete board checks all 60
        legal combinations (C(4, 2) * C(5, 3)).
        """
        score, _ = HandEvaluator.evaluate_plo_with_hand(hole_4, board_5)
        return score

    @staticmethod
    def evaluate_plo_with_hand(
        hole_4: Sequence[Card], board_5: Sequence[Card]
    ) -> tuple[int, tuple[Card, ...]]:
        """Return the best Omaha score and its exact two-hole/three-board cards."""
        hole = tuple(hole_4)
        board = tuple(board_5)
        if len(hole) != 4:
            raise ValueError(f"Omaha requires exactly four hole cards, received {len(hole)}.")
        if len(board) not in (3, 4, 5):
            raise ValueError("Omaha evaluation requires a flop, turn, or five-card board.")
        if any(not isinstance(card, Card) for card in hole + board):
            raise TypeError("Omaha evaluation requires Card instances.")
        if len(set(hole + board)) != len(hole) + len(board):
            raise ValueError("Omaha hole and board cards must all be distinct.")

        best_score = 7463
        best_hand: tuple[Card, ...] = ()
        for hole_pair in combinations(hole, 2):
            for board_triple in combinations(board, 3):
                candidate = hole_pair + board_triple
                score = _evaluate_5_unchecked(candidate)
                if score < best_score:
                    best_score, best_hand = score, candidate
                    if score == 1:
                        return score, best_hand
        return best_score, best_hand

    @staticmethod
    def has_plo_straight(hole_4: Sequence[Card], board_5: Sequence[Card]) -> bool:
        """Return whether any legal two-hole/three-board combo is a straight.

        Unlike best-hand ranking, this also recognizes a straight that is
        outranked by a flush made from a different legal combination.
        """
        hole = tuple(hole_4)
        board = tuple(board_5)
        if len(hole) != 4:
            raise ValueError("Omaha requires exactly four hole cards.")
        if len(board) not in (3, 4, 5):
            raise ValueError("Omaha evaluation requires a flop, turn, or five-card board.")
        if any(not isinstance(card, Card) for card in hole + board):
            raise TypeError("Omaha evaluation requires Card instances.")
        if len(set(hole + board)) != len(hole) + len(board):
            raise ValueError("Omaha hole and board cards must all be distinct.")
        return any(
            _is_straight_score(_evaluate_5_unchecked(hole_pair + board_triple))
            for hole_pair in combinations(hole, 2)
            for board_triple in combinations(board, 3)
        )

    @classmethod
    def evaluate_7_with_hand(cls, cards: Sequence[Card]) -> tuple[int, tuple[Card, ...]]:
        """Return the best seven-card score and its winning five-card subset."""
        hand = _validated_cards(cards, 7)
        best_score = 7463
        best_hand: tuple[Card, ...] = ()
        for combo in combinations(hand, 5):
            score = _evaluate_5_unchecked(combo)
            if score < best_score:
                best_score, best_hand = score, combo
                if score == 1:
                    break
        return best_score, best_hand

    @classmethod
    def describe(cls, cards: Sequence[Card]) -> str:
        """Describe the best five-card hand in a five-, six-, or seven-card set."""
        hand = tuple(cards)
        if len(hand) == 5:
            best = _validated_cards(hand, 5)
        elif len(hand) == 7:
            _, best = cls.evaluate_7_with_hand(hand)
        elif len(hand) == 6:
            _validated_cards(hand, 6)
            best = min(combinations(hand, 5), key=cls.evaluate_5)
        else:
            raise ValueError("A hand description requires five, six, or seven cards.")
        return cls._describe_five(best)

    @staticmethod
    def _describe_five(cards: Sequence[Card]) -> str:
        counts = Counter(int(card.rank) for card in cards)
        grouped = sorted(counts, key=lambda rank: (counts[rank], rank), reverse=True)
        rank_desc = sorted(counts, reverse=True)
        flush = len({card.suit for card in cards}) == 1
        straight_high = _STRAIGHT_SETS.get(frozenset(counts)) if len(counts) == 5 else None

        if flush and straight_high == 14:
            return "Royal Flush"
        if flush and straight_high is not None:
            return f"Straight Flush, {_RANK_NAMES[straight_high]}-High"
        if counts[grouped[0]] == 4:
            quad = grouped[0]
            kicker = next(rank for rank in rank_desc if rank != quad)
            return f"Four of a Kind, {_PLURAL_RANK_NAMES[quad]} ({_RANK_NAMES[kicker]} Kicker)"
        if sorted(counts.values()) == [2, 3]:
            trip = next(rank for rank, count in counts.items() if count == 3)
            pair = next(rank for rank, count in counts.items() if count == 2)
            return f"Full House, {_PLURAL_RANK_NAMES[trip]} full of {_PLURAL_RANK_NAMES[pair]}"
        if flush:
            return f"Flush, {_RANK_NAMES[rank_desc[0]]}-High"
        if straight_high is not None:
            return f"Straight, {_RANK_NAMES[straight_high]}-High"
        if counts[grouped[0]] == 3:
            trip = grouped[0]
            kickers = sorted((rank for rank in counts if rank != trip), reverse=True)
            return f"Three of a Kind, {_PLURAL_RANK_NAMES[trip]} ({_format_kickers(kickers)})"
        pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
        if len(pairs) == 2:
            kicker = next(rank for rank, count in counts.items() if count == 1)
            return (
                f"Two Pair, {_PLURAL_RANK_NAMES[pairs[0]]} and {_PLURAL_RANK_NAMES[pairs[1]]}, "
                f"{_RANK_NAMES[kicker]} Kicker"
            )
        if pairs:
            pair = pairs[0]
            kickers = sorted((rank for rank, count in counts.items() if count == 1), reverse=True)
            return f"Pair of {_PLURAL_RANK_NAMES[pair]} ({_format_kickers(kickers)})"
        return f"{_RANK_NAMES[rank_desc[0]]}-High ({_format_kickers(rank_desc[1:])})"


def _format_kickers(ranks: Iterable[int]) -> str:
    names = [_RANK_NAMES[rank] for rank in ranks]
    if len(names) == 1:
        return f"{names[0]} Kicker"
    if len(names) == 2:
        return f"{names[0]} and {names[1]} Kickers"
    if len(names) > 2:
        return f"{', '.join(names[:-1])}, and {names[-1]} Kickers"
    return "No Kickers"


def _is_straight_score(score: int) -> bool:
    return score <= 10 or 1600 <= score <= 1609
