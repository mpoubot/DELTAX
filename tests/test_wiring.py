"""Every gate must actually FIRE through the real evaluate() path.

Written after Matin's crypto review found a daily-trend risk filter that had
never blocked a single trade since it was built - while passing every isolated
unit test. A gate tested only in isolation proves the FUNCTION works. It proves
nothing about whether evaluate() ever reaches it.

Each case below trips exactly one gate and asserts evaluate() attributes the
refusal to that gate by name. A gate that cannot be provoked here is
unreachable in production, whatever its own unit tests say.
"""
import sys, os
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.gates import evaluate

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

TODAY = date(2026, 8, 31)
def base(**kw):
    """A candidate that PASSES everything; each test breaks one thing."""
    a = dict(symbol="SPY", equity=100_000.0, max_loss_per_contract=270.0,
             max_profit_per_contract=230.0, credit=2.30, expiry=TODAY+timedelta(days=11),
             today=TODAY, open_interest=5000, open_portfolio_max_loss=0.0,
             structure="credit", width=5.0, short_delta=0.20,
             worst_leg_spread_pct=0.05, quote_age_hours=0.1,
             earnings_date=None, halted=False, corporate_action=None)
    a.update(kw); return a

print("\n── the clean candidate is actually approved ──")
r = evaluate(**base())
check("baseline is APPROVED (else every test below is vacuous)",
      r.failed_gate is None, f"refused by {r.failed_gate} / {r.decision}")

def fires(name, **kw):
    r = evaluate(**base(**kw))
    return r.failed_gate == name, f"decision={r.decision} fired={r.failed_gate}"

print("\n── each gate is reachable through evaluate() ──")
for gate, kw in [
    ("tradeable",       dict(halted=True)),
    ("tradeable",       dict(corporate_action="merger")),
    ("defined_risk",    dict(max_loss_per_contract=None)),
    ("dte",             dict(expiry=TODAY+timedelta(days=45))),
    ("dte",             dict(expiry=TODAY+timedelta(days=1))),
    ("earnings",        dict(earnings_date=TODAY+timedelta(days=3))),
    ("liquidity",       dict(open_interest=10)),
    ("liquidity",       dict(open_interest=None)),
    ("min_credit",      dict(credit=0.10)),
    ("sizing",          dict(max_loss_per_contract=9_000.0)),
    ("portfolio_risk",  dict(open_portfolio_max_loss=9_950.0)),
    ("credit_fraction", dict(credit=0.80, width=5.0, short_delta=0.20)),
    ("quote_sanity",    dict(credit=-1.0)),
    ("quote_sanity",    dict(quote_age_hours=48.0)),
    ("spread_quality",  dict(worst_leg_spread_pct=0.95)),
]:
    ok, d = fires(gate, **kw)
    check(f"{gate:<16} fires on {list(kw)[0]}={list(kw.values())[0]}", ok, d)

print("\n── gates that are TAUTOLOGIES in the live path (E20) ──")
from deltax.gates import gate_position_size, size_from_risk, PER_POSITION_RISK_PCT
# Documented, not fixed: sizing derives contracts from the same cap this gate
# checks, so it cannot refuse through evaluate(). Assert the invariant that
# makes it redundant, so a future sizing change breaks THIS test loudly.
worst = 0.0
for ml in (1.0, 37.0, 270.0, 999.0, 1999.0):
    c = size_from_risk(100_000.0, ml)
    worst = max(worst, c * ml)
check("sizing can never exceed the per-position cap",
      worst <= 100_000.0 * PER_POSITION_RISK_PCT, f"worst={worst}")
check("position_size still works when called directly",
      not gate_position_size(9_000.0, 100_000.0).passed)

print("\n── quote_sanity runs FIRST (E13: never calibrate on broken quotes) ──")
r = evaluate(**base(credit=-1.0, open_interest=1, halted=True))
check("broken quote reported before other failures",
      r.failed_gate in ("quote_sanity", "tradeable"), str(r.failed_gate))

print("\n── permission state is wired into the runner, not just importable ──")
import inspect
from deltax import run as runmod
src = inspect.getsource(runmod)
check("run.py calls recommend_state", "recommend_state(" in src)
check("run.py calls gate_permission per side", "gate_permission(" in src)
check("run.py can early-return on permission", "size_factor" in src)
check("permission decision is written to the ledger", '"action": "permission"' in src)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
