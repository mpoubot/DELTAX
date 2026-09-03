"""Multi-timeframe inventory — where business actually got done, and who may care.

A volume profile is not support and resistance. It is a record of where
participants transacted, which is the only observable trace of where they may
now be positioned.

WHAT THIS CANNOT KNOW, and says so everywhere: nothing in public market data
reveals whether historical volume opened longs or shorts. Every statement about
participants is therefore a HYPOTHESIS with a stated possibility level, never a
claim. The word "may" in this module is load-bearing.

Long horizons come from Massive daily aggregates and short ones from minute
aggregates - both entitled on this account. Trades and quotes are not entitled
on Massive; those come from Alpaca via events.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional
import json
import os
import urllib.request
import urllib.error

UTC = timezone.utc

# Horizons in trading days. A trader may hold for minutes or for years, so
# inventory laid down long ago still matters - but only where enough data
# exists, which is checked rather than assumed.
HORIZONS = {
    "5D": 5, "10D": 10, "20D": 20,
    "3M": 63, "6M": 126, "1Y": 252, "2Y": 504,
}

# A profile needs enough bars to describe a distribution rather than a handful
# of prints. Below this the horizon is reported UNAVAILABLE, not approximated.
MIN_BARS = {"5D": 4, "10D": 8, "20D": 15, "3M": 45, "6M": 90, "1Y": 180, "2Y": 350}

VALUE_AREA = 0.70          # conventional 70% of volume
HVN_PERCENTILE = 0.80      # a bucket above this share of the max is a high node
LVN_PERCENTILE = 0.20      # below this is a low node - a gap price moves through
CLUSTER_TOLERANCE = 0.004  # 0.4% - levels closer than this are one zone


def _massive(path: str, timeout: int = 25) -> dict:
    key = os.environ.get("MASSIVE_API_KEY")
    if not key:
        raise RuntimeError("MASSIVE_API_KEY not set")
    sep = "&" if "?" in path else "?"
    with urllib.request.urlopen(
            f"https://api.massive.com{path}{sep}apiKey={key}", timeout=timeout) as r:
        return json.loads(r.read())


def daily_bars(symbol: str, days: int, today: Optional[date] = None) -> list:
    """Daily OHLCV+VWAP. Returns [] on any failure - never a fabricated series.

    Alpaca first. Measured 2 Sep: Massive rate-limits after roughly five calls -
    a seven-name sweep returned bars for five, and the next sweep returned
    nothing at all. The dashboard publishes every three minutes, so it would
    have hit that ceiling on every render and the fail-soft caller would have
    hidden it. Alpaca serves the same daily bars, is already the repo's feed,
    and did not throttle under the same load. Massive remains the fallback.
    """
    today = today or date.today()
    start = today - timedelta(days=int(days * 1.5) + 10)   # calendar vs trading
    try:
        from deltax.feeds import AlpacaFeed
        bars = AlpacaFeed().daily_bars(symbol, str(start), str(today), 5000)
        bars = [b for b in (bars or []) if b.get("v")]
        if bars:
            return bars
    except Exception:
        pass
    try:
        d = _massive(f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{today}?limit=5000")
    except Exception:
        return []
    return [b for b in (d.get("results") or []) if b.get("v")]


@dataclass
class Profile:
    """One horizon's inventory distribution."""
    horizon: str
    poc: Optional[float] = None
    vah: Optional[float] = None
    val: Optional[float] = None
    hvns: list = field(default_factory=list)
    lvns: list = field(default_factory=list)
    total_volume: float = 0.0
    bars: int = 0
    status: str = "UNAVAILABLE"
    reason: str = ""

    def as_dict(self) -> dict:
        return {"horizon": self.horizon, "poc": self.poc, "vah": self.vah,
                "val": self.val, "hvns": self.hvns[:6], "lvns": self.lvns[:6],
                "total_volume": round(self.total_volume, 1), "bars": self.bars,
                "status": self.status, "reason": self.reason}


def _bucket_size(price: float) -> float:
    return 0.01 if price < 25 else (0.05 if price < 100 else
                                    (0.10 if price < 300 else 0.25))


def build_profile(bars: list, horizon: str) -> Profile:
    """Volume by price from daily bars.

    Each bar's volume is placed at its VWAP when supplied, which is the best
    single-price summary available at daily resolution. This is an
    APPROXIMATION of the true intraday distribution: a wide-range day really
    spread its volume across the range, and this concentrates it. Documented
    rather than hidden, because it understates how wide real inventory zones are.
    """
    p = Profile(horizon=horizon, bars=len(bars))
    need = MIN_BARS.get(horizon, 5)
    if len(bars) < need:
        p.reason = f"{len(bars)} bars, need {need}"
        return p
    dist: dict = {}
    for b in bars:
        px = b.get("vw") or b.get("c")
        vol = b.get("v") or 0
        if not px or not vol:
            continue
        inc = _bucket_size(px)
        k = round(round(px / inc) * inc, 4)
        dist[k] = dist.get(k, 0.0) + float(vol)
    if not dist:
        p.reason = "no usable volume"
        return p
    items = sorted(dist.items())
    total = sum(v for _, v in items)
    poc = max(items, key=lambda kv: kv[1])[0]
    peak = max(v for _, v in items)
    # value area expands from the POC until it holds the target share
    idx = [k for k, _ in items].index(poc)
    lo = hi = idx
    acc = items[idx][1]
    target = total * VALUE_AREA
    while acc < target and (lo > 0 or hi < len(items) - 1):
        a = items[lo - 1][1] if lo > 0 else -1
        b_ = items[hi + 1][1] if hi < len(items) - 1 else -1
        if b_ >= a:
            hi += 1; acc += items[hi][1]
        else:
            lo -= 1; acc += items[lo][1]
    p.poc, p.val, p.vah = poc, items[lo][0], items[hi][0]
    p.total_volume = total
    p.hvns = sorted([k for k, v in items if v >= peak * HVN_PERCENTILE])
    p.lvns = sorted([k for k, v in items if v <= peak * LVN_PERCENTILE])
    p.status = "OK"
    p.reason = f"{len(items)} price buckets over {len(bars)} bars"
    return p


def build_all(symbol: str, today: Optional[date] = None) -> dict:
    """Every horizon that has enough history. Missing ones are marked, not faked."""
    longest = daily_bars(symbol, max(HORIZONS.values()), today)
    out = {}
    for name, n in HORIZONS.items():
        out[name] = build_profile(longest[-n:] if longest else [], name)
    return out


@dataclass
class Zone:
    """Several horizons agreeing on one price area."""
    low: float
    high: float
    horizons: list
    strength: float
    total_volume: float

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0

    def as_dict(self) -> dict:
        return {"low": round(self.low, 2), "high": round(self.high, 2),
                "mid": round(self.mid, 2), "horizons": self.horizons,
                "strength": round(self.strength, 3),
                "total_volume": round(self.total_volume, 1)}


# A level confirmed by a long horizon is different in kind from one made in the
# last week: it represents business done by participants who may still be there.
HORIZON_WEIGHT = {"5D": 0.5, "10D": 0.7, "20D": 1.0,
                  "3M": 1.4, "6M": 1.6, "1Y": 1.8, "2Y": 2.0}


def cluster(profiles: dict, tolerance: float = CLUSTER_TOLERANCE) -> list:
    """Merge POCs and HVNs that overlap across horizons into inventory zones.

    Strength weights BOTH the number of independent horizons agreeing and how
    old they are - a price confirmed by the 3-month and 1-year profiles is a
    materially stronger claim than one confirmed twice inside a week.
    """
    pts = []
    for name, p in profiles.items():
        if p.status != "OK":
            continue
        w = HORIZON_WEIGHT.get(name, 1.0)
        if p.poc:
            pts.append((p.poc, name, w * 1.5, p.total_volume))   # POC outweighs an HVN
        for h in p.hvns[:4]:
            pts.append((h, name, w, p.total_volume))
    if not pts:
        return []
    pts.sort()
    zones, cur = [], [pts[0]]
    for pt in pts[1:]:
        if abs(pt[0] - cur[-1][0]) / max(cur[-1][0], 1e-9) <= tolerance:
            cur.append(pt)
        else:
            zones.append(cur); cur = [pt]
    zones.append(cur)
    out = []
    for z in zones:
        hs = sorted({h for _, h, _, _ in z})
        out.append(Zone(low=min(p for p, _, _, _ in z),
                        high=max(p for p, _, _, _ in z),
                        horizons=hs,
                        strength=sum(w for _, _, w, _ in z) * len(hs) ** 0.5,
                        total_volume=sum(v for _, _, _, v in z)))
    out.sort(key=lambda z: -z.strength)
    return out


def participant_hypotheses(price: float, zone: Zone) -> dict:
    """Who MAY be positioned where, and what MAY force them to act.

    Every value is a possibility level, never a probability, because the
    underlying fact - whether that volume opened longs or shorts - is not
    observable in public data. Presenting these as probabilities would be
    fabricating precision that does not exist.
    """
    if price <= 0 or zone.mid <= 0:
        return {"status": "UNAVAILABLE", "reason": "no price"}
    dist = (price - zone.mid) / zone.mid
    strong = zone.strength >= 4.0
    near = abs(dist) < 0.01

    if dist > 0.002:
        state = "PRICE_ABOVE_INVENTORY"
        h = {"long_inventory_profitable": "HIGH",
             "short_inventory_underwater": "HIGH" if strong else "MEDIUM",
             "profit_taking_risk": "MEDIUM-HIGH" if dist > 0.03 else "MEDIUM",
             "short_cover_potential": "HIGH" if strong else "MEDIUM",
             "breakeven_selling_on_return": "MEDIUM"}
        forced = ("A move back INTO the zone may meet longs defending entry and "
                  "shorts seeking breakeven; a move further away may force "
                  "short covering.")
    elif dist < -0.002:
        state = "PRICE_BELOW_INVENTORY"
        h = {"long_inventory_underwater": "HIGH",
             "short_inventory_profitable": "HIGH" if strong else "MEDIUM",
             "breakeven_selling_on_rally": "HIGH" if strong else "MEDIUM",
             "long_liquidation_risk": "MEDIUM-HIGH" if dist < -0.03 else "MEDIUM",
             "profit_taking_risk": "LOW"}
        forced = ("A rally back INTO the zone may meet trapped longs selling at "
                  "breakeven; continued weakness may force long liquidation.")
    else:
        state = "PRICE_INSIDE_INVENTORY"
        h = {"positioning_mixed": "HIGH", "profit_taking_risk": "MEDIUM",
             "breakeven_selling_on_rally": "MEDIUM",
             "short_cover_potential": "MEDIUM"}
        forced = ("Price is inside the zone, so participants are on both sides "
                  "of entry. Direction out of the zone determines who is forced.")

    return {"status": "OK", "state": state,
            "zone": zone.as_dict(),
            "distance_pct": round(dist * 100, 3),
            "near_zone": near,
            "hypotheses": h,
            "if_price_moves": forced,
            "caveat": ("Whether this volume opened longs or shorts is NOT "
                       "observable. These are possibilities, not probabilities, "
                       "and require historical validation before use.")}


def analyse(symbol: str, price: float, today: Optional[date] = None) -> dict:
    """Full multi-timeframe inventory picture for one symbol."""
    profiles = build_all(symbol, today)
    zones = cluster(profiles)
    ok = [n for n, p in profiles.items() if p.status == "OK"]
    return {
        "symbol": symbol, "price": price,
        "horizons_available": ok,
        "horizons_unavailable": [n for n, p in profiles.items() if p.status != "OK"],
        "profiles": {n: p.as_dict() for n, p in profiles.items()},
        "zones": [z.as_dict() for z in zones[:5]],
        "nearest": (participant_hypotheses(
            price, min(zones, key=lambda z: abs(z.mid - price)))
            if zones and price else {"status": "UNAVAILABLE"}),
        "strongest": (participant_hypotheses(price, zones[0])
                      if zones and price else {"status": "UNAVAILABLE"}),
        "data_quality": ("HIGH" if len(ok) >= 6 else
                         "MEDIUM" if len(ok) >= 3 else "LOW"),
    }
