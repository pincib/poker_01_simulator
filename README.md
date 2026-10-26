# Poker Mastery Simulator & Training Suite

A local poker training simulator for Texas Hold'em and Pot-Limit Omaha (PLO4 high), with heuristic bots, a mathematical coach, and session review. No real-money play or third-party runtime packages are used.

---

## Workspace Structure

```
poker_01-teste/
│
├── README.md                                  # Project overview and navigation map (this file)
│
├── docs/                                      # Theoretical, strategic & architectural documentation
│   ├── study_guides/                          # Original Champion Study Materials
│   │   ├── Zero to PLO50 - v7.0 (PT-BR).pdf   # Macro roadmap: Beginner to PLO50 cash stable
│   │   ├── Zero to PLO50 - v7.md              # Markdown transcription of the roadmap
│   │   ├── Zero to PLO50 - Study Companion v1.0 (EN).pdf  # 24 structured lessons & answer keys
│   │   └── Zero to PLO50 - Study Companion v1.0 (EN).md   # Markdown transcription of companion
│   │
│   ├── API.md                                    # Local HTTP route and payload reference
│   ├── USER_GUIDE.md                             # Local setup and play instructions
│   └── architecture/                             # Technical specifications and product rules
│       ├── 01_Texas_Holdem_Complete_Guide.md    # Rules, positions, and poker math
│       ├── 02_Poker_Simulator_Brain_Architecture.md # Engine, equity, and bot design
│       ├── 03_Simulator_Implementation_Roadmap.md # Original engineering roadmap
│       ├── 04_Technology_Stack_Decision.md       # Zero-install stack
│       ├── 05_Pot_Limit_Omaha_Implementation_Roadmap.md # Delivered PLO phases
│       ├── 06_PLO_MVP_Product_Rules.md           # Fixed PLO4 rules and scope
│       ├── 07_PLO_Equity_Accuracy_and_Performance.md # Accuracy and latency contract
│       ├── 11_PLO_Integrated_Verification.md     # Reproducible integrated audit
│       └── 12_PLO_MVP_Release_and_Roadmap.md     # Release scope and future work
│
├── data/                                      # Card data & asset registries
│   ├── cards_52_extracted.json                # Complete machine-readable 52-card JSON database
│   └── Standard_52_Card_Deck_Extracted.md     # Full card catalog with SVG links & nicknames
│
├── backend/                                   # Standard-library Python application
│   ├── server.py                              # Local HTTP server and JSON API boundary
│   ├── engine/
│   │   ├── card.py                            # Card value and encoding
│   │   ├── deck.py                            # Standard deck and shuffling
│   │   ├── evaluator.py                       # Hold'em and exact-two-card Omaha evaluation
│   │   ├── game_state.py                      # Immutable variant-aware betting state machine
│   │   ├── pot_limit.py                       # Pot-Limit raise sizing
│   │   ├── player.py                          # Player state and table positions
│   │   └── rules.py                           # Hold'em and PLO rulesets
│   ├── brain/
│   │   ├── equity.py                          # Equity-rollout extension point
│   │   ├── pot_odds.py                        # Pot odds, EV, and SPR
│   │   ├── ranges.py                          # Opponent-range extension point
│   │   ├── ai_agent.py                        # Bot decision extension point
│   │   ├── coach.py                           # Coaching and leak tracking
│   │   └── plo_draws.py                       # Omaha wrap outs and blocker analysis
│   ├── simulation/
│   │   └── self_play.py                       # Seeded variant-aware self-play and chip audits
│   └── tests/
│       ├── test_plo.py                         # Omaha evaluation, sizing, and wrap tests
│       ├── test_self_play.py                   # Chip conservation and rake tests
│       └── test_roadmap_benchmarks.py          # Equity accuracy and performance targets
├── frontend/                                  # Vanilla browser SPA
│   ├── index.html                             # Table and coach workspace shell
│   ├── css/
│   │   ├── table.css                           # Table and workspace styles
│   │   └── hud.css                             # Coach HUD styles
│   ├── js/app.js                               # Local API connection status
│   ├── js/components/
│   │   ├── table_view.js                       # Table rendering boundary
│   │   ├── action_bar.js                       # Legal action controls boundary
│   │   └── coach_hud.js                        # Coaching metrics boundary
│   └── assets/                                 # Card vectors and optional sounds
├── run_simulator.py                           # Single-command local launcher
└── scripts/run_phase11_verification.py       # PLO equity, showdown, and escalating self-play audit
```

## Architecture Foundation

The application is organized as a local browser client talking to a Python HTTP boundary. The engine owns poker state and variant rules; the brain layer handles hand evaluation, equity, opponent decisions, and coaching. The engine also exposes an Omaha analysis bridge for exact-two-card evaluation and Pot-Limit training math.

The repository follows the roadmap's engine, brain, test, and browser component boundaries. Both Hold'em and PLO4 have playable local hand flows. PLO uses pot-limit rules, exact-two-hole/three-board showdown evaluation, side pots, Omaha equity/draw analysis, heuristic bots, and variant-aware review. The coach and bots are training aids; their estimates and decisions are not solver/GTO strategy. The core has no required third-party packages.

### Run the local server

Requires Python 3.10 or newer. No third-party installation is needed.

```powershell
python run_simulator.py
```

The server binds to `127.0.0.1` and serves the browser client from `frontend/`. `--no-browser` starts it without opening a tab; `--port 8001` selects a different local port. The SPA reads `/api/health` and `/api/config` from the same origin and reports whether the local server is ready.

See the [user guide](docs/USER_GUIDE.md) for selecting PLO, playing a hand, and opening the review. The PLO practice table is fixed at six seats, $1/$2 blinds and $200 stacks, without rake. Hand history and review remain in process memory and are cleared when the local server stops.

### Verification

Run the test suite and the phase 11 equity, showdown, and escalating PLO self-play audit:

```powershell
python -B -m pytest -p no:cacheprovider backend/tests -q
python -B scripts/run_phase11_verification.py
```

The PLO audit runs 100, 500, and 2,000 seeded self-play hands by default. See [integrated verification](docs/architecture/11_PLO_Integrated_Verification.md) for tolerances and benchmark results.

### API overview

- `GET /api/health` returns local server status.
- `GET /api/config` returns API version `1`, the default game variant, and variant metadata (hole-card counts, betting structures, and seat limits).
- `POST /api/game/start` accepts `{}` or `{"variant":"texas_holdem"}` / `{"variant":"pot_limit_omaha"}`. The chosen variant is held by the server for later hands; omitting it retains the server-side selection.
- `GET /api/game/state` returns the current hand, including `variant_id` (stable enum), hole-card count, legal actions, betting limits, and showdown/pot-award data. The legacy display field `variant` remains unchanged.
- `POST /api/game/action` accepts `{ "action": "call" }` or `{ "action": "raise", "amount": 24 }`. An optional `variant` must match the active hand; bet/raise amounts are integer street totals and are checked by the backend rules.
- `POST /api/coach/analyze` accepts two-card Hold’em or four-card Omaha hands and ranges; Omaha opponent range entries each contain four card codes.
- Invalid variants, actions, amounts, and actions outside the active hand's legal rules return HTTP `400` with an `error` message. Existing response fields remain available; stable variant and betting metadata are additive.
- Static files are served from the `frontend/` directory.

Full routes, payloads, response fields, errors, and session-memory behavior are documented in the [API reference](docs/API.md).

---

## Quick Navigation

### 1. Champion Study Materials (`docs/study_guides/`)
* **[Zero to PLO50 - v7.md](docs/study_guides/Zero%20to%20PLO50%20-%20v7.md)**: The 7-stage macro path from play money to PLO50 breakeven/winning, detailing hours, bankroll rules, and stable evaluation criteria.
* **[Zero to PLO50 - Study Companion v1.0 (EN).md](docs/study_guides/Zero%20to%20PLO50%20-%20Study%20Companion%20v1.0%20(EN).md)**: 24 actionable micro-lessons covering rules, pot odds, EV, tilt management, hand review routines, and PLO mechanics.

### 2. Simulator Specifications (`docs/architecture/`)
* **[01_Texas_Holdem_Complete_Guide.md](docs/architecture/01_Texas_Holdem_Complete_Guide.md)**: Complete game mechanics, 6-max positions, 10 hand ranks, pot odds calculations, and betting dynamics.
* **[02_Poker_Simulator_Brain_Architecture.md](docs/architecture/02_Poker_Simulator_Brain_Architecture.md)**: Deep technical architecture of the simulation engine, Cactus Kev bitwise evaluation, Monte Carlo simulation, 13x13 range matrices, and AI decision logic.
* **[03_Simulator_Implementation_Roadmap.md](docs/architecture/03_Simulator_Implementation_Roadmap.md)**: 7-phase step-by-step development roadmap from domain models to the live coaching UI and PLO bridge.
* **[04_Technology_Stack_Decision.md](docs/architecture/04_Technology_Stack_Decision.md)**: Selected Python standard-library server and vanilla browser client, with optional evaluator acceleration deferred.
* **[05_Pot_Limit_Omaha_Implementation_Roadmap.md](docs/architecture/05_Pot_Limit_Omaha_Implementation_Roadmap.md)**: PLO delivery phases and acceptance criteria.
* **[06_PLO_MVP_Product_Rules.md](docs/architecture/06_PLO_MVP_Product_Rules.md)**: Fixed table, betting, all-in, payout, and coach scope.
* **[12_PLO_MVP_Release_and_Roadmap.md](docs/architecture/12_PLO_MVP_Release_and_Roadmap.md)**: MVP activation, known limits, and separately validated future formats.

### 3. Product guides
* **[User guide](docs/USER_GUIDE.md)**: Local setup, PLO play, coaching, and hand review.
* **[API reference](docs/API.md)**: HTTP routes and PLO request/response contracts.

### 4. Deck Assets (`data/`)
* **[Standard_52_Card_Deck_Extracted.md](data/Standard_52_Card_Deck_Extracted.md)**: Human-readable markdown reference with Unicode symbols and vector SVG URLs from Wikipedia.
* **[cards_52_extracted.json](data/cards_52_extracted.json)**: Normalized JSON database with codes (`Ac`, `Kh`), suits, ranks, Unicode codepoints, and colors for traditional and 4-colour decks.
