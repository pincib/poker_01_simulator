"""Tests for live coach metrics, bet purpose, and hand review tracking."""

import unittest
from datetime import datetime, timezone

from backend.brain.ai_agent import OpponentProfile
from backend.brain.coach import BetPurpose, CoachService, DecisionNote, SessionTracker
from backend.engine.card import Card
from backend.engine.deck import Deck
from backend.engine.game_state import ActionType, GameState
from backend.engine.player import Player


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class CoachTests(unittest.TestCase):
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
        self.assertIn("Calls below break-even equity", report.study_target)

    def test_game_state_recording_requires_completion_and_keeps_action_history(self) -> None:
        tracker = SessionTracker()
        state = GameState.new_hand((Player("hero", "Hero", 100), Player("bot", "Bot", 100)), 5, 10, deck=Deck(shuffle=False))
        with self.assertRaisesRegex(ValueError, "completed hands"):
            tracker.record_hand(state, "hero")
        finished = state.apply_action("hero", ActionType.FOLD)
        record = tracker.record_hand(finished, "hero")

        self.assertEqual(len(tracker.list_hands()), 1)
        self.assertEqual(record.actions[0]["action"], "fold")


if __name__ == "__main__":
    unittest.main()
