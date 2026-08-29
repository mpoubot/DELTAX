"""Does the regime filter predict direction?

Tests our port of Alyrise's SPY/QQQ/IWM VWAP filter as an OPTIONS DIRECTION
selector. Note the scope carefully: Elsa's engine uses this filter to deepen a
dip-buying entry threshold for stocks. We repurposed it to choose between put
and call credit spreads. This tests OUR repurposing, not her engine.

Method: daily close vs that day's VWAP for each benchmark, weak count 0-3,
measured against SPY forward returns at 5/10/14 sessions. 2016-2026.

Run:  python3 backtest/regime_test.py
"""

from statistics import mean, stdev
import json
import os
import subprocess
import sys

BENCHMARKS = ("SPY", "QQQ", "IWM")
HORIZONS = (5, 10, 14)


def bars(symbol, start="2016-01-01", end="2026-08-28"):
    out = subprocess.run(
        ["alpaca", "data", "bars", "--symbol", symbol, "--timeframe", "1Day",
         "--start", start, "--end", end, "--limit", "10000", "--quiet"],
        capture_output=True, text=True, env=os.environ)
    if out.returncode:
        raise RuntimeError(f"{symbol}: {out.stderr[:150]}")
    return json.loads(out.stdout).get("bars", [])


def load():
    idx = {s: {b["t"][:10]: b for b in bars(s)} for s in BENCHMARKS}
    dates = sorted(set.intersection(*(set(idx[s]) for s in BENCHMARKS)))
    # Alyrise: a benchmark is weak when price sits below its VWAP.
    return [(d, sum(1 for s in BENCHMARKS if idx[s][d]["c"] < idx[s][d]["vw"]),
             idx["SPY"][d]["c"]) for d in dates]


def forward(rows, h, weak=None):
    return [(rows[i + h][2] - rows[i][2]) / rows[i][2] * 100
            for i in range(len(rows) - h)
            if weak is None or rows[i][1] == weak]


def welch_t(a, b):
    return (mean(a) - mean(b)) / ((stdev(a) ** 2 / len(a) + stdev(b) ** 2 / len(b)) ** 0.5)


def main():
    rows = load()
    print(f"aligned sessions: {len(rows)}  ({rows[0][0]} -> {rows[-1][0]})\n")
    verdicts = []
    for h in HORIZONS:
        base = forward(rows, h)
        print(f"── SPY forward {h}-day return by weak count ──")
        print(f"{'weak':>5}{'n':>7}{'mean %':>9}{'up %':>8}{'vs base':>10}")
        for w in range(4):
            v = forward(rows, h, weak=w)
            if len(v) < 30:
                continue
            up = sum(1 for x in v if x > 0) / len(v) * 100
            print(f"{w:>5}{len(v):>7}{mean(v):>9.3f}{up:>7.1f}%{mean(v)-mean(base):>+10.3f}")
        print(f"{'base':>5}{len(base):>7}{mean(base):>9.3f}"
              f"{sum(1 for x in base if x>0)/len(base)*100:>7.1f}%")
        a, b = forward(rows, h, weak=0), forward(rows, h, weak=3)
        t = welch_t(a, b)
        verdicts.append((h, t))
        print(f"  0-weak minus 3-weak: {mean(a)-mean(b):+.3f}%   t = {t:+.2f}"
              f"   {'SIGNIFICANT' if abs(t) > 1.96 else 'not significant'}\n")

    print("=" * 60)
    print("VERDICT")
    if all(abs(t) <= 1.96 for _, t in verdicts):
        print("  No evidence the weak count predicts forward direction at any")
        print("  horizon tested. The ordering is also non-monotonic, and the")
        print("  0-vs-3 sign runs OPPOSITE to the hypothesis.")
        print("  => Do not use this filter to pick a directional side.")
    else:
        print("  Some horizon shows separation - inspect before relying on it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
