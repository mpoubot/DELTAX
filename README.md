# DELTAX

> **Team: start at [STATUS.md](STATUS.md)** — current state, decisions, and what still needs deciding.

Autonomous options trading agent for the **[Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon)**
(lablab.ai × Alpaca, 28 Aug – 4 Sep 2026).

**Team:** 🇺🇸 pautax007 · 🇱🇻 IlzeTheGreat (Elsa) · 🇩🇰 mpoubot (Matin)

## The idea

Five days of paper P&L is noise, and our own research proves it — so we don't
chase the number. The product is the **discipline**: an agent that sizes every
position from defined risk, refuses any candidate that fails a deterministic
gate, logs the reason for every refusal, and pre-registers its rules before the
market opens. The AI proposes; pure-function code disposes. All three team
members converged on that boundary independently.

```
Expectancy gate    E = (1 + W/L) × P − 1 > 0
Per-position cap   max loss ≤ 1% of equity
Portfolio cap      Σ max loss ≤ 5% of equity
Structures         defined-risk only (verticals, iron condors)
Expiry             7–21 DTE · 0DTE banned
Reward:risk        ≥ 2:1 before entry
Validation bar     OOS PF > 1.10 AND >50% folds positive · no post-holdout tuning
```

## Status — 2026-08-29

| Piece | State |
|---|---|
| Research corpus (10 videos, 3 team packs, 9+ viewpoints) | ✅ `research/` |
| Risk gate module + 29 unit tests | ✅ `deltax/gates.py` |
| Alpaca CLI wired (paper), account verified | ✅ `PA397N6FXXIE`, $100k, options L3 |
| Decision logger · chain screener · backtest harness | 🔜 next |
| Pre-registration commit | ⏰ **before Mon 31 Aug, 09:30 ET** |
| Flatten + submit, repo → public | ⏰ **Fri 4 Sep, before 11:00 ET** |

## Map

| Read | For |
|---|---|
| [HACKATHON-RULES.md](HACKATHON-RULES.md) | Binding constraints + red flags |
| [STRATEGY.md](STRATEGY.md) | Why the agent is built this way |
| [TEAM.md](TEAM.md) | Prize split, repos, time zones |
| [ONBOARDING.md](ONBOARDING.md) | Teammate setup, step by step |
| [DATA-FEEDS.md](DATA-FEEDS.md) | News as veto, never signal |
| [research/00-README.md](research/00-README.md) | Corpus index: options · stocks · crypto · AURA |
| [CLAUDE.md](CLAUDE.md) | Auto-loaded context for every Claude Code session |

## Quick start

```bash
brew install alpacahq/tap/cli
cp .env.alpaca.example .env.alpaca   # YOUR OWN paper keys — never the team's
set -a; . ./.env.alpaca; set +a
alpaca doctor                        # expect: profile paper, all checks passed
python3 tests/test_gates.py          # expect: 29 passed
```

Paper trading only. The competition account is locked — see CLAUDE.md rule 4.
