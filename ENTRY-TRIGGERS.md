# DELTAX — Entry Triggers (competition week)

The answer to "what actually makes us enter": **two independent trigger paths,
one per book, both feeding the same gates and ledger.** Elsa's market analysis
owns the income core. Matin's signal family owns the satellite. Nobody's
judgment fires an order — a trigger only *nominates* a candidate; the gates
decide.

```
Elsa's regime filter ──► income candidates ──┐
                                             ├──► gates.evaluate() ──► ledger ──► order / refusal
Matin's signal family ─► satellite candidates┘
```

---

## Book 1 — Income core trigger (Elsa / Alyrise)

**Cadence:** twice daily — 10:00 ET (after opening noise) and **14:30 ET**
(start of the afternoon liquidity window — the prior 13:30 check sat in the
lunch lull, where thin books widen spreads on multi-leg orders).

**Step 1 — Regime.** For SPY, QQQ, IWM: is `latest_price < intraday_vwap`?
Count the weak ones. (Alyrise §4, verbatim. Data: `alpaca data multi-snapshots`.)

**Step 2 — Posture.**

| Weak | Structure to nominate |
|---|---|
| 0/3 | Put credit spread on SPY and QQQ |
| 1/3 | Put credit spread on the *strongest* index; iron condor on the others |
| 2/3 | Iron condors; call credit spread on the *weakest* index |
| 3/3 | Call credit spreads only — stand aside entirely if regime flipped ≥2 counts since the last check (vol expanding) |

**Step 3 — Contract selection.**
- Expiry: nearest inside **7–21 DTE**.
- Short strike: nearest to **25Δ** (mid of the 15–35 band).
- Width: SPY/QQQ **$5** · IWM **$2**.
- Long strike: short strike ∓ width.

**Step 4 — Entry conditions (all must hold; gates enforce):**
- mid credit ≥ **$0.75** AND ≥ **30% of width** (`credit_fraction`)
- OI ≥ 500 on **both** legs; order ≤ 5% of the smaller leg's OI
- no earnings before expiry (ETFs: n/a by construction)
- caps: ≤ $2,000 max loss this position, ≤ $10,000 portfolio, core book ≤ $6,000

**Step 5 — Execution.** `alpaca order submit --order-class mleg` limit at mid;
re-peg one tick toward the market each 2 min, max 3 attempts, then log
REFUSE-equivalent (`unfilled`) and walk away.

**Exit trigger:** buy back at **50% of credit collected** (GTC order placed at
fill), else Thursday-close flatten per the Friday branch.

**Max simultaneous core positions: 3** (one per index family).

## Book 2 — Satellite trigger (Matin / Equity Lab family)

**Cadence:** evaluated **after each close** on daily bars; qualifying names are
entered the **next morning 9:45–10:15 ET** (his next-day-OPEN discipline,
shifted past the opening auction).

**Universe:** liquid optionable mega-caps — AAPL MSFT NVDA AMZN META GOOGL
TSLA AVGO COST NFLX AMD JPM. (Chains that actually pass the OI gate.)

**Long trigger — all three on yesterday's completed daily bar:**
1. **EMA3 crossed above EMA8** (cross on that bar, not merely above)
2. **MACD histogram > 0**
3. **Relative volume ≥ 1.5×** its 20-day average *(tightened from Matin's ≥1 per our review)*

**Short trigger:** exact mirror (cross below, histogram < 0, RelVol ≥ 1.5)
→ put debit spread.

**Structure:** debit vertical, 7–21 DTE. Buy the ~35–45Δ strike, sell further
OTM, choosing width so **mid debit ≤ 28% of width** — that is what makes the
**≥ 2.5:1** reward:risk gate pass. If no width achieves it, there is no trade
(that's a logged refusal, not a failure).

**Caps:** ≤ $1,500 max loss per position (debit × 100 × contracts), **max 4
concurrent**, satellite book ≤ $4,000.

**Exit trigger:** sell at **+100% of debit** (GTC), or Thursday-close flatten;
red-Thursday branch may carry ≤ 4% equity into Friday, flat by 10:15 ET.

## Monday morning, concretely (worked sequence)

1. **9:35** — screener pulls SPY/QQQ/IWM snapshots → regime count.
   Satellite signals were already computed from Friday's close (Sun evening run).
2. **9:45–10:15** — any satellite triggers from Friday's bars → nominate debit
   spreads → gates → ledger → orders.
3. **10:00** — regime posture → nominate 2–3 income spreads → gates → ledger
   → mleg orders at mid.
4. **14:30** — regime re-check; top up core if a slot is free and gates pass.
5. **Every fill** → GTC exit order placed immediately (50% credit / 100% debit).
6. **Evening** — daily-bar scan for tomorrow's satellite entries;
   `python3 -m deltax.ledger logs/` summary posted to the team.

## Session-timing rules (execution hygiene, not edge)

Intraday liquidity is U-shaped — deep near the open and close, thin over
lunch. For an agent working multi-leg limit orders at mid, that's a fill-quality
issue, so entries are confined to the deep windows:

| ET window | Rule |
|---|---|
| 9:30–9:45 | **No entries.** Opening auction noise; spreads at their widest |
| 9:45–10:30 | Satellite entry window (morning liquidity) |
| 10:00–10:30 | Core entry window #1 |
| 11:00–14:00 | **No new entries.** Lunch lull — worst mleg fills of the day. Exits (50%-credit / 100%-debit GTCs) remain live |
| 14:30–15:15 | Core entry window #2 + any satellite top-up |
| after 15:15 | **No new entries.** Late-day volatility; overnight gap risk on a fresh position isn't compensated |
| any time | Exit orders always active; flatten routines exempt |

Provenance note: prompted by a session-clock infographic (folklore-grade
source), retained only where it matches the documented U-shaped intraday
volume pattern. The "10:30 reversal" claim and similar are **not** encoded —
timing here is fill-quality hygiene, never a signal.

## Who owns what

| | Elsa | Matin | Agent (deterministic) |
|---|---|---|---|
| Analyzes | Index regime (her filter, her call on ties) | Signal universe & parameters (his family) | — |
| Nominates | Core structures | Satellite structures | — |
| Decides | ✗ | ✗ | **Gates + caps, every time** |
| Records | — | — | Ledger, every evaluation |

Two humans strategize; neither triggers. That's the line all three of us drew
independently, and this document is where it becomes operational.
