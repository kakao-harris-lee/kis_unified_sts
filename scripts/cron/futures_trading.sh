#!/bin/bash
# ============================================================
# DEPRECATED (2026-02-12)
# 선물 거래는 RL Paper Trader (rl_paper.sh)로 완전 전환됨.
# 이 스크립트는 더 이상 crontab에서 호출되지 않음.
# 재사용 금지: 모든 futures 전략 YAML이 enabled: false 처리됨.
# 선물 거래: rl_paper.sh (MaskablePPO, sts rl paper --no-daemon)
# ============================================================
#
# [Legacy] Futures Trading Service - kis_unified_sts
# Replaces: kospi_mini_sts paper_trading_service.py
#
# crontab (DISABLED):
#   50 8 * * 1-5 futures_trading.sh start
#   0 16 * * 1-5 futures_trading.sh stop

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/futures_trading_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
PID_FILE="$PROJECT_DIR/pids/futures_trading.pid"

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

    log "=== Futures Trading Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"

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

    log "Trading day confirmed. Starting futures trading..."

    # Start trading via CLI (paper trading, single session)
    # --single mode means it will run for today only and stop at market close
    nohup sts trade start \
        --asset futures \
        --capital 50000000 \
        --paper \
        --single \
        >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    log "Futures trading started (PID: $!)"
}

stop_trading() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "Stopping futures trading (PID: $PID)"
            kill "$PID" 2>/dev/null || true
            sleep 5
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null || true
                log "Force killed (SIGKILL)"
            else
                log "Graceful shutdown completed"
            fi
            rm -f "$PID_FILE"
            log "Futures trading stopped"
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
