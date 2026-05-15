#!/usr/bin/env bash
# Idempotent install of the Setup A/C signal-timing monitor cron entry.
#
# Immediate purpose: validate PR #252 (indicator-cache staleness fix) over
# the next trading week — confirm Setup A/C generates signals throughout the
# session, not just before the old ~4h cache-freeze point. Ongoing value:
# catches any future cache-freeze regression in the orchestrator path.
#
# Schedule: Mon-Fri 16:05 KST (5 min after the §10.2 daily verification at
# 16:00, before the Sunday reports rotation).
set -euo pipefail
BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
crontab -l 2>/dev/null \
    | grep -v "setup_ac_signal_timing\|install_setup_ac_monitor" > "$TMP" || true

cat >> "$TMP" <<EOF
# --- Setup A/C signal-timing monitor (Mon-Fri 16:05 KST) — PR #252 validation ---
5 16 * * 1-5 $BASE/scripts/cron/setup_ac_signal_timing.sh >> $BASE/logs/setup_ac_monitor_cron_\$(date +\%Y\%m\%d).log 2>&1
EOF

crontab "$TMP"
rm -f "$TMP"
echo "installed."
