# Overnight microstructure build — report

Built 2026-09-02 evening. **838 tests passing, 0 failing.**

---

## The finding that reshaped the build

The specification assumes **Massive** supplies trades, quotes/NBBO, most-active
and options flow. Probed directly with this account's credentials, it does not:
every microstructure endpoint returns `403 You are not entitled to this data`.

**Alpaca supplies all of it**, and was already in the repo. The engine is built
on Alpaca market data; Massive is retained for aggregates, option reference and
news. Full evidence in `docs/MICROSTRUCTURE_DISCOVERY.md`.

---

## What was built

| File | What it is |
|---|---|
| `deltax/micro/events.py` | Canonical `Trade` / `Quote` / `Bar`, nanosecond timestamp parsing, paginated Alpaca adapters, chronological merge |
| `deltax/micro/features.py` | The shared feature engine — tape pressure, NBBO pressure, volume profile, high/low direction |
| `deltax/micro/replay.py` | Chronological replay, sealed decisions, forward-outcome measurement, contamination checker |
| `tests/test_micro.py` | 48 tests, 16 of them on lookahead alone |
| `docs/MICROSTRUCTURE_DISCOVERY.md` | Phase 0 entitlement evidence |

**One engine, both modes.** Live and replay feed the same `FeatureEngine` the
same canonical events. There is no research variant, so a signal measured in
replay is measured by production code — the property the whole design exists for.

---

## Point-in-time correctness

Structural, not conventional. The engine is fed one event at a time and holds no
index, no future window, and no reference to the source stream. There is no
mechanism by which a feature *could* read ahead.

`contamination_check()` proves it per decision: it rebuilds the snapshot from a
fresh engine fed only events at or before the decision timestamp, and any
difference is a failure. A deliberately contaminated decision is asserted to
fail — a check that cannot fail proves nothing.

`Decision` is a frozen dataclass and outcomes attach to a separate `Outcome`,
so a forward return cannot write back into the features that produced it.

---

## Verified on real market data

SPY, 2 Sep 14:00–14:05 UTC: **7,074 trades and 61,001 quotes**, fully paginated.

```
14:01:00  px 763.30   tape -0.194 (rel 0.70)   nbbo +0.689   ABOVE_VALUE  POC 763.00
14:02:00  px 763.38   tape +0.080 (rel 0.70)   nbbo -0.956   INSIDE_VALUE POC 763.50
14:03:00  px 763.45   tape +0.002 (rel 0.75)   nbbo -0.529   INSIDE_VALUE POC 763.25
14:04:00  px 763.34   tape -0.134 (rel 0.73)   nbbo +0.161   INSIDE_VALUE POC 763.25
LOOKAHEAD: PASS — every decision rebuilds identically
```

---

## Failures found and fixed

**Pagination was not optional.** The first run looked fine and was wrong: 8,000
quotes covered **42 seconds** of SPY, not the 20 minutes requested. Every print
after that classified UNKNOWN because no fresh book existed. A feature that
looks present and is wrong is worse than one that is absent. Paged.

**Tests depended on live operational state.** `test_execute.py` crashed because
the freeze state had gone stale at 479 minutes — correct fail-safe behaviour
outside market hours, but a test of order mechanics must not read today's
posture. Both freeze inputs are now redirected and restored.

---

## What NOT to trust yet

Read this section before using any of it.

- **No signal here has been validated as predictive.** The engine measures and
  seals correctly. Whether tape pressure or NBBO pressure predicts anything is
  an open question, and four sealed decisions is not a sample.
- **NBBO pressure is volatile and thin.** It swung +0.689 → −0.956 → −0.529
  within three minutes. Top-of-book size is easily transient; the persistence
  scoring the spec asks for is **not implemented**, so treat single readings as
  noise.
- **The aggressor rule is an approximation, and 25–30% of prints are
  unclassified.** A print above the midpoint is buy-*like*. It may be a seller
  crossing the spread, a spread leg, or a hedge.
- **Options flow does not exist.** Neither provider entitles OPRA prints on this
  account. Nothing in the system observes option executions, and nothing claims
  to.
- **Depth of book does not exist.** Top-of-book only, which is why the feature
  is named `NBBO_PRESSURE`.
- **Breadth, most-active, regime, confluence and historical analogs are NOT
  built.** They are specified and unimplemented. The dashboard shows nothing
  about them because there is nothing truthful to show.

---

## Not built, and why

The specification is several weeks of engineering. With the market opening in
hours and judging on Friday, I built the foundation the rest depends on —
data integrity and point-in-time correctness, which the spec itself ranks first
and second — rather than a broad surface of unvalidated signals.

Not built: regime engine, confluence engine, historical analog search, signal
decay tracking, regime-specific edge, most-active, breadth, options flow,
replay UI controls, chart annotations, the workstation layout, the AI reasoning
layer, and the storage schema.

**Nothing was faked to appear complete.** No fabricated confidence, no invented
endpoint, no signal presented as validated.

---

## Risk architecture — untouched

- 15 gates (**not 17**; the spec says 17 throughout, `evaluate()` emits 15). Not
  modified.
- Entry freeze intact and currently **FROZEN** on staleness — the fail-safe.
- Risk-reducing exits always permitted; verified by mutation test.
- The microstructure layer produces **evidence only**. It cannot authorise a
  trade and is not wired into the order path.

---

## Next three, ranked by engineering value

1. **Validate one signal.** Replay several sessions, seal decisions, measure
   forward returns, and find out whether tape pressure predicts anything. Until
   this exists the engine is instrumentation, not edge.
2. **Quote persistence scoring.** NBBO pressure is currently unusable on single
   readings; persistence is what separates a real imbalance from a flicker.
3. **Storage.** Sealed decisions and outcomes are in memory only. Persisting
   them is what lets tomorrow learn from tonight.

---

## Second build — behaviour, inventory and regime nesting

Added after the microstructure foundation. **875 tests passing.**

| File | What it is |
|---|---|
| `deltax/micro/inventory.py` | Multi-timeframe volume profile (5D→2Y), cross-horizon clustering, participant hypotheses |
| `deltax/micro/regime.py` | Regime nesting — waves inside waves |
| `tests/test_behavior.py` | 37 tests, most of them asserting the system stays honest |

### Regime nesting, live on SPY

```
2Y   TREND_UP         +38.6%   1.7 sigma of its own volatility
1Y   TREND_UP         +18.9%   1.5 sigma
3M   VOL_COMPRESSION           recent vol 0.58x the horizon's own
20D  RANGE            -0.44%   inside 0.5 sigma
5D   DRIFT_DOWN       -0.77%

"5d drift down inside 20D range inside 3M vol compression
 inside 1Y trend up inside 2Y trend up."

alignment 0.333 -> confidence 0.333
```

Nothing is collapsed to one label. **Confidence falls when horizons disagree** —
that is asserted by test, because a system that grows more certain as its
evidence conflicts is worse than useless.

Each horizon is measured against **its own** realised volatility, so a 2% move
means something different over five days than over a year.

### Inventory, live on SPY at 765.20

```
762.25-766.75   strength 19.2   confirmed by 5D, 10D, 20D   <- price is INSIDE
683.00          strength 13.4   confirmed by 1Y, 2Y
657.25          strength  4.0   confirmed by 6M
```

All seven horizons available. A level confirmed by the 1Y and 2Y profiles is
weighted far above one made this week, because it represents business done by
participants who may still be there.

### The honesty constraint, enforced by test

Nothing in public market data reveals whether historical volume opened longs or
shorts. So every participant read returns **possibility levels — HIGH,
MEDIUM-HIGH, MEDIUM — never probabilities**, and every one carries the caveat
that the underlying fact is not observable. A test asserts the values are
strings rather than numbers: a number there would fabricate precision that does
not exist.

With price inside the strongest zone the model refuses to pick a side and says
so: `positioning_mixed: HIGH`, plus what a move in either direction would force.

### Known approximation, stated rather than hidden

Long-horizon profiles place each daily bar's volume at its VWAP. A wide-range
day genuinely spread its volume across the range; this concentrates it. The
effect is to make inventory zones look **narrower** than they are. Documented in
the module.

### Still not built

Crowd expectation, expectation/reality gap, regime-shift detection, alpha decay,
GEX, options flow, breadth, most-active, historical analogs, scenario graphs,
dashboard integration. The spec is weeks of work; this is items 1, 2, 3 and 9 of
its own priority list, which is what the market opening in hours allows.

**No signal here is validated as predictive.** The engine measures and nests
correctly. Whether inventory position or regime nesting forecasts anything is
untested, and four horizons agreeing is not evidence.
