#!/usr/bin/env bash
# 매일 장 마감 후 주식 일봉 데이터 수집.
# crontab: 20 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_daily_backfill.sh

set -euo pipefail

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/stock_daily_backfill_$(date +%Y%m%d).log"
DAYS="${STOCK_DAILY_BACKFILL_DAYS:-100}"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

cd "$PROJECT_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

IS_TRADING_DAY=$(python -c "
from datetime import date
from shared.collector.historical.calendar import is_trading_day
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "0")

if [ "$IS_TRADING_DAY" != "1" ]; then
  log "오늘은 휴장일입니다. 일봉 수집 스킵."
  exit 0
fi

log "=== Stock daily backfill start (days=$DAYS) ==="
sts stock-backfill daily --days "$DAYS" >> "$LOG_FILE" 2>&1
sts stock-backfill daily-status --days "$DAYS" >> "$LOG_FILE" 2>&1
log "=== Stock daily backfill done ==="
