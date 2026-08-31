"""Walk-forward the real-price configs. Does the edge survive out of sample?

180 configurations were tested and the best picked. That is textbook selection
bias, and E10 exists to catch exactly this. So: fit on TRAIN, test on data the
selection never saw, and apply a Bonferroni threshold for the number of
configurations actually searched.

A config passes only if it is positive in BOTH periods AND clears the corrected
significance bar out of sample.
"""
import sys, os, json, subprocess
from math import exp, log, sqrt
from statistics import mean, stdev
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from real_price_test import CREDIT_RATIO, Z, LOOK, bars, run, stats

N_SEARCHED = 180                     # configs scanned when the best was chosen
BONFERRONI_T = 1.96 + 0.62 * log(N_SEARCHED)


def split(bars_):
    idx = [(i, datetime.fromisoformat(b["t"].replace("Z", "+00:00")))
           for i, b in enumerate(bars_)]
    mons = [(i, d) for i, d in idx if d.weekday() == 0]
    return ([i for i, d in mons if d.year <= 2023],
            [i for i, d in mons if d.year >= 2024])


def main():
    print(f"WALK-FORWARD AT REAL PRICES\n")
    print(f"  TRAIN <=2023 · TEST >=2024 · {N_SEARCHED} configs searched")
    print(f"  Bonferroni threshold: t >= {BONFERRONI_T:.2f} out of sample\n")
    cfgs = [("IWM", 0.30, 20, 18, 4), ("IWM", 0.40, 20, 18, 4),
            ("IWM", 0.30, 20, 11, 4), ("IWM", 0.20, 20, 18, 4),
            ("SPY", 0.30, 20, 18, 4), ("SPY", 0.20, 20, 18, 4),
            ("SPY", 0.30, 10, 18, 4), ("QQQ", 0.30, 20, 18, 4),
            ("QQQ", 0.20, 20, 18, 4), ("IWM", 0.30, 10, 18, 4)]
    cache = {}
    print(f"{'sym':>5}{'δ':>6}{'w':>4}{'DTE':>5}{'hold':>5} │"
          f"{'TRAIN E':>9}{'n':>5} │{'TEST E':>8}{'win%':>7}{'t':>7}  verdict")
    survivors = []
    for sym, d, w, dte, hold in cfgs:
        if sym not in cache:
            cache[sym] = bars(sym)
        b = cache[sym]
        if len(b) < 300:
            continue
        c = [x["c"] for x in b]
        tr, te = split(b)
        a = stats(run(c, tr, d, w, dte, hold), w)
        z = stats(run(c, te, d, w, dte, hold), w)
        if not a or not z:
            continue
        passes = a["E"] > 0 and z["E"] > 0 and z["t"] >= BONFERRONI_T
        mark = "✅ SURVIVES" if passes else (
            "⚠️ positive, fails Bonferroni" if z["E"] > 0 else "❌ fails out of sample")
        print(f"{sym:>5}{d:>6.2f}{w:>4}{dte:>5}{hold:>5} │"
              f"{a['E']:>9.3f}{a['n']:>5} │{z['E']:>8.3f}{z['win']*100:>6.1f}%"
              f"{z['t']:>7.2f}  {mark}")
        if passes:
            survivors.append((sym, d, w, dte, hold, z))
    print()
    if survivors:
        print(f"  {len(survivors)} of {len(cfgs)} survive walk-forward AND Bonferroni:")
        for sym, d, w, dte, hold, z in sorted(survivors, key=lambda x: -x[5]["E"]):
            print(f"    {sym} δ{d} {w}-wide {dte}DTE hold {hold}d  →  "
                  f"out-of-sample E {z['E']:+.3f}  win {z['win']*100:.0f}%  t {z['t']:.1f}  n={z['n']}")
    else:
        print("  NOTHING survives. The in-sample result was selection bias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
