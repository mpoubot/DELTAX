"""Earnings blocklist — computed once per morning, read cheaply every cycle.

WHY A FILE AND NOT A LIVE CALL. The earnings check reads SEC EDGAR, which is
throttled to ~7 requests/second and can 403 under load. Calling it for every
name on every 5-minute cycle would be slow, rate-limited, and would put a
network dependency inside the trading loop — where a timeout becomes either a
missed trade or, worse, a silently skipped check.

So it runs ONCE in pre-market across the whole universe and writes a blocklist.
The runner reads a local file in microseconds. This is the design Matin proposed
for his own Earnings Gate, and it is the right one.

FAIL-CLOSED, in three places:
  * a name with no usable 8-K history is BLOCKED (earnings.blackout already
    does this — absence is not safety)
  * a missing blocklist file blocks every single-name candidate
  * a blocklist older than MAX_AGE_HOURS blocks every single-name candidate

ETFs are exempt by construction: they file no earnings. That exemption is the
one thing here allowed to pass without evidence, because it is structural.
"""
from __future__ import annotations
import json, os
from datetime import date, datetime, timezone
from typing import Optional

from deltax.calendar import NO_EARNINGS

PATH = "logs/earnings-blocklist.json"
MAX_AGE_HOURS = 20.0          # one trading day; a stale list is treated as absent


def build(symbols: list, expiry: date, *, profiles: Optional[dict] = None) -> dict:
    """Resolve every non-ETF name against SEC 8-K history. Slow by design."""
    from deltax import earnings as E
    blocked, clear, errors = {}, [], {}
    for sym in symbols:
        if sym in NO_EARNINGS:
            clear.append(sym)
            continue
        try:
            is_blocked, reason = E.blackout(sym, expiry, profiles)
        except Exception as exc:            # a failed lookup is not a clean bill
            errors[sym] = f"{type(exc).__name__}: {str(exc)[:90]}"
            blocked[sym] = f"lookup failed - {type(exc).__name__}"
            continue
        (blocked.__setitem__(sym, reason) if is_blocked else clear.append(sym))
    return {"built_at": datetime.now(timezone.utc).isoformat(),
            "expiry": str(expiry), "blocked": blocked,
            "clear": sorted(clear), "errors": errors,
            "n_checked": len(symbols)}


def write(data: dict, path: str = PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    return path


def load(path: str = PATH) -> Optional[dict]:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def age_hours(data: dict) -> Optional[float]:
    try:
        built = datetime.fromisoformat(data["built_at"])
        return (datetime.now(timezone.utc) - built).total_seconds() / 3600.0
    except Exception:
        return None


def check(symbol: str, expiry: date, data: Optional[dict] = None) -> tuple:
    """(allowed, reason). The only function the runner calls.

    Returns False for anything it cannot positively clear.
    """
    if symbol in NO_EARNINGS:
        return True, "ETF - files no earnings"

    if data is None:
        data = load()
    if data is None:
        return False, "no earnings blocklist - single names blocked (fail-closed)"

    age = age_hours(data)
    if age is None or age > MAX_AGE_HOURS:
        return False, (f"earnings blocklist is {age:.1f}h old (limit {MAX_AGE_HOURS}h) "
                       f"- single names blocked" if age is not None
                       else "earnings blocklist has no usable timestamp")

    # The blocklist must COVER the expiry being traded, not equal it. A list
    # built to a later date is strictly more conservative - it blocks on any
    # earnings between now and that further horizon - so it is safe to use for
    # a nearer expiry. An earlier one is not: it has not looked far enough.
    try:
        built_for = date.fromisoformat(str(data.get("expiry")))
    except (TypeError, ValueError):
        return False, "blocklist has no usable expiry - blocked"
    if built_for < expiry:
        return False, (f"blocklist only covers to {built_for}, "
                       f"trade expires {expiry} - blocked")

    if symbol in (data.get("blocked") or {}):
        return False, f"earnings: {data['blocked'][symbol]}"
    if symbol in (data.get("clear") or []):
        return True, "earnings window clear of expiry"
    return False, f"{symbol} absent from blocklist - never checked, blocked"
