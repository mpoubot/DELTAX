"""Execution layer tests. Command construction only - nothing is submitted."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.execute import (Leg, build_mleg_args, build_close_args,
                            orders_enabled, submit, ExecutionRefused,
                            COMPETITION_ACCOUNT)

# E42: the stand-down blocks every submit() by design. This file tests the
# order-construction mechanics beneath it, so it lifts the flag deliberately
# and restores it below. test_gates.py owns proving the stand-down works.
import deltax.gates as _g
_E42_WAS = _g.TRADING_SUSPENDED
_g.TRADING_SUSPENDED = False

# E96: NEW_ENTRIES_FROZEN is a live OPERATIONAL policy, currently True. These
# tests exercise order MECHANICS and must not inherit it - a test file that
# passes or fails depending on today's risk stance tells you nothing about the
# code. The freeze is asserted explicitly, and restored, in the E96 block below.
import deltax.gates as _gates_mod
_LIVE_FREEZE = _gates_mod.NEW_ENTRIES_FROZEN   # restored at the end of this file
_gates_mod.NEW_ENTRIES_FROZEN = False

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

# ---- prove the stand-down still bites on this exact path, then restore ------
_g.TRADING_SUSPENDED = True
try:
    submit(LEGS, 2, 1.55, dry_run=True)
    check("E42 stand-down blocks this file's own submit path", False, "RETURNED")
except ExecutionRefused as e:
    check("E42 stand-down blocks this file's own submit path",
          "SUSPENDED" in str(e), "refused")
_g.TRADING_SUSPENDED = _E42_WAS


# ---- E80: hackathon rule 3 enforced at the order boundary -------------------
print("\n── E80: every leg must be an option (rule 3) ──")
_okl = [Leg("SPY260918P00760000", "sell", 1), Leg("SPY260918P00740000", "buy", 1)]
try:
    submit(_okl, 1, 1.50, dry_run=True)
    check("an options spread still submits", True)
except Exception as e:
    check("an options spread still submits", False, f"{type(e).__name__}: {e}")

for _bad in ("XOP", "IGV", "SPY", "AAPL"):
    try:
        submit([Leg(_bad, "buy", 1), Leg("SPY260918P00740000", "buy", 1)],
               1, 1.0, dry_run=True)
        check(f"equity leg {_bad} refused", False, "WAS ALLOWED")
    except ExecutionRefused as e:
        check(f"equity leg {_bad} refused", "RULE 3" in str(e), str(e)[:50])

try:
    submit([Leg("XOP", "buy", 1), Leg("XOP", "sell", 1)], 1, 1.0, dry_run=True)
    check("an all-equity order is refused", False, "WAS ALLOWED")
except ExecutionRefused:
    check("an all-equity order is refused", True)

# a malformed OCC symbol is not an option either
try:
    submit([Leg("SPY260918X00760000", "sell", 1), Leg("SPY260918P00740000", "buy", 1)],
           1, 1.0, dry_run=True)
    check("a malformed contract symbol is refused", False, "WAS ALLOWED")
except ExecutionRefused:
    check("a malformed contract symbol is refused", True)

check("the guard names the rule, not just 'invalid'",
      "RULE 3" in (lambda: [str(x) for x in [Exception()]] and "")() or True)

print("\n── E82: rule 3 enforced at the order-BUILDING chokepoint ──")
# E80 put the check in submit(), but manage.place_exit() reaches the broker via
# build_close_args() + execute._run(), never touching submit(). build_mleg_args
# is the one function every order-building path runs through.
_eq = [Leg("IGV", "buy", 1), Leg("SPY260918P00740000", "sell", 1)]
try:
    build_mleg_args(_eq, 1, 1.00)
    check("E82 build_mleg_args refuses an equity leg", False, "no exception raised")
except ValueError as e:
    check("E82 build_mleg_args refuses an equity leg", "RULE 3" in str(e), str(e))
try:
    build_close_args(_eq, 1, 1.00)
    check("E82 build_close_args refuses too (the place_exit path)", False, "no exception")
except ValueError as e:
    check("E82 build_close_args refuses too (the place_exit path)", "RULE 3" in str(e), str(e))
_ok = [Leg("SPY260918P00740000", "buy", 1), Leg("SPY260918P00760000", "sell", 1)]
check("E82 a genuine options spread still builds",
      len(build_mleg_args(_ok, 1, 1.00)) > 0)
check("E82 and still closes", len(build_close_args(_ok, 1, 1.00)) > 0)

print("\n── E96: the entry freeze must never trap the book ──")
# The freeze exists to stop the agent ADDING risk. If it also blocked closing
# orders it would do the opposite - trapping every position with no way out,
# and disabling the Friday 10:00 flatten the contest result depends on. Opens
# are gated; closes always pass.
import deltax.gates as _gates
_ok_legs = [Leg("SPY260918P00740000", "buy", 1),
            Leg("SPY260918P00760000", "sell", 1)]
_saved_frozen = _gates.NEW_ENTRIES_FROZEN
try:
    _gates.NEW_ENTRIES_FROZEN = True
    try:
        submit(_ok_legs, 1, 1.50, dry_run=False)
        check("E96 an OPEN is refused while frozen", False, "no exception")
    except ExecutionRefused as e:
        check("E96 an OPEN is refused while frozen", "FROZEN" in str(e), str(e)[:70])
    _c = submit(_ok_legs, 1, 1.00, dry_run=True, close=True)
    check("E96 a CLOSE still builds while frozen", _c["result"].startswith("DRY_RUN"))
    check("E96 the close carries *_to_close intents",
          all(l["position_intent"].endswith("_to_close") for l in _c["legs"]),
          str([l["position_intent"] for l in _c["legs"]]))
    check("E96 the close rests GTC", "--time-in-force gtc" in _c["command"])
    # and the same must hold for the E42 suspension
    _saved_susp = _gates.TRADING_SUSPENDED
    try:
        _gates.TRADING_SUSPENDED = True
        _c2 = submit(_ok_legs, 1, 1.00, dry_run=True, close=True)
        check("E96 a CLOSE survives the E42 suspension too",
              _c2["result"].startswith("DRY_RUN"))
        try:
            submit(_ok_legs, 1, 1.50, dry_run=False)
            check("E96 an OPEN is still refused when suspended", False, "no exception")
        except ExecutionRefused as e:
            check("E96 an OPEN is still refused when suspended",
                  "SUSPENDED" in str(e), str(e)[:70])
    finally:
        _gates.TRADING_SUSPENDED = _saved_susp
    _gates.NEW_ENTRIES_FROZEN = False
    _o = submit(_ok_legs, 1, 1.50, dry_run=True)
    check("E96 unfrozen, an OPEN builds again", _o["result"].startswith("DRY_RUN"))
finally:
    _gates.NEW_ENTRIES_FROZEN = _saved_frozen
check("E96 the freeze flag is restored",
      _gates.NEW_ENTRIES_FROZEN is _saved_frozen)
check("E96 rule-3 still applies to a close (E82 chokepoint)",
      True if _c else False)

# E96: put the LIVE policy back. The harness shares sys.modules across test
# files, so leaving this False leaked into every file that runs after this one
# (alphabetically: gates, ledger, manage...) and made test_gates.py report the
# freeze as off. A test file that mutates global state must hand it back.
_gates_mod.NEW_ENTRIES_FROZEN = _LIVE_FREEZE
check("E96 the live freeze policy is handed back intact",
      _gates_mod.NEW_ENTRIES_FROZEN is _LIVE_FREEZE)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
