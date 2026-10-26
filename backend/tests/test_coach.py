"""Tests for live coach metrics, bet purpose, and hand review tracking."""

import unittest
from datetime import datetime, timezone

from backend.brain.ai_agent import OpponentProfile
from backend.brain.coach import BetPurpose, CoachService, DecisionNote, SessionTracker
from backend.engine.card import Card
from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState
from backend.engine.player import Player
from backend.engine.rules import GameRules


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class CoachTests(unittest.TestCase):
    def test_plo_multiway_coach_uses_four_card_ranges(self) -> None:
        state = GameState.new_hand(
            (Player("hero", "Hero", 100), Player("v1", "Villain 1", 100), Player("v2", "Villain 2", 100)),
            1, 2, deck=Deck(seed=404), rules=GameRules.pot_limit_omaha(),
        )
        state = state.apply_action("hero", ActionType.CALL)
        state = state.apply_action("v1", ActionType.CALL)
        state = state.apply_action("v2", ActionType.CHECK)
        snapshot = CoachService.analyze_state(state, "hero", iterations=40, seed=92)

        self.assertEqual(snapshot.equity_source, "action-filtered multiway ranges")
        self.assertGreater(snapshot.opponent_range_size, 0)
        self.assertEqual(snapshot.variant, "pot_limit_omaha")
        self.assertTrue(any("Monte Carlo" in note for note in snapshot.limitations))
        self.assertIsNotNone(snapshot.draw_analysis)
        selected = CoachService.analyze_state(state, "hero", "v1", iterations=8, seed=92)
        self.assertTrue(any("only the selected opponent" in note for note in selected.limitations))

    def test_plo_decision_uses_four_card_equity_and_legal_hand_description(self) -> None:
        snapshot = CoachService.analyze_decision(
            hero_hole=cards("As", "Ah", "Kd", "Qc"),
            board=cards("2c", "3d", "4h"),
            pot=20,
            call_amount=5,
            hero_stack=100,
            opponent_stack=100,
            iterations=100,
            seed=404,
        )

        self.assertEqual(snapshot.iterations, 100)
        self.assertEqual(snapshot.equity_source, "uniform four-card combinations")
        self.assertIsNotNone(snapshot.hand_description)
        self.assertIsNotNone(snapshot.draw_analysis)
        self.assertTrue(snapshot.to_dict()["draw_analysis"]["evidence"])
        self.assertEqual(snapshot.variant, "pot_limit_omaha")
        self.assertEqual(snapshot.seed, 404)
        self.assertTrue(snapshot.limitations)

    def test_plo_preflop_bet_purpose_is_marked_unmodeled(self) -> None:
        result = CoachService.classify_bet(
            hero_hole=cards("As", "Ah", "Ks", "Qh"),
            board=(), pot=3, bet_amount=6,
        )
        self.assertEqual(result.purpose, BetPurpose.UNMODELED)
        self.assertEqual(result.variant, "pot_limit_omaha")
        self.assertIn("not equity", result.evidence)

    def test_plo_postflop_bet_purpose_compares_four_card_omaha_ranges(self) -> None:
        result = CoachService.classify_bet(
            hero_hole=cards("As", "Ah", "Kd", "Qc"),
            board=cards("2c", "3d", "4h"),
            pot=20,
            bet_amount=10,
            opponent_range=(cards("Ks", "Kh", "Jd", "Tc"), cards("8s", "9s", "Ts", "Js")),
        )
        self.assertEqual(result.variant, "pot_limit_omaha")
        self.assertEqual(result.range_size, 2)

    def test_live_feedback_calculates_price_equity_ev_spr_and_warning(self) -> None:
        snapshot = CoachService.analyze_decision(
            hero_hole=cards("As", "Kd"),
            board=cards("Ah", "7c", "2d"),
            pot=12,
            call_amount=6,
            hero_stack=72,
            opponent_stack=48,
            opponent_range=(cards("Kc", "Qd"), cards("Jc", "Td"), cards("9c", "8d")),
            iterations=50,
            seed=3,
        )

        self.assertEqual(snapshot.pot_odds_percentage, 33.33333333333333)
        self.assertEqual(snapshot.spr_value, 4.0)
        self.assertIsNotNone(snapshot.hand_description)
        self.assertIsNotNone(snapshot.ev_call)
        self.assertIn("future-street", snapshot.advice)

    def test_spr_warning_uses_top_pair_without_declaring_auto_commitment(self) -> None:
        snapshot = CoachService.analyze_decision(
            hero_hole=cards("As", "Kd"),
            board=cards("Ah", "7c", "2d"),
            pot=40,
            call_amount=0,
            hero_stack=60,
            opponent_stack=72,
            opponent_range=(cards("Kc", "Qd"), cards("Jc", "Td")),
            iterations=30,
            seed=4,
        )

        self.assertEqual(snapshot.spr_value, 1.5)
        self.assertIn("top pair", snapshot.spr_warning)
        self.assertIn("before committing", snapshot.spr_warning)

    def test_bet_purpose_distinguishes_value_bluff_and_pointless(self) -> None:
        value = CoachService.classify_bet(
            hero_hole=cards("Ac", "Ad"),
            board=cards("As", "7c", "2h"),
            pot=20,
            bet_amount=10,
            opponent_range=(cards("Kc", "Qd"), cards("Jc", "Td")),
            opponent_profile=OpponentProfile.TAG,
        )
        better_range = (cards("Ad", "Kh"), cards("Ah", "Ks"))
        bluff = CoachService.classify_bet(
            hero_hole=cards("2c", "3c"),
            board=cards("As", "Kd", "Qh"),
            pot=10,
            bet_amount=10,
            opponent_range=better_range,
            opponent_profile=OpponentProfile.TAG,
        )
        pointless = CoachService.classify_bet(
            hero_hole=cards("2c", "3c"),
            board=cards("As", "Kd", "Qh"),
            pot=10,
            bet_amount=10,
            opponent_range=better_range,
            opponent_profile=OpponentProfile.STATION,
        )

        self.assertEqual(value.purpose, BetPurpose.VALUE)
        self.assertEqual(bluff.purpose, BetPurpose.BLUFF)
        self.assertEqual(pointless.purpose, BetPurpose.POINTLESS)

    def test_session_tracker_reconstructs_hands_and_flags_repeated_decisions(self) -> None:
        tracker = SessionTracker()
        now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
        for _ in range(3):
            record = tracker.record_payload({
                "hero_id": "hero",
                "recorded_at": now.isoformat(),
                "players": [
                    {"id": "hero", "name": "Hero", "position": "BTN", "starting_stack": 100, "hole_cards": ["As", "Kd"]},
                    {"id": "bot", "name": "Bot", "position": "BB", "starting_stack": 100, "hole_cards": ["Qc", "Qd"]},
                ],
                "board": ["2c", "3d", "4h"],
                "final_pot": 40,
                "actions": [{"player_id": "hero", "street": "flop", "action": "call", "chips": 10, "bet_to": 10}],
                "payouts": {"bot": 40},
                "decisions": [
                    {
                        "street": "flop", "action": "call", "chips": 10, "pot_before": 20,
                        "equity_percentage": 25, "pot_odds_percentage": 33, "ev_call": -5,
                        "facing_cbet": False, "out_of_position": True,
                        "rationale": "I thought the draw was enough.", "review_question": "Was the call price right?",
                    },
                    {
                        "street": "flop", "action": "fold", "chips": 0, "pot_before": 20,
                        "equity_percentage": 25, "pot_odds_percentage": 33, "ev_call": None,
                        "facing_cbet": True, "out_of_position": True,
                        "rationale": "I folded to the c-bet.", "review_question": "Could I continue here?",
                    },
                ],
            })

        self.assertTrue(record.tricky)
        self.assertEqual(record.hole_cards, ("As", "Kd"))
        self.assertEqual(record.board, ("2c", "3d", "4h"))
        self.assertEqual(len(record.actions), 1)
        report = tracker.weekly_leak_report(now=now)
        self.assertEqual(report.hands_reviewed, 3)
        self.assertEqual({flag.key for flag in report.flags}, {"negative_ev_calls", "overfold_cbet", "out_of_position"})
        self.assertIn("calls below break-even equity", report.study_target.lower())
        self.assertEqual(report.by_variant["texas_holdem"]["hands_reviewed"], 3)
        self.assertEqual(report.by_variant["pot_limit_omaha"]["hands_reviewed"], 0)

    def test_game_state_recording_requires_completion_and_keeps_action_history(self) -> None:
        tracker = SessionTracker()
        state = GameState.new_hand((Player("hero", "Hero", 100), Player("bot", "Bot", 100)), 5, 10, deck=Deck(shuffle=False))
        with self.assertRaisesRegex(ValueError, "completed hands"):
            tracker.record_hand(state, "hero")
        finished = state.apply_action("hero", ActionType.FOLD)
        record = tracker.record_hand(finished, "hero")

        self.assertEqual(len(tracker.list_hands()), 1)
        self.assertEqual(record.actions[0]["action"], "fold")

    def test_plo_hand_review_persists_variant_cards_contributions_and_showdown(self) -> None:
        tracker = SessionTracker()
        payload = {
            "hero_id": "hero",
            "variant": "pot_limit_omaha",
            "players": [
                {"id": "hero", "name": "Hero", "position": "BTN", "starting_stack": 100,
                 "final_stack": 70, "total_contributed": 30, "hole_cards": ["As", "Ah", "Kd", "Qc"]},
                {"id": "villain", "name": "Villain", "position": "BB", "starting_stack": 100,
                 "final_stack": 130, "total_contributed": 30, "hole_cards": ["Ks", "Kh", "Jd", "Tc"]},
            ],
            "board": ["2c", "3d", "4h", "5s", "6c"],
            "final_pot": 60,
            "actions": [{"player_id": "hero", "street": "river", "action": "call", "chips": 20, "bet_to": 30}],
            "contributions": {"hero": 30, "villain": 30},
            "payouts": {"villain": 60},
            "winners": ["villain"],
            "showdown_ranks": {"hero": 1000, "villain": 900},
            "winning_hands": {"villain": ["Ks", "Kh", "3d", "4h", "5s"]},
            "pot_awards": [{"label": "main", "amount": 60, "winner_ids": ["villain"]}],
            "decisions": [{
                "street": "river", "action": "call", "chips": 20, "pot_before": 40,
                "equity_percentage": 31.5, "pot_odds_percentage": 33.3, "ev_call": -1,
                "equity_source": "uniform four-card combinations", "equity_iterations": 500,
                "opponent_range_size": 91390, "estimation_seed": 45,
                "limitations": ["Monte Carlo estimate"],
                "draw_analysis": {"nut_outs": [], "non_nut_outs": []},
            }],
        }
        record = tracker.record_payload(payload)
        serialized = record.to_dict()
        self.assertEqual(record.variant, "pot_limit_omaha")
        self.assertEqual(len(record.hole_cards), 4)
        self.assertEqual(record.contributions, {"hero": 30, "villain": 30})
        self.assertEqual(record.winning_hands["villain"], ("Ks", "Kh", "3d", "4h", "5s"))
        self.assertEqual(record.decisions[0].equity_iterations, 500)
        self.assertEqual(record.decisions[0].variant, "pot_limit_omaha")
        self.assertEqual(serialized["actions"][0]["variant"], "pot_limit_omaha")
        board_only = dict(payload)
        board_only["winning_hands"] = {"villain": ["2c", "3d", "4h", "5s", "6c"]}
        with self.assertRaisesRegex(ValueError, "exactly two hole cards"):
            tracker.record_payload(board_only)

    def test_completed_plo_game_state_records_replay_inputs_and_result(self) -> None:
        tracker = SessionTracker()
        state = GameState.new_hand(
            (Player("hero", "Hero", 80), Player("villain", "Villain", 80)),
            1, 2, deck=Deck(seed=774), rules=GameRules.pot_limit_omaha(),
        )
        while not state.hand_complete and state.street.value != "showdown":
            actor = state.current_player
            action = ActionType.CHECK if ActionType.CHECK in state.legal_actions() else ActionType.CALL
            state = state.apply_action(actor.id, action)
        if not state.hand_complete:
            state = state.resolve_showdown()
        record = tracker.record_hand(state, "hero")
        payload = record.to_dict()

        self.assertEqual(record.variant, "pot_limit_omaha")
        self.assertEqual(len(record.hole_cards), 4)
        self.assertEqual(set(record.contributions), {"hero", "villain"})
        self.assertTrue(record.actions)
        self.assertEqual({action["variant"] for action in record.actions}, {"pot_limit_omaha"})
        self.assertEqual(sum(record.payouts.values()), sum(record.contributions.values()))
        self.assertTrue(payload["winners"])
        self.assertTrue(payload["winning_hands"])

    def test_leak_indicators_are_grouped_by_variant(self) -> None:
        tracker = SessionTracker()
        now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
        for variant in ("texas_holdem", "pot_limit_omaha"):
            hole = ["As", "Kd"] if variant == "texas_holdem" else ["As", "Ah", "Kd", "Qc"]
            for _ in range(3):
                tracker.record_payload({
                    "hero_id": "hero", "variant": variant, "recorded_at": now.isoformat(),
                    "players": [{"id": "hero", "hole_cards": hole}], "board": [],
                    "decisions": [{"street": "flop", "action": "call", "ev_call": -3}],
                })
        grouped = tracker.weekly_leak_report(now=now).to_dict()["by_variant"]
        self.assertEqual(grouped["texas_holdem"]["flags"][0]["key"], "negative_ev_calls")
        self.assertEqual(grouped["pot_limit_omaha"]["flags"][0]["key"], "plo_negative_ev_calls")


if __name__ == "__main__":
    unittest.main()
