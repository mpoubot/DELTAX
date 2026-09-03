#!/bin/bash
# ╔════════════════════════════════════════════════════════════════════════╗
# ║  RETIRED 2026-09-03 09:50 ET — DO NOT RUN. THIS SCRIPT MADE THINGS WORSE ║
# ╚════════════════════════════════════════════════════════════════════════╝
#
# What it was supposed to do: close the SMH book at 09:31 Thu.
# What it actually did at 09:31:
#   1. Cancelled the two resting GTC exits on SMH.           <- REAL
#   2. Ran `alpaca position close --symbol <option>` x4.     <- NO-OP
#      Each returned `{"code": 0}` - the CLI's own success envelope, which
#      `| head -2` truncated before any error body - and created NO broker
#      order. Confirmed: zero SMH orders existed at the broker afterwards.
#   3. Reported "SMH legs remaining: 4" and exited 0.
#
# Net effect: SMH went from "covered by resting exits" to "no exit at all",
# while the log read as a success. The 540 put bled to -$1,450 before it was
# caught. It was closed manually at 09:44 through execute.submit(close=True),
# which builds a real multi-leg order with buy_to_close/sell_to_close intents -
# the SAME path the exit sweep and the Friday flatten use. That is the only
# correct way to close a spread in this system, and it is the way this script
# should have been written.
#
# Two lessons, both already in the E-series:
#   - `code 0` from a CLI is not a fill. Success is a filled order at the
#     broker, checked from the broker (E78: "a sweep that reports an action it
#     did not take is worse than no sweep").
#   - Never cancel a protective order before its replacement is CONFIRMED
#     working. The cancel should have come after the close filled, not before
#     it was attempted.
#
# The cron entry was one-shot (31 9 3 9 *) and has fired; it cannot run again
# this year. The body below is preserved unchanged as the record of what ran,
# and disabled by the exit on the next line.
exit 3   # RETIRED - see header
#
# ── original body, preserved for the record ──────────────────────────────
# E101 — close the SMH book at Thursday's open, on the operator's instruction.
#
# WHY: SMH measured IV/RV 0.91 on 2 Sep. Selling a credit spread is selling
# volatility, so a ratio below 1 means we are selling movement for less than the
# underlying delivers - negative expectancy that no strike choice repairs. It
# had also grown to 42% of committed risk ($5,507 across six spreads), which is
# the largest single concentration in the book.
#
# Runs ONCE, 09:31 ET Thu 3 Sep - a minute after the open so the first prints
# have landed and quotes are real rather than the overnight indicative spread.
# Cancels the resting exits first so they cannot race the close.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PYBIN="/opt/homebrew/bin/python3"
set -uo pipefail
cd /Users/pautax/Documents/DELTAX || exit 1
[ -f ./.env.alpaca ] || { echo "$(date -u +%FT%TZ) FATAL: .env.alpaca missing" >> logs/smh.log; exit 1; }
set -a; . ./.env.alpaca; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY
unset ALPACA_LIVE_TRADE
{
  echo "──────── CLOSE SMH $(date -u +%FT%TZ) ────────"
  # cancel resting exits on SMH legs only - other books keep theirs
  for id in $(alpaca order list --status open --limit 100 --quiet 2>/dev/null \
      | "$PYBIN" -c "
import sys,json
d=json.load(sys.stdin); d=d if isinstance(d,list) else d.get('orders',[])
for o in d:
    legs=o.get('legs') or [o]
    if any(str(l.get('symbol','')).startswith('SMH') for l in legs):
        print(o['id'])"); do
    alpaca order cancel --order-id "$id" --quiet >/dev/null 2>&1 && echo "  cancelled $id"
  done
  sleep 3
  for sym in $(alpaca position list --quiet 2>/dev/null \
      | "$PYBIN" -c "
import sys,json
d=json.load(sys.stdin); d=d if isinstance(d,list) else d.get('positions',[])
for p in d:
    if str(p.get('symbol','')).startswith('SMH'): print(p['symbol'])"); do
    alpaca position close --symbol "$sym" --quiet 2>&1 | head -2 | sed "s/^/  closed $sym: /"
  done
  sleep 5
  echo "  SMH legs remaining:"
  alpaca position list --quiet 2>/dev/null | "$PYBIN" -c "
import sys,json
d=json.load(sys.stdin); d=d if isinstance(d,list) else d.get('positions',[])
n=[p for p in d if str(p.get('symbol','')).startswith('SMH')]
print('   ', len(n))"
} >> logs/smh.log 2>&1
