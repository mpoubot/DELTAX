#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ RETIRED 2026-09-06 — DO NOT RUN. IT CANCELLED EVERY EXIT AND CLOSED NONE ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# What it was supposed to do: flatten the book at Fri 4 Sep 10:00 ET, before
# judging. What it actually did, from logs/judging.log:
#   1. Cancelled all 11 resting GTC exits.                        <- REAL
#   2. Ran `alpaca position close-all --cancel-orders`.           <- REJECTED
#      The broker returned 403 with an empty order body:
#        {"body":{"notional":null,"time_in_force":"","type":""},
#         "status":403,"symbol":"C260918P00130000"}
#      `position close-all` submits no order type and no time-in-force, which
#      the API will not accept for an option leg.
#   3. Logged "remaining positions: 11" and exited 0.
#
# Net effect: identical to close-smh.sh (E104). The book went from fully
# covered by resting exits to eleven naked legs over a weekend, and the log
# read as a completed flatten. This is the SECOND time a bulk/positional CLI
# close has silently done nothing after cancelling real protection.
#
# THE RULE, now twice-earned: a spread is only ever closed through
# execute.submit(..., close=True), which builds a multi-leg order with real
# buy_to_close/sell_to_close intents. Nothing else in this system closes a
# spread. `position close`, `position close-all` and per-leg variants do not.
#
# THE REPLACEMENT: no script. The 5-minute cycle already flattens correctly.
# During the weekly window (Fri 10:00-16:00 ET) manage.past_contest_deadline()
# is True, so Managed.reason() returns "CONTEST DEADLINE" for every position
# and the sweep closes each one through _closer -> execute.submit(close=True).
# That path is tested, and it placed three live re-priced exits on 4 Sep while
# this script was failing beside it. E119.
exit 3

# ---- original, kept only as the record of what failed ----
# # Flatten the book before judging. Runs Fri 4 Sep 10:00 ET.
# #
# # Whatever is open at 11:00 is marked mid-decay, so a credit spread that has
# # not reached target by then never will - there is no time left. This closes
# # everything at market regardless of P&L (E37).
# export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# PYBIN="/opt/homebrew/bin/python3"
# cd /Users/pautax/Documents/DELTAX || exit 1
# set -a; . ./.env.alpaca 2>/dev/null; set +a
# export ALPACA_API_KEY ALPACA_SECRET_KEY DELTAX_ORDERS_ALLOWED=1
# unset ALPACA_LIVE_TRADE
# mkdir -p logs
# {
#   echo "──────── CLOSE FOR JUDGING $(date -u +%FT%TZ) ────────"
#   # Cancel resting exits first so they cannot race the close.
#   for id in $(alpaca order list --status open --limit 50 --quiet 2>/dev/null \
#               | "$PYBIN" -c "import sys,json;d=json.load(sys.stdin);d=d if isinstance(d,list) else d.get('orders',[]);[print(o['id']) for o in d]"); do
#     alpaca order cancel --order-id "$id" --quiet >/dev/null 2>&1 && echo "  cancelled resting order $id"
#   done
#   sleep 3
#   alpaca position close-all --cancel-orders --quiet 2>&1 | head -20
#   sleep 5
#   echo "  remaining positions:"
#   alpaca position list --quiet 2>/dev/null | "$PYBIN" -c "import sys,json;d=json.load(sys.stdin);d=d if isinstance(d,list) else d.get('positions',[]);print('   ',len(d))"
#   alpaca account get --quiet 2>/dev/null | "$PYBIN" -c "import sys,json;d=json.load(sys.stdin);print(f\"   final equity \${float(d['equity']):,.2f} · cash \${float(d['cash']):,.2f}\")"
# } >> logs/judging.log 2>&1