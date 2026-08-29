"""Unit tests for the DELTAX risk gates. No network, no market connection."""

import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from deltax.gates import (
    evaluate, size_from_risk, Decision,
    PER_POSITION_RISK_PCT, PORTFOLIO_RISK_PCT,
    gate_expectancy, gate_dte, gate_liquidity, gate_reward_risk,
    gate_portfolio_risk, gate_defined_risk, gate_no_earnings_before_expiry,
)

EQUITY = 100_000.0
TODAY = date(2026, 8, 31)
GOOD_EXPIRY = date(2026, 9, 14)   # 14 DTE — inside the band

passed = failed = 0

def check(name, cond, detail=""):
    global passed, failed
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
check("2 DTE rejected", not gate_dte(date(2026, 9, 2), TODAY).passed)
check("14 DTE accepted", gate_dte(GOOD_EXPIRY, TODAY).passed)
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
check("earnings before expiry vetoes", not gate_no_earnings_before_expiry(date(2026, 9, 5), GOOD_EXPIRY).passed)
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
    credit=1.60, expiry=GOOD_EXPIRY, today=TODAY,
    open_interest=12_000, short_delta=0.30,
)
check("OTM credit spread now TRADES", d.decision == Decision.TRADE, d.failed_gate or "")
check("credit_fraction gate ran", any(g.gate == "credit_fraction" for g in d.gates))
check("reward_risk gate NOT applied to credit", not any(g.gate == "reward_risk" for g in d.gates))
# thin credit rejected: $5 wide, $0.90 credit = 18% of width
d = evaluate(
    symbol="SPY", equity=EQUITY, structure="credit", width=5.0,
    max_loss_per_contract=410.0, max_profit_per_contract=90.0,
    credit=0.90, expiry=GOOD_EXPIRY, today=TODAY, open_interest=12_000,
    short_delta=0.30,
)
check("credit below 0.9 x delta refused", d.decision == Decision.REFUSE and d.failed_gate == "credit_fraction")
check("delta-relative floor: 0.20 delta needs 18% of width",
      gate_credit_fraction(0.95, 5.0, 0.20).passed and not gate_credit_fraction(0.85, 5.0, 0.20).passed)
check("delta-relative floor: 0.35 delta needs 31.5% of width",
      gate_credit_fraction(1.60, 5.0, 0.35).passed and not gate_credit_fraction(1.50, 5.0, 0.35).passed)
check("sign of delta is irrelevant (puts are negative)",
      gate_credit_fraction(0.95, 5.0, -0.20).passed)
check("no delta -> flat fallback floor 0.20",
      gate_credit_fraction(1.05, 5.0).passed and not gate_credit_fraction(0.95, 5.0).passed)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
