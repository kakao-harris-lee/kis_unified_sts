#!/bin/bash
# Reports rotation — kis_unified_sts cron wrapper.
#
# Compresses old daily-verification / counterfactual / drill reports under
# reports/ and prunes already-gzipped files past their retention window.
# See scripts/maintenance/rotate_reports.py for policy details.
#
# crontab: 0 4 * * 0 /home/deploy/project/kis_unified_sts/scripts/cron/rotate_reports.sh
#          (Sunday 04:00 KST — quiet hours, weekly cadence is enough)

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/rotate_reports_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
source "$VENV"

python3 -m scripts.maintenance.rotate_reports --apply >> "$LOG_FILE" 2>&1
status=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] rotation exit=$status" >> "$LOG_FILE"
exit "$status"
