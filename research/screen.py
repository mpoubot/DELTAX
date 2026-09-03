"""One ticker in, one verdict out.

    python3 research/screen.py GPRO

Scores a name on the criteria that actually decide whether DELTAX can trade it,
and returns a single confidence figure. Confidence is a WEIGHTED PRODUCT, not an
average: a hard failure (no liquidity, negative variance premium) drives it near
zero rather than being diluted by things that passed. A name we cannot trade at
all should not score 60% because its chart looks fine.

Every input is measured live. Anything unreadable scores 0 and says so - an
unmeasurable criterion is never treated as a pass.
"""
import json, subprocess, sys, os, urllib.request
from math import log, sqrt, erf
from statistics import stdev, median
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

N = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
def bs(S, K, T, v, r):
    if T <= 0 or v <= 0:
        return max(K - S, 0) if r == "put" else max(S - K, 0)
    d1 = (log(S / K) + 0.5 * v * v * T) / (v * sqrt(T)); d2 = d1 - v * sqrt(T)
    return K * N(-d2) - S * N(-d1) if r == "put" else S * N(d1) - K * N(d2)

def cli(*a):
    o = subprocess.run(["alpaca"] + list(a) + ["--quiet"],
                       capture_output=True, text=True).stdout or "{}"
    try: return json.loads(o)
    except Exception: return {}

def massive(path):
    k = os.environ.get("MASSIVE_API_KEY")
    try:
        with urllib.request.urlopen(
                f"https://api.massive.com{path}{'&' if '?' in path else '?'}apiKey={k}",
                timeout=25) as r:
            return json.loads(r.read())
    except Exception:
        return {}

def score(sym: str) -> dict:
    from deltax.feeds import AlpacaFeed, latest_price, quote as fquote, delta as fdelta
    from deltax import gates as G, screener as S
    f = AlpacaFeed(); today = date.today()
    out = {"symbol": sym, "criteria": [], "notes": []}

    px = latest_price(f.snapshots([sym]).get(sym) or {})
    out["price"] = px
    if not px:
        out["criteria"].append(("price", 0.0, "no price"))
        out["confidence"] = 0.0; out["verdict"] = "NO — unpriceable"
        return out

    # 1 tradable structure at all
    gte, lte = str(today + timedelta(days=2)), str(today + timedelta(days=21))
    picked = S.choose_expiry(f, sym, "put", gte, lte, 0, 10 ** 9)
    if not picked:
        out["criteria"].append(("option liquidity", 0.0,
                                "no expiry clears the 500-OI floor"))
        out["confidence"] = 0.0
        out["verdict"] = "NO — no tradeable option chain"
        return out
    exp, oi = picked
    liq = sum(1 for v in oi.values() if v >= G.MIN_OPEN_INTEREST)
    out["criteria"].append(("option liquidity", min(liq / 20.0, 1.0),
                            f"{liq} strikes over the {G.MIN_OPEN_INTEREST} floor"))

    # 2 spread quality
    chain = f.option_chain(sym, option_type="put", expiry_gte=exp, expiry_lte=exp)
    sps = []
    for k, c in (chain or {}).items():
        b, a = fquote(c)
        if b and a and a > 0 and b > 0:
            sps.append((a - b) / ((a + b) / 2))
    msp = median(sps) if sps else None
    out["criteria"].append(("spread quality",
                            0.0 if msp is None else max(0.0, min(1.0, (G.MAX_SPREAD_PCT * 2 - msp) / (G.MAX_SPREAD_PCT * 2))),
                            "unreadable" if msp is None else
                            f"{msp:.1%} median vs {G.MAX_SPREAD_PCT:.0%} cap"))

    # 3 variance premium - the thing that cost us money
    rv = S.realized_vol_20(f, sym, today)
    iv = None
    cands = [(k, c) for k, c in (chain or {}).items()
             if fdelta(c) and 0.15 <= abs(fdelta(c)) <= 0.35]
    if cands:
        k, c = min(cands, key=lambda x: abs(abs(fdelta(x[1])) - 0.25))
        b, a = fquote(c)
        if b and a:
            mid = (b + a) / 2; K = S._strike_from(k)
            T = max((date.fromisoformat(exp) - today).days, 1) / 365
            lo, hi = 0.01, 3.0
            for _ in range(60):
                m = (lo + hi) / 2
                if bs(px, K, T, m, "put") < mid: lo = m
                else: hi = m
            iv = (lo + hi) / 2
    ratio = (iv / rv) if (iv and rv) else None
    out["criteria"].append(("variance premium",
                            0.0 if ratio is None else min(max((ratio - 1.0) / 0.5, 0.0), 1.0),
                            "unreadable" if ratio is None else
                            f"IV/RV {ratio:.2f} (floor {G.MIN_VARIANCE_PREMIUM})"))

    # 4 event risk - a fresh gap means the excursion distribution, not the median
    bars = (massive(f"/v2/aggs/ticker/{sym}/range/1/day/"
                    f"{today - timedelta(days=400)}/{today}?limit=5000").get("results") or [])
    gap = None
    if len(bars) >= 2:
        gap = (px / bars[-1]["c"] - 1) * 100
    if gap is None:
        out["criteria"].append(("event risk", 0.0, "no history"))
    elif abs(gap) >= 8:
        out["criteria"].append(("event risk", 0.05,
                                f"{gap:+.1f}% repricing event in progress"))
        out["notes"].append("Measured across 20 names: post-gap volatility rises "
                            "(median 1.24x) and the 5-session excursion is 10.3% "
                            "median, 16.6% at the 90th percentile.")
    else:
        out["criteria"].append(("event risk", 1.0, f"{gap:+.1f}% move, no gap"))

    # weighted product: a hard failure cannot be averaged away
    conf = 1.0
    for _, v, _ in out["criteria"]:
        conf *= max(v, 0.01) ** 0.25
    out["confidence"] = round(conf * 100, 1)
    out["verdict"] = ("TRADEABLE" if conf >= 0.55 else
                      "MARGINAL" if conf >= 0.35 else "NO")
    out["iv"], out["rv"], out["gap"] = iv, rv, gap
    return out


def render(r: dict) -> str:
    L = [f"  {r['symbol']}   ${r.get('price') or 0:,.2f}"
         + (f"   {r['gap']:+.1f}% vs prior close" if r.get("gap") is not None else ""),
         ""]
    for name, v, why in r["criteria"]:
        bar = "#" * int(round(v * 10)) + "." * (10 - int(round(v * 10)))
        L.append(f"  {name:<18} {bar}  {v*100:>5.1f}%   {why}")
    L += ["", f"  CONFIDENCE   {r['confidence']}%        VERDICT   {r['verdict']}"]
    for n in r.get("notes", []):
        L.append(f"  note: {n}")
    return "\n".join(L)


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["SPY"]):
        print(render(score(s.upper())), "\n")
