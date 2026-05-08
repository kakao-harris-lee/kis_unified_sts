#!/bin/bash
# Counterfactual Weekly Report — kis_unified_sts §10.2 cron wrapper.
#
# Generates a weekly Setup A/C vs RL shadow counterfactual analysis for the
# previous ISO week (Mon-Sun), archives the JSON to reports/counterfactual/,
# and posts a Telegram summary to the briefing channel.
#
# crontab: 0 7 * * 1 /home/deploy/project/kis_unified_sts/scripts/cron/counterfactual_weekly.sh
#          (Mon 07:00 KST — after Sunday's full week is closed)

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/counterfactual_weekly_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Counterfactual Weekly Report Start ==="

cd "$PROJECT_DIR"
source "$VENV"
set -a && source .env && set +a

python3 -m scripts.analysis.counterfactual_weekly_report >> "$LOG_FILE" 2>&1

log "=== Counterfactual Weekly Report Complete ==="
