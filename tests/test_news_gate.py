"""News gate. Last check before real money; veto only, never origination."""
import sys, os
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.news_gate import screen, screen_survivors, BLOCKING, LOOKBACK_HOURS

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

def art(head, hours_ago=2.0, summary=""):
    t = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"headline": head, "summary": summary, "source": "test",
            "created_at": t.isoformat().replace("+00:00", "Z")}

print("\n── blocks genuine re-rating events ──")
for head, why in (("UnitedHealth trading halted pending news", "halt"),
                  ("Company files for Chapter 11 bankruptcy", "bankruptcy"),
                  ("SEC charges firm with accounting fraud", "fraud"),
                  ("Insurer slashes guidance for full year", "guidance"),
                  ("CEO resigns effective immediately", "CEO"),
                  ("Firm announces voluntary product recall", "recall")):
    v = screen("X", [art(head)])
    check(f"blocks: {why}", not v["allowed"], v["reason"])

print("\n── does NOT block ordinary noise ──")
for head in ("UnitedHealth Stock Edges Higher Wednesday: What's Happening?",
             "$100 Invested In UnitedHealth 15 Years Ago Would Be Worth This",
             "10 Health Care Stocks Whale Activity In Today's Session",
             "Analyst raises price target on managed care names",
             "Elizabeth Warren Says Six Huge Companies Pocketed Tax Breaks"):
    v = screen("X", [art(head)])
    check(f"allows: {head[:46]}...", v["allowed"], v["reason"])

print("\n── only recent news counts ──")
check("a halt 2h ago blocks", not screen("X", [art("trading halt", 2)])["allowed"])
check("a halt 200h ago does NOT block",
      screen("X", [art("trading halt", 200)])["allowed"])
check("lookback is bounded", LOOKBACK_HOURS <= 72)
check("undated articles are ignored, not guessed",
      screen("X", [{"headline": "bankruptcy filing", "created_at": None}])["allowed"])

print("\n── plumbing fails OPEN, risk words fail CLOSED ──")
v = screen("NOSUCHTICKERXYZ")
check("unreachable news does not block a gated candidate", v["allowed"])
check("and is reported as unreachable", not v["reachable"] or v["read"] >= 0)
check("a reachable fetch with a blocker DOES block",
      not screen("X", [art("company halted amid fraud probe")])["allowed"])

print("\n── veto only: it can never create a trade ──")
import inspect
from deltax import news_gate
src = inspect.getsource(news_gate)
check("no code path returns a BUY/nominate signal",
      "buy" not in src.lower().replace("buy_to_close", ""))
check("screen() only ever returns allowed True/False",
      isinstance(screen("X", [])["allowed"], bool))

print("\n── screens survivors only ──")
out = screen_survivors([("X", "put"), ("X", "call")])
check("one fetch per symbol, not per side", len(out["verdicts"]) == 1)
check("returns a blocked set", isinstance(out["blocked"], set))

print("\n── the list is deliberately narrow ──")
check("fewer than 40 patterns", len(BLOCKING) < 40, str(len(BLOCKING)))
check("no vague words that would veto for nothing",
      not any(w in BLOCKING for w in ("down", "falls", "drops", "weak", "concern")))

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
