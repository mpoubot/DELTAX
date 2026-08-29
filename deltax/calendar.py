"""Session guard and earnings blackout — the two time-based safety checks.

Both answer questions the price data cannot: *may we trade right now*, and
*is a known catalyst sitting inside this contract's life*.
"""

from datetime import date, datetime, time, timezone, timedelta
from typing import Optional

# ── Session windows (E1/E2), US Eastern ──────────────────────────────────────
ENTRY_WINDOWS = [(time(9, 45), time(10, 30)), (time(14, 30), time(15, 15))]


def _eastern(now_utc: datetime) -> datetime:
    """US Eastern. EDT (UTC-4) covers the whole competition window."""
    return now_utc.astimezone(timezone(timedelta(hours=-4)))


def entry_allowed(now_utc: datetime, market_is_open: bool) -> tuple:
    """(allowed, reason). Entries need BOTH an open market and a deep-liquidity window.

    Exits and flatten routines bypass this deliberately - E1 restricts opening
    a position, never closing one.
    """
    if not market_is_open:
        return False, "market closed"
    t = _eastern(now_utc).time()
    for start, end in ENTRY_WINDOWS:
        if start <= t <= end:
            return True, f"inside entry window {start:%H:%M}-{end:%H:%M} ET"
    return False, f"{t:%H:%M} ET outside entry windows 09:45-10:30 and 14:30-15:15"


# ── Earnings blackout ────────────────────────────────────────────────────────
# Ticker -> confirmed next earnings date (YYYY-MM-DD).
#
# DELIBERATELY EMPTY. Populate ONLY from a verified source - each company's
# investor-relations page or its 8-K filing - and commit the filled list as
# part of the pre-registration so the exclusions are auditable.
#
# Guessing a date here is worse than having none: a wrong date either lets a
# trade through an earnings print or blocks a good trade for no reason.
EARNINGS: dict = {
    # "AVGO": "2026-09-04",   <- example shape only; verify before adding
}

# ETFs do not report earnings. The income book trades these, so it is immune
# to this gate by construction; only single-name satellite trades need it.
NO_EARNINGS = {"SPY", "QQQ", "IWM", "DIA", "IBIT"}


def earnings_before(symbol: str, expiry: date) -> Optional[date]:
    """Confirmed earnings date falling on or before expiry, else None.

    Returns None for ETFs and for any symbol absent from the list. Absence is
    'unknown', not 'safe' - see coverage_gap().
    """
    if symbol in NO_EARNINGS:
        return None
    iso = EARNINGS.get(symbol)
    if not iso:
        return None
    d = date.fromisoformat(iso)
    return d if d <= expiry else None


def coverage_gap(symbols: list) -> list:
    """Single names with no confirmed earnings date - the gate is blind on these."""
    return sorted(s for s in symbols if s not in NO_EARNINGS and s not in EARNINGS)
