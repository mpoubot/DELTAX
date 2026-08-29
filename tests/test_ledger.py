"""Unit tests for the decision ledger. No network, deterministic clock."""

import sys, os, json, tempfile, shutil
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from deltax.gates import evaluate, PER_POSITION_RISK_PCT
from deltax.ledger import Ledger, GENESIS_HASH

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  ✓ {name}")
    else: failed += 1; print(f"  ✗ {name}  {detail}")

EQUITY = 100_000.0
TODAY = date(2026, 8, 31)

def make_decision(symbol="SPY", oi=12_000, expiry=date(2026, 9, 14)):
    return evaluate(
        symbol=symbol, equity=EQUITY,
        max_loss_per_contract=100.0, max_profit_per_contract=250.0,
        credit=1.20, expiry=expiry, today=TODAY,
        open_interest=oi, open_portfolio_max_loss=0.0,
    )

tmp = tempfile.mkdtemp()
try:
    # deterministic clock: two UTC days to test file rotation
    stamps = iter([
        "2026-08-31T14:30:00.000+00:00",
        "2026-08-31T14:35:00.000+00:00",
        "2026-08-31T14:40:00.000+00:00",
        "2026-09-01T14:30:00.000+00:00",
    ])
    led = Ledger(tmp, run_id="testrun", clock=lambda: next(stamps), rules_commit="abc123")

    print("\n── recording ──")
    e1 = led.record(make_decision("SPY"), context={"underlying_price": 645.10})
    e2 = led.record(make_decision("SPCX", oi=6, expiry=date(2026, 9, 4)))
    e3 = led.record(make_decision("QQQ"))
    e4 = led.record(make_decision("IWM"))

    check("seq increments from 0", [e["seq"] for e in (e1,e2,e3,e4)] == [0,1,2,3])
    check("genesis prev_hash", e1["prev_hash"] == GENESIS_HASH)
    check("chain links", e2["prev_hash"] == e1["hash"] and e3["prev_hash"] == e2["hash"])
    check("rules_commit stamped", e1["rules_commit"] == "abc123")
    check("run_id stamped", e1["run_id"] == "testrun")
    check("context stored", e1["context"]["underlying_price"] == 645.10)
    check("SPY is TRADE", e1["decision"] == "TRADE")
    check("SPCX is REFUSE with failed gate", e2["decision"] == "REFUSE" and e2["failed_gate"] == "dte")
    check("full gate detail present", len(e1["gates"]) >= 9 and all("observed" in g for g in e1["gates"]))

    print("\n── file rotation by UTC day ──")
    files = sorted(os.path.basename(p) for p in os.listdir(tmp))
    check("two day files", files == ["decisions-2026-08-31.jsonl", "decisions-2026-09-01.jsonl"], str(files))
    day1_lines = open(os.path.join(tmp, files[0])).read().splitlines()
    check("day 1 holds three records", len(day1_lines) == 3)

    print("\n── integrity ──")
    ok, msg = led.verify()
    check("chain verifies", ok, msg)

    # tamper: change one value in the middle record
    p = os.path.join(tmp, files[0])
    lines = open(p).read().splitlines()
    rec = json.loads(lines[1]); rec["max_loss"] = 1.0
    lines[1] = json.dumps(rec, default=str)
    open(p, "w").write("\n".join(lines) + "\n")
    ok2, msg2 = Ledger(tmp, clock=lambda: "2026-09-01T15:00:00.000+00:00").verify()
    check("tampering detected", not ok2, msg2)
    # restore
    rec["max_loss"] = 0.0
    # (recompute is unnecessary — rewrite original line)
    lines[1] = day1_lines[1]
    open(p, "w").write("\n".join(lines) + "\n")
    ok3, _ = Ledger(tmp, clock=lambda: "x").verify()
    check("restored chain verifies", ok3)

    print("\n── resume across restarts ──")
    led2 = Ledger(tmp, run_id="run2",
                  clock=lambda: "2026-09-01T15:05:00.000+00:00", rules_commit="abc124")
    e5 = led2.record(make_decision("DIA"))
    check("seq continues (4)", e5["seq"] == 4, str(e5["seq"]))
    check("chain continues across restart", e5["prev_hash"] == e4["hash"])
    ok4, msg4 = led2.verify()
    check("whole chain still verifies", ok4, msg4)

    print("\n── summary ──")
    s = led2.summary()
    check("evaluated 5", s["evaluated"] == 5, str(s))
    check("4 trades, 1 refusal", s["trades"] == 4 and s["refusals"] == 1)
    check("refusal attributed to dte", s["refusals_by_first_failed_gate"] == {"dte": 1})
    check("liquidity failure also counted", s["gate_failure_counts"].get("liquidity") == 1)
    per_pos = float(int((EQUITY * PER_POSITION_RISK_PCT) // 100) * 100)
    check("committed max loss = 4 × per-position budget", s["committed_max_loss"] == 4 * per_pos, str(s["committed_max_loss"]))
    check("both runs listed", s["runs"] == ["run2", "testrun"])
finally:
    shutil.rmtree(tmp)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
