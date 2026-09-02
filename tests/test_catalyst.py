"""E58 catalyst-rule guards.

The rule BUYS premium, which nothing else in this system does, so every refusal
path is tested explicitly. A setup that cannot refuse is not a setup.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date
from deltax.catalyst import (occ, catalyst_active, price_vertical, legs_for,
                             Vertical, MAX_DEBIT, MIN_LEG_OI, RISK_BUDGET,
                             MAX_OI_FRACTION, CATALYST_MIN_MOVE_PCT)

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if not isinstance(name, str) or not isinstance(cond, (bool, type(None))):
        raise TypeError("check(label:str, cond:bool, detail)")
    if cond: passed += 1; print(f"  ✓ {name}")
    else: failed += 1; print(f"  ✗ {name}  {detail}")


print("── OCC symbol construction ──")
check("145 call builds correctly",
      occ("USO", date(2026, 9, 4), "C", 145.0) == "USO260904C00145000",
      occ("USO", date(2026, 9, 4), "C", 145.0))
check("150 call builds correctly",
      occ("USO", date(2026, 9, 4), "C", 150.0) == "USO260904C00150000")
check("fractional strikes round correctly",
      occ("USO", date(2026, 9, 4), "C", 145.5) == "USO260904C00145500")


print("\n── catalyst: BOTH confirmations required, fails closed ──")
NEWS = [{"headline": f"Hormuz tension {i}", "summary": "crude supply"} for i in range(5)]
ok, why = catalyst_active(133.70, 141.00, NEWS)
check("live shock + corroboration -> active", ok, why)
ok, why = catalyst_active(133.70, 134.50, NEWS)
check("move below trigger -> inactive", not ok, why)
ok, why = catalyst_active(133.70, 141.00, [])
check("no headlines -> inactive (fails closed)", not ok, why)
ok, why = catalyst_active(133.70, 141.00, [{"headline": "earnings", "summary": ""}])
check("uncorroborated headlines -> inactive", not ok, why)
ok, why = catalyst_active(None, 141.00, NEWS)
check("missing price -> inactive (fails closed)", not ok, why)
ok, why = catalyst_active(0.0, 141.00, NEWS)
check("zero prev close does not divide by zero", not ok, why)


class FakeFeed:
    """Controllable book. Defaults mirror the live 2 Sep pre-open quotes for
    the E59 re-strike: 140c 2.89/3.05, 145c 1.07/1.12, OI 2421/7745."""
    def __init__(self, long_ask=3.05, long_bid=2.89, short_bid=1.07,
                 short_ask=1.12, long_oi=2421, short_oi=7745, listed=True,
                 raise_on=False):
        self.__dict__.update(locals()); del self.self
    def option_contracts(self, u, **kw):
        if self.raise_on: raise RuntimeError("feed down")
        return [{"symbol": "USO260904C00140000", "open_interest": str(self.long_oi)},
                {"symbol": "USO260904C00145000", "open_interest": str(self.short_oi)}]
    def option_chain(self, u, **kw):
        if self.raise_on: raise RuntimeError("feed down")
        if not self.listed: return {}
        return {
            "USO260904C00140000": {"latestQuote": {"ap": self.long_ask, "bp": self.long_bid}},
            "USO260904C00145000": {"latestQuote": {"ap": self.short_ask, "bp": self.short_bid}},
        }


print("\n── pricing: pay the ask, receive the bid ──")
v = price_vertical(FakeFeed())
check("prices at ask minus bid, never mid", v.debit == 1.98, str(v.debit))
check("accepted at a debit inside the ceiling", v.ok, v.reason)
check("breakeven is long strike plus debit", v.breakeven == 141.98, str(v.breakeven))
check("exit is capped INSIDE the width (E59: 3x $1.98 = $5.94 > $5 width)",
      v.exit_limit == 3.96 and v.exit_limit < 5.0, str(v.exit_limit))
deep = price_vertical(FakeFeed(long_ask=3.55))         # debit 2.48, 2x = 4.96 > 4.50
check("exit never exceeds 90% of width",
      deep.exit_limit is not None and deep.exit_limit <= 4.50,
      str(deep.exit_limit))

print("\n── sizing derives from the ACTUAL debit, never a fixed count ──")
check("$1.98 -> 37 contracts at the $7,500 budget", v.contracts == 37, str(v.contracts))
check("risk is the debit paid", v.max_loss == 7326.0, str(v.max_loss))
check("max profit uses width minus debit",
      v.max_profit == round((5.0 - 1.98) * 100 * 37, 2), str(v.max_profit))
v220 = price_vertical(FakeFeed(long_ask=3.27))         # debit 2.20
check("$2.20 -> 34 contracts", v220.contracts == 34, str(v220.contracts))
v250 = price_vertical(FakeFeed(long_ask=3.57))         # debit 2.50 = ceiling
check("$2.50 (the ceiling) -> 30 contracts", v250.contracts == 30, str(v250.contracts))
check("risk never exceeds the budget",
      all(x.max_loss <= RISK_BUDGET for x in (v, v220, v250)),
      f"{v.max_loss}, {v220.max_loss}, {v250.max_loss}")

print("\n── every refusal path ──")
over = price_vertical(FakeFeed(long_ask=3.58))         # debit 2.51
check("a debit one cent over the ceiling REFUSES", not over.ok, over.reason)
check("refusal names the ceiling", "ceiling" in over.reason, over.reason)
thin = price_vertical(FakeFeed(long_oi=100))
check("thin open interest refuses", not thin.ok, thin.reason)
thin2 = price_vertical(FakeFeed(short_oi=int(MIN_LEG_OI - 1)))
check("thin SHORT leg refuses too", not thin2.ok, thin2.reason)
wide = price_vertical(FakeFeed(long_ask=3.05, long_bid=0.10))
check("a wide book refuses", not wide.ok, wide.reason)
crossed = price_vertical(FakeFeed(long_ask=0.90, short_bid=1.07))
check("non-positive debit refuses", not crossed.ok, crossed.reason)
missing = price_vertical(FakeFeed(listed=False))
check("unlisted legs refuse", not missing.ok, missing.reason)
broken = price_vertical(FakeFeed(raise_on=True))
check("a broken feed refuses rather than raising", not broken.ok, broken.reason)
noask = price_vertical(FakeFeed(long_ask=0.0))
check("no ask on the long leg refuses", not noask.ok, noask.reason)

print("\n── open-interest cap ──")
# 600 OI -> cap 30, below the 50 the $1.98 debit would otherwise size to.
capped = price_vertical(FakeFeed(long_oi=600, short_oi=600))
check("size is capped at 5% of the thinner leg",
      capped.contracts == int(600 * MAX_OI_FRACTION), str(capped.contracts))
check("the cap is recorded, not silent", "oi_capped" in capped.detail, str(capped.detail))

print("\n── execution legs ──")
lg = legs_for(v)
check("two legs", len(lg) == 2)
check("buys the low strike", lg[0].symbol.endswith("00140000") and lg[0].side == "buy")
check("sells the high strike", lg[1].symbol.endswith("00145000") and lg[1].side == "sell")
check("legs open positions",
      all(l.to_dict()["position_intent"].endswith("_to_open") for l in lg))

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
