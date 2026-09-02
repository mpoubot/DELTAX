"""Exit management. The 50% exit is where the measured edge lives (E15)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.manage import (Managed, exit_limit, place_exit, manage,
                           TAKE_PROFIT_FRACTION, TIME_STOP_DTE)
from deltax.execute import Leg

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

print("\n── exit price ──")
check("half of a 2.30 credit is 1.15", exit_limit(2.30) == 1.15, str(exit_limit(2.30)))
check("half of a 0.92 credit is 0.46", exit_limit(0.92) == 0.46, str(exit_limit(0.92)))
check("rounded to a tradeable tick", exit_limit(1.111) == round(1.111*0.5, 2))
check("target matches E5/E15", TAKE_PROFIT_FRACTION == 0.50)

print("\n── when to close ──")
check("56% captured closes", Managed("SPY",7,2.30,1.02,7).reason() is not None)
check("exactly 50% closes", Managed("SPY",7,2.00,1.00,7).reason() is not None)
check("49% holds", Managed("SPY",7,2.00,1.02,7).reason() is None)
check("12% holds", Managed("SPY",7,2.25,1.98,7).reason() is None)
# E22/E57: derive from the live constant. These hardcoded 2 and broke silently
# when E57 cut TIME_STOP_DTE to 1 - the value has moved twice now, so assert the
# BEHAVIOUR at the threshold rather than a particular number of days.
check("at the time stop, closes even on a small profit",
      "time stop" in (Managed("IWM",18,0.92,0.61,TIME_STOP_DTE).reason() or ""),
      f"TIME_STOP_DTE={TIME_STOP_DTE}")
check("inside the time stop, closes even at a LOSS",
      Managed("IWM",18,0.92,1.40,max(TIME_STOP_DTE-1,0)).reason() is not None)
check("one day outside the time stop, a small profit holds",
      Managed("IWM",18,0.92,0.85,TIME_STOP_DTE+1).reason() is None)
check("7 DTE with small profit holds", Managed("IWM",18,0.92,0.85,7).reason() is None)

print("\n── never guess a price ──")
m = Managed("MA",7,2.40,None,7)
check("unpriceable position reports no capture", m.captured is None)
check("unpriceable position is NOT closed", m.reason() is None)
check("zero entry credit does not divide by zero", Managed("X",1,0.0,1.0,7).captured is None)

print("\n── sweep ──")
out = manage([Managed("SPY",7,2.30,1.02,7),                 # target hit
              Managed("QQQ",7,2.25,1.98,7),                 # hold
              Managed("IWM",18,0.92,0.61,TIME_STOP_DTE),    # time stop
              Managed("MA",7,2.40,None,7)],                 # unpriceable
             dry_run=True)
check("closes the two that qualify", len(out["closed"]) == 2, str(out["closed"]))
check("holds the one that does not", out["held"] == ["QQQ"], str(out["held"]))
check("reports the unpriceable one rather than closing it",
      out["unpriceable"] == ["MA"], str(out["unpriceable"]))

print("\n── exit order shape ──")
legs = [Leg("SPY260911P00750000","sell"), Leg("SPY260911P00745000","buy")]
r = place_exit(legs, 7, 2.30, dry_run=True)
check("dry run does not place", "DRY_RUN" in r["result"])
check("limit is half the credit", r["limit_price"] == 1.15)
check("order rests GTC", "gtc" in r["command"])
check("sides are flipped to close", "buy_to_close" in r["command"] and "sell_to_close" in r["command"])
check("entry credit is recorded", r["entry_credit"] == 2.30)

print("\n── ledger ──")
class L:
    def __init__(self): self.rows=[]
    def record_raw(self, d): self.rows.append(d)
led = L(); place_exit(legs, 7, 2.30, ledger=led, dry_run=True)
check("exit order is recorded", len(led.rows) == 1 and led.rows[0]["action"] == "exit_order")
led2 = L(); manage([Managed("SPY",7,2.30,1.02,7)], ledger=led2, dry_run=True)
check("close is recorded with its reason",
      led2.rows and "target hit" in led2.rows[0]["reason"])

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
