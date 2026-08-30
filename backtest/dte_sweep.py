"""Which expiry maximises P&L over the contest's 4-day hold?

THE QUESTION. The hackathon runs Mon 31 Aug -> Fri 4 Sep: five sessions, and
Friday's 11:00 ET submission truncates the last one. Our +0.107 expectancy was
measured on a day-7/50%-credit exit that fires Mon 7 Sep - after the deadline
(rule E17). So we do not know our expected return, and we do not know which
expiry to trade.

WHY REPRICING, NOT THE E15 PROXY. E15 approximated the exit as "neither short
strike touched by day 7". That proxy has no time model, so it scores a 7-DTE
and a 21-DTE condor identically. Expiry choice for a fixed hold is entirely a
question about the shape of the decay curve, so the position must be repriced.

METHOD, per trade:
  1. Entry on a Monday. Spot S0, realized 20-day vol sigma.
  2. Strikes at z(delta) * sigma * sqrt(D/365) either side - the agent's own
     placement rule, unchanged from condor_expectancy.py.
  3. Credit = the gate floor, CREDIT_DELTA_MULTIPLE * delta * width per side.
     Read from deltax/gates.py so this can never drift from the live gate again.
  4. Calibrate an implied vol that makes Black-Scholes agree with that credit.
     This is what lets the reprice inherit the real premium: if the floor sits
     above BS-at-realized-vol, the calibrated IV carries the variance risk
     premium that is the seller's actual edge.
  5. Reprice on Friday - 4 trading days on, D-4 days left - at that same IV.
  6. P&L = credit - buyback value.

Entries are Mondays only and holds are 4 trading days, so consecutive samples
DO NOT OVERLAP. The original 14-day test overlapped roughly threefold; this one
is cleaner, and its t-statistics mean what they say.

ASSUMPTIONS, STATED PLAINLY:
  * credit is the gate MINIMUM - real fills at or above it would do better
  * implied vol is held constant from entry to exit; a vol spike would hurt
    the short condor and this does not model one
  * no commissions or slippage
  * Monday close to Friday close; the real exit is Friday ~11:00 ET

Run:  python3 backtest/dte_sweep.py
"""
from math import exp, log, sqrt
from statistics import mean, stdev
from datetime import datetime
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bs import condor_value, implied_vol
from deltax.gates import CREDIT_DELTA_MULTIPLE   # single source of truth

Z_BY_DELTA = {0.15: 1.0364, 0.20: 0.8416, 0.25: 0.6745, 0.30: 0.5244}
HOLD = 4                      # trading days, Monday -> Friday
DTE_GRID = (4, 5, 7, 10, 14, 21, 30)
VOL_LOOKBACK = 20


def bars(symbol, end="2026-08-28"):
    out = subprocess.run(
        ["alpaca", "data", "bars", "--symbol", symbol, "--timeframe", "1Day",
         "--start", "2016-01-01", "--end", end, "--limit", "10000",
         "--feed", "iex", "--quiet"],
        capture_output=True, text=True, env=os.environ)
    if out.returncode:
        return []
    d = json.loads(out.stdout)
    return [] if d.get("error") else d.get("bars", [])


def realized_vol(closes, i, n=VOL_LOOKBACK):
    rets = [log(closes[j] / closes[j - 1]) for j in range(i - n + 1, i + 1)]
    return stdev(rets) * sqrt(252)


def sweep(closes, mondays, delta, width, dte):
    """One (delta, dte) cell. Returns per-contract P&L in dollars."""
    z, pnl, skipped = Z_BY_DELTA[delta], [], 0
    for i in mondays:
        if i < VOL_LOOKBACK + 1 or i + HOLD >= len(closes):
            continue
        S0 = closes[i]
        sig = realized_vol(closes, i)
        if sig <= 0:
            continue
        T0 = dte / 365.0
        move = z * sig * sqrt(T0)
        k_put, k_call = S0 * exp(-move), S0 * exp(move)
        credit = 2.0 * CREDIT_DELTA_MULTIPLE * delta * width
        iv = implied_vol(credit, S0, k_put, k_call, width, T0)
        if iv is None:                      # credit unreachable at any vol
            skipped += 1
            continue
        T1 = max(dte - HOLD, 0) / 365.0
        buyback = condor_value(closes[i + HOLD], k_put, k_call, width, T1, iv)
        pnl.append((credit - buyback) * 100.0)
    return pnl, skipped


def stats(pnl, width, delta):
    if len(pnl) < 30:
        return None
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x <= 0]
    p = len(wins) / len(pnl)
    aw = mean(wins) if wins else 0.0
    al = abs(mean(losses)) if losses else 0.0
    E = ((1 + aw / al) * p - 1) if al > 0 else float("inf")
    m, sd = mean(pnl), (stdev(pnl) if len(pnl) > 1 else 0.0)
    t = m / (sd / sqrt(len(pnl))) if sd > 0 else 0.0
    credit = 2.0 * CREDIT_DELTA_MULTIPLE * delta * width
    max_loss = (width - credit) * 100.0        # only one side can finish ITM
    return {"n": len(pnl), "win": p, "E": E, "mean": m, "t": t,
            "worst": min(pnl), "max_loss": max_loss,
            "ret_on_risk": m / max_loss if max_loss > 0 else 0.0}


def main():
    print(__doc__.split("Run:")[0].strip()[:0] or "", end="")
    print(f"4-DAY HOLD SWEEP  ·  credit floor = {CREDIT_DELTA_MULTIPLE} x delta "
          f"x width  ·  entries: Mondays only, non-overlapping\n")
    universe = (("SPY", 5.0), ("QQQ", 5.0), ("IWM", 2.0))
    cache = {}
    for symbol, width in universe:
        bs_ = bars(symbol)
        if len(bs_) < 300:
            print(f"{symbol}: no data"); continue
        closes = [b["c"] for b in bs_]
        mondays = [i for i, b in enumerate(bs_)
                   if datetime.fromisoformat(b["t"].replace("Z", "+00:00")).weekday() == 0]
        cache[symbol] = (closes, mondays, width)
        print(f"{symbol}: {len(closes)} sessions, {len(mondays)} Mondays "
              f"({bs_[0]['t'][:10]} -> {bs_[-1]['t'][:10]})")
    print()
    hdr = (f"{'sym':>4}{'delta':>7}{'DTE':>5}{'n':>5}{'win%':>7}{'E (R)':>8}"
           f"{'mean $':>9}{'t':>7}{'worst $':>9}{'maxloss':>9}{'ret/risk':>9}")
    for symbol in cache:
        closes, mondays, width = cache[symbol]
        print(f"── {symbol} ─────────────────────────────────────────"
              f"──────────────────────────────")
        print(hdr)
        for delta in (0.15, 0.20, 0.30):
            for dte in DTE_GRID:
                pnl, skipped = sweep(closes, mondays, delta, width, dte)
                s = stats(pnl, width, delta)
                if not s:
                    print(f"{symbol:>4}{delta:>7.2f}{dte:>5}   -- insufficient "
                          f"samples ({len(pnl)}, {skipped} unpriceable)")
                    continue
                print(f"{symbol:>4}{delta:>7.2f}{dte:>5}{s['n']:>5}"
                      f"{s['win']*100:>6.1f}%{s['E']:>8.3f}{s['mean']:>9.2f}"
                      f"{s['t']:>7.2f}{s['worst']:>9.0f}{s['max_loss']:>9.0f}"
                      f"{s['ret_on_risk']*100:>8.2f}%")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
