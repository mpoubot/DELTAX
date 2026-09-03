#!/bin/bash
# DELTAX scheduled run — LIVE. This places real paper orders.
#
# E93: the header used to read "DRY RUN ONLY" and list three reasons an order
# was impossible, while the body below passes --live AND sets
# DELTAX_ORDERS_ALLOWED=1. Both statements could not be true. Anyone reading
# the top of this file to decide whether it was safe to edit was being told the
# opposite of what it does; the comment is now what the script actually is.
#
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

# E93: SINGLE INSTANCE. cron fires every 5 minutes; a healthy cycle takes ~20s,
# but every broker call retries 3x (E76) against a 30s timeout, so one degraded
# endpoint can stretch a cycle past 40 minutes. cron keeps firing regardless,
# so eight or more cycles can run at once - and two cycles that both reconcile
# the book BEFORE either submits will each size against the same free budget
# and breach the portfolio cap. That is precisely the failure reconcile.py
# exists to prevent, reintroduced through concurrency.
#
# mkdir is atomic on every filesystem here, unlike a test-then-create pidfile.
# A lock older than 15 minutes is treated as abandoned (the process died
# without its trap running) and reclaimed.
LOCK="/tmp/deltax-cycle.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  LOCK_AGE=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0) ))
  if [ "$LOCK_AGE" -gt 900 ]; then
    echo "$(date -u +%FT%TZ) reclaiming stale lock (${LOCK_AGE}s old)" >> logs/cron.log
    rm -rf "$LOCK"
    mkdir "$LOCK" 2>/dev/null || exit 0
  else
    echo "$(date -u +%FT%TZ) SKIPPED: a cycle is already running (lock ${LOCK_AGE}s old)" >> logs/cron.log
    exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

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
