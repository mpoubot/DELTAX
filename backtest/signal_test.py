"""Does Matin's Equity Lab signal family predict forward direction?

Signal (on a completed daily bar):
    EMA3 crosses above EMA8   AND   MACD histogram > 0   AND   RelVol >= X

Entry is the NEXT session's open, per his stated discipline - so the decision
bar never sees data it would not have had. Forward return is measured from
that open, over horizons matching our 7-21 DTE band.

Compared against the unconditional base rate for the same universe and period,
which is the honest null: a signal must beat "own the same names at random
times", not merely be positive in a market that drifts up.

Run:  python3 backtest/signal_test.py
"""

from statistics import mean, stdev
import json
import os
import subprocess
import sys

UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL",
            "TSLA", "AVGO", "COST", "NFLX", "AMD", "JPM"]
HORIZONS = (5, 10, 15)
RELVOL_VARIANTS = (1.0, 1.5, 2.0)     # his floor, ours, and stricter


def bars(symbol, start="2016-01-01", end="2026-08-28"):
    out = subprocess.run(
        ["alpaca", "data", "bars", "--symbol", symbol, "--timeframe", "1Day",
         "--start", start, "--end", end, "--limit", "10000", "--quiet"],
        capture_output=True, text=True, env=os.environ)
    if out.returncode:
        raise RuntimeError(f"{symbol}: {out.stderr[:120]}")
    return json.loads(out.stdout).get("bars", [])


def ema(vals, span):
    k, out, prev = 2 / (span + 1), [], None
    for v in vals:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def macd_hist(closes):
    line = [a - b for a, b in zip(ema(closes, 12), ema(closes, 26))]
    return [l - s for l, s in zip(line, ema(line, 9))]


def signals(bs, relvol_min):
    """Indices i where the signal fires on bar i (entry at open of i+1)."""
    c = [b["c"] for b in bs]
    v = [b["v"] for b in bs]
    e3, e8, hist = ema(c, 3), ema(c, 8), macd_hist(c)
    out = []
    for i in range(30, len(bs) - 1):
        crossed = e3[i] > e8[i] and e3[i - 1] <= e8[i - 1]
        if not crossed or hist[i] <= 0:
            continue
        avg20 = sum(v[i - 20:i]) / 20
        if avg20 > 0 and v[i] / avg20 >= relvol_min:
            out.append(i)
    return out


def main():
    data = {}
    for s in UNIVERSE:
        try:
            data[s] = bars(s)
        except Exception as e:
            print(f"  skip {s}: {e}")
    print(f"universe: {len(data)} names, "
          f"{sum(len(v) for v in data.values()):,} bars total\n")

    # unconditional null: every session, same names, same horizons
    base = {h: [] for h in HORIZONS}
    for bs in data.values():
        for i in range(30, len(bs) - max(HORIZONS) - 1):
            o = bs[i + 1]["o"]
            for h in HORIZONS:
                base[h].append((bs[i + h]["c"] - o) / o * 100)

    print(f"{'relvol':>7}{'horizon':>9}{'n':>7}{'mean %':>9}{'up %':>8}"
          f"{'base %':>9}{'edge':>9}{'t':>7}")
    results = []
    for rv in RELVOL_VARIANTS:
        fired = {s: signals(bs, rv) for s, bs in data.items()}
        for h in HORIZONS:
            rets = []
            for s, bs in data.items():
                for i in fired[s]:
                    if i + h < len(bs):
                        o = bs[i + 1]["o"]
                        rets.append((bs[i + h]["c"] - o) / o * 100)
            if len(rets) < 30:
                continue
            b = base[h]
            edge = mean(rets) - mean(b)
            t = edge / ((stdev(rets) ** 2 / len(rets) + stdev(b) ** 2 / len(b)) ** 0.5)
            up = sum(1 for x in rets if x > 0) / len(rets) * 100
            results.append((rv, h, t))
            print(f"{rv:>7.1f}{h:>9}{len(rets):>7}{mean(rets):>9.3f}{up:>7.1f}%"
                  f"{mean(b):>9.3f}{edge:>+9.3f}{t:>+7.2f}")

    print("\n" + "=" * 62)
    sig = [(rv, h, t) for rv, h, t in results if abs(t) > 1.96]
    if not sig:
        print("VERDICT: no configuration beats the base rate at p<0.05.")
        print("  The signal fires often and the forward returns look positive -")
        print("  but so does simply holding these names. There is no evidence")
        print("  the crossover adds information beyond the drift already in the")
        print("  universe. Matin's own dossier raised exactly this suspicion.")
    else:
        print(f"VERDICT: {len(sig)} configuration(s) clear p<0.05: {sig}")
        print("  Multiple-testing caution: 9 combinations were examined.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ── Walk-forward result, recorded 2026-08-29 ────────────────────────────────
#
# TRAIN 2016-2022 / TEST 2023-2026, 10-day horizon, edge vs base rate:
#
#   relvol            period    n   signal%   base%     edge       t
#      1.5   TRAIN 2016-2022    84     2.243   0.919   +1.323   +1.75
#      1.5   TEST  2023-2026    27     3.303   1.404   +1.898   +1.42
#      2.0   TRAIN 2016-2022    40     2.860   0.919   +1.940   +1.67
#      2.0   TEST  2023-2026    18     4.292   1.404   +2.888   +1.95
#
# Reading it honestly:
#   - Matin's ORIGINAL parameter (relvol >= 1.0) shows nothing: t = -0.79,
#     0.00, -1.39 across horizons. No edge.
#   - The tightened variants are positive and the sign HOLDS out of sample -
#     it did not collapse, which is more than most candidates manage.
#   - But nothing reaches |t| > 1.96 in either period alone, let alone the
#     Bonferroni floor of 2.77 for the 9 combinations examined.
#   - Out-of-sample n is 27 and 18. Far too small to conclude either way.
#   - Only the 10-day horizon works; 5 and 15 do not. A real effect would
#     more likely show a gradient than a spike at one horizon.
#
# VERDICT: NOT PROVEN, NOT REFUTED. Under the validation bar we adopted from
# AURA (OOS PF > 1.10, >50% folds positive, multiple-testing correction) this
# does not pass. Selecting relvol 2.0 now because it looked best in TEST would
# be post-holdout tuning - the exact thing that bar exists to prevent.
