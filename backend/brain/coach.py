"""Training feedback, bet-purpose analysis, and in-memory hand review."""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import combinations
from math import comb, isfinite
from threading import RLock
from typing import Mapping, Sequence
from uuid import uuid4

from backend.brain.ai_agent import OpponentProfile
from backend.brain.ai_agent import plo_starting_hand_score
from backend.brain.equity import EquityCalculator
from backend.brain.pot_odds import PotOddsCalculator
from backend.brain.plo_draws import OmahaWrapDetector
from backend.brain.ranges import get_opening_range, starting_hand_class
from backend.brain.spr import SPRCalculator
from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionRecord, GameState, Street
from backend.engine.player import Player, Position
from backend.engine.rules import GameVariant

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
    UNMODELED = "unmodeled"


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
    draw_analysis: Mapping[str, object] | None = None
    variant: str = GameVariant.TEXAS_HOLDEM.value
    opponent_range_size: int | None = None
    range_description: str = ""
    seed: int | None = None
    limitations: tuple[str, ...] = ()
    deterministic: bool = False
    learning_steps: tuple[Mapping[str, str], ...] = ()

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
            "draw_analysis": dict(self.draw_analysis) if self.draw_analysis is not None else None,
            "variant": self.variant,
            "opponent_range_size": self.opponent_range_size,
            "range_description": self.range_description,
            "seed": self.seed,
            "limitations": list(self.limitations),
            "deterministic": self.deterministic,
            "learning_steps": [dict(step) for step in self.learning_steps],
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
    variant: str = GameVariant.TEXAS_HOLDEM.value

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
            "variant": self.variant,
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
    variant: str = GameVariant.TEXAS_HOLDEM.value
    equity_source: str | None = None
    equity_iterations: int | None = None
    opponent_range_size: int | None = None
    range_description: str | None = None
    estimation_seed: int | None = None
    deterministic: bool = False
    limitations: tuple[str, ...] = ()
    draw_analysis: Mapping[str, object] | None = None
    learning_steps: tuple[Mapping[str, str], ...] = ()
    process_feedback: str = ""

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
            "variant": self.variant,
            "equity_source": self.equity_source,
            "equity_iterations": self.equity_iterations,
            "opponent_range_size": self.opponent_range_size,
            "range_description": self.range_description,
            "estimation_seed": self.estimation_seed,
            "deterministic": self.deterministic,
            "limitations": list(self.limitations),
            "draw_analysis": dict(self.draw_analysis) if self.draw_analysis is not None else None,
            "learning_steps": [dict(step) for step in self.learning_steps],
            "process_feedback": self.process_feedback,
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
    variant: str = "texas_holdem"
    players: tuple[Mapping[str, object], ...] = ()
    contributions: Mapping[str, int] = field(default_factory=dict)
    winners: tuple[str, ...] = ()
    showdown_ranks: Mapping[str, int] = field(default_factory=dict)
    winning_hands: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    pot_awards: tuple[Mapping[str, object], ...] = ()

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
            "variant": self.variant,
            "players": [dict(player) for player in self.players],
            "contributions": dict(self.contributions),
            "winners": list(self.winners),
            "showdown_ranks": dict(self.showdown_ranks),
            "winning_hands": {key: list(cards) for key, cards in self.winning_hands.items()},
            "pot_awards": [dict(award) for award in self.pot_awards],
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
    by_variant: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "since": self.since,
            "until": self.until,
            "hands_reviewed": self.hands_reviewed,
            "flags": [flag.to_dict() for flag in self.flags],
            "study_target": self.study_target,
            "weekly_plan": list(self.weekly_plan),
            "by_variant": {key: dict(value) for key, value in self.by_variant.items()},
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
        all_active_opponents = [player for player in state.players if player.id != hero_id and player.is_active]
        opponents = list(all_active_opponents)
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
                if len(hero.hole_cards) == 4:
                    preflop_action = next((
                        record.action for record in reversed(state.action_history)
                        if record.player_id == active_opponent.id and record.street is Street.PREFLOP
                    ), None)
                    opponent_ranges.append(_sample_four_card_range(
                        known, seed=_opponent_range_seed(seed, active_opponent.id),
                        keep_fraction=_plo_range_fraction(active_opponent.position, preflop_action),
                    ))
                    range_was_filtered = True
                    continue
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
                iterations=iterations,
                seed=seed,
                opponent_ranges_action_filtered=range_was_filtered,
                variant=state.rules.variant,
                available_actions=(
                    tuple(action.value for action in state.legal_actions())
                    if state.current_player_id == hero_id else ()
                ),
                range_description=(
                    "uniform sampled PLO4 combinations, position/action adjusted by a simple heuristic"
                    if len(hero.hole_cards) == 4 else "position/action filtered Hold'em opening ranges"
                ),
            )
        preflop_action = next((
            record.action for record in reversed(state.action_history)
            if record.player_id == opponent.id and record.street is Street.PREFLOP
        ), None)
        additional_limitations = ()
        if opponent_id is not None and len(all_active_opponents) > 1:
            additional_limitations = (
                "This snapshot models only the selected opponent in a multiway hand; its equity is not the hero's equity against the full field.",
            )
        return cls.analyze_decision(
            hero_hole=hero.hole_cards,
            board=state.community_cards,
            pot=state.pot,
            call_amount=max(0, state.current_bet - hero.current_bet),
            hero_stack=hero.stack,
            opponent_stack=min(player.stack for player in all_active_opponents),
            opponent_position=opponent.position or Position.BUTTON,
            opponent_last_action=preflop_action,
            big_blind=state.big_blind,
            iterations=iterations,
            seed=seed,
            variant=state.rules.variant,
            available_actions=(
                tuple(action.value for action in state.legal_actions())
                if state.current_player_id == hero_id else ()
            ),
            additional_limitations=additional_limitations,
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
        variant: GameVariant | str | None = None,
        range_description: str | None = None,
        additional_limitations: Sequence[str] = (),
        available_actions: Sequence[str] = (),
    ) -> CoachSnapshot:
        hero = _validated_hole_cards(hero_hole, "Hero hole cards")
        resolved_variant = GameVariant(variant) if variant is not None else (
            GameVariant.POT_LIMIT_OMAHA if len(hero) == 4 else GameVariant.TEXAS_HOLDEM
        )
        expected_hole_count = 4 if resolved_variant is GameVariant.POT_LIMIT_OMAHA else 2
        if len(hero) != expected_hole_count:
            raise ValueError("Coach hole-card count does not match the game variant.")
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
            villain = _validated_cards(opponent_hole, len(hero), "Opponent hole cards")
            if len(set(blockers + villain)) != len(blockers) + len(villain):
                raise ValueError("Hero, opponent, and board cards must all be distinct.")
            source = "known opponent hand"
            opponent_range_size = 1
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
            opponent_range_size = sum(len(range_) for range_ in opponent_ranges)
        else:
            supplied_range = opponent_range is not None
            candidates = tuple(tuple(combo) for combo in opponent_range) if supplied_range else None
            if candidates is None and resolved_variant is GameVariant.TEXAS_HOLDEM:
                position = Position(opponent_position)
                estimated = get_opening_range(position)
                if opponent_last_action is not None:
                    estimated = estimated.filtered_by_action(opponent_last_action)
                candidates = estimated.to_combos(blockers)
            if candidates is not None and not candidates:
                raise ValueError("Opponent range has no hands after removing known cards.")
            source = (
                "uniform four-card combinations"
                if candidates is None
                else "provided opponent range" if supplied_range
                else "action-filtered opponent range" if opponent_last_action is not None else "estimated opponent range"
            )
            opponent_range_size = len(candidates) if candidates is not None else comb(52 - len(blockers), 4)
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
            advice = (
                (
                    "No call price is pending. Before the flop, use four-card structure, nut-suit potential, position, and stack depth; the range-based equity is only an estimate."
                    if not community else
                    "No call price is pending. Evaluate made-hand strength and nut redraws with exactly two hole cards and three board cards; checking is valid when neither value nor fold equity has evidence."
                ) if resolved_variant is GameVariant.POT_LIMIT_OMAHA else
                "No call price is pending. Give a bet a value or bluff reason; checking is valid when neither has evidence."
            )
        elif equity_share > odds.required_equity_percentage:
            call_assessment = CallAssessment.PROFITABLE
            advice = (
                (
                    "The PLO4 preflop estimate is above the call price against this modeled range. Starting-hand structure and range width can change the result; future streets still need a plan."
                    if not community else
                    "The PLO4 equity estimate is above the call price before rake. It uses exact-two/three Omaha evaluation; account for redraws and side-pot eligibility before committing further."
                ) if resolved_variant is GameVariant.POT_LIMIT_OMAHA else
                "The estimated equity is above the call price. This is positive expected value before rake; future-street bets still need a plan."
            )
        elif equity_share < odds.required_equity_percentage:
            call_assessment = CallAssessment.UNPROFITABLE
            advice = (
                (
                    "The PLO4 preflop estimate is below the call price against this modeled range. Recheck range width, position, and four-card structure; the model does not predict future betting choices."
                    if not community else
                    "The PLO4 equity estimate is below the call price before rake. Recheck the four-card opponent range, nut outs and redraw risk; this estimate does not model future betting choices."
                ) if resolved_variant is GameVariant.POT_LIMIT_OMAHA else
                "The estimated equity is below the call price before rake and implied odds. Recheck the range and future-street plan."
            )
        else:
            call_assessment = CallAssessment.BREAK_EVEN
            advice = "Estimated equity matches the call price before rake. The result of this hand will not change that expectation."

        if len(community) >= 3 and resolved_variant is GameVariant.POT_LIMIT_OMAHA:
            _, chosen = HandEvaluator.evaluate_plo_with_hand(hero, community)
            description = HandEvaluator.describe(chosen)
        else:
            description = HandEvaluator.describe(hero + community) if len(community) >= 3 else None
        spr_value: float | None = None
        warning: str | None = None
        if pot > 0:
            spr = SPRCalculator.calculate(hero_stack, opponent_stack, pot)
            spr_value = spr.value
            if spr_value <= 2:
                if resolved_variant is GameVariant.POT_LIMIT_OMAHA:
                    warning = f"SPR {spr_value:.1f}: stacks are close to the pot. In PLO4, include four-card structure preflop or nut potential and redraws postflop; a pair alone is not enough."
                elif len(community) >= 3 and _has_top_pair(hero, community):
                    warning = f"SPR {spr_value:.1f}: you have top pair. Plan the remaining stack using the board and opponent range before committing."
                else:
                    warning = f"SPR {spr_value:.1f}: effective stacks are close to the pot. Check hand strength and opponent range before committing."
            else:
                warning = f"SPR {spr_value:.1f}: compare the effective stack with the pot as future bets develop."

        draw_analysis = None
        if resolved_variant is GameVariant.POT_LIMIT_OMAHA and len(community) in (3, 4, 5):
            draw_analysis = OmahaWrapDetector.analyze(
                hero,
                community,
                opponent_hole if opponent_hole is not None else None,
            ).to_dict()

        limitations = []
        if source in ("uniform four-card combinations", "estimated multiway ranges", "action-filtered multiway ranges") and resolved_variant is GameVariant.POT_LIMIT_OMAHA:
            limitations.append("Opponent ranges are modeled samples; position/action adjustments are heuristics, not observed cards or a solver range.")
        deterministic = len(community) == 5 and opponent_hole is not None
        if not deterministic:
            limitations.append("Equity is a Monte Carlo estimate over the recorded range model; it does not model future opponent actions.")
        else:
            limitations.append("Known hands on the river are deterministic; this result does not model future opponent actions.")
        if opponent_ranges is not None:
            limitations.append("SPR and side-pot decisions are simplified for the shortest active opponent.")
        limitations.extend(str(value) for value in additional_limitations)

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
            draw_analysis=draw_analysis,
            variant=resolved_variant.value,
            opponent_range_size=opponent_range_size,
            range_description=range_description or source,
            seed=seed,
            limitations=tuple(limitations),
            deterministic=deterministic,
            learning_steps=_learning_steps(
                variant=resolved_variant,
                board=community,
                pot=pot,
                call_amount=call_amount,
                pot_odds=odds.required_equity_percentage if call_amount else None,
                equity=equity_share,
                ev_call=ev_call,
                assessment=call_assessment,
                spr=spr_value,
                hand_description=description,
                advice=advice,
                draw_analysis=draw_analysis,
                available_actions=available_actions,
            ),
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
        hero = _validated_hole_cards(hero_hole, "Hero hole cards")
        variant = GameVariant.POT_LIMIT_OMAHA if len(hero) == 4 else GameVariant.TEXAS_HOLDEM
        community = _validated_board(board)
        _non_negative_chips("Pot", pot)
        _non_negative_chips("Bet amount", bet_amount)
        if bet_amount == 0:
            raise ValueError("A bet purpose requires a positive bet amount.")
        profile = OpponentProfile.parse(opponent_profile)

        if variant is GameVariant.POT_LIMIT_OMAHA and not community:
            score = plo_starting_hand_score(hero)
            return BetPurposeResult(
                BetPurpose.UNMODELED,
                f"PLO4 preflop structure score {score:.1f}/100 is a heuristic, not equity; no opponent response or four-card range is modeled for bet-purpose classification.",
                bet_amount, 0, 0, 0, 0, 0, 0, variant.value,
            )

        if not community:
            hand_class = starting_hand_class(hero)
            premium = get_opening_range(Position(hero_position), 10).frequency_for(hero) >= 0.9
            if premium:
                return BetPurposeResult(BetPurpose.VALUE, "This starting hand is in the top positional opening range.", bet_amount, 0, 1, 0, 0, 1, 0, variant.value)
            if profile is OpponentProfile.NIT:
                return BetPurposeResult(BetPurpose.BLUFF, "The hand is outside the top range and a nit profile can fold better unpaired hands.", bet_amount, 0, 0, 1, 0, 0, 0.5, variant.value)
            return BetPurposeResult(BetPurpose.POINTLESS, f"{hand_class} is not a premium opening hand; no clear value or fold target is modeled.", bet_amount, 0, 0, 0, 1, 0, 0, variant.value)

        blockers = hero + community
        if len(set(blockers)) != len(blockers):
            raise ValueError("Hero and board cards must all be distinct.")
        if opponent_range is None:
            if variant is GameVariant.POT_LIMIT_OMAHA:
                keep_fraction = _plo_range_fraction(Position(opponent_position), opponent_last_action)
                range_combos = _sample_four_card_range(blockers, seed=0, keep_fraction=keep_fraction)
            else:
                estimated = get_opening_range(Position(opponent_position))
                if opponent_last_action is not None:
                    estimated = estimated.filtered_by_action(opponent_last_action)
                range_combos = estimated.to_combos(blockers)
        else:
            range_combos = tuple(tuple(combo) for combo in opponent_range)
        if not range_combos:
            raise ValueError("Opponent range has no hands after removing known cards.")

        hero_rank = (
            HandEvaluator.evaluate_plo(hero, community)
            if variant is GameVariant.POT_LIMIT_OMAHA else _best_rank(hero + community)
        )
        worse = better = tied = 0
        for combo in range_combos:
            villain = _validated_cards(combo, len(hero), "Opponent range hand")
            if len(set(blockers + villain)) != len(blockers) + len(villain):
                continue
            villain_rank = (
                HandEvaluator.evaluate_plo(villain, community)
                if variant is GameVariant.POT_LIMIT_OMAHA else _best_rank(villain + community)
            )
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
            OpponentProfile.BALANCED: (0.52, 0.32),
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
            expected_worse_calls, expected_better_folds, variant.value,
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
        variant = state.rules.variant.value
        decisions = tuple(replace(note, variant=variant) for note in decisions)
        players = tuple({
            "id": player.id,
            "name": player.name,
            "position": player.position.value if player.position else "unknown",
            "starting_stack": player.stack + player.total_contributed - payouts.get(player.id, 0),
            "final_stack": player.stack,
            "total_contributed": player.total_contributed,
            "hole_cards": [card.code for card in player.hole_cards if player.id == hero.id or player.is_active],
            "active_at_end": player.is_active,
            "all_in_at_end": player.is_all_in,
        } for player in state.players)
        pot_awards = tuple({
            "label": award.label,
            "amount": award.amount,
            "eligible_player_ids": list(award.eligible_player_ids),
            "winner_ids": list(award.winner_ids),
            "payouts": dict(award.payouts),
            "refund_to": award.refund_to,
        } for award in state.pot_awards)
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
            variant=variant,
            players=players,
            contributions={player.id: player.total_contributed for player in state.players},
            winners=state.winners,
            showdown_ranks=dict(state.showdown_ranks),
            winning_hands={player_id: tuple(card.code for card in cards) for player_id, cards in state.winning_hands},
            pot_awards=pot_awards,
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
        variant = GameVariant(str(payload.get("variant", GameVariant.TEXAS_HOLDEM.value)))
        expected_hole_count = 4 if variant is GameVariant.POT_LIMIT_OMAHA else 2
        hole_cards = _card_codes(hero_data.get("hole_cards"), "Hero hole cards", allowed=(expected_hole_count,))
        board = _card_codes(payload.get("board", []), "Board cards", allowed=(0, 3, 4, 5))
        all_card_codes = list(hole_cards) + list(board)
        normalized_players = []
        for player_data in players:
            other_hole = player_data.get("hole_cards", [])
            normalized_hole = _card_codes(
                other_hole, "Player hole cards", allowed=(0, expected_hole_count)
            )
            if player_data is hero_data and normalized_hole != hole_cards:
                raise ValueError("Hero hand cards must match the hero player record.")
            if player_data is not hero_data:
                all_card_codes.extend(normalized_hole)
            normalized_players.append({
                "id": _optional_string(player_data, "id", "unknown"),
                "name": _optional_string(player_data, "name", "unknown"),
                "position": _optional_string(player_data, "position", "unknown"),
                "starting_stack": _non_negative_chips("Player starting stack", player_data.get("starting_stack", 0)),
                "final_stack": _non_negative_chips("Player final stack", player_data.get("final_stack", 0)),
                "total_contributed": _non_negative_chips("Player contribution", player_data.get("total_contributed", 0)),
                "hole_cards": list(normalized_hole),
                "active_at_end": player_data.get("active_at_end") is True,
                "all_in_at_end": player_data.get("all_in_at_end") is True,
            })
        if len({Card.from_code(code) for code in all_card_codes}) != len(all_card_codes):
            raise ValueError("Cards cannot be duplicated across players and the board.")
        decisions_value = payload.get("decisions", [])
        if not isinstance(decisions_value, list):
            raise ValueError("Decisions must be a list.")
        decisions = tuple(replace(_decision_note_from_payload(item), variant=variant.value) for item in decisions_value)
        actions_value = payload.get("actions", [])
        if not isinstance(actions_value, list) or any(not isinstance(item, dict) for item in actions_value):
            raise ValueError("Actions must be a list of objects.")
        actions = []
        for item in actions_value:
            action_variant = GameVariant(str(item.get("variant", variant.value)))
            if action_variant is not variant:
                raise ValueError("Action history variant must match the hand variant.")
            actions.append({**item, "variant": variant.value})
        payouts_value = payload.get("payouts", {})
        if not isinstance(payouts_value, dict):
            raise ValueError("Payouts must be an object keyed by player id.")
        payouts = {str(key): _non_negative_chips("Payout", value) for key, value in payouts_value.items()}
        contributions_value = payload.get("contributions", {})
        provided_contributions = contributions_value if isinstance(contributions_value, dict) else {}
        contributions = {
            str(player["id"]): _non_negative_chips(
                "Contribution",
                provided_contributions.get(player["id"], player["total_contributed"]),
            )
            for player in normalized_players
        }
        winning_hands = _parse_winning_hands(payload.get("winning_hands", {}))
        player_cards = {str(player["id"]): set(player["hole_cards"]) for player in normalized_players}
        board_set = set(board)
        for player_id, winning_hand in winning_hands.items():
            if player_id not in player_cards or not set(winning_hand).issubset(player_cards[player_id] | board_set):
                raise ValueError("A winning combination must use the winner's cards and the recorded board.")
            if variant is GameVariant.POT_LIMIT_OMAHA and (
                sum(card in player_cards[player_id] for card in winning_hand) != 2
                or sum(card in board_set for card in winning_hand) != 3
            ):
                raise ValueError("PLO winning combinations must use exactly two hole cards and three board cards.")
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
            actions=tuple(actions),
            payouts=payouts,
            decisions=decisions,
            tricky=_is_tricky(decisions),
            variant=variant.value,
            players=tuple(normalized_players),
            contributions=contributions,
            winners=tuple(str(value) for value in payload.get("winners", []) if isinstance(value, str)) if isinstance(payload.get("winners", []), list) else (),
            showdown_ranks={
                str(key): _non_negative_chips("Showdown rank", value)
                for key, value in (payload.get("showdown_ranks", {}) if isinstance(payload.get("showdown_ranks", {}), dict) else {}).items()
            },
            winning_hands=winning_hands,
            pot_awards=tuple(dict(item) for item in payload.get("pot_awards", []) if isinstance(item, dict)) if isinstance(payload.get("pot_awards", []), list) else (),
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
        by_variant: dict[str, Mapping[str, object]] = {}
        all_flags: list[LeakFlag] = []
        for variant in GameVariant:
            variant_hands = [hand for hand in hands if hand.variant == variant.value]
            decisions = [decision for hand in variant_hands for decision in hand.decisions]
            flags = _variant_leak_flags(decisions, variant)
            by_variant[variant.value] = {
                "hands_reviewed": len(variant_hands),
                "flags": [flag.to_dict() for flag in flags],
                "limitations": [
                    "Leak indicators are review prompts, not proof of a mistake.",
                    "Equity-based call indicators inherit the range and Monte Carlo uncertainty recorded for each decision.",
                    *(["Nut-potential, redraw, and blocker patterns are shown as hand evidence and are not yet scored as standalone leaks."] if variant is GameVariant.POT_LIMIT_OMAHA else []),
                ],
            }
            all_flags.extend(flags)
        flags = all_flags
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
            by_variant,
        )


def _variant_leak_flags(decisions: Sequence[DecisionNote], variant: GameVariant) -> tuple[LeakFlag, ...]:
    flags: list[LeakFlag] = []
    calls = [
        decision for decision in decisions
        if decision.action.lower() in ("call", "all_in") and decision.ev_call is not None
    ]
    negative_calls = [decision for decision in calls if decision.ev_call is not None and decision.ev_call < 0]
    if len(calls) >= 3 and len(negative_calls) / len(calls) >= 0.30:
        rate = len(negative_calls) / len(calls) * 100
        if variant is GameVariant.POT_LIMIT_OMAHA:
            key = "plo_negative_ev_calls"
            title = "PLO calls below estimated break-even"
            message = f"{len(negative_calls)} of {len(calls)} reviewed PLO calls were below the recorded equity estimate at the call price. Check each four-card range and uncertainty note."
        else:
            key = "negative_ev_calls"
            title = "Hold'em calls below break-even equity"
            message = f"{len(negative_calls)} of {len(calls)} reviewed Hold'em call decisions were below the recorded equity estimate at the call price."
        flags.append(LeakFlag(
            key, title, len(negative_calls), len(calls), rate, message,
            "Compare the call price, estimated range, and future-street plan.",
        ))

    if variant is GameVariant.TEXAS_HOLDEM:
        cbet_opportunities = [decision for decision in decisions if decision.facing_cbet]
        cbet_folds = [decision for decision in cbet_opportunities if decision.action.lower() == "fold"]
        if len(cbet_opportunities) >= 3 and len(cbet_folds) / len(cbet_opportunities) >= 0.60:
            rate = len(cbet_folds) / len(cbet_opportunities) * 100
            flags.append(LeakFlag(
                "overfold_cbet", "Frequent folds to continuation bets", len(cbet_folds), len(cbet_opportunities), rate,
                f"You folded to {len(cbet_folds)} of {len(cbet_opportunities)} recorded Hold'em continuation bets; review the price and board before deciding.",
                "Review the price and board texture before deciding.",
            ))

        postflop_entries = [
            decision for decision in decisions
            if decision.street.lower() in ("flop", "turn", "river") and decision.action.lower() != "fold"
        ]
        oop_entries = [decision for decision in postflop_entries if decision.out_of_position]
        if len(postflop_entries) >= 3 and len(oop_entries) / len(postflop_entries) >= 0.45:
            rate = len(oop_entries) / len(postflop_entries) * 100
            flags.append(LeakFlag(
                "out_of_position", "Review Hold'em pots played out of position", len(oop_entries), len(postflop_entries), rate,
                f"{len(oop_entries)} of {len(postflop_entries)} recorded Hold'em postflop entries were out of position. Check whether entry and later-street plans were justified.",
                "Review position, entry range, and later-street plan.",
            ))
    return tuple(flags)


def _learning_steps(
    *,
    variant: GameVariant,
    board: Sequence[Card],
    pot: int,
    call_amount: int,
    pot_odds: float | None,
    equity: float,
    ev_call: float | None,
    assessment: CallAssessment,
    spr: float | None,
    hand_description: str | None,
    advice: str,
    draw_analysis: Mapping[str, object] | None,
    available_actions: Sequence[str],
) -> tuple[Mapping[str, str], ...]:
    street = {0: "preflop", 3: "the flop", 4: "the turn", 5: "the river"}.get(len(board), "this decision")
    context = (
        f"On {street}, the pot is {pot} chips and calling costs {call_amount} chips. "
        "First read the price, then decide what range and future cards make the call worthwhile."
        if call_amount else
        f"On {street}, the pot is {pot} chips and there is no call to make. "
        "Checking is free; a bet needs a clear reason such as worse hands calling or better hands folding."
    )
    if hand_description:
        context += f" Your current made hand is {hand_description}."
    if available_actions:
        labels = {"fold": "fold", "check": "check", "call": "call", "bet": "bet", "raise": "raise", "all_in": "all-in"}
        context += " The legal actions from the server are: " + ", ".join(
            labels.get(action, action) for action in available_actions
        ) + "."

    concepts: list[str] = []
    if variant is GameVariant.POT_LIMIT_OMAHA:
        concepts.append(
            "PLO4 rule: a showdown hand uses exactly two of your four private cards and exactly three board cards. "
            "A pair may be part of the result, but it still has to follow that two-plus-three rule."
        )
        if not board:
            concepts.append(
                "Before the flop, look at how all four cards work together: connected ranks and an ace-high suited pair "
                "can create more nut potential than one attractive pair on its own."
            )
        if draw_analysis is not None:
            straight_outs = len(draw_analysis.get("straight_outs", ()))
            if straight_outs:
                wrap_definition = "A wrap is a draw with more than eight distinct straight-completing cards. "
                concepts.append(
                    wrap_definition
                    + (
                        f"This spot has {straight_outs} available straight cards, so it meets that threshold."
                        if draw_analysis.get("is_wrap") else
                        f"This spot has {straight_outs} available straight cards, so it does not meet that threshold."
                    )
                )
            flush_outs = len(draw_analysis.get("flush_outs", ()))
            nut_flush_outs = len(draw_analysis.get("nut_flush_outs", ()))
            if flush_outs:
                concepts.append(
                    f"A flush draw has {flush_outs} available cards that complete a flush using the Omaha two-plus-three rule; "
                    f"{nut_flush_outs} make the nut flush on that board. A non-nut flush can still be behind a higher flush."
                )
            nut_outs = len(draw_analysis.get("nut_outs", ()))
            non_nut_outs = len(draw_analysis.get("non_nut_outs", ()))
            concepts.append(
                "The nuts are the strongest legal hand possible on the current board. Nut potential means a path to that "
                "hand; it does not guarantee a win because an opponent may tie or a later card may change the board."
            )
            if nut_outs or non_nut_outs:
                concepts.append(
                    f"The draw check marks {nut_outs} cards as nut outs and {non_nut_outs} as non-nut improvements. "
                    "These describe the next-board hand rank, not a guaranteed pot."
                )
            blocker_combos = int(draw_analysis.get("hero_blocked_opponent_combos", 0) or 0)
            if blocker_combos:
                concepts.append(
                    f"A blocker is a card you hold that removes possible opponent combinations; these four cards "
                    f"remove {blocker_combos} combinations from an unweighted deck count. A blocker changes a range, "
                    "but is not a made hand by itself."
                )
            redraws = draw_analysis.get("opponent_redraws", ())
            if redraws:
                redraw_count = sum(len(item.get("river_cards", ())) for item in redraws if isinstance(item, Mapping))
                concepts.append(
                    f"A redraw is a later card that can overtake a hand after it improves. The exposed opponent "
                    f"has {redraw_count} modeled turn-river redraw runouts in this analysis."
                )
            elif draw_analysis.get("unverified_outs"):
                concepts.append(
                    "A redraw is a later card that can overtake a hand after it improves. Opponent cards are hidden, "
                    "so this analysis cannot verify which outs stay clean or what redraws the field has."
                )
        if not board:
            concepts.append(
                "Nut potential means the chance to make the best possible hand on later boards; it is a plan for "
                "future cards, not a promise to win."
            )
    else:
        concepts.append(
            "In Hold’em, your best five-card hand can use zero, one, or two of your private cards. "
            "An opponent range is a set of possible hands, not a known hand."
        )
    concepts.append(
        "Equity is your expected share of the pot across the modeled outcomes; a split pot counts as a share, "
        "so equity is not exactly the same as the chance of winning outright."
    )

    if call_amount and pot_odds is not None:
        gap = equity - pot_odds
        comparison = (
            f"The estimated equity is {abs(gap):.1f} percentage points above the immediate break-even price."
            if gap > 0 else
            f"The estimated equity is {abs(gap):.1f} percentage points below the immediate break-even price."
            if gap < 0 else
            "The estimated equity matches the immediate break-even price."
        )
        numbers = (
            f"Pot odds of {pot_odds:.1f}% are the break-even equity for this call: call amount divided by "
            f"the pot after calling ({call_amount} ÷ {pot + call_amount}). The model estimates {equity:.1f}% equity. "
            f"{comparison}"
        )
        if ev_call is not None:
            numbers += f" The call EV is {ev_call:+.1f} chips on average if this modeled spot repeats, before rake."
    else:
        numbers = (
            f"Pot odds do not apply because there is no call price. The {equity:.1f}% equity is a modeled expected "
            "pot share if the hand reaches showdown; it does not, by itself, show that betting is profitable."
        )
    if spr is not None:
        numbers += (
            f" SPR is {spr:.1f}: the shortest relevant effective stack divided by the pot. "
            "It helps estimate how many large bets may remain before stacks are committed."
        )

    if call_amount:
        if assessment is CallAssessment.PROFITABLE:
            process = (
                "The price comparison gives a reason to consider continuing against this modeled range. "
                "It does not automatically make a raise better; include position and your plan for later streets. "
                "A well-reasoned choice is judged by its inputs, not by who wins this pot."
            )
        elif assessment is CallAssessment.UNPROFITABLE:
            process = (
                "Treat the price comparison as a prompt to inspect the assumptions, not as a grade. "
                "Check whether the range includes enough weaker hands or draws, then compare calling with folding. "
                "The eventual result does not tell you whether that reasoning was sound."
            )
        else:
            process = (
                "This estimate sits at the break-even line, where small changes to the range can change the answer. "
                "Name the assumption that matters most before choosing call, fold, or raise."
            )
    else:
        process = (
            "There is no price to call. If you bet, name a weaker hand that can call for value or a better hand "
            "that may fold. If neither is clear, checking can keep the decision simple."
        )

    question = (
        "Which turn cards make you the nuts, and which could improve an opponent instead?"
        if variant is GameVariant.POT_LIMIT_OMAHA and board else
        "Which two cards work together best, and what kind of nut hand could they make?"
        if variant is GameVariant.POT_LIMIT_OMAHA else
        "Which hands in the modeled range are you ahead of, and how might the next card change that?"
    )
    if call_amount:
        question = (
            "Which assumptions about the opponent's range would move your equity above or below the call price?"
        )
        if variant is GameVariant.POT_LIMIT_OMAHA and board:
            question += " Which turn cards make you the nuts, and which could give an opponent a redraw?"

    return (
        {"kind": "context", "label": "THE SPOT", "title": "Start with what is happening", "body": context},
        {"kind": "concept", "label": "POKER IDEA", "title": "Name the rule or concept", "body": " ".join(concepts)},
        {"kind": "estimate", "label": "MATH ESTIMATE", "title": "Connect the numbers", "body": numbers},
        {"kind": "suggestion", "label": "COACH SUGGESTION", "title": "Build a process, not a verdict", "body": f"{advice} {process}"},
        {"kind": "practice", "label": "TAKE IT FORWARD", "title": "One question for next time", "body": question},
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


def _validated_hole_cards(cards: Sequence[Card], label: str) -> tuple[Card, ...]:
    result = tuple(cards)
    if len(result) not in (2, 4):
        raise ValueError(f"{label} must contain exactly two Hold'em cards or four Omaha cards.")
    return _validated_cards(result, len(result), label)


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


def _sample_four_card_range(
    blockers: Sequence[Card], *, seed: int | None, keep_fraction: float = 0.4, sample_size: int = 512
) -> tuple[tuple[Card, ...], ...]:
    unavailable = set(blockers)
    available = tuple(card for card in _FULL_DECK if card not in unavailable)
    if len(available) < 4:
        raise ValueError("No four-card PLO opponent range remains after removing blockers.")
    rng = random.Random(seed)
    sampled: dict[tuple[str, ...], tuple[float, tuple[Card, ...]]] = {}
    attempts = 0
    while len(sampled) < sample_size and attempts < sample_size * 8:
        attempts += 1
        hand = tuple(rng.sample(available, 4))
        key = tuple(sorted(card.code for card in hand))
        if key not in sampled:
            sampled[key] = (plo_starting_hand_score(hand), hand)
    ordered = sorted(sampled.values(), key=lambda entry: entry[0], reverse=True)
    keep_count = min(len(ordered), max(24, round(len(ordered) * min(0.95, max(0.05, keep_fraction)))))
    return tuple(hand for _, hand in ordered[:keep_count])


def _plo_range_fraction(position: Position | str | None, last_action: object | None) -> float:
    try:
        resolved_position = Position(position) if position is not None else Position.BUTTON
    except ValueError:
        resolved_position = Position.BUTTON
    fraction = {
        Position.UNDER_THE_GUN: 0.26,
        Position.HIJACK: 0.32,
        Position.CUTOFF: 0.4,
        Position.BUTTON: 0.48,
        Position.SMALL_BLIND: 0.36,
        Position.BIG_BLIND: 0.52,
    }[resolved_position]
    action = getattr(last_action, "value", last_action)
    fraction *= {"raise": 0.65, "bet": 0.72, "call": 0.88, "check": 1.0}.get(action, 1.0)
    return fraction


def _opponent_range_seed(seed: int | None, player_id: str) -> int | None:
    if seed is None:
        return None
    stable_id = sum((index + 1) * ord(character) for index, character in enumerate(player_id))
    return (seed + stable_id) % (2**32)


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
        variant=GameVariant(str(value.get("variant", GameVariant.TEXAS_HOLDEM.value))).value,
        equity_source=_optional_string(value, "equity_source", "") or None,
        equity_iterations=_optional_int(value.get("equity_iterations")),
        opponent_range_size=_optional_int(value.get("opponent_range_size")),
        range_description=_optional_string(value, "range_description", "") or None,
        estimation_seed=_optional_int(value.get("estimation_seed")),
        deterministic=value.get("deterministic") is True,
        limitations=_string_tuple(value.get("limitations", []), "Decision limitations"),
        draw_analysis=dict(value["draw_analysis"]) if isinstance(value.get("draw_analysis"), dict) else None,
        learning_steps=_learning_steps_from_payload(value.get("learning_steps", [])),
        process_feedback=_optional_string(value, "process_feedback", ""),
    )


def _learning_steps_from_payload(value: object) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ValueError("Decision learning_steps must be a list.")
    result: list[Mapping[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each decision learning step must be an object.")
        result.append({key: _required_string(item, key) for key in ("kind", "label", "title", "body")})
    return tuple(result)


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Decision metrics must be numeric or null.")
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("Decision counts and seeds must be non-negative integers or null.")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings.")
    return tuple(value)


def _parse_winning_hands(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise ValueError("Winning hands must be an object keyed by player id.")
    result = {}
    for player_id, cards in value.items():
        result[str(player_id)] = _card_codes(cards, "Winning hand", allowed=(5,))
    return result


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
        "variant": record.variant.value,
    }


def _is_tricky(decisions: Sequence[DecisionNote]) -> bool:
    return any(
        (decision.ev_call is not None and decision.ev_call < 0 and decision.action.lower() in ("call", "all_in"))
        or decision.bet_purpose == BetPurpose.POINTLESS.value
        or (decision.facing_cbet and decision.action.lower() == "fold")
        for decision in decisions
    )
