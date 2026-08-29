# DELTAX — Competition Playbook (P&L-forward)

**Team decision 2026-08-29: P&L is the priority for the competition week.**
This document turns the conservative research posture into a tournament
posture — deliberately — while keeping the floor structural. It merges the
three rule sets: our gates, Elsa's regime filter, Matin's signal family and
validation discipline. It becomes part of Monday's pre-registration commit.

---

## The tournament logic, stated honestly

A one-week P&L contest is a tournament: what wins is not expected value but a
**right-tail outcome with a survivable floor**. Pure premium selling is too slow
(realistic +0.5–1.5% in 4 days). Pure directional punting is a coin flip that
busts half the field. The answer is a **barbell**:

- an **income core** that makes the account green with high probability, and
- a **directional satellite** that buys positive skew with capped cost.

Both books are defined-risk options. The worst case for the entire week is a
known number chosen in advance.

## Risk dial — needs team ratification

| Parameter | Research posture | **Competition posture** |
|---|---|---|
| Per-position max loss | 1% ($1,000) | **2% ($2,000)** |
| Portfolio max loss | 5% ($5,000) | **10% ($10,000)** |
| Worst possible week | −5% | **−10% → account floor $90,000** |

Everything else holds: defined-risk structures only, 7–21 DTE, no 0DTE (R5),
liquidity gates, earnings veto, ledger on every evaluation.

## Book 1 — Income core (~60% of risk budget, ≤ $6,000 total max loss)

Credit spreads / iron condors on **SPY, QQQ, IWM + mega-cap optionables**,
7–21 DTE, short strike in the 15–35Δ band, credit ≥ $0.75, R:R gates applied
to the spread width.

**Direction chosen by Elsa's regime filter, verbatim from Alyrise:** count how
many of SPY / QQQ / IWM trade below their intraday VWAP.

| Weak count | Options posture |
|---|---|
| 0 / 3 | Sell put credit spreads (bullish tilt) |
| 1 / 3 | Put spreads on the strongest index; iron condor elsewhere |
| 2 / 3 | Iron condors / call credit spreads |
| 3 / 3 | Call credit spreads only — or stand aside if vol is exploding |

This is Alyrise's exact mechanism repurposed as the options direction selector —
her engine's deeper-discount logic becomes our deeper-OTM logic.

**Management:** take profit at **50% of credit** (frees risk budget to recycle —
the compounding engine of the week). No stop: the spread's max loss is the stop.
Open the core **Monday morning** — theta needs every one of the 4.5 days.

## Book 2 — Directional satellite (~40% of risk budget, ≤ $4,000 total max loss)

**Debit spreads** (calls or puts), 7–21 DTE, minimum **2.5:1** reward:risk at
entry (TradingLab floor, above Cameron's 2:1), max loss per position ≤ $1,500.

**Entry signal from Matin's Equity Lab family, tightened per our review:**
EMA3/EMA8 crossover + MACD histogram > 0 + **relative volume ≥ 1.5** (his ≥ 1
is a near-null filter), on his liquid optionable universe (AAPL MSFT NVDA AMZN
META GOOGL TSLA AVGO COST …) — names whose chains pass our OI gate, unlike
low-float momentum stocks. Mirrored logic for bearish entries. Cap: **4
concurrent satellite positions.**

Labeled honestly in the write-up: *unvalidated signal family used as a
candidate generator; every entry still passes the deterministic gates; max
loss bounded at entry.*

## The Friday decision — pre-registered, conditional

The September jobs report typically lands **Friday ~8:30 ET — 2.5 hours before
the submission deadline.** Holding through it is a coin flip on the entire week.
Pre-commit the branch now so it's strategy, not panic:

- **If the account is GREEN at Thursday's close:** flatten everything Thursday
  EOD. Lock the realized number. Friday morning = submission assembly only.
- **If the account is RED at Thursday's close:** keep/add satellite exposure
  ≤ 4% of equity into Friday morning as recovery optionality, flatten by
  **10:15 ET** regardless of outcome. Capped lottery, not a hail mary.

## What we are deliberately NOT running this week

| Excluded | Why |
|---|---|
| Alyrise CORE / ACTIVE | +12% / +6.5% take-profits rarely resolve in 4 days; −30% stops sized for a small live account |
| Alyrise INTRADAY as a stock engine | Only if Elsa has running code by Monday; zero build budget for it |
| Equity Lab raw stock trades | Stocks score nothing that options don't; capital fights the options books |
| 0DTE / same-week expiry | R5. One −8.7× day ends the tournament |
| Naked short options | Undefined risk breaks the floor |
| Crypto / MEXC | Cannot score; wrong venue |

## Expected outcome, stated for the write-up

Floor **−10% (structural, not statistical)**. Income core alone: realistic
+0.5–1.5%. Core + 1–2 satellite hits: **+4–10%**. Strong week (3+ hits at
2.5:1): +10–15%. We publish this range in the pre-registration and report
actuals against it — win or lose, the number means something.

## Ratification checklist (before Monday 09:30 ET)

- [ ] Caps 2% / 10% — Pautax / Elsa / Matin
- [ ] 60/40 barbell split
- [ ] Regime-filter direction mapping (Elsa confirms the Alyrise port)
- [ ] Satellite signal family (Matin confirms the Equity Lab port + RelVol 1.5)
- [ ] Friday conditional branch
- [ ] Then: pre-registration commit freezes all of it
