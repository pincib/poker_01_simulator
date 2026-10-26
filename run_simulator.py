"""Start the local poker simulator with Python's standard library."""

import argparse
import sys

from backend.server import main


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local poker training simulator.")
    parser.add_argument("--port", type=int, default=8000, help="Local HTTP port (default: 8000).")
    parser.add_argument("--no-browser", action="store_true", help="Start without opening a browser tab.")
    return parser.parse_args()


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        raise SystemExit("Poker Mastery Simulator requires Python 3.10 or newer.")
    args = _parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    main(port=args.port, open_browser=not args.no_browser)
