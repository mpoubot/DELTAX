#!/bin/bash
# Flatten the book before judging. Runs Fri 4 Sep 10:00 ET.
#
# Whatever is open at 11:00 is marked mid-decay, so a credit spread that has
# not reached target by then never will - there is no time left. This closes
# everything at market regardless of P&L (E37).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="/opt/homebrew/bin/python3"
cd /Users/pautax/Documents/DELTAX || exit 1
set -a; . ./.env.alpaca 2>/dev/null; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY DELTAX_ORDERS_ALLOWED=1
unset ALPACA_LIVE_TRADE
mkdir -p logs
{
  echo "──────── CLOSE FOR JUDGING $(date -u +%FT%TZ) ────────"
  # Cancel resting exits first so they cannot race the close.
  for id in $(alpaca order list --status open --limit 50 --quiet 2>/dev/null \
              | "$PYBIN" -c "import sys,json;d=json.load(sys.stdin);d=d if isinstance(d,list) else d.get('orders',[]);[print(o['id']) for o in d]"); do
    alpaca order cancel --order-id "$id" --quiet >/dev/null 2>&1 && echo "  cancelled resting order $id"
  done
  sleep 3
  alpaca position close-all --cancel-orders --quiet 2>&1 | head -20
  sleep 5
  echo "  remaining positions:"
  alpaca position list --quiet 2>/dev/null | "$PYBIN" -c "import sys,json;d=json.load(sys.stdin);d=d if isinstance(d,list) else d.get('positions',[]);print('   ',len(d))"
  alpaca account get --quiet 2>/dev/null | "$PYBIN" -c "import sys,json;d=json.load(sys.stdin);print(f\"   final equity \${float(d['equity']):,.2f} · cash \${float(d['cash']):,.2f}\")"
} >> logs/judging.log 2>&1
