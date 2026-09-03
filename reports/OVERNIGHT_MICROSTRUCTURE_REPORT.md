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
