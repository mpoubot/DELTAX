"""Reconciliation. Without it the risk cap means nothing across cycles."""
import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.reconcile import parse_occ, reconcile, safe_to_open, pending
from deltax.run import run

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

print("\n── OCC symbol parsing ──")
o = parse_occ("SPY260911P00750000")
check("underlying", o and o["underlying"] == "SPY")
check("right", o and o["right"] == "put")
check("strike", o and o["strike"] == 750.0)
check("call parses", parse_occ("QQQ260911C00736000")["right"] == "call")
check("multi-char root", parse_occ("AAPL260911P00230000")["underlying"] == "AAPL")
for bad in ("", "JUNK", "SPY", "SPY260911X00750000", "SPYAAAAAAP00750000"):
    check(f"refuses {bad or '(empty)'!r}", parse_occ(bad) is None)

print("\n── reconciling a live book ──")
r = reconcile([{"symbol":"SPY260911P00750000","qty":"-5","avg_entry_price":"1.15","cost_basis":"-575"},
               {"symbol":"SPY260911P00745000","qty":"5","avg_entry_price":"0.60","cost_basis":"300"},
               {"symbol":"QQQ260911C00736000","qty":"-5","avg_entry_price":"1.00","cost_basis":"-500"}])
check("held pairs found", r["held"] == {("SPY","put"),("QQQ","call")}, str(r["held"]))
# E79: this previously asserted committed == 1075.0 - the sum of the SHORT legs'
# premium. That is the bug, written down as an expectation, which is why every
# earlier audit passed over it. Committed risk is TRUE max loss:
#   SPY 750/745, 5x, credit 1.15-0.60=0.55 -> (5-0.55)*100*5 = 2,225
#   QQQ 736 call, 5x, NAKED (no long leg)  -> 736*100*5      = 368,000
_expect = (5 - 0.55) * 100 * 5 + 736 * 100 * 5
check("committed is TRUE max loss, not premium received",
      abs(r["committed"] - _expect) < 1.0, f"{r['committed']} vs {_expect}")
check("a naked short dominates the number, as it should",
      r["committed"] > 300_000, str(r["committed"]))
check("counts every position", r["count"] == 3)
check("empty book is safe", safe_to_open(reconcile([]))[0])

print("\n── fail closed on an illegible book ──")
bad = reconcile([{"symbol":"NOTANOPTION","qty":"1","cost_basis":"1"}])
check("unparseable symbol is reported", bad["unparsed"] == ["NOTANOPTION"])
check("and blocks new risk", not safe_to_open(bad)[0])
check("reason is stated", "could not be parsed" in safe_to_open(bad)[1])
check("bad qty is reported not ignored",
      reconcile([{"symbol":"SPY260911P00750000","qty":"abc","cost_basis":"1"}])["unparsed"])

print("\n── THE BUG: a second cycle must not re-open the same book ──")
class Feed:
    def __init__(self, pos): self.pos = pos
    def clock(self): return {"is_open": True}
    def snapshots(self, syms):
        return {s: {"latestTrade":{"p":100.0},"dailyBar":{"c":100.0,"o":99.0,"t":"2026-08-31T20:00:00Z"},
                    "prevDailyBar":{"c":99.0}} for s in syms}
    def positions(self): return self.pos
    def open_orders(self): return []
    def option_contracts(self, *a, **k): return []
    def chain(self, *a, **k): return {}
class L:
    def __init__(self): self.rows=[]
    def record_raw(self, d): self.rows.append(d)
    def record(self, *a, **k): return {"result":"ok"}

led = L()
out = run(Feed([{"symbol":"SPY260911P00750000","qty":"-5","cost_basis":"-1925"}]),
          led, equity=100_000.0, today=date.today(), dry_run=True, force_window=True)
check("committed is seeded from the live book, not 0",
      out["committed"] >= 1925.0, str(out["committed"]))
rec = [r for r in led.rows if r.get("action") == "reconcile"]
check("reconciliation is logged", len(rec) == 1)
check("held legs recorded", rec and rec[0]["held"] == ["SPY/put"], str(rec[0]["held"] if rec else None))

led2 = L()
out2 = run(Feed([{"symbol":"BROKEN","qty":"1","cost_basis":"1"}]),
           led2, equity=100_000.0, today=date.today(), dry_run=True, force_window=True)
check("illegible book refuses to trade", out2.get("skipped") is not None, str(out2.get("skipped")))
check("and opens nothing", out2["traded"] == [])

print("\n── THE 31 AUG BUG: a working order is still risk (E36) ──")
OPEN = [{"legs": [{"symbol": "UNH260918P00380000", "position_intent": "sell_to_open"},
                  {"symbol": "UNH260918P00370000", "position_intent": "buy_to_open"}]}]
r = reconcile([], OPEN)
check("a working order with NO position is seen", ("UNH", "put") in r["held"])
check("so a second identical order is blocked", ("UNH", "put") in r["held"])
check("it is counted", r.get("pending_orders") == 1)

EXIT = [{"legs": [{"symbol": "UNH260918P00380000", "position_intent": "buy_to_close"},
                  {"symbol": "UNH260918P00370000", "position_intent": "sell_to_close"}]}]
check("a resting EXIT blocks nothing — it is how a position closes",
      reconcile([], EXIT)["held"] == set())

check("positions and orders combine, not replace",
      reconcile([{"symbol": "SPY260911P00750000", "qty": "-1", "cost_basis": "-100"}],
                OPEN)["held"] == {("SPY", "put"), ("UNH", "put")})
check("no orders behaves exactly as before", reconcile([], [])["held"] == set())
check("an unparseable working order still fails closed",
      reconcile([], [{"legs": [{"symbol": "GARBAGE", "position_intent": "sell_to_open"}]}])["unparsed"])
check("a legless order falls back to its own symbol",
      ("UNH", "call") in pending([{"symbol": "UNH260918C00400000"}])["held"])

print("\n── E72: equity positions must not disable the options engine ──")
MIXED = [
  {"symbol":"IWM260918P00288000","qty":"-10","cost_basis":"-2460","asset_class":"us_option"},
  {"symbol":"IWM260918P00283000","qty":"10","cost_basis":"1500","asset_class":"us_option"},
  {"symbol":"XOP","qty":"51","cost_basis":"9844","asset_class":"us_equity"},
  {"symbol":"IGV","qty":"96","cost_basis":"9985","asset_class":"us_equity"},
]
b = reconcile(MIXED, [])
check("equity tickers are recognised, not 'unparseable'",
      sorted(b["equities"]) == ["IGV","XOP"], str(b["equities"]))
check("no false anomalies from equity", b["unparsed"] == [], str(b["unparsed"]))
check("option pairs still detected", ("IWM","put") in b["held"], str(b["held"]))
ok, why = safe_to_open(b)
check("a mixed book does NOT block new options risk", ok, why)
check("equity cost basis counts toward committed risk",
      b["committed"] >= 9844 + 9985, str(b["committed"]))
# a genuine anomaly must STILL block - the fix must not blanket-allow
BAD = MIXED + [{"symbol":"QQQ260908P0068000X","qty":"1","cost_basis":"10"}]
b2 = reconcile(BAD, [])
check("a malformed OCC symbol is still an anomaly", len(b2["unparsed"]) == 1, str(b2["unparsed"]))
check("and it still blocks new risk", not safe_to_open(b2)[0])
check("equity detection needs the ticker shape, not just any string",
      "QQQ260908P0068000X" not in b2["equities"], str(b2["equities"]))



print("\n── E75: a dead feed must fail closed, never crash the cycle ──")
class _Dead:
    """Every endpoint times out - the 2 Sep TLS handshake failure."""
    def clock(self): raise RuntimeError("TLS handshake timeout")
    def snapshots(self, s): raise RuntimeError("TLS handshake timeout")
    def positions(self): raise RuntimeError("TLS handshake timeout")
    def open_orders(self): raise RuntimeError("TLS handshake timeout")
    def account(self): raise RuntimeError("TLS handshake timeout")
class _Flaky(_Dead):
    def clock(self): return {"is_open": True}

_l = L()
try:
    o = run(_Dead(), _l, equity=100_000.0, today=date.today(), dry_run=True)
    check("a dead clock SKIPS instead of raising", o.get("skipped") is not None, str(o)[:60])
    check("it opens nothing", o["traded"] == [])
    check("and says the clock was unreadable",
          "clock unreadable" in str(o.get("skipped")), str(o.get("skipped")))
    check("the failure is LOGGED, not silent",
          any(r.get("action") == "clock_unreadable" for r in _l.rows),
          str([r.get("action") for r in _l.rows]))
except Exception as e:
    check("a dead clock SKIPS instead of raising", False, f"{type(e).__name__}: {e}")

_l2 = L()
try:
    o2 = run(_Flaky(), _l2, equity=100_000.0, today=date.today(),
             dry_run=True, force_window=True)
    check("dead benchmarks SKIP instead of raising", o2.get("skipped") is not None)
    check("benchmark failure is logged",
          any(r.get("action") == "benchmarks_unreadable" for r in _l2.rows))
except Exception as e:
    check("dead benchmarks SKIP instead of raising", False, f"{type(e).__name__}: {e}")

_r = open("deltax/run.py").read()
check("E75 guards the SECOND clock read in the skip report",
      "_mkt = bool(feed.clock()" in _r and "_mkt = False" in _r)
check("E75 guards the per-symbol snapshot inside the scan loop",
      "snapshot_failed" in _r)


print("\n── E76: transient faults are RETRIED, real errors are not ──")
from deltax.feeds import AlpacaFeed, FeedError
import deltax.feeds as _F

class _R:
    def __init__(self, rc, out="", err=""): self.returncode=rc; self.stdout=out; self.stderr=err
_calls = {"n": 0}
def _seq(items):
    _calls["n"] = 0
    def fake(cmd, **k):
        i = _calls["n"]; _calls["n"] += 1
        return items[min(i, len(items) - 1)]
    return fake

_orig_run = _F.subprocess.run
_f = AlpacaFeed(); _f.BACKOFF = 0.001
try:
    _F.subprocess.run = _seq([_R(1, err="TLS handshake timeout"), _R(0, '{"is_open":true}')])
    check("a TLS timeout is retried and recovers", _f._run(["clock"]) == {"is_open": True})
    check("it took exactly 2 attempts", _calls["n"] == 2, str(_calls["n"]))

    _F.subprocess.run = _seq([_R(1, err="TLS handshake timeout")])
    try:
        _f._run(["clock"]); check("persistent transient failure raises", False)
    except FeedError:
        check("persistent transient failure raises", True)
    check("and stops at RETRIES, no infinite loop", _calls["n"] == _f.RETRIES, str(_calls["n"]))

    _F.subprocess.run = _seq([_R(1, err="unauthorized: invalid API key")])
    try:
        _f._run(["account"]); check("an auth error is NOT retried", False)
    except FeedError:
        check("an auth error is NOT retried", _calls["n"] == 1, str(_calls["n"]))

    _F.subprocess.run = _seq([_R(0, '{"error":"symbol not found"}')])
    try:
        _f._run(["bars"]); check("a bad symbol is NOT retried", False)
    except FeedError:
        check("a bad symbol is NOT retried", _calls["n"] == 1, str(_calls["n"]))

    _F.subprocess.run = _seq([_R(0, '{"trunc'), _R(0, '{"ok":1}')])
    check("truncated JSON is retried", _f._run(["clock"]) == {"ok": 1})

    check("transient list covers the observed fault",
          AlpacaFeed._is_transient("net/http: TLS handshake timeout"))
    check("and does not over-match real errors",
          not AlpacaFeed._is_transient("unauthorized"))
    check("worst-case backoff stays inside a 5-minute cycle",
          sum(_f.BACKOFF * (2 ** i) for i in range(_f.RETRIES)) < 300)
finally:
    _F.subprocess.run = _orig_run


print("\n── E79: committed risk must equal TRUE max loss ──")
# The live 2 Sep book. Ground truth computed by hand from the broker:
#   IWM 10x 5-wide  credit 0.96 -> (5-0.96)*100*10  = 4,040
#   QQQ  1x 20-wide credit 2.15 -> (20-2.15)*100*1  = 1,785
#   SMH  1x 20-wide credit 3.43 -> (20-3.43)*100*1  = 1,657   (calls)
#   SMH  5x 10-wide credit 2.30 -> (10-2.30)*100*5  = 3,850   (puts)
#   SPY  1x 20-wide credit 1.74 -> (20-1.74)*100*1  = 1,826
LIVE = [
 {"symbol":"IWM260918P00288000","qty":"-10","avg_entry_price":"2.46","cost_basis":"-2460"},
 {"symbol":"IWM260918P00283000","qty":"10","avg_entry_price":"1.50","cost_basis":"1500"},
 {"symbol":"QQQ260908P00700000","qty":"-1","avg_entry_price":"2.69","cost_basis":"-269"},
 {"symbol":"QQQ260908P00680000","qty":"1","avg_entry_price":"0.54","cost_basis":"54"},
 {"symbol":"SMH260911C00565000","qty":"-1","avg_entry_price":"4.65","cost_basis":"-465"},
 {"symbol":"SMH260911C00585000","qty":"1","avg_entry_price":"1.22","cost_basis":"122"},
 {"symbol":"SMH260918P00540000","qty":"-5","avg_entry_price":"9.00","cost_basis":"-4500"},
 {"symbol":"SMH260918P00530000","qty":"5","avg_entry_price":"6.70","cost_basis":"3350"},
 {"symbol":"SPY260908P00760000","qty":"-1","avg_entry_price":"1.98","cost_basis":"-198"},
 {"symbol":"SPY260908P00740000","qty":"1","avg_entry_price":"0.24","cost_basis":"24"},
]
TRUE_OPT = 4040 + 1785 + 1657 + 3850 + 1826
b = reconcile(LIVE, [])
check("committed equals TRUE max loss, to the dollar",
      abs(b["committed"] - TRUE_OPT) < 1.0, f"{b['committed']} vs {TRUE_OPT}")
check("it is NOT the premium received (the old bug)",
      abs(b["committed"] - (2460 + 269 + 465 + 4500 + 198)) > 1000, str(b["committed"]))

# a naked short must be charged its FULL notional, not a credit
NAKED = [{"symbol":"SPY260918P00700000","qty":"-1","avg_entry_price":"3.00","cost_basis":"-300"}]
n = reconcile(NAKED, [])
check("a naked short is charged full notional", n["committed"] == 700 * 100, str(n["committed"]))

# a partially covered short: 5 short, 2 long -> 2 spreads + 3 naked
PART = [{"symbol":"SPY260918P00700000","qty":"-5","avg_entry_price":"3.00","cost_basis":"-1500"},
        {"symbol":"SPY260918P00680000","qty":"2","avg_entry_price":"1.00","cost_basis":"200"}]
pt = reconcile(PART, [])
expect = (20 - 2.0) * 100 * 2 + 700 * 100 * 3
check("partial cover charges the uncovered legs as naked",
      abs(pt["committed"] - expect) < 1.0, f"{pt['committed']} vs {expect}")

# a LONG-only holding carries no short risk
LONG = [{"symbol":"SPY260918P00700000","qty":"3","avg_entry_price":"2.00","cost_basis":"600"}]
check("long-only carries no committed risk", reconcile(LONG, [])["committed"] == 0.0)

# equity still counts toward the budget
EQ = LIVE + [{"symbol":"XOP","qty":"51","cost_basis":"9844","asset_class":"us_equity"}]
check("equity cost basis is still included",
      abs(reconcile(EQ, [])["committed"] - (TRUE_OPT + 9844)) < 1.0)

print("\n── E78: the sweep must not report closes it never made ──")
from deltax.manage import manage as _manage, Managed as _M
hit = [_M(symbol="X260918P00100000", qty=1, entry_credit=2.00, current=0.50, dte=9)]
out = _manage(hit, dry_run=False, closer=None)
check("with no closer wired, nothing is reported as closed", out["closed"] == [], str(out["closed"]))
check("and the failure is surfaced", out["failed"] and out["failed"][0][1] == "no closer wired",
      str(out.get("failed")))
calls = []
out2 = _manage(hit, dry_run=False, closer=lambda s, q: calls.append((s, q)) or {"result": "SUBMITTED"})
check("with a closer wired, an order IS submitted", calls == [("X260918P00100000", 1)], str(calls))
check("and only then is it reported closed", len(out2["closed"]) == 1)
def _boom(s, q): raise RuntimeError("broker rejected")
out3 = _manage(hit, dry_run=False, closer=_boom)
check("a failed close is NOT reported as closed", out3["closed"] == [] and out3["failed"])

print("\n-- E85: an unreadable equity holding must widen the refusal --")
# `pass` on a bad cost_basis counted the holding as ZERO committed risk, so the
# portfolio cap silently understated the book - the E79 shape again. The
# options path already routed such a position to `unparsed`; made consistent.
# Reachable in normal operation: an assigned short option becomes stock with no
# order placed, so the E82 rule-3 guard never sees it.
_bad = reconcile([{"symbol": "SPY", "asset_class": "us_equity",
                   "qty": "100", "cost_basis": "not-a-number"}])
check("E85 unreadable equity cost basis lands in unparsed",
      "SPY" in _bad["unparsed"], str(_bad))
check("E85 it does NOT silently count as zero risk",
      _bad["committed"] == 0.0 and _bad["unparsed"] != [])
_ok2, _why2 = safe_to_open(_bad)
check("E85 and the book therefore fails closed", _ok2 is False, _why2)
_good = reconcile([{"symbol": "SPY", "asset_class": "us_equity",
                    "qty": "100", "cost_basis": "76000"}])
check("E85 a readable equity still counts its basis",
      _good["committed"] == 76000.0 and not _good["unparsed"], str(_good))

print(f"\n{chr(61)*52}\n  {passed} passed, {failed} failed\n{chr(61)*52}")
sys.exit(1 if failed else 0)
