#!/bin/bash
# Stock Trading Service - kis_unified_sts
# Replaces: quant_moment_sts main.py
#
# crontab: 55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh start
#          2-52/5 9-15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh start
#          0 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh stop

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/stock_trading_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
STS_BIN="$PROJECT_DIR/.venv/bin/sts"
PID_FILE="$PROJECT_DIR/pids/stock_trading.pid"
PROC_PATTERN_STS="$STS_BIN trade start --asset stock"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

detect_running_pid() {
    pgrep -f "$PROC_PATTERN_STS" 2>/dev/null | head -n 1 || true
}

get_process_group_id() {
    local pid="$1"
    ps -o pgid= -p "$pid" 2>/dev/null | tr -d '[:space:]'
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

    # Fallback: recover a live stock process even when the PID file is missing.
    # This keeps watchdog cron safe and prevents duplicate orchestrators.
    DETECTED_PID=$(detect_running_pid)
    if [ -n "$DETECTED_PID" ]; then
        echo "$DETECTED_PID" > "$PID_FILE"
        log "Already running (PID: $DETECTED_PID, recovered without PID file)"
        exit 0
    fi

    log "=== Stock Trading Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"
    if [ ! -x "$STS_BIN" ]; then
        log "sts binary not found: $STS_BIN"
        exit 1
    fi

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

    log "Trading day confirmed. Starting stock trading..."

    # Force stock metrics endpoint to match Prometheus scrape target.
    # Prevent inherited shell env (e.g. PROMETHEUS_PORT=8080) from breaking scrape.
    export PROMETHEUS_PORT="${STOCK_TRADING_PROMETHEUS_PORT:-9091}"
    log "Prometheus metrics port: $PROMETHEUS_PORT"

    # Start trading via fully detached session.
    setsid bash -c "exec '$STS_BIN' trade start \
        --asset stock \
        --capital 100000000 \
        --paper \
        --daemon" \
        >> "$LOG_FILE" 2>&1 < /dev/null &

    PID=$!
    echo "$PID" > "$PID_FILE"

    # Early liveness check to avoid stale PID files on immediate startup failure.
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        log "Stock trading started (PID: $PID)"
    else
        rm -f "$PID_FILE"
        log "Failed to start stock trading (process exited early)"
        exit 1
    fi
}

stop_trading() {
    PID=""
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ! ps -p "$PID" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            PID=$(detect_running_pid)
        fi
    else
        PID=$(detect_running_pid)
    fi

    if [ -n "$PID" ]; then
        if ps -p "$PID" > /dev/null 2>&1; then
            PGID=$(get_process_group_id "$PID")
            if [ -n "$PGID" ]; then
                log "Stopping stock trading (PID: $PID, PGID: $PGID)"
                kill -TERM -- "-$PGID" 2>/dev/null || true
            else
                log "Stopping stock trading (PID: $PID)"
                kill "$PID" 2>/dev/null || true
            fi
            sleep 5
            if [ -n "${PGID:-}" ]; then
                if pgrep -g "$PGID" > /dev/null 2>&1; then
                    kill -KILL -- "-$PGID" 2>/dev/null || true
                    log "Force killed process group (SIGKILL, PGID: $PGID)"
                else
                    log "Graceful shutdown completed"
                fi
            else
                if kill -0 "$PID" 2>/dev/null; then
                    kill -9 "$PID" 2>/dev/null || true
                    log "Force killed (SIGKILL)"
                else
                    log "Graceful shutdown completed"
                fi
            fi
            rm -f "$PID_FILE"
            log "Stock trading stopped"
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
    fi
    DETECTED_PID=$(detect_running_pid)
    if [ -n "$DETECTED_PID" ]; then
        echo "Running (PID: $DETECTED_PID, missing PID file)"
        exit 0
    fi
    echo "Not running"
    exit 1
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
