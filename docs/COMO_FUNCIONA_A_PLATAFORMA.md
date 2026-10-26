# Poker Mastery — Platform Overview

## Cover

**A clearer way to study poker.**

Local practice. Live decision support. Structured hand review.

Texas Hold’em · PLO4 · Play, analyze, review

## 01 / Platform overview

One workspace. Three learning loops. Practice a hand, understand the decision, then revisit the evidence.

- **Play:** A six-seat table against five heuristic bots.
- **Understand:** Live context for price, equity and stack depth.
- **Review:** Completed hands, decision notes and study cues.

Runs locally. No real-money play. No third-party Python packages.

## 02 / How a session flows

**Deal → Decide → Showdown → Review**

Choose a game. Take a legal action. Compare eligible hands. Study the hand history.

Actions: Fold · Check · Call · Bet/Raise · All-in. The local game engine validates actions and betting limits.

## 03 / Game formats

### Texas Hold’em

2 hole cards. Build the best five-card hand using any combination of hole cards and community cards.

### Pot-Limit Omaha (PLO4)

4 hole cards. At showdown, use exactly 2 hole cards and exactly 3 community cards.

Training table: 6 seats, 5 bots. PLO4 defaults: $1/$2 blinds, $200 stacks, no rake or fees. The format can be changed between hands.

## 04 / Live coach

| Metric | Quick read |
| --- | --- |
| Pot odds | Equity threshold for a call |
| Estimated equity | Estimated share of the pot |
| Call EV | Expected value of calling |
| SPR | Effective stack divided by pot |
| Draw analysis | Outs, blockers and redraws |

Equity uses sampling. Bots are heuristic. Multiway spots may be simplified. This is not solver or GTO advice; outcomes are not guaranteed.

## 05 / Hand review & setup

Session review includes cards revealed at showdown, actions, contributions, payouts, coach notes and study prompts. Study targets are prompts, not verdicts.

History is stored in local memory and cleared when the server stops.

### Start locally

Python 3.10+ · `python run_simulator.py` · opens at `127.0.0.1:8000`
