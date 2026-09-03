#!/bin/bash
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
