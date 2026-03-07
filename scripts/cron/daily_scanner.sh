#!/bin/bash
# Daily scanner — pre-market universe selection with Layer 1 filters
# Crontab: 30 8 * * 1-5  (Mon-Fri 08:30 KST, before market open)
#
# Usage: crontab -e
#   30 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/daily_scanner.sh

cd /home/deploy/project/kis_unified_sts || exit 1
source .venv/bin/activate
set -a && source .env && set +a

python scripts/run_daily_scanner.py 2>&1 | logger -t daily-scanner
