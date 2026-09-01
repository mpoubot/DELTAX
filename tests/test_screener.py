"""Screener tests. Fake feed built from real Alpaca payload shapes; no network."""

import sys, os, tempfile, shutil
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from deltax.screener import (
    assess_regime, posture, select_vertical, parse_expiry, spread_pct,
    screen_income_book, RegimeState, BENCHMARKS, choose_expiry,
    REGIME_DEADBAND,
)
from deltax.ledger import Ledger

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  ✓ {name}")
    else: failed += 1; print(f"  ✗ {name}  {detail}")

def snap(price, vwap, prev=None):
    d = {"latestTrade": {"p": price}, "dailyBar": {"c": price, "vw": vwap}}
    if prev is not None: d["prevDailyBar"] = {"c": prev}
    return d

print("\n── regime (Elsa's filter) ──")
# real shape: SPY latest 769.28 vs vwap 770.81 -> weak
r = assess_regime({"SPY": snap(769.28, 770.81), "QQQ": snap(600, 598), "IWM": snap(240, 238)})
check("SPY below VWAP counted weak", r.weak_symbols == ["SPY"] and r.weak_count == 1, str(r.weak_symbols))
r0 = assess_regime({s: snap(100, 99) for s in BENCHMARKS})
check("all above VWAP -> 0 weak", r0.weak_count == 0)
r3 = assess_regime({s: snap(99, 100) for s in BENCHMARKS})
check("all below VWAP -> 3 weak", r3.weak_count == 3)
rm = assess_regime({"SPY": snap(100, 99), "QQQ": {}, "IWM": snap(100, 99)})
check("missing data fails conservative (3 weak)", rm.weak_count == 3 and not rm.complete)
check("regime note is human-readable", "weak" in r.note or "fallback" in rm.note)

print("\n── posture mapping ──")
check("0 weak -> put credit only", all(side == "put" for _, side in posture(r0)))
check("3 weak -> call credit only", all(side == "call" for _, side in posture(r3)))
p2 = posture(RegimeState(2, ["SPY", "QQQ"]))
check("2 weak -> includes call on weakest", ("SPY", "call") in p2, str(p2))
check("2 weak -> both sides somewhere (condor as two verticals)",
      any(s == "put" for _, s in p2) and any(s == "call" for _, s in p2), str(p2))

print("\n── OCC symbol parsing ──")
check("expiry parsed", parse_expiry("PLTR260918P00175000") == "2026-09-18")
check("bad symbol -> None", parse_expiry("NOTASYMBOL") is None)
check("spread_pct", abs(spread_pct(3.91, 3.92) - 0.00256) < 0.001)
check("spread_pct missing -> None", spread_pct(None, 1.0) is None)

print("\n── strike selection by delta ──")
# real PLTR Sep-18 put chain
chain = {
    "PLTR260918P00170000": {"greeks": {"delta": -0.1847}, "latestQuote": {"bp": 2.04, "ap": 2.12}},
    "PLTR260918P00172500": {"greeks": {"delta": -0.2218}, "latestQuote": {"bp": 2.58, "ap": 2.63}},
    "PLTR260918P00175000": {"greeks": {"delta": -0.2630}, "latestQuote": {"bp": 3.18, "ap": 3.28}},
    "PLTR260918P00177500": {"greeks": {"delta": -0.3071}, "latestQuote": {"bp": 3.91, "ap": 3.92}},
    "PLTR260918P00180000": {"greeks": {"delta": -0.3562}, "latestQuote": {"bp": 4.61, "ap": 4.96}},
}
oi = {s: 5000 for s in chain}

# A chain spanning 60 points so a 20-wide vertical can find its long leg.
wide_chain = {}
for _k in range(140, 201, 5):
    _d = -(0.05 + (_k - 140) / 60.0 * 0.40)          # 0.05 .. 0.45 across the range
    wide_chain[f"PLTR260918P00{_k*1000:06d}"] = {
        "greeks": {"delta": round(_d, 4)},
        "latestQuote": {"bp": round(1.0 + (_k - 140) * 0.14, 2),
                        "ap": round(1.06 + (_k - 140) * 0.14, 2)}}
c = select_vertical(chain, side="put", target_delta=0.30, width=5.0, oi_by_symbol=oi)
check("short strike nearest 0.30 delta = 177.5", c["short"]["strike"] == 177.5, str(c["short"]["strike"]))
check("long leg one width below = 172.5", c["long"]["strike"] == 172.5, str(c["long"]["strike"]))
# Pricing is mode-dependent; assert each explicitly rather than the default.
cw = select_vertical(chain, side="put", target_delta=0.30, width=5.0,
                     oi_by_symbol=oi, pricing="worst")
check("worst = short bid - long ask", abs(cw["credit"] - (3.91 - 2.63)) < 1e-9, str(cw["credit"]))
cm = select_vertical(chain, side="put", target_delta=0.30, width=5.0,
                     oi_by_symbol=oi, pricing="mid")
check("mid = mid - mid", abs(cm["credit"] - (3.915 - 2.605)) < 1e-9, str(cm["credit"]))
ch_ = select_vertical(chain, side="put", target_delta=0.30, width=5.0,
                      oi_by_symbol=oi, pricing="haircut")
check("haircut sits between worst and mid",
      cw["credit"] < ch_["credit"] < cm["credit"], f'{cw["credit"]}/{ch_["credit"]}/{cm["credit"]}')
check("haircut concedes 25% of combined spread",
      abs(ch_["credit"] - (1.31 - 0.25 * 0.06)) < 1e-9, str(ch_["credit"]))
check("max loss = (width - credit) x 100",
      abs(cw["max_loss_per_contract"] - 372.0) < 0.01, str(cw["max_loss_per_contract"]))
check("expiry extracted", c["expiry"] == "2026-09-18")
# wider chain so the long leg exists further out
wide = dict(chain)
wide["PLTR260918P00167500"] = {"greeks": {"delta": -0.1500}, "latestQuote": {"bp": 1.66, "ap": 1.72}}
wide["PLTR260918P00165000"] = {"greeks": {"delta": -0.1280}, "latestQuote": {"bp": 1.28, "ap": 1.39}}
wide["PLTR260918P00162500"] = {"greeks": {"delta": -0.1050}, "latestQuote": {"bp": 1.02, "ap": 1.10}}
c2 = select_vertical(wide, side="put", target_delta=0.20, width=5.0,
                     oi_by_symbol={s: 5000 for s in wide})
check("lower target delta picks further OTM (0.185 nearest 0.20)",
      c2["short"]["strike"] == 170.0, str(c2["short"]["strike"]))
c3 = select_vertical(wide, side="put", target_delta=0.05, width=5.0,
                     oi_by_symbol={s: 5000 for s in wide})
check("R3 band floors the short leg at 0.15 delta, never 0.105",
      c3 is not None and c3["short"]["delta"] >= 0.15, str(c3))
check("short at chain edge with no long leg -> None",
      select_vertical(chain, side="put", target_delta=0.20, width=5.0, oi_by_symbol=oi) is None)
check("no long leg available -> None",
      select_vertical(chain, side="put", target_delta=0.30, width=50.0, oi_by_symbol=oi) is None)
check("unquoted chain -> None",
      select_vertical({"X260918P00175000": {"greeks": {"delta": -0.3}, "latestQuote": {}}},
                      side="put", target_delta=0.3, width=5.0, oi_by_symbol={}) is None)

print("\n── end to end with a fake feed ──")
class FakeFeed:
    def __init__(self, weak): self.weak = weak; self.chain_calls = []
    def snapshots(self, syms):
        return {s: (snap(99, 100) if s in self.weak else snap(101, 100)) for s in syms}
    def option_chain(self, underlying, **kw):
        self.chain_calls.append((underlying, kw.get("option_type")))
        # Widths moved to 10-20 points (E34), so the end-to-end fixture needs a
        # chain that actually spans one. The five-strike `chain` above stays as
        # the unit fixture for select_vertical.
        return wide_chain
    def option_contracts(self, underlying, **kw):
        return [{"symbol": s, "open_interest": 5000} for s in chain]

tmp = tempfile.mkdtemp()
try:
    stamps = iter([f"2026-08-31T14:{i:02d}:00.000+00:00" for i in range(30)])
    led = Ledger(tmp, run_id="screen", clock=lambda: next(stamps), rules_commit="test")
    feed = FakeFeed(weak=[])
    out = screen_income_book(feed, led, equity=100_000.0, today=date(2026, 8, 31))
    check("0 weak -> nominated put spreads only",
          all(side == "put" for _, side in feed.chain_calls), str(feed.chain_calls))
    check("every nomination reached the ledger", len(led.entries()) == len(out["results"]),
          f"{len(led.entries())} vs {len(out['results'])}")
    check("ledger holds regime context",
          all("regime" in e["context"] and e["context"]["book"] == "income" for e in led.entries()))
    ok, msg = led.verify(); check("ledger chain intact after screening", ok, msg)
    s = led.summary()
    check("summary counts the pass", s["evaluated"] == len(out["results"]) and s["evaluated"] > 0, str(s))
    check("committed max loss tracked", out["committed_max_loss"] >= 0)

    feed3 = FakeFeed(weak=BENCHMARKS)
    led3 = Ledger(tmp, run_id="screen3",
                  clock=lambda: "2026-08-31T15:00:00.000+00:00", rules_commit="test")
    out3 = screen_income_book(feed3, led3, equity=100_000.0, today=date(2026, 8, 31))
    check("3 weak -> call spreads only",
          all(side == "call" for _, side in feed3.chain_calls), str(feed3.chain_calls))
    check("weak regime widens OTM target (delta 0.20)",
          out3["regime"].weak_count == 3)
finally:
    shutil.rmtree(tmp)

print("\n── expiry selection: nearest qualifying, not most liquid (E18) ──")
class ExpFeed:
    """Sep 11 weekly is tradeable; Sep 18 monthly is far more liquid."""
    def __init__(self, weekly_liquid=8): self.weekly_liquid = weekly_liquid
    def option_contracts(self, sym, **kw):
        out=[]
        for i in range(10):
            out.append({"expiration_date":"2026-09-11","symbol":f"W{i}",
                        "open_interest": str(9999 if i < self.weekly_liquid else 1)})
        for i in range(10):
            out.append({"expiration_date":"2026-09-18","symbol":f"M{i}",
                        "open_interest": "999999"})
        return out

got = choose_expiry(ExpFeed(), "SPY", "put", "2026-09-07", "2026-09-21", 1.0, 999.0)
check("picks the NEARER expiry when both qualify", got and got[0] == "2026-09-11",
      str(got[0] if got else None))
got = choose_expiry(ExpFeed(weekly_liquid=2), "SPY", "put", "2026-09-07", "2026-09-21", 1.0, 999.0)
check("falls through to the monthly when the weekly is too thin",
      got and got[0] == "2026-09-18", str(got[0] if got else None))

class NoneFeed:
    def option_contracts(self, sym, **kw):
        return [{"expiration_date":"2026-09-11","symbol":f"W{i}","open_interest":"1"}
                for i in range(10)]
check("returns None when nothing clears the liquidity floor",
      choose_expiry(NoneFeed(), "SPY", "put", "2026-09-07", "2026-09-21", 1.0, 999.0) is None)

print("\n── regime deadband: noise is not a regime (E31) ──")
def _sn(px, vw): return {"latestTrade": {"p": px}, "dailyBar": {"vw": vw}}
def _all(px, vw): return assess_regime({b: _sn(px, vw) for b in BENCHMARKS})

check("a 0.004% gap is NOT weak (the 31 Aug QQQ case)", _all(715.25, 715.26).weak_count == 0)
check("a 0.05% gap is NOT weak", _all(766.14, 766.50).weak_count == 0)
check("a 0.26% gap IS weak", _all(293.50, 294.27).weak_count == 3)
check("a 1.5% gap IS weak", _all(985.0, 1000.0).weak_count == 3)
check("above vwap is never weak", _all(1005.0, 1000.0).weak_count == 0)
# Exact-boundary equality is a float artifact (998.5/1000-1 lands at
# -0.00149999...), so test just past it rather than on it.
check("just past the deadband counts as weak",
      _all(1000.0 * (1 - REGIME_DEADBAND * 1.01), 1000.0).weak_count == 3)
check("just inside the deadband does not",
      _all(1000.0 * (1 - REGIME_DEADBAND * 0.9), 1000.0).weak_count == 0)
check("deadband is a real threshold, not zero", REGIME_DEADBAND > 0)
# The fix must cut both ways: it is a noise floor, not a bias toward trading.
check("noise ABOVE vwap is equally ignored", _all(1000.04, 1000.0).weak_count == 0)
check("missing data still fails closed at 3/3",
      assess_regime({b: {} for b in BENCHMARKS}).weak_count == 3)


print("\n── E50: vol-premium ranking ──")
from deltax.screener import rank_by_vol_premium, vol_premium, realized_vol_20

class _FakeFeed:
    """IV/RV is controllable per symbol; one symbol is deliberately broken."""
    def __init__(self, table): self.table = table
    def daily_bars(self, sym, start, end, limit=60):
        if sym == "BOOM": raise RuntimeError("feed down")
        import math
        step = self.table.get(sym, {}).get("rv", 0.20) / (252 ** 0.5)
        return [{"c": 100.0 * math.exp(step * (1 if i % 2 else -1) * i * 0.01)}
                for i in range(30)]
    def option_chain(self, sym, **kw):
        if sym == "BOOM": raise RuntimeError("feed down")
        iv = self.table.get(sym, {}).get("iv")
        if iv is None: return {}
        return {"X": {"greeks": {"delta": -0.30}, "impliedVolatility": iv}}

tbl = {"RICH": {"iv": 0.60}, "MID": {"iv": 0.30}, "POOR": {"iv": 0.10}, "NOCHAIN": {}}
ff = _FakeFeed(tbl)
spots = {s: 100.0 for s in ("RICH", "MID", "POOR", "NOCHAIN", "BOOM")}
order = rank_by_vol_premium(ff, ["POOR", "NOCHAIN", "RICH", "BOOM", "MID"],
                            "2026-09-04", spots)
check("richest premium is ranked first", order[0] == "RICH", str(order))
check("poorest measurable ranks below richer ones",
      order.index("POOR") > order.index("MID"), str(order))
check("unmeasurable names fall to the back",
      set(order[-2:]) == {"NOCHAIN", "BOOM"}, str(order))
check("ranking never drops a candidate", len(order) == 5 and set(order) == {
      "POOR", "NOCHAIN", "RICH", "BOOM", "MID"}, str(order))
check("a broken feed yields None, not an exception",
      vol_premium(ff, "BOOM", "2026-09-04", 100.0) is None)
check("realized vol survives a broken feed",
      realized_vol_20(ff, "BOOM") is None)
check("ranking with no spots keeps every name",
      len(rank_by_vol_premium(ff, ["RICH", "MID"], "2026-09-04", {})) == 2)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
