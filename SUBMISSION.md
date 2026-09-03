# Submission fields — copy/paste into lablab.ai

## Project title

**DELTAX — the options agent that refuses**

*(alternates: "DELTAX — 1,000 candidates, 9 trades" · "DELTAX — audited refusals,
defined risk")*

---

## Short description (one line)

An autonomous options agent that screened 1,000 spreads, approved 9, and can name
the gate that killed every one of the other 991.

---

## Long description

DELTAX trades defined-risk vertical credit spreads on liquid ETFs, autonomously,
every five minutes of the session. Fifteen deterministic gates run on every
candidate and all of them fail closed — unreadable data is a refusal, never a
skip. Every decision, approval and refusal alike, is written to a hash-chained
append-only ledger: 2,851 entries and counting.

The agent does not guess an entry. It enumerates every eligible strike pair in the
chain and maximises credit net of the round-trip cost of crossing both books.
Exits are placed at entry, not watched for: a GTC buy-to-close at 50% of credit
rests from the moment a spread is opened, backed by a trailing take-profit and a
hard flatten before judging.

We also turned strategies off. A supply-shock catalyst structure was retired after
backtesting on 46 expiries of real OPRA prices returned −9% per trade with its one
good regime failing Bonferroni correction. Mid-contest we measured that we were
selling volatility below realised on our largest position — a mathematically
losing trade — and shipped a variance-premium gate that makes it impossible to
repeat.

The engineering record is the product. In the final 48 hours we found and fixed a
variable-shadowing bug that silently disabled a safety gate for an entire session,
a risk formula that measured premium instead of maximum loss (with a test that
asserted the bug), a fully-tested gate that was never fed any data, and a deadline
control with no test at all. The last two were caught by mutation testing —
corrupting each rule on purpose to see whether the suite noticed.

789 tests. 28 modules. Paper trading only.

---

## Tech tags

`python` · `alpaca-trading-api` · `alpaca-cli` · `options-trading` ·
`credit-spreads` · `algorithmic-trading` · `risk-management` · `monte-carlo` ·
`quantitative-finance` · `autonomous-agents` · `mutation-testing` · `black-scholes`

## Category tags

`fintech` · `trading-agents` · `risk-engineering` · `automation`

---

## Links

- Live board: https://pautax007.github.io/DELTAX/
- Repository: public, MIT
- Paper account: `PA397N6FXXIE`
- Write-up: `WRITEUP.md`
