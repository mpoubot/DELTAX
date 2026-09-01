#!/bin/bash
# Go/no-go for Monday. Every line is a check that must be true to trade.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/pautax/Documents/DELTAX || exit 1
set -a; . ./.env.alpaca 2>/dev/null; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY
P=0; F=0; W=0
ok(){ printf "  \033[32m✅\033[0m %-46s %s\n" "$1" "$2"; P=$((P+1)); }
no(){ printf "  \033[31m❌\033[0m %-46s %s\n" "$1" "$2"; F=$((F+1)); }
warn(){ printf "  \033[33m⚠️ \033[0m %-46s %s\n" "$1" "$2"; W=$((W+1)); }
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║  DELTAX PREFLIGHT — Monday 31 Aug 2026, 09:30 ET                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"

echo; echo "── 1. infrastructure ──"
command -v alpaca >/dev/null && ok "alpaca CLI" "$(alpaca version 2>/dev/null|head -1)" || no "alpaca CLI" "NOT FOUND"
command -v python3 >/dev/null && ok "python3" "$(python3 -V 2>&1)" || no "python3" "missing"
[ -f .env.alpaca ] && ok "credentials file" "present, mode $(stat -f %Lp .env.alpaca)" || no "credentials file" "MISSING"
git check-ignore .env.alpaca >/dev/null 2>&1 && ok "credentials gitignored" "yes" || no "credentials gitignored" "EXPOSED"
# Read the key from the env file at runtime - NEVER hardcode it here. The
# first version of this line embedded the literal key, which put it into a
# public repo and into git history. A leak detector must not carry the secret
# it detects.
KEYPAT="${ALPACA_API_KEY:-}"
if [ -n "$KEYPAT" ] && git grep -qI -- "$KEYPAT" . 2>/dev/null; then
  no "no keys in tracked files" "LEAK"
else
  ok "no keys in tracked files" "clean"
fi

echo; echo "── 2. account ──"
PYBIN=/opt/homebrew/bin/python3
A=$(alpaca account get --quiet 2>/dev/null)
# The check that matters is not "is it this literal account" but "do the keys
# open the account execution is pinned to". Hardcoding the ID meant switching
# accounts blocked preflight on a label rather than a real fault (E40).
PINNED="${DELTAX_ACCOUNT:-PA397N6FXXIE}"
LIVE=$(echo "$A" | "$PYBIN" -c "import sys,json;print(json.load(sys.stdin).get('account_number',''))" 2>/dev/null)
if [ -n "$LIVE" ] && [ "$LIVE" = "$PINNED" ]; then
  ok "account matches execution pin" "$LIVE"
elif [ -n "$LIVE" ]; then
  no "account mismatch" "keys open $LIVE, execution pinned to $PINNED - run bin/switch-account.sh"
else
  no "account unreachable" "no account number returned"
fi
echo "$A" | grep -q '"status": *"ACTIVE"' && ok "account status" "ACTIVE" || no "account status" "not active"
EQ=$(echo "$A"|python3 -c "import sys,json;print(json.load(sys.stdin).get('equity'))" 2>/dev/null)
if [ "$EQ" = "100000" ]; then
  ok "equity" "\$100,000 — untouched"
else
  warn "equity" "$(python3 -c "print(f'\${float('$EQ'):,.2f}  ({float('$EQ')-100000:+,.2f} vs start)')" 2>/dev/null || echo "$EQ")"
fi
echo "$A" | grep -q '"options_trading_level": *3' && ok "options level" "3 (spreads permitted)" || no "options level" "insufficient for spreads"

echo; echo "── 3. autonomous execution ──"
# The agent is MEANT to place orders. These verify it can, and that the guards
# which must survive that are intact. Checking for orders-disabled here would
# fail on the intended configuration and train the reader to ignore preflight.
grep -q "DELTAX_ORDERS_ALLOWED=1" bin/deltax-cron.sh && ok "orders enabled in cron" "autonomous" || no "orders NOT enabled" "agent cannot trade"
grep -q -- "--live" bin/deltax-cron.sh && ok "cron passes --live" "orders will submit" || no "cron missing --live" "dry run only"
grep -vE '^\s*#' bin/deltax-cron.sh | grep -q -- "--force" && no "cron passes --force" "WOULD OVERRIDE PERMISSION STATE" || ok "cron never passes --force" "permission state authoritative"
[ -z "${ALPACA_LIVE_TRADE:-}" ] && ok "paper only" "ALPACA_LIVE_TRADE unset" || no "ALPACA_LIVE_TRADE" "SET — refuse to run"
grep -q "unset ALPACA_LIVE_TRADE" bin/deltax-cron.sh && ok "cron forces paper" "live-trade unset in wrapper" || no "cron paper guard" "missing"
python3 -m deltax.run --force --live 2>&1 | grep -q REFUSED && ok "--force cannot reach --live" "refused" || no "--force + --live" "ALLOWED"
python3 -c "
import sys; sys.path.insert(0,'.')
from deltax import execute
import inspect
src = inspect.getsource(execute.preflight)
sys.exit(0 if 'COMPETITION_ACCOUNT' in inspect.getsource(execute) and 'account mismatch' in src else 1)" 2>/dev/null && ok "orders pinned to one account" "preflight refuses mismatch" || no "account pinning" "NOT enforced"
python3 -c "
import sys; sys.path.insert(0,'.')
from deltax.manage import TAKE_PROFIT_FRACTION, TIME_STOP_DTE
sys.exit(0 if TAKE_PROFIT_FRACTION==0.50 and TIME_STOP_DTE==2 else 1)" 2>/dev/null && ok "exit rule armed" "GTC at 50% credit, 2-DTE time stop" || no "exit rule" "not configured"
grep -q "place_exit" deltax/run.py && ok "exits placed at fill" "E5 wired into run.py" || no "exits NOT wired" "agent would never close"

echo; echo "── 4. agent ──"
# A file that produces no summary line used to make this arithmetic throw and
# silently truncate the total - it reported 111 of 380 while still printing a
# tick. A verification script that under-counts is worse than none, so a file
# that yields no result is now a FAILURE, not a zero.
TP=0; TF=0; TSILENT=0
for t in tests/*.py; do
  R=$(python3 "$t" 2>&1 | grep -oE "[0-9]+ passed, [0-9]+ failed" | tail -1)
  P=$(echo "$R" | grep -oE "^[0-9]+")
  F=$(echo "$R" | grep -oE "[0-9]+ failed" | grep -oE "^[0-9]+")
  if [ -z "$P" ]; then TSILENT=$((TSILENT+1)); continue; fi
  TP=$((TP + P)); TF=$((TF + ${F:-0}))
done
if [ "$TSILENT" != "0" ]; then
  no "test suite" "$TSILENT file(s) produced no result - cannot verify"
elif [ "$TF" != "0" ]; then
  no "test suite" "$TF FAILING"
else
  ok "test suite" "$TP passed, 0 failed across $(ls tests/*.py | wc -l | tr -d ' ') files"
fi
python3 -c "import deltax.run,deltax.gates,deltax.screener,deltax.execute,deltax.permission,deltax.ledger" 2>/dev/null && ok "all modules import" "clean" || no "module import" "BROKEN"
rm -rf logs/preflight && python3 -m deltax.run >/dev/null 2>&1 && ok "dry run completes" "exit 0" || warn "dry run" "non-zero (market closed is normal)"
python3 -m deltax.ledger logs 2>/dev/null | grep -q "intact" && ok "ledger chain" "intact" || warn "ledger chain" "no entries yet"

echo; echo "── 5. schedule ──"
crontab -l 2>/dev/null | grep -q deltax-cron && ok "cron installed" "*/5 * * * *" || no "cron" "not installed"
pgrep -x cron >/dev/null && ok "cron daemon" "running" || no "cron daemon" "stopped"
pgrep -x caffeinate >/dev/null && ok "machine stays awake" "caffeinate running" || warn "caffeinate" "not running — Mac may sleep"
grep -c "exit=0" logs/cron.log 2>/dev/null | xargs -I{} sh -c '[ {} -gt 0 ] && exit 0 || exit 1' && ok "cron has run successfully" "$(grep -c 'exit=0' logs/cron.log) times" || warn "cron runs" "none yet"

echo; echo "── 6. contest requirements ──"
grep -q "MIT" LICENSE 2>/dev/null && ok "MIT license" "present" || no "MIT license" "missing"
[ -f README.md ] && ok "README" "present" || no "README" "missing"
git remote -v 2>/dev/null | grep -q github && ok "GitHub remote" "$(git remote get-url origin 2>/dev/null)" || no "GitHub remote" "none"
[ -z "$(git status --porcelain)" ] && ok "working tree clean" "all committed" || warn "uncommitted changes" "$(git status --porcelain|wc -l|tr -d ' ') files"
git log -1 --format=%H >/dev/null 2>&1 && ok "rule provenance" "commit $(git log -1 --format=%h)" || no "git history" "none"

echo
echo "══════════════════════════════════════════════════════════════════════════"
printf "  \033[1m%d passed · %d warnings · %d BLOCKING\033[0m\n" $P $W $F
# E42: a green preflight must never read as "go" while the stand-down is on.
SUSPENDED=$(python3 -c "import sys;sys.path.insert(0,'.');import deltax.gates as g;print('1' if g.TRADING_SUSPENDED else '0')" 2>/dev/null || echo "?")
if [ $F -gt 0 ]; then
  echo -e "  \033[31m⛔ NOT CLEARED TO TRADE\033[0m"
elif [ "$SUSPENDED" = "1" ]; then
  echo -e "  \033[33m◆ SYSTEMS GREEN — BUT TRADING IS SUSPENDED (E42)\033[0m"
  echo -e "  \033[33m  Every 2-3 DTE structure the contest window allows tests\033[0m"
  echo -e "  \033[33m  negative (-\$50,904 / 26wk). No orders will be placed.\033[0m"
elif [ "$SUSPENDED" = "?" ]; then
  echo -e "  \033[31m⛔ CANNOT READ STAND-DOWN STATE — treating as NOT CLEARED\033[0m"
else
  echo -e "  \033[32m✅ CLEARED — agent may trade at the open\033[0m"
fi
echo "══════════════════════════════════════════════════════════════════════════"
exit $F
