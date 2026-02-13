#!/bin/bash
# Fusion Ranker - kis_unified_sts
# Merges real-time screener + LLM quality scores → trade targets.
#
# crontab: 55 8 * * 1-5 .../fusion_ranker.sh start
#          0 16 * * 1-5 .../fusion_ranker.sh stop

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/fusion_ranker_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
PID_FILE="$PROJECT_DIR/pids/fusion_ranker.pid"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_fusion() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            log "Already running (PID: $OLD_PID)"
            exit 0
        else
            rm -f "$PID_FILE"
        fi
    fi

    log "=== Fusion Ranker Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"
    set -a && source .env && set +a

    # Check trading day
    IS_TRADING_DAY=$(python3 -c "
from shared.utils.market_calendar import is_trading_day
from datetime import date
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "1")

    if [ "$IS_TRADING_DAY" != "1" ]; then
        log "Not a trading day. Exiting."
        exit 0
    fi

    log "Starting fusion ranker..."

    nohup python3 -m services.fusion_ranker \
        >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    log "Fusion ranker started (PID: $!)"
}

stop_fusion() {
    local killed=0

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "Stopping fusion ranker (PID: $PID)"
            kill "$PID" 2>/dev/null || true
            sleep 2
            kill -9 "$PID" 2>/dev/null || true
            killed=1
        fi
        rm -f "$PID_FILE"
    fi

    ORPHANS=$(pgrep -f "python3 -m services.fusion_ranker" 2>/dev/null || true)
    if [ -n "$ORPHANS" ]; then
        log "Killing orphan fusion ranker processes: $ORPHANS"
        echo "$ORPHANS" | xargs kill 2>/dev/null || true
        sleep 2
        echo "$ORPHANS" | xargs kill -9 2>/dev/null || true
        killed=1
    fi

    if [ "$killed" -eq 1 ]; then
        log "Fusion ranker stopped"
    else
        log "No fusion ranker process found"
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
        start_fusion
        ;;
    stop)
        stop_fusion
        ;;
    restart)
        stop_fusion
        sleep 2
        start_fusion
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
