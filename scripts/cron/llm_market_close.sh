#!/bin/bash
# LLM Market Close Briefing - kis_unified_sts
# Sends comprehensive end-of-day trading report via Telegram.
#
# crontab: 30 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_market_close.sh

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/llm_market_close_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Market Close Briefing Start ==="

cd "$PROJECT_DIR"
source "$VENV"
set -a && source .env && set +a

python3 -m scripts.analysis.llm_market_close_briefing >> "$LOG_FILE" 2>&1

log "=== Market Close Briefing Complete ==="
