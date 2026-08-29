"""Generic RSS ingestion.

Stores metadata only - title, link, timestamp, categories. Never article
bodies: they are licensed third-party content, the agent does not need them,
and DATA-FEEDS.md commits us to keeping them out of the repo.

Feeds are registered per bucket. A feed that cannot inform a gate the agent
actually runs is registered but inactive, so the wiring exists without
pretending it affects decisions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
import html
import re
import os
import urllib.request

USER_AGENT = "DELTAX/0.1 (hackathon research; contact via repo)"

# SEC rejects generic agents with 403. Their policy requires a real name and
# contact email, e.g. "DELTAX Research ops@yourdomain.com". Set it in the
# environment - never hardcode a personal address into the repo.
SEC_USER_AGENT = os.environ.get("DELTAX_SEC_UA")


@dataclass
class Item:
    title: str
    link: str
    published: Optional[datetime]
    categories: list
    source: str


# feed key -> (url, bucket, active)
# 'active' means: can this feed inform a gate the agent currently runs?
FEEDS = {
    "coindesk": (
        "https://www.coindesk.com/arc/outboundfeeds/rss",
        "crypto",
        False,   # crypto engine not built yet - activate with that bucket
    ),
    "oilprice": (
        "https://oilprice.com/rss/main",
        "macro",
        False,   # energy/macro context; informs no gate the agent currently runs
    ),
    # From the team's n8n "Market Notes to Telegram" workflow. Registered so the
    # source is tracked - but see is_stale(): as of 2026-08-29 its newest item
    # was from 2025-01-27, i.e. the feed is dead and was silently serving
    # 19-month-old headlines into that workflow.
    "wsj_markets": (
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "equities",
        False,
    ),
    # 8-K Item 2.02 is where earnings releases are filed - the authoritative
    # source for the earnings gate. Needs DELTAX_SEC_UA set; inactive without it.
    "sec_8k": (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        "?action=getcompany&CIK={cik}&type=8-K&count=20&output=atom",
        "equities",
        bool(SEC_USER_AGENT),
    ),
}

# CIKs for the satellite universe, for the 8-K lookup.
CIK = {"AVGO": "0001730168"}


def fetch(url: str, timeout: int = 20, user_agent: Optional[str] = None) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent or USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def _tag(block: str, name: str) -> str:
    m = re.search(
        rf"<{name}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{name}>", block, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def _when(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None


def parse(xml: str, source: str) -> list:
    """RSS <item> or Atom <entry>. Metadata only."""
    blocks = re.findall(r"<item>(.*?)</item>", xml, re.S) or \
             re.findall(r"<entry>(.*?)</entry>", xml, re.S)
    out = []
    for b in blocks:
        link = _tag(b, "link")
        if not link:
            m = re.search(r'<link[^>]*href="([^"]+)"', b)
            link = m.group(1) if m else ""
        out.append(Item(
            title=_tag(b, "title"),
            link=link,
            published=_when(_tag(b, "pubDate") or _tag(b, "updated")),
            categories=re.findall(r"<category[^>]*>(?:<!\[CDATA\[)?([^<\]]+)", b),
            source=source,
        ))
    return out


def poll(key: str) -> list:
    if key not in FEEDS:
        raise KeyError(f"unknown feed {key!r}; known: {sorted(FEEDS)}")
    url, _bucket, active = FEEDS[key]
    if key.startswith("sec") and not SEC_USER_AGENT:
        raise RuntimeError(
            "SEC feeds require DELTAX_SEC_UA, e.g. "
            "export DELTAX_SEC_UA='DELTAX Research ops@yourdomain.com'")
    if "{cik}" in url:
        raise ValueError(f"{key} needs a CIK; use poll_sec_8k(symbol)")
    return parse(fetch(url, user_agent=SEC_USER_AGENT if key.startswith("sec") else None), key)


def poll_sec_8k(symbol: str) -> list:
    """Recent 8-K filings for one symbol. Item 2.02 filings are earnings releases."""
    if not SEC_USER_AGENT:
        raise RuntimeError(
            "set DELTAX_SEC_UA='Your Name your@email' - SEC rejects generic agents")
    cik = CIK.get(symbol)
    if not cik:
        raise KeyError(f"no CIK registered for {symbol}; add it to rss.CIK")
    url = FEEDS["sec_8k"][0].format(cik=cik)
    return parse(fetch(url, user_agent=SEC_USER_AGENT), "sec_8k")


MAX_FEED_AGE_HOURS = 48


def is_stale(items: list, max_age_hours: int = MAX_FEED_AGE_HOURS) -> tuple:
    """(stale, age_hours). A feed that parses is not a feed that is alive.

    Dead feeds fail silently - they keep returning well-formed, months-old
    items. Any feed must pass this before it can inform a decision.
    """
    dated = [i.published for i in items if i.published]
    if not dated:
        return True, None
    newest = max(dated)
    age = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    return age > max_age_hours, round(age, 1)


def active_feeds(bucket: str) -> list:
    return [k for k, (_u, b, a) in FEEDS.items() if b == bucket and a]
