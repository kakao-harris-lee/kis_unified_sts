#!/usr/bin/env bash
# DEPRECATED (M5e): installs the stock-orchestrator watchdog cron. Superseded by
# the decoupled M4 pipeline + its systemd units after the M5d cutover. Do not
# install on a cut-over host. Runbook: docs/runbooks/stock-pipeline-cutover-m5d.md
# Idempotent install of the stock trading watchdog cron entries.
#
# stock_trading.sh start is idempotent and recovers an existing process when
# the PID file is missing, so it is safe to call every 5 minutes during market
# hours. This closes the operational gap where a single 08:55 start failure or
# an intraday crash leaves stock paper trading stopped until the next day.
set -euo pipefail

BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

crontab -l 2>/dev/null > "$TMP" || true
sed -i '/# BEGIN STOCK_TRADING_WATCHDOG/,/# END STOCK_TRADING_WATCHDOG/d' "$TMP"
sed -i '/# --- Stock trading watchdog/d' "$TMP"
sed -i '\#scripts/cron/stock_trading.sh start.*/stock_trading_watchdog_#d' "$TMP"

cat >> "$TMP" <<EOF
# BEGIN STOCK_TRADING_WATCHDOG
# Stock trading watchdog (Mon-Fri 09:02-15:52 KST, every 5 min)
2-52/5 9-15 * * 1-5 $BASE/scripts/cron/stock_trading.sh start >> $BASE/logs/stock_trading_watchdog_\$(date +\%Y\%m\%d).log 2>&1
# END STOCK_TRADING_WATCHDOG
EOF

crontab "$TMP"
echo "installed."
