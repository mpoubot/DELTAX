"""The shared feature engine. Live and replay both run exactly this.

POINT-IN-TIME BY CONSTRUCTION. The engine is fed one event at a time via
`step()` and keeps only what it has already seen. It holds no index, no future
window, and no reference to the source stream - so there is no mechanism by
which a feature could read ahead. Lookahead is prevented structurally rather
than by reviewer discipline, which is the only version of that guarantee worth
having.

Every feature reports a `reliability` and `status`. Missing data is never zero:
an absent quote yields UNAVAILABLE, and downstream weighting must treat that
differently from a genuine reading of 0.0.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from deltax.micro.events import Trade, Quote, Bar

EPS = 1e-9

# Thresholds are configuration, not magic numbers buried in code. Each is
# justified where it is used and overridable at construction.
DEFAULTS = {
    # rolling windows, seconds - the spec's 5/15/30/60/300
    "windows": (5, 15, 30, 60, 300),
    # a quote older than this cannot classify a print. Alpaca NBBO updates many
    # times a second in liquid names; 2s is generous and still excludes a stale
    # book left over from a halt.
    "quote_max_age_s": 2.0,
    # a print within this fraction of the spread from the midpoint is genuinely
    # ambiguous and is counted UNKNOWN rather than forced to a side.
    "mid_tolerance": 0.10,
    # value area, fraction of session volume - the conventional 70%
    "value_area": 0.70,
    # minimum prints before tape features are considered reliable
    "min_trades_for_tape": 30,
}


@dataclass
class Feature:
    """One signal, in the spec's normalized shape."""
    name: str
    direction: Optional[float] = None      # -1..+1
    strength: float = 0.0                  # 0..1
    reliability: float = 0.0               # 0..1
    freshness_s: Optional[float] = None
    status: str = "UNAVAILABLE"            # OK | DEGRADED | UNAVAILABLE
    reason: str = ""
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"signal": self.name, "direction": self.direction,
                "strength": round(self.strength, 4),
                "reliability": round(self.reliability, 4),
                "freshness_seconds": (None if self.freshness_s is None
                                      else round(self.freshness_s, 3)),
                "status": self.status, "reason": self.reason, **self.detail}


class FeatureEngine:
    """Consumes canonical events in timestamp order; exposes features as of the
    last event consumed. Never reaches forward."""

    def __init__(self, symbol: str, config: Optional[dict] = None):
        self.symbol = symbol
        self.cfg = {**DEFAULTS, **(config or {})}
        self.now = None                    # timestamp of the last event seen
        self._quote: Optional[Quote] = None
        self._trades: deque = deque()      # (ts, price, size, side)
        self._by_price: dict = {}          # price bucket -> volume
        self._session_high: Optional[float] = None
        self._session_low: Optional[float] = None
        self._high_events = 0
        self._low_events = 0
        self._last_price: Optional[float] = None
        self._quote_updates: deque = deque()
        self._dropped = 0

    # ── ingestion ───────────────────────────────────────────────────────────
    def step(self, ev) -> None:
        """Consume ONE event. Out-of-order events are dropped, not reordered:
        silently accepting them would let a late print alter a window that has
        already produced a decision."""
        if self.now is not None and ev.ts < self.now:
            self._dropped += 1
            return
        self.now = ev.ts
        if isinstance(ev, Quote):
            self._on_quote(ev)
        elif isinstance(ev, Trade):
            self._on_trade(ev)
        elif isinstance(ev, Bar):
            self._on_bar(ev)
        self._evict()

    def _on_quote(self, q: Quote) -> None:
        self._quote_updates.append(q.ts)
        if q.crossed:
            return                         # a crossed book prices nothing
        self._quote = q

    def _on_trade(self, t: Trade) -> None:
        self._trades.append((t.ts, t.price, t.size, self._classify(t)))
        self._last_price = t.price
        # volume profile bucket, sized to the instrument rather than globally
        b = self._bucket(t.price)
        self._by_price[b] = self._by_price.get(b, 0.0) + t.size
        # session extremes and the events that made them
        if self._session_high is None or t.price > self._session_high:
            if self._session_high is not None:
                self._high_events += 1
            self._session_high = t.price
        if self._session_low is None or t.price < self._session_low:
            if self._session_low is not None:
                self._low_events += 1
            self._session_low = t.price

    def _on_bar(self, b: Bar) -> None:
        if b.vwap and b.volume:
            self._by_price[self._bucket(b.vwap)] = (
                self._by_price.get(self._bucket(b.vwap), 0.0) + b.volume)
        self._last_price = b.close
        if self._session_high is None or b.high > self._session_high:
            self._session_high = b.high
        if self._session_low is None or b.low < self._session_low:
            self._session_low = b.low

    def _bucket(self, price: float) -> float:
        """Tick-proportional bucket. A fixed cent bucket is meaningless across a
        $35 ETF and a $765 index, so the increment scales with price."""
        inc = 0.01 if price < 25 else (0.05 if price < 100 else
                                       (0.10 if price < 300 else 0.25))
        return round(round(price / inc) * inc, 4)

    def _classify(self, t: Trade) -> str:
        """Aggressor APPROXIMATION - never proof of intent.

        A print above the midpoint is buy-LIKE. It may equally be a seller
        crossing the spread, a leg of a spread, or a hedge. The name says
        'like' because that is the strongest claim the data supports.
        """
        q = self._quote
        if q is None or q.mid is None:
            return "UNKNOWN"
        age = (t.ts - q.ts).total_seconds()
        if age < 0 or age > self.cfg["quote_max_age_s"]:
            return "UNKNOWN"               # stale book cannot classify
        sp = q.spread or 0.0
        tol = max(sp * self.cfg["mid_tolerance"], 1e-4)
        if t.price > q.mid + tol:
            return "BUY_LIKE"
        if t.price < q.mid - tol:
            return "SELL_LIKE"
        return "UNKNOWN"

    def _evict(self) -> None:
        if not self._trades:
            return
        cutoff = self.now - timedelta(seconds=max(self.cfg["windows"]))
        while self._trades and self._trades[0][0] < cutoff:
            self._trades.popleft()
        while self._quote_updates and self._quote_updates[0] < cutoff:
            self._quote_updates.popleft()

    # ── features ────────────────────────────────────────────────────────────
    def tape_pressure(self, window_s: int = 60) -> Feature:
        f = Feature("TAPE_PRESSURE")
        if self.now is None:
            f.reason = "no events consumed"
            return f
        cut = self.now - timedelta(seconds=window_s)
        w = [t for t in self._trades if t[0] >= cut]
        if not w:
            f.reason = f"no prints in the last {window_s}s"
            return f
        buy = sum(s for _, _, s, k in w if k == "BUY_LIKE")
        sell = sum(s for _, _, s, k in w if k == "SELL_LIKE")
        unk = sum(s for _, _, s, k in w if k == "UNKNOWN")
        total = buy + sell + unk
        classified = buy + sell
        f.direction = (buy - sell) / max(classified, EPS) if classified else None
        f.strength = min(classified / max(total, EPS), 1.0) if total else 0.0
        # reliability falls with sample size AND with the unclassified share
        n_ok = min(len(w) / max(self.cfg["min_trades_for_tape"], 1), 1.0)
        f.reliability = round(n_ok * (classified / max(total, EPS)), 4) if total else 0.0
        f.freshness_s = (self.now - w[-1][0]).total_seconds()
        f.status = "OK" if f.reliability >= 0.4 else "DEGRADED"
        f.detail = {"trades": len(w), "buy_like": buy, "sell_like": sell,
                    "unknown": unk,
                    "trades_per_second": round(len(w) / max(window_s, 1), 3),
                    "shares_per_second": round(total / max(window_s, 1), 1)}
        f.reason = (f"{len(w)} prints, {buy/max(total,EPS):.0%} buy-like, "
                    f"{unk/max(total,EPS):.0%} unclassified (approximation)")
        return f

    def nbbo_pressure(self) -> Feature:
        """Top-of-book only. Named NBBO, never 'order book' - depth is not
        entitled on this account and the distinction is not cosmetic."""
        f = Feature("NBBO_PRESSURE")
        q = self._quote
        if q is None or self.now is None:
            f.reason = "no usable quote"
            return f
        age = (self.now - q.ts).total_seconds()
        if q.bid_size <= 0 and q.ask_size <= 0:
            f.reason = "zero size on both sides"
            return f
        imb = (q.bid_size - q.ask_size) / max(q.bid_size + q.ask_size, EPS)
        micro = ((q.ask * q.bid_size + q.bid * q.ask_size)
                 / max(q.bid_size + q.ask_size, EPS))
        mid = q.mid
        f.direction = max(-1.0, min(1.0, imb))
        f.strength = abs(imb)
        # one large displayed size is not proof; freshness carries the weight
        f.reliability = round(max(0.0, 1.0 - age / max(self.cfg["quote_max_age_s"], EPS)) * 0.8, 4)
        f.freshness_s = age
        f.status = "OK" if age <= self.cfg["quote_max_age_s"] else "DEGRADED"
        f.detail = {"bid": q.bid, "bid_size": q.bid_size, "ask": q.ask,
                    "ask_size": q.ask_size,
                    "spread": None if q.spread is None else round(q.spread, 4),
                    "microprice": round(micro, 4),
                    "microprice_offset": (None if mid is None
                                          else round(micro - mid, 5)),
                    "quote_updates": len(self._quote_updates)}
        f.reason = f"bid/ask size {q.bid_size}x{q.ask_size}, quote {age:.1f}s old"
        return f

    def volume_profile(self) -> Feature:
        """POC, value area, and where price sits relative to it."""
        f = Feature("VOLUME_PROFILE")
        if not self._by_price or self._last_price is None:
            f.reason = "no volume distribution yet"
            return f
        buckets = sorted(self._by_price.items())
        total = sum(v for _, v in buckets)
        poc = max(buckets, key=lambda kv: kv[1])[0]
        # value area: expand from POC until the target share of volume is inside
        target = total * self.cfg["value_area"]
        idx = [p for p, _ in buckets].index(poc)
        lo = hi = idx
        acc = buckets[idx][1]
        while acc < target and (lo > 0 or hi < len(buckets) - 1):
            take_lo = buckets[lo - 1][1] if lo > 0 else -1
            take_hi = buckets[hi + 1][1] if hi < len(buckets) - 1 else -1
            if take_hi >= take_lo:
                hi += 1; acc += buckets[hi][1]
            else:
                lo -= 1; acc += buckets[lo][1]
        val, vah = buckets[lo][0], buckets[hi][0]
        px = self._last_price
        where = ("ABOVE_VALUE" if px > vah else
                 "BELOW_VALUE" if px < val else "INSIDE_VALUE")
        span = max(vah - val, EPS)
        f.direction = max(-1.0, min(1.0, (px - poc) / span))
        f.strength = min(abs(px - poc) / span, 1.0)
        f.reliability = round(min(total / 100000.0, 1.0), 4)
        f.freshness_s = 0.0
        f.status = "OK" if total > 0 else "UNAVAILABLE"
        f.detail = {"poc": poc, "vah": vah, "val": val, "position": where,
                    "distance_from_poc": round(px - poc, 4),
                    "total_volume": round(total, 1), "buckets": len(buckets)}
        f.reason = f"price {where.lower().replace('_',' ')}, POC {poc}"
        return f

    def high_low_direction(self) -> Feature:
        f = Feature("HIGH_LOW_DIRECTION")
        tot = self._high_events + self._low_events
        if tot == 0:
            f.reason = "no new session extremes yet"
            f.status = "OK"                # genuinely zero, not missing
            f.direction, f.strength, f.reliability = 0.0, 0.0, 0.5
            return f
        f.direction = (self._high_events - self._low_events) / max(tot, EPS)
        f.strength = min(tot / 20.0, 1.0)
        f.reliability = round(min(tot / 10.0, 1.0), 4)
        f.freshness_s = 0.0
        f.status = "OK"
        f.detail = {"high_events": self._high_events,
                    "low_events": self._low_events,
                    "net": self._high_events - self._low_events,
                    "session_high": self._session_high,
                    "session_low": self._session_low}
        f.reason = f"{self._high_events} new highs vs {self._low_events} new lows"
        return f

    def health(self) -> dict:
        return {"symbol": self.symbol,
                "as_of": None if self.now is None else self.now.isoformat(),
                "trades_in_window": len(self._trades),
                "quote": "PRESENT" if self._quote else "UNAVAILABLE",
                "out_of_order_dropped": self._dropped}

    def snapshot(self) -> dict:
        """Every feature as of the last event consumed."""
        return {"as_of": None if self.now is None else self.now.isoformat(),
                "symbol": self.symbol,
                "features": [self.tape_pressure().as_dict(),
                             self.nbbo_pressure().as_dict(),
                             self.volume_profile().as_dict(),
                             self.high_low_direction().as_dict()],
                "health": self.health()}
