#!/usr/bin/env bash
# DELTAX morning ritual — run pre-open on the Hetzner box.
# Cron (07:00 ET weekdays; host clock in UTC):
#   0 11 * * 1-5 /path/to/DELTAX/scripts/morning-ritual.sh >> /var/log/deltax-morning.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

# .env.alpaca is gitignored and lives only on the host.
set -a; . ./.env.alpaca; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY
# SEC returns 403 without a real name + contact address.
: "${DELTAX_SEC_UA:?set DELTAX_SEC_UA='Your Name your@email.com'}"

echo "=== $(date -u +%FT%TZ) ==="
python3 -m deltax.morning
