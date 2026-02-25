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
PROC_PATTERN="/home/deploy/project/kis_unified_sts/.venv/bin/sts rl paper --no-daemon"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

detect_running_pid() {
    pgrep -f "$PROC_PATTERN" 2>/dev/null | head -n 1 || true
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

    # Fallback: detect live process even when PID file is missing/stale.
    DETECTED_PID=$(detect_running_pid)
    if [ -n "$DETECTED_PID" ]; then
        echo "$DETECTED_PID" > "$PID_FILE"
        log "Already running (PID: $DETECTED_PID, recovered without PID file)"
        exit 0
    fi

    log "=== RL Paper Trading Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"

    # Load environment variables
    set -a && source .env && set +a

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

    log "Trading day confirmed. Starting RL paper trading..."

    # Start RL paper trading in a detached session.
    # setsid avoids parent shell/session cleanup side effects and keeps PID stable.
    setsid bash -c 'exec sts rl paper --no-daemon' \
        >> "$LOG_FILE" 2>&1 < /dev/null &

    PID=$!
    echo "$PID" > "$PID_FILE"

    # Early liveness check to avoid stale PID files on immediate startup failure.
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        log "RL paper trading started (PID: $PID)"
    else
        rm -f "$PID_FILE"
        log "Failed to start RL paper trading (process exited early)"
        exit 1
    fi
}

stop_trading() {
    PID=""
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
    else
        PID=$(detect_running_pid)
    fi

    if [ -n "$PID" ]; then
        if ps -p "$PID" > /dev/null 2>&1; then
            log "Stopping RL paper trading (PID: $PID)"
            kill "$PID" 2>/dev/null || true
            sleep 5
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null || true
                log "Force killed (SIGKILL)"
            else
                log "Graceful shutdown completed"
            fi
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
        PID=$(detect_running_pid)
        if [ -n "$PID" ]; then
            echo "$PID" > "$PID_FILE"
            echo "Running (PID: $PID, recovered)"
            exit 0
        fi
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
