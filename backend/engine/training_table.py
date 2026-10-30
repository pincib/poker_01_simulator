"""A local six-seat training table connecting the engine to the browser UI."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from backend.brain.ai_agent import OpponentAI, OpponentProfile
from backend.brain.coach import CoachService, CoachSnapshot, DecisionNote, SessionTracker
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.evaluator import HandEvaluator
from backend.engine.player import Player
from backend.engine.rules import BettingStructure, GameRules, GameVariant


class TrainingTable:
    """Process-local variant-aware table for one player and five profile-driven bots."""

    hero_id = "hero"
    starting_stack = 200
    small_blind = 1
    big_blind = 2

    def __init__(
        self,
        session_tracker: SessionTracker,
        default_variant: GameVariant | str = GameVariant.TEXAS_HOLDEM,
    ) -> None:
        self._tracker = session_tracker
        self._variant = _resolve_variant(default_variant)
        self._lock = RLock()
        self._state: GameState | None = None
        self._stacks = [self.starting_stack] * 6
        self._button_index = 0
        self._hand_number = 0
        self._decisions: list[DecisionNote] = []
        self._last_decision_feedback: str | None = None
        self._recorded = False
        self._coach_cache_key: tuple[object, ...] | None = None
        self._coach_cache: CoachSnapshot | None = None
        self._bots = {
            f"bot-{index}": OpponentAI(profile, equity_iterations=96)
            for index, profile in enumerate(
                (OpponentProfile.TAG, OpponentProfile.NIT, OpponentProfile.STATION, OpponentProfile.BALANCED, OpponentProfile.TAG),
                start=1,
            )
        }

    def start_hand(self, variant: GameVariant | str | None = None) -> dict[str, object]:
        with self._lock:
            if self._state is not None and not self._state.hand_complete:
                raise ValueError("Conclua a mão atual antes de distribuir outra.")
            selected_variant = self._variant if variant is None else _resolve_variant(variant)
            rules = _rules_for(selected_variant)
            # A practice table supports a fresh buy-in after a player loses the stack.
            if self._stacks[0] <= 0:
                self._stacks[0] = self.starting_stack
            for index in range(1, len(self._stacks)):
                if self._stacks[index] <= 0:
                    self._stacks[index] = self.starting_stack
            players = (Player(self.hero_id, "Você", self._stacks[0]),) + tuple(
                Player(f"bot-{index}", name, self._stacks[index])
                for index, name in enumerate(("Alex agressivo", "Norman conservador", "Kevin pagador", "Blair equilibrado", "Alex agressivo"), start=1)
            )
            self._state = GameState.new_hand(
                players,
                self.small_blind,
                self.big_blind,
                self._button_index,
                rules=rules,
            )
            self._variant = selected_variant
            self._hand_number += 1
            self._decisions = []
            self._last_decision_feedback = None
            self._recorded = False
            self._coach_cache_key = None
            self._coach_cache = None
            self._button_index = (self._button_index + 1) % len(players)
            self._run_bots()
            self._resolve_showdown()
            self._record_if_complete()
            return self.snapshot()

    def act(
        self,
        action_value: object,
        amount_value: object = None,
        *,
        variant: GameVariant | str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            state = self._require_state()
            if variant is not None and _resolve_variant(variant) is not state.rules.variant:
                raise ValueError("A modalidade da ação não corresponde à mão atual e não pode ser alterada durante uma mão.")
            if state.current_player_id != self.hero_id:
                raise ValueError("Ainda não é sua vez de agir.")
            if not isinstance(action_value, str):
                raise ValueError("A ação deve ser um texto válido.")
            try:
                action = ActionType(action_value)
            except ValueError as exc:
                raise ValueError(f"Ação desconhecida: '{action_value}'.") from exc
            if amount_value is not None and action not in (ActionType.BET, ActionType.RAISE):
                raise ValueError("O valor só pode ser informado nas ações bet ou raise.")
            if amount_value is not None and (not isinstance(amount_value, int) or isinstance(amount_value, bool)):
                raise ValueError("Os valores de bet e raise devem ser totais inteiros de fichas.")
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
            process_feedback = _process_feedback(
                action,
                coach,
                call_amount=call_amount,
                target=amount_value if isinstance(amount_value, int) else None,
            )
            self._last_decision_feedback = process_feedback
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
                    rationale=coach_error or "Nenhum modelo de adversário estava disponível quando esta decisão foi tomada.",
                    review_question="Que faixa e plano para as próximas streets justificam esta decisão?",
                    variant=state.rules.variant.value,
                    process_feedback=process_feedback,
                ))
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
                    ev_call=coach.ev_call if action in (ActionType.CALL, ActionType.ALL_IN) else None,
                    bet_purpose=bet_purpose,
                    facing_cbet=(
                        state.street is not Street.PREFLOP and call_amount > 0
                        and state.rules.variant.value == "texas_holdem"
                    ),
                    out_of_position=hero.position is not None and hero.position.value not in ("BTN", "CO"),
                    rationale=coach.advice,
                    review_question=(
                        coach.learning_steps[-1]["body"] if coach.learning_steps else
                        "Qual suposição sobre a faixa e qual plano para as próximas streets mais importaram?"
                    ),
                    variant=state.rules.variant.value,
                    equity_source=coach.equity_source,
                    equity_iterations=coach.iterations,
                    opponent_range_size=coach.opponent_range_size,
                    range_description=coach.range_description,
                    estimation_seed=coach.seed,
                    deterministic=coach.deterministic,
                    limitations=coach.limitations,
                    draw_analysis=coach.draw_analysis,
                    learning_steps=coach.learning_steps,
                    process_feedback=process_feedback,
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
                        "Não foi registrada uma estimativa mano a mano nesta mão. A equity multiway ainda não é modelada; "
                        "consulte a revisão da sessão para ver as ações."
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
                    coach_note = "Não há adversário ativo para estimar a equity."
            bet_bounds = state.betting_bounds(hero.id)
            min_raise = bet_bounds["minimum_raise_to"] or (state.current_bet + state.last_full_raise_size)
            max_raise = bet_bounds["maximum_raise_to"] or (hero.current_bet + hero.stack)
            spr_value = None
            if hero.is_active and not state.hand_complete and len(active_opponents) == 1 and state.pot > 0:
                spr_value = min(hero.stack, active_opponents[0].stack) / state.pot
            last_action = state.action_history[-1] if state.action_history else None
            variant_label = "Omaha Pot-Limit" if state.rules.variant is GameVariant.POT_LIMIT_OMAHA else "Texas Hold’em"
            return {
                "started": True,
                "hand_number": self._hand_number,
                # Keep the original display-valued field and expose a stable enum for API clients.
                "variant": variant_label,
                "variant_id": state.rules.variant.value,
                "variant_label": variant_label,
                "betting_structure": state.rules.betting_structure.value,
                "hole_card_count": state.rules.hole_card_count,
                "rules": {
                    "variant": state.rules.variant.value,
                    "betting_structure": state.rules.betting_structure.value,
                    "hole_card_count": state.rules.hole_card_count,
                    "min_players": state.rules.min_players,
                    "max_players": state.rules.max_players,
                },
                "table_label": f"6-max · {'Pot-limit' if state.rules.betting_structure is BettingStructure.POT_LIMIT else 'No-limit'} · $1/$2",
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
                "betting_limits": {
                    "minimum_raise_to": bet_bounds["minimum_raise_to"],
                    "maximum_raise_to": bet_bounds["maximum_raise_to"],
                    "amount_to_call": bet_bounds["amount_to_call"],
                    "all_in_to": bet_bounds["all_in_to"],
                },
                "raise_min": min_raise,
                "raise_max": max_raise,
                "amount_to_call": bet_bounds["amount_to_call"],
                "all_in_to": bet_bounds["all_in_to"],
                "can_start_next": state.hand_complete,
                "hand_complete": state.hand_complete,
                "winners": list(state.winners),
                "payouts": dict(state.payouts),
                "showdown_ranks": dict(state.showdown_ranks),
                "showdown_descriptions": {
                    player_id: HandEvaluator.describe(cards)
                    for player_id, cards in state.winning_hands
                },
                "winning_hands": {
                    player_id: [card.code for card in cards]
                    for player_id, cards in state.winning_hands
                },
                "pot_awards": [
                    {
                        "label": award.label,
                        "amount": award.amount,
                        "eligible_player_ids": list(award.eligible_player_ids),
                        "winner_ids": list(award.winner_ids),
                        "payouts": dict(award.payouts),
                        "refund_to": award.refund_to,
                    }
                    for award in state.pot_awards
                ],
                "outcome": self._outcome(state),
                "last_action": None if last_action is None else {
                    "player_id": last_action.player_id,
                    "action": last_action.action.value,
                    "chips": last_action.chips,
                },
                "coach": coach_snapshot,
                "coach_note": coach_note,
                "coach_context": coach_context,
                "coach_feedback": self._last_decision_feedback,
                "multiway": len(active_opponents) > 1,
            }

    def _run_bots(self) -> None:
        state = self._require_state()
        guard = 0
        while state.current_player_id and state.current_player_id != self.hero_id and not state.hand_complete:
            guard += 1
            if guard > 32:
                raise RuntimeError("O limite de ações dos adversários foi atingido; a mão foi interrompida com segurança.")
            bot_id = state.current_player_id
            ai = self._bots.get(bot_id)
            if ai is None:
                raise RuntimeError("O jogador neste assento não tem um perfil de adversário.")
            hero = state.player_by_id(self.hero_id)
            decision = ai.decide(
                state,
                bot_id,
                opponent_id=self.hero_id if hero and hero.is_active else None,
                allow_fold=False,
            )
            if decision.action is ActionType.FOLD:
                legal = state.legal_actions()
                fallback = ActionType.CALL if ActionType.CALL in legal else ActionType.CHECK
                decision = replace(
                    decision,
                    action=fallback,
                    amount=None,
                    reason=f"{decision.reason} A mesa converte fold automático em {fallback.value}.",
                )
            legal_for_bot = state.legal_actions(allow_fold=False)
            if decision.action not in legal_for_bot:
                decision = replace(
                    decision,
                    action=ActionType.CALL if ActionType.CALL in legal_for_bot else ActionType.CHECK,
                    amount=None,
                )
            state = state.apply_action(bot_id, decision.action, decision.amount, allow_fold=False)
        self._state = state

    def _resolve_showdown(self) -> None:
        state = self._require_state()
        if state.street is Street.SHOWDOWN and not state.hand_complete:
            state = state.resolve_showdown()
            self._state = state

    def _record_if_complete(self) -> None:
        state = self._require_state()
        if state.hand_complete and not self._recorded:
            self._stacks = [player.stack for player in state.players]
            self._tracker.record_hand(state, self.hero_id, self._decisions)
            self._recorded = True

    def _require_state(self) -> GameState:
        if self._state is None:
            raise ValueError("Distribua uma mão antes de escolher uma ação.")
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
                state, self.hero_id, opponent.id if opponent else None, iterations=256,
                seed=(self._hand_number * 1_000_003 + len(state.action_history)) % (2**32),
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
            return f"Você ganhou ${hero_payout:.2f}" if len(state.winners) == 1 else f"Pote dividido · ${hero_payout:.2f} para você"
        return "Mão concluída · o adversário levou o pote"


def _resolve_variant(value: GameVariant | str) -> GameVariant:
    if not isinstance(value, (str, GameVariant)):
        raise ValueError("A modalidade deve ser 'texas_holdem' ou 'pot_limit_omaha'.")
    try:
        return GameVariant(value)
    except ValueError as exc:
        raise ValueError(
            f"Modalidade não compatível: '{value}'. Modalidades disponíveis: Texas Hold’em e Omaha Pot-Limit."
        ) from exc


def _rules_for(variant: GameVariant) -> GameRules:
    if variant is GameVariant.POT_LIMIT_OMAHA:
        return GameRules.pot_limit_omaha()
    return GameRules.texas_holdem()


def _process_feedback(
    action: ActionType,
    coach: CoachSnapshot | None,
    *,
    call_amount: int,
    target: int | None,
) -> str:
    if coach is None:
        return (
            "Sua ação seguiu as regras da mesa. Na revisão, anote a faixa, o preço e o plano para as próximas streets; "
            "o resultado da mão, por si só, não avalia esse raciocínio."
        )
    if action in (ActionType.CALL, ActionType.FOLD) and call_amount > 0 and coach.pot_odds_percentage is not None:
        gap = coach.equity_percentage - coach.pot_odds_percentage
        if gap > 0:
            relation = f"A equity modelada ficou {gap:.1f} pontos acima do preço imediato do call."
        elif gap < 0:
            relation = f"A equity modelada ficou {abs(gap):.1f} pontos abaixo do preço imediato do call."
        else:
            relation = "A equity modelada correspondeu ao preço imediato do call."
        if action is ActionType.CALL:
            return (
                f"Você deu call. {relation} Confira se a suposição sobre a faixa e o plano para as próximas streets justificam a escolha; "
                "este é um ponto de revisão do raciocínio, não um veredito baseado no resultado da mão."
            )
        return (
            f"Você deu fold antes de pagar o call. {relation} Se sua leitura diferiu do modelo, compare-a "
            "com a faixa na revisão; o resultado não determina se a escolha foi boa."
        )
    if action is ActionType.CHECK:
        return (
            "Você deu check sem precisar pagar um call. Na revisão, avalie se uma mão pior poderia pagar por valor ou se uma mão melhor "
            "poderia desistir; o check também pode manter o pote controlado."
        )
    if action in (ActionType.BET, ActionType.RAISE):
        total = f" até {target} fichas" if target is not None else ""
        return (
            f"A mesa aceitou seu {action.value} dentro das regras{total}. A equity de um call, por si só, não justifica uma aposta; "
            "avalie quais mãos piores poderiam continuar ou quais mãos melhores poderiam desistir."
        )
    if action is ActionType.ALL_IN:
        return (
            "A mesa aceitou este all-in conforme as regras da mão. Ser permitido não significa ser a melhor decisão: revise "
            "o preço, o stack efetivo, a faixa e o risco de redraw."
        )
    return "Você deu fold. Na revisão, compare a faixa que atribuiu ao adversário com o preço e o plano que tinha em mente."
