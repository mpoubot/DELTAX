"""Earnings-date inference from SEC 8-K Item 2.02 filings.

Item 2.02 ("Results of Operations and Financial Condition") is the filing a
company makes when it releases earnings. Filing dates are therefore an
authoritative record of when earnings HAPPENED - free, public, no vendor.

What this gives us and what it does not:

  FACT      - past earnings dates (structural: it is the filing record)
  INFERENCE - the next expected date, from the observed cadence (empirical)

Under E10 the inference cannot be treated as a confirmed date. So the gate
consumes a WINDOW, not a point estimate, and any overlap with a contract's
life is a blackout. Fail-closed: an unknown symbol blocks rather than passes.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Optional
import html
import json
import re
import time

from deltax.rss import fetch, SEC_USER_AGENT

EDGAR_8K = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            "&CIK={cik}&type=8-K&count=40&output=atom")
TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"

_cik_cache: dict = {}
_last_request = [0.0]
MIN_REQUEST_INTERVAL = 0.15   # SEC throttles; batch runs silently returned empty


class SECFetchError(RuntimeError):
    """Fetch failed. Distinct from 'no filings' - never conflate the two."""


# Foreign private issuers file 6-K / 20-F, never 8-K, so Item 2.02 does not
# exist for them. Structural, not a data gap - a different source is required.
FOREIGN_FORMS = {"6-K", "20-F", "40-F"}


def _throttle():
    wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()


@dataclass
class EarningsProfile:
    symbol: str
    history: list          # confirmed past earnings dates, newest first
    median_gap: Optional[int]
    min_gap: Optional[int]
    max_gap: Optional[int]
    next_earliest: Optional[date]
    next_latest: Optional[date]
    filer_note: str = ""          # set when the symbol is unsupported by this method

    @property
    def confident(self) -> bool:
        """Enough history for the cadence to mean anything."""
        return len(self.history) >= 4 and self.median_gap is not None

    def overlaps(self, through: date) -> bool:
        """Could an earnings release land on or before `through`?

        True when the estimated window opens on or before that date. Being
        wrong in this direction costs a skipped trade; the other direction
        costs an earnings gap through an open position.
        """
        return bool(self.next_earliest and self.next_earliest <= through)


def _require_ua():
    if not SEC_USER_AGENT:
        raise RuntimeError(
            "set DELTAX_SEC_UA='Your Name your@email.com' - SEC rejects generic agents")


def cik_for(symbol: str) -> Optional[str]:
    """Ticker -> zero-padded CIK, from SEC's own mapping."""
    _require_ua()
    if not _cik_cache:
        data = json.loads(fetch(TICKER_MAP, user_agent=SEC_USER_AGENT))
        for row in data.values():
            _cik_cache[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    return _cik_cache.get(symbol.upper())


def earnings_history(symbol: str) -> list:
    """Past earnings dates from Item 2.02 filings, newest first."""
    _require_ua()
    cik = cik_for(symbol)
    if not cik:
        return []
    _throttle()
    try:
        xml = fetch(EDGAR_8K.format(cik=cik), user_agent=SEC_USER_AGENT)
    except Exception as e:
        raise SECFetchError(f"{symbol}: 8-K fetch failed - {type(e).__name__}") from e
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        def tag(n):
            m = re.search(rf"<{n}[^>]*>(.*?)</{n}>", entry, re.S)
            return html.unescape(m.group(1)).strip() if m else ""
        if "2.02" in tag("items-desc"):
            try:
                out.append(date.fromisoformat(tag("filing-date")))
            except ValueError:
                pass
    return sorted(set(out), reverse=True)


def recent_forms(symbol: str) -> list:
    """All recent form types - used to classify a symbol that has no 8-Ks."""
    _require_ua()
    cik = cik_for(symbol)
    if not cik:
        return []
    _throttle()
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&CIK={cik}&type=&count=20&output=atom")
    try:
        return re.findall(r"<filing-type>(.*?)</filing-type>",
                          fetch(url, user_agent=SEC_USER_AGENT))
    except Exception:
        return []


def profile(symbol: str) -> EarningsProfile:
    hist = earnings_history(symbol)
    if len(hist) < 2:
        note = ""
        forms = set(recent_forms(symbol))
        if forms & FOREIGN_FORMS:
            note = (f"foreign private issuer (files "
                    f"{'/'.join(sorted(forms & FOREIGN_FORMS))}, not 8-K) - "
                    f"Item 2.02 does not exist for this filer")
        elif not forms:
            note = "no filings retrieved"
        else:
            note = "no Item 2.02 filings found"
        return EarningsProfile(symbol, hist, None, None, None, None, None, note)
    gaps = [(hist[i] - hist[i + 1]).days for i in range(len(hist) - 1)]
    med, lo, hi = int(median(gaps)), min(gaps), max(gaps)
    last = hist[0]
    return EarningsProfile(
        symbol, hist, med, lo, hi,
        next_earliest=last + timedelta(days=lo),
        next_latest=last + timedelta(days=hi),
    )


def blackout(symbol: str, expiry: date,
             profiles: Optional[dict] = None) -> tuple:
    """(blocked, reason) for a single name. ETFs are handled by calendar.py.

    Fail-closed: no usable history means we cannot rule out an event, so we
    block. Absence is not safety.
    """
    p = (profiles or {}).get(symbol) or profile(symbol)
    if not p.confident:
        detail = p.filer_note or "insufficient 8-K history"
        return True, f"{symbol}: {detail} - cannot rule out earnings"
    if p.overlaps(expiry):
        return True, (f"{symbol}: earnings window "
                      f"{p.next_earliest}..{p.next_latest} opens on or before {expiry}")
    return False, (f"{symbol}: next earnings window "
                   f"{p.next_earliest}..{p.next_latest}, clear of {expiry}")
