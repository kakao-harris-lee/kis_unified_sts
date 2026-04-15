#!/bin/bash
# Daily equity snapshot publisher for cross-session capital tracking.
# Intended cron: 40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh
set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/equity_snapshot_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a && source "$PROJECT_DIR/.env" && set +a
fi
source "$PROJECT_DIR/.venv/bin/activate"
python "$PROJECT_DIR/scripts/analysis/publish_equity_snapshot.py" >> "$LOG_FILE" 2>&1
