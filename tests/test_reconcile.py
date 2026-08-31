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
r = reconcile([{"symbol":"SPY260911P00750000","qty":"-5","cost_basis":"-575"},
               {"symbol":"SPY260911P00745000","qty":"5","cost_basis":"300"},
               {"symbol":"QQQ260911C00736000","qty":"-5","cost_basis":"-500"}])
check("held pairs found", r["held"] == {("SPY","put"),("QQQ","call")}, str(r["held"]))
check("committed counts short legs only", r["committed"] == 1075.0, str(r["committed"]))
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

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
