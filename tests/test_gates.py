"""Unit tests for the DELTAX risk gates. No network, no market connection."""

import sys, os
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from deltax.gates import (
    evaluate, size_from_risk, Decision,
    PER_POSITION_RISK_PCT, PORTFOLIO_RISK_PCT,
    CREDIT_SURFACE, CREDIT_MARKET_FRACTION, market_credit_ratio,
    gate_expectancy, gate_dte, gate_liquidity, gate_reward_risk,
    gate_portfolio_risk, gate_defined_risk, gate_no_earnings_before_expiry,
    gate_dte_vs_time_stop, MIN_DTE)

EQUITY = 100_000.0
TODAY = date(2026, 8, 31)
# E37 caps every expiry at the contest close (4 Sep), and MIN_DTE is 4, so
# 4 Sep is now the ONLY date satisfying both gates. The old 14-DTE fixture is
# refused by contest_window before any other gate is reached.
GOOD_EXPIRY = date(2026, 9, 4)    # 4 DTE — the only expiry inside both gates

passed = failed = 0

def check(name, cond, detail=""):
    global passed, failed
    # E42: swapped args made three tests vacuous - the condition slot held a
    # non-empty string, so they passed unconditionally. Never again.
    if not isinstance(name, str) or not isinstance(cond, (bool, type(None))):
        raise TypeError(f"check(label:str, cond:bool, detail) - got "
                        f"({type(name).__name__}, {type(cond).__name__})")
    if cond:
        passed += 1; print(f"  ✓ {name}")
    else:
        failed += 1; print(f"  ✗ {name}  {detail}")


print("\n── expectancy ──")
# Video 07's worked example: W=200, L=170, P=0.55 -> +0.20
r = gate_expectancy(200, 170, 0.55)
check("worked example E=+0.20", r.passed and abs(r.observed - 0.1971) < 0.001, f"got {r.observed}")
# High win rate, terrible payoff — the trap the whole corpus falls into
r = gate_expectancy(50, 500, 0.85)
check("85% win rate with bad payoff is REJECTED", not r.passed, f"E={r.observed}")
# Sky View's basket: 4 of 5 winners, still negative
r = gate_expectancy(35, 298, 0.80)
check("4-of-5 winners still fails when loss is large", not r.passed, f"E={r.observed}")
r = gate_expectancy(300, 100, 0.40)
check("40% win rate with 3:1 payoff PASSES", r.passed, f"E={r.observed}")

print("\n── DTE band (rule R5: no 0DTE) ──")
check("0DTE rejected", not gate_dte(TODAY, TODAY).passed)
# The floor has moved three times and the INVARIANT, not the value, is what
# must hold: MIN_DTE strictly above TIME_STOP_DTE, or a position is eligible for
# the time stop the moment it opens (E45). E41 set 2, E45 raised it to 3, E57
# lowered it to 2 again with TIME_STOP_DTE cut to 1 so the invariant survives.
# E57 is a knowing, capped override of R5 for submission evidence - see E56/E57.
check("0 DTE always rejected", not gate_dte(TODAY, TODAY).passed)
check("the floor itself is accepted",
      gate_dte(TODAY + timedelta(days=MIN_DTE), TODAY).passed, f"MIN_DTE={MIN_DTE}")
check("one day inside the floor is rejected",
      not gate_dte(TODAY + timedelta(days=MIN_DTE - 1), TODAY).passed)

from deltax.manage import TIME_STOP_DTE as _TS
check("E45 MIN_DTE stays strictly above TIME_STOP_DTE", MIN_DTE > _TS,
      f"MIN_DTE={MIN_DTE} TIME_STOP_DTE={_TS}")
check("E45 gate refuses when that invariant breaks", gate_dte_vs_time_stop().passed)
check("4 DTE accepted", gate_dte(GOOD_EXPIRY, TODAY).passed)
check("45 DTE rejected (won't resolve in window)", not gate_dte(date(2026, 10, 15), TODAY).passed)

print("\n── liquidity (the SPCX case) ──")
check("SPCX OI=6 rejected", not gate_liquidity(6, 1).passed)
check("SPCX OI=1 rejected", not gate_liquidity(1, 1).passed)
check("OI unknown rejected", not gate_liquidity(None, 1).passed)
check("OI=5000 with 10 contracts accepted", gate_liquidity(5000, 10).passed)
check("OI=5000 but 400 contracts rejected (too big a share)", not gate_liquidity(5000, 400).passed)

print("\n── defined risk ──")
check("undefined max loss rejected (naked)", not gate_defined_risk(None).passed)
check("bounded max loss accepted", gate_defined_risk(150.0).passed)

print("\n── reward:risk ──")
check("1.5:1 rejected", not gate_reward_risk(150, 100).passed)
check("2:1 accepted", gate_reward_risk(200, 100).passed)

print("\n── portfolio cap ──")
CAP = EQUITY * PORTFOLIO_RISK_PCT
check("within portfolio cap accepted", gate_portfolio_risk(1000, CAP - 2000, EQUITY).passed)
check("breaching portfolio cap rejected", not gate_portfolio_risk(1000, CAP - 500, EQUITY).passed)

print("\n── earnings veto ──")
check("earnings before expiry vetoes", not gate_no_earnings_before_expiry(date(2026, 9, 2), GOOD_EXPIRY).passed)
check("earnings after expiry allowed", gate_no_earnings_before_expiry(date(2026, 10, 1), GOOD_EXPIRY).passed)
check("no earnings scheduled allowed", gate_no_earnings_before_expiry(None, GOOD_EXPIRY).passed)

print("\n── sizing ──")
BUDGET = EQUITY * PER_POSITION_RISK_PCT
check("sizing = budget // risk-per-contract", size_from_risk(EQUITY, 100) == int(BUDGET // 100),
      f"got {size_from_risk(EQUITY, 100)}")
check("contract costlier than budget -> 0", size_from_risk(EQUITY, BUDGET + 1) == 0)

print("\n── end-to-end: a clean candidate ──")
d = evaluate(
    symbol="SPY", equity=EQUITY,
    max_loss_per_contract=100.0, max_profit_per_contract=250.0,
    credit=1.20, expiry=GOOD_EXPIRY, today=TODAY,
    open_interest=12_000, open_portfolio_max_loss=0.0,
    avg_win=250, avg_loss=100, win_rate=0.45,
)
check("clean candidate -> TRADE", d.decision == Decision.TRADE, d.failed_gate or "")
check("sized to budget // 100", d.contracts == int(BUDGET // 100), f"got {d.contracts}")
check("max loss = per-position budget", d.max_loss == float(int(BUDGET // 100) * 100), f"got {d.max_loss}")

print("\n── end-to-end: the real SPCX chain ──")
d = evaluate(
    symbol="SPCX", equity=EQUITY,
    max_loss_per_contract=100.0, max_profit_per_contract=250.0,
    credit=1.20, expiry=date(2026, 9, 4), today=TODAY,   # 4 DTE
    open_interest=6,                                      # live value
)
check("SPCX -> REFUSE", d.decision == Decision.REFUSE)
check("refusal names a gate", d.failed_gate is not None, "")
print(f"     first failing gate: {d.failed_gate}")
for g in d.gates:
    if not g.passed:
        print(f"       · {g.gate}: {g.detail}")


print("\n── structure-aware payoff gate ──")
from deltax.gates import gate_credit_fraction
# SPY put credit spread: $5 wide, $1.60 credit -> max loss/ct $340, max profit $160
d = evaluate(
    symbol="SPY", equity=EQUITY, structure="credit", width=5.0,
    max_loss_per_contract=340.0, max_profit_per_contract=160.0,
    credit=1.85, expiry=GOOD_EXPIRY, today=TODAY,
    open_interest=12_000, short_delta=0.30,
)
check("OTM credit spread now TRADES", d.decision == Decision.TRADE, d.failed_gate or "")
check("credit_fraction gate ran", any(g.gate == "credit_fraction" for g in d.gates))
check("reward_risk gate NOT applied to credit", not any(g.gate == "reward_risk" for g in d.gates))
# Thin credit rejected. It must clear MIN_CREDIT ($0.75) so that
# credit_fraction is the gate that actually fires: $10 wide at δ0.30 has a
# measured floor of 0.85 x 0.150 x 10 = $1.275, so $1.00 passes the flat floor
# and fails the market-relative one.
d = evaluate(
    symbol="SPY", equity=EQUITY, structure="credit", width=10.0,
    max_loss_per_contract=900.0, max_profit_per_contract=100.0,
    credit=1.00, expiry=GOOD_EXPIRY, today=TODAY, open_interest=12_000,
    short_delta=0.30,
)
check("credit below the measured market floor refused",
      d.decision == Decision.REFUSE and d.failed_gate == "credit_fraction",
      f"{d.decision}/{d.failed_gate}")
# Floor = CREDIT_MARKET_FRACTION x the MEASURED market rate (E34), not a
# multiple of delta. At δ0.20 on a 5-wide the market pays 0.112 of width, so the
# floor is 0.85 x 0.112 x 5 = $0.476 — an ordinary fill clears it, a poor one does not.
_f20 = CREDIT_MARKET_FRACTION * market_credit_ratio(0.20, 5.0) * 5.0
check("floor tracks the measured market rate at delta 0.20",
      gate_credit_fraction(_f20 * 1.15, 5.0, 0.20).passed
      and not gate_credit_fraction(_f20 * 0.80, 5.0, 0.20).passed)
_f35 = CREDIT_MARKET_FRACTION * market_credit_ratio(0.35, 5.0) * 5.0
check("and at delta 0.35, where the market pays more",
      gate_credit_fraction(_f35 * 1.15, 5.0, 0.35).passed
      and not gate_credit_fraction(_f35 * 0.80, 5.0, 0.35).passed)
check("a richer delta demands a higher floor", _f35 > _f20)
check("floor is backtested breakeven, not a guess",
      # E34 replaced the 1.15 x delta floor with a MEASURED surface: the old
      # constant demanded a credit the market never pays. The floor is now a
      # discount on what live chains actually quote.
      abs(market_credit_ratio(0.20, 5.0) - CREDIT_SURFACE[(0.20, 5.0)]) < 1e-9
      and 0.5 < CREDIT_MARKET_FRACTION < 1.0)
check("sign of delta is irrelevant (puts are negative)",
      gate_credit_fraction(1.20, 5.0, -0.20).passed)
check("no delta -> flat fallback floor 0.20",
      gate_credit_fraction(1.05, 5.0).passed and not gate_credit_fraction(0.95, 5.0).passed)


print("\n── quote sanity (weekend-data guard) ──")
from deltax.gates import gate_quote_sanity, MAX_QUOTE_AGE_HOURS
check("negative credit on a credit spread rejected",
      not gate_quote_sanity(-0.04, "credit").passed)
check("zero credit rejected", not gate_quote_sanity(0.0, "credit").passed)
check("positive credit accepted", gate_quote_sanity(1.20, "credit").passed)
check("debit structures are not credit-signed",
      gate_quote_sanity(-0.04, "debit").passed)
check("missing credit rejected", not gate_quote_sanity(None, "credit").passed)
check("stale quotes rejected", not gate_quote_sanity(1.2, "credit", quote_age_hours=48).passed)
check("fresh quotes accepted", gate_quote_sanity(1.2, "credit", quote_age_hours=0.2).passed)
check("reason names the cause",
      "crossed or stale" in gate_quote_sanity(-0.01, "credit").detail)
d = evaluate(symbol="XLK", equity=EQUITY, structure="credit", width=3.0,
             max_loss_per_contract=301.0, max_profit_per_contract=-1.0,
             credit=-0.01, expiry=GOOD_EXPIRY, today=TODAY,
             open_interest=5000, short_delta=0.19)
check("broken quote fails first, before economic gates",
      d.decision == Decision.REFUSE and d.failed_gate == "quote_sanity", str(d.failed_gate))

# ---- E42: the stand-down is enforced in code, not just documented ----------
def test_e42_submit_refuses_while_suspended():
    """Calls submit() with its REAL signature. An earlier version of this test
    passed wrong kwargs, got TypeError, and counted that as a refusal - which
    hid an AttributeError in the guard itself. No escape hatch here."""
    import deltax.gates as g
    from deltax.execute import submit, ExecutionRefused
    was = g.TRADING_SUSPENDED
    g.TRADING_SUSPENDED = True          # prove the MECHANISM, not today's state
    legs = [{"symbol": "SPY260904P00760000", "side": "sell", "ratio": 1},
            {"symbol": "SPY260904P00740000", "side": "buy",  "ratio": 1}]
    try:
        submit(legs=legs, qty=1, limit_price=1.50, dry_run=True)
        check("E42 submit refused while suspended", False, "submit RETURNED")
    except ExecutionRefused as e:
        check("E42 submit refused while suspended", "SUSPENDED" in str(e), str(e)[:55])
    except Exception as e:
        check("E42 submit refused while suspended", False,
              f"wrong exception {type(e).__name__}: {e}")
    finally:
        g.TRADING_SUSPENDED = was


def test_e42_guard_survives_dry_run_false():
    """dry_run=False must refuse too - that is the path that sends real orders."""
    import deltax.gates as g
    from deltax.execute import submit, ExecutionRefused
    was = g.TRADING_SUSPENDED
    g.TRADING_SUSPENDED = True
    legs = [{"symbol": "SPY260904P00760000", "side": "sell", "ratio": 1}]
    try:
        submit(legs=legs, qty=1, limit_price=1.50, dry_run=False)
        check("E42 live path refused", False, "LIVE submit RETURNED")
    except ExecutionRefused:
        check("E42 live path refused", True, "refused")
    except Exception as e:
        check("E42 live path refused", False, f"{type(e).__name__}: {e}")
    finally:
        g.TRADING_SUSPENDED = was


def test_e42_screening_still_runs():
    """The stand-down must not blind the agent - it still evaluates and logs."""
    import deltax.gates as g
    check("E42 gate exists", hasattr(g, "gate_trading_enabled"), "present")
    was = g.TRADING_SUSPENDED
    g.TRADING_SUSPENDED = False
    check("gate passes when trading is enabled", g.gate_trading_enabled().passed)
    g.TRADING_SUSPENDED = True
    check("gate fails when the stand-down is armed", not g.gate_trading_enabled().passed)
    g.TRADING_SUSPENDED = was
    body = open("deltax/gates.py").read().split("def evaluate(")[1].split("\ndef ")[0]
    check("E42 evaluate() still gates normally",
          "gate_trading_enabled()" not in body, "not short-circuited")


test_e42_submit_refuses_while_suspended()
test_e42_guard_survives_dry_run_false()
test_e42_screening_still_runs()

print("\n── E57: demonstration mode (a capped, explicit override of R5) ──")
import deltax.gates as _G
from deltax.gates import demo_cap, demo_permits, DEMO_MAX_CONTRACTS

check("E57 cap reduces an oversized position", demo_cap(47) == DEMO_MAX_CONTRACTS,
      f"47 -> {demo_cap(47)}")
check("E57 cap never RAISES size",
      demo_cap(0) == 0 and demo_cap(1) <= DEMO_MAX_CONTRACTS,
      f"0 -> {demo_cap(0)}, 1 -> {demo_cap(1)}")
check("E57 cap is monotone",
      all(demo_cap(a) <= demo_cap(b) for a, b in zip(range(0, 20), range(1, 21))))
check("E57 proceeds through a directional caution", demo_permits("DEFENSIVE"))
check("E57 NEVER proceeds through NO_NEW_POSITIONS",
      not demo_permits("NO_NEW_POSITIONS"))
check("E57 NEVER proceeds through HALT", not demo_permits("HALT"))

# Mutation: with the mode off, the cap must go inert and the overrides stop.
# A control that behaves identically switched off was never doing anything.
_was = _G.DEMONSTRATION_MODE
_G.DEMONSTRATION_MODE = False
check("E57 disabled -> cap is inert", _G.demo_cap(47) == 47, str(_G.demo_cap(47)))
check("E57 disabled -> no permission override", _G.demo_permits("HALT") is True)
_G.DEMONSTRATION_MODE = _was
check("E57 state restored after mutation", _G.DEMONSTRATION_MODE == _was)

# E43: the controls must be WIRED, not merely defined. A guard nothing calls
# reports green forever.
_run = open("deltax/run.py").read()
check("E57 cap is applied in the trading path", "demo_cap(dec.contracts)" in _run)
check("E57 submit uses the CAPPED quantity", "execute.submit(legs, qty," in _run)
check("E57 exit uses the CAPPED quantity", "place_exit(legs, qty," in _run)
check("E57 permission override is wired", "demo_permits(perm.state)" in _run)
check("E57 sized-vs-capped divergence is logged", "demo_size_cap" in _run)
check("E57 committed risk follows the capped size",
      "dec.max_loss * (qty / dec.contracts" in _run)


print("\n── E74: round-trip friction must not eat the credit ──")
from deltax.gates import gate_spread_quality, MAX_FRICTION_OF_CREDIT
# the SMH trade: legs looked fine (9%), round trip ate 57% of the credit
r = gate_spread_quality(0.09, 0.83 + 0.49, 2.30)
check("E74 refuses the SMH case tight legs would have passed", not r.passed, r.detail)
check("E74 refusal names the share of credit", "% of the" in r.detail, r.detail)
r = gate_spread_quality(0.02, 0.07, 0.96)
check("E74 passes IWM-style tight legs", r.passed, r.detail)
r = gate_spread_quality(0.20, 0.01, 5.00)
check("E74 still refuses a wide LEG even when friction is cheap",
      not r.passed and "worst leg" in r.detail, r.detail)
r = gate_spread_quality(0.02, None, None)
check("E74 without friction data behaves as before", r.passed, r.detail)
r = gate_spread_quality(None, 0.10, 2.00)
check("missing quote still refuses", not r.passed)
r = gate_spread_quality(0.02, 0.70, 2.00)   # exactly 35%
check("exactly at the ceiling passes", r.passed, r.detail)
r = gate_spread_quality(0.02, 0.71, 2.00)   # just over
check("one cent over the ceiling refuses", not r.passed, r.detail)
check("friction ceiling is a fraction", 0 < MAX_FRICTION_OF_CREDIT < 1)
_g = open("deltax/gates.py").read()
check("E74 is WIRED into evaluate()", "gate_spread_quality(worst_leg_spread_pct,\n" in _g
      or "roundtrip_cost, credit)" in _g)


print("\n── E74 WIRING: the gate must receive real data, not just exist ──")
# The first version of E74 passed 10 unit tests and did NOTHING live: the
# screener never computed roundtrip_cost, so it was always None and the branch
# never ran. Testing a function directly proves the function; it does not prove
# the caller feeds it. These assertions check the DATA PATH.
_scr = open("deltax/screener.py").read()
_run_src = open("deltax/run.py").read()
check("screener COMPUTES roundtrip_cost", '"roundtrip_cost": roundtrip' in _scr)
check("screener PASSES it to evaluate", "roundtrip_cost=cand.get" in _scr)
check("run.py PASSES it to evaluate", "roundtrip_cost=cand.get" in _run_src)
check("evaluate ACCEPTS it", "roundtrip_cost: Optional[float]" in open("deltax/gates.py").read())

# End-to-end: the exact SMH quotes that cost us $625 must now REFUSE.
d = evaluate(symbol="SMH", equity=EQUITY, structure="credit", width=10.0,
             max_loss_per_contract=740.0, max_profit_per_contract=260.0,
             credit=2.30, expiry=date(2026, 9, 18), today=date(2026, 9, 2),
             open_interest=4179, short_delta=0.36,
             worst_leg_spread_pct=0.09, roundtrip_cost=0.83 + 0.49)
check("the real SMH trade is now REFUSED end-to-end",
      d.decision == Decision.REFUSE and d.failed_gate == "spread_quality",
      f"{d.decision}/{d.failed_gate}")
check("and the reason names the friction",
      any("round-trip" in g.detail for g in d.gates if g.gate == "spread_quality"))
# ...while a tight book still trades
d2 = evaluate(symbol="IWM", equity=EQUITY, structure="credit", width=5.0,
              max_loss_per_contract=404.0, max_profit_per_contract=96.0,
              credit=0.96, expiry=date(2026, 9, 18), today=date(2026, 9, 2),
              open_interest=65798, short_delta=0.30,
              worst_leg_spread_pct=0.02, roundtrip_cost=0.07)
check("a tight book still TRADES", d2.decision == Decision.TRADE, d2.failed_gate or "")

print("\n-- E96: the live entry-freeze policy --")
# This asserts an OPERATIONAL decision, not a code invariant: new entries are
# frozen on the operator's instruction (2 Sep) because the book runs 4.7:1
# risk/reward - $14,918 at risk against $3,182 of credit - which needs an 82.4%
# win rate while the strikes imply about 68%. If the policy is deliberately
# changed, change this line in the same commit. It is here so an ACCIDENTAL
# un-freeze cannot go unnoticed.
import deltax.gates as _g96
check("E96 new entries are frozen", _g96.NEW_ENTRIES_FROZEN is True,
      str(_g96.NEW_ENTRIES_FROZEN))
_r96 = _g96.gate_new_entries()
check("E96 the gate refuses accordingly", _r96.passed is False, str(_r96.detail))
check("E96 and says why", "risk/reward" in _r96.detail, _r96.detail)
check("E96 exits are NOT suspended by it", _g96.TRADING_SUSPENDED is False)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)

