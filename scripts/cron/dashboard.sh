#!/bin/bash
# Dashboard API Service - kis_unified_sts
# Replaces: quant_moment_sts dashboard
#
# crontab: 0 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/dashboard.sh start
# Health check: */5 9-16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/dashboard.sh start

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/dashboard_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
PID_FILE="$PROJECT_DIR/pids/dashboard.pid"
PORT=8000

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_dashboard() {
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            # Check if port is responding
            if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
                log "Dashboard already running and healthy (PID: $OLD_PID)"
                exit 0
            else
                log "Dashboard process exists but not responding, restarting..."
                stop_dashboard
            fi
        else
            rm -f "$PID_FILE"
        fi
    fi

    log "=== Dashboard Start ==="

    cd "$PROJECT_DIR"
    source "$VENV"

    # Start FastAPI with uvicorn
    nohup uvicorn services.api.app:app \
        --host 0.0.0.0 \
        --port $PORT \
        --workers 2 \
        >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    log "Dashboard started (PID: $!, Port: $PORT)"

    # Wait for startup
    sleep 3
    if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
        log "Dashboard health check passed"
    else
        log "Warning: Dashboard may not be fully started yet"
    fi
}

stop_dashboard() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "Stopping dashboard (PID: $PID)"
            kill "$PID" 2>/dev/null || true
            sleep 2
            kill -9 "$PID" 2>/dev/null || true
            rm -f "$PID_FILE"
            log "Dashboard stopped"
        else
            rm -f "$PID_FILE"
            log "Process not running, cleaned up PID file"
        fi
    fi

    # Also kill any orphaned uvicorn processes on our port
    pkill -f "uvicorn.*:$PORT" 2>/dev/null || true
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
                echo "Running and healthy (PID: $PID, Port: $PORT)"
                exit 0
            else
                echo "Running but unhealthy (PID: $PID)"
                exit 1
            fi
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
        start_dashboard
        ;;
    stop)
        stop_dashboard
        ;;
    restart)
        stop_dashboard
        sleep 2
        start_dashboard
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
