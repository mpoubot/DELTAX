#!/bin/bash
# DELTAX — freeze signal check. Places NO orders and touches NO positions.
#
# Reads the live book, prices it through the Fri 4 Sep 10:00 ET judging
# deadline with the regime-mixture engine, evaluates every unfreeze signal, and
# rewrites state/freeze.json. gates.gate_new_entries() reads that file.
#
# Fails closed by construction: on any error the check itself writes FROZEN, and
# an unfrozen state older than freeze.MAX_STATE_AGE_MIN re-freezes on read - so
# if this job stops running, exposure is not left authorised on a dead signal.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PYBIN="/opt/homebrew/bin/python3"
ALPACA="/opt/homebrew/bin/alpaca"

set -uo pipefail
cd /Users/pautax/Documents/DELTAX || exit 1

for req in "$PYBIN" "$ALPACA"; do
  [ -x "$req" ] || { echo "$(date -u +%FT%TZ) FATAL: missing $req" >> logs/unfreeze.log; exit 1; }
done
[ -f ./.env.alpaca ] || { echo "$(date -u +%FT%TZ) FATAL: .env.alpaca missing" >> logs/unfreeze.log; exit 1; }
set -a; . ./.env.alpaca; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY
unset ALPACA_LIVE_TRADE
unset DELTAX_ORDERS_ALLOWED     # this job must never be able to trade

# Single instance, same reasoning as deltax-cron.sh.
LOCK="/tmp/deltax-unfreeze.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  AGE=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0) ))
  if [ "$AGE" -gt 900 ]; then rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 0
  else exit 0; fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

mkdir -p logs state
{
  echo "──────── UNFREEZE CHECK $(date -u +%FT%TZ) ────────"
  "$PYBIN" -m deltax.unfreeze_check 2>&1
  echo "exit=$?"
} >> logs/unfreeze.log
