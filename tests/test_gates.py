"""Unit tests for the DELTAX risk gates. No network, no market connection."""

import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from deltax.gates import (
    evaluate, size_from_risk, Decision,
    PER_POSITION_RISK_PCT, PORTFOLIO_RISK_PCT,
    CREDIT_SURFACE, CREDIT_MARKET_FRACTION, market_credit_ratio,
    gate_expectancy, gate_dte, gate_liquidity, gate_reward_risk,
    gate_portfolio_risk, gate_defined_risk, gate_no_earnings_before_expiry,
)

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
# E41 lowered MIN_DTE to 2 so a Sep 4 expiry stays reachable through the
# contest. 2 DTE is now the floor and is accepted; 1 DTE is the gamma zone.
check("1 DTE rejected — gamma zone", not gate_dte(date(2026, 9, 1), TODAY).passed)
check("2 DTE accepted — the floor", gate_dte(date(2026, 9, 2), TODAY).passed)
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
    assert g.TRADING_SUSPENDED, "E42 stand-down must be active"
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


def test_e42_guard_survives_dry_run_false():
    """dry_run=False must refuse too - that is the path that sends real orders."""
    from deltax.execute import submit, ExecutionRefused
    legs = [{"symbol": "SPY260904P00760000", "side": "sell", "ratio": 1}]
    try:
        submit(legs=legs, qty=1, limit_price=1.50, dry_run=False)
        check("E42 live path refused", False, "LIVE submit RETURNED")
    except ExecutionRefused:
        check("E42 live path refused", True, "refused")
    except Exception as e:
        check("E42 live path refused", False, f"{type(e).__name__}: {e}")


def test_e42_screening_still_runs():
    """The stand-down must not blind the agent - it still evaluates and logs."""
    import deltax.gates as g
    check("E42 gate exists", hasattr(g, "gate_trading_enabled"), "present")
    body = open("deltax/gates.py").read().split("def evaluate(")[1].split("\ndef ")[0]
    check("E42 evaluate() still gates normally",
          "gate_trading_enabled()" not in body, "not short-circuited")


test_e42_submit_refuses_while_suspended()
test_e42_guard_survives_dry_run_false()
test_e42_screening_still_runs()

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)

