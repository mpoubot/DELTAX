#!/bin/bash
# Point DELTAX at a different Alpaca paper account.
#
#   bin/switch-account.sh
#
# Reads the new credentials already saved in .env.alpaca, asks Alpaca which
# account they belong to, and writes that account number back as DELTAX_ACCOUNT
# so the execution pin follows the keys instead of blocking every order.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/pautax/Documents/DELTAX || exit 1
set -a; . ./.env.alpaca 2>/dev/null; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY

ACCT=$(alpaca account get --quiet 2>/dev/null \
       | /opt/homebrew/bin/python3 -c "import sys,json;print(json.load(sys.stdin).get('account_number',''))" 2>/dev/null)
if [ -z "$ACCT" ]; then
  echo "❌ could not reach Alpaca with the keys in .env.alpaca — check them first"
  exit 1
fi

grep -v '^DELTAX_ACCOUNT=' .env.alpaca > .env.alpaca.tmp
echo "DELTAX_ACCOUNT=$ACCT" >> .env.alpaca.tmp
mv .env.alpaca.tmp .env.alpaca
chmod 600 .env.alpaca

echo "✅ execution pinned to $ACCT"
set -a; . ./.env.alpaca; set +a
/opt/homebrew/bin/python3 - <<'PY'
import json, os, subprocess
o = subprocess.run(["alpaca","account","get","--quiet"], capture_output=True, text=True, env=os.environ)
d = json.loads(o.stdout)
print(f"   status  {d.get('status')}")
print(f"   equity  ${float(d.get('equity',0)):,.2f}")
print(f"   options level {d.get('options_trading_level')}")
PY
echo
echo "Next: run ./bin/preflight.sh to confirm all 30 checks pass on the new account."
