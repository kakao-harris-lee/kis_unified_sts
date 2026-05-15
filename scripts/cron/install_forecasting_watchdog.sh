#!/usr/bin/env bash
# Idempotent install of the forecasting daemon watchdog cron entry.
#
# The `forecasting` Docker container runs the Phase D HAR-RV publisher
# (~390 rows/session into kospi.vol_forecasts) plus the event scorer.
# `docker-compose.yml` already declares `restart: unless-stopped`, but if the
# container is explicitly stopped (or the host is rebooted) nothing brings it
# back automatically.  This watchdog runs every 5 minutes during market hours
# and calls `forecasting.sh start` — which is idempotent (no-op when the
# container is up).
#
# The schedule mirrors the rl_paper watchdog (`2-37/5 9-15 * * 1-5`) but starts
# 10 min earlier so the daemon is warm when the orchestrator opens its first
# tick at 09:00 KST.
set -euo pipefail
BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "install_forecasting_watchdog\|forecasting.sh start" > "$TMP" || true

cat >> "$TMP" <<EOF
# --- Forecasting daemon watchdog (Mon-Fri 08:50-15:55 KST, every 5 min) ---
50-55/5 8 * * 1-5 $BASE/scripts/cron/forecasting.sh start >> $BASE/logs/forecasting_watchdog_\$(date +\%Y\%m\%d).log 2>&1
*/5 9-15 * * 1-5 $BASE/scripts/cron/forecasting.sh start >> $BASE/logs/forecasting_watchdog_\$(date +\%Y\%m\%d).log 2>&1
EOF

crontab "$TMP"
rm -f "$TMP"
echo "installed."
