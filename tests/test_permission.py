"""Trade-permission state tests. Pure logic, no network."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.permission import (Evidence, recommend_state, gate_permission,
                               NORMAL, CAUTION, DEFENSIVE, NO_NEW_POSITIONS,
                               HALT, ORDER, POLICY)

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

OK = dict(vix_change_pct=2, benchmarks_weak=0, market_open=True, drawdown_pct=-1)

print("\n── normal conditions ──")
d = recommend_state(Evidence(**OK))
check("quiet market -> NORMAL", d.state == NORMAL, d.state)
check("both sides permitted", gate_permission(d,"put")[0] and gate_permission(d,"call")[0])
check("full size", d.policy["size_factor"] == 1.0)

print("\n── escalation ──")
d = recommend_state(Evidence(**{**OK, "benchmarks_weak": 3}))
check("3 weak -> DEFENSIVE", d.state == DEFENSIVE, d.state)
check("put side blocked when all weak", not gate_permission(d,"put")[0])
check("call side still allowed", gate_permission(d,"call")[0])
d = recommend_state(Evidence(**{**OK, "vix_change_pct": 20}))
check("VIX +20% -> DEFENSIVE", d.state == DEFENSIVE, d.state)
d = recommend_state(Evidence(**{**OK, "vix_change_pct": 45}))
check("VIX +45% -> NO_NEW_POSITIONS", d.state == NO_NEW_POSITIONS, d.state)
check("shock blocks both sides",
      not gate_permission(d,"put")[0] and not gate_permission(d,"call")[0])

print("\n── kill switch (S5) ──")
d = recommend_state(Evidence(**{**OK, "drawdown_pct": -11}))
check("drawdown past backtested worst -> HALT", d.state == HALT, d.state)
d = recommend_state(Evidence(**{**OK, "drawdown_pct": -6.5}))
check("drawdown approaching limit -> CAUTION", d.state == CAUTION, d.state)

print("\n── fail closed ──")
check("stale data -> HALT", recommend_state(Evidence(data_stale=True, market_open=True)).state == HALT)
check("unknown market status -> HALT", recommend_state(Evidence(vix_change_pct=1)).state == HALT)
check("market closed -> NO_NEW_POSITIONS",
      recommend_state(Evidence(**{**OK, "market_open": False})).state == NO_NEW_POSITIONS)
d = recommend_state(Evidence(vix_change_pct=None, benchmarks_weak=0, market_open=True, drawdown_pct=-1))
check("missing VIX raises to CAUTION, never NORMAL", d.state != NORMAL, d.state)
d = recommend_state(Evidence(vix_change_pct=2, benchmarks_weak=None, market_open=True, drawdown_pct=-1))
check("missing regime raises to CAUTION", d.state != NORMAL, d.state)

print("\n── most restrictive wins ──")
d = recommend_state(Evidence(vix_change_pct=45, benchmarks_weak=0, market_open=True, drawdown_pct=-11))
check("halt beats no-new-positions", d.state == HALT, d.state)
check("every reason recorded", len(d.reasons) >= 2, str(d.reasons))

print("\n── policy integrity ──")
check("states ordered by restriction", ORDER.index(NORMAL) < ORDER.index(HALT))
check("every state has a policy", all(s in POLICY for s in ORDER))
check("HALT permits nothing", POLICY[HALT]["size_factor"] == 0
      and not POLICY[HALT]["put_side"] and not POLICY[HALT]["call_side"])
check("size never exceeds 100%", all(p["size_factor"] <= 1.0 for p in POLICY.values()))

print("\n── override is scoped to dry-run (run.py) ──")
from datetime import date
from deltax.run import run

class StubFeed:
    """Market closed, benchmarks fine - permission will say NO_NEW_POSITIONS."""
    def clock(self): return {"is_open": False}
    def snapshots(self, syms):
        return {s: {"latestTrade": {"p": 100.0},
                    "dailyBar": {"c": 100.0, "o": 99.0},
                    "prevDailyBar": {"c": 99.0}} for s in syms}
    def chain(self, *a, **k): return {}
    def option_contracts(self, *a, **k): return []

class StubLedger:
    def __init__(self): self.rows = []
    def record_raw(self, d): self.rows.append(d)
    def record(self, *a, **k): return {"result": "ok"}

def go(**kw):
    led = StubLedger()
    return run(StubFeed(), led, equity=100_000.0, today=date.today(), **kw), led

out, led = go(dry_run=True, force_window=False)
check("closed market blocks dry run without force", out["skipped"] is not None, out.get("skipped"))

out, led = go(dry_run=True, force_window=True)
check("force + dry_run proceeds for analysis", out.get("skipped") is None)
check("and is flagged advisory_only", out.get("advisory_only") is True)

out, led = go(dry_run=False, force_window=True)
check("force is inert in live mode", out["skipped"] is not None, out.get("skipped"))
check("live run never flagged advisory", not out.get("advisory_only"))

_, led2 = go(dry_run=True, force_window=True)
perm_rows = [r for r in led2.rows if r.get("action") == "permission"]
check("permission decision is logged", len(perm_rows) == 1)
check("override flag recorded in ledger", perm_rows[0].get("overridden") is True)
check("blocking reason recorded", bool(perm_rows[0].get("reasons")))

import subprocess, sys as _s
r = subprocess.run([_s.executable, "-m", "deltax.run", "--force", "--live"],
                   capture_output=True, text=True)
check("CLI refuses --force --live", r.returncode != 0 and "REFUSED" in r.stderr,
      r.stderr[:60])

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
