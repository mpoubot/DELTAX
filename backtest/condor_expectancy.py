"""Expectancy of the income strategy, measured on ten years of real outcomes.

THE INSIGHT THAT MAKES THIS POSSIBLE WITHOUT OPTION QUOTES:

A credit spread held to expiry pays out on exactly two things - the credit
received, and where the underlying finishes. We cannot observe historical
credits (no historical option quotes), but our own gate CONSTRAINS them:

    credit / width >= 0.9 x short_delta        (gate_credit_fraction)

So we assume the credit is exactly that floor - the worst premium the agent
would ever accept - and measure the payoff against real underlying history.
Any real trade would have collected at least this much, so the result is a
conservative lower bound on the strategy, not an optimistic one.

Structure tested: the iron condor E11 mandates - a put credit spread and a
call credit spread at the same delta, both sized by the same rules.

Assumptions, stated plainly:
  * strikes placed by realized volatility, not by dealer-quoted delta
  * held to expiry - no 50%-of-credit early exit (which would raise the result)
  * no commissions or slippage
  * assignment is settled at expiry value

Run:  python3 backtest/condor_expectancy.py
"""

from math import exp, log, sqrt
from statistics import mean, stdev
import json
import os
import subprocess
import sys

Z_BY_DELTA = {0.15: 1.0364, 0.20: 0.8416, 0.25: 0.6745, 0.30: 0.5244}
DTE = 14
CREDIT_MULT = 0.9          # gate_credit_fraction floor
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


def condor_pnl(spot, final, sigma, width, delta, dte=DTE):
    """P&L per contract for a condor opened at `spot`, settled at `final`."""
    t = dte / 365.0
    z = Z_BY_DELTA[delta]
    move = z * sigma * sqrt(t)
    k_put, k_call = spot * exp(-move), spot * exp(move)
    credit_side = CREDIT_MULT * delta * width      # per side, in points
    total_credit = 2 * credit_side

    def short_leg_loss(breached, strike, is_put):
        if not breached:
            return 0.0
        intrinsic = (strike - final) if is_put else (final - strike)
        return min(intrinsic, width)               # capped by the long leg

    loss = (short_leg_loss(final < k_put, k_put, True)
            + short_leg_loss(final > k_call, k_call, False))
    return (total_credit - loss) * 100             # x100 multiplier


def run(symbol, delta=0.20, width=5.0):
    bs = bars(symbol)
    if len(bs) < 300:
        return None
    closes = [b["c"] for b in bs]
    trades = []
    i = VOL_LOOKBACK + 1
    while i + DTE < len(closes):
        sigma = realized_vol(closes, i)
        if sigma > 0:
            trades.append(condor_pnl(closes[i], closes[i + DTE], sigma, width, delta))
        i += 5                                     # one new condor per week
    if not trades:
        return None
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    p = len(wins) / len(trades)
    aw = mean(wins) if wins else 0.0
    al = abs(mean(losses)) if losses else 0.0
    E = ((1 + aw / al) * p - 1) if al > 0 else float("inf")
    return {"symbol": symbol, "n": len(trades), "win_rate": p, "avg_win": aw,
            "avg_loss": al, "expectancy_R": E, "total": sum(trades),
            "worst": min(trades), "mean": mean(trades)}


def main():
    print(f"Iron condor, {DTE} DTE, credit at the gate floor "
          f"({CREDIT_MULT} x delta x width per side)\n")
    print(f"{'sym':>5}{'delta':>7}{'n':>6}{'win%':>7}{'avg win':>9}{'avg loss':>10}"
          f"{'E (R)':>8}{'mean $':>9}{'worst $':>10}")
    any_row = False
    for symbol, width in (("SPY", 5.0), ("QQQ", 5.0), ("IWM", 2.0)):
        for delta in (0.15, 0.20, 0.30):
            r = run(symbol, delta, width)
            if not r:
                continue
            any_row = True
            print(f"{r['symbol']:>5}{delta:>7.2f}{r['n']:>6}{r['win_rate']*100:>6.1f}%"
                  f"{r['avg_win']:>9.0f}{r['avg_loss']:>10.0f}{r['expectancy_R']:>8.3f}"
                  f"{r['mean']:>9.0f}{r['worst']:>10.0f}")
    if not any_row:
        print("  no data returned")
        return 1
    print("\nE > 0 means positive expectancy under the gate's MINIMUM credit.")
    print("Real fills at or above that floor would do better; costs would do worse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
