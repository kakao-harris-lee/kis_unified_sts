#!/usr/bin/env bash
# Idempotent install of Phase 1 cron entries.
set -euo pipefail
BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "macro_overnight.sh" > "$TMP" || true
cat >> "$TMP" <<'EOF'
# --- Phase 1 Futures Paradigm macro ---
30 6 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/macro_overnight.sh us >> /var/log/kis-macro-us.log 2>&1
*/15 * * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/macro_overnight.sh fx >> /var/log/kis-macro-fx.log 2>&1
EOF
crontab "$TMP"
rm -f "$TMP"
echo "installed."
