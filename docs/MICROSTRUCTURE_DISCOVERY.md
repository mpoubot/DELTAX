# Microstructure discovery — Phase 0

Probed live against both providers on 2026-09-02. No endpoint names guessed:
every row below is an actual HTTP response from this account's credentials.

---

## Headline finding: the spec's data assumption is inverted

The build order assumes **Massive** supplies trades, quotes/NBBO, most-active,
and options flow. **It does not.** This account is entitled to aggregates,
reference data and news only. Every microstructure endpoint returns
`403 You are not entitled to this data`.

**Alpaca supplies all of it instead**, and is already wired into the repo.
The intelligence layer is therefore built on Alpaca market data, with Massive
retained for what it does serve.

---

## Massive — measured entitlements

| Endpoint | Status | Usable for |
|---|---|---|
| `/v2/aggs/ticker/{t}/range/1/day/...` | **200** | daily bars, realized vol |
| `/v2/aggs/ticker/{t}/range/1/minute/...` | **200** (869 bars/session) | volume profile, high/low, breadth |
| `/v3/reference/options/contracts` | **200** | contract reference |
| `/v1/marketstatus/now` | **200** | session state |
| `/v2/reference/news` | **200** | catalyst evidence |
| `/v3/trades/{t}` | **403** | — time & sales UNAVAILABLE |
| `/v3/quotes/{t}` | **403** | — NBBO UNAVAILABLE |
| `/v2/last/trade`, `/v2/last/nbbo` | **403** | — UNAVAILABLE |
| `/v2/snapshot/.../tickers` | **403** | — UNAVAILABLE |
| `/v2/snapshot/.../gainers` | **403** | — most-active UNAVAILABLE |
| `/v3/snapshot/options/{u}` | **403** | — option chain UNAVAILABLE |
| `/v3/trades/O:...`, `/v3/quotes/O:...` | **403** | — options flow UNAVAILABLE |

## Alpaca — measured entitlements

| Command | Status | Fields returned |
|---|---|---|
| `data trades` | **200** | `p` price, `s` size, `t` ns-timestamp, `x` exchange, `c` conditions, `i` id, `z` tape |
| `data quotes` | **200** | `bp/bs/bx` bid, `ap/as/ax` ask, `t`, `c`, `z` — **real NBBO** |
| `data latest-quote` / `latest-trade` | **200** | current top-of-book |
| `data multi-snapshots` | **200** | latestQuote + latestTrade + dailyBar + minuteBar |
| `data screener most-actives` | **200** | most-active ranking |
| `data screener movers` | **200** | top movers |
| `data option` | **200** | option chain, greeks, quotes, open interest |
| `data meta` | **200** | exchange + condition reference (for aggressor rules) |

---

## What this means module by module

| Spec module | Verdict | Source |
|---|---|---|
| 1 Time & Sales | **BUILDABLE** | Alpaca `data trades` |
| 2 Volume Profile | **BUILDABLE** | Massive minute aggs or Alpaca bars |
| 3 NBBO Pressure | **BUILDABLE — top-of-book only** | Alpaca `data quotes` |
| 4 High/Low Direction | **BUILDABLE** | minute aggregates |
| 5 Market Breadth | **BUILDABLE — partial universe** | multi-bars across the tracked list |
| 6 Most Active | **BUILDABLE** | Alpaca `screener` |
| 7 Options Flow | **PARTIAL** | Alpaca option chain + OI. No OPRA time & sales on either provider, so *flow* is inferred from chain state, never from executions |
| 8 Vol / Liquidity | **BUILDABLE** | option chain IV + realized vol |

**Depth of book is UNAVAILABLE from both providers.** Per the spec's own
instruction the feature is named `NBBO_PRESSURE`, never order-book pressure.

**True options flow is UNAVAILABLE.** No option prints are entitled anywhere, so
nothing in this system may claim to observe option executions. Chain-derived
measures are labelled as such.

---

## Existing DELTAX state — preserved

- **Risk gates: 15, not 17.** The spec says 17 throughout; `evaluate()` emits 15
  (14 plus E101 variance premium). The dashboard carried the same wrong count
  until today. Corrected here rather than propagated.
- **Entry freeze: ACTIVE mechanism**, driven by `state/freeze.json` and eight
  signals re-evaluated every 15 minutes. Not modified.
- **Risk-reducing orders always permitted** — `execute.submit()` exempts
  `close=True` from every stand-down. Verified by mutation test.
- 789 tests passing before this work began.

---

## Architecture consequence

Because the spec requires **identical code in live and replay**, the engine is
event-sourced: both modes emit the same canonical events into the same feature
engine. Live reads the tail of the Alpaca stream; replay reads a historical
window. Neither path has a separate "simplified" implementation, so a feature
cannot behave differently in research than in production.

Point-in-time correctness is enforced structurally rather than by convention:
the feature engine only ever sees events it has been fed, in timestamp order,
and cannot address future ones.
