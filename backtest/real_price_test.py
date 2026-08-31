"""Expectancy at REAL market credit — the backtest we should have run first.

condor_expectancy.py assumed credit = 1.15 x delta x width and measured +0.107.
Live chains on 31 Aug pay roughly HALF that. Measured medians:

    delta 0.15 -> credit/width 0.074
    delta 0.20 -> 0.092
    delta 0.30 -> 0.157
    delta 0.40 -> 0.231

The assumed floor was never a conservative estimate; it was unfillable. So this
re-runs ten years of real SPY/QQQ/IWM outcomes against the credit the market
ACTUALLY offers, across delta, width and hold length, and asks one question:
is ANY configuration positive at these prices?

Held-to-expiry and the day-N/50% exit are both measured, because E15 established
the exit is where the edge lives.
"""
import sys, os, json, subprocess
from math import exp, log, sqrt
from statistics import mean, stdev, median
from datetime import datetime

# credit/width MEASURED per (delta, width) from live chains 31 Aug. It falls as
# width grows - a 20-wide does not pay four times a 5-wide - so a single
# per-delta ratio applied across widths overstates wide spreads by roughly 2x
# and manufactures a false "wider is better" result.
CREDIT_RATIO = {
    (0.15, 5): 0.076, (0.15, 10): 0.066, (0.15, 20): 0.046,
    (0.20, 5): 0.112, (0.20, 10): 0.095, (0.20, 20): 0.066,
    (0.30, 5): 0.180, (0.30, 10): 0.150, (0.30, 20): 0.106,
    (0.40, 5): 0.234, (0.40, 10): 0.172, (0.40, 20): 0.127,
}
Z = {0.15: 1.0364, 0.20: 0.8416, 0.30: 0.5244, 0.40: 0.2533}
LOOK = 20


def bars(sym):
    o = subprocess.run(["alpaca", "data", "bars", "--symbol", sym, "--timeframe", "1Day",
                        "--start", "2018-01-01", "--end", "2026-08-28", "--limit", "10000",
                        "--feed", "iex", "--quiet"], capture_output=True, text=True, env=os.environ)
    try:
        return json.loads(o.stdout).get("bars", []) or []
    except Exception:
        return []


def run(closes, mondays, delta, width, dte, hold):
    """P&L per contract, in points, at the market's real credit."""
    ratio = CREDIT_RATIO.get((delta, width))
    if ratio is None:
        return []
    z, out = Z[delta], []
    for i in mondays:
        if i < LOOK + 1 or i + hold >= len(closes):
            continue
        s0 = closes[i]
        sig = stdev([log(closes[j] / closes[j-1]) for j in range(i-LOOK+1, i+1)]) * sqrt(252)
        if sig <= 0:
            continue
        mv = z * sig * sqrt(dte / 365.0)
        kp, kc = s0 * exp(-mv), s0 * exp(mv)
        credit = 2.0 * ratio * width           # both sides, real pricing
        final = closes[i + hold]
        if hold >= dte:                         # settled at expiry
            loss = 0.0
            if final < kp: loss = min(kp - final, width)
            elif final > kc: loss = min(final - kc, width)
            out.append(credit - loss)
        else:
            # E15's exit proxy: untouched by the exit day -> close for half the
            # credit; touched -> carry to expiry and take the settlement.
            lo = min(closes[i+1:i+hold+1]); hi = max(closes[i+1:i+hold+1])
            if lo > kp and hi < kc:
                out.append(credit * 0.5)
            else:
                loss = 0.0
                if final < kp: loss = min(kp - final, width)
                elif final > kc: loss = min(final - kc, width)
                out.append(credit - loss)
    return out


def stats(p, width):
    if len(p) < 30:
        return None
    w = [x for x in p if x > 0]; l = [abs(x) for x in p if x <= 0]
    if not w or not l:
        return None
    m, sd = mean(p), stdev(p)
    return {"n": len(p), "E": (1 + mean(w)/mean(l)) * len(w)/len(p) - 1,
            "mean": m, "t": m/(sd/sqrt(len(p))), "win": len(w)/len(p),
            "ret": m / max(width - m, 0.01)}


def main():
    print("EXPECTANCY AT REAL MARKET CREDIT\n")
    print(f"{'sym':>5}{'δ':>6}{'width':>7}{'DTE':>5}{'hold':>6}{'n':>6}"
          f"{'win%':>7}{'E':>8}{'mean':>8}{'t':>7}  verdict")
    hits = []
    for sym in ("SPY", "QQQ", "IWM"):
        b = bars(sym)
        if len(b) < 300:
            continue
        c = [x["c"] for x in b]
        mons = [i for i, x in enumerate(b)
                if datetime.fromisoformat(x["t"].replace("Z", "+00:00")).weekday() == 0]
        for delta in (0.15, 0.20, 0.30, 0.40):
            for width in (5, 10, 20):
                for dte, hold in ((11, 4), (11, 11), (18, 4), (18, 9), (32, 14)):
                    s = stats(run(c, mons, delta, width, dte, hold), width)
                    if not s:
                        continue
                    good = s["E"] > 0 and s["t"] > 1.5
                    if good or s["E"] > 0.02:
                        print(f"{sym:>5}{delta:>6.2f}{width:>7}{dte:>5}{hold:>6}{s['n']:>6}"
                              f"{s['win']*100:>6.1f}%{s['E']:>8.3f}{s['mean']:>8.3f}{s['t']:>7.2f}"
                              f"  {'✅ POSITIVE' if good else 'marginal'}")
                    if good:
                        hits.append((sym, delta, width, dte, hold, s))
    print()
    if hits:
        hits.sort(key=lambda h: -h[5]["E"])
        print(f"  {len(hits)} configurations positive with t > 1.5. Best:")
        for sym, d, w, dte, hold, s in hits[:6]:
            print(f"    {sym} δ{d} {w}-wide {dte}DTE hold {hold}d  ->  "
                  f"E {s['E']:+.3f}  win {s['win']*100:.0f}%  t {s['t']:.2f}")
    else:
        print("  NOTHING is positive at real market prices.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
