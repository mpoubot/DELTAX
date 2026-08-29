"""Daily snapshot tests. Fake feed, no network."""
import sys, os, json, tempfile, shutil
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.daily import run, snapshot_symbol, WATCHLIST

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

TODAY = date(2026, 8, 31)

class FakeFeed:
    def __init__(self, weak=(), thin=(), noopt=()):
        self.weak, self.thin, self.noopt = set(weak), set(thin), set(noopt)
    def snapshots(self, syms):
        s = syms[0]
        price, vwap = (99.0, 100.0) if s in self.weak else (101.0, 100.0)
        return {s: {"latestTrade": {"p": price},
                    "dailyBar": {"c": price, "vw": vwap, "v": 1_000_000, "n": 5000},
                    "prevDailyBar": {"c": 100.0}}}
    def option_contracts(self, sym, **kw):
        if sym in self.noopt: return []
        oi = "10" if sym in self.thin else "5000"
        return [{"symbol": f"{sym}260918P00100000", "expiration_date": "2026-09-18",
                 "open_interest": oi} for _ in range(8)]

print("\n── per-symbol snapshot ──")
r = snapshot_symbol(FakeFeed(weak=["SPY"]), "SPY", TODAY)
check("below_vwap detected", r.below_vwap is True)
check("change_pct computed", r.change_pct == -1.0, str(r.change_pct))
check("expiries in band listed", r.expiries_in_band == ["2026-09-18"])
check("liquid strikes counted", r.liquid_strikes == 8, str(r.liquid_strikes))
check("chain health ok", r.chain_health == "ok")
r2 = snapshot_symbol(FakeFeed(thin=["XYZ"]), "XYZ", TODAY)
check("thin chain flagged", r2.chain_health == "thin" and r2.liquid_strikes == 0)
r3 = snapshot_symbol(FakeFeed(noopt=["ABC"]), "ABC", TODAY)
check("no options -> health none", r3.chain_health == "none")
check("strong symbol not below vwap", snapshot_symbol(FakeFeed(), "QQQ", TODAY).below_vwap is False)

print("\n── daily run ──")
tmp = tempfile.mkdtemp()
try:
    p = run(FakeFeed(weak=["SPY", "QQQ"], thin=["TSLA"]), out_dir=tmp, today=TODAY,
            watchlist=["SPY", "QQQ", "IWM", "TSLA", "PDD"])
    check("regime counts only benchmarks", p["regime"]["weak_count"] == 2, str(p["regime"]))
    check("weak symbols listed", p["regime"]["weak"] == ["SPY", "QQQ"])
    check("thin name excluded from tradeable", "TSLA" not in p["tradeable_universe"])
    check("PDD included", "PDD" in p["tradeable_universe"])
    check("dated file written", os.path.exists(os.path.join(tmp, "2026-08-31.json")))
    saved = json.load(open(os.path.join(tmp, "2026-08-31.json")))
    check("file round-trips", saved["as_of"] == "2026-08-31" and len(saved["symbols"]) == 5)
    check("capture timestamp recorded", "captured_utc" in saved)
finally:
    shutil.rmtree(tmp)

print("\n── watchlist ──")
check("benchmarks present", all(s in WATCHLIST for s in ("SPY", "QQQ", "IWM")))
check("PDD on watchlist", "PDD" in WATCHLIST)
check("no duplicates", len(WATCHLIST) == len(set(WATCHLIST)))

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
