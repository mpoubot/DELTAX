"""Session guard and earnings blackout — the two time-based safety checks.

Both answer questions the price data cannot: *may we trade right now*, and
*is a known catalyst sitting inside this contract's life*.
"""

from datetime import date, datetime, time, timezone, timedelta
from typing import Optional

# ── Session windows (E1/E2 -> E67), US Eastern ───────────────────────────────
# E67: opened to the FULL session on Pautax's instruction. E1 confined entries
# to 09:45-10:30 and 14:30-15:15 as a proxy for "the book is deep" - but that is
# now measured directly on every candidate by gate_liquidity (OI >= 500),
# gate_spread_quality (worst leg <= 15% of mid) and MAX_QUOTE_AGE_HOURS. A clock
# cannot see a book; those gates can, and they refuse per-contract rather than
# per-hour. Two windows also cost roughly 5 of the session's 6.5 hours, which in
# a four-day contest is most of the opportunity.
#
# What is genuinely LOST, and is not covered by any gate: E2's observation that
# 15:00-16:00 carries closing/hedging flow and that a position opened late has
# no time to breathe before it inherits overnight gap risk. The gates measure
# spread and depth; they do not measure how long a trade has to work.
ENTRY_WINDOWS = [(time(9, 30), time(16, 0))]


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
# Every ETF the agent can trade. This list being incomplete is not a cosmetic
# gap: the earnings blocklist fails CLOSED, so an ETF missing from here is
# treated as a single name with no 8-K history and is blocked outright. When
# first wired, XLE/XLK/XLF/SMH and eleven others were blocked for "no filings
# retrieved" - which is correct behaviour for a stock and nonsense for a fund
# (E32). An ETF absent here silently removes itself from the tradeable universe.
NO_EARNINGS = {
    # broad market
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "IVV", "RSP", "MDY",
    # sectors
    "XLE", "XLF", "XLK", "XLI", "XLV", "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE",
    # industry / thematic
    "XOP", "SMH", "SOXX", "KRE", "XBI", "IBB", "ITB", "XHB", "XRT", "OIH", "JETS",
    # international / EM
    "EEM", "EFA", "IEFA", "IEMG", "FXI", "EWZ", "EWJ", "VEA", "VWO",
    # rates / credit / commodity
    "TLT", "IEF", "SHY", "AGG", "BND", "LQD", "HYG", "JNK", "TIP",
    "GLD", "SLV", "USO", "UNG", "GDX", "GDXJ",
    # volatility / crypto trusts
    "VXX", "UVXY", "SVXY", "VIXY", "IBIT", "GBTC", "ETHE",
}


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
