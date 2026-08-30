"""Long/short labelling. The mapping inverts with structure, so it is tested."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.screener import directional_bias

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

print("\n── credit spreads (what we trade) ──")
check("SELL put spread  -> LONG",  directional_bias("put","credit")[0]  == "LONG")
check("SELL call spread -> SHORT", directional_bias("call","credit")[0] == "SHORT")

print("\n── debit spreads: the mapping INVERTS ──")
check("BUY put spread  -> SHORT", directional_bias("put","debit")[0]  == "SHORT")
check("BUY call spread -> LONG",  directional_bias("call","debit")[0] == "LONG")

print("\n── the inversion is the whole point ──")
check("same side, opposite structure, opposite bias",
      directional_bias("put","credit")[0] != directional_bias("put","debit")[0])
check("same structure, opposite side, opposite bias",
      directional_bias("put","credit")[0] != directional_bias("call","credit")[0])

print("\n── labels are usable by a human ──")
for side, st in (("put","credit"),("call","credit"),("put","debit"),("call","debit")):
    b, e, note = directional_bias(side, st)
    check(f"{st} {side}: '{b}' {e} — {note}",
          b in ("LONG","SHORT") and len(e) > 0 and len(note) > 10)
check("unknown side is NEUTRAL, not guessed",
      directional_bias("iron_condor","credit")[0] == "NEUTRAL")

print("\n── ledger no longer overloads the words 'short'/'long' ──")
import inspect
from deltax import run as runmod
src = inspect.getsource(runmod)
check("records an explicit bias field", '"bias": bias' in src)
check("spread legs renamed to short_leg/long_leg", '"short_leg"' in src and '"long_leg"' in src)
check("ambiguous bare keys are gone",
      '"short": cand' not in src and '"long": cand' not in src)

print("\n── dashboard exposes it ──")
from deltax.dashboard import Position
from datetime import date, timedelta
p = Position("SPY","put",645,640,date.today()+timedelta(days=7),1,2.30,1.00,660.0)
check("put position reports LONG", p.bias[0] == "LONG", p.bias[0])
p = Position("SPY","call",678,683,date.today()+timedelta(days=7),1,2.25,1.00,660.0)
check("call position reports SHORT", p.bias[0] == "SHORT", p.bias[0])

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
