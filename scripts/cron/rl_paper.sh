#!/bin/bash
# RL Paper Trading Service - kis_unified_sts
# MaskablePPO 모델 실시간 paper trading (KIS WebSocket + DataEngine)
#
# crontab: 55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh start
#          40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh stop

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/rl_paper_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
PID_FILE="$PROJECT_DIR/pids/rl_paper.pid"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_trading() {
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

    log "=== RL Paper Trading Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"

    # Load environment variables
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

    log "Trading day confirmed. Starting RL paper trading..."

    # Start RL paper trading (single session, stops at force_close_time 15:35)
    nohup sts rl paper --no-daemon \
        >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    log "RL paper trading started (PID: $!)"
}

stop_trading() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "Stopping RL paper trading (PID: $PID)"
            kill "$PID" 2>/dev/null || true
            sleep 3
            kill -9 "$PID" 2>/dev/null || true
            rm -f "$PID_FILE"
            log "RL paper trading stopped"
        else
            rm -f "$PID_FILE"
            log "Process not running, cleaned up PID file"
        fi
    else
        log "No PID file found"
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
        start_trading
        ;;
    stop)
        stop_trading
        ;;
    restart)
        stop_trading
        sleep 2
        start_trading
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
