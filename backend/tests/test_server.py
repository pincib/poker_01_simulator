"""HTTP integration tests for coach and in-memory review endpoints."""

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.server import create_server


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
