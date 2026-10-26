# Poker Mastery Simulator & Training Suite

A professional poker training environment designed to help players progress from foundational Texas Hold'em to advanced Pot-Limit Omaha (PLO), guided by the World Champion's structured curriculum.

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
│   └── architecture/                          # Technical Specifications & Game Theory
│       ├── 01_Texas_Holdem_Complete_Guide.md  # Comprehensive guide to rules, positions & math
│       ├── 02_Poker_Simulator_Brain_Architecture.md  # Engine design, Monte Carlo & AI logic
│       ├── 03_Simulator_Implementation_Roadmap.md    # Phased software engineering roadmap
│       └── 04_Technology_Stack_Decision.md           # Selected zero-install stack
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
│   │   ├── game_state.py                      # Immutable Hold'em betting state machine
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
│   │   └── self_play.py                       # Seeded bot self-play and rake accounting
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
└── scripts/run_phase7_verification.py         # 10k equity benchmarks and 50k-hand self-play
```

## Architecture Foundation

The application is organized as a local browser client talking to a Python HTTP boundary. The engine owns poker state and variant rules; the brain layer handles hand evaluation, equity, opponent decisions, and coaching. The engine also exposes an Omaha analysis bridge for exact-two-card evaluation and Pot-Limit training math.

The repository follows the roadmap's engine, brain, test, and browser component boundaries. Implemented modules include the standard-library server, immutable Hold'em game state machine, fast seven-card evaluator, Monte Carlo equity, coaching and opponent analysis, rake-aware self-play, and an Omaha bridge for exact-two-card evaluation, pot-limit raise sizing, and wrap outs. The PLO bridge supports evaluation and training math; full playable PLO hand flow remains a separate extension. The core has no required third-party packages.

### Run the local server

Requires Python 3.10 or newer. No third-party installation is needed.

```powershell
python run_simulator.py
```

The server binds to `127.0.0.1` and serves the browser client from `frontend/`. `--no-browser` starts it without opening a tab; `--port 8001` selects a different local port. The SPA reads `/api/health` and `/api/config` from the same origin and reports whether the local server is ready.

### Phase 7 verification

Run the automated suite and the roadmap's equity and 50,000-hand self-play checks:

```powershell
python -m unittest discover -s backend/tests -v
python scripts/run_phase7_verification.py
```

### Current API foundation

- `GET /api/health` returns local server status.
- `GET /api/config` returns the default game variant and declared rule variants.
- Static files are served from the `frontend/` directory.

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

### 3. Deck Assets (`data/`)
* **[Standard_52_Card_Deck_Extracted.md](data/Standard_52_Card_Deck_Extracted.md)**: Human-readable markdown reference with Unicode symbols and vector SVG URLs from Wikipedia.
* **[cards_52_extracted.json](data/cards_52_extracted.json)**: Normalized JSON database with codes (`Ac`, `Kh`), suits, ranks, Unicode codepoints, and colors for traditional and 4-colour decks.
