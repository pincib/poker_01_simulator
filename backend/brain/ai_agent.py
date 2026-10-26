"""Profile-driven Hold'em opponent actions using ranges, equity, and sizing."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import Enum
from itertools import combinations
from typing import Sequence

from backend.brain.board_texture import BoardTexture, BoardTextureClassifier, SuitPattern
from backend.brain.bet_sizing import BetSizer, SizingOption
from backend.brain.equity import EquityCalculator
from backend.brain.pot_odds import PotOddsCalculator
from backend.brain.ranges import PreflopRange, get_opening_range, starting_hand_class
from backend.engine.card import Card, Rank, Suit
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player, Position
from backend.engine.rules import GameVariant


_FULL_DECK_CARDS = tuple(Card(rank, suit) for suit in Suit for rank in Rank)


def _neutral_texture() -> BoardTexture:
    return BoardTexture(False, SuitPattern.RAINBOW, False, 0, False, False, 0, 0)


def plo_starting_hand_score(hole_cards: Sequence[Card]) -> float:
    """Return a transparent 0-100 heuristic for PLO4 starting-hand structure.

    This is a profile input, not a solved preflop equity or GTO ranking. It rewards
    high-card strength, pairs, suited ace potential and compact connected ranks.
    """
    if len(hole_cards) != 4 or len(set(hole_cards)) != 4:
        raise ValueError("PLO starting-hand score requires four distinct hole cards.")
    ranks = [int(card.rank) for card in hole_cards]
    score = sum(sorted(ranks, reverse=True)) * 0.72
    rank_counts = {rank: ranks.count(rank) for rank in set(ranks)}
    score += sum(8.0 + (rank - 10) * 0.65 for rank, count in rank_counts.items() if count >= 2)
    suit_counts = {suit: sum(card.suit is suit for card in hole_cards) for suit in Suit}
    for suit, count in suit_counts.items():
        if count == 2:
            score += 4.0
        elif count >= 3:
            score += 2.0  # A third card in a suit reduces two-card backup quality.
        if count >= 2 and any(card.suit is suit and card.rank is Rank.ACE for card in hole_cards):
            score += 4.0
    unique_ranks = sorted(set(ranks))
    connectivity = 0.0
    for low, high in combinations(unique_ranks, 2):
        gap = high - low
        if gap == 1:
            connectivity += 2.0
        elif gap == 2:
            connectivity += 1.0
        elif gap == 3:
            connectivity += 0.25
    if Rank.ACE.value in unique_ranks and 2 in unique_ranks:
        connectivity += 1.0  # Wheel connectivity.
    score += min(connectivity, 12.0)
    return round(min(100.0, max(0.0, score)), 1)


class OpponentProfile(str, Enum):
    NIT = "nit"
    STATION = "station"
    TAG = "tag"
    BALANCED = "balanced"

    @property
    def display_name(self) -> str:
        return {
            OpponentProfile.NIT: "Nitty Norman",
            OpponentProfile.STATION: "Calling Kevin",
            OpponentProfile.TAG: "Aggro Alex",
            OpponentProfile.BALANCED: "Balanced Blair",
        }[self]

    @classmethod
    def parse(cls, profile: OpponentProfile | str) -> OpponentProfile:
        if isinstance(profile, cls):
            return profile
        normalized = profile.strip().lower()
        aliases = {
            "tight": cls.NIT,
            "calling_station": cls.STATION,
            "calling station": cls.STATION,
            "aggressive": cls.TAG,
            "balanced heuristic": cls.BALANCED,
        }
        if normalized in aliases:
            return aliases[normalized]
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
    profile: str = "tag"
    seed: int | None = None
    range_size: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "amount": self.amount,
            "reason": self.reason,
            "equity_percentage": self.equity_percentage,
            "pot_odds_percentage": self.pot_odds_percentage,
            "sizing": self.sizing.value if self.sizing else None,
            "profile": self.profile,
            "seed": self.seed,
            "range_size": self.range_size,
        }


class OpponentAI:
    """Selectable heuristic baseline; profiles are not solver/GTO strategies."""

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
        self.decision_history: list[AIDecision] = []

    def decide(
        self, state: GameState, player_id: str, opponent_id: str | None = None, *, seed: int | None = None
    ) -> AIDecision:
        """Choose a legal action for the current player without reading opponents' cards."""
        player = state.current_player
        if player is None or player.id != player_id:
            raise ValueError("AI can decide only for the player currently waiting to act.")
        if len(player.hole_cards) != state.rules.hole_card_count:
            raise ValueError("AI player's private-card count does not match the game variant.")
        legal = state.legal_actions()
        opponents = [candidate for candidate in state.players if candidate.id != player_id and candidate.is_active]
        if opponent_id is not None:
            opponents = [candidate for candidate in opponents if candidate.id == opponent_id]
        if not opponents:
            raise ValueError("AI decision requires at least one active opponent.")
        decision_seed = seed if seed is not None else self._random.getrandbits(32)
        self._random = random.Random(decision_seed)
        if state.rules.variant is GameVariant.POT_LIMIT_OMAHA:
            decision = self._decide_plo(state, player, opponents, legal, decision_seed)
        else:
            opponent = max(opponents, key=lambda candidate: candidate.current_bet)
            decision = (
                self._decide_preflop(state, player, opponent, legal)
                if state.street is Street.PREFLOP
                else self._decide_postflop(state, player, opponent, legal)
            )
        decision = replace(decision, profile=self.profile.value, seed=decision_seed)
        self.decision_history.append(decision)
        return decision

    def _decide_plo(
        self,
        state: GameState,
        player: Player,
        opponents: Sequence[Player],
        legal: Sequence[ActionType],
        decision_seed: int,
    ) -> AIDecision:
        if state.street is Street.PREFLOP:
            return self._decide_plo_preflop(state, player, legal)

        ranges = tuple(
            self._sample_plo_opponent_range(state, player, opponent, self._random.getrandbits(32))
            for opponent in opponents
        )
        equity_seed = self._random.getrandbits(32)
        if len(ranges) == 1:
            equity_result = EquityCalculator.calculate(
                player.hole_cards, board=state.community_cards, villain_range=ranges[0],
                iterations=self.equity_iterations, seed=equity_seed,
            )
        else:
            equity_result = EquityCalculator.calculate_multiway(
                player.hole_cards, ranges, board=state.community_cards,
                iterations=self.equity_iterations, seed=equity_seed,
            )
        equity = equity_result.equity_percentage
        to_call = state.amount_to_call
        pot_odds = PotOddsCalculator.calculate(to_call, state.pot).required_equity_percentage
        texture = BoardTextureClassifier.classify(state.community_cards)
        _, chosen = HandEvaluator.evaluate_plo_with_hand(player.hole_cards, state.community_cards)
        hand_description = HandEvaluator.describe(chosen)
        from backend.brain.plo_draws import OmahaWrapDetector
        draws = OmahaWrapDetector.analyze(player.hole_cards, state.community_cards)
        nut_out_count = len(draws.nut_outs)
        nut_flush_count = len(draws.nut_flush_outs)
        effective_stack = min(player.stack, *(opponent.stack for opponent in opponents))
        spr = effective_stack / max(state.pot, 1)
        in_position = self._is_in_position(player, opponents, state)
        positional_adjustment = -2.0 if in_position else 2.0
        draw_adjustment = min(8.0, nut_out_count * 0.25 + nut_flush_count * 0.75)

        call_adjustment = {
            OpponentProfile.NIT: 7.0,
            OpponentProfile.STATION: -8.0,
            OpponentProfile.TAG: 1.0,
            OpponentProfile.BALANCED: 0.0,
        }[self.profile]
        call_threshold = max(0.0, pot_odds + call_adjustment + positional_adjustment - draw_adjustment)
        raise_threshold = {
            OpponentProfile.NIT: max(78.0, call_threshold + 24),
            OpponentProfile.STATION: max(88.0, call_threshold + 34),
            OpponentProfile.TAG: max(70.0, call_threshold + 24),
            OpponentProfile.BALANCED: max(74.0, call_threshold + 24),
        }[self.profile]
        value_threshold = {
            OpponentProfile.NIT: 72.0,
            OpponentProfile.STATION: 80.0,
            OpponentProfile.TAG: 62.0,
            OpponentProfile.BALANCED: 65.0,
        }[self.profile]
        range_size = sum(map(len, ranges))

        def with_range_size(decision: AIDecision) -> AIDecision:
            return replace(decision, range_size=range_size)

        summary = (
            f"PLO {hand_description}; equity {equity:.1f}% from {equity_result.iterations} seeded rollouts "
            f"against {len(opponents)} sampled heuristic range(s) ({range_size} combos); "
            f"nut outs {nut_out_count}, nut-flush outs {nut_flush_count}, SPR {spr:.1f}, "
            f"{'in position' if in_position else 'out of position'}."
        )

        if to_call > 0:
            if equity >= raise_threshold and ActionType.RAISE in legal:
                return self._plo_aggressive_decision(
                    state, player, legal, equity, pot_odds, ranges, texture,
                    fraction=0.66 if texture.wet else 0.5,
                    reason=f"{summary} Raise threshold met; pot-limit bounds cap the target.",
                )
            if equity >= call_threshold and ActionType.CALL in legal:
                return with_range_size(self._decision(
                    ActionType.CALL,
                    f"{summary} Call threshold {call_threshold:.1f}% covers pot odds {pot_odds:.1f}%; heuristic profile decision.",
                    equity=equity, pot_odds=pot_odds,
                ))
            if ActionType.FOLD in legal:
                return with_range_size(self._decision(
                    ActionType.FOLD,
                    f"{summary} Estimated equity is below the profile's {call_threshold:.1f}% call threshold.",
                    equity=equity, pot_odds=pot_odds,
                ))

        bluff_frequency = {
            OpponentProfile.NIT: 0.01,
            OpponentProfile.STATION: 0.01,
            OpponentProfile.TAG: 0.05 if texture.wet else 0.08,
            OpponentProfile.BALANCED: 0.12 if texture.dry else 0.07,
        }[self.profile]
        if equity >= value_threshold or (equity >= value_threshold - 8 and nut_out_count >= 8):
            return self._plo_aggressive_decision(
                state, player, legal, equity, pot_odds, ranges, texture,
                fraction=0.66 if texture.wet else 0.5,
                reason=f"{summary} Value/draw threshold met; target is clipped to the pot-limit maximum.",
            )
        if self._random.random() < bluff_frequency:
            return self._plo_aggressive_decision(
                state, player, legal, equity, pot_odds, ranges, texture,
                fraction=0.33,
                reason=f"{summary} Low-frequency profile bluff selected; this is a heuristic, not solver output.",
            )
        return with_range_size(self._decision(
            ActionType.CHECK,
            f"{summary} Checks outside the value and bluff thresholds.",
            equity=equity, pot_odds=pot_odds,
        ))

    def _decide_plo_preflop(
        self, state: GameState, player: Player, legal: Sequence[ActionType]
    ) -> AIDecision:
        score = plo_starting_hand_score(player.hole_cards)
        position = player.position or Position.UNDER_THE_GUN
        position_threshold = {
            Position.UNDER_THE_GUN: 60.0,
            Position.HIJACK: 57.0,
            Position.CUTOFF: 54.0,
            Position.BUTTON: 50.0,
            Position.SMALL_BLIND: 55.0,
            Position.BIG_BLIND: 44.0,
        }[position]
        profile_adjustment = {
            OpponentProfile.NIT: 8.0,
            OpponentProfile.STATION: -9.0,
            OpponentProfile.TAG: 0.0,
            OpponentProfile.BALANCED: -2.0,
        }[self.profile]
        threshold = position_threshold + profile_adjustment
        call = state.amount_to_call
        price_ratio = call / max(state.pot + call, 1)
        if price_ratio <= 0.12:
            threshold -= 5
        elif price_ratio >= 0.35:
            threshold += 6
        if state.pot > 0 and player.stack / state.pot < 2:
            threshold += 3
        summary = (
            f"PLO4 preflop quality {score:.1f} vs {threshold:.1f} threshold; "
            f"{position.value}, {player.stack / max(state.pot, 1):.1f} stack/pot. "
            "Quality reflects pair strength, suitedness, connectivity and nut-suit potential."
        )
        raise_margin = {
            OpponentProfile.NIT: 22.0,
            OpponentProfile.STATION: 32.0,
            OpponentProfile.TAG: 18.0,
            OpponentProfile.BALANCED: 20.0,
        }[self.profile]
        raise_frequency = {
            OpponentProfile.NIT: 0.35,
            OpponentProfile.STATION: 0.08,
            OpponentProfile.TAG: 0.3,
            OpponentProfile.BALANCED: 0.24,
        }[self.profile]
        if score >= threshold + raise_margin and self._random.random() < raise_frequency:
            return self._plo_aggressive_decision(
                state, player, legal, None, None, (), BoardTextureClassifier.classify((
                    state.community_cards if len(state.community_cards) >= 3 else
                    (player.hole_cards[0], player.hole_cards[1], player.hole_cards[2])
                )),
                fraction=0.66,
                reason=f"{summary} Strong four-card structure selected for a pot-limit raise.",
            )
        if score >= threshold and call > 0 and ActionType.CALL in legal:
            return self._decision(ActionType.CALL, f"{summary} Continues at this price.")
        if score >= threshold and call == 0:
            if ActionType.RAISE in legal or ActionType.BET in legal:
                return self._plo_aggressive_decision(
                    state, player, legal, None, None, (),
                    BoardTextureClassifier.classify((
                        player.hole_cards[0], player.hole_cards[1], player.hole_cards[2]
                    )),
                    fraction=0.66,
                    reason=f"{summary} Opens within the profile's position-adjusted PLO range.",
                )
            return self._decision(ActionType.CHECK, f"{summary} No raise is currently available.")
        action = ActionType.FOLD if call > 0 and ActionType.FOLD in legal else ActionType.CHECK
        return self._decision(action, f"{summary} Folds or checks outside the starting-hand threshold.")

    def _sample_plo_opponent_range(
        self, state: GameState, hero: Player, opponent: Player, seed: int
    ) -> tuple[tuple[Card, ...], ...]:
        rng = random.Random(seed)
        available = [card for card in _FULL_DECK_CARDS if card not in set(hero.hole_cards + state.community_cards)]
        sampled: dict[tuple[str, ...], tuple[float, tuple[Card, ...]]] = {}
        attempts = 0
        while len(sampled) < 512 and attempts < 3_000:
            attempts += 1
            hand = tuple(rng.sample(available, 4))
            key = tuple(sorted(card.code for card in hand))
            if key not in sampled:
                sampled[key] = (plo_starting_hand_score(hand), hand)
        ordered = sorted(sampled.values(), key=lambda item: item[0], reverse=True)
        keep_fraction = {
            OpponentProfile.NIT: 0.18,
            OpponentProfile.STATION: 0.68,
            OpponentProfile.TAG: 0.34,
            OpponentProfile.BALANCED: 0.4,
        }[self.profile]
        position = opponent.position
        if position in (Position.BUTTON, Position.CUTOFF):
            keep_fraction += 0.12
        elif position is Position.UNDER_THE_GUN:
            keep_fraction -= 0.08
        last_action = next((
            record.action for record in reversed(state.action_history) if record.player_id == opponent.id
        ), None)
        keep_fraction *= {
            ActionType.RAISE: 0.55,
            ActionType.BET: 0.62,
            ActionType.CALL: 0.84,
            ActionType.CHECK: 1.0,
            ActionType.FOLD: 1.0,
            None: 1.0,
        }[last_action]
        keep_count = max(24, round(len(ordered) * min(0.9, max(0.08, keep_fraction))))
        return tuple(hand for _, hand in ordered[:keep_count])

    def _plo_aggressive_decision(
        self,
        state: GameState,
        player: Player,
        legal: Sequence[ActionType],
        equity: float | None,
        pot_odds: float | None,
        opponent_ranges: Sequence[Sequence[Sequence[Card]]],
        texture: BoardTexture,
        *,
        fraction: float,
        reason: str,
    ) -> AIDecision:
        bounds = state.betting_bounds(player.id)
        minimum = int(bounds["minimum_raise_to"] or state.big_blind)
        maximum = int(bounds["maximum_raise_to"] or player.current_bet + player.stack)
        facing = state.amount_to_call > 0
        option = SizingOption.SMALL_CBET if fraction <= 0.4 else SizingOption.STANDARD
        if facing:
            increment = max(state.last_full_raise_size, round((state.pot + state.amount_to_call) * fraction))
            target = min(maximum, state.current_bet + increment)
            if target < minimum:
                if ActionType.ALL_IN in legal:
                    return self._decision(ActionType.ALL_IN, reason + f" Short all-in is the only legal raise; max-to {maximum}.", equity=equity, pot_odds=pot_odds)
                return self._decision(ActionType.CALL, reason + " Raise unavailable at the current pot-limit cap.", equity=equity, pot_odds=pot_odds)
            action = ActionType.RAISE
        else:
            target = min(maximum, max(state.big_blind, player.current_bet + round(state.pot * fraction)))
            if target <= state.current_bet or target < state.big_blind:
                if ActionType.CHECK in legal:
                    return self._decision(ActionType.CHECK, reason + " Bet unavailable at the current pot-limit cap.", equity=equity, pot_odds=pot_odds)
                return self._decision(ActionType.FOLD, reason + " No legal aggressive action.", equity=equity, pot_odds=pot_odds)
            action = ActionType.BET if ActionType.BET in legal else ActionType.RAISE
        if action not in legal:
            if ActionType.ALL_IN in legal:
                return self._decision(ActionType.ALL_IN, reason + f" Uses the legal all-in cap {maximum}.", equity=equity, pot_odds=pot_odds)
            return self._decision(ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL, reason + " Aggression is not legal in this state.", equity=equity, pot_odds=pot_odds)
        return replace(
            self._decision(action, reason + f" Target {target}, backend pot-limit maximum-to {maximum}.", target,
                           equity=equity, pot_odds=pot_odds, sizing=option),
            range_size=sum(len(range_) for range_ in opponent_ranges) if opponent_ranges else None,
        )

    @staticmethod
    def _is_in_position(player: Player, opponents: Sequence[Player], state: GameState) -> bool:
        order = {Position.BUTTON: 0, Position.CUTOFF: 1, Position.HIJACK: 2,
                 Position.UNDER_THE_GUN: 3, Position.BIG_BLIND: 4, Position.SMALL_BLIND: 5}
        return all(order.get(player.position, 6) < order.get(opponent.position, 6) for opponent in opponents)

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
            OpponentProfile.BALANCED: None,
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
                OpponentProfile.BALANCED: pot_odds - 1,
            }[self.profile]
            if self.profile is OpponentProfile.STATION and self._has_pair(player, state.community_cards):
                should_call = True
            elif self.profile is OpponentProfile.BALANCED and equity >= call_threshold - 3 and equity < call_threshold + 3:
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
            OpponentProfile.BALANCED: 62.0,
        }[self.profile]
        value_bet = equity >= value_threshold
        bluff_frequency = {
            OpponentProfile.NIT: 0.01,
            OpponentProfile.STATION: 0.01,
            OpponentProfile.TAG: 0.08 if texture.dry else 0.04,
            OpponentProfile.BALANCED: 0.12 if texture.dry else 0.07,
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
            OpponentProfile.BALANCED: 0.22,
        }[self.profile]

    def _value_raise_threshold(self) -> float:
        return {
            OpponentProfile.NIT: 78.0,
            OpponentProfile.STATION: 88.0,
            OpponentProfile.TAG: 68.0,
            OpponentProfile.BALANCED: 72.0,
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
