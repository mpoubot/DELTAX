"""Final check on the SURVIVORS, immediately before an order is sent.

Position in the pipeline matters. This is the LAST gate, not another screen:
it runs after the 13 deterministic gates have already reduced a universe to a
handful of candidates, so it makes a few API calls instead of hundreds, and it
looks at exactly the names about to receive real money.

WHY THE EXISTING FEEDS COULD NOT DO THIS. On 31 Aug the broad-market feeds
carried 216 live articles and **zero** mentioned UNH - a name we were about to
trade. CNBC, FT and Yahoo markets cover the market, not the ticker. Alpaca's
per-symbol news endpoint returns 20 UNH-specific items for the same query, so
that is what a single-name veto has to read.

VETO ONLY, never origination. News can refuse a trade the gates approved; it
can never create one. That is the corpus rule and it is also what makes the
pipeline injection-resistant: a headline cannot talk the agent INTO anything.

FAIL-CLOSED on the risk words, OPEN on the plumbing. If the endpoint errors we
do NOT block - the 13 gates already approved this candidate on price and
structure, and letting a news outage halt trading hands an availability problem
veto power over a validated decision. But a fetch that SUCCEEDS and returns a
blocking headline stops the order.
"""
from __future__ import annotations
import json, os, subprocess
from datetime import datetime, timezone
from typing import Optional

LOOKBACK_HOURS = 48.0
MAX_ARTICLES = 30

# Events that genuinely re-rate a stock overnight. Deliberately narrow: this
# list vetoes real money, so a vague word costs us trades for nothing.
BLOCKING = {
    "halted": "trading halt",
    "trading halt": "trading halt",
    "bankruptcy": "bankruptcy",
    "chapter 11": "bankruptcy",
    "delisting": "delisting",
    "fraud": "fraud allegation",
    "accounting irregular": "accounting irregularity",
    "restat": "restatement",
    "sec charges": "SEC enforcement",
    "sec investigation": "SEC investigation",
    "doj investigation": "DOJ investigation",
    "criminal probe": "criminal probe",
    "guidance cut": "guidance cut",
    "slashes guidance": "guidance cut",
    "withdraws guidance": "guidance withdrawn",
    "profit warning": "profit warning",
    "ceo resigns": "CEO departure",
    "ceo steps down": "CEO departure",
    "cfo resigns": "CFO departure",
    "acquisition of": "M&A event",
    "to be acquired": "M&A event",
    "takeover bid": "M&A event",
    "merger agreement": "M&A event",
    "recall": "product recall",
    "clinical hold": "clinical hold",
}


def fetch(symbol: str, limit: int = MAX_ARTICLES) -> list:
    """Per-symbol news. Raises on failure so the caller can distinguish
    'nothing found' from 'could not look' (E28)."""
    out = subprocess.run(
        ["alpaca", "data", "news", "--symbols", symbol,
         "--limit", str(limit), "--quiet"],
        capture_output=True, text=True, timeout=25, env=os.environ)
    if out.returncode:
        raise RuntimeError(f"news fetch failed: {out.stderr.strip()[:120]}")
    d = json.loads(out.stdout)
    return (d.get("news") if isinstance(d, dict) else d) or []


def _age_hours(article: dict) -> Optional[float]:
    for k in ("created_at", "updated_at"):
        v = article.get(k)
        if not v:
            continue
        try:
            t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0
        except (TypeError, ValueError):
            continue
    return None


def screen(symbol: str, articles: Optional[list] = None) -> dict:
    """Read the tape for one name. Returns a decision, never raises."""
    try:
        arts = articles if articles is not None else fetch(symbol)
        reachable = True
    except Exception as exc:
        return {"symbol": symbol, "allowed": True, "reachable": False,
                "read": 0, "recent": 0, "reason": f"news unreachable ({type(exc).__name__}) "
                                                  f"- gates already approved, not blocking",
                "hits": []}

    recent, hits = 0, []
    for a in arts:
        age = _age_hours(a)
        if age is None or age > LOOKBACK_HOURS:
            continue
        recent += 1
        head = f"{a.get('headline','')} {a.get('summary','')}".lower()
        for needle, label in BLOCKING.items():
            if needle in head:
                hits.append({"label": label, "age_hours": round(age, 1),
                             "headline": (a.get("headline") or "")[:120],
                             "source": a.get("source", "?")})
                break

    return {"symbol": symbol, "allowed": not hits, "reachable": reachable,
            "read": len(arts), "recent": recent, "hits": hits,
            "reason": (f"{hits[0]['label']} — \"{hits[0]['headline']}\"" if hits
                       else f"{recent} article(s) in {LOOKBACK_HOURS:.0f}h, nothing blocking")}


def screen_survivors(candidates: list, *, ledger=None) -> dict:
    """Screen ONLY what the gates approved. candidates: [(symbol, side), ...]"""
    verdicts, blocked = {}, []
    for sym in sorted({s for s, _ in candidates}):
        v = screen(sym)
        verdicts[sym] = v
        if not v["allowed"]:
            blocked.append(sym)
        if ledger is not None:
            ledger.record_raw({"action": "news_gate", "symbol": sym,
                               "allowed": v["allowed"], "read": v["read"],
                               "recent": v["recent"], "reachable": v["reachable"],
                               "reason": v["reason"]})
    return {"verdicts": verdicts, "blocked": set(blocked)}
