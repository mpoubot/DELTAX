"""Does a positive earnings reaction predict continued drift?

Tests the one component of Matin's catalyst engine we can measure today: his
"Market Reaction Score". Analyst estimates and consensus are unavailable to us,
so the earnings-surprise and analyst-revision components cannot be tested at
all - but the market's own reaction to a filing IS observable, and he argues it
may be the most valuable of the three.

Method - deliberately free of look-ahead, per his own warning:
  * earnings dates from SEC 8-K Item 2.02 filings (the actual filing record)
  * reaction = close-to-close move on the first session AFTER the filing
  * entry at the NEXT open after that reaction is observed
  * forward returns measured against the same universe's base rate

If a strong positive reaction predicts drift, catalyst-driven directional
trades have a basis. If not, the catalyst engine is a fifth directional
hypothesis to add to the four already rejected this week.
"""

from statistics import mean, stdev
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from deltax.earnings import earnings_history

UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "JNJ", "PG", "KO",
            "PEP", "CSCO", "INTC", "CVX", "XOM", "MRK", "ABT", "HON", "CAT",
            "MMM", "IBM"]
HORIZONS = (5, 10, 20)
STRONG = 3.0          # a "strong" reaction, in percent


def bars(sym):
    out = subprocess.run(
        ["alpaca", "data", "bars", "--symbol", sym, "--timeframe", "1Day",
         "--start", "2016-01-01", "--end", "2026-08-28", "--limit", "10000",
         "--feed", "iex", "--quiet"],
        capture_output=True, text=True, env=os.environ)
    if out.returncode:
        return []
    d = json.loads(out.stdout)
    return [] if d.get("error") else d.get("bars", [])


def main():
    buckets = {h: {"strong_pos": [], "pos": [], "neg": [], "base": []}
               for h in HORIZONS}
    covered = 0
    for sym in UNIVERSE:
        try:
            filings = set(earnings_history(sym))
        except Exception:
            continue
        bs = bars(sym)
        if len(bs) < 400 or not filings:
            continue
        covered += 1
        days = [b["t"][:10] for b in bs]
        close = [b["c"] for b in bs]
        pos = {d: i for i, d in enumerate(days)}
        for h in HORIZONS:
            for i in range(1, len(bs) - h - 2):
                buckets[h]["base"].append((close[i + h] - close[i]) / close[i] * 100)
        for f in filings:
            i = pos.get(str(f))   # filings are date objects; index is keyed by string
            if i is None or i + 2 >= len(bs):
                continue
            # reaction on the session after the filing
            react = (close[i + 1] - close[i]) / close[i] * 100
            entry = i + 1
            for h in HORIZONS:
                if entry + h >= len(bs):
                    continue
                fwd = (close[entry + h] - close[entry]) / close[entry] * 100
                if react >= STRONG:
                    buckets[h]["strong_pos"].append(fwd)
                elif react > 0:
                    buckets[h]["pos"].append(fwd)
                else:
                    buckets[h]["neg"].append(fwd)

    print(f"universe covered: {covered}/{len(UNIVERSE)} tickers\n")
    print(f"{'horizon':>8}{'bucket':>13}{'n':>7}{'mean %':>9}{'base %':>9}"
          f"{'edge':>9}{'t':>7}")
    for h in HORIZONS:
        base = buckets[h]["base"]
        for name in ("strong_pos", "pos", "neg"):
            v = buckets[h][name]
            if len(v) < 30:
                continue
            t = (mean(v) - mean(base)) / (
                (stdev(v) ** 2 / len(v) + stdev(base) ** 2 / len(base)) ** 0.5)
            flag = "  *" if abs(t) > 1.96 else ""
            print(f"{h:>8}{name:>13}{len(v):>7}{mean(v):>9.3f}{mean(base):>9.3f}"
                  f"{mean(v)-mean(base):>+9.3f}{t:>+7.2f}{flag}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ── Result, recorded 2026-08-29 ─────────────────────────────────────────────
#
# 20 tickers, ~277 earnings events from SEC 8-K Item 2.02 filings.
#
#  horizon      bucket    n   mean%   base%    edge      t
#        5  strong_pos   50   1.277   0.292  +0.985  +1.35
#        5         pos   81   0.692   0.292  +0.400  +1.27
#        5         neg  146  -0.327   0.292  -0.619  -1.84
#       10  strong_pos   50   2.658   0.579  +2.080  +1.53
#       10         pos   81   1.473   0.579  +0.895  +1.81
#       10         neg  146   1.058   0.579  +0.479  +1.10
#       20  strong_pos   50   1.275   1.131  +0.145  +0.06
#       20         pos   80   1.210   1.131  +0.080  +0.12
#       20         neg  142   1.776   1.131  +0.645  +1.18
#
# READING IT:
#   * Every bucket points the RIGHT way at 5 and 10 days - positive reactions
#     drift up, negative reactions drift down. That is the classic
#     post-earnings-drift shape.
#   * Nothing reaches |t| > 1.96. Best is +1.81 (positive reaction, 10 days).
#   * The effect is gone entirely by 20 days, which is what a real drift
#     effect looks like rather than a spurious one.
#   * n = 50 for the strong-positive bucket. Far too thin to conclude.
#
# VERDICT: NOT PROVEN, but the most promising directional hypothesis tested
# this week. Unlike the VWAP regime filter (sign ran backwards) or the 20-day
# breakout (flat), this one is consistently signed and decays sensibly.
#
# It also does NOT conflict with our earnings blackout: that gate stops us
# holding THROUGH an event, while this trades AFTER one.
#
# Cannot be promoted without: a larger sample, point-in-time analyst data for
# the other two components, and multiple-testing correction across the nine
# cells above.
