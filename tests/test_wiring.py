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
from deltax.gates import evaluate, PORTFOLIO_RISK_PCT, gate_listed, MAX_BAR_AGE_DAYS

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

TODAY = date(2026, 8, 31)
def base(**kw):
    """A candidate that PASSES everything; each test breaks one thing."""
    a = dict(symbol="SPY", equity=100_000.0, max_loss_per_contract=270.0,
             max_profit_per_contract=230.0, credit=2.30, expiry=TODAY+timedelta(days=4),
             today=TODAY, open_interest=5000, open_portfolio_max_loss=0.0,
             structure="credit", width=5.0, short_delta=0.20,
             worst_leg_spread_pct=0.05, quote_age_hours=0.1,
             # E87: both production callers (screener.py and run.py) always
             # supply this, and the gate now refuses when it is None - an
             # unverifiable friction number cannot be accepted. The fixture
             # omitted it, which is why these tests passed while the friction
             # check was silently skipped.
             roundtrip_cost=0.20,
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
    # E28: a failed lookup must refuse, not sail through as "no earnings"
    ("earnings",        dict(earnings_checked=False)),
    ("liquidity",       dict(open_interest=10)),
    ("liquidity",       dict(open_interest=None)),
    ("min_credit",      dict(credit=0.10)),
    ("sizing",          dict(max_loss_per_contract=9_000.0)),
    # derived, so it keeps testing the gate when the cap moves (E22)
    ("portfolio_risk",  dict(open_portfolio_max_loss=100_000.0*PORTFOLIO_RISK_PCT - 50.0)),
    # floor is now 85% of the MEASURED market rate (E34), so a poor fill
    # has to be genuinely poor: 0.30/5 = 0.060 vs a 0.095 floor.
    ("credit_fraction", dict(credit=0.90, width=20.0, short_delta=0.20)),
    ("quote_sanity",    dict(credit=-1.0)),
    ("quote_sanity",    dict(quote_age_hours=48.0)),
    ("spread_quality",  dict(worst_leg_spread_pct=0.95)),
    ("listed",          dict(tradable=False, last_bar_age_days=0.1)),
    ("listed",          dict(tradable=True,  last_bar_age_days=900.0)),
]:
    ok, d = fires(gate, **kw)
    check(f"{gate:<16} fires on {list(kw)[0]}={list(kw.values())[0]}", ok, d)

print("\n── earnings: unknown is not the same as none (E28) ──")
from deltax.gates import gate_no_earnings_before_expiry as _eg
_exp = TODAY + timedelta(days=4)
check("ETF with genuinely no earnings passes", _eg(None, _exp, True).passed)
check("FAILED lookup refuses", not _eg(None, _exp, False).passed)
check("the two states are distinguishable",
      _eg(None,_exp,True).passed != _eg(None,_exp,False).passed)
check("earnings before expiry still refuses",
      not _eg(TODAY+timedelta(days=3), _exp, True).passed)
check("earnings after expiry still passes",
      _eg(TODAY+timedelta(days=40), _exp, True).passed)
r = evaluate(**base(earnings_checked=False))
check("unknown earnings refuses through evaluate()", r.failed_gate == "earnings", str(r.failed_gate))

print("\n── listing gate: the TRON case (E25) ──")
# TRX/USD: 332 clean daily bars ending 2023-04-19, zero bars in Aug 2026.
TRX_AGE = 1227.0
check("delisted crypto is refused", not gate_listed(True, TRX_AGE, "crypto").passed)
check("live crypto passes", gate_listed(True, 0.4, "crypto").passed)
check("crypto is stricter than equity",
      MAX_BAR_AGE_DAYS["crypto"] < MAX_BAR_AGE_DAYS["equity"])
check("equity survives a long weekend", gate_listed(True, 3.0, "equity").passed)
check("untradable asset refused regardless of freshness",
      not gate_listed(False, 0.0, "equity").passed)
check("unknown listing status fails CLOSED",
      not gate_listed(None, 1.0).passed and not gate_listed(True, None).passed)
r = evaluate(**base(tradable=True, last_bar_age_days=TRX_AGE, asset_class="crypto"))
check("stale listing refuses through evaluate()", r.failed_gate == "listed", str(r.failed_gate))
r = evaluate(**base())
check("callers without listing evidence still work", r.failed_gate is None, str(r.failed_gate))

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

import re
print("\n── E83: the cycle timestamp must never be shadowed ──")
# `now = sm - lm` in the exit sweep replaced the cycle's UTC timestamp with the
# spread's mark (a float). Line 568's `(now - bar_t)` then raised TypeError,
# was swallowed by `except (ValueError, TypeError)`, and bar_age became None -
# so gate_listed took its fail-closed branch for EVERY candidate from the first
# cycle that held a position, reporting healthy ETFs as "likely delisted".
_run_src = open(os.path.join(os.path.dirname(__file__), "..", "deltax", "run.py")).read()
check("E83 the sweep no longer assigns to `now`",
      "\n            now = sm - lm" not in _run_src)
check("E83 it uses a distinct name instead", "mark_now = sm - lm" in _run_src)
check("E83 only one assignment to `now` remains in run.py",
      len(re.findall(r"^\s+now = ", _run_src, re.M)) == 1,
      str(re.findall(r"^\s+now = .*", _run_src, re.M)))
check("E83 an unreadable bar age is now recorded, not swallowed",
      "bar_age_unreadable" in _run_src)

print("\n── E83b: partial listing evidence must not silently fail closed ──")
# gate_listed is inserted when EITHER tradable or age is supplied, but fails
# closed when EITHER is None - so tradable=True with age=None guarantees a
# refusal attributed to "listed". That is the exact state run.py was in.
_d = evaluate(**base(tradable=True, last_bar_age_days=None))
_g = {g.gate: g for g in _d.gates}
check("E83b tradable=True + age=None still refuses (fail-closed is correct)",
      "listed" in _g and not _g["listed"].passed)
check("E83b and the refusal is legible as unknown, not as delisted",
      "unknown" in _g["listed"].detail, _g["listed"].detail)
_d2 = evaluate(**base(tradable=True, last_bar_age_days=0.5))
_g2 = {g.gate: g for g in _d2.gates}
check("E83b a real age passes the gate", _g2["listed"].passed, _g2["listed"].detail)

print("\n── E84: a position the sweep cannot read must not vanish ──")
# The parse failure was a bare `continue`: the holding then appeared in NONE of
# closed/held/unpriceable/failed, so it silently left the sweep and the board
# with nobody told. A position the sweep cannot see is one that never closes.
check("E84 an unreadable position is recorded", "sweep_drop" in _run_src)
check("E84 an unreadable expiry is recorded", "sweep_dte_unreadable" in _run_src)
check("E84 dropped positions are collected", "sweep_dropped" in _run_src)
check("E84 and surfaced on the result, not only logged",
      '"dropped"' in _run_src and "sweep_incomplete" in _run_src)
check("E84 swept is initialised with every key manage() returns",
      all(k in _run_src.split("swept = {")[1].split("}")[0]
          for k in ('"closed"', '"held"', '"unpriceable"', '"failed"')),
      _run_src.split("swept = {")[1].split("}")[0])

print("\n── E86: an equity holding can never be silent ──")
# reconcile() always collected `equities` and nothing read it - computed every
# cycle and thrown away. It matters because assignment creates stock with NO
# order placed, which bypasses the E82 rule-3 guard entirely.
check("E86 unexpected equity is recorded loudly", "UNEXPECTED_EQUITY" in _run_src)
check("E86 the record names the rule at stake", "rule 3" in _run_src)
check("E86 it names assignment as the cause the guard cannot see",
      "assignment" in _run_src)
check("E86 equities are surfaced on the run result", '"equities": _eq' in _run_src)
check("E86 but do NOT block trading (the E72 deadlock)",
      "refusing new risk" not in _run_src.split("UNEXPECTED_EQUITY")[1][:600])

print("\n── E87: unverifiable friction must refuse, not skip ──")
_nf = evaluate(**base(roundtrip_cost=None))
_gf = {g.gate: g for g in _nf.gates}
check("E87 roundtrip_cost=None refuses", not _gf["spread_quality"].passed,
      _gf["spread_quality"].detail)
check("E87 the refusal explains why", "unreadable" in _gf["spread_quality"].detail)
check("E87 a readable friction still passes",
      {g.gate: g for g in evaluate(**base()).gates}["spread_quality"].passed)
check("E87 and excessive friction still refuses",
      not {g.gate: g for g in evaluate(**base(roundtrip_cost=2.00)).gates}["spread_quality"].passed)
# the reachable path: ONE leg unreadable still yields a worst_leg_spread_pct
check("E87 both production callers pass roundtrip_cost",
      "roundtrip_cost=cand" in open(os.path.join(os.path.dirname(__file__), "..",
          "deltax", "run.py")).read()
      and "roundtrip_cost=cand" in open(os.path.join(os.path.dirname(__file__), "..",
          "deltax", "screener.py")).read())

print("\n── E89: an unreadable account must not render as a total loss ──")
# A failed feed.account() degraded to eq = csh = 0.0, and the board rendered
# "$0.00 (-100.0% today)" and "net -100,000.00 vs $100,000 start". A transient
# API timeout was displayed to the team - and on the public board to the
# judges - as the fund having lost everything.
from deltax import report as _rep
_h = _rep.header(None, None, market_open=False)
check("E89 header renders None as unavailable", "unavailable" in _h, _h[-90:])
check("E89 header does NOT claim -100%", "-100.0" not in _h, _h[-90:])
check("E89 header does NOT show $0.00", "$0.00" not in _h, _h[-90:])
_sb = _rep.scoreboard(None, 0.0, 0.0)
check("E89 scoreboard reports the read failure", "unreadable" in _sb, _sb)
check("E89 scoreboard does NOT print a -100,000 net", "100,000.00" not in _sb, _sb)
# a real equity must still render normally
_h2 = _rep.header(98_943.18, 102_719.0, market_open=True)
check("E89 a real equity still renders", "98,943.18" in _h2, _h2[-90:])
_sb2 = _rep.scoreboard(98_943.18, 0.0, 0.0)
check("E89 and its net still computes", "1,056" in _sb2 or "1,057" in _sb2, _sb2)
check("E89 run.py records the account read failure",
      "account_read_failed" in _run_src)
check("E89 run.py no longer zeroes equity on failure",
      "eq = csh = 0.0" not in _run_src)

print("\n── E101: the variance-premium gate ──")
# Selling a credit spread is selling volatility, so the only edge is implied
# vol above what the underlying actually delivers. Nothing checked this for
# three days: on 2 Sep six SMH spreads - $5,507 and 42% of committed risk - sat
# at IV/RV 0.91 while DIA offered 1.64. A negative premium is a mathematically
# losing trade that no strike selection rescues, because the market prices the
# whole curve fairly and moving the short strike trades win rate against payoff
# at roughly constant expectancy.
from deltax.gates import gate_variance_premium, MIN_VARIANCE_PREMIUM
_g = {g.gate: g for g in evaluate(**base(implied_vol=0.278, realized_vol=0.307)).gates}
check("E101 the gate runs on a credit structure", "variance_premium" in _g)
check("E101 the real SMH reading (0.91x) is refused",
      not _g["variance_premium"].passed, _g["variance_premium"].detail)
check("E101 the refusal names the shortfall",
      "below what the stock delivers" in _g["variance_premium"].detail)
_d = {g.gate: g for g in evaluate(**base(implied_vol=0.133, realized_vol=0.081)).gates}
check("E101 the real DIA reading (1.64x) passes", _d["variance_premium"].passed,
      _d["variance_premium"].detail)
# fail closed on missing evidence - a premium we cannot measure is not one we sell
for _iv, _rv, _why in ((None, 0.10, "implied vol missing"),
                       (0.20, None, "realised vol missing"),
                       (0.20, 0.0, "realised vol zero")):
    _r = gate_variance_premium(_iv, _rv)
    check(f"E101 fails closed when {_why}", _r.passed is False, _r.detail)
check("E101 exactly at the floor passes",
      gate_variance_premium(0.110, 0.100).passed is True)
check("E101 a hair under the floor refuses",
      gate_variance_premium(0.1099, 0.100).passed is False)
check("E101 the floor is 1.10", abs(MIN_VARIANCE_PREMIUM - 1.10) < 1e-9)
# a debit structure is BUYING vol - the gate must not invert onto it
_deb = {g.gate: g for g in evaluate(**base(structure="debit",
        max_profit_per_contract=900.0, implied_vol=0.10, realized_vol=0.30)).gates}
check("E101 does not gate debit structures", "variance_premium" not in _deb)
# and it must actually be fed - a gate with no data is dead code (E74)
check("E101 run.py passes both readings",
      "implied_vol=cand.get(\"implied_vol\")" in _run_src
      and "realized_vol=_rv_cache.get(symbol)" in _run_src)
check("E101 the screener captures implied vol from the chain",
      '"iv": c.get("impliedVolatility")' in open(os.path.join(
          os.path.dirname(__file__), "..", "deltax", "screener.py")).read())

print("\n── E102: the trailing exit must actually be FED ──")
# Found by mutation testing: replacing peak_captured=_peaks.get(ssym) with None
# broke no test. The trail would then be fully implemented, fully unit-tested,
# and permanently inert - a peak of None can never exceed the arm threshold.
# The E74 lesson: a rule with no data is dead code, and its own unit tests will
# not notice.
check("E102 run.py loads peaks before building the sweep",
      "_peaks = _load_peaks()" in _run_src)
check("E102 and passes each structure its own peak",
      "peak_captured=_peaks.get(ssym)" in _run_src)
check("E102 and persists the raised marks after the sweep",
      "_update_peaks(live)" in _run_src)
check("E102 peaks are read BEFORE this cycle's marks are folded in",
      _run_src.index("_peaks = _load_peaks()") < _run_src.index("_update_peaks(live)"))
check("E102 the peak store is anchored to the repo, not the CWD",
      "PEAKS_PATH = _os.path.join(" in open(os.path.join(
          os.path.dirname(__file__), "..", "deltax", "manage.py")).read())

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
