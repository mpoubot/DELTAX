#!/bin/bash
# Regenerate the public team board and push it. Runs from cron.
#
# SAFETY: stages ONLY docs/index.html. Never `git add -A` from an automated
# job - one stray file and the credentials go public with the page.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/pautax/Documents/DELTAX || exit 1
set -a; . ./.env.alpaca 2>/dev/null; set +a
export ALPACA_API_KEY ALPACA_SECRET_KEY

/opt/homebrew/bin/python3 -m deltax.webdash >/dev/null 2>&1 || exit 1

# Refuse to publish if the generated page contains anything key-shaped.
if grep -qE "PK[A-Z0-9]{18,}|SECRET" docs/index.html; then
  echo "$(date -u +%FT%TZ) REFUSED: key-shaped string in generated page" >> logs/publish.log
  exit 1
fi

git add docs/index.html
if git diff --cached --quiet; then exit 0; fi          # nothing changed
git -c user.name="DELTAX bot" -c user.email="noreply@deltax.local" \
    commit -q -m "dashboard: refresh $(date -u +%FT%TZ)" || exit 1
git push -q origin main 2>>logs/publish.log \
  && echo "$(date -u +%FT%TZ) published" >> logs/publish.log
