"""Training feedback, bet-purpose analysis, and in-memory hand review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import combinations
from math import isfinite
from threading import RLock
from typing import Mapping, Sequence
from uuid import uuid4

from backend.brain.ai_agent import OpponentProfile
from backend.brain.equity import EquityCalculator
from backend.brain.pot_odds import PotOddsCalculator
from backend.brain.ranges import get_opening_range, starting_hand_class
from backend.brain.spr import SPRCalculator
from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionRecord, GameState, Street
from backend.engine.player import Player, Position

_FULL_DECK = tuple(Card(rank, suit) for suit in Suit for rank in Rank)


class CallAssessment(str, Enum):
    PROFITABLE = "profitable"
    UNPROFITABLE = "unprofitable"
    BREAK_EVEN = "break_even"
    NO_CALL = "no_call"


class BetPurpose(str, Enum):
    VALUE = "value"
    BLUFF = "bluff"
    POINTLESS = "pointless"


@dataclass(frozen=True, slots=True)
class CoachSnapshot:
    pot_odds_percentage: float | None
    equity_percentage: float
    win_percentage: float
    tie_percentage: float
    loss_percentage: float
    ev_call: float | None
    call_assessment: CallAssessment
    spr_value: float | None
    spr_warning: str | None
    hand_description: str | None
    advice: str
    iterations: int
    equity_source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "pot_odds_percentage": self.pot_odds_percentage,
            "equity_percentage": self.equity_percentage,
            "equity_share_percentage": self.equity_percentage,
            "win_percentage": self.win_percentage,
            "tie_percentage": self.tie_percentage,
            "loss_percentage": self.loss_percentage,
            "ev_call": self.ev_call,
            "call_assessment": self.call_assessment.value,
            "spr_value": self.spr_value,
            "spr_warning": self.spr_warning,
            "hand_description": self.hand_description,
            "advice": self.advice,
            "iterations": self.iterations,
            "equity_source": self.equity_source,
        }


@dataclass(frozen=True, slots=True)
class BetPurposeResult:
    purpose: BetPurpose
    evidence: str
    bet_amount: int
    range_size: int
    worse_hands: int
    better_hands: int
    tied_hands: int
    expected_worse_calls: float
    expected_better_folds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "purpose": self.purpose.value,
            "evidence": self.evidence,
            "bet_amount": self.bet_amount,
            "range_size": self.range_size,
            "worse_hands": self.worse_hands,
            "better_hands": self.better_hands,
            "tied_hands": self.tied_hands,
            "expected_worse_calls": round(self.expected_worse_calls, 2),
            "expected_better_folds": round(self.expected_better_folds, 2),
        }


@dataclass(frozen=True, slots=True)
class DecisionNote:
    street: str
    action: str
    chips: int
    pot_before: int
    equity_percentage: float | None = None
    pot_odds_percentage: float | None = None
    ev_call: float | None = None
    bet_purpose: str | None = None
    facing_cbet: bool = False
    out_of_position: bool = False
    rationale: str = ""
    review_question: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "street": self.street,
            "action": self.action,
            "chips": self.chips,
            "pot_before": self.pot_before,
            "equity_percentage": self.equity_percentage,
            "pot_odds_percentage": self.pot_odds_percentage,
            "ev_call": self.ev_call,
            "bet_purpose": self.bet_purpose,
            "facing_cbet": self.facing_cbet,
            "out_of_position": self.out_of_position,
            "rationale": self.rationale,
            "review_question": self.review_question,
        }


@dataclass(frozen=True, slots=True)
class HandReview:
    hand_id: str
    recorded_at: str
    hero_id: str
    hero_name: str
    hero_position: str
    starting_stack: int
    hole_cards: tuple[str, ...]
    board: tuple[str, ...]
    final_pot: int
    actions: tuple[dict[str, object], ...]
    payouts: Mapping[str, int]
    decisions: tuple[DecisionNote, ...]
    tricky: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "hand_id": self.hand_id,
            "recorded_at": self.recorded_at,
            "hero_id": self.hero_id,
            "hero_name": self.hero_name,
            "hero_position": self.hero_position,
            "starting_stack": self.starting_stack,
            "hole_cards": list(self.hole_cards),
            "board": list(self.board),
            "final_pot": self.final_pot,
            "actions": [dict(action) for action in self.actions],
            "payouts": dict(self.payouts),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "tricky": self.tricky,
        }


@dataclass(frozen=True, slots=True)
class LeakFlag:
    key: str
    title: str
    count: int
    opportunities: int
    rate_percentage: float
    message: str
    lesson: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "count": self.count,
            "opportunities": self.opportunities,
            "rate_percentage": self.rate_percentage,
            "message": self.message,
            "lesson": self.lesson,
        }


@dataclass(frozen=True, slots=True)
class WeeklyLeakReport:
    since: str
    until: str
    hands_reviewed: int
    flags: tuple[LeakFlag, ...]
    study_target: str
    weekly_plan: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "since": self.since,
            "until": self.until,
            "hands_reviewed": self.hands_reviewed,
            "flags": [flag.to_dict() for flag in self.flags],
            "study_target": self.study_target,
            "weekly_plan": list(self.weekly_plan),
        }


class CoachService:
    """Build live training feedback from known cards, ranges, and chip state."""

    @classmethod
    def analyze_state(
        cls,
        state: GameState,
        hero_id: str,
        opponent_id: str | None = None,
        *,
        iterations: int = 1_000,
        seed: int | None = None,
    ) -> CoachSnapshot:
        """Analyze a live immutable game snapshot without exposing villain cards."""
        hero = state.player_by_id(hero_id)
        if hero is None:
            raise ValueError("Hero id is not seated in this hand.")
        opponents = [player for player in state.players if player.id != hero_id and player.is_active]
        if opponent_id is not None:
            opponents = [player for player in opponents if player.id == opponent_id]
        if not opponents:
            raise ValueError("Live coach analysis requires an active opponent.")
        opponent = max(opponents, key=lambda player: player.current_bet)
        if len(opponents) > 1 and opponent_id is None:
            known = hero.hole_cards + state.community_cards
            opponent_ranges = []
            range_was_filtered = False
            for active_opponent in opponents:
                preflop_action = next((
                    record.action for record in reversed(state.action_history)
                    if record.player_id == active_opponent.id and record.street is Street.PREFLOP
                ), None)
                starting_range = get_opening_range(active_opponent.position or Position.BUTTON)
                if preflop_action is not None:
                    starting_range = starting_range.filtered_by_action(preflop_action)
                    range_was_filtered = True
                opponent_ranges.append(starting_range.to_combos(known))
            return cls.analyze_decision(
                hero_hole=hero.hole_cards,
                board=state.community_cards,
                pot=state.pot,
                call_amount=max(0, state.current_bet - hero.current_bet),
                hero_stack=hero.stack,
                opponent_stack=min(player.stack for player in opponents),
                opponent_ranges=opponent_ranges,
                big_blind=state.big_blind,
                iterations=256,
                seed=None,
                opponent_ranges_action_filtered=range_was_filtered,
            )
        preflop_action = next((
            record.action for record in reversed(state.action_history)
            if record.player_id == opponent.id and record.street is Street.PREFLOP
        ), None)
        return cls.analyze_decision(
            hero_hole=hero.hole_cards,
            board=state.community_cards,
            pot=state.pot,
            call_amount=max(0, state.current_bet - hero.current_bet),
            hero_stack=hero.stack,
            opponent_stack=opponent.stack,
            opponent_position=opponent.position or Position.BUTTON,
            opponent_last_action=preflop_action,
            big_blind=state.big_blind,
            iterations=iterations,
            seed=seed,
        )

    @staticmethod
    def analyze_decision(
        *,
        hero_hole: Sequence[Card],
        board: Sequence[Card],
        pot: int,
        call_amount: int = 0,
        hero_stack: int = 0,
        opponent_stack: int = 0,
        opponent_position: Position | str = Position.BUTTON,
        opponent_last_action: object | None = None,
        opponent_hole: Sequence[Card] | None = None,
        opponent_range: Sequence[Sequence[Card]] | None = None,
        opponent_ranges: Sequence[Sequence[Sequence[Card]]] | None = None,
        opponent_ranges_action_filtered: bool = False,
        big_blind: int = 1,
        iterations: int = 1_000,
        seed: int | None = None,
    ) -> CoachSnapshot:
        hero = _validated_cards(hero_hole, 2, "Hero hole cards")
        community = _validated_board(board)
        _non_negative_chips("Pot", pot)
        _non_negative_chips("Call amount", call_amount)
        _non_negative_chips("Hero stack", hero_stack)
        _non_negative_chips("Opponent stack", opponent_stack)
        _non_negative_chips("Big blind", big_blind)
        if big_blind == 0:
            raise ValueError("Big blind must be greater than zero.")
        if sum(value is not None for value in (opponent_hole, opponent_range, opponent_ranges)) > 1:
            raise ValueError("Provide opponent cards or one opponent range model, not multiple models.")

        blockers = hero + community
        if len(set(blockers)) != len(blockers):
            raise ValueError("Hero and board cards must all be distinct.")
        if opponent_hole is not None:
            villain = _validated_cards(opponent_hole, 2, "Opponent hole cards")
            if len(set(blockers + villain)) != len(blockers) + len(villain):
                raise ValueError("Hero, opponent, and board cards must all be distinct.")
            source = "known opponent hand"
            result = EquityCalculator.calculate(
                hero, villain_hole=villain, board=community, iterations=iterations, seed=seed
            )
        elif opponent_ranges is not None:
            if len(opponent_ranges) < 2:
                raise ValueError("Multiway analysis requires at least two opponent ranges.")
            result = EquityCalculator.calculate_multiway(
                hero,
                opponent_ranges,
                board=community,
                iterations=iterations,
                seed=seed,
            )
            source = "action-filtered multiway ranges" if opponent_ranges_action_filtered else "estimated multiway ranges"
        else:
            candidates = tuple(tuple(combo) for combo in opponent_range) if opponent_range is not None else None
            if candidates is None:
                position = Position(opponent_position)
                estimated = get_opening_range(position)
                if opponent_last_action is not None:
                    estimated = estimated.filtered_by_action(opponent_last_action)
                candidates = estimated.to_combos(blockers)
            if not candidates:
                raise ValueError("Opponent range has no hands after removing known cards.")
            source = "action-filtered opponent range" if opponent_last_action is not None else "estimated opponent range"
            result = EquityCalculator.calculate(
                hero,
                board=community,
                villain_range=candidates,
                iterations=iterations,
                seed=seed,
            )

        odds = PotOddsCalculator.calculate(call_amount, pot)
        equity_share = result.equity_percentage
        ev_call = equity_share / 100 * (pot + call_amount) - call_amount if call_amount else None
        if call_amount == 0:
            call_assessment = CallAssessment.NO_CALL
            advice = "No call price is pending. Give a bet a value or bluff reason; checking is valid when neither has evidence."
        elif equity_share > odds.required_equity_percentage:
            call_assessment = CallAssessment.PROFITABLE
            advice = "The estimated equity is above the call price. This is positive expected value before rake; future-street bets still need a plan."
        elif equity_share < odds.required_equity_percentage:
            call_assessment = CallAssessment.UNPROFITABLE
            advice = "The estimated equity is below the call price before rake and implied odds. Recheck the range and future-street plan."
        else:
            call_assessment = CallAssessment.BREAK_EVEN
            advice = "Estimated equity matches the call price before rake. The result of this hand will not change that expectation."

        description = HandEvaluator.describe(hero + community) if len(community) >= 3 else None
        spr_value: float | None = None
        warning: str | None = None
        if len(community) >= 3 and pot > 0:
            spr = SPRCalculator.calculate(hero_stack, opponent_stack, pot)
            spr_value = spr.value
            if spr_value <= 2:
                if _has_top_pair(hero, community):
                    warning = f"SPR {spr_value:.1f}: you have top pair. Plan the remaining stack using the board and opponent range before committing."
                else:
                    warning = f"SPR {spr_value:.1f}: effective stacks are close to the pot. Check hand strength and opponent range before committing."
            else:
                warning = f"SPR {spr_value:.1f}: compare the effective stack with the pot as future bets develop."

        return CoachSnapshot(
            pot_odds_percentage=odds.required_equity_percentage if call_amount else None,
            equity_percentage=equity_share,
            win_percentage=result.win_percentage,
            tie_percentage=result.tie_percentage,
            loss_percentage=result.loss_percentage,
            ev_call=ev_call,
            call_assessment=call_assessment,
            spr_value=spr_value,
            spr_warning=warning,
            hand_description=description,
            advice=advice,
            iterations=result.iterations,
            equity_source=source,
        )

    @staticmethod
    def classify_bet(
        *,
        hero_hole: Sequence[Card],
        board: Sequence[Card],
        pot: int,
        bet_amount: int,
        opponent_position: Position | str = Position.BUTTON,
        opponent_last_action: object | None = None,
        opponent_range: Sequence[Sequence[Card]] | None = None,
        opponent_profile: OpponentProfile | str = OpponentProfile.TAG,
        hero_position: Position | str = Position.BUTTON,
    ) -> BetPurposeResult:
        hero = _validated_cards(hero_hole, 2, "Hero hole cards")
        community = _validated_board(board)
        _non_negative_chips("Pot", pot)
        _non_negative_chips("Bet amount", bet_amount)
        if bet_amount == 0:
            raise ValueError("A bet purpose requires a positive bet amount.")
        profile = OpponentProfile.parse(opponent_profile)

        if not community:
            hand_class = starting_hand_class(hero)
            premium = get_opening_range(Position(hero_position), 10).frequency_for(hero) >= 0.9
            if premium:
                return BetPurposeResult(BetPurpose.VALUE, "This starting hand is in the top positional opening range.", bet_amount, 0, 1, 0, 0, 1, 0)
            if profile is OpponentProfile.NIT:
                return BetPurposeResult(BetPurpose.BLUFF, "The hand is outside the top range and a nit profile can fold better unpaired hands.", bet_amount, 0, 0, 1, 0, 0, 0.5)
            return BetPurposeResult(BetPurpose.POINTLESS, f"{hand_class} is not a premium opening hand; no clear value or fold target is modeled.", bet_amount, 0, 0, 0, 1, 0, 0)

        blockers = hero + community
        if len(set(blockers)) != len(blockers):
            raise ValueError("Hero and board cards must all be distinct.")
        if opponent_range is None:
            estimated = get_opening_range(Position(opponent_position))
            if opponent_last_action is not None:
                estimated = estimated.filtered_by_action(opponent_last_action)
            range_combos = estimated.to_combos(blockers)
        else:
            range_combos = tuple(tuple(combo) for combo in opponent_range)
        if not range_combos:
            raise ValueError("Opponent range has no hands after removing known cards.")

        hero_rank = _best_rank(hero + community)
        worse = better = tied = 0
        for combo in range_combos:
            villain = _validated_cards(combo, 2, "Opponent range hand")
            if len(set(blockers + villain)) != len(blockers) + len(villain):
                continue
            villain_rank = _best_rank(villain + community)
            if villain_rank > hero_rank:
                worse += 1
            elif villain_rank < hero_rank:
                better += 1
            else:
                tied += 1
        valid_count = worse + better + tied
        if valid_count == 0:
            raise ValueError("Opponent range has no legal hands after card removal.")

        worse_call_rate, better_fold_rate = {
            OpponentProfile.NIT: (0.34, 0.18),
            OpponentProfile.STATION: (0.88, 0.04),
            OpponentProfile.TAG: (0.58, 0.28),
            OpponentProfile.GTO: (0.52, 0.32),
        }[profile]
        size_ratio = bet_amount / max(pot, 1)
        worse_call_rate = max(0.08, worse_call_rate - 0.18 * size_ratio)
        better_fold_rate = min(0.75, better_fold_rate + 0.16 * size_ratio)
        expected_worse_calls = worse * worse_call_rate
        expected_better_folds = better * better_fold_rate
        expected_better_calls = better - expected_better_folds

        if worse and expected_worse_calls >= expected_better_calls and expected_worse_calls >= expected_better_folds:
            purpose = BetPurpose.VALUE
            evidence = f"About {worse / valid_count * 100:.0f}% of modeled hands are worse and may call."
        elif better and expected_better_folds > expected_worse_calls and expected_better_folds / valid_count >= 0.25:
            purpose = BetPurpose.BLUFF
            evidence = f"The bet needs better hands to fold; about {expected_better_folds / valid_count * 100:.0f}% of the modeled range is expected to fold better hands."
        else:
            purpose = BetPurpose.POINTLESS
            evidence = "Most continuing hands are at least as strong; few better hands are expected to fold."
        return BetPurposeResult(
            purpose, evidence, bet_amount, valid_count, worse, better, tied,
            expected_worse_calls, expected_better_folds,
        )

    @staticmethod
    def _best_rank(cards: Sequence[Card]) -> int:
        return _best_rank(cards)


class SessionTracker:
    """Thread-safe process-memory hand history and seven-day leak summaries."""

    def __init__(self) -> None:
        self._hands: dict[str, HandReview] = {}
        self._lock = RLock()

    def record_hand(
        self,
        state: GameState,
        hero_id: str,
        decisions: Sequence[DecisionNote] = (),
        *,
        recorded_at: datetime | None = None,
    ) -> HandReview:
        if not state.hand_complete:
            raise ValueError("Only completed hands can be added to session review.")
        hero = state.player_by_id(hero_id)
        if hero is None:
            raise ValueError("Hero id is not seated in this hand.")
        payouts = dict(state.payouts)
        initial_stack = hero.stack + hero.total_contributed - payouts.get(hero.id, 0)
        when = (recorded_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        actions = tuple(_action_to_dict(action) for action in state.action_history)
        record = HandReview(
            hand_id=uuid4().hex,
            recorded_at=when,
            hero_id=hero.id,
            hero_name=hero.name,
            hero_position=hero.position.value if hero.position else "unknown",
            starting_stack=initial_stack,
            hole_cards=tuple(card.code for card in hero.hole_cards),
            board=tuple(card.code for card in state.community_cards),
            final_pot=state.pot,
            actions=actions,
            payouts=payouts,
            decisions=tuple(decisions),
            tricky=_is_tricky(decisions),
        )
        with self._lock:
            self._hands[record.hand_id] = record
        return record

    def record_payload(self, payload: Mapping[str, object]) -> HandReview:
        """Record a completed hand sent by a local client integration."""
        hero_id = _required_string(payload, "hero_id")
        players_value = payload.get("players")
        if not isinstance(players_value, list) or not players_value:
            raise ValueError("Hand review requires a players list.")
        players = [item for item in players_value if isinstance(item, dict)]
        if len(players) != len(players_value):
            raise ValueError("Each player in a hand review must be an object.")
        hero_data = next((item for item in players if item.get("id") == hero_id), None)
        if hero_data is None:
            raise ValueError("Hero id is not present in the players list.")
        hole_cards = _card_codes(hero_data.get("hole_cards"), "Hero hole cards", allowed=(2,))
        board = _card_codes(payload.get("board", []), "Board cards", allowed=(0, 3, 4, 5))
        all_card_codes = list(hole_cards) + list(board)
        for player_data in players:
            if player_data is hero_data:
                continue
            other_hole = player_data.get("hole_cards", [])
            if other_hole:
                all_card_codes.extend(_card_codes(other_hole, "Player hole cards", allowed=(2,)))
        if len({Card.from_code(code) for code in all_card_codes}) != len(all_card_codes):
            raise ValueError("Cards cannot be duplicated across players and the board.")
        decisions_value = payload.get("decisions", [])
        if not isinstance(decisions_value, list):
            raise ValueError("Decisions must be a list.")
        decisions = tuple(_decision_note_from_payload(item) for item in decisions_value)
        actions_value = payload.get("actions", [])
        if not isinstance(actions_value, list) or any(not isinstance(item, dict) for item in actions_value):
            raise ValueError("Actions must be a list of objects.")
        payouts_value = payload.get("payouts", {})
        if not isinstance(payouts_value, dict):
            raise ValueError("Payouts must be an object keyed by player id.")
        payouts = {str(key): _non_negative_chips("Payout", value) for key, value in payouts_value.items()}
        recorded = _parse_datetime(payload.get("recorded_at"))
        record = HandReview(
            hand_id=uuid4().hex,
            recorded_at=recorded.isoformat(),
            hero_id=hero_id,
            hero_name=_optional_string(hero_data, "name", hero_id),
            hero_position=_optional_string(hero_data, "position", "unknown"),
            starting_stack=_non_negative_chips("Starting stack", hero_data.get("starting_stack", 0)),
            hole_cards=hole_cards,
            board=board,
            final_pot=_non_negative_chips("Final pot", payload.get("final_pot", 0)),
            actions=tuple(dict(item) for item in actions_value),
            payouts=payouts,
            decisions=decisions,
            tricky=_is_tricky(decisions),
        )
        with self._lock:
            self._hands[record.hand_id] = record
        return record

    def list_hands(self, *, since: datetime | None = None) -> tuple[HandReview, ...]:
        with self._lock:
            records = tuple(self._hands.values())
        if since is not None:
            cutoff = since.astimezone(timezone.utc)
            records = tuple(record for record in records if _parse_datetime(record.recorded_at) >= cutoff)
        return tuple(sorted(records, key=lambda record: record.recorded_at, reverse=True))

    def get_hand(self, hand_id: str) -> HandReview | None:
        with self._lock:
            return self._hands.get(hand_id)

    def weekly_leak_report(self, *, now: datetime | None = None) -> WeeklyLeakReport:
        until = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        since = until - timedelta(days=7)
        hands = self.list_hands(since=since)
        decisions = [decision for hand in hands for decision in hand.decisions]
        flags: list[LeakFlag] = []

        calls = [decision for decision in decisions if decision.action.lower() in ("call", "all_in") and decision.ev_call is not None]
        negative_calls = [decision for decision in calls if decision.ev_call is not None and decision.ev_call < 0]
        if len(calls) >= 3 and len(negative_calls) / len(calls) >= 0.30:
            rate = len(negative_calls) / len(calls) * 100
            flags.append(LeakFlag(
                "negative_ev_calls", "Calls below break-even equity", len(negative_calls), len(calls), rate,
                f"{len(negative_calls)} of {len(calls)} reviewed call decisions were below break-even equity.",
                "Lesson 05 — Work out the price of a call",
            ))

        cbet_opportunities = [decision for decision in decisions if decision.facing_cbet]
        cbet_folds = [decision for decision in cbet_opportunities if decision.action.lower() == "fold"]
        if len(cbet_opportunities) >= 3 and len(cbet_folds) / len(cbet_opportunities) >= 0.60:
            rate = len(cbet_folds) / len(cbet_opportunities) * 100
            flags.append(LeakFlag(
                "overfold_cbet", "Frequent folds to continuation bets", len(cbet_folds), len(cbet_opportunities), rate,
                f"You folded to {len(cbet_folds)} of {len(cbet_opportunities)} recorded continuation bets; review the price and board before deciding.",
                "Lessons 08–09 — Value first; review one hand properly",
            ))

        postflop_entries = [decision for decision in decisions if decision.street.lower() in ("flop", "turn", "river") and decision.action.lower() != "fold"]
        oop_entries = [decision for decision in postflop_entries if decision.out_of_position]
        if len(postflop_entries) >= 3 and len(oop_entries) / len(postflop_entries) >= 0.45:
            rate = len(oop_entries) / len(postflop_entries) * 100
            flags.append(LeakFlag(
                "out_of_position", "Review pots played out of position", len(oop_entries), len(postflop_entries), rate,
                f"{len(oop_entries)} of {len(postflop_entries)} recorded postflop entries were out of position. Check whether the entry and later-street plan were justified.",
                "Lessons 09 and 24 — Review one hand; choose one study target",
            ))

        study_target = flags[0].title if flags else (
            "Record a few hands with your decision and reason to create a useful weekly review."
        )
        return WeeklyLeakReport(
            since.isoformat(),
            until.isoformat(),
            len(hands),
            tuple(flags),
            study_target,
            (
                "Choose one repeated decision to study.",
                "Mark five relevant hands and record the price, board, action, and reason.",
                "Review one marked hand and name one alternative and one uncertainty.",
                "Write what changed and what still needs checking.",
            ),
        )


def _validated_cards(cards: Sequence[Card], count: int, label: str) -> tuple[Card, ...]:
    result = tuple(cards)
    if len(result) != count:
        raise ValueError(f"{label} must contain exactly {count} cards.")
    if any(not isinstance(card, Card) for card in result):
        raise TypeError(f"{label} must contain Card instances.")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must be distinct.")
    return result


def _validated_board(board: Sequence[Card]) -> tuple[Card, ...]:
    result = tuple(board)
    if len(result) not in (0, 3, 4, 5):
        raise ValueError("Board must contain 0, 3, 4, or 5 community cards.")
    if any(not isinstance(card, Card) for card in result):
        raise TypeError("Board must contain Card instances.")
    if len(set(result)) != len(result):
        raise ValueError("Board cards must be distinct.")
    return result


def _best_rank(cards: Sequence[Card]) -> int:
    return min(HandEvaluator.evaluate_5(combo) for combo in combinations(cards, 5))


def _has_top_pair(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    if not board:
        return False
    top_rank = max(int(card.rank) for card in board)
    return any(int(card.rank) == top_rank for card in hero)


def _non_negative_chips(label: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return value


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string.")
    return value


def _optional_string(payload: Mapping[str, object], key: str, fallback: str) -> str:
    value = payload.get(key, fallback)
    return value if isinstance(value, str) else fallback


def _card_codes(value: object, label: str, *, allowed: tuple[int, ...]) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) not in allowed:
        counts = ", ".join(str(count) for count in allowed)
        raise ValueError(f"{label} must be a list with {counts} card(s).")
    cards = tuple(Card.from_code(code) for code in value if isinstance(code, str))
    if len(cards) != len(value):
        raise ValueError(f"{label} must contain card-code strings.")
    if len(set(cards)) != len(cards):
        raise ValueError(f"{label} must be distinct.")
    return tuple(card.code for card in cards)


def _decision_note_from_payload(value: object) -> DecisionNote:
    if not isinstance(value, dict):
        raise ValueError("Each decision note must be an object.")
    return DecisionNote(
        street=_optional_string(value, "street", "unknown"),
        action=_optional_string(value, "action", "unknown"),
        chips=_non_negative_chips("Decision chips", value.get("chips", 0)),
        pot_before=_non_negative_chips("Pot before decision", value.get("pot_before", 0)),
        equity_percentage=_optional_number(value.get("equity_percentage")),
        pot_odds_percentage=_optional_number(value.get("pot_odds_percentage")),
        ev_call=_optional_number(value.get("ev_call")),
        bet_purpose=_optional_string(value, "bet_purpose", "") or None,
        facing_cbet=value.get("facing_cbet") is True,
        out_of_position=value.get("out_of_position") is True,
        rationale=_optional_string(value, "rationale", ""),
        review_question=_optional_string(value, "review_question", ""),
    )


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Decision metrics must be numeric or null.")
    return float(value)


def _parse_datetime(value: object) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise ValueError("recorded_at must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("recorded_at must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _action_to_dict(record: ActionRecord) -> dict[str, object]:
    return {
        "player_id": record.player_id,
        "street": record.street.value,
        "action": record.action.value,
        "chips": record.chips,
        "bet_to": record.bet_to,
    }


def _is_tricky(decisions: Sequence[DecisionNote]) -> bool:
    return any(
        (decision.ev_call is not None and decision.ev_call < 0 and decision.action.lower() in ("call", "all_in"))
        or decision.bet_purpose == BetPurpose.POINTLESS.value
        or (decision.facing_cbet and decision.action.lower() == "fold")
        for decision in decisions
    )
