#!/bin/bash
# 매일 장 마감 후 주식 분봉 데이터 수집
# crontab: 50 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_backfill.sh
#
# 사용법:
#   ./scripts/cron/stock_backfill.sh          # 오늘 데이터만 (기본)
#   ./scripts/cron/stock_backfill.sh --days 7 # 최근 7일 백필

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/stock_backfill_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
source "$VENV"

# 거래일 확인 (공휴일/주말 체크)
IS_TRADING_DAY=$(python3 -c "
from datetime import date
from shared.collector.historical.calendar import is_trading_day
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "0")

if [ "$IS_TRADING_DAY" != "1" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 오늘은 휴장일입니다. 수집 스킵." >> "$LOG_FILE"
    exit 0
fi

# Parse arguments
DAYS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --days|-d)
            DAYS="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') 주식 분봉 수집 시작 ==="

    if [ -n "$DAYS" ]; then
        # 지정된 기간 백필
        sts stock-backfill run --days "$DAYS"
    else
        # 오늘 데이터만 수집
        sts stock-backfill today
    fi

    # 데이터 현황
    sts stock-backfill status

    echo "=== $(date '+%Y-%m-%d %H:%M:%S') 주식 분봉 수집 완료 ==="
} >> "$LOG_FILE" 2>&1
