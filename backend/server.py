"""Dependency-free local HTTP server for the browser client."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from backend.brain.coach import CoachService, SessionTracker
from backend.engine.card import Card
from backend.engine.training_table import TrainingTable

FRONTEND_ROOT = Path(__file__).resolve().parent.parent / "frontend"
SESSION_TRACKER = SessionTracker()
TRAINING_TABLE = TrainingTable(SESSION_TRACKER)


class SimulatorRequestHandler(SimpleHTTPRequestHandler):
    """Serve the SPA and a small JSON API from one local origin."""

    server_version = "PokerSimulator/0.1"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FRONTEND_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "ok", "service": "poker-simulator"})
            return
        if parsed.path == "/api/config":
            self._send_json({
                "name": "Poker Mastery Simulator",
                "api_version": 1,
                "default_variant": "texas_holdem",
                "rule_variants": ["texas_holdem", "pot_limit_omaha"],
                "variants": {
                    "texas_holdem": {
                        "label": "Texas Hold’em",
                        "hole_card_count": 2,
                        "betting_structure": "no_limit",
                        "min_players": 2,
                        "max_players": 6,
                    },
                    "pot_limit_omaha": {
                        "label": "Omaha Pot-Limit",
                        "hole_card_count": 4,
                        "betting_structure": "pot_limit",
                        "min_players": 2,
                        "max_players": 6,
                    },
                },
                "features": {"training_coach": "available", "session_review": "available"},
            })
            return
        if parsed.path == "/api/game/state":
            self._send_json(TRAINING_TABLE.snapshot())
            return
        if parsed.path == "/api/session/hands":
            self._send_json({"hands": [hand.to_dict() for hand in SESSION_TRACKER.list_hands()]})
            return
        if parsed.path == "/api/session/leaks":
            self._send_json(SESSION_TRACKER.weekly_leak_report().to_dict())
            return
        if parsed.path.startswith("/api/session/hands/"):
            hand_id = unquote(parsed.path.rsplit("/", 1)[-1])
            hand = SESSION_TRACKER.get_hand(hand_id)
            if hand is None:
                self._send_json({"error": "Revisão da mão não encontrada."}, 404)
            else:
                self._send_json(hand.to_dict())
            return
        if parsed.path.startswith("/api/"):
            self._send_json({"error": "Rota da API não encontrada."}, 404)
            return
        if parsed.path in ("/", "/index.html") and not (FRONTEND_ROOT / "index.html").is_file():
            self._send_error_json(503, "A interface do navegador ainda não foi criada.")
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        try:
            payload = self._read_json_payload()
            if parsed.path == "/api/coach/analyze":
                result = CoachService.analyze_decision(
                    hero_hole=_cards(payload.get("hero_hole"), "hero_hole"),
                    board=_cards(payload.get("board", []), "board"),
                    pot=payload.get("pot", 0),
                    call_amount=payload.get("call_amount", 0),
                    hero_stack=payload.get("hero_stack", 0),
                    opponent_stack=payload.get("opponent_stack", 0),
                    opponent_position=payload.get("opponent_position", "BTN"),
                    opponent_last_action=payload.get("opponent_last_action"),
                    opponent_hole=_optional_cards(payload.get("opponent_hole"), "opponent_hole"),
                    opponent_range=_optional_range(payload.get("opponent_range")),
                    opponent_ranges=_optional_ranges(payload.get("opponent_ranges")),
                    opponent_ranges_action_filtered=payload.get("opponent_ranges_action_filtered") is True,
                    big_blind=payload.get("big_blind", 1),
                    iterations=payload.get("iterations", 1_000),
                    seed=payload.get("seed"),
                    variant=payload.get("variant"),
                )
                self._send_json(result.to_dict())
                return
            if parsed.path == "/api/coach/action-purpose":
                result = CoachService.classify_bet(
                    hero_hole=_cards(payload.get("hero_hole"), "hero_hole"),
                    board=_cards(payload.get("board", []), "board"),
                    pot=payload.get("pot", 0),
                    bet_amount=payload.get("bet_amount", 0),
                    opponent_position=payload.get("opponent_position", "BTN"),
                    opponent_last_action=payload.get("opponent_last_action"),
                    opponent_range=_optional_range(payload.get("opponent_range")),
                    opponent_profile=payload.get("opponent_profile", "tag"),
                    hero_position=payload.get("hero_position", "BTN"),
                )
                self._send_json(result.to_dict())
                return
            if parsed.path == "/api/session/hands":
                record = SESSION_TRACKER.record_payload(payload)
                self._send_json(record.to_dict(), 201)
                return
            if parsed.path == "/api/game/start":
                variant = payload.get("variant")
                self._send_json(TRAINING_TABLE.start_hand(variant))
                return
            if parsed.path == "/api/game/action":
                self._send_json(TRAINING_TABLE.act(
                    payload.get("action"), payload.get("amount"), variant=payload.get("variant")
                ))
                return
            self._send_json({"error": "Rota da API não encontrada."}, 404)
        except (KeyError, TypeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def _read_json_payload(self) -> dict[str, object]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("O tamanho do conteúdo deve ser um número inteiro.") from exc
        if content_length <= 0 or content_length > 1_000_000:
            raise ValueError("O corpo da solicitação deve ter entre 1 byte e 1 MB.")
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("O corpo da solicitação deve conter JSON válido.") from exc
        if not isinstance(payload, dict):
            raise ValueError("O JSON da solicitação deve ser um objeto.")
        return payload

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)


def create_server(port: int = 8000) -> ThreadingHTTPServer:
    """Create a server bound to localhost so it stays on the user's machine."""
    return ThreadingHTTPServer(("127.0.0.1", port), SimulatorRequestHandler)


def main(port: int = 8000, *, open_browser: bool = True) -> None:
    import webbrowser

    server = create_server(port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Simulador de poker em execução em {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping poker simulator.")
    finally:
        server.server_close()


def _cards(value: object, label: str) -> tuple[Card, ...]:
    if not isinstance(value, list) or any(not isinstance(code, str) for code in value):
        raise ValueError(f"{label} must be a list of card codes.")
    return tuple(Card.from_code(code) for code in value)


def _optional_cards(value: object, label: str) -> tuple[Card, ...] | None:
    return None if value is None else _cards(value, label)


def _optional_range(value: object) -> tuple[tuple[Card, ...], ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("opponent_range must be a list of hands matching hero_hole's card count.")
    return tuple(_cards(combo, "opponent_range hand") for combo in value)


def _optional_ranges(value: object) -> tuple[tuple[tuple[Card, ...], ...], ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("opponent_ranges must be a list of opponent ranges.")
    return tuple(_optional_range(range_value) or () for range_value in value)


if __name__ == "__main__":
    main()
