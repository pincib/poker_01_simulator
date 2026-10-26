# Technology Stack Decision

This decision implements section 2 of `03_Simulator_Implementation_Roadmap.md` while preserving its zero-install local workflow.

## Selected stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Runtime | Python 3.10 or newer | Matches the roadmap baseline and supports modern typing and dataclasses. |
| Core engine | Python standard library | Keeps the game usable without installing packages. |
| Local HTTP boundary | `http.server` with `ThreadingHTTPServer` | Serves the browser client and same-origin JSON endpoints without a framework dependency. |
| Browser client | HTML, CSS, and vanilla JavaScript modules | Runs directly in a modern browser without a bundler, package manager, or build step. |
| Hand evaluation | Pure Python as the required fallback | Keeps the evaluator available in a standard Python installation. |
| Optional evaluator acceleration | `eval7` or `treys`, behind an adapter | Can be considered after the pure-Python evaluator exists and has a parity check. Neither is required or wired into the current build. |

## Runtime contract

Start the application from the project root with:

```powershell
python run_simulator.py
```

The server binds to `127.0.0.1`, serves files from `frontend/`, and exposes JSON through the same origin. The current endpoints are `GET /api/health` and `GET /api/config`. No CORS configuration, frontend build, or package installation is needed for the current scaffold.

## Dependency policy

- Required third-party Python dependencies: none.
- Required JavaScript packages: none.
- Optional evaluator packages must never replace the pure-Python path or block startup.
- Do not add a server framework unless a concrete requirement such as persistent sessions or WebSocket gameplay justifies the added install step.

## Current limits

The selected stack is in place, and the static browser client confirms same-origin communication with the local server. The hand state machine, evaluator, equity calculations, bots, coaching logic, and playable frontend controls are still later implementation work. The optional evaluator adapter should be evaluated with correctness parity before it is enabled.
