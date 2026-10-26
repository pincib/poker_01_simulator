"""Immutable no-limit Hold'em hand state and betting-round transitions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Mapping, Sequence

from backend.engine.card import Card
from backend.engine.deck import Deck
from backend.engine.player import Player, Position
from backend.engine.pot import PotManager


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass(frozen=True, slots=True)
class ActionRecord:
    player_id: str
    street: Street
    action: ActionType
    chips: int
    bet_to: int


@dataclass(frozen=True, slots=True)
class GameState:
    """A hand snapshot. Every operation returns a new state and new players.

    Seats are stored clockwise. For BET and RAISE, ``amount`` passed to
    :meth:`apply_action` is the player's total street bet to raise to.
    """

    players: tuple[Player, ...]
    button_index: int
    small_blind: int
    big_blind: int
    street: Street
    community_cards: tuple[Card, ...]
    current_player_id: str | None
    pending_action_ids: tuple[str, ...]
    last_full_raise_size: int
    deck_order: tuple[Card, ...] = field(repr=False)
    deck_cursor: int = field(repr=False)
    burned_cards: tuple[Card, ...] = ()
    acted_since_full_raise: frozenset[str] = frozenset()
    action_history: tuple[ActionRecord, ...] = ()
    hand_complete: bool = False
    payouts: tuple[tuple[str, int], ...] = ()
    winners: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "players", tuple(self.players))
        object.__setattr__(self, "community_cards", tuple(self.community_cards))
        object.__setattr__(self, "pending_action_ids", tuple(self.pending_action_ids))
        object.__setattr__(self, "deck_order", tuple(self.deck_order))
        object.__setattr__(self, "burned_cards", tuple(self.burned_cards))
        object.__setattr__(self, "acted_since_full_raise", frozenset(self.acted_since_full_raise))
        object.__setattr__(self, "action_history", tuple(self.action_history))
        object.__setattr__(self, "payouts", tuple(self.payouts))
        object.__setattr__(self, "winners", tuple(self.winners))
        object.__setattr__(self, "street", Street(self.street))
        if not 2 <= len(self.players) <= 6:
            raise ValueError("A Hold'em table must have between 2 and 6 players.")
        player_ids = [player.id for player in self.players]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("Player ids must be unique in a hand.")
        if not 0 <= self.button_index < len(self.players):
            raise ValueError("Button index is outside the table.")
        if self.small_blind <= 0 or self.big_blind < self.small_blind:
            raise ValueError("Blinds must satisfy 0 < small blind <= big blind.")
        if self.last_full_raise_size <= 0:
            raise ValueError("Minimum raise size must be positive.")
        if len(self.pending_action_ids) != len(set(self.pending_action_ids)):
            raise ValueError("A player cannot appear twice in the pending action queue.")
        if any(player_id not in player_ids for player_id in self.pending_action_ids):
            raise ValueError("Pending action queue references an unknown player.")
        if any(
            not self.player_by_id(player_id).is_active or self.player_by_id(player_id).stack == 0
            for player_id in self.pending_action_ids
        ):
            raise ValueError("Only active players with chips may wait to act.")
        if self.current_player_id != (self.pending_action_ids[0] if self.pending_action_ids else None):
            raise ValueError("Current player must be first in the pending action queue.")
        if self.hand_complete and (self.current_player_id is not None or self.pending_action_ids):
            raise ValueError("A completed hand cannot have a player waiting to act.")
        if len(self.deck_order) != 52 or len(set(self.deck_order)) != 52:
            raise ValueError("Game state must retain one complete, unique 52-card deck order.")
        if not 0 <= self.deck_cursor <= 52:
            raise ValueError("Deck cursor is outside the deck.")
        dealt = list(self.community_cards) + list(self.burned_cards)
        for player in self.players:
            dealt.extend(player.hole_cards)
        if len(dealt) != len(set(dealt)):
            raise ValueError("A card cannot appear in more than one hand or board location.")
        if any(card not in self.deck_order for card in dealt):
            raise ValueError("Every dealt card must come from this hand's deck.")
        if len(dealt) != self.deck_cursor:
            raise ValueError("Deck cursor must match the cards dealt and burned so far.")
        expected_board = {Street.PREFLOP: (0,), Street.FLOP: (3,), Street.TURN: (4,), Street.RIVER: (5,)}
        if self.street in expected_board and len(self.community_cards) not in expected_board[self.street]:
            raise ValueError(f"{self.street.value} has an invalid community-card count.")
        if self.street is Street.SHOWDOWN and not self.hand_complete and len(self.community_cards) != 5:
            raise ValueError("A showdown requires a complete five-card board.")

    @classmethod
    def new_hand(
        cls,
        players: Sequence[Player],
        small_blind: int,
        big_blind: int,
        button_index: int = 0,
        *,
        deck: Deck | None = None,
    ) -> GameState:
        """Create a shuffled hand, deal two cards, and post table-stakes blinds."""
        players = tuple(players)
        if not 2 <= len(players) <= 6:
            raise ValueError("A Hold'em table must have between 2 and 6 players.")
        if not isinstance(small_blind, int) or isinstance(small_blind, bool) or small_blind <= 0:
            raise ValueError("Small blind must be a positive integer.")
        if not isinstance(big_blind, int) or isinstance(big_blind, bool) or big_blind < small_blind:
            raise ValueError("Big blind must be an integer at least as large as the small blind.")
        if not 0 <= button_index < len(players):
            raise ValueError("Button index is outside the table.")
        if len({player.id for player in players}) != len(players):
            raise ValueError("Player ids must be unique in a hand.")
        if any(player.stack <= 0 for player in players):
            raise ValueError("Every seated player must have a positive stack to start a hand.")
        if deck is None:
            deck = Deck()
        deck_order = tuple(reversed(deck.cards))
        if len(deck_order) != 52 or len(set(deck_order)) != 52:
            raise ValueError("A new hand requires a complete, unique 52-card deck.")

        position_layout = {
            2: (Position.BUTTON, Position.BIG_BLIND),
            3: (Position.BUTTON, Position.SMALL_BLIND, Position.BIG_BLIND),
            4: (Position.BUTTON, Position.SMALL_BLIND, Position.BIG_BLIND, Position.UNDER_THE_GUN),
            5: (Position.BUTTON, Position.SMALL_BLIND, Position.BIG_BLIND, Position.UNDER_THE_GUN, Position.CUTOFF),
            6: (Position.BUTTON, Position.SMALL_BLIND, Position.BIG_BLIND, Position.UNDER_THE_GUN, Position.HIJACK, Position.CUTOFF),
        }[len(players)]
        hand_players: list[Player] = []
        for player in players:
            hand_players.append(replace(
                player,
                current_bet=0,
                hole_cards=(),
                is_active=True,
                is_all_in=False,
                total_contributed=0,
            ))
        for offset, position in enumerate(position_layout):
            seat = (button_index + offset) % len(players)
            hand_players[seat] = replace(hand_players[seat], position=position)

        first_deal = button_index if len(players) == 2 else (button_index + 1) % len(players)
        deal_order = tuple((first_deal + offset) % len(players) for offset in range(len(players)))
        cursor = 0
        hole_cards: list[list[Card]] = [[] for _ in players]
        for _ in range(2):
            for seat in deal_order:
                hole_cards[seat].append(deck_order[cursor])
                cursor += 1
        for seat, cards in enumerate(hole_cards):
            hand_players[seat] = hand_players[seat].with_hole_cards(tuple(cards))

        small_blind_seat = button_index if len(players) == 2 else (button_index + 1) % len(players)
        big_blind_seat = (small_blind_seat + 1) % len(players)
        hand_players[small_blind_seat] = hand_players[small_blind_seat].commit(
            min(small_blind, hand_players[small_blind_seat].stack)
        )
        hand_players[big_blind_seat] = hand_players[big_blind_seat].commit(
            min(big_blind, hand_players[big_blind_seat].stack)
        )

        first_actor = button_index if len(players) == 2 else (big_blind_seat + 1) % len(players)
        pending = cls._clockwise_ids(hand_players, first_actor, only_can_act=True)
        state = cls(
            players=tuple(hand_players),
            button_index=button_index,
            small_blind=small_blind,
            big_blind=big_blind,
            street=Street.PREFLOP,
            community_cards=(),
            current_player_id=pending[0] if pending else None,
            pending_action_ids=pending,
            last_full_raise_size=big_blind,
            deck_order=deck_order,
            deck_cursor=cursor,
        )
        return state._auto_progress()

    @staticmethod
    def _clockwise_ids(
        players: Sequence[Player], start_index: int, *, only_can_act: bool = False
    ) -> tuple[str, ...]:
        result = []
        for offset in range(len(players)):
            player = players[(start_index + offset) % len(players)]
            if player.is_active and (not only_can_act or player.stack > 0):
                result.append(player.id)
        return tuple(result)

    @property
    def pot(self) -> int:
        return sum(player.total_contributed for player in self.players)

    @property
    def current_bet(self) -> int:
        return max((player.current_bet for player in self.players), default=0)

    @property
    def amount_to_call(self) -> int:
        player = self.current_player
        return 0 if player is None else max(0, self.current_bet - player.current_bet)

    @property
    def current_player(self) -> Player | None:
        return self.player_by_id(self.current_player_id) if self.current_player_id else None

    def player_by_id(self, player_id: str | None) -> Player | None:
        if player_id is None:
            return None
        return next((player for player in self.players if player.id == player_id), None)

    def legal_actions(self) -> tuple[ActionType, ...]:
        player = self.current_player
        if player is None or self.hand_complete:
            return ()
        actions = [ActionType.FOLD]
        to_call = max(0, self.current_bet - player.current_bet)
        can_raise = self._has_raise_right(player.id) and self._has_opponent_with_chips(player.id)
        if to_call == 0:
            actions.append(ActionType.CHECK)
            if can_raise and player.stack > 0:
                actions.append(ActionType.BET if self.current_bet == 0 else ActionType.RAISE)
        else:
            actions.append(ActionType.CALL)
            if can_raise and player.stack > to_call:
                actions.append(ActionType.RAISE)
        if player.stack > 0:
            all_in_to = player.current_bet + player.stack
            if all_in_to <= self.current_bet or (can_raise and all_in_to > self.current_bet):
                actions.append(ActionType.ALL_IN)
        return tuple(actions)

    def apply_action(
        self,
        player_id: str,
        action: ActionType | str,
        amount: int | None = None,
    ) -> GameState:
        """Apply one legal action and return the next immutable hand snapshot.

        For BET and RAISE, ``amount`` is the total current-street contribution
        the player is raising to. CALL uses the exact amount needed or a short
        all-in when the player's stack is smaller.
        """
        try:
            action = ActionType(action)
        except ValueError as exc:
            raise ValueError(f"Unknown poker action: {action!r}.") from exc
        actor = self.current_player
        if actor is None or self.hand_complete:
            raise ValueError("There is no player waiting to act.")
        if player_id != actor.id:
            raise ValueError(f"It is {actor.id}'s turn, not {player_id}'s.")
        if action not in self.legal_actions():
            raise ValueError(f"{action.value} is not legal for {actor.id} in this state.")

        old_high_bet = self.current_bet
        to_call = max(0, old_high_bet - actor.current_bet)
        committed = 0
        target_bet = actor.current_bet
        full_raise = False
        short_raise = False
        updated_actor = actor

        if action is ActionType.FOLD:
            updated_actor = actor.fold()
        elif action is ActionType.CHECK:
            if to_call:
                raise ValueError("Cannot check while facing a bet.")
        elif action is ActionType.CALL:
            if to_call == 0:
                raise ValueError("There is no bet to call; check instead.")
            committed = min(to_call, actor.stack)
            updated_actor = actor.commit(committed)
            target_bet = updated_actor.current_bet
        elif action in (ActionType.BET, ActionType.RAISE):
            if not isinstance(amount, int) or isinstance(amount, bool):
                raise ValueError("BET and RAISE require an integer total bet amount.")
            if action is ActionType.BET and old_high_bet != 0:
                raise ValueError("A bet can only be made when no one has bet this street.")
            if action is ActionType.RAISE and old_high_bet == 0:
                raise ValueError("Use BET when no one has bet this street.")
            target_bet = amount
            if target_bet <= old_high_bet:
                raise ValueError("A bet or raise must exceed the current street bet.")
            if target_bet > actor.current_bet + actor.stack:
                raise ValueError("Bet exceeds the player's remaining stack.")
            increase = target_bet - old_high_bet
            all_in = target_bet == actor.current_bet + actor.stack
            if action is ActionType.BET and target_bet < self.big_blind and not all_in:
                raise ValueError("The minimum bet is one big blind.")
            if increase < self.last_full_raise_size:
                if not all_in:
                    raise ValueError("Raise is below the minimum and is not an all-in.")
                short_raise = True
            else:
                full_raise = True
            committed = target_bet - actor.current_bet
            updated_actor = actor.commit(committed)
        elif action is ActionType.ALL_IN:
            committed = actor.stack
            target_bet = actor.current_bet + committed
            if target_bet > old_high_bet:
                if not self._has_raise_right(actor.id) or not self._has_opponent_with_chips(actor.id):
                    raise ValueError("This player's action cannot raise or reopen betting.")
                increase = target_bet - old_high_bet
                short_raise = increase < self.last_full_raise_size
                full_raise = not short_raise
            updated_actor = actor.commit(committed)

        updated_players = tuple(updated_actor if p.id == actor.id else p for p in self.players)
        record = ActionRecord(actor.id, self.street, action, committed, target_bet)
        acted = set(self.acted_since_full_raise)
        acted.add(actor.id)
        last_full_raise_size = self.last_full_raise_size
        if full_raise:
            acted = {actor.id}
            last_full_raise_size = target_bet - old_high_bet

        if full_raise or short_raise:
            pending = self._clockwise_ids(
                updated_players,
                (self._player_index(actor.id) + 1) % len(self.players),
                only_can_act=True,
            )
            pending = tuple(player_id for player_id in pending if player_id != actor.id)
        else:
            pending = tuple(pid for pid in self.pending_action_ids if pid != actor.id)

        next_state = replace(
            self,
            players=updated_players,
            current_player_id=pending[0] if pending else None,
            pending_action_ids=pending,
            last_full_raise_size=last_full_raise_size,
            acted_since_full_raise=frozenset(acted),
            action_history=self.action_history + (record,),
        )
        if sum(1 for player in next_state.players if player.is_active) == 1:
            winner = next(player.id for player in next_state.players if player.is_active)
            return next_state._finish_by_fold(winner)
        return next_state._auto_progress()

    def _player_index(self, player_id: str) -> int:
        return next(i for i, player in enumerate(self.players) if player.id == player_id)

    def _has_raise_right(self, player_id: str) -> bool:
        return player_id not in self.acted_since_full_raise

    def _has_opponent_with_chips(self, player_id: str) -> bool:
        return any(p.id != player_id and p.is_active and p.stack > 0 for p in self.players)

    def _auto_progress(self) -> GameState:
        """Run streets forward when nobody can make a meaningful decision."""
        state = self
        while not state.hand_complete:
            if sum(1 for player in state.players if player.is_active) == 1:
                winner = next(player.id for player in state.players if player.is_active)
                return state._finish_by_fold(winner)
            if state.street is Street.SHOWDOWN:
                return state
            if state.pending_action_ids:
                actor = state.current_player
                if actor is not None and state.amount_to_call == 0 and not state._has_opponent_with_chips(actor.id):
                    state = replace(state, pending_action_ids=(), current_player_id=None)
                else:
                    return state
            state = state._advance_street()
        return state

    def _advance_street(self) -> GameState:
        """Return a new street, refund unmatched chips, and deal board cards."""
        players = list(self.players)
        active_players = [player for player in players if player.is_active]
        if len(active_players) == 1:
            return self._finish_by_fold(active_players[0].id)

        # Only the unique highest total contribution can contain an uncalled
        # layer. Return that excess before constructing the next betting round.
        totals = sorted((p.total_contributed for p in players), reverse=True)
        if len(totals) > 1 and totals[0] > totals[1]:
            highest = [p for p in players if p.total_contributed == totals[0]]
            if len(highest) == 1 and highest[0].current_bet >= totals[0] - totals[1]:
                index = self._player_index(highest[0].id)
                players[index] = highest[0].refund(totals[0] - totals[1])

        if self.street is Street.RIVER:
            return replace(
                self,
                players=tuple(players),
                street=Street.SHOWDOWN,
                current_player_id=None,
                pending_action_ids=(),
            )

        next_street = {
            Street.PREFLOP: Street.FLOP,
            Street.FLOP: Street.TURN,
            Street.TURN: Street.RIVER,
        }[self.street]
        board_count = 3 if next_street is Street.FLOP else 1
        cursor = self.deck_cursor
        burned = self.burned_cards
        if cursor >= len(self.deck_order):
            raise ValueError("Deck is exhausted before the next street can be dealt.")
        burned += (self.deck_order[cursor],)
        cursor += 1
        if cursor + board_count > len(self.deck_order):
            raise ValueError("Deck is exhausted before the board can be completed.")
        board = self.community_cards + self.deck_order[cursor : cursor + board_count]
        cursor += board_count
        players = [player.reset_bet() for player in players]
        can_act = [p for p in players if p.is_active and p.stack > 0]
        if len(can_act) >= 2:
            first = (self.button_index + 1) % len(players)
            pending = self._clockwise_ids(players, first, only_can_act=True)
            return replace(
                self,
                players=tuple(players),
                street=next_street,
                community_cards=board,
                burned_cards=burned,
                deck_cursor=cursor,
                current_player_id=pending[0],
                pending_action_ids=pending,
                last_full_raise_size=self.big_blind,
                acted_since_full_raise=frozenset(),
            )
        next_state = replace(
            self,
            players=tuple(players),
            street=next_street,
            community_cards=board,
            burned_cards=burned,
            deck_cursor=cursor,
            current_player_id=None,
            pending_action_ids=(),
            last_full_raise_size=self.big_blind,
            acted_since_full_raise=frozenset(),
        )
        return next_state._auto_progress()

    def _finish_by_fold(self, winner_id: str) -> GameState:
        if self.hand_complete:
            raise ValueError("This hand has already been completed.")
        winner = self.player_by_id(winner_id)
        if winner is None or not winner.is_active:
            raise ValueError("The fold winner must be an active player.")
        total = self.pot
        players = tuple(p.receive(total) if p.id == winner_id else p for p in self.players)
        return replace(
            self,
            players=players,
            street=Street.SHOWDOWN,
            current_player_id=None,
            pending_action_ids=(),
            hand_complete=True,
            payouts=((winner_id, total),),
            winners=(winner_id,),
        )

    def resolve_showdown(self, hand_rankings: Mapping[str, object]) -> GameState:
        """Award the main and side pots using lower-is-stronger hand ranks."""
        if self.street is not Street.SHOWDOWN or self.hand_complete:
            raise ValueError("The hand must be at an unresolved showdown.")
        active = [p for p in self.players if p.is_active]
        if len(active) < 2:
            if len(active) == 1:
                return self._finish_by_fold(active[0].id)
            raise ValueError("A showdown requires at least one active player.")
        pots = PotManager.build_side_pots(self.players)
        payouts = PotManager.award(pots, hand_rankings, self.players, self.button_index)
        paid_players = tuple(p.receive(payouts[p.id]) for p in self.players)
        winners = tuple(player.id for player in self.players if payouts[player.id] > 0)
        return replace(
            self,
            players=paid_players,
            current_player_id=None,
            pending_action_ids=(),
            hand_complete=True,
            payouts=tuple((player.id, payouts[player.id]) for player in paid_players if payouts[player.id] > 0),
            winners=winners,
        )
