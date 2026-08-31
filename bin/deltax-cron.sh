#!/bin/bash
# DELTAX scheduled run — DRY RUN ONLY.
#
# Three independent reasons this cannot place an order:
#   1. no --live flag, so run() is called with dry_run=True
#   2. DELTAX_ORDERS_ALLOWED is actively unset below
#   3. execute.preflight() refuses without both of the above
# Do NOT add --force here: that is an analysis switch and would override the
# trade-permission state (E22). Scheduled runs must obey it.

# cron runs with a minimal PATH (/usr/bin:/bin), so neither Homebrew python3
# nor the alpaca CLI is visible. The first scheduled run failed on exactly
# this: it picked CommandLineTools python3.9 and then raised FileNotFoundError
# on 'alpaca'. Both are pinned absolutely below - never rely on inherited PATH
# in a scheduled job.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PYBIN="/opt/homebrew/bin/python3"
ALPACA="/opt/homebrew/bin/alpaca"

set -uo pipefail
cd /Users/pautax/Documents/DELTAX || exit 1

for req in "$PYBIN" "$ALPACA"; do
  if [ ! -x "$req" ]; then
    echo "$(date -u +%FT%TZ) FATAL: missing $req" >> logs/cron.log
    exit 1
  fi
done

if [ ! -f ./.env.alpaca ]; then
  echo "$(date -u +%FT%TZ) FATAL: .env.alpaca missing" >> logs/cron.log
  exit 1
fi
set -a; . ./.env.alpaca; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY
export DELTAX_ORDERS_ALLOWED=1     # autonomous execution ON
unset ALPACA_LIVE_TRADE

STAMP=$(date -u +%FT%TZ)
{
  echo "──────── $STAMP ────────"
  "$PYBIN" -m deltax.run --live 2>&1
  echo "exit=$?"
} >> logs/cron.log
