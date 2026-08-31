# 🔴 GOING LIVE — Mon 31 Aug 2026, 09:30 ET

**The agent begins placing real orders on the competition paper account today.**
Nobody needs to approve individual trades. It decides, executes, and closes on
its own. This page is the pre-flight record.

---

## Pre-flight: 30 passed · 0 blocking · CLEARED

| Section | Result |
|---|---|
| Infrastructure | Alpaca CLI · Python 3.14 · credentials mode 600, gitignored, absent from tracked files |
| Account | `PA3ID1B9L6BP` · ACTIVE · $100,000 untouched · options level 3 |
| Autonomous execution | Orders **enabled** · `--live` passed · `--force` never passed · paper only |
| Order safety | Every order pinned to one account; a mismatch is refused |
| Exits | GTC at 50% of credit, **rested at fill** · 2-DTE time stop |
| Agent | **366 tests passing**, 0 failing · ledger chain intact |
| Schedule | cron live · daemon running · machine held awake · 127 successful runs |

---

## What the agent does, unattended

```
09:30  screen 17 names
   ↓   13 fail-closed gates — unknown is never treated as safe
   ↓   reconcile against the live book (never re-opens what it holds)
   ↓   size to 2% per position
   ↓   OPEN what passes
   ↓   rest a GTC buy-back at 50% of credit, immediately
every 5 min  repeat · close anything at target or 2 DTE
```

**Expected book:** ~12 positions, balanced long/short, **~$23,100 at risk**,
~$6,900 credit collected. ~$76,900 cannot be touched by any trade.

---

## The limits, in hard numbers

| Control | Value |
|---|---|
| Per position | **2%** — $2,000, defined risk, structurally capped |
| Portfolio | **30%** — $23,100 deployed today |
| Daily kill switch | **−5% → HALT** |
| Drawdown halt | **−20%** |
| Volatility | VIX +15% → DEFENSIVE · +30% → NO NEW POSITIONS |

**There is no path to total loss.** A condor's downside is capped by a long leg
already owned — not by a stop that might miss. Every failure mode fails toward
*not trading*: unknown earnings, unreadable book, stale quote, bad fill — each
one refuses.

---

## Watch it live

| | |
|---|---|
| **Dashboard** | https://pautax007.github.io/DELTAX/ |
| **Slides** | https://pautax007.github.io/DELTAX/slides.html |
| **Code** | https://github.com/pautax007/DELTAX |

The dashboard's terminal feed shows **every decision as it lands** — every
approval, every refusal with the gate that fired, every exit, every
reconciliation. Nothing summarised, nothing hidden.

---

## Overnight work (03:00–09:20)

Three critical bugs found and fixed before they could cost anything:

- **E30 — no position reconciliation.** Every cycle believed the book was
  empty. Would have breached the risk cap on the **second** run and carried
  ~1,150 positions by the close.
- **E29 — exits were never implemented.** `build_close_args()` existed and
  nothing called it. The 50% exit is where the entire measured edge lives.
- **E28 — earnings gate fail-open.** A SEC outage would have waved every
  candidate through.

Also: credentials rotated and verified · 8 financial news feeds added (10 live,
~217 articles/pass) · pre-market intelligence running since 04:00 · Matin's
decision gates registered.

**All three were found while every test was green.** Tests verify the code does
what it says; none of them asked what happens on the second run.

---

## Known limitation, stated rather than buried

`run.py` does not pass earnings data into the gates — ours runs on defaults.
Today's exposure is nil (11 ETFs plus MA, V, KO, PG, XOM, WMT, none reporting
before 11 Sep). **This must be wired before any individual-stock name joins the
universe.** Matin's blocklist-file design is the intended fix.

---

**56 rules · 366 tests · 85 commits · 3 days.** Paper trading only — no real
capital at risk.
