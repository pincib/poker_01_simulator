"""Evidence-based turn outs and blocker analysis for four-card PLO."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Sequence

from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator
from backend.brain.board_texture import BoardTextureClassifier

_FULL_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)


@dataclass(frozen=True, slots=True)
class OmahaWrapAnalysis:
    """One-card Omaha draw analysis with explicit uncertainty and evidence."""

    straight_outs: tuple[Card, ...]
    clean_outs: tuple[Card, ...]
    dirty_outs: tuple[Card, ...]
    is_wrap: bool
    flush_outs: tuple[Card, ...] = ()
    improvement_outs: tuple[Card, ...] = ()
    nut_outs: tuple[Card, ...] = ()
    non_nut_outs: tuple[Card, ...] = ()
    nut_flush_outs: tuple[Card, ...] = ()
    unverified_outs: tuple[Card, ...] = ()
    villain_blocked_straight_outs: tuple[Card, ...] = ()
    villain_blocked_flush_outs: tuple[Card, ...] = ()
    board_pairing_cards: tuple[Card, ...] = ()
    hero_blocker_cards: tuple[Card, ...] = ()
    hero_blocked_opponent_combos: int = 0
    opponent_redraws: tuple[tuple[Card, tuple[Card, ...]], ...] = ()
    board_texture: tuple[tuple[str, object], ...] = ()
    evidence: tuple[str, ...] = ()

    @property
    def out_count(self) -> int:
        return len(self.straight_outs)

    def to_dict(self) -> dict[str, object]:
        def codes(cards: Sequence[Card]) -> list[str]:
            return [card.code for card in cards]

        return {
            "straight_outs": codes(self.straight_outs),
            "flush_outs": codes(self.flush_outs),
            "improvement_outs": codes(self.improvement_outs),
            "clean_outs": codes(self.clean_outs),
            "dirty_outs": codes(self.dirty_outs),
            "unverified_outs": codes(self.unverified_outs),
            "nut_outs": codes(self.nut_outs),
            "non_nut_outs": codes(self.non_nut_outs),
            "nut_flush_outs": codes(self.nut_flush_outs),
            "villain_blocked_straight_outs": codes(self.villain_blocked_straight_outs),
            "villain_blocked_flush_outs": codes(self.villain_blocked_flush_outs),
            "board_pairing_cards": codes(self.board_pairing_cards),
            "hero_blocker_cards": codes(self.hero_blocker_cards),
            "hero_blocked_opponent_combos": self.hero_blocked_opponent_combos,
            "opponent_redraws": [
                {"turn_card": turn.code, "river_cards": codes(rivers)}
                for turn, rivers in self.opponent_redraws
            ],
            "is_wrap": self.is_wrap,
            "board_texture": dict(self.board_texture),
            "evidence": list(self.evidence),
        }

    @property
    def coach_summary(self) -> str:
        if not self.evidence:
            return "No one-card Omaha draw was identified on this street."
        return " ".join(self.evidence)


class OmahaWrapDetector:
    """Analyze straight, flush and made-hand improvement outs under exact-two rules."""

    @staticmethod
    def analyze(
        hole_4: Sequence[Card],
        board: Sequence[Card],
        villain_hole_4: Sequence[Card] | None = None,
    ) -> OmahaWrapAnalysis:
        hero = _validate_hand(hole_4, "Hero hole cards")
        community = _validate_board(board)
        villain = _validate_hand(villain_hole_4, "Villain hole cards") if villain_hole_4 is not None else ()
        if len(set(hero + community + villain)) != len(hero) + len(community) + len(villain):
            raise ValueError("Hero, villain, and board cards must all be distinct.")
        texture = BoardTextureClassifier.classify(community)
        if len(community) == 5:
            return OmahaWrapAnalysis((), (), (), False, board_texture=_texture_dict(texture),
                                     evidence=("River reached: no card remains to improve the hand.",))

        blocked = set(hero + community + villain)
        board_ranks = {int(card.rank) for card in community}
        pairing_cards = tuple(card for card in _FULL_DECK if card not in blocked and int(card.rank) in board_ranks)
        current_rank = HandEvaluator.evaluate_plo(hero, community)
        already_has_straight = HandEvaluator.has_plo_straight(hero, community)
        already_has_flush = _has_plo_flush(hero, community)
        candidates: list[Card] = []
        straights: list[Card] = []
        flushes: list[Card] = []
        improvements: list[Card] = []
        nut_outs: list[Card] = []
        non_nut_outs: list[Card] = []
        nut_flushes: list[Card] = []
        opponent_redraws: list[tuple[Card, tuple[Card, ...]]] = []

        for card in _FULL_DECK:
            if card in blocked:
                continue
            next_board = community + (card,)
            rank = HandEvaluator.evaluate_plo(hero, next_board)
            straight = not already_has_straight and HandEvaluator.has_plo_straight(hero, next_board)
            flush = not already_has_flush and _has_plo_flush(hero, next_board)
            improves = rank < current_rank
            if straight:
                straights.append(card)
            if flush:
                flushes.append(card)
            if improves:
                improvements.append(card)
            if not (straight or flush or improves):
                continue
            candidates.append(card)

            best_opponent_rank = _best_possible_plo_rank(hero, next_board, villain)
            if villain:
                best_opponent_rank = min(best_opponent_rank, HandEvaluator.evaluate_plo(villain, next_board))
            is_nut = rank <= best_opponent_rank
            if is_nut:
                nut_outs.append(card)
                if flush:
                    nut_flushes.append(card)
            else:
                non_nut_outs.append(card)

            if villain:
                redraw_cards = _opponent_redraw_cards(hero, villain, next_board)
                if redraw_cards:
                    opponent_redraws.append((card, redraw_cards))

        draw_outs = tuple(dict.fromkeys(straights + flushes))
        if villain:
            clean: list[Card] = []
            dirty: list[Card] = []
            for out in draw_outs:
                if _is_clean_through_river(hero, villain, community + (out,)):
                    clean.append(out)
                else:
                    dirty.append(out)
            unverified: list[Card] = []
        else:
            clean = []
            dirty = []
            unverified = list(draw_outs)

        blocked_straights = tuple(
            card for card in villain
            if not already_has_straight and card not in community and HandEvaluator.has_plo_straight(hero, community + (card,))
        ) if villain else ()
        blocked_flushes = tuple(
            card for card in villain
            if not already_has_flush and card not in community and _has_plo_flush(hero, community + (card,))
        ) if villain else ()
        unseen_before_hero = 52 - len(community)
        hero_blocked_combos = _choose(unseen_before_hero, 4) - _choose(unseen_before_hero - 4, 4)

        evidence = [
            f"{len(straights)} distinct available cards make a legal straight on the next street under exact-two-hole/three-board rules."
        ]
        if straights:
            evidence.append(
                f"This is {'a wrap' if len(straights) > 8 else 'not a wrap'} by the study-guide threshold (>8 straight outs)."
            )
        evidence.append(f"{len(flushes)} available next cards make a legal flush; {len(nut_flushes)} are nut flushes on that resulting board.")
        evidence.append(f"{len(improvements)} cards improve the current Omaha rank; {len(nut_outs)} produce the best possible Omaha hand on that board and {len(non_nut_outs)} do not.")
        if villain:
            evidence.append(f"Against the exposed four-card hand, {len(clean)} outs stay ahead through every possible river; {len(dirty)} are dirty because the opponent can tie or overtake.")
            evidence.append(f"The exposed hand blocks {len(blocked_straights)} straight-completing card(s) and {len(blocked_flushes)} flush-completing card(s).")
            evidence.append(f"After an improving turn, the opponent has redraws on {sum(len(rivers) for _, rivers in opponent_redraws)} turn/river runout(s) across {len(opponent_redraws)} turn card(s).")
        else:
            evidence.append("No opponent hand was exposed, so clean/dirty status is unverified; nut status describes the resulting board, not a guaranteed showdown win.")
        evidence.append(
            f"Board texture: {'paired' if texture.paired else 'unpaired'}, {texture.suit_pattern.value}, "
            f"{'connected' if texture.low_connected else 'not strongly connected'}; board-only cards are never used as an Omaha hand."
        )
        evidence.append(
            f"Your four known cards remove {hero_blocked_combos} possible four-card opponent combinations before action/range weighting."
        )
        evidence.append(
            f"{len(pairing_cards)} unseen cards pair a board rank; paired-board runouts are checked separately for full-house/quads redraws."
        )

        return OmahaWrapAnalysis(
            straight_outs=tuple(straights),
            clean_outs=tuple(clean),
            dirty_outs=tuple(dirty),
            is_wrap=len(straights) > 8,
            flush_outs=tuple(flushes),
            improvement_outs=tuple(improvements),
            nut_outs=tuple(nut_outs),
            non_nut_outs=tuple(non_nut_outs),
            nut_flush_outs=tuple(nut_flushes),
            unverified_outs=tuple(unverified),
            villain_blocked_straight_outs=blocked_straights,
            villain_blocked_flush_outs=blocked_flushes,
            board_pairing_cards=pairing_cards,
            hero_blocker_cards=hero,
            hero_blocked_opponent_combos=hero_blocked_combos,
            opponent_redraws=tuple(opponent_redraws),
            board_texture=_texture_dict(texture),
            evidence=tuple(evidence),
        )


def detect_omaha_wrap(
    hole_4: Sequence[Card],
    board: Sequence[Card],
    villain_hole_4: Sequence[Card] | None = None,
) -> OmahaWrapAnalysis:
    """Convenience function for :meth:`OmahaWrapDetector.analyze`."""
    return OmahaWrapDetector.analyze(hole_4, board, villain_hole_4)


def _best_possible_plo_rank(
    hero: Sequence[Card], board: Sequence[Card], villain: Sequence[Card],
) -> int:
    """Best legal five-card hand any opponent could make on this board."""
    available = [card for card in _FULL_DECK if card not in set(hero + tuple(board) + tuple(villain))]
    best = 7463
    for hole_pair in combinations(available, 2):
        for board_triple in combinations(board, 3):
            best = min(best, HandEvaluator.evaluate_5(hole_pair + board_triple))
            if best == 1:
                return best
    return best


def _has_plo_flush(hole: Sequence[Card], board: Sequence[Card]) -> bool:
    hole_suits: dict[Suit, int] = {}
    for card in hole:
        hole_suits[card.suit] = hole_suits.get(card.suit, 0) + 1
    board_suits: dict[Suit, int] = {}
    for card in board:
        board_suits[card.suit] = board_suits.get(card.suit, 0) + 1
    return any(hole_suits.get(suit, 0) >= 2 and count >= 3 for suit, count in board_suits.items())


def _is_clean_through_river(hero: Sequence[Card], villain: Sequence[Card], turn_board: Sequence[Card]) -> bool:
    if len(turn_board) == 5:
        return HandEvaluator.evaluate_plo(hero, turn_board) < HandEvaluator.evaluate_plo(villain, turn_board)
    known = set(hero + villain + tuple(turn_board))
    rivers = [card for card in _FULL_DECK if card not in known]
    return all(
        HandEvaluator.evaluate_plo(hero, tuple(turn_board) + (river,))
        < HandEvaluator.evaluate_plo(villain, tuple(turn_board) + (river,))
        for river in rivers
    )


def _opponent_redraw_cards(hero: Sequence[Card], villain: Sequence[Card], turn_board: Sequence[Card]) -> tuple[Card, ...]:
    if len(turn_board) == 5:
        return ()
    known = set(hero + villain + tuple(turn_board))
    hero_rank = HandEvaluator.evaluate_plo(hero, turn_board)
    return tuple(
        river for river in _FULL_DECK
        if river not in known
        and HandEvaluator.evaluate_plo(villain, tuple(turn_board) + (river,))
        <= HandEvaluator.evaluate_plo(hero, tuple(turn_board) + (river,))
        and hero_rank < HandEvaluator.evaluate_plo(villain, turn_board)
    )


def _texture_dict(texture: object) -> tuple[tuple[str, object], ...]:
    return (
        ("paired", texture.paired),
        ("suit_pattern", texture.suit_pattern.value),
        ("low_connected", texture.low_connected),
        ("wetness_score", texture.wetness_score),
    )


def _choose(n: int, r: int) -> int:
    return comb(n, r) if n >= r else 0


def _validate_hand(cards: Sequence[Card] | None, label: str) -> tuple[Card, ...]:
    if cards is None:
        raise ValueError(f"{label} are required.")
    hand = tuple(cards)
    if len(hand) != 4:
        raise ValueError(f"{label} must contain exactly four cards.")
    if any(not isinstance(card, Card) for card in hand):
        raise TypeError(f"{label} must contain Card instances.")
    if len(set(hand)) != 4:
        raise ValueError(f"{label} must be distinct.")
    return hand


def _validate_board(board: Sequence[Card]) -> tuple[Card, ...]:
    community = tuple(board)
    if len(community) not in (3, 4, 5):
        raise ValueError("Omaha draw analysis requires a flop, turn, or river board.")
    if any(not isinstance(card, Card) for card in community):
        raise TypeError("Board must contain Card instances.")
    if len(set(community)) != len(community):
        raise ValueError("Board cards must be distinct.")
    return community
