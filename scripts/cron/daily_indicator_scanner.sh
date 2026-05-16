#!/bin/bash
# Daily indicator scanner — pre-compute daily SMA/RSI/ATR for paper trading.
# The Python runner includes recent Redis candidates by default, so the 08:58
# pass expands coverage after screener/fusion publish dynamic targets.
# Crontab: 50,58 8 * * 1-5  (Mon-Fri KST, before market open)
#
# Usage: crontab -e
#   50,58 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/daily_indicator_scanner.sh

cd /home/deploy/project/kis_unified_sts || exit 1
source .venv/bin/activate
set -a && source .env && set +a

python scripts/daily_indicator_scanner.py 2>&1 | logger -t daily-indicator-scanner
