# DELTAX — Complete Rule Set

**For team evaluation before the Monday pre-registration freeze.**
Updated 2026-08-29 · 91 unit tests green · account `PA3ID1B9L6BP` ($100,000)

Three layers: **gates** (code the agent enforces), **strategy** (what it trades),
**research** (where the rules came from). Only the first layer can stop a trade.

---

# LAYER 1 — Gates · `deltax/gates.py`

Every candidate passes all applicable gates or is refused and logged. Pure
functions, no network, no model-overridable path.

| # | Gate | Rule | Source |
|---|---|---|---|
| 1 | `tradeable` | No halts, no pending corporate action | DATA-FEEDS gate 2 |
| 2 | `defined_risk` | Max loss must be bounded at entry | R5 / Alyrise / AURA |
| 3 | `dte` | **7–21 days.** 0DTE banned | R5 |
| 4 | `earnings` | No earnings announcement before expiry | DATA-FEEDS gate 1 |
| 5 | `liquidity` | OI ≥ **500** per leg; order ≤ **5%** of OI | Video 02 |
| 6 | `min_credit` | Credit ≥ **$0.75** per contract | Videos 01, 04 |
| 7 | `spread_quality` | Worst leg bid/ask ≤ **15%** of its mid | AURA criteria |
| 8 | `position_size` | Max loss ≤ **2%** of equity ($2,000) | E7 |
| 9 | `portfolio_risk` | Σ max loss ≤ **10%** of equity ($10,000) | E7 |
| 10 | `credit_fraction` | **credit/width ≥ 0.9 × short delta** *(credit only)* | E3 + live measurement |
| 11 | `reward_risk` | **≥ 2:1** *(debit only)* | S1 |
| 12 | `expectancy` | **E = (1 + W/L) × P − 1 > 0** | S0 |

**Sizing:** `contracts = (0.02 × equity) ÷ max_loss_per_contract`
**Structural floor:** if every open position hit max loss simultaneously, the
account ends at **$90,000**. Not a forecast — arithmetic.

### Why gate 10 is delta-relative (decided today)

A flat floor cannot work. Measured on live chains, credit/width runs ≈ 0.75–0.8 ×
short delta. Any fixed floor selective at 35Δ silently bans every trade at 20Δ —
and our regime logic pushes delta *down* exactly when markets weaken. The
delta-relative floor asks the economically meaningful question instead: *is this
premium fair for the probability of loss being taken?*

---

# LAYER 2 — Strategy

## Barbell: two books, one account

| | Income core | Directional satellite |
|---|---|---|
| Share of risk | 60% (≤ $6,000) | 40% (≤ $4,000) |
| Structure | Credit verticals / condors | Debit verticals |
| Underlyings | SPY, QQQ, IWM + mega-caps | Liquid optionable mega-caps |
| Trigger owner | **Elsa** (regime) | **Matin** (signal family) |
| Payoff test | credit/width ≥ 0.9 × δ | ≥ 2.5:1 at entry |
| Position cap | — | ≤ $1,500, max 4 concurrent |
| Exit | Buy back at **50% of credit** | Sell at **+100% of debit** |

## Entry trigger — income core (Elsa's Alyrise filter, ported)

Count how many of SPY/QQQ/IWM trade **below their intraday VWAP**:

| Weak | Posture | Target short delta |
|---|---|---|
| 0/3 | Put credit spreads (SPY, QQQ) | 0.30 |
| 1/3 | Put on strongest; condor others | 0.27 |
| 2/3 | Condors; call on weakest | 0.24 |
| 3/3 | Call credit spreads only | 0.20 |

Missing benchmark data **fails conservative** — treated as 3/3 weak.
Iron condors are expressed as **two independent verticals**, each gated and
sized separately.

## Entry trigger — satellite (Matin's Equity Lab family, tightened)

On completed daily bars, entered next morning 9:45–10:15 ET:
1. EMA3 **crosses** above EMA8 (the cross, not merely above)
2. MACD histogram > 0
3. **Relative volume ≥ 1.5×** 20-day average *(tightened from his ≥ 1)*

Mirrored for bearish → put debit spreads. Width chosen so debit ≤ 28% of width,
which is what makes 2.5:1 achievable.

## Session windows (E1, E2)

| ET | Rule |
|---|---|
| 9:30–9:45 | No entries — auction noise |
| 9:45–10:30 | Satellite + income window 1 |
| 11:00–14:00 | **No entries** — lunch lull, worst mleg fills |
| 14:30–15:15 | Income window 2 |
| after 15:15 | No entries — uncompensated overnight gap risk |
| always | Exits live; flatten routines exempt |

## Pre-registered Friday branch (E6)

- **Green at Thursday close** → flatten Thursday. Lock the realized number.
- **Red at Thursday close** → carry ≤ 4% equity of satellite into Friday as
  capped recovery, **flat by 10:15 ET** regardless.

## Expected range (goes in the pre-registration)

Floor **−10% structural** · income alone +0.5–1.5% · +1–2 satellite hits
**+4–10%** · strong week +10–15%.

---

# LAYER 3 — Research golden rules

## Options (6 videos, 5 viewpoints)

| | Rule | Support |
|---|---|---|
| **R1** | Never sell a put unless glad to own at that strike; never write a call unless glad to sell there | 2 sources |
| **R2** | Own the collateral before selling against it | 2 sources |
| **R3** | Short strike in the **15–35Δ** band | 2 sources — *convention, not proven edge* |
| **R4** | Exposure shrinks as expiry approaches | 2 sources |
| **R5** | **0DTE out of scope** — hard constraint | WSJ evidence |

## Process (4 videos + AURA)

| | Rule |
|---|---|
| **S0** | **Expectancy gate** E = (1+W/L)×P − 1 > 0 — 3 independent sources |
| **S1** | Minimum reward:risk floor — 4 sources |
| **S2** | Size from defined risk, constant fraction |
| **S3** | Backtest → simulator → live at minimum size → scale, gated on **measured metrics** |
| **S4** | Log every evaluation with the conditions present at entry |
| **S5** | Kill-switch thresholds come from the backtest, not intuition |
| **S6** | Not trading is a position |
| **S7** | Screen the underlying before analysing it |

## Execution & timing (E1–E9)

E1 enter where the book is deep · E2 most active ≠ best to enter ·
E3 payoff gates must be structure-aware · E4 **triggers nominate, gates decide** ·
E5 exits placed at entry · E6 branches decided before they arrive ·
E7 raise risk only where the floor stays arithmetic · E8 sell premium in the
morning · E9 **time-of-day is hygiene, never signal**

## Validation bar (AURA, adopted corpus-wide)

Pre-committed **before** looking: **OOS profit factor > 1.10 AND >50% of
walk-forward folds positive**, on top of E > 0. **Never tune after holdout.**
Failed branches are stopped, not tuned until they pass.

## Stocks — Alyrise (Elsa, authoritative for the stock engine)

CORE / ACTIVE / INTRADAY dip-buying off VWAP references, isolated capital pools,
sell priority stop → trailing → target → max-hold. Not running this week (its
+12%/−30.5% profile needs longer than 4.5 sessions). Full spec in
`research/stocks/golden-rules.md`.

---

# OPEN ITEMS — need team decisions before Monday 09:30 ET

1. **Ratify the risk dial.** 2% / 10% caps and the 60/40 barbell split.
2. **Conservative vs mid pricing.** Candidates are currently priced at
   worst-case (sell the bid, buy the ask) while ENTRY-TRIGGERS says we *work a
   limit at mid*. That inconsistency may itself be why nothing passed today's
   dry run. Options: keep worst-case (understates credit, refuses good trades),
   price at mid (matches intent, risks unfilled orders), or price at mid minus a
   haircut. **Recommend mid minus 25% of the spread**, with fills logged so we
   can measure the assumption.
3. **Confirm the ports.** Elsa on the regime→posture mapping; Matin on the
   signal family and RelVol 1.5.
4. **Saturday-quote caveat.** Today's dry run ran on Friday's stale closes —
   20% bid/ask on SPY and thin far-OTM OI are likely weekend artifacts, not
   Monday conditions. Re-run the dry run Monday pre-open before trusting it.
5. **Satellite screener + backtest harness** still to build; the harness supplies
   the predicted expectancy the pre-registration commits to.
