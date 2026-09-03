"""Regime nesting — waves inside waves.

A single trend label destroys the information that matters. "Bullish" is not a
market state; a bullish micro move inside a bearish short-term pullback inside a
bullish structural trend is a market state, and the three disagreeing IS the
signal.

Each horizon is classified independently from its own bars. Nothing is
collapsed, and disagreement is reported rather than resolved - the resolution
would be an invention.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import log, sqrt
from statistics import mean, stdev
from typing import Optional

from deltax.micro.inventory import daily_bars

# Horizon -> bars used to classify it. Ordered longest first so the stack reads
# structural -> micro, the way the nesting is meant to be understood.
LADDER = [("2Y", 504), ("1Y", 252), ("3M", 63), ("20D", 20), ("5D", 5)]

# Thresholds are configuration, justified, not buried. Return is measured over
# the horizon and compared against that horizon's own realised volatility, so a
# 2% move means something different over 5 days than over a year.
TREND_SIGMA = 1.0        # move beyond 1 sigma of its own vol = a trend
RANGE_SIGMA = 0.5        # inside 0.5 sigma = range
VOL_EXPANSION = 1.35     # recent vol vs horizon vol
VOL_COMPRESSION = 0.70
MIN_BARS = 5


@dataclass
class RegimeRead:
    horizon: str
    label: str = "UNKNOWN"
    confidence: float = 0.0
    ret_pct: Optional[float] = None
    vol_ratio: Optional[float] = None
    bars: int = 0
    reason: str = ""

    def as_dict(self) -> dict:
        return {"horizon": self.horizon, "regime": self.label,
                "confidence": round(self.confidence, 3),
                "return_pct": (None if self.ret_pct is None
                               else round(self.ret_pct, 2)),
                "vol_ratio": (None if self.vol_ratio is None
                              else round(self.vol_ratio, 2)),
                "bars": self.bars, "reason": self.reason}


def _classify(bars: list, horizon: str) -> RegimeRead:
    r = RegimeRead(horizon=horizon, bars=len(bars))
    if len(bars) < MIN_BARS:
        r.reason = f"{len(bars)} bars, need {MIN_BARS}"
        return r
    closes = [b.get("c") for b in bars if b.get("c")]
    if len(closes) < MIN_BARS:
        r.reason = "closes unusable"
        return r
    rets = [log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
            if closes[i - 1] > 0]
    if len(rets) < 3:
        r.reason = "not enough returns"
        return r
    total = (closes[-1] / closes[0] - 1) * 100
    sd = stdev(rets) if len(rets) > 1 else 0.0
    horizon_sigma = sd * sqrt(len(rets)) * 100          # expected move, %
    r.ret_pct = total
    # recent vol vs the horizon's own vol - the volatility-regime axis
    tail = rets[-max(len(rets) // 4, 3):]
    r.vol_ratio = ((stdev(tail) / sd) if len(tail) > 1 and sd > 0 else None)

    z = total / horizon_sigma if horizon_sigma > 1e-9 else 0.0
    if r.vol_ratio is not None and r.vol_ratio >= VOL_EXPANSION:
        r.label = "VOL_EXPANSION"
        r.confidence = min((r.vol_ratio - 1.0), 1.0)
        r.reason = f"recent vol {r.vol_ratio:.2f}x the horizon's own"
    elif r.vol_ratio is not None and r.vol_ratio <= VOL_COMPRESSION:
        r.label = "VOL_COMPRESSION"
        r.confidence = min((1.0 - r.vol_ratio), 1.0)
        r.reason = f"recent vol {r.vol_ratio:.2f}x the horizon's own"
    elif z >= TREND_SIGMA:
        r.label = "TREND_UP"
        r.confidence = min(z / 2.0, 1.0)
        r.reason = f"{total:+.1f}% is {z:.1f} sigma of its own volatility"
    elif z <= -TREND_SIGMA:
        r.label = "TREND_DOWN"
        r.confidence = min(abs(z) / 2.0, 1.0)
        r.reason = f"{total:+.1f}% is {z:.1f} sigma of its own volatility"
    elif abs(z) <= RANGE_SIGMA:
        r.label = "RANGE"
        r.confidence = min(1.0 - abs(z) / max(RANGE_SIGMA, 1e-9), 1.0)
        r.reason = f"{total:+.1f}% is inside {RANGE_SIGMA} sigma"
    else:
        r.label = "DRIFT_UP" if z > 0 else "DRIFT_DOWN"
        r.confidence = 0.4
        r.reason = f"{total:+.1f}%, between range and trend"
    return r


def stack(symbol: str, today: Optional[date] = None,
          bars: Optional[list] = None) -> dict:
    """The full nested read, longest horizon first."""
    series = bars if bars is not None else daily_bars(symbol, 504, today)
    reads = [_classify(series[-n:] if series else [], h) for h, n in LADDER]
    ok = [r for r in reads if r.label != "UNKNOWN"]
    labels = [r.label for r in ok]

    # agreement, honestly measured: how much of the stack shares a direction
    up = sum(1 for l in labels if l in ("TREND_UP", "DRIFT_UP"))
    down = sum(1 for l in labels if l in ("TREND_DOWN", "DRIFT_DOWN"))
    directional = up + down
    if directional == 0:
        alignment, direction = 0.0, "NEUTRAL"
    else:
        alignment = abs(up - down) / directional
        direction = "UP" if up > down else ("DOWN" if down > up else "MIXED")

    conflicts = []
    for i in range(len(ok) - 1):
        a, b = ok[i], ok[i + 1]
        if {a.label, b.label} & {"TREND_UP", "DRIFT_UP"} and \
           {a.label, b.label} & {"TREND_DOWN", "DRIFT_DOWN"}:
            conflicts.append(f"{a.horizon} {a.label} contains {b.horizon} {b.label}")

    return {
        "symbol": symbol,
        "stack": [r.as_dict() for r in reads],
        "available": [r.horizon for r in ok],
        "unavailable": [r.horizon for r in reads if r.label == "UNKNOWN"],
        "alignment": round(alignment, 3),
        "direction": direction,
        "conflicts": conflicts,
        "narrative": _narrate(reads),
        # confidence FALLS when horizons disagree - the system must become less
        # certain when its evidence conflicts, never more
        "confidence": round(alignment * (len(ok) / max(len(reads), 1)), 3),
        "data_quality": ("HIGH" if len(ok) >= 4 else
                         "MEDIUM" if len(ok) >= 2 else "LOW"),
    }


def _narrate(reads: list) -> str:
    ok = [r for r in reads if r.label != "UNKNOWN"]
    if not ok:
        return "No horizon has enough history to classify."
    parts = [f"{r.horizon} {r.label.lower().replace('_', ' ')}" for r in ok]
    if len(parts) == 1:
        return f"Only {parts[0]} is readable."
    inner = parts[-1]
    outer = " inside ".join(reversed(parts[:-1]))
    return f"{inner.capitalize()} inside {outer}."
