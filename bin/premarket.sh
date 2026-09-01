#!/bin/bash
# PRE-MARKET INTELLIGENCE — gather, never trade.
#
# run.py returns at entry_allowed() the moment the market is closed, so the
# 5-minute agent job does nothing useful before the open. This runs the
# gathering stages that do NOT need an open market, so that by 09:30 the
# universe, the news and the earnings blackout are already resolved.
#
# It cannot trade: no --live anywhere, DELTAX_ORDERS_ALLOWED unset, and it
# never calls deltax.run.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PYBIN="/opt/homebrew/bin/python3"
cd /Users/pautax/Documents/DELTAX || exit 1
[ -x "$PYBIN" ] || { echo "$(date -u +%FT%TZ) FATAL: no python" >> logs/premarket.log; exit 1; }
set -a; . ./.env.alpaca 2>/dev/null; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY
unset DELTAX_ORDERS_ALLOWED ALPACA_LIVE_TRADE
mkdir -p logs

STAMP=$(date -u +%FT%TZ)
{
  echo "──────── PRE-MARKET $STAMP ────────"
  for stage in rss daily blocklist morning; do
    echo "── $stage"
    # macOS has no coreutils timeout; guard with a background wait instead so a
    # hung feed can never wedge the whole pre-market window.
    "$PYBIN" -m "deltax.$stage" > /tmp/dx_$stage.out 2>&1 &
    PID=$!
    for _ in $(seq 1 60); do kill -0 $PID 2>/dev/null || break; sleep 5; done
    if kill -0 $PID 2>/dev/null; then kill -9 $PID 2>/dev/null; echo "   TIMEOUT after 300s"; fi
    wait $PID 2>/dev/null; RC=$?
    tail -14 /tmp/dx_$stage.out
    echo "   exit=$RC"
  done
  "$PYBIN" -m deltax.webdash 2>&1 | tail -1
} >> logs/premarket.log 2>&1
