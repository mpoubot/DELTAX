"""Canonical market events, and the adapters that produce them.

Both modes emit these same three types. A feature calculated in replay is
computed by the identical code path that computes it live - the property the
whole design exists to guarantee.

Timestamps are UTC and nanosecond-aware. Alpaca returns RFC3339 with nanosecond
precision ("2026-09-02T14:00:00.03174671Z"); Python's fromisoformat truncates to
microseconds, which is fine for ordering but must not be mistaken for the exchange
timestamp itself. Both are kept.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import json
import subprocess

UTC = timezone.utc


def parse_ts(raw: str) -> Optional[datetime]:
    """RFC3339 with optional nanoseconds -> aware datetime. None if unusable."""
    if not raw:
        return None
    s = str(raw).replace("Z", "+00:00")
    # trim ns -> us; fromisoformat rejects more than 6 fractional digits
    if "." in s:
        head, _, tail = s.partition(".")
        digits = "".join(ch for ch in tail if ch.isdigit())
        offset = tail[len(digits):]
        s = f"{head}.{digits[:6]:0<6}{offset}"
    try:
        d = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Trade:
    symbol: str
    ts: datetime
    price: float
    size: int
    exchange: str = ""
    conditions: tuple = ()
    tape: str = ""
    raw_ts: str = ""


@dataclass(frozen=True)
class Quote:
    """Top of book. NBBO only - neither provider entitles depth on this account,
    so nothing downstream may call this an order book."""
    symbol: str
    ts: datetime
    bid: float
    bid_size: int
    ask: float
    ask_size: int
    bid_ex: str = ""
    ask_ex: str = ""
    raw_ts: str = ""

    @property
    def mid(self) -> Optional[float]:
        if self.bid > 0 and self.ask > 0 and self.ask >= self.bid:
            return (self.bid + self.ask) / 2.0
        return None

    @property
    def spread(self) -> Optional[float]:
        if self.bid > 0 and self.ask > 0 and self.ask >= self.bid:
            return self.ask - self.bid
        return None

    @property
    def crossed(self) -> bool:
        """Ask below bid. Real and transient around the open; such a quote is
        unusable for a midpoint and must not be silently averaged."""
        return self.bid > 0 and self.ask > 0 and self.ask < self.bid


@dataclass(frozen=True)
class Bar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    trades: Optional[int] = None


def _cli(args: list, timeout: int = 45) -> dict:
    out = subprocess.run(["alpaca"] + args + ["--quiet"],
                         capture_output=True, text=True, timeout=timeout)
    if out.returncode or not out.stdout.strip():
        raise RuntimeError((out.stderr or "empty response").strip()[:160])
    return json.loads(out.stdout)


# ── adapters ────────────────────────────────────────────────────────────────
# Each returns canonical events sorted by timestamp. A window is requested by
# time, never by "latest N", so replay and live differ only in which window is
# asked for - not in how the result is interpreted.

# A single request is capped, and the cap is reached FAST: measured on SPY,
# 8,000 trades covered 337s but 8,000 quotes covered only 42s (190 quotes/sec).
# Without paging, a "20 minute window" silently becomes 42 seconds of quotes
# followed by nothing - and the tape then classifies every later print UNKNOWN
# because no fresh book exists. That is not a missing feature, it is a feature
# that looks present and is wrong, so paging is mandatory rather than an option.
MAX_PAGES = 40

# E108: the Alpaca free tier refuses SIP trades/quotes newer than about 15
# minutes - "subscription does not permit querying recent SIP data". Measured
# 3 Sep 10:30 ET: a window ending 20 min ago returned 27,539 prints; one
# ending 10 min ago was refused outright. Last night's replay worked only
# because its window was hours old. "Live" on this account therefore means
# "15 minutes ago", and the engine says so instead of letting the CLI 403 and
# a caller mistake that for an empty tape.
MIN_SIP_LAG_MIN = 15


def _check_window(end: str) -> None:
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    e = parse_ts(end)
    if e is None:
        return
    cutoff = _dt.now(_tz.utc) - _td(minutes=MIN_SIP_LAG_MIN)
    if e > cutoff:
        raise RuntimeError(
            f"SIP window ends {end}; this subscription only serves data older "
            f"than {MIN_SIP_LAG_MIN} min (cutoff {cutoff:%H:%M:%S}Z). "
            f"Live tape on this tier is {MIN_SIP_LAG_MIN}-minute delayed.")


def _paged(args: list, key: str, limit: int) -> list:
    rows, token, pages = [], None, 0
    while pages < MAX_PAGES:
        a = list(args) + ["--limit", str(limit)]
        if token:
            a += ["--page-token", token]
        d = _cli(a)
        got = d.get(key) or []
        rows.extend(got)
        token = d.get("next_page_token")
        pages += 1
        if not token or not got:
            break
    return rows


def fetch_trades(symbol: str, start: str, end: str, limit: int = 10000) -> list:
    _check_window(end)                    # E108: refuse a forbidden window loudly
    raw = _paged(["data", "trades", "--symbol", symbol,
                  "--start", start, "--end", end], "trades", limit)
    out = []
    for t in raw:
        ts = parse_ts(t.get("t"))
        if ts is None:
            continue
        try:
            out.append(Trade(symbol=symbol, ts=ts, price=float(t["p"]),
                             size=int(t["s"]), exchange=str(t.get("x") or ""),
                             conditions=tuple(t.get("c") or ()),
                             tape=str(t.get("z") or ""), raw_ts=str(t.get("t"))))
        except (KeyError, TypeError, ValueError):
            continue                      # a malformed print is dropped, never guessed
    out.sort(key=lambda e: e.ts)
    return out


def fetch_quotes(symbol: str, start: str, end: str, limit: int = 10000) -> list:
    _check_window(end)                    # E108: refuse a forbidden window loudly
    raw = _paged(["data", "quotes", "--symbol", symbol,
                  "--start", start, "--end", end], "quotes", limit)
    out = []
    for q in raw:
        ts = parse_ts(q.get("t"))
        if ts is None:
            continue
        try:
            out.append(Quote(symbol=symbol, ts=ts,
                             bid=float(q.get("bp") or 0), bid_size=int(q.get("bs") or 0),
                             ask=float(q.get("ap") or 0), ask_size=int(q.get("as") or 0),
                             bid_ex=str(q.get("bx") or ""), ask_ex=str(q.get("ax") or ""),
                             raw_ts=str(q.get("t"))))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda e: e.ts)
    return out


def merge(*streams) -> list:
    """Interleave event streams into one chronological sequence.

    Stable on ties: a quote timestamped identically to a trade is emitted
    BEFORE it, so the trade is classified against a book that already existed.
    Sorting trades first would let a print be measured against a quote that had
    not yet been published - a lookahead of microseconds that still inverts the
    aggressor label.
    """
    order = {Quote: 0, Trade: 1, Bar: 2}
    events = [e for s in streams for e in s]
    events.sort(key=lambda e: (e.ts, order.get(type(e), 9)))
    return events
