"""E71 — Three-layer ETF sector rotation.

    Layer 1  regime      SPY vs safe havens (GLD, TLT, BIL)
    Layer 2  core        the 11 GICS sector SPDRs, ranked by relative strength
    Layer 3  subsector   high-beta expression inside a winning sector

Relative strength is `ROC(sector) - ROC(SPY)` over a lookback: how much a
sector beat the index, not how much it rose. A sector up 1% in a market up 3%
is *weak*, and ranking on raw return would buy it.

**The honest limitation, stated where it cannot be missed.** The source
framework says rotation "takes weeks to unfold" and that daily rebalancing
produces whipsaws and fee drag. This contest has days. What runs here is
therefore a **momentum tilt on a rotation signal**, not a rotation strategy:
the ranking is real and measurable today, the holding period is not the one
the signal was designed for. LOOKBACK is deliberately short (5 sessions) so
the measurement window at least matches the horizon we can hold.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Layer 2 — the 11 GICS pillars (State Street SPDR suite).
CORE_SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLU",
                "XLY", "XLP", "XLI", "XLB", "XLRE", "XLC"]

# Layer 3 — high-beta expression, mapped to the core sector it amplifies.
SUBSECTORS = {
    "XLK":  ["SMH", "IGV", "CIBR"],
    "XLC":  ["IGV"],
    "XLV":  ["XBI", "IHI"],
    "XLF":  ["KRE", "IAI"],
    "XLI":  ["IYT", "ITA"],
    "XLE":  ["XOP"],
}

SAFE_HAVENS = ["GLD", "TLT", "BIL"]
BENCHMARK   = "SPY"

LOOKBACK        = 5      # sessions; matched to the horizon we can actually hold
TOP_N           = 3      # buy the strongest three
RISK_OFF_PAIR   = ("SMH", "XLU")   # cyclical / defensive ratio
RISK_OFF_MA     = 50


@dataclass
class Ranked:
    symbol: str
    roc: float
    rs: float                    # roc minus benchmark roc
    subsector: Optional[str] = None


def roc(closes: list, lookback: int = LOOKBACK) -> Optional[float]:
    """Rate of change over `lookback` sessions. None when unusable."""
    if not closes or len(closes) < lookback + 1:
        return None
    a, b = closes[-lookback - 1], closes[-1]
    if not a or a <= 0:
        return None
    return b / a - 1


def regime(spy: list, gld: list, tlt: list) -> tuple:
    """(state, reason). RISK_ON / RISK_OFF / UNKNOWN.

    Risk-off when SPY's momentum is negative AND a safe haven is beating it.
    Both conditions are required: falling equities alone can be noise, and a
    rising haven alone is often just a rate move.
    """
    r_spy, r_gld, r_tlt = roc(spy), roc(gld), roc(tlt)
    if r_spy is None:
        return "UNKNOWN", "no benchmark history - fails to UNKNOWN"
    havens = [r for r in (r_gld, r_tlt) if r is not None]
    if not havens:
        return "UNKNOWN", "no safe-haven history"
    best = max(havens)
    if r_spy < 0 and best > r_spy:
        return "RISK_OFF", f"SPY {r_spy:+.2%} negative, haven {best:+.2%} ahead"
    return "RISK_ON", f"SPY {r_spy:+.2%}, best haven {best:+.2%}"


def defensive_switch(smh: list, xlu: list, ma: int = RISK_OFF_MA) -> tuple:
    """(triggered, reason). SMH/XLU ratio below its moving average = risk-off."""
    if len(smh) < ma + 1 or len(xlu) < ma + 1:
        return False, f"need {ma}+ sessions for the ratio MA - not triggered"
    n = min(len(smh), len(xlu))
    ratio = [smh[-n + i] / xlu[-n + i] for i in range(n) if xlu[-n + i]]
    if len(ratio) < ma + 1:
        return False, "ratio series too short"
    avg = sum(ratio[-ma:]) / ma
    cur = ratio[-1]
    if cur < avg:
        return True, f"SMH/XLU {cur:.3f} below {ma}d MA {avg:.3f} - RISK OFF"
    return False, f"SMH/XLU {cur:.3f} above {ma}d MA {avg:.3f}"


def rank_sectors(closes_by_symbol: dict, universe: Optional[list] = None,
                 benchmark: str = BENCHMARK) -> list:
    """Core sectors sorted by relative strength, strongest first."""
    bench = roc(closes_by_symbol.get(benchmark) or [])
    if bench is None:
        return []
    out = []
    for s in (universe or CORE_SECTORS):
        r = roc(closes_by_symbol.get(s) or [])
        if r is None:
            continue
        out.append(Ranked(s, r, r - bench))
    out.sort(key=lambda x: x.rs, reverse=True)
    return out


def best_subsector(sector: str, closes_by_symbol: dict,
                   benchmark: str = BENCHMARK) -> Optional[Ranked]:
    """Layer 3: the strongest subsector inside a winning core sector.

    Returns None unless a subsector actually beats its parent - amplifying a
    sector with something weaker than the sector is a worse trade, not a
    higher-beta one.
    """
    kids = SUBSECTORS.get(sector) or []
    if not kids:
        return None
    bench = roc(closes_by_symbol.get(benchmark) or [])
    parent = roc(closes_by_symbol.get(sector) or [])
    if bench is None or parent is None:
        return None
    best = None
    for k in kids:
        r = roc(closes_by_symbol.get(k) or [])
        if r is None or r <= parent:
            continue
        cand = Ranked(k, r, r - bench, subsector=sector)
        if best is None or cand.rs > best.rs:
            best = cand
    return best


def select(closes_by_symbol: dict, top_n: int = TOP_N) -> dict:
    """The full three-layer decision. Never raises; refuses on thin data."""
    spy = closes_by_symbol.get(BENCHMARK) or []
    state, why = regime(spy, closes_by_symbol.get("GLD") or [],
                        closes_by_symbol.get("TLT") or [])
    risk_off, ratio_why = defensive_switch(closes_by_symbol.get("SMH") or [],
                                           closes_by_symbol.get("XLU") or [])
    ranked = rank_sectors(closes_by_symbol)
    if state == "UNKNOWN":
        return {"regime": state, "reason": why, "ratio": ratio_why,
                "picks": [], "note": "no action on unusable data"}
    if state == "RISK_OFF" or risk_off:
        havens = [Ranked(h, roc(closes_by_symbol.get(h) or []) or 0.0, 0.0)
                  for h in SAFE_HAVENS
                  if roc(closes_by_symbol.get(h) or []) is not None]
        havens.sort(key=lambda x: x.roc, reverse=True)
        return {"regime": "RISK_OFF", "reason": why, "ratio": ratio_why,
                "picks": havens[:1], "note": "capital to safe havens"}
    picks, seen = [], set()
    for r in ranked[:top_n]:
        if r.rs <= 0:
            continue                       # never buy a sector lagging SPY
        boost = best_subsector(r.symbol, closes_by_symbol)
        chosen = boost or r
        # A subsector can sit under two parents (IGV under both XLK and XLC),
        # which produced the same ticker twice and would have doubled the
        # intended position size. Dedupe on the SYMBOL, and when a name is
        # already taken fall back to the parent sector rather than dropping
        # the slot entirely.
        if chosen.symbol in seen:
            if r.symbol in seen:
                continue
            chosen = r
        seen.add(chosen.symbol)
        picks.append(chosen)
    return {"regime": state, "reason": why, "ratio": ratio_why,
            "picks": picks, "ranked": ranked,
            "note": f"top {len(picks)} by relative strength"}
