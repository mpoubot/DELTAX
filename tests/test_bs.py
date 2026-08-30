"""Black-Scholes pricer tests. The 4-day sweep's conclusions rest on this."""
import sys, os
from math import exp, sqrt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backtest"))
from bs import call, put, condor_value, implied_vol, N, RATE

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")
def near(a, b, tol=1e-4): return abs(a - b) < tol

print("\n── normal CDF ──")
check("N(0) = 0.5", near(N(0), 0.5))
check("N(1.96) = 0.975", near(N(1.96), 0.975002, 1e-5))
check("N is symmetric", near(N(-1.3) + N(1.3), 1.0))
check("N is monotonic", N(-2) < N(-1) < N(0) < N(1) < N(2))

print("\n── put-call parity ──")
for S, K, T, v in ((100,100,0.25,0.20), (650,634,0.04,0.18), (50,55,1.0,0.35)):
    check(f"parity S={S} K={K}", near(call(S,K,T,v) - put(S,K,T,v), S - K*exp(-RATE*T)))

print("\n── known values ──")
check("ATM 1y call r=4% s=20% = 9.925", near(call(100,100,1.0,0.20), 9.92509, 1e-3))
check("deep ITM call -> S - Ke^-rT", near(call(200,50,0.1,0.15), 200-50*exp(-RATE*0.1), 1e-6))
check("deep OTM call -> 0", call(50,200,0.1,0.15) < 1e-6)

print("\n── boundaries ──")
check("T=0 call = intrinsic", near(call(110,100,0.0,0.2), 10.0))
check("T=0 put = intrinsic", near(put(90,100,0.0,0.2), 10.0))
check("T=0 OTM = 0", near(call(90,100,0.0,0.2), 0.0) and near(put(110,100,0.0,0.2), 0.0))
check("call >= 0 always", all(call(100,k,0.1,0.2) >= 0 for k in (50,100,200)))

print("\n── monotonicity ──")
check("call falls as strike rises", call(100,90,0.25,0.2) > call(100,100,0.25,0.2) > call(100,110,0.25,0.2))
check("put rises as strike rises", put(100,90,0.25,0.2) < put(100,100,0.25,0.2) < put(100,110,0.25,0.2))
check("value rises with vol", call(100,100,0.25,0.10) < call(100,100,0.25,0.30))

print("\n── condor ──")
v = condor_value(650, 634, 666, 5.0, 14/365, 0.18)
check("value within (0, 2*width)", 0 < v < 10.0, f"{v}")
check("decays with time",
      condor_value(650,634,666,5.0,14/365,0.18) > condor_value(650,634,666,5.0,10/365,0.18))
check("worth more as vol rises",
      condor_value(650,634,666,5.0,14/365,0.12) < condor_value(650,634,666,5.0,14/365,0.30))
check("near-zero when far OTM and calm",
      condor_value(650,500,800,5.0,7/365,0.10) < 0.01)

print("\n── implied vol calibration ──")
iv = implied_vol(2.30, 650, 634, 666, 5.0, 14/365)
check("solves", iv is not None)
check("round-trips to target", near(condor_value(650,634,666,5.0,14/365,iv), 2.30, 1e-6))
check("returns None when target unreachable",
      implied_vol(9.99, 650, 634, 666, 5.0, 14/365) is None)
check("higher credit implies higher vol",
      implied_vol(1.5,650,634,666,5.0,14/365) < implied_vol(3.0,650,634,666,5.0,14/365))

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
