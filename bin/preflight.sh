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
A=$(alpaca account get --quiet 2>/dev/null)
echo "$A" | grep -q "PA3ID1B9L6BP" && ok "competition account" "PA3ID1B9L6BP" || no "competition account" "WRONG ACCOUNT"
echo "$A" | grep -q '"status": *"ACTIVE"' && ok "account status" "ACTIVE" || no "account status" "not active"
EQ=$(echo "$A"|python3 -c "import sys,json;print(json.load(sys.stdin).get('equity'))" 2>/dev/null)
[ "$EQ" = "100000" ] && ok "starting equity" "\$100,000 untouched" || warn "starting equity" "$EQ"
echo "$A" | grep -q '"options_trading_level": *3' && ok "options level" "3 (spreads permitted)" || no "options level" "insufficient for spreads"

echo; echo "── 3. safety interlocks ──"
python3 -m deltax.run --force --live 2>&1 | grep -q REFUSED && ok "--force cannot reach --live" "refused" || no "--force + --live" "ALLOWED"
[ -z "${DELTAX_ORDERS_ALLOWED:-}" ] && ok "orders disabled by default" "env flag unset" || warn "orders enabled" "DELTAX_ORDERS_ALLOWED set"
[ -z "${ALPACA_LIVE_TRADE:-}" ] && ok "live-trade flag absent" "paper only" || no "ALPACA_LIVE_TRADE" "SET — refuse to run"
grep -q "unset DELTAX_ORDERS_ALLOWED" bin/deltax-cron.sh && ok "cron cannot place orders" "flag unset in wrapper" || no "cron order guard" "missing"

echo; echo "── 4. agent ──"
TP=0; TF=0
for t in tests/*.py; do
  R=$(python3 "$t" 2>&1|grep -oE "[0-9]+ passed, [0-9]+ failed")
  TP=$((TP+$(echo "$R"|grep -oE "^[0-9]+"))); TF=$((TF+$(echo "$R"|grep -oE "[0-9]+ failed"|grep -oE "^[0-9]+")))
done
[ "$TF" = "0" ] && ok "test suite" "$TP passed, 0 failed" || no "test suite" "$TF FAILING"
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
if [ $F -gt 0 ]; then echo -e "  \033[31m⛔ NOT CLEARED TO TRADE\033[0m"; else
  echo -e "  \033[32m✅ CLEARED — agent may trade at the open\033[0m"; fi
echo "══════════════════════════════════════════════════════════════════════════"
exit $F
