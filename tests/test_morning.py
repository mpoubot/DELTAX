"""Morning brief tests. Fake feed, earnings check disabled (network)."""
import sys, os, tempfile
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.morning import brief, render, SATELLITE
from deltax.screener import BENCHMARKS, TARGET_DELTA_BY_WEAK

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

class FakeFeed:
    def __init__(self, weak=(), is_open=False):
        self.weak, self._open = set(weak), is_open
    def clock(self):
        return {"is_open": self._open, "next_open": "2026-08-31T09:30:00-04:00"}
    def snapshots(self, syms):
        out = {}
        for s in syms:
            p, v = (99.0, 100.0) if s in self.weak else (101.0, 100.0)
            out[s] = {"latestTrade": {"p": p},
                      "dailyBar": {"c": p, "vw": v, "v": 1_000_000, "n": 5000},
                      "prevDailyBar": {"c": 100.0}}
        return out
    def option_contracts(self, sym, **kw):
        return [{"symbol": f"{sym}260918P00100000",
                 "expiration_date": "2026-09-18", "open_interest": "5000"}
                for _ in range(8)]

cwd = os.getcwd()
tmp = tempfile.mkdtemp(); os.chdir(tmp); os.makedirs("data", exist_ok=True)
try:
    print("\n── closed market ──")
    b = brief(FakeFeed(weak=["SPY"]), today=date(2026,8,29), check_earnings=False)
    check("market reported closed", b["market_open"] is False)
    check("entries blocked when closed", b["entry_allowed"] is False)
    check("reason names the cause", "closed" in b["window"], b["window"])
    check("next_open surfaced", b["next_open"].startswith("2026-08-31"))

    print("\n── regime ──")
    check("1 weak benchmark detected", b["regime"]["weak_count"] == 1)
    check("weak symbol named", b["regime"]["weak"] == ["SPY"])
    check("target delta comes from the backtested table",
          b["regime"]["target_short_delta"] == TARGET_DELTA_BY_WEAK[1],
          str(b["regime"]["target_short_delta"]))
    check("posture present", len(b["regime"]["posture"]) > 0)
    b3 = brief(FakeFeed(weak=BENCHMARKS), today=date(2026,8,29), check_earnings=False)
    check("3 weak -> delta 0.25", b3["regime"]["target_short_delta"] == 0.25)
    check("all targets sit in the walk-forward validated 0.25-0.30 band",
          all(0.25 <= v <= 0.30 for v in TARGET_DELTA_BY_WEAK.values()),
          str(TARGET_DELTA_BY_WEAK))
    check("3 weak -> calls only", all("call" in p for p in b3["regime"]["posture"]),
          str(b3["regime"]["posture"]))

    print("\n── universe ──")
    check("tradeable populated", len(b["universe"]["tradeable"]) > 10)
    check("no thin chains in this fixture", b["universe"]["excluded_thin_chain"] == [])
    check("satellite excludes benchmarks", not set(SATELLITE) & set(BENCHMARKS))

    print("\n── render ──")
    txt = render(b)
    check("brief renders", "DELTAX morning brief" in txt)
    check("regime line present", "REGIME" in txt)
    check("earnings section present", "EARNINGS BLACKOUT" in txt)
    check("no crash on empty earnings", isinstance(txt, str) and len(txt) > 100)
finally:
    os.chdir(cwd)
    import shutil; shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
