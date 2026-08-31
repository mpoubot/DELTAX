"""Dealer gamma map. Advisory only — it cannot be backtested (E38)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.gamma import build, gate_gamma_regime, GammaMap, _zero_crossing

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

def chain(rows):
    """rows: [(strike, 'C'|'P', gamma, oi)]"""
    ch, oi = {}, {}
    for k, kind, g, o in rows:
        occ = f"SPY260904{kind}{int(k*1000):08d}"
        ch[occ] = {"greeks": {"gamma": g}}
        oi[occ] = o
    return ch, oi

print("\n── sign convention: calls positive, puts negative ──")
ch, oi = chain([(770, "C", 0.02, 5000)] * 1)
m = build("SPY", 766.0, ch, oi | {k: 5000 for k in ch})
ch2, oi2 = chain([(760, "P", 0.02, 5000)])
m2 = build("SPY", 766.0, ch2, oi2)
check("a call-only book is positive gamma", m.total > 0 or not m.complete)
check("a put-only book is negative gamma", m2.total < 0 or not m2.complete)

print("\n── regime and the gate ──")
big = [(760 + i, "C", 0.02, 8000) for i in range(15)]
ch, oi = chain(big)
mp = build("SPY", 766.0, ch, oi)
check("enough strikes builds a complete map", mp.complete, str(mp.complete))
check("positive book -> POSITIVE", mp.regime == "POSITIVE", mp.regime)
check("and premium selling is favoured", mp.premium_selling_favoured)
ok, why = gate_gamma_regime(mp)
check("gate allows a positive regime", ok, why)

neg = [(760 + i, "P", 0.02, 8000) for i in range(15)]
ch, oi = chain(neg)
mn = build("SPY", 766.0, ch, oi)
check("negative book -> NEGATIVE", mn.regime == "NEGATIVE", mn.regime)
ok, why = gate_gamma_regime(mn)
check("gate refuses a negative regime when required", not ok, why)
ok, why = gate_gamma_regime(mn, require_positive=False)
check("ADVISORY mode never blocks — E10, it is unbacktested", ok, why)

print("\n── fails OPEN, unlike the earnings gate ──")
check("no map does not block", gate_gamma_regime(None)[0])
check("empty chain does not block", gate_gamma_regime(build("X", 100.0, {}, {}))[0])
thin = build("SPY", 766.0, *chain([(760, "C", 0.02, 100)]))
check("a thin chain is incomplete", not thin.complete)
check("and does not block", gate_gamma_regime(thin)[0])
check("incomplete reports UNKNOWN, never a guess", thin.regime == "UNKNOWN")

print("\n── pin and flip ──")
rows = [(750, "C", 0.01, 1000), (770, "C", 0.05, 9000), (780, "C", 0.01, 1000)]
rows += [(755 + i, "C", 0.005, 700) for i in range(12)]
m = build("SPY", 766.0, *chain(rows))
check("pin is the heaviest positive strike", m.pin == 770.0, str(m.pin))
check("flip crossing returns None when never crossing",
      _zero_crossing({760.0: 5.0, 770.0: 5.0}, 766.0) is None)
check("flip found when cumulative GEX changes sign",
      _zero_crossing({760.0: -5.0, 770.0: 10.0}, 766.0) is not None)

print("\n── it is a gate, never an originator ──")
import inspect
from deltax import gamma as gm
src = inspect.getsource(gm)
check("no code path returns a trade or a size",
      "def size" not in src and "return {'trade'" not in src)
check("gate returns only (allowed, reason)", len(gate_gamma_regime(mp)) == 2)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
