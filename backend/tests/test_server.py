"""HTTP integration tests for coach and in-memory review endpoints."""

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import backend.server as server_module
from backend.brain.coach import SessionTracker
from backend.server import create_server
from backend.engine.training_table import TrainingTable


class CoachAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request_json(self, path: str, payload: dict | None = None) -> tuple[int, dict]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        return response.status, json.loads(response.read())

    def test_config_advertises_coach_and_session_review(self) -> None:
        status, body = self.request_json("/api/config")

        self.assertEqual(status, 200)
        self.assertEqual(body["features"]["training_coach"], "available")
        self.assertEqual(body["features"]["session_review"], "available")
        self.assertEqual(body["api_version"], 1)
        self.assertEqual(body["variants"]["pot_limit_omaha"]["hole_card_count"], 4)

    def test_game_api_starts_and_advances_plo_with_server_side_variant(self) -> None:
        server_module.TRAINING_TABLE = TrainingTable(SessionTracker())
        status, started = self.request_json("/api/game/start", {"variant": "pot_limit_omaha"})

        self.assertEqual(status, 200)
        self.assertEqual(started["variant_id"], "pot_limit_omaha")
        self.assertEqual(started["betting_structure"], "pot_limit")
        self.assertEqual(started["hole_card_count"], 4)
        self.assertEqual(len(started["hero_hole"]), 4)
        self.assertEqual(len(started["seats"][0]["hole_cards"]), 4)
        self.assertIn("betting_limits", started)
        self.assertTrue(started["legal_actions"])
        self.assertIn(started["legal_actions"][0], {"fold", "check", "call", "bet", "raise", "all_in"})

        chosen = "check" if "check" in started["legal_actions"] else "call"
        action_status, advanced = self.request_json("/api/game/action", {"action": chosen})

        self.assertEqual(action_status, 200)
        self.assertEqual(advanced["variant_id"], "pot_limit_omaha")
        self.assertEqual(advanced["hole_card_count"], 4)
        self.assertEqual(advanced["rules"]["variant"], "pot_limit_omaha")

    def test_plo_session_completes_through_api_and_is_reconstructable_in_review(self) -> None:
        tracker = SessionTracker()
        server_module.SESSION_TRACKER = tracker
        server_module.TRAINING_TABLE = TrainingTable(tracker)

        start_status, started = self.request_json(
            "/api/game/start", {"variant": "pot_limit_omaha"}
        )
        self.assertEqual(start_status, 200)
        self.assertIn("fold", started["legal_actions"])
        action_status, completed = self.request_json(
            "/api/game/action", {"action": "fold", "variant": "pot_limit_omaha"}
        )
        self.assertEqual(action_status, 200)
        self.assertTrue(completed["hand_complete"])

        list_status, listing = self.request_json("/api/session/hands")
        self.assertEqual(list_status, 200)
        hand_id = listing["hands"][-1]["hand_id"]
        detail_status, review = self.request_json(f"/api/session/hands/{hand_id}")
        self.assertEqual(detail_status, 200)
        self.assertEqual(review["variant"], "pot_limit_omaha")
        self.assertEqual(len(review["hole_cards"]), 4)
        self.assertEqual(review["board"], [])
        self.assertTrue(review["actions"])
        self.assertEqual(review["actions"][-1]["action"], "fold")
        self.assertEqual(sum(review["contributions"].values()), review["final_pot"])

    def test_game_api_rejects_unknown_and_mid_hand_variant_changes(self) -> None:
        server_module.TRAINING_TABLE = TrainingTable(SessionTracker())
        invalid_status, invalid = self.request_json("/api/game/start", {"variant": "short_deck"})
        start_status, started = self.request_json("/api/game/start", {"variant": "texas_holdem"})
        mismatch_status, mismatch = self.request_json("/api/game/action", {
            "action": "fold",
            "variant": "pot_limit_omaha",
        })

        self.assertEqual(invalid_status, 400)
        self.assertIn("Supported variants", invalid["error"])
        self.assertEqual(start_status, 200)
        self.assertEqual(started["variant_id"], "texas_holdem")
        self.assertEqual(mismatch_status, 400)
        self.assertIn("cannot change mid-hand", mismatch["error"])

    def test_game_api_advances_holdem_and_rejects_unknown_actions(self) -> None:
        server_module.TRAINING_TABLE = TrainingTable(SessionTracker())
        start_status, started = self.request_json("/api/game/start", {"variant": "texas_holdem"})

        self.assertEqual(start_status, 200)
        self.assertEqual(started["variant_id"], "texas_holdem")
        self.assertEqual(started["betting_structure"], "no_limit")
        self.assertEqual(started["hole_card_count"], 2)
        self.assertEqual(len(started["hero_hole"]), 2)
        self.assertTrue(started["legal_actions"])

        bad_status, bad_action = self.request_json("/api/game/action", {"action": "straddle"})
        chosen = "check" if "check" in started["legal_actions"] else "call"
        advance_status, advanced = self.request_json("/api/game/action", {"action": chosen})

        self.assertEqual(bad_status, 400)
        self.assertIn("Unknown action", bad_action["error"])
        self.assertEqual(advance_status, 200)
        self.assertEqual(advanced["variant_id"], "texas_holdem")

    def test_live_analysis_and_bet_purpose_endpoints(self) -> None:
        status, analysis = self.request_json("/api/coach/analyze", {
            "hero_hole": ["As", "Kd"],
            "board": ["Ah", "7c", "2d"],
            "pot": 12,
            "call_amount": 6,
            "hero_stack": 72,
            "opponent_stack": 48,
            "opponent_range": [["Kc", "Qd"], ["Jc", "Td"]],
            "iterations": 24,
            "seed": 9,
        })
        purpose_status, purpose = self.request_json("/api/coach/action-purpose", {
            "hero_hole": ["Ac", "Ad"],
            "board": ["As", "7c", "2h"],
            "pot": 20,
            "bet_amount": 10,
            "opponent_range": [["Kc", "Qd"], ["Jc", "Td"]],
        })

        self.assertEqual(status, 200)
        self.assertIn("equity_percentage", analysis)
        self.assertIn("pot_odds_percentage", analysis)
        self.assertEqual(purpose_status, 200)
        self.assertEqual(purpose["purpose"], "value")

    def test_plo_coach_api_returns_variant_ranges_and_draw_evidence(self) -> None:
        status, analysis = self.request_json("/api/coach/analyze", {
            "variant": "pot_limit_omaha",
            "hero_hole": ["As", "Ah", "Kd", "Qc"],
            "board": ["2c", "3d", "4h"],
            "pot": 20,
            "call_amount": 5,
            "hero_stack": 100,
            "opponent_stack": 100,
            "opponent_range": [["Ks", "Kh", "Jd", "Tc"], ["8s", "9s", "Ts", "Js"]],
            "iterations": 8,
            "seed": 92,
        })
        purpose_status, purpose = self.request_json("/api/coach/action-purpose", {
            "hero_hole": ["As", "Ah", "Ks", "Qh"],
            "board": [],
            "pot": 3,
            "bet_amount": 6,
        })

        self.assertEqual(status, 200)
        self.assertEqual(analysis["variant"], "pot_limit_omaha")
        self.assertEqual(analysis["equity_source"], "provided opponent range")
        self.assertEqual(analysis["opponent_range_size"], 2)
        self.assertIn("nut_outs", analysis["draw_analysis"])
        self.assertEqual(purpose_status, 200)
        self.assertEqual(purpose["variant"], "pot_limit_omaha")
        self.assertEqual(purpose["purpose"], "unmodeled")

    def test_hand_submission_is_available_to_session_review(self) -> None:
        status, hand = self.request_json("/api/session/hands", {
            "hero_id": "hero",
            "players": [
                {"id": "hero", "name": "Hero", "position": "BTN", "starting_stack": 100, "hole_cards": ["As", "Kd"]},
                {"id": "bot", "name": "Bot", "position": "BB", "starting_stack": 100},
            ],
            "board": ["2c", "3d", "4h"],
            "final_pot": 20,
            "actions": [{"player_id": "hero", "street": "flop", "action": "check", "chips": 0, "bet_to": 0}],
            "payouts": {"hero": 20},
            "decisions": [],
        })
        list_status, hand_list = self.request_json("/api/session/hands")
        report_status, report = self.request_json("/api/session/leaks")

        self.assertEqual(status, 201)
        self.assertEqual(list_status, 200)
        self.assertIn(hand["hand_id"], {item["hand_id"] for item in hand_list["hands"]})
        self.assertEqual(report_status, 200)
        self.assertGreaterEqual(report["hands_reviewed"], 1)

    def test_malformed_coach_payload_returns_a_client_error(self) -> None:
        status, body = self.request_json("/api/coach/analyze", {"hero_hole": ["As"]})

        self.assertEqual(status, 400)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
