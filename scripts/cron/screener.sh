#!/bin/bash
# Stock Universe Screener - kis_unified_sts
# Polls KIS ranking APIs and publishes top-N symbols to Redis.
#
# crontab: 55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/screener.sh start
#          0 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/screener.sh stop

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/screener_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
PID_FILE="$PROJECT_DIR/pids/screener.pid"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_screener() {
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            log "Already running (PID: $OLD_PID)"
            exit 0
        else
            rm -f "$PID_FILE"
        fi
    fi

    log "=== Screener Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"

    # Load environment variables
    set -a && source .env && set +a

    # Aggressive trend-confirm tuning (Option 2):
    # keep more candidates while still applying anti-fakeout checks.
    export SCREENER_INTERVAL_SECONDS=${SCREENER_INTERVAL_SECONDS:-20}
    export KIS_RANKING_API_RATE_LIMIT=${KIS_RANKING_API_RATE_LIMIT:-1}
    export SCREENER_TREND_CONFIRM_ENABLED=${SCREENER_TREND_CONFIRM_ENABLED:-false}
    export SCREENER_TREND_CONFIRM_MAX_SCAN_CODES=${SCREENER_TREND_CONFIRM_MAX_SCAN_CODES:-3}
    export SCREENER_TREND_CONFIRM_CACHE_SECONDS=${SCREENER_TREND_CONFIRM_CACHE_SECONDS:-180}
    export SCREENER_TREND_CONFIRM_MIN_RETURN_PCT=0.25
    export SCREENER_TREND_CONFIRM_MAX_PULLBACK_PCT=0.60

    # Check trading day
    IS_TRADING_DAY=$(python3 -c "
from shared.collector.historical.calendar import is_trading_day
from datetime import date
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "1")

    if [ "$IS_TRADING_DAY" != "1" ]; then
        log "Not a trading day. Exiting."
        exit 0
    fi

    log "Trading day confirmed. Starting screener..."
    log "Rate tuning: interval=${SCREENER_INTERVAL_SECONDS}s, ranking_rate=${KIS_RANKING_API_RATE_LIMIT}/s"
    log "Trend confirm tuning: enabled=${SCREENER_TREND_CONFIRM_ENABLED}, max_scan=${SCREENER_TREND_CONFIRM_MAX_SCAN_CODES}, cache=${SCREENER_TREND_CONFIRM_CACHE_SECONDS}s, min_return=${SCREENER_TREND_CONFIRM_MIN_RETURN_PCT}, max_pullback=${SCREENER_TREND_CONFIRM_MAX_PULLBACK_PCT}"

    nohup setsid python3 -m services.screener \
        >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    log "Screener started (PID: $!)"
}

stop_screener() {
    local killed=0

    # 1) PID 파일 기반 종료
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "Stopping screener (PID: $PID)"
            kill "$PID" 2>/dev/null || true
            sleep 2
            kill -9 "$PID" 2>/dev/null || true
            killed=1
        fi
        rm -f "$PID_FILE"
    fi

    # 2) 프로세스명 기반 종료 (좀비 방지)
    ORPHANS=$(pgrep -f "python3 -m services.screener" 2>/dev/null || true)
    if [ -n "$ORPHANS" ]; then
        log "Killing orphan screener processes: $ORPHANS"
        echo "$ORPHANS" | xargs kill 2>/dev/null || true
        sleep 2
        echo "$ORPHANS" | xargs kill -9 2>/dev/null || true
        killed=1
    fi

    if [ "$killed" -eq 1 ]; then
        log "Screener stopped"
    else
        log "No screener process found"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Running (PID: $PID)"
            exit 0
        else
            echo "Not running (stale PID file)"
            exit 1
        fi
    else
        echo "Not running"
        exit 1
    fi
}

case "${1:-start}" in
    start)
        start_screener
        ;;
    stop)
        stop_screener
        ;;
    restart)
        stop_screener
        sleep 2
        start_screener
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
