"""What the agent would have traded on Monday 2026-08-24, and how it settled.

This is a real replay. Option prices come from ACTUAL TRADE PRINTS on the day -
not marks, not models. Historical option quotes do not exist, but historical
trades do, and a trade is a price someone genuinely transacted at.

Method:
  1. Place strikes at ~0.20 delta from that morning's spot and trailing vol
  2. Take the volume-weighted trade price of each leg inside our own entry
     window (09:45-10:30 ET), which is when the agent is permitted to enter
  3. Build the condor credit: sell the short legs, buy the long legs
  4. Run the real gates
  5. Settle: exit day 7 at 50% of credit if neither short strike was touched,
     otherwise carry to expiry

Honest limitations:
  * trade prints are not bid/ask, so gate_spread_quality cannot run
  * we assume we transacted at the window VWAP; a real fill could be worse
  * one week is a sample of one
"""

from datetime import date
from math import exp, log, sqrt
from statistics import stdev
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

ENTRY_START, ENTRY_END = "13:45", "14:30"     # 09:45-10:30 ET in UTC


def run_cli(args):
    out = subprocess.run(["alpaca"] + args + ["--quiet"],
                         capture_output=True, text=True, env=os.environ)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {}


def stock_bars(sym, start, end):
    d = run_cli(["data", "bars", "--symbol", sym, "--timeframe", "1Day",
                 "--start", start, "--end", end, "--feed", "iex", "--limit", "500"])
    return {b["t"][:10]: b for b in d.get("bars", [])}


def window_vwap(occ, day):
    """Volume-weighted trade price inside our entry window."""
    d = run_cli(["data", "option", "trades", "--symbols", occ,
                 "--start", day, "--end", day, "--limit", "10000"])
    trades = (d.get("trades") or {}).get(occ, [])
    sel = [t for t in trades if ENTRY_START <= t["t"][11:16] <= ENTRY_END]
    if not sel:
        return None, 0
    vol = sum(t["s"] for t in sel)
    return sum(t["p"] * t["s"] for t in sel) / vol, vol


def main():
    entry_day, expiry_day = "2026-08-24", "2026-09-04"
    bars = stock_bars("SPY", "2026-06-01", "2026-08-28")
    days = sorted(bars)
    i = days.index(entry_day)
    spot = bars[entry_day]["c"]
    closes = [bars[d]["c"] for d in days[:i + 1]]
    rets = [log(closes[j] / closes[j - 1]) for j in range(len(closes) - 20, len(closes))]
    sigma = stdev(rets) * sqrt(252)
    dte = (date.fromisoformat(expiry_day) - date.fromisoformat(entry_day)).days
    move = 0.8416 * sigma * sqrt(dte / 365)

    kp, kc, width = 749, 778, 5
    legs = {
        "short put":  ("SPY260904P00749000", "sell"),
        "long put":   ("SPY260904P00744000", "buy"),
        "short call": ("SPY260904C00778000", "sell"),
        "long call":  ("SPY260904C00783000", "buy"),
    }

    print(f"ENTRY {entry_day}   SPY {spot:.2f}   20d vol {sigma:.1%}   {dte} DTE")
    print(f"0.20-delta band: put {kp} / call {kc}, ${width} wide\n")
    print(f"{'leg':>12}{'contract':>22}{'action':>8}{'VWAP':>8}{'vol':>7}")
    prices = {}
    for name, (occ, side) in legs.items():
        p, v = window_vwap(occ, entry_day)
        prices[name] = p
        print(f"{name:>12}{occ:>22}{side:>8}"
              f"{(f'{p:.2f}' if p else 'none'):>8}{v:>7}")
    if any(v is None for v in prices.values()):
        print("\nmissing prints on at least one leg - cannot price the condor")
        return 1

    credit = ((prices["short put"] - prices["long put"])
              + (prices["short call"] - prices["long call"]))
    print(f"\ncredit received: ${credit:.2f} on ${width} width = {credit/width:.1%}")

    from deltax.gates import evaluate
    dec = evaluate(symbol="SPY", equity=100_000.0, structure="credit", width=width,
                   max_loss_per_contract=(width - credit) * 100,
                   max_profit_per_contract=credit * 100, credit=credit,
                   expiry=date.fromisoformat(expiry_day),
                   today=date.fromisoformat(entry_day),
                   open_interest=20_000, short_delta=0.20)
    print(f"\nGATES -> {dec.decision}"
          + (f"   {dec.contracts} contracts, max loss ${dec.max_loss:,.0f}"
             if dec.decision == "TRADE" else f"   (failed: {dec.failed_gate})"))
    for g in dec.gates:
        if not g.passed:
            print(f"   FAIL {g.gate}: {g.detail}")

    # settle
    path = [d for d in days if entry_day < d <= expiry_day]
    breach_day = next((d for d in path
                       if bars[d]["l"] < kp or bars[d]["h"] > kc), None)
    print(f"\nSETTLEMENT")
    print(f"  path {path[0]} .. {path[-1]}  "
          f"SPY {bars[path[0]]['c']:.2f} -> {bars[path[-1]]['c']:.2f}")
    print(f"  short strikes {kp}/{kc} breached: "
          f"{breach_day or 'never'}")
    day7 = path[min(6, len(path) - 1)]
    touched_by_7 = any(bars[d]["l"] < kp or bars[d]["h"] > kc
                       for d in path[:7])
    if not touched_by_7:
        pnl_per = 0.5 * credit * 100
        print(f"  E5 exit on {day7} at 50% of credit -> +${pnl_per:.0f}/contract")
    else:
        f = bars[path[-1]]["c"]
        loss = 0.0
        if f < kp: loss += min(kp - f, width)
        if f > kc: loss += min(f - kc, width)
        pnl_per = (credit - loss) * 100
        print(f"  carried to expiry, settled {f:.2f} -> ${pnl_per:+.0f}/contract")
    if dec.decision == "TRADE":
        print(f"\n  TOTAL on {dec.contracts} contracts: ${pnl_per*dec.contracts:+,.0f}")
    else:
        print(f"\n  Not taken (gates refused). Had it been: "
              f"${pnl_per:+.0f}/contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
