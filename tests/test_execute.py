"""Execution layer tests. Command construction only - nothing is submitted."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.execute import (Leg, build_mleg_args, build_close_args,
                            orders_enabled, submit, ExecutionRefused,
                            COMPETITION_ACCOUNT)

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

LEGS = [Leg("SPY260918P00760000", "sell"), Leg("SPY260918P00755000", "buy")]

print("\n── opening order ──")
a = build_mleg_args(LEGS, 2, 1.55)
check("order-class mleg", a[a.index("--order-class")+1] == "mleg")
check("limit type", a[a.index("--type")+1] == "limit")
check("price formatted to 2dp", a[a.index("--limit-price")+1] == "1.55")
check("day TIF on open", a[a.index("--time-in-force")+1] == "day")
legs = json.loads(a[a.index("--legs")+1])
check("two legs", len(legs) == 2)
check("short leg sells to open", legs[0]["position_intent"] == "sell_to_open")
check("long leg buys to open", legs[1]["position_intent"] == "buy_to_open")

print("\n── closing order ──")
c = build_close_args(LEGS, 2, 0.78)
cl = json.loads(c[c.index("--legs")+1])
check("sides flipped", cl[0]["side"] == "buy" and cl[1]["side"] == "sell")
check("intent is to close", all(l["position_intent"].endswith("_to_close") for l in cl))
check("GTC so the exit rests", c[c.index("--time-in-force")+1] == "gtc")

print("\n── input validation ──")
for bad, why in ((1, "one leg"), (5, "five legs")):
    try:
        build_mleg_args(LEGS * bad if bad > 1 else LEGS[:1], 1, 1.0)
        check(f"rejects {why}", False)
    except ValueError:
        check(f"rejects {why}", True)
try:
    build_mleg_args(LEGS, 0, 1.0); check("rejects qty 0", False)
except ValueError: check("rejects qty 0", True)

print("\n── safety switches ──")
os.environ.pop("DELTAX_ORDERS_ALLOWED", None)
check("orders disabled by default", not orders_enabled())
r = submit(LEGS, 2, 1.55, dry_run=True)
check("dry run does not submit", r["dry_run"] and "DRY_RUN" in r["result"])
check("dry run still records the command", r["command"].startswith("alpaca order submit"))
try:
    submit(LEGS, 2, 1.55, dry_run=False)
    check("live submit refused without env switch", False)
except ExecutionRefused as e:
    check("live submit refused without env switch", "DELTAX_ORDERS_ALLOWED" in str(e))
# E40: the pin follows DELTAX_ACCOUNT so switching the paper account does not
# halt every order. What must hold is that a pin EXISTS and is well-formed —
# not that it equals one particular account we may no longer be trading.
check("an account pin exists", bool(COMPETITION_ACCOUNT))
check("pin looks like an Alpaca paper account",
      COMPETITION_ACCOUNT.startswith("PA") and len(COMPETITION_ACCOUNT) >= 10,
      COMPETITION_ACCOUNT)
check("pin follows DELTAX_ACCOUNT when set",
      __import__("os").environ.get("DELTAX_ACCOUNT", COMPETITION_ACCOUNT) == COMPETITION_ACCOUNT)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
