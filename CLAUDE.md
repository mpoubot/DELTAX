# DELTAX — project instructions

Autonomous options trading agent for the **Alpaca AI Trading Agents Hackathon**
(lablab.ai × Alpaca). Team of 3: 🇺🇸 US · 🇱🇻 Latvia · 🇩🇰 Denmark.

**Deadline: Fri 4 Sept 2026, 11:00 AM EDT.** Read `HACKATHON-RULES.md` before
proposing any scope. If a task doesn't advance one of the five judging criteria
before that timestamp, it waits until after.

---

## Read these first

| File | What it is |
|---|---|
| `HACKATHON-RULES.md` | Binding competition constraints + open red flags |
| `STRATEGY.md` | Why the agent is built the way it is; the design response to the short-window P&L problem |
| `research/options/golden-rules.md` | Options rules from the video corpus, with the expectancy gate |
| `research/stocks/golden-rules.md` | **Alyrise** — Elsa's stock engine spec. Authoritative for stocks; never apply to options |
| `TEAM.md` | Team logistics, prize split, time zones |

---

## 🔴 Hard constraints — never violate

1. **Options are mandatory.** Every strategy must incorporate options trading.
   Stock-only or crypto-only work does not qualify for judging.
2. **Must use the Alpaca CLI or MCP server.** We use the **CLI** (installed:
   `alpaca`, v0.0.14). Not the raw REST API — the CLI usage is a graded
   requirement.
3. **Paper trading only.** Never set `ALPACA_LIVE_TRADE=true`. Never touch a live
   account. The CLI defaults to paper; keep it that way.
4. **The competition account `PA3ID1B9L6BP` is locked.** Created 2026-08-29
   05:23 UTC with zero prior orders — that clean history is our eligibility
   evidence, and its P&L is what gets judged. Do all development against your own
   personal paper account. Only the designated runner trades the competition
   account, only for the real run.
5. **Never commit credentials.** `.env.alpaca` is gitignored and the secret
   appears nowhere in history. Keep it that way. Verify before any push.
6. **Never commit raw video captions** or third-party PDFs. The research notes are
   our own distillation; raw source material stays out of the public repo.
7. **Keep the engines separate.** Alyrise (stocks) and our options engine share a
   risk/execution/ledger layer but never share strategy rules or capital pools.
   Elsa's spec is explicit: do not merge stock rules with options rules.

---

## Risk gates — the product

These are not suggestions. They are the thing being demonstrated, and they exist
because the research corpus showed that every commercial source optimizes for win
rate and ignores the tail.

```
Expectancy gate:   E = (1 + W/L) × P − 1        trade only if E > 0
Per-position:      max loss ≤ 1% of equity      ($1,000)
Portfolio:         Σ max loss ≤ 5% of equity    ($5,000)
Structures:        defined-risk only            (verticals, iron condors)
Expiry:            7–21 DTE                     (0DTE is banned — rule R5)
Reward:risk:       ≥ 2:1, defined before entry
Sizing:            quantity = risk budget ÷ (entry − stop)
```

**Refusing to trade is a first-class outcome.** The agent must log a decision
record for *every* evaluation — trade or refusal — naming the gate that failed and
its value. An agent that explains 78 refusals is the deliverable; the P&L is one
criterion of five.

---

## Working principles

- **Never promote a rule on win rate.** Expectancy only. This is how the earlier
  TSLA playbook failed validation, and the entire video corpus is built on the
  assumption that killed it.
- **Pre-registration matters.** The rule set and predicted expectancy get
  committed to git *before* Monday's open. Actual is then reported against
  predicted. Don't retroactively adjust the strategy and present it as the plan.
- **Report P&L with error bars** — n, win rate, average win/loss in R-multiples,
  computed expectancy, and an explicit note that the sample is too small to be
  significant.
- **Flatten all positions before Friday 11:00 AM EDT** so the judged number is
  realized, not a mark.

---

## Setup for a new teammate

```bash
git clone <repo-url> && cd DELTAX
brew install alpacahq/tap/cli          # macOS
cp .env.alpaca.example .env.alpaca     # add YOUR OWN paper keys, not the team's
chmod 600 .env.alpaca
set -a; . ./.env.alpaca; set +a
alpaca doctor                          # expect: profile paper, all checks passed
```

Get your own paper account at alpaca.markets — free, no card. The rules
explicitly permit any paper account during development.

## Useful CLI commands

```bash
alpaca account get                     # balances, options level, buying power
alpaca clock                           # is the market open
alpaca option contracts --help         # chain discovery
alpaca data option --help              # quotes and greeks
alpaca order submit --order-class mleg --legs ...   # multi-leg spreads
alpaca position list
```

Multi-leg (`mleg`, up to 4 legs) is how defined-risk spreads get submitted. Every
command takes `--jq` for filtering and emits JSON, which suits agent loops.

---

## Build order

1. Risk gate module — pure functions, unit-tested, no market dependency
2. Decision logger — structured JSON per evaluation
3. Candidate screen — chain pull, liquidity filter, 7–21 DTE band
4. Backtest harness — historical expectancy for the pre-registration
5. Execution via `alpaca order submit`
6. Pre-registration commit — **before Monday 09:30 ET**
7. Flatten routine — scheduled before Friday 11:00 ET

## Conventions

- Python 3, standard library first; keep dependencies minimal and MIT-compatible.
- Shell out to the `alpaca` CLI rather than calling REST directly — CLI usage is
  graded.
- Every module that makes a trading decision must be testable without a live
  market connection.
- Submission repo must be original and MIT-compliant.
