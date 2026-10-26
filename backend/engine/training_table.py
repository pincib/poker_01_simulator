"""A local six-seat training table connecting the engine to the browser UI."""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend.brain.ai_agent import OpponentAI, OpponentProfile
from backend.brain.coach import CoachService, CoachSnapshot, DecisionNote, SessionTracker
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player


class TrainingTable:
    """Process-local Hold'em table for one player and five profile-driven bots."""

    hero_id = "hero"
    starting_stack = 200
    small_blind = 1
    big_blind = 2

    def __init__(self, session_tracker: SessionTracker) -> None:
        self._tracker = session_tracker
        self._lock = RLock()
        self._state: GameState | None = None
        self._stacks = [self.starting_stack] * 6
        self._button_index = 0
        self._hand_number = 0
        self._decisions: list[DecisionNote] = []
        self._recorded = False
        self._coach_cache_key: tuple[object, ...] | None = None
        self._coach_cache: CoachSnapshot | None = None
        self._bots = {
            f"bot-{index}": OpponentAI(profile, equity_iterations=96)
            for index, profile in enumerate(
                (OpponentProfile.TAG, OpponentProfile.NIT, OpponentProfile.STATION, OpponentProfile.GTO, OpponentProfile.TAG),
                start=1,
            )
        }

    def start_hand(self) -> dict[str, object]:
        with self._lock:
            if self._state is not None and not self._state.hand_complete:
                raise ValueError("Finish the current hand before dealing another.")
            # A practice table supports a fresh buy-in after a player loses the stack.
            if self._stacks[0] <= 0:
                self._stacks[0] = self.starting_stack
            for index in range(1, len(self._stacks)):
                if self._stacks[index] <= 0:
                    self._stacks[index] = self.starting_stack
            players = (Player(self.hero_id, "You", self._stacks[0]),) + tuple(
                Player(f"bot-{index}", name, self._stacks[index])
                for index, name in enumerate(("Aggro Alex", "Nitty Norman", "Calling Kevin", "Solver Sam", "Aggro Alex"), start=1)
            )
            self._state = GameState.new_hand(
                players,
                self.small_blind,
                self.big_blind,
                self._button_index,
            )
            self._hand_number += 1
            self._decisions = []
            self._recorded = False
            self._coach_cache_key = None
            self._coach_cache = None
            self._button_index = (self._button_index + 1) % len(players)
            self._run_bots()
            self._resolve_showdown()
            self._record_if_complete()
            return self.snapshot()

    def act(self, action_value: object, amount_value: object = None) -> dict[str, object]:
        with self._lock:
            state = self._require_state()
            if state.current_player_id != self.hero_id:
                raise ValueError("It is not your turn yet.")
            if not isinstance(action_value, str):
                raise ValueError("Action must be a string.")
            action = ActionType(action_value)
            hero = state.player_by_id(self.hero_id)
            assert hero is not None
            pot_before = state.pot
            call_amount = state.amount_to_call
            active_opponents = [player for player in state.players if player.id != self.hero_id and player.is_active]
            coach = None
            coach_error: str | None = None
            bet_purpose = None
            if active_opponents:
                try:
                    coach = self._coach_for(state, active_opponents[0] if len(active_opponents) == 1 else None)
                except ValueError as exc:
                    # Coaching must never prevent a legal poker action.
                    coach_error = str(exc)
            if coach is not None and len(active_opponents) == 1:
                if action in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                    target = amount_value if isinstance(amount_value, int) else hero.current_bet + hero.stack
                    try:
                        purpose = CoachService.classify_bet(
                            hero_hole=hero.hole_cards,
                            board=state.community_cards,
                            pot=pot_before,
                            bet_amount=max(1, target - hero.current_bet),
                            opponent_position=active_opponents[0].position,
                            opponent_profile="tag",
                            hero_position=hero.position,
                        )
                        bet_purpose = purpose.purpose.value
                    except ValueError:
                        bet_purpose = None
            if coach is None:
                self._decisions.append(DecisionNote(
                    street=state.street.value,
                    action=action.value,
                    chips=call_amount if action is ActionType.CALL else max(0, int(amount_value or 0) - hero.current_bet),
                    pot_before=pot_before,
                    rationale=coach_error or "No opponent model was available when this decision was made.",
                    review_question="What range and future-street plan support this decision?",
                ))
            before_count = len(self._decisions)
            if coach is not None:
                chips = call_amount if action is ActionType.CALL else (
                    max(0, int(amount_value or 0) - hero.current_bet)
                    if action in (ActionType.BET, ActionType.RAISE)
                    else hero.stack if action is ActionType.ALL_IN else 0
                )
                self._decisions.append(DecisionNote(
                    street=state.street.value,
                    action=action.value,
                    chips=chips,
                    pot_before=pot_before,
                    equity_percentage=coach.equity_percentage,
                    pot_odds_percentage=coach.pot_odds_percentage,
                    ev_call=coach.ev_call if action is ActionType.CALL else None,
                    bet_purpose=bet_purpose,
                    facing_cbet=state.street is not Street.PREFLOP and call_amount > 0,
                    out_of_position=hero.position is not None and hero.position.value not in ("BTN", "CO"),
                    rationale=coach.advice,
                    review_question="Was the estimated range accurate, and what alternative did you consider?",
                ))
            amount = amount_value if action in (ActionType.BET, ActionType.RAISE) else None
            self._state = state.apply_action(self.hero_id, action, amount)
            self._run_bots()
            self._resolve_showdown()
            self._record_if_complete()
            return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            state = self._state
            if state is None:
                return {"started": False}
            hero = state.player_by_id(self.hero_id)
            assert hero is not None
            ended_by_fold = bool(state.action_history and state.action_history[-1].action is ActionType.FOLD)
            display_street = state.street
            if state.hand_complete and ended_by_fold:
                # A fold ends the hand immediately; SHOWDOWN is only the engine's
                # terminal marker in that case, not a street the players reached.
                display_street = state.action_history[-1].street
            seats = []
            for player in state.players:
                # In training mode, reveal every surviving hand after settlement,
                # including a fold winner's hand. Folded players stay hidden.
                cards_visible = player.id == self.hero_id or (state.hand_complete and player.is_active)
                seats.append({
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value if player.position else "",
                    "stack": player.stack,
                    "street_bet": player.current_bet,
                    "active": player.is_active,
                    "is_all_in": player.is_all_in,
                    "is_hero": player.id == self.hero_id,
                    "is_turn": player.id == state.current_player_id,
                    "is_button": state.players[state.button_index].id == player.id,
                    "hole_cards": [card.code for card in player.hole_cards] if cards_visible else [],
                    "cards_hidden": player.id != self.hero_id and not cards_visible,
                    "profile": self._profile_name(player.id),
                })
            to_call = max(0, state.current_bet - hero.current_bet)
            legal = state.legal_actions() if state.current_player_id == self.hero_id else ()
            pot_after_call = state.pot + to_call
            coach_snapshot: dict[str, object] | None = None
            coach_note: str | None = None
            active_opponents = [player for player in state.players if player.id != self.hero_id and player.is_active]
            coach_context: str | None = None
            if state.hand_complete:
                if self._coach_cache is not None:
                    coach_snapshot = self._coach_cache.to_dict()
                    coach_context = "last_decision"
                else:
                    coach_note = (
                        "No heads-up estimate was recorded for this hand. Multiway equity is not modeled yet; "
                        "open Session review to inspect the actions."
                    )
            elif state.current_player_id == self.hero_id:
                if active_opponents:
                    try:
                        coach_snapshot = self._coach_for(
                            state, active_opponents[0] if len(active_opponents) == 1 else None
                        ).to_dict()
                        coach_context = "current_decision"
                    except ValueError as exc:
                        coach_note = str(exc)
                else:
                    coach_note = "No active opponent is available for an equity estimate."
            min_raise = state.current_bet + state.last_full_raise_size
            max_raise = hero.current_bet + hero.stack
            spr_value = None
            if hero.is_active and not state.hand_complete and len(active_opponents) == 1 and state.pot > 0:
                spr_value = min(hero.stack, active_opponents[0].stack) / state.pot
            last_action = state.action_history[-1] if state.action_history else None
            return {
                "started": True,
                "hand_number": self._hand_number,
                "variant": "Texas Hold’em",
                "table_label": "6-max · No-limit · $1/$2",
                "small_blind": self.small_blind,
                "big_blind": self.big_blind,
                "street": display_street.value,
                "pot": state.pot,
                "board": [card.code for card in state.community_cards],
                "seats": seats,
                "hero_stack": hero.stack,
                "hero_position": hero.position.value if hero.position else "",
                "hero_hole": [card.code for card in hero.hole_cards],
                "current_player_id": state.current_player_id,
                "hero_to_call": to_call,
                "pot_after_call": pot_after_call,
                "current_bet": state.current_bet,
                "spr_value": spr_value,
                "legal_actions": [action.value for action in legal],
                "raise_min": min_raise,
                "raise_max": max_raise,
                "can_start_next": state.hand_complete,
                "hand_complete": state.hand_complete,
                "winners": list(state.winners),
                "payouts": dict(state.payouts),
                "outcome": self._outcome(state),
                "last_action": None if last_action is None else {
                    "player_id": last_action.player_id,
                    "action": last_action.action.value,
                    "chips": last_action.chips,
                },
                "coach": coach_snapshot,
                "coach_note": coach_note,
                "coach_context": coach_context,
                "multiway": len(active_opponents) > 1,
            }

    def _run_bots(self) -> None:
        state = self._require_state()
        guard = 0
        while state.current_player_id and state.current_player_id != self.hero_id and not state.hand_complete:
            guard += 1
            if guard > 32:
                raise RuntimeError("Opponent action limit exceeded; the hand was stopped safely.")
            bot_id = state.current_player_id
            ai = self._bots.get(bot_id)
            if ai is None:
                raise RuntimeError("The current table seat has no opponent profile.")
            hero = state.player_by_id(self.hero_id)
            decision = ai.decide(state, bot_id, opponent_id=self.hero_id if hero and hero.is_active else None)
            state = state.apply_action(bot_id, decision.action, decision.amount)
        self._state = state

    def _resolve_showdown(self) -> None:
        state = self._require_state()
        if state.street is Street.SHOWDOWN and not state.hand_complete:
            rankings = {
                player.id: HandEvaluator.evaluate_7(player.hole_cards + state.community_cards)
                for player in state.players
                if player.is_active
            }
            state = state.resolve_showdown(rankings)
            self._state = state

    def _record_if_complete(self) -> None:
        state = self._require_state()
        if state.hand_complete and not self._recorded:
            self._stacks = [player.stack for player in state.players]
            self._tracker.record_hand(state, self.hero_id, self._decisions)
            self._recorded = True

    def _require_state(self) -> GameState:
        if self._state is None:
            raise ValueError("Start a hand before taking an action.")
        return self._state

    def _coach_for(self, state: GameState, opponent: Player | None) -> CoachSnapshot:
        active_opponents = tuple(
            player.id for player in state.players
            if player.id != self.hero_id and player.is_active
        )
        key = (
            self._hand_number,
            len(state.action_history),
            state.street.value,
            state.current_player_id,
            state.pot,
            opponent.id if opponent else active_opponents,
            tuple(card.code for card in state.community_cards),
        )
        if key != self._coach_cache_key or self._coach_cache is None:
            self._coach_cache = CoachService.analyze_state(
                state, self.hero_id, opponent.id if opponent else None, iterations=256
            )
            self._coach_cache_key = key
        return self._coach_cache

    def _profile_name(self, player_id: str) -> str:
        ai = self._bots.get(player_id)
        return ai.profile.display_name if ai else "Hero"

    def _outcome(self, state: GameState) -> str | None:
        if not state.hand_complete:
            return None
        hero_payout = dict(state.payouts).get(self.hero_id, 0)
        if self.hero_id in state.winners:
            return f"You won ${hero_payout:.2f}" if len(state.winners) == 1 else f"Split pot · ${hero_payout:.2f} to you"
        return "Hand complete · the pot went to your opponent"
