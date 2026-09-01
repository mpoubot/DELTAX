"""Weekly credit-spread backtest — corrected 1 Sep 2026.

Supersedes the 31 Aug run that produced -$50,904 and triggered the E42
stand-down. That run had four defects (see research/execution/golden-rules.md
E44). Each is fixed here and the fix is named at the site.

The headline number is now reported across a range of IV/RV assumptions,
because strike placement depends on implied vol and we cannot observe
historical IV through the bars API. A result that only survives at a
generous IV/RV is not a result.
"""
import os, sys, json, subprocess
from math import log, sqrt, exp
from statistics import stdev, median
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backtest"))
from bs import put as bs_put, call as bs_call
from deltax.gates import (market_credit_ratio, PORTFOLIO_RISK_PCT,
                          PER_POSITION_RISK_PCT)
from deltax.screener import DEFAULT_WIDTH

EQUITY   = 100_000.0
BUDGET   = EQUITY * PORTFOLIO_RISK_PCT
PER_POS  = EQUITY * PER_POSITION_RISK_PCT
LOOKBACK = 20
TP_FRAC  = 0.50                      # matches manage.TAKE_PROFIT_FRACTION

# N^-1(1-delta): converts a target delta into a strike distance in sigmas.
Z = {0.10: 1.2816, 0.15: 1.0364, 0.20: 0.8416, 0.25: 0.6745, 0.30: 0.5244}


def load(symbols, start="2026-01-01", end="2026-08-28"):
    out = {}
    for s in symbols:
        r = subprocess.run(
            ["alpaca", "data", "bars", "--symbol", s, "--timeframe", "1Day",
             "--start", start, "--end", end, "--limit", "300",
             "--feed", "iex", "--quiet"],
            capture_output=True, text=True, env=os.environ)
        try:
            out[s] = json.loads(r.stdout).get("bars", []) or []
        except json.JSONDecodeError:
            out[s] = []
    return out


def realized_vol(closes, i, n=LOOKBACK):
    rets = [log(closes[j] / closes[j - 1]) for j in range(i - n + 1, i + 1)]
    return stdev(rets) * sqrt(252) if len(rets) > 1 else 0.0


def regime(closes, i, deadband=0.0015):
    """B4 fix: mirror the live screener's direction choice instead of always
    selling puts. Above the 20-day mean by more than the deadband -> uptrend,
    sell puts. Below -> downtrend, sell calls. Inside the band -> stand aside."""
    sma = sum(closes[i - LOOKBACK + 1:i + 1]) / LOOKBACK
    edge = (closes[i] - sma) / sma
    if edge > deadband:
        return "put"
    if edge < -deadband:
        return "call"
    return None


def spread_value(side, spot, strike, width, T, sigma):
    """Mark-to-market value of the short vertical, in points."""
    if T <= 0:
        return max(strike - spot, 0.0) if side == "put" else max(spot - strike, 0.0)
    if side == "put":
        return bs_put(spot, strike, T, sigma) - bs_put(spot, strike - width, T, sigma)
    return bs_call(spot, strike, T, sigma) - bs_call(spot, strike + width, T, sigma)


def leg_pnl(side, spot0, spot1, sigma, dte, delta, width, hold=None):
    """One spread, entry to expiry.

    B1 fix: `sigma` is IMPLIED vol. The credit surface was measured on real
    quotes, so the strike must be placed on the same vol the credit is priced
    from. Placing it on realized vol while charging implied-vol credit put
    strikes 33% too close and manufactured breaches.

    B2/B3 fix: the payoff depends only on the CLOSE at expiry. A defined-risk
    spread held to expiry does not care about an intraday wick, and a trade
    that breached and recovered must never out-earn a clean one.
    """
    credit = market_credit_ratio(delta, width) * width
    if credit <= 0:
        return None
    dist = Z[delta] * sigma * sqrt(dte / 365.0)
    if side == "put":
        strike = spot0 * exp(-dist)
        intrinsic = max(strike - spot1, 0.0)
    else:
        strike = spot0 * exp(dist)
        intrinsic = max(spot1 - strike, 0.0)
    # manage.py rests a GTC exit at TP_FRAC of the credit, so upside is CAPPED
    # there: a position cannot expire worthless without first passing through
    # that fill. Without the cap a shallow breach out-earns a clean win, which
    # is the same inversion as B2 in a milder form.
    # B5 fix: closing BEFORE expiry buys the spread back at intrinsic PLUS the
    # remaining time value. Treating an early exit as intrinsic-only credited us
    # decay that had not happened yet. Black-Scholes supplies the decay fraction;
    # the measured market surface still supplies the absolute credit, so the
    # result stays anchored to prices we can actually fill.
    held = dte if hold is None else hold
    t_rem = max(dte - held, 0) / 365.0
    if t_rem > 0:
        v0 = spread_value(side, spot0, strike, width, dte / 365.0, sigma)
        v1 = spread_value(side, spot1, strike, width, t_rem, sigma)
        if v0 <= 0:
            return None
        settled = credit * (1.0 - v1 / v0)
    else:
        settled = credit - min(intrinsic, width)
    settled = max(settled, credit - width)          # defined risk floor
    return min(settled, credit * TP_FRAC), credit, strike


def run(symbols, bars, entry_weekday=1, hold=3, dte=3, delta=0.30,
        ivrv=1.30, use_regime=True, start="2026-03-01"):
    ref = bars[symbols[0]]
    entries = [i for i, b in enumerate(ref)
               if datetime.fromisoformat(b["t"].replace("Z", "+00:00")).weekday()
               == entry_weekday
               and b["t"][:10] >= start and i + hold < len(ref)]
    weeks, total = [], 0.0
    for ei in entries:
        day = ref[ei]["t"][:10]
        wk_pnl = 0.0
        committed = 0.0
        traded = 0
        for s in symbols:
            b = bars.get(s) or []
            idx = {x["t"][:10]: k for k, x in enumerate(b)}
            i = idx.get(day)
            if i is None or i < LOOKBACK + 1 or i + hold >= len(b):
                continue
            closes = [x["c"] for x in b]
            rv = realized_vol(closes, i)
            if rv <= 0:
                continue
            side = regime(closes, i) if use_regime else "put"
            if side is None:
                continue
            width = DEFAULT_WIDTH.get(s, 10.0)
            res = leg_pnl(side, closes[i], closes[i + hold], rv * ivrv,
                          dte, delta, width, hold=hold)
            if res is None:
                continue
            per_contract, credit, _ = res
            max_loss = (width - credit) * 100
            room = min(PER_POS, BUDGET - committed)
            qty = int(room // max_loss)
            if qty < 1:
                continue
            committed += qty * max_loss
            wk_pnl += per_contract * 100 * qty
            traded += 1
        if traded:
            weeks.append((day, wk_pnl, traded))
            total += wk_pnl
    return total, weeks


def summarize(total, weeks, label=""):
    if not weeks:
        return f"  {label:<26} no qualifying weeks"
    pnls = [w[1] for w in weeks]
    wins = sum(1 for p in pnls if p > 0)
    return (f"  {label:<26}{total:>+11,.0f}{total/EQUITY*100:>8.1f}%"
            f"{wins/len(pnls)*100:>7.0f}%{len(pnls):>5}"
            f"{median(pnls):>+10,.0f}{min(pnls):>+11,.0f}")
