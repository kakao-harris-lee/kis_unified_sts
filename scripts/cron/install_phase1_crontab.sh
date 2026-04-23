#!/usr/bin/env bash
# Idempotent install of Phase 1 cron entries.
set -euo pipefail
BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "macro_overnight.sh" > "$TMP" || true
mkdir -p "$BASE/logs"
cat >> "$TMP" <<EOF
# --- Phase 1 Futures Paradigm macro ---
30 6 * * 1-5 $BASE/scripts/cron/macro_overnight.sh us >> $BASE/logs/macro-us.log 2>&1
*/15 * * * 1-5 $BASE/scripts/cron/macro_overnight.sh fx >> $BASE/logs/macro-fx.log 2>&1
EOF
crontab "$TMP"
rm -f "$TMP"
echo "installed."
