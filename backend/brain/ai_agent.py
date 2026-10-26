"""Profile-driven Hold'em opponent actions using ranges, equity, and sizing."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Sequence

from backend.brain.board_texture import BoardTexture, BoardTextureClassifier
from backend.brain.bet_sizing import BetSizer, SizingOption
from backend.brain.equity import EquityCalculator
from backend.brain.pot_odds import PotOddsCalculator
from backend.brain.ranges import PreflopRange, get_opening_range, starting_hand_class
from backend.engine.card import Card
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player, Position


class OpponentProfile(str, Enum):
    NIT = "nit"
    STATION = "station"
    TAG = "tag"
    GTO = "gto"

    @property
    def display_name(self) -> str:
        return {
            OpponentProfile.NIT: "Nitty Norman",
            OpponentProfile.STATION: "Calling Kevin",
            OpponentProfile.TAG: "Aggro Alex",
            OpponentProfile.GTO: "Solver Sam",
        }[self]

    @classmethod
    def parse(cls, profile: OpponentProfile | str) -> OpponentProfile:
        if isinstance(profile, cls):
            return profile
        normalized = profile.strip().lower()
        names = {item.display_name.lower(): item for item in cls}
        if normalized in names:
            return names[normalized]
        return cls(normalized)


@dataclass(frozen=True, slots=True)
class AIDecision:
    action: ActionType
    amount: int | None
    reason: str
    equity_percentage: float | None = None
    pot_odds_percentage: float | None = None
    sizing: SizingOption | None = None


class OpponentAI:
    """A selectable opponent baseline; Solver Sam is GTO-inspired, not solved."""

    def __init__(
        self,
        profile: OpponentProfile | str = OpponentProfile.TAG,
        *,
        equity_iterations: int = 512,
        seed: int | None = None,
    ) -> None:
        self.profile = OpponentProfile.parse(profile)
        if not isinstance(equity_iterations, int) or isinstance(equity_iterations, bool) or equity_iterations <= 0:
            raise ValueError("Equity iterations must be a positive integer.")
        self.equity_iterations = equity_iterations
        self._random = random.Random(seed)

    def decide(self, state: GameState, player_id: str, opponent_id: str | None = None) -> AIDecision:
        """Choose a legal action for the current player without reading opponents' cards."""
        player = state.current_player
        if player is None or player.id != player_id:
            raise ValueError("AI can decide only for the player currently waiting to act.")
        if len(player.hole_cards) != 2:
            raise ValueError("AI player must have two private cards before acting.")
        legal = state.legal_actions()
        opponents = [candidate for candidate in state.players if candidate.id != player_id and candidate.is_active]
        if opponent_id is not None:
            opponents = [candidate for candidate in opponents if candidate.id == opponent_id]
        if not opponents:
            raise ValueError("AI decision requires at least one active opponent.")
        # Heads-up equity is the current math engine's supported model. Against
        # multiple players, use the active opponent showing the most street action.
        opponent = max(opponents, key=lambda candidate: candidate.current_bet)

        if state.street is Street.PREFLOP:
            return self._decide_preflop(state, player, opponent, legal)
        return self._decide_postflop(state, player, opponent, legal)

    def _decide_preflop(
        self,
        state: GameState,
        player: Player,
        opponent: Player,
        legal: Sequence[ActionType],
    ) -> AIDecision:
        position = player.position or Position.UNDER_THE_GUN
        target = {
            OpponentProfile.NIT: 10.0,
            OpponentProfile.STATION: 55.0,
            OpponentProfile.TAG: None,
            OpponentProfile.GTO: None,
        }[self.profile]
        starting_range = get_opening_range(position, target) if target is not None else get_opening_range(position)
        frequency = starting_range.frequency_for(player.hole_cards)
        hand_class = starting_hand_class(player.hole_cards)
        pair = hand_class[0] == hand_class[1]
        to_call = state.amount_to_call

        if to_call > 0:
            if self.profile is OpponentProfile.STATION:
                continue_hand = pair or frequency > 0 and self._random.random() < 0.65
            else:
                continue_hand = frequency > 0 and self._random.random() < frequency
            if not continue_hand:
                return self._decision(ActionType.FOLD, "Outside the profile's preflop continuing range.")
            premium_frequency = get_opening_range(position, 10.0).frequency_for(player.hole_cards)
            strong = premium_frequency >= 0.9
            if strong and ActionType.RAISE in legal and self._random.random() < self._preflop_raise_frequency():
                target_bet = self._preflop_raise_to(state, player)
                return self._decision(ActionType.RAISE, "Premium hand selected for a value re-raise.", target_bet)
            return self._decision(ActionType.CALL, "Hand continues against the current price.")

        if frequency > 0 and self._random.random() < frequency:
            if ActionType.RAISE in legal:
                return self._decision(ActionType.RAISE, "Open-raising within the positional range.", self._preflop_raise_to(state, player))
            if ActionType.BET in legal:
                return self._decision(ActionType.BET, "Opening the pot within the positional range.", self._preflop_raise_to(state, player))
        return self._decision(ActionType.CHECK, "Checks rather than opening this starting hand.")

    def _decide_postflop(
        self,
        state: GameState,
        player: Player,
        opponent: Player,
        legal: Sequence[ActionType],
    ) -> AIDecision:
        opponent_range = self._estimate_range(state, opponent)
        equity = EquityCalculator.calculate(
            player.hole_cards,
            board=state.community_cards,
            villain_range=opponent_range.to_combos(player.hole_cards + state.community_cards),
            iterations=self.equity_iterations,
            seed=self._random.getrandbits(32),
        ).equity_percentage
        texture = BoardTextureClassifier.classify(state.community_cards)
        to_call = state.amount_to_call
        pot_odds = PotOddsCalculator.calculate(to_call, state.pot).required_equity_percentage

        if to_call > 0:
            call_threshold = {
                OpponentProfile.NIT: pot_odds + 7,
                OpponentProfile.STATION: min(pot_odds, 24),
                OpponentProfile.TAG: pot_odds + 2,
                OpponentProfile.GTO: pot_odds - 1,
            }[self.profile]
            if self.profile is OpponentProfile.STATION and self._has_pair(player, state.community_cards):
                should_call = True
            elif self.profile is OpponentProfile.GTO and equity >= call_threshold - 3 and equity < call_threshold + 3:
                should_call = self._random.random() < 0.5
            else:
                should_call = equity >= call_threshold
            if should_call and ActionType.CALL in legal:
                return self._decision(ActionType.CALL, "Equity meets this profile's calling threshold.", equity=equity, pot_odds=pot_odds)
            if equity >= self._value_raise_threshold() and ActionType.RAISE in legal:
                return self._aggressive_decision(state, player, texture, legal, equity, pot_odds, facing_bet=True)
            return self._decision(ActionType.FOLD, "Estimated equity does not justify continuing.", equity=equity, pot_odds=pot_odds)

        value_threshold = {
            OpponentProfile.NIT: 72.0,
            OpponentProfile.STATION: 78.0,
            OpponentProfile.TAG: 58.0,
            OpponentProfile.GTO: 62.0,
        }[self.profile]
        value_bet = equity >= value_threshold
        bluff_frequency = {
            OpponentProfile.NIT: 0.01,
            OpponentProfile.STATION: 0.01,
            OpponentProfile.TAG: 0.08 if texture.dry else 0.04,
            OpponentProfile.GTO: 0.22 if texture.dry else 0.14,
        }[self.profile]
        bluff = not value_bet and self._random.random() < bluff_frequency
        aggression = ActionType.BET if ActionType.BET in legal else ActionType.RAISE
        if (value_bet or bluff) and aggression in legal:
            reason = "Value bet with strong estimated equity." if value_bet else "Selected a mixed-frequency bluff on this texture."
            return self._aggressive_decision(state, player, texture, legal, equity, pot_odds, reason=reason, polarized=value_bet and equity >= 82)
        return self._decision(ActionType.CHECK, "Checks with a hand outside the value-bet and bluff mix.", equity=equity, pot_odds=pot_odds)

    def _estimate_range(self, state: GameState, opponent: Player) -> PreflopRange:
        position = opponent.position or Position.UNDER_THE_GUN
        estimated = get_opening_range(position)
        last_action = next(
            (record.action for record in reversed(state.action_history) if record.player_id == opponent.id),
            None,
        )
        if last_action is not None:
            estimated = estimated.filtered_by_action(last_action)
        return estimated

    def _aggressive_decision(
        self,
        state: GameState,
        player: Player,
        texture: BoardTexture,
        legal: Sequence[ActionType],
        equity: float,
        pot_odds: float,
        *,
        facing_bet: bool = False,
        reason: str = "Aggressive sizing selected for the current range advantage.",
        polarized: bool = False,
    ) -> AIDecision:
        sizing = BetSizer.recommend(
            pot=state.pot,
            remaining_stack=player.stack,
            big_blind=state.big_blind,
            street=state.street,
            texture=texture,
            current_bet=state.current_bet,
            player_current_bet=player.current_bet,
            amount_to_call=state.amount_to_call if facing_bet else 0,
            minimum_raise_size=state.last_full_raise_size,
            polarized=polarized,
        )
        if sizing.option is SizingOption.ALL_IN and ActionType.ALL_IN in legal:
            action, amount = ActionType.ALL_IN, None
        else:
            action = ActionType.RAISE if facing_bet else (
                ActionType.BET if ActionType.BET in legal else ActionType.RAISE
            )
            amount = sizing.bet_to
            if action not in legal and ActionType.ALL_IN in legal:
                action, amount = ActionType.ALL_IN, None
        return self._decision(
            action, reason, amount, equity=equity, pot_odds=pot_odds, sizing=sizing.option
        )

    def _preflop_raise_to(self, state: GameState, player: Player) -> int:
        minimum = state.current_bet + state.last_full_raise_size
        if state.amount_to_call > 0:
            desired = max(minimum, state.current_bet * 3)
        else:
            desired = max(minimum, round(state.big_blind * 2.5))
        return min(player.current_bet + player.stack, desired)

    def _preflop_raise_frequency(self) -> float:
        return {
            OpponentProfile.NIT: 0.5,
            OpponentProfile.STATION: 0.08,
            OpponentProfile.TAG: 0.3,
            OpponentProfile.GTO: 0.22,
        }[self.profile]

    def _value_raise_threshold(self) -> float:
        return {
            OpponentProfile.NIT: 78.0,
            OpponentProfile.STATION: 88.0,
            OpponentProfile.TAG: 68.0,
            OpponentProfile.GTO: 72.0,
        }[self.profile]

    @staticmethod
    def _has_pair(player: Player, board: Sequence[Card]) -> bool:
        cards = player.hole_cards + tuple(board)
        return min(HandEvaluator.evaluate_5(combo) for combo in combinations(cards, 5)) <= 6185

    @staticmethod
    def _decision(
        action: ActionType,
        reason: str,
        amount: int | None = None,
        *,
        equity: float | None = None,
        pot_odds: float | None = None,
        sizing: SizingOption | None = None,
    ) -> AIDecision:
        return AIDecision(action, amount, reason, equity, pot_odds, sizing)
