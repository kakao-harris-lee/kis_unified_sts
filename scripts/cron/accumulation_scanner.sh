#!/bin/bash
# Accumulation Scanner - kis_unified_sts
# Scans for volume accumulation patterns and publishes candidates to Redis.
# Runs once nightly after backfill completes.
#
# crontab: 30 21 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/accumulation_scanner.sh

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/accumulation_scanner_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Accumulation Scanner Start ==="

cd "$PROJECT_DIR"
source "$VENV"

# Load environment variables
set -a && source .env && set +a

# Check trading day
IS_TRADING_DAY=$(python3 -c "
from shared.collector.historical.calendar import is_trading_day
from datetime import date
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "0")

if [ "$IS_TRADING_DAY" != "1" ]; then
    log "Not a trading day. Exiting."
    exit 0
fi

log "Running accumulation scan..."

python3 -m shared.scanner.accumulation >> "$LOG_FILE" 2>&1

log "=== Accumulation Scanner Complete ==="
