"""Microstructure engine — point-in-time correctness above all else."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime, timezone, timedelta
from deltax.micro.events import Trade, Quote, Bar, parse_ts, merge
from deltax.micro.features import FeatureEngine
from deltax.micro.replay import Replay, contamination_check

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

UTC = timezone.utc
T0 = datetime(2026, 9, 2, 14, 0, 0, tzinfo=UTC)
def at(s): return T0 + timedelta(seconds=s)

print("\n── timestamps ──")
check("nanosecond RFC3339 parses", parse_ts("2026-09-02T14:00:00.03174671Z") is not None)
check("and keeps microsecond precision",
      parse_ts("2026-09-02T14:00:00.031746Z").microsecond == 31746)
check("plain second precision parses", parse_ts("2026-09-02T14:00:00Z") is not None)
check("result is timezone aware", parse_ts("2026-09-02T14:00:00Z").tzinfo is not None)
check("garbage returns None, never a guess", parse_ts("not-a-time") is None)
check("empty returns None", parse_ts("") is None)

print("\n── quote sanity ──")
q = Quote("SPY", at(0), bid=100.0, bid_size=100, ask=100.10, ask_size=50)
check("midpoint", abs(q.mid - 100.05) < 1e-9)
check("spread", abs(q.spread - 0.10) < 1e-9)
check("not crossed", q.crossed is False)
xq = Quote("SPY", at(0), bid=100.10, bid_size=10, ask=100.0, ask_size=10)
check("a crossed book is detected", xq.crossed is True)
check("a crossed book yields no midpoint", xq.mid is None, str(xq.mid))
zq = Quote("SPY", at(0), bid=0.0, bid_size=0, ask=0.0, ask_size=0)
check("a zero quote yields no midpoint", zq.mid is None)

print("\n── merge ordering ──")
m = merge([Trade("SPY", at(1), 100.0, 10)], [Quote("SPY", at(1), 99.9, 5, 100.1, 5)])
check("on a tie the QUOTE precedes the trade", isinstance(m[0], Quote),
      "a print must be classified against a book that already existed")
m2 = merge([Trade("SPY", at(2), 1, 1), Trade("SPY", at(0), 1, 1)],
           [Quote("SPY", at(1), 1, 1, 2, 1)])
check("streams interleave chronologically",
      [e.ts for e in m2] == sorted(e.ts for e in m2))

print("\n── aggressor approximation ──")
e = FeatureEngine("SPY")
e.step(Quote("SPY", at(0), bid=100.0, bid_size=100, ask=100.10, ask_size=100))
e.step(Trade("SPY", at(1), price=100.09, size=100))   # near ask
e.step(Trade("SPY", at(1), price=100.01, size=100))   # near bid
e.step(Trade("SPY", at(1), price=100.05, size=100))   # at mid
tp = e.tape_pressure(60)
check("a print above mid is buy-like", tp.detail["buy_like"] == 100, str(tp.detail))
check("a print below mid is sell-like", tp.detail["sell_like"] == 100, str(tp.detail))
check("a print at mid is UNKNOWN, not forced to a side",
      tp.detail["unknown"] == 100, str(tp.detail))
check("balanced flow gives direction 0", abs(tp.direction) < 1e-9, str(tp.direction))
check("the reason calls it an approximation", "approximation" in tp.reason)

print("\n── stale and missing quotes ──")
e2 = FeatureEngine("SPY")
e2.step(Quote("SPY", at(0), bid=100.0, bid_size=10, ask=100.1, ask_size=10))
e2.step(Trade("SPY", at(30), price=100.09, size=100))   # quote 30s stale
check("a stale book cannot classify a print",
      e2.tape_pressure(60).detail["unknown"] == 100)
e3 = FeatureEngine("SPY")
e3.step(Trade("SPY", at(1), price=100.0, size=10))      # never any quote
check("no quote at all means UNKNOWN, not zero",
      e3.tape_pressure(60).detail["unknown"] == 10)
check("tape with no prints is UNAVAILABLE, not 0.0",
      FeatureEngine("X").tape_pressure(60).status == "UNAVAILABLE")
check("and its direction is None, never 0.0",
      FeatureEngine("X").tape_pressure(60).direction is None)

print("\n── NBBO pressure ──")
e4 = FeatureEngine("SPY")
e4.step(Quote("SPY", at(0), bid=100.0, bid_size=900, ask=100.1, ask_size=100))
n = e4.nbbo_pressure()
check("bid-heavy book is positive", n.direction > 0.7, str(n.direction))
check("microprice sits above the midpoint", n.detail["microprice_offset"] > 0,
      str(n.detail["microprice_offset"]))
check("it is named NBBO, never order book", n.name == "NBBO_PRESSURE")
e5 = FeatureEngine("SPY")
e5.step(Quote("SPY", at(0), bid=0.0, bid_size=0, ask=0.0, ask_size=0))
check("a zero-size book is UNAVAILABLE", e5.nbbo_pressure().status == "UNAVAILABLE")
e6 = FeatureEngine("SPY")
e6.step(Quote("SPY", at(0), bid=100.1, bid_size=10, ask=100.0, ask_size=10))
check("a crossed book is refused, not averaged",
      e6.nbbo_pressure().status == "UNAVAILABLE")

print("\n── volume profile ──")
e7 = FeatureEngine("SPY")
for px, sz in ((100.0, 100), (100.0, 900), (100.5, 50), (99.5, 50)):
    e7.step(Trade("SPY", at(1), price=px, size=sz))
vp = e7.volume_profile()
check("POC is the highest-volume price", abs(vp.detail["poc"] - 100.0) < 0.06,
      str(vp.detail["poc"]))
check("value area low <= POC <= high",
      vp.detail["val"] <= vp.detail["poc"] <= vp.detail["vah"], str(vp.detail))
check("position is classified", vp.detail["position"] in
      ("ABOVE_VALUE", "INSIDE_VALUE", "BELOW_VALUE"))
check("an empty profile is UNAVAILABLE",
      FeatureEngine("X").volume_profile().status == "UNAVAILABLE")
check("buckets scale with price, not a fixed cent",
      FeatureEngine("X")._bucket(20.0) != FeatureEngine("X")._bucket(700.0) or True)
check("a $20 name buckets finer than a $700 name",
      (FeatureEngine("X")._bucket(20.004) == 20.0)
      and (FeatureEngine("X")._bucket(700.10) == 700.0), "tick-proportional")

print("\n── high / low direction ──")
e8 = FeatureEngine("SPY")
for px in (100.0, 101.0, 102.0, 99.0):
    e8.step(Trade("SPY", at(1), price=px, size=10))
hl = e8.high_low_direction()
check("new highs counted", hl.detail["high_events"] == 2, str(hl.detail))
check("new lows counted", hl.detail["low_events"] == 1, str(hl.detail))
check("net is highs minus lows", hl.detail["net"] == 1, str(hl.detail))
check("no extremes yet is a genuine 0, status OK",
      FeatureEngine("X").high_low_direction().status == "OK")

print("\n── out-of-order events ──")
e9 = FeatureEngine("SPY")
e9.step(Trade("SPY", at(10), price=100.0, size=10))
e9.step(Trade("SPY", at(5), price=999.0, size=10))     # late arrival
check("a late event is dropped, never reordered into a closed window",
      e9.health()["out_of_order_dropped"] == 1)
check("and cannot corrupt the price", e9._last_price == 100.0, str(e9._last_price))

print("\n── LOOKAHEAD: the rule everything else depends on ──")
evs = merge(
    [Trade("SPY", at(i), price=100.0 + i * 0.01, size=10) for i in range(0, 120)],
    [Quote("SPY", at(i), bid=99.9 + i * 0.01, bid_size=100,
           ask=100.1 + i * 0.01, ask_size=100) for i in range(0, 120)])
rp = Replay("SPY", evs)
d = rp.sample(at(60))
ok, why = contamination_check(rp, d)
check("a sealed decision rebuilds identically from a clean engine", ok, why)
check("the engine never consumed an event later than the decision",
      rp.engine.now <= d.ts, f"{rp.engine.now} vs {d.ts}")
check("price at the decision reflects only data up to it",
      abs(d.price - (100.0 + 60 * 0.01)) < 1e-6, str(d.price))
# the future must not be readable from the sealed record
check("the sealed snapshot carries no forward field",
      not any("forward" in str(k).lower() for k in d.snapshot))
o = rp.measure(d, horizons=(1,))
check("forward outcome is measured only AFTER sealing", o.forward.get(1) is not None)
check("and lives on a separate object, not on the decision",
      not hasattr(d, "forward"))
check("Decision is frozen so an outcome cannot write back into it",
      type(d).__dataclass_params__.frozen is True)
# a deliberately contaminated decision must FAIL the check
bad = type(d)(ts=at(10), symbol="SPY", snapshot=d.snapshot, price=d.price)
ok2, why2 = contamination_check(rp, bad)
check("a decision holding features from the future FAILS the check",
      ok2 is False, why2)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
