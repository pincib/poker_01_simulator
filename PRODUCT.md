# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: Python 3.10+ standard library for the local backend and server, with vanilla HTML, CSS, and JavaScript in the browser. This follows the roadmap's zero-install local execution constraint.

## Users

Poker players training from Texas Hold'em fundamentals toward Pot-Limit Omaha (PLO), using the supplied Champion study materials and companion lessons.

## Product Purpose

Provide a local poker simulator where players can practice hands and learn from mathematical feedback, including equity, pot odds, expected value, stack-to-pot ratio, and hand review.

## Positioning

The simulator connects playable poker decisions to a training coach grounded in the project's supplied study guides, while keeping the application locally runnable without third-party Python dependencies.

## Operating Context

The application runs on the player's computer and opens in a web browser at localhost. Texas Hold'em is the initial game; PLO is a planned extension. The existing study guides and architecture documents are the curriculum and technical reference.

## Capabilities and Constraints

- The planned training experience includes a poker table, live coaching information, session review, and leak tracking.
- The mathematical layer is intended to calculate equity, pot odds, EV, and SPR.
- The core should keep game rules, mathematical analysis, opponent decisions, and coaching modular.
- Python 3.10+ and the Python standard library are the default backend constraints; the browser client uses HTML, CSS, and vanilla JavaScript.
- The application must be usable locally without a dependency installation step.
- Texas Hold'em is the first game mode; the architecture should leave a path to four-card PLO rules.

## Evidence on Hand

- `docs/study_guides/Zero to PLO50 - v7.md`
- `docs/study_guides/Zero to PLO50 - Study Companion v1.0 (EN).md`
- `docs/architecture/01_Texas_Holdem_Complete_Guide.md`
- `docs/architecture/02_Poker_Simulator_Brain_Architecture.md`
- `docs/architecture/03_Simulator_Implementation_Roadmap.md`
- No product analytics, user research, or external performance benchmarks are present; do not invent them.

## Product Principles

- Keep the live decision and the information needed to understand it close together.
- Make coaching explain decisions with visible poker mathematics.
- Preserve the project's study-guide terminology and learning progression.
- Keep the first playable game focused on Texas Hold'em while isolating rules for future variants.
- Make local setup straightforward and avoid mandatory third-party runtime dependencies.
