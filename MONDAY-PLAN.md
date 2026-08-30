# DELTAX — Monday 31 Aug trading plan

> ## ⚠️ STALE — do not trade from this document
>
> Written before two findings that change it:
>
> 1. **The contest window is 5 sessions, not a week.** The day-7 exit this
>    plan assumes fires **Mon 7 Sep — after the deadline** (rule **E17**).
>    The 4-day expectancy is unmeasured.
> 2. **The universe below is 3 ETFs.** Screening has since passed 46 tickers.
>
> Read **[STATUS.md](STATUS.md)** instead. This file must be rewritten before
> it becomes the pre-registration commit at 09:30 ET Monday.

**Status: draft for ratification. Becomes the pre-registration commit before
09:30 ET.** Nothing below is a prediction — it is a commitment to rules. Which
contracts actually trade is resolved by the gates at entry time.

---

## 🔴 Honest position: only one book can trade Monday

| Book | Scanner | Can trade Monday? |
|---|---|---|
| **Income core** (credit verticals) | ✅ `screen_income_book` built, dry-run against live chains | **Yes** |
| **Satellite** (debit verticals) | ❌ **not built** — no signal scanner exists | **No** |

The satellite book's entry trigger (EMA3/8 cross + MACD histogram + RelVol ≥1.5
on daily bars) has no implementation. Until it exists, 40% of the risk budget
is idle and the plan is income-only. That is the single highest-value build
item remaining.

---

## Book 1 — Income core

**Budget:** ≤ $6,000 total max loss (60% of the $10,000 portfolio cap)
**Per position:** ≤ $2,000 max loss · **max 3 concurrent**

### Universe — fixed, three names

| | Why these only |
|---|---|
| **SPY** | Deepest options market in existence |
| **QQQ** | Deep, and the regime filter's tech read |
| **IWM** | Deep, small-cap read |

**All three are ETFs — no earnings risk by construction.** That is why the
income book is unaffected by the blackout below.

### Structure

Credit verticals. Width: **SPY $5 · QQQ $5 · IWM $2**. Expiry: nearest inside
**7–21 DTE** — Monday that means **Sep 9, Sep 11, Sep 14 or Sep 18**.

### Direction — resolved at 10:00 ET, not now

Counted from SPY/QQQ/IWM vs their intraday VWAP:

| Weak | Posture | Target short δ |
|---|---|---|
| 0/3 | Put credit spreads, SPY + QQQ | 0.30 |
| 1/3 | Put on strongest; condor others | 0.27 |
| 2/3 | Condors; call on weakest | 0.24 |
| 3/3 | Call credit spreads only | 0.20 |

**Friday's close read 3/3 weak** → call spreads at δ 0.20. That reading is
stale and will be recomputed Monday morning. Do not treat it as the plan.

### Every candidate must clear

`tradeable · defined_risk · dte 7–21 · earnings · liquidity (OI ≥ 500, order
≤ 5% of OI) · min_credit ≥ $0.75 · spread_quality ≤ 15% · credit/width ≥ 0.9 ×
short δ · position_size ≤ $2,000 · portfolio_risk ≤ $10,000`

**Exit placed at fill:** GTC buy-back at **50% of credit**.

---

## Book 2 — Satellite (blocked pending build)

**Budget:** ≤ $4,000 · per position ≤ $1,500 · max 4 concurrent · debit
verticals at **≥ 2:1**.

### Eligible universe after the earnings blackout

**✅ Clear (9):** AAPL · AMD · AMZN · GOOGL · JPM · META · MSFT · NFLX · NVDA

**⛔ Excluded (4):**

| Symbol | Reason |
|---|---|
| **AVGO** | Earnings window 2026-08-25 .. 2026-09-09 |
| **COST** | Earnings window 2026-08-13 .. 2026-09-29 |
| **TSLA** | Earnings window 2026-08-07 .. 2026-10-06 |
| **PDD** | Foreign private issuer — files 20-F/6-K, so Item 2.02 never exists. We cannot verify it is clear, so it fails closed |

Derived from SEC 8-K Item 2.02 filing cadence. Re-run each morning; a window
that closes moves a name back to eligible.

---

## Session windows (both books)

| ET | |
|---|---|
| 09:30–09:45 | No entries — auction noise |
| **09:45–10:30** | Entry window 1 |
| 11:00–14:00 | No entries — lunch lull |
| **14:30–15:15** | Entry window 2 |
| after 15:15 | No entries — uncompensated overnight gap risk |
| any time | Exits and flatten always permitted |

---

## What "trading Monday" actually looks like

1. **~07:00** — `scripts/morning-ritual.sh` runs. Regime, universe, blackout.
2. **09:45–10:30** — screener reads regime, nominates 2–3 credit verticals,
   gates decide, ledger records **every** evaluation including refusals.
3. **On each fill** — GTC exit at 50% of credit placed immediately.
4. **14:30–15:15** — regime re-read; top up if a slot is free and gates pass.
5. **Evening** — daily snapshot; ledger summary to the team.

**It is entirely possible nothing trades Monday.** Saturday's dry run nominated
two candidates and refused both. That is the system working, not failing — but
the team should expect it rather than read it as breakage.

---

## Open before the freeze

| # | Item | Owner |
|---|---|---|
| 1 | **Pricing model** — worst-case vs mid vs mid−25% of spread. Likely why the dry run refused everything | **Pautax** |
| 2 | Ratify 2%/10% caps and the 60/40 split | Elsa + Matin |
| 3 | Confirm the regime→posture port | Elsa |
| 4 | Confirm the signal-family port + RelVol 1.5 | Matin |
| 5 | Build the satellite scanner, or accept an income-only week | Claude |
| 6 | Backtest harness → the predicted expectancy this commit registers | Claude |
