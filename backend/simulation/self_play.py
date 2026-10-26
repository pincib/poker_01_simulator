"""Seeded Hold'em bot self-play with per-hand chip and rake accounting."""

from __future__ import annotations

import random
from dataclasses import dataclass

from backend.engine.deck import Deck
from backend.engine.evaluator import HandEvaluator
from backend.engine.game_state import ActionType, GameState, Street
from backend.engine.player import Player


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

    @property
    def chips_conserved(self) -> bool:
        return self.chips_after_payouts + self.rake_collected == self.starting_chips


class SelfPlaySimulator:
    """Play independent, cash-table bot hands and audit each settlement."""

    def __init__(
        self,
        *,
        seed: int = 1,
        player_count: int = 6,
        starting_stack: int = 1_000,
        small_blind: int = 5,
        big_blind: int = 10,
        rake: RakePolicy = RakePolicy(),
        max_actions_per_hand: int = 200,
    ) -> None:
        if not 2 <= player_count <= 6:
            raise ValueError("Self-play supports two to six players.")
        if not isinstance(starting_stack, int) or isinstance(starting_stack, bool) or starting_stack <= 0:
            raise ValueError("Starting stack must be a positive integer.")
        if small_blind <= 0 or big_blind < small_blind:
            raise ValueError("Blinds must satisfy 0 < small blind <= big blind.")
        if max_actions_per_hand <= 0:
            raise ValueError("Action limit must be positive.")
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
        total_after = total_rake = action_total = showdowns = folds = max_actions_seen = 0

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
            )
            hand_actions = 0
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

            action_total += hand_actions
            max_actions_seen = max(max_actions_seen, hand_actions)
            folds += int(bool(state.action_history and state.action_history[-1].action is ActionType.FOLD))
            if state.street is Street.SHOWDOWN and not state.payouts:
                state = self._resolve_showdown(state)
                showdowns += 1
            elif len(state.community_cards) == 5:
                showdowns += 1

            rake_amount = self._rake.collect(state.pot if not state.hand_complete else sum(p.total_contributed for p in state.players), flop_dealt=len(state.community_cards) >= 3)
            payout_total = sum(amount for _, amount in state.payouts)
            if payout_total != (sum(player.total_contributed for player in state.players)):
                raise RuntimeError(f"Payouts do not match contributions on hand {hand_number + 1}.")
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
            hands_won_by_fold=folds,
            max_actions_in_a_hand=max_actions_seen,
        )

    @staticmethod
    def _resolve_showdown(state: GameState) -> GameState:
        rankings = {
            player.id: HandEvaluator.evaluate_7(player.hole_cards + state.community_cards)
            for player in state.players
            if player.is_active
        }
        return state.resolve_showdown(rankings)

    def _choose_action(self, state: GameState, actor: Player, legal: tuple[ActionType, ...], rng: random.Random) -> tuple[ActionType, int | None]:
        call_amount = state.amount_to_call
        if call_amount == 0:
            if ActionType.BET in legal and state.street is not Street.PREFLOP and rng.random() < 0.08:
                target = min(actor.stack, max(self._big_blind, state.pot // 3))
                if target > 0:
                    return ActionType.BET, target
            return ActionType.CHECK, None
        if ActionType.FOLD in legal and rng.random() < 0.04:
            return ActionType.FOLD, None
        return ActionType.CALL, None
