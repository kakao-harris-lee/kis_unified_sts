#!/usr/bin/env bash
# Idempotent install of the stock trading watchdog cron entries.
#
# stock_trading.sh start is idempotent and recovers an existing process when
# the PID file is missing, so it is safe to call every 5 minutes during market
# hours. This closes the operational gap where a single 08:55 start failure or
# an intraday crash leaves stock paper trading stopped until the next day.
set -euo pipefail

BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "install_stock_trading_watchdog\|stock_trading_watchdog" > "$TMP" || true

cat >> "$TMP" <<EOF
# --- Stock trading watchdog (Mon-Fri 09:02-15:52 KST, every 5 min) ---
2-52/5 9-15 * * 1-5 $BASE/scripts/cron/stock_trading.sh start >> $BASE/logs/stock_trading_watchdog_\$(date +\%Y\%m\%d).log 2>&1
EOF

crontab "$TMP"
rm -f "$TMP"
echo "installed."
