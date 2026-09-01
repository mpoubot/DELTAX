"""Guards on research/backtest/weekly.py.

Every one of these encodes a defect that was actually present in the 31 Aug
backtest whose -$50,904 result triggered the E42 stand-down.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "research", "backtest"))
from weekly import leg_pnl, regime, realized_vol, Z, TP_FRAC, LOOKBACK
from math import exp, sqrt

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if not isinstance(name, str) or not isinstance(cond, (bool, type(None))):
        raise TypeError("check(label:str, cond:bool, detail)")
    if cond: passed += 1; print(f"  ✓ {name}")
    else: failed += 1; print(f"  ✗ {name}  {detail}")

W, D, DTE, SIG = 20.0, 0.30, 3, 0.20

print("── B2/B3: the payoff inversion must be gone ──")
clean, credit, kp = leg_pnl("put", 100.0, 101.0, SIG, DTE, D, W)
brea, _, _ = leg_pnl("put", 100.0, kp - 1.0, SIG, DTE, D, W)
recov, _, _ = leg_pnl("put", 100.0, kp + 0.01, SIG, DTE, D, W)
check("clean trade earns take-profit", abs(clean - credit * TP_FRAC) < 1e-9,
      f"{clean:.4f} vs {credit*TP_FRAC:.4f}")
check("no breach ever out-earns a clean trade", brea <= clean + 1e-9,
      f"breach {brea:.3f} > clean {clean:.3f}")
deep = leg_pnl("put", 100.0, kp - credit - 0.5, SIG, DTE, D, W)[0]
check("a breach past the credit turns the trade negative", deep < 0, f"{deep:.3f}")
ladder = [leg_pnl("put", 100.0, kp - x, SIG, DTE, D, W)[0]
          for x in (0.0, 1.0, 3.0, 6.0, 12.0, 25.0)]
check("payoff is monotonically non-increasing in the breach depth",
      all(a >= b - 1e-9 for a, b in zip(ladder, ladder[1:])),
      " ".join(f"{v:.2f}" for v in ladder))
check("payoff can never exceed the resting take-profit",
      max(ladder) <= credit * TP_FRAC + 1e-9, f"{max(ladder):.3f}")
check("recovering above the strike never out-earns a clean trade",
      recov <= clean + 1e-9, f"recovered {recov:.3f} > clean {clean:.3f}")
check("deep breach is capped at width minus credit",
      abs(leg_pnl("put", 100.0, 1.0, SIG, DTE, D, W)[0] - (credit - W)) < 1e-9)

print("\n── B1: strike is placed on the sigma it is handed ──")
_, _, k_lo = leg_pnl("put", 100.0, 100.0, 0.10, DTE, D, W)
_, _, k_hi = leg_pnl("put", 100.0, 100.0, 0.30, DTE, D, W)
check("higher implied vol pushes the put strike further out", k_hi < k_lo,
      f"iv0.10 -> {k_lo:.3f}, iv0.30 -> {k_hi:.3f}")
check("strike matches the closed form",
      abs(k_lo - 100.0 * exp(-Z[D] * 0.10 * sqrt(DTE/365.0))) < 1e-9)

print("\n── call side mirrors the put side ──")
cc, ccr, kc = leg_pnl("call", 100.0, 99.0, SIG, DTE, D, W)
check("call strike sits above spot", kc > 100.0, f"{kc:.3f}")
check("call collects the same credit as the put", abs(ccr - credit) < 1e-9)
cladder = [leg_pnl("call", 100.0, kc + x, SIG, DTE, D, W)[0]
           for x in (0.0, 1.0, 3.0, 6.0, 12.0, 25.0)]
check("call payoff is monotonically non-increasing in the rally",
      all(a >= b - 1e-9 for a, b in zip(cladder, cladder[1:])),
      " ".join(f"{v:.2f}" for v in cladder))
check("a deep rally turns the call spread negative", cladder[-1] < 0, f"{cladder[-1]:.3f}")

print("\n── B4: the regime filter actually filters ──")
up   = [100.0 + i * 0.5 for i in range(LOOKBACK + 1)]
down = [100.0 - i * 0.5 for i in range(LOOKBACK + 1)]
flat = [100.0] * (LOOKBACK + 1)
check("uptrend sells puts",   regime(up,   len(up) - 1) == "put")
check("downtrend sells calls", regime(down, len(down) - 1) == "call")
check("flat tape stands aside", regime(flat, len(flat) - 1) is None)

print("\n── sanity on realized vol ──")
check("flat series has zero vol", realized_vol(flat, len(flat) - 1) == 0.0)
check("vol is positive on a moving series", realized_vol(up, len(up) - 1) > 0)

print("\n── B5: an early exit must pay for remaining time value ──")
from weekly import spread_value
flat_e, cr_e, k_e = leg_pnl("put", 100.0, 100.0, SIG, DTE, D, W, hold=1)
flat_f, _, _      = leg_pnl("put", 100.0, 100.0, SIG, DTE, D, W, hold=DTE)
check("closing early earns less than holding to expiry on an unchanged tape",
      flat_e < flat_f - 1e-9, f"early {flat_e:.4f} vs expiry {flat_f:.4f}")
check("early exit still earns something on an unchanged tape", flat_e > 0,
      f"{flat_e:.4f}")
ladder = [leg_pnl("put", 100.0, 100.0, SIG, DTE, D, W, hold=h)[0] for h in (1, 2, 3)]
check("profit grows monotonically with days held",
      all(a <= b + 1e-9 for a, b in zip(ladder, ladder[1:])),
      " ".join(f"{v:.3f}" for v in ladder))
check("early exit is still capped by the resting take-profit",
      max(ladder) <= cr_e * TP_FRAC + 1e-9, f"{max(ladder):.4f}")
adverse = leg_pnl("put", 100.0, k_e - 8.0, SIG, DTE, D, W, hold=1)[0]
check("an adverse move loses money even on an early exit", adverse < 0, f"{adverse:.3f}")
check("early-exit loss respects the defined-risk floor",
      adverse >= cr_e - W - 1e-9, f"{adverse:.3f} vs floor {cr_e - W:.3f}")
check("spread value decays toward intrinsic as time runs out",
      spread_value("put", 100.0, 100.0, W, 0.0001, SIG)
      < spread_value("put", 100.0, 100.0, W, 3/365.0, SIG))

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
