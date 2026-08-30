"""Combined book: options + stocks + crypto, on the team's allocation.

ALLOCATION (team decision, 30 Aug 2026):
    options  $30,000 risk   iron condors, Sep-11-style 11 DTE, delta 0.20
    stocks   $60,000        COVERED CALLS - the compliant structure: a stock
                            strategy that incorporates options (Rule 3), and one
                            that sells premium rather than predicting direction,
                            which is the only equity edge we have evidence for
    crypto   $10,000        SPOT ONLY - Alpaca lists no crypto options

HOLD: 4 days, Monday -> Friday, matching the contest window (E17).

PREMIUM ASSUMPTION. Condor credit is the gate floor, calibrated to an implied
vol as in dte_sweep. Covered-call premium uses IV = 1.20 x realized, the
CONSERVATIVE end of the 1.2-1.4 variance premium measured on SPY. Crypto has no
premium to collect - it is long spot and carries full directional risk.

Run:  python3 backtest/portfolio_test.py
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import exp, log, sqrt
from statistics import mean, stdev, median
from datetime import datetime
from bs import call as bs_call, condor_value, implied_vol
from deltax.gates import CREDIT_DELTA_MULTIPLE, PORTFOLIO_RISK_PCT

EQUITY = 100_000.0
OPT_RISK, STOCK_CAP, CRYPTO_CAP = 30_000.0, 60_000.0, 10_000.0
DELTA, Z, DTE, HOLD, LOOK = 0.20, 0.8416, 11, 4, 20
VRP = 1.20

def ebars(sym, start="2018-01-01"):
    o = subprocess.run(["alpaca","data","bars","--symbol",sym,"--timeframe","1Day",
        "--start",start,"--end","2026-08-28","--limit","10000","--feed","iex","--quiet"],
        capture_output=True, text=True, env=os.environ)
    try: d = json.loads(o.stdout)
    except Exception: return []
    return d.get("bars", []) or []

def cbars(sym):
    o = subprocess.run(["alpaca","data","crypto","bars","--symbols",sym,"--timeframe","1Day",
        "--start","2021-01-01","--end","2026-08-28","--limit","10000","--quiet"],
        capture_output=True, text=True, env=os.environ)
    try: d = json.loads(o.stdout)
    except Exception: return []
    return (d.get("bars") or {}).get(sym, []) or []

def rvol(c, i, ann=252, n=LOOK):
    return stdev([log(c[j]/c[j-1]) for j in range(i-n+1, i+1)]) * sqrt(ann)

def condor_week(c, i, W=5.0):
    """P&L for the options sleeve, sized to OPT_RISK."""
    s = rvol(c, i)
    if s <= 0: return None
    S0, T0 = c[i], DTE/365.0
    mv = Z*s*sqrt(T0); kp, kc = S0*exp(-mv), S0*exp(mv)
    cr = 2.0*CREDIT_DELTA_MULTIPLE*DELTA*W
    iv = implied_vol(cr, S0, kp, kc, W, T0)
    if iv is None: return None
    ct = int(OPT_RISK // ((W-cr)*100.0))
    buyback = condor_value(c[i+HOLD], kp, kc, W, max(DTE-HOLD,0.2)/365.0, iv)
    return (cr-buyback)*100.0*ct

def covered_call_week(c, i):
    """Own STOCK_CAP of stock, sell one OTM call per 100 shares."""
    s = rvol(c, i)
    if s <= 0: return None
    S0, S1, T0 = c[i], c[i+HOLD], DTE/365.0
    shares = STOCK_CAP / S0
    k = S0*exp(Z*s*sqrt(T0))
    prem = bs_call(S0, k, T0, s*VRP)                       # sold
    back = bs_call(S1, k, max(DTE-HOLD,0.2)/365.0, s*VRP)  # bought back
    return (S1-S0)*shares + (prem-back)*shares             # stock + short call

def spot_week(c, i, cap):
    return (c[i+HOLD]/c[i] - 1.0) * cap

def summarize(name, pnl, cap):
    if not pnl: return None
    n = len(pnl); m = mean(pnl); sd = stdev(pnl) if n > 1 else 0.0
    wins = [x for x in pnl if x > 0]
    return {"name": name, "n": n, "mean": m, "median": median(pnl),
            "win": len(wins)/n, "worst": min(pnl), "best": max(pnl),
            "t": m/(sd/sqrt(n)) if sd > 0 else 0.0, "ret": m/cap*100.0}

def main():
    print(f"COMBINED PORTFOLIO · ${EQUITY:,.0f} · {HOLD}-day hold\n")
    print(f"  options ${OPT_RISK:,.0f} risk | stocks ${STOCK_CAP:,.0f} covered calls "
          f"| crypto ${CRYPTO_CAP:,.0f} spot\n")

    # ── options + stocks on SPY history, Mondays only
    b = ebars("SPY")
    c = [x["c"] for x in b]
    mons = [i for i,x in enumerate(b)
            if datetime.fromisoformat(x["t"].replace("Z","+00:00")).weekday()==0]
    opt, cc = [], []
    for i in mons:
        if i < LOOK+1 or i+HOLD >= len(c): continue
        o = condor_week(c, i);  s = covered_call_week(c, i)
        if o is not None and s is not None: opt.append(o); cc.append(s)

    # ── crypto: equal-weight the four listed pairs
    coins = ["BTC/USD","ETH/USD","SOL/USD","XRP/USD"]
    series = {}
    for sym in coins:
        cb = cbars(sym)
        if len(cb) > 200: series[sym] = [x["c"] for x in cb]
    per = CRYPTO_CAP/len(series) if series else 0.0
    L = min(len(v) for v in series.values()) if series else 0
    cry = []
    for i in range(LOOK+1, L-HOLD, 7):          # weekly entries
        cry.append(sum(spot_week(v, i, per) for v in series.values()))

    rows = [summarize("options (condor)", opt, OPT_RISK),
            summarize("stocks (cov call)", cc, STOCK_CAP),
            summarize(f"crypto spot x{len(series)}", cry, CRYPTO_CAP)]
    print(f"{'sleeve':>19}{'n':>6}{'mean $':>10}{'median $':>10}{'win%':>7}"
          f"{'worst $':>11}{'best $':>10}{'t':>7}{'ret%':>8}")
    for r in rows:
        if not r: continue
        print(f"{r['name']:>19}{r['n']:>6}{r['mean']:>10,.0f}{r['median']:>10,.0f}"
              f"{r['win']*100:>6.1f}%{r['worst']:>11,.0f}{r['best']:>10,.0f}"
              f"{r['t']:>7.2f}{r['ret']:>7.2f}%")

    # ── combined, pairing options+stocks weeks with crypto weeks by index
    k = min(len(opt), len(cry))
    comb = [opt[i]+cc[i]+cry[i] for i in range(k)]
    r = summarize("COMBINED BOOK", comb, EQUITY)
    print(f"\n{'-'*86}")
    print(f"{r['name']:>19}{r['n']:>6}{r['mean']:>10,.0f}{r['median']:>10,.0f}"
          f"{r['win']*100:>6.1f}%{r['worst']:>11,.0f}{r['best']:>10,.0f}"
          f"{r['t']:>7.2f}{r['ret']:>7.2f}%")
    print(f"{'-'*86}")
    los = sorted(comb)[:max(1,len(comb)//20)]
    print(f"\n  worst 5% of weeks average   ${mean(los):>12,.0f}  ({mean(los)/EQUITY*100:>6.2f}%)")
    print(f"  single worst week           ${min(comb):>12,.0f}  ({min(comb)/EQUITY*100:>6.2f}%)")
    print(f"  weeks losing >5% of equity  {sum(1 for x in comb if x < -0.05*EQUITY):>4}/{len(comb)}"
          f"  = {sum(1 for x in comb if x < -0.05*EQUITY)/len(comb)*100:.1f}%  <- kill-switch rate")
    return 0

if __name__ == "__main__":
    sys.exit(main())
