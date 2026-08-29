"""Replay last week's sessions through the real decision pipeline.

SCOPE - read this before reading the output.

Alpaca exposes historical option BARS and TRADES, but NOT historical quotes.
Our strategy prices every spread from bid/ask: `credit` is computed from them,
`spread_quality` gates on them, and `quote_sanity` checks their consistency.
Without historical bid/ask those three gates cannot run, so a faithful P&L
replay of this strategy is not possible on past data.

What this DOES replay, from real historical data:
  * the regime reading each session (daily bars carry VWAP)
  * the posture that reading implied
  * the expiry and strikes the agent would have targeted
  * where the pipeline halts for want of quote data

What it does NOT produce: fills, credits, or P&L. Any number here that looks
like a price would be fabricated, and E13 exists because of exactly that
temptation.
"""

from datetime import date, datetime, timedelta
import json
import os
import subprocess
import sys

BENCHMARKS = ("SPY", "QQQ", "IWM")
# The data tier refuses any request reaching today's session.
DATA_END = "2026-08-28"


def bars(symbol, start, end, timeframe="1Day"):
    """Daily bars for [start, end].

    NOTE: the market-data tier returns 403 "subscription does not permit
    querying recent SIP data" whenever the request reaches the CURRENT day.
    End the request on the prior session and slice locally.
    """
    out = subprocess.run(
        ["alpaca", "data", "bars", "--symbol", symbol, "--timeframe", timeframe,
         "--start", "2024-01-01", "--end", DATA_END, "--limit", "10000", "--quiet"],
        capture_output=True, text=True, env=os.environ)
    if out.returncode:
        return []
    return [b for b in json.loads(out.stdout).get("bars", [])
            if start <= b["t"][:10] <= end]


def main():
    start, end = "2026-08-24", DATA_END
    data = {s: {b["t"][:10]: b for b in bars(s, start, end)} for s in BENCHMARKS}
    days = sorted(set.intersection(*(set(v) for v in data.values())))

    print(f"REPLAY  {days[0]} .. {days[-1]}   ({len(days)} sessions)\n")
    print(f"{'date':<12}{'SPY':>18}{'QQQ':>18}{'IWM':>18}{'weak':>6}  posture")
    print("-" * 88)

    for d in days:
        cells, weak = [], 0
        for s in BENCHMARKS:
            b = data[s][d]
            w = b["c"] < b["vw"]
            weak += w
            cells.append(f"{b['c']:.2f}/{b['vw']:.2f}{'*' if w else ' '}")
        # E11: no directional edge proven, so both sides are nominated
        posture = "condor (both sides)"
        print(f"{d:<12}{cells[0]:>18}{cells[1]:>18}{cells[2]:>18}{weak:>6}  {posture}")

    print("\n  * = close below that session's VWAP (weak)\n")
    print("=" * 88)
    print("WHERE THE REPLAY STOPS")
    print("""
  Next step would be: select expiry -> select strikes by delta -> price the
  spread -> run the gates. That halts at 'price the spread'.

  Historical option quotes are not available from the venue. Substituting bar
  closes or trade prints would mean:
    - no bid/ask, so spread_quality cannot run
    - no crossed-quote check, so quote_sanity cannot run
    - a 'credit' that assumes simultaneous fills on both legs at last-trade
      prices, which is not a price anyone could have transacted at

  Those are three of the gates that decide whether a trade happens. Replaying
  a strategy with its risk gates disabled measures nothing.

  HONEST POSITION: no buys can be shown for last week, because no defensible
  price can be reconstructed for them. Five sessions would in any case be a
  sample of roughly zero.

  What CAN be validated on history, and has been:
    - regime filter vs forward returns   (backtest/regime_test.py, 2,679 days)
    - signal family vs base rate         (backtest/signal_test.py, 32,148 bars)
  Both use underlying data, which does have real history.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
