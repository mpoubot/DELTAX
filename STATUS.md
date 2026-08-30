# DELTAX — Team Status

**Updated: Sun 30 Aug 2026 (expiry decision)** · Trading opens **Mon 31 Aug 09:30 ET** ·
Submission **Fri 4 Sep 11:00 ET**

For Elsa (`IlzeTheGreat`) and Matin (`mpoubot`). This is the single page to
read to catch up. Everything below is either committed code or a decision
that has been made — open questions are listed separately at the end.

---

## 🔴 Read this first: the contest window is 5 sessions, not a week

| | |
|---|---|
| Sessions available | **5** — Mon 31 Aug → Fri 4 Sep |
| Labor Day 2026 | 7 Sep — *outside* our window, no holiday |
| Friday submission | 11:00 ET, ~90 min after the open |
| **Usable** | **~4.5 sessions** |

**This invalidates a number we have all been quoting.** Our headline
expectancy of **+0.107** was measured on a **day-7 / 50%-credit exit**. Entry
Monday plus seven days is **Mon 7 Sep — three days after the deadline.**

That exit cannot fire inside the contest. Positions will be marked to market
having captured only partial decay. **The 4-day expectancy has never been
measured.** Recorded as rule **E17**; the sweep is the next task.

Nothing here says the strategy is worse — it says we do not yet know the
number that describes what we are actually placing.

---

## Asset allocation — decided

| Class | Status | Rationale |
|---|---|---|
| **Options** | **Core book.** Trading Monday. | Only class with proven positive expectancy, working execution code, and it satisfies hackathon Rule 3. |
| **Crypto** | **Approved, not built.** | Directed by Pautax 30 Aug. No engine and no backtest yet — `deltax/rss.py` references crypto only as a news feed. |
| **Stocks** | **Approved, not built.** Long *and* short. | Directed by Pautax 30 Aug. See the evidence problem below. |

**Sequencing.** Options deploy Monday because they are validated. Stocks and
crypto get built and tested during the week and added once they clear
validation. Deploying untested code at Monday's open is the one genuinely
unrecoverable mistake available to us.

---

## Why the stocks work has not shipped yet

Not a preference — five independent tests, none of which cleared the bar:

| Strategy | Source | Data | Result |
|---|---|---|---|
| VWAP regime filter | our screener | 2,679 days | **t = −1.29** — sign ran *backwards* |
| EMA / MACD / RelVol | Matin's Equity Lab | 32,148 bars | **failed Bonferroni** |
| 20-day breakout | Pautax | full history | t = +1.08, not significant |
| Breakout + uptrend | our refinement | full history | t = −0.11 — filter made it worse |
| News direction (TSLA) | research corpus | full history | **p = 0.44** — coin flip |
| Catalyst / PEAD | Matin's engine | full history | not proven — *best signed* |

### But we found a flaw in how we tested them

**Every one of those tests measured fixed-horizon forward returns — buy, hold
5/10/15 days, measure. Not one modelled an exit.** No stop, no profit target,
no time stop. `grep -rn "stop_loss\|take_profit\|trail" backtest/` returns
nothing.

That is the same mistake that nearly killed the options book: held to expiry
the condor scored −0.021 to +0.076 and was almost abandoned; modelling the
exit flipped **every configuration** positive. **The edge lived in the exit.**

**So we tested stock entries. We never tested stock strategies.** Those are
not the same thing. The signals above deserve a re-run with exits modelled
before anyone concludes they are dead.

### What a 5-day clock does to the stock ideas

Honest revision: **pairs trading and PEAD both need weeks to converge** —
post-earnings drift plays out over roughly 60 days. Across 4 sessions you
capture a sliver. They are good ideas for the wrong horizon. The exit re-test
is the part that survives the schedule.

---

## Shipped since the last update

**`deltax/permission.py` — global trade-permission state** *(from Matin's
proposal)*

One state above strategy that no candidate can override:

`NORMAL → CAUTION → DEFENSIVE → NO_NEW_POSITIONS → HALT`

Evidence recommends, deterministic code decides, and the **most restrictive**
justified reading always wins. Generalises three things we were enforcing
separately: E13 data validation, the S5 kill-switch, and the market-closed
check. Fail-closed on every field — a missing input never yields `NORMAL`.

*Adapted for a condor book:* Matin's `SHORT_ONLY` became **`DEFENSIVE` =
call spreads only.** A call credit spread is already defined-risk bearish
exposure, so we get the bearish state without borrow or locate.

**Security fix found while wiring it in.** `--force` bypassed both the
calendar window *and* the new permission state **regardless of `--live`** —
one flag could have pushed real orders outside session hours during a HALT.
`--force` is now inert whenever real orders are possible, the CLI refuses
`--force --live`, and any override prints an ADVISORY banner and records
`overridden: true` in the ledger.

**Verification:** 229 tests green · live dry run reaches the strategy and
refuses on real gates · ledger chain intact.

### Not adopted from Matin's proposal, with reasons

- **Short-equity engine** — a call credit spread already gives defined-risk
  bearish exposure. Shorting stock adds borrow, locate and unbounded loss to
  reach a place we can already stand.
- **Market Intelligence layer** (Asia / Europe / futures, 3 daily news scans)
  — sound architecture, but "Asia down → be careful" is an untested empirical
  claim. **E10** says nothing gates trades until it is backtested. Queued.

---

## Risk posture

| Control | Value |
|---|---|
| Per position | **2%** ($2,000 max loss) |
| Portfolio | **10%** ($10,000 max loss) |
| Collateral deployed | ~$9,700 |
| Idle cash | ~$90,300 — *the mechanism, not waste* |

The idle 90% is what makes the risk defined. Last week's backtest: **$9,684
collateral → +$4,459, +46% on capital at risk**, +4.46% on the account.

**Diversification matters more over 4 days, not less.** With a short window
and a dozen positions, outcome variance swamps expectancy — the law of large
numbers does not save us. More positions, smaller each, tightens the
distribution around our edge.

---

## ✅ DECIDED — expiry for Monday

**Trade the Sep 11 expiry. `MIN_DTE` stays 7. No gate constant changed.**

The sweep ran and overturned itself twice. Full write-up in **E17–E19**;
the short version:

1. Sweeping 4–30 DTE showed shorter expiries capture more of a fixed 4-day
   hold — as theta acceleration predicts.
2. **δ0.30 was an artifact.** Holding the credit at `1.15 × δ × width` demands
   the market pay 1.6–2.1× realized vol; the real premium is ~1.1–1.4×.
   Discarded.
3. **5, 7 and 10 DTE do not exist.** A Monday entry reaches only Sep 4,
   Sep 11 or Sep 18. BDX and CB list no weeklies at all.

Walk-forward at the expiries that exist, δ0.20, TEST ≥2024:

| | Sep 4 | Sep 11 | Sep 18 |
|---|---|---|---|
| SPY | +0.245, t=2.70 | **+0.109**, t=1.22 | +0.030, t=0.33 |
| QQQ | +0.136, t=1.63 | **+0.023**, t=0.32 | −0.020, t=−0.29 |
| IWM | +0.251, t=2.84 | **+0.147**, t=1.73 | +0.076, t=0.92 |
| Gate | 🔒 blocked | ✅ | ✅ |

**The only significant column is the one MIN_DTE forbids.** We are trading a
positive point estimate with a wide error bar, and that is the honest
description of it.

**Why not Sep 4.** It requires relaxing a safety rule the night before, on a
model built the same day, at the point where that model's constant-implied-vol
assumption is weakest and gamma is largest. **E19** is the deciding argument:
per-trade expectancy is measured over 127 independent weeks and the contest
gets one draw. Forty condors on correlated equities are roughly one bet on
realized market volatility, so the shortest expiry maximises expected return
*and* the correlated tail at once.

**Bug this surfaced.** `choose_expiry` ranked expiries by *most liquid*, which
always selects the monthly — monthlies carry far more open interest than
weeklies. The agent would have traded Sep 18, the weakest column. Selection is
now **nearest qualifying**, with liquidity kept as a threshold rather than the
ranking key. Verified live: SPY → Sep 11; IWM → Sep 18 (its weekly is too thin
in band, which is the fallback working).

---

## Open — needs a decision

1. **Universe** — add JBGS, ZETA, ACHC, BV, FN? They passed screening. Still
   unanswered.
2. **Ratify** the 2% / 10% caps, the 40-ticker universe, and direction-neutral
   condors.
3. **`MONDAY-PLAN.md` is stale** — still describes a 3-ETF universe and an
   unbuilt satellite book. Must be rewritten before it becomes the
   pre-registration commit at 09:30 Monday.
4. **Crypto is 24/7**, which conflicts with the `market_open` check in
   `permission.py` and the entry window in `calendar.py`. Needs deciding
   before code.

## Admin still outstanding

- [ ] Pre-registration commit — **before Mon 09:30 ET**
- [ ] Repo public — **before Fri 4 Sep 11:00 ET**
- [ ] Demo video, slides, cover image, one-page write-up
- [ ] Alpaca Finance contacted re: three-way prize split
- [ ] Each teammate uses their **own** paper account. The competition account
      `PA3ID1B9L6BP` is locked to one designated runner.
