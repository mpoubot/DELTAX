"""Pre-open morning brief.

One command, run before the 09:45 entry window. Answers: can we trade today,
what regime are we in, which names are excluded and why, are our feeds alive,
and what did yesterday's session record.

Every source is one we are licensed to use - Alpaca for market data, SEC for
filings. Nothing here scrapes a site that forbids it.
"""

from datetime import date, datetime, timezone
from typing import Optional
import json

from deltax import feeds
from deltax.calendar import entry_allowed
from deltax.daily import run as daily_run, WATCHLIST
from deltax.screener import assess_regime, posture, TARGET_DELTA_BY_WEAK, BENCHMARKS

SATELLITE = [s for s in WATCHLIST if s not in BENCHMARKS]


def brief(feed, today: Optional[date] = None, check_earnings: bool = True) -> dict:
    today = today or date.today()
    now = datetime.now(timezone.utc)

    clock = feed.clock()
    is_open = bool(clock.get("is_open"))
    allowed, window_reason = entry_allowed(now, is_open)

    snaps = feed.snapshots(BENCHMARKS)
    regime = assess_regime(snaps)
    target_delta = TARGET_DELTA_BY_WEAK[min(regime.weak_count, 3)]

    universe = daily_run(feed, today=today)
    tradeable = set(universe["tradeable_universe"])

    blocked, clear, unchecked = {}, [], []
    if check_earnings:
        try:
            from deltax.earnings import profile, blackout
            for s in SATELLITE:
                if s not in tradeable:
                    continue
                try:
                    p = profile(s)
                    b, why = blackout(s, today, profiles={s: p})
                    # block if earnings could land before a typical 18 DTE expiry
                    horizon = date.fromordinal(today.toordinal() + 18)
                    b, why = blackout(s, horizon, profiles={s: p})
                    (blocked.setdefault(s, why) if b else clear.append(s))
                except Exception as e:
                    unchecked.append(f"{s} ({type(e).__name__})")
        except RuntimeError as e:
            unchecked = [f"earnings check unavailable: {e}"]

    return {
        "as_of": today.isoformat(),
        "generated_utc": now.isoformat(timespec="seconds"),
        "market_open": is_open,
        "next_open": clock.get("next_open"),
        "entry_allowed": allowed,
        "window": window_reason,
        "regime": {
            "weak_count": regime.weak_count,
            "weak": regime.weak_symbols,
            "detail": regime.detail,
            "target_short_delta": target_delta,
            "posture": [f"{sym} {side}" for sym, side in posture(regime)],
        },
        "universe": {
            "tradeable": sorted(tradeable),
            "excluded_thin_chain": [s for s in WATCHLIST if s not in tradeable],
        },
        "earnings": {
            "blocked": blocked,
            "clear": sorted(clear),
            "unchecked": unchecked,
        },
    }


def render(b: dict) -> str:
    L = []
    L.append(f"DELTAX morning brief — {b['as_of']}")
    L.append("=" * 52)
    L.append(f"market open: {b['market_open']}   entries: "
             f"{'ALLOWED' if b['entry_allowed'] else 'BLOCKED'}  ({b['window']})")
    if not b["market_open"]:
        L.append(f"next open: {b['next_open']}")
    r = b["regime"]
    L.append("")
    L.append(f"REGIME  {r['weak_count']}/3 weak {r['weak'] or ''}"
             f"   target short delta {r['target_short_delta']}")
    for sym, d in r["detail"].items():
        if d.get("price") is not None:
            L.append(f"   {sym:4} {d['price']:>9.2f} vs vwap {d['vwap']:>9.2f}"
                     f"  {'WEAK' if d['weak'] else 'strong'}")
    L.append(f"   posture: {', '.join(r['posture'])}")
    e = b["earnings"]
    L.append("")
    L.append(f"EARNINGS BLACKOUT  ({len(e['blocked'])} blocked)")
    for s, why in e["blocked"].items():
        L.append(f"   BLOCK {s:6} {why.split(': ',1)[-1][:62]}")
    if e["clear"]:
        L.append(f"   clear: {', '.join(e['clear'])}")
    if e["unchecked"]:
        L.append(f"   UNCHECKED: {'; '.join(e['unchecked'])[:70]}")
    u = b["universe"]
    if u["excluded_thin_chain"]:
        L.append("")
        L.append(f"THIN CHAINS excluded: {', '.join(u['excluded_thin_chain'])}")
    return "\n".join(L)


if __name__ == "__main__":
    from deltax.feeds import AlpacaFeed
    b = brief(AlpacaFeed())
    print(render(b))
    with open(f"data/morning-{b['as_of']}.json", "w") as f:
        json.dump(b, f, indent=1)
