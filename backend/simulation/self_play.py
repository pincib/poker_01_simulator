"""Seeded variant-aware self-play with per-hand settlement and chip audits.

The action policy is intentionally a lightweight rules stressor, not a product
bot strategy or a solver. PLO runs default to the no-rake training rules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player
from backend.engine.rules import GameRules, GameVariant


@dataclass(frozen=True, slots=True)
class RakePolicy:
    """Cash-game rake in basis points with a cap and no-flop-no-drop rule."""

    basis_points: int = 500
    cap: int = 3
    no_flop_no_drop: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.basis_points, int) or isinstance(self.basis_points, bool) or not 0 <= self.basis_points <= 10_000:
            raise ValueError("Rake basis points must be an integer from 0 to 10000.")
        if not isinstance(self.cap, int) or isinstance(self.cap, bool) or self.cap < 0:
            raise ValueError("Rake cap must be a non-negative integer.")

    def collect(self, pot: int, *, flop_dealt: bool) -> int:
        if not isinstance(pot, int) or isinstance(pot, bool) or pot < 0:
            raise ValueError("Pot must be a non-negative integer.")
        if self.no_flop_no_drop and not flop_dealt:
            return 0
        return min(self.cap, pot * self.basis_points // 10_000)


@dataclass(frozen=True, slots=True)
class SelfPlayResult:
    hands: int
    starting_chips: int
    chips_after_payouts: int
    rake_collected: int
    actions: int
    showdowns: int
    hands_won_by_fold: int
    max_actions_in_a_hand: int
    variant: str
    ties: int
    all_in_hands: int
    all_in_events: int
    fold_actions: int
    deadlocks: int

    @property
    def chips_conserved(self) -> bool:
        return self.chips_after_payouts + self.rake_collected == self.starting_chips


class SelfPlaySimulator:
    """Play independent Hold'em or PLO hands and audit each settlement."""

    def __init__(
        self,
        *,
        seed: int = 1,
        player_count: int = 6,
        starting_stack: int = 1_000,
        small_blind: int = 5,
        big_blind: int = 10,
        rake: RakePolicy | None = None,
        max_actions_per_hand: int = 200,
        variant: GameVariant | str = GameVariant.TEXAS_HOLDEM,
    ) -> None:
        try:
            self._variant = GameVariant(variant)
        except ValueError as exc:
            raise ValueError(f"Unsupported self-play variant: {variant!r}.") from exc
        self._rules = (
            GameRules.pot_limit_omaha()
            if self._variant is GameVariant.POT_LIMIT_OMAHA
            else GameRules.texas_holdem()
        )
        if not self._rules.min_players <= player_count <= self._rules.max_players:
            raise ValueError(
                f"{self._variant.value} self-play supports {self._rules.min_players} "
                f"to {self._rules.max_players} players."
            )
        if not isinstance(starting_stack, int) or isinstance(starting_stack, bool) or starting_stack <= 0:
            raise ValueError("Starting stack must be a positive integer.")
        if small_blind <= 0 or big_blind < small_blind:
            raise ValueError("Blinds must satisfy 0 < small blind <= big blind.")
        if max_actions_per_hand <= 0:
            raise ValueError("Action limit must be positive.")
        if rake is not None and not isinstance(rake, RakePolicy):
            raise ValueError("rake must be a RakePolicy instance.")
        # The PLO training MVP explicitly has no rake; Hold'em keeps its
        # existing cash-game default. Callers can still pass a policy directly.
        if rake is None:
            rake = (
                RakePolicy(basis_points=0, cap=0)
                if self._variant is GameVariant.POT_LIMIT_OMAHA
                else RakePolicy()
            )
        self._seed = seed
        self._player_count = player_count
        self._starting_stack = starting_stack
        self._small_blind = small_blind
        self._big_blind = big_blind
        self._rake = rake
        self._max_actions_per_hand = max_actions_per_hand

    def run(self, hands: int = 50_000) -> SelfPlayResult:
        if not isinstance(hands, int) or isinstance(hands, bool) or hands <= 0:
            raise ValueError("Hand count must be a positive integer.")
        rng = random.Random(self._seed)
        initial_chips = self._player_count * self._starting_stack
        total_after = total_rake = action_total = showdowns = fold_wins = max_actions_seen = 0
        ties = all_in_hands = all_in_events = fold_actions = 0

        for hand_number in range(hands):
            players = tuple(
                Player(f"bot-{seat}", f"Bot {seat + 1}", self._starting_stack)
                for seat in range(self._player_count)
            )
            deck = Deck(seed=rng.getrandbits(64))
            state = GameState.new_hand(
                players,
                self._small_blind,
                self._big_blind,
                button_index=hand_number % self._player_count,
                deck=deck,
                rules=self._rules,
            )
            hand_actions = 0
            hand_all_in_events = 0
            if state.street is Street.SHOWDOWN and not state.hand_complete:
                state = self._resolve_showdown(state)
            while not state.hand_complete:
                # _auto_progress may finish a full board while everyone who
                # can act is all-in. That state still needs its showdown ranks.
                if state.street is Street.SHOWDOWN:
                    state = self._resolve_showdown(state)
                    break
                if hand_actions >= self._max_actions_per_hand:
                    raise RuntimeError(f"Self-play deadlocked on hand {hand_number + 1}.")
                actor = state.current_player
                legal = state.legal_actions()
                if actor is None or not legal:
                    raise RuntimeError(f"Hand {hand_number + 1} has no legal next action.")
                action, amount = self._choose_action(state, actor, legal, rng)
                state = state.apply_action(actor.id, action, amount)
                hand_actions += 1
                fold_actions += int(action is ActionType.FOLD)
                updated_actor = state.player_by_id(actor.id)
                hand_all_in_events += int(
                    action is ActionType.ALL_IN or bool(updated_actor and updated_actor.is_all_in)
                )

            action_total += hand_actions
            max_actions_seen = max(max_actions_seen, hand_actions)
            if state.street is Street.SHOWDOWN and not state.payouts:
                state = self._resolve_showdown(state)
            if state.showdown_ranks:
                showdowns += 1
            else:
                # A fold may occur before a later showdown, so classify the
                # hand by settlement path rather than its final action.
                fold_wins += 1

            all_in_events += hand_all_in_events
            all_in_hands += int(hand_all_in_events > 0)
            ties += int(any(len(award.winner_ids) > 1 for award in state.pot_awards))

            rake_amount = self._rake.collect(state.pot if not state.hand_complete else sum(p.total_contributed for p in state.players), flop_dealt=len(state.community_cards) >= 3)
            payout_total = sum(amount for _, amount in state.payouts)
            if payout_total != sum(player.total_contributed for player in state.players):
                raise RuntimeError(f"Payouts do not match contributions on hand {hand_number + 1}.")
            if not state.hand_complete or state.current_player_id is not None:
                raise RuntimeError(f"Self-play hand {hand_number + 1} did not reach a terminal state.")
            adjusted_payouts = dict(state.payouts)
            remaining_rake = rake_amount
            for player_id, payout in state.payouts:
                deduction = min(payout, remaining_rake)
                adjusted_payouts[player_id] -= deduction
                remaining_rake -= deduction
            if remaining_rake:
                raise RuntimeError(f"Rake exceeded the available pot on hand {hand_number + 1}.")
            ending_stacks = sum(player.stack for player in state.players) - payout_total + sum(adjusted_payouts.values())
            if ending_stacks + rake_amount != initial_chips:
                raise RuntimeError(f"Chips were not conserved on hand {hand_number + 1}.")
            total_after += ending_stacks
            total_rake += rake_amount

        return SelfPlayResult(
            hands=hands,
            starting_chips=initial_chips * hands,
            chips_after_payouts=total_after,
            rake_collected=total_rake,
            actions=action_total,
            showdowns=showdowns,
            hands_won_by_fold=fold_wins,
            max_actions_in_a_hand=max_actions_seen,
            variant=self._variant.value,
            ties=ties,
            all_in_hands=all_in_hands,
            all_in_events=all_in_events,
            fold_actions=fold_actions,
            deadlocks=0,
        )

    @staticmethod
    def _resolve_showdown(state: GameState) -> GameState:
        return state.resolve_showdown()

    def _choose_action(self, state: GameState, actor: Player, legal: tuple[ActionType, ...], rng: random.Random) -> tuple[ActionType, int | None]:
        call_amount = state.amount_to_call
        if ActionType.ALL_IN in legal and rng.random() < 0.035:
            return ActionType.ALL_IN, None
        if call_amount == 0:
            bet_action = ActionType.BET if ActionType.BET in legal else ActionType.RAISE
            if bet_action in legal and state.street is not Street.PREFLOP and rng.random() < 0.08:
                bounds = state.betting_bounds(actor.id)
                minimum = int(bounds["minimum_raise_to"] or state.current_bet + self._big_blind)
                maximum = int(bounds["maximum_raise_to"] or actor.current_bet + actor.stack)
                target = min(
                    maximum,
                    max(minimum, actor.current_bet + max(self._big_blind, state.pot // 3)),
                )
                if target > state.current_bet:
                    return bet_action, target
            return ActionType.CHECK, None
        if ActionType.FOLD in legal and rng.random() < 0.04:
            return ActionType.FOLD, None
        return ActionType.CALL, None
