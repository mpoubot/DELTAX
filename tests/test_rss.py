"""RSS module tests. Parsing is offline; network feeds are checked separately."""
import sys, os
from datetime import timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.rss import parse, FEEDS, active_feeds, poll, poll_sec_8k

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

RSS = """<rss><channel>
<item><title>Headline One</title><link>https://x/1</link>
<pubDate>Sat, 29 Aug 2026 12:00:00 +0000</pubDate>
<category>Energy</category><category>News</category></item>
<item><title><![CDATA[Headline &amp; Two]]></title><link>https://x/2</link>
<pubDate>Sat, 29 Aug 2026 11:00:00 +0000</pubDate></item>
</channel></rss>"""
ATOM = """<feed><entry><title>8-K - Current report</title>
<link href="https://sec.gov/f/1"/><updated>2026-07-06T12:00:00Z</updated></entry></feed>"""

print("\n── parsing ──")
r = parse(RSS, "test")
check("two RSS items", len(r) == 2)
check("title extracted", r[0].title == "Headline One")
check("CDATA and entities unescaped", "&" in r[1].title, r[1].title)
check("link extracted", r[0].link == "https://x/1")
check("pubDate -> tz-aware datetime", r[0].published.tzinfo is not None)
check("categories collected", r[0].categories == ["Energy", "News"], str(r[0].categories))
check("missing categories -> empty", r[1].categories == [])
a = parse(ATOM, "sec")
check("atom entry parsed", len(a) == 1 and a[0].title.startswith("8-K"))
check("atom href link", a[0].link == "https://sec.gov/f/1")
check("atom updated parsed", a[0].published.year == 2026)
check("no body stored (metadata only)", not hasattr(r[0], "description"))

print("\n── registry ──")
check("coindesk registered under crypto", FEEDS["coindesk"][1] == "crypto")
check("oilprice registered under macro", FEEDS["oilprice"][1] == "macro")
check("neither is active yet", not FEEDS["coindesk"][2] and not FEEDS["oilprice"][2])
check("no active crypto feeds", active_feeds("crypto") == [])
check("no active macro feeds", active_feeds("macro") == [])
try:
    poll("nope"); check("unknown feed raises", False)
except KeyError: check("unknown feed raises", True)
if not os.environ.get("DELTAX_SEC_UA"):
    try:
        poll_sec_8k("AVGO"); check("SEC refuses without UA", False)
    except RuntimeError: check("SEC refuses without UA", True)
    check("sec_8k inactive without UA", not FEEDS["sec_8k"][2])


print("\n── freshness guard ──")
from deltax.rss import is_stale, Item, MAX_FEED_AGE_HOURS
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)
fresh   = [Item("a", "u", now - timedelta(hours=2), [], "t")]
old     = [Item("a", "u", now - timedelta(days=580), [], "t")]
undated = [Item("a", "u", None, [], "t")]
check("fresh feed passes", is_stale(fresh)[0] is False)
check("19-month-old feed flagged stale", is_stale(old)[0] is True)
check("age reported in hours", is_stale(old)[1] > 13000, str(is_stale(old)[1]))
check("undated feed treated as stale", is_stale(undated) == (True, None))
check("threshold is 48h", MAX_FEED_AGE_HOURS == 48)
check("wsj registered but inactive", not FEEDS["wsj_markets"][2])

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
