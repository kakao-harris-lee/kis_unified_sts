#!/bin/bash
# RL Training Batch - kis_unified_sts
# Runs nightly RL training from ClickHouse 1-minute candles.
#
# crontab: 40 22 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_train.sh
#
# Usage:
#   ./scripts/cron/rl_train.sh              # run (default)
#   ./scripts/cron/rl_train.sh status       # lock/process status
#   RL_TRAIN_ALGO=mppo RL_TRAIN_CONFIG=ml/rl_mppo.yaml ./scripts/cron/rl_train.sh

set -euo pipefail

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/rl_train_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOCK_FILE="$PROJECT_DIR/pids/rl_train.lock"

ALGO="${RL_TRAIN_ALGO:-mppo}"
CONFIG="${RL_TRAIN_CONFIG:-ml/rl_mppo.yaml}"
TIMEOUT_VALUE="${RL_TRAIN_TIMEOUT:-8h}"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cleanup_lock() {
    rm -f "$LOCK_FILE"
}

is_locked_running() {
    if [ ! -f "$LOCK_FILE" ]; then
        return 1
    fi

    local old_pid
    old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")

    if [ -n "$old_pid" ] && ps -p "$old_pid" > /dev/null 2>&1; then
        return 0
    fi

    rm -f "$LOCK_FILE"
    return 1
}

status() {
    if is_locked_running; then
        local pid
        pid=$(cat "$LOCK_FILE")
        echo "Running (PID: $pid)"
        exit 0
    fi
    echo "Not running"
    exit 1
}

validate_inputs() {
    case "$ALGO" in
        mppo|sac|dqn|a2c|ppo|dt|all)
            ;;
        *)
            log "Invalid RL_TRAIN_ALGO: $ALGO"
            exit 1
            ;;
    esac
}

run_training() {
    if is_locked_running; then
        local old_pid
        old_pid=$(cat "$LOCK_FILE")
        log "Previous run still active (PID: $old_pid). Skipping."
        exit 0
    fi

    log "=== RL Training Batch Start ==="
    log "algo=$ALGO config=$CONFIG timeout=$TIMEOUT_VALUE"

    cd "$PROJECT_DIR"
    source "$VENV"

    # Load env vars from .env (ClickHouse, Redis, MLflow, etc.)
    set -a
    source .env
    set +a

    # Skip holidays/weekends.
    IS_TRADING_DAY=$(python3 -c "
from datetime import date
from shared.collector.historical.calendar import is_trading_day
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "0")

    if [ "$IS_TRADING_DAY" != "1" ]; then
        log "Not a trading day. Skipping RL training batch."
        exit 0
    fi

    echo $$ > "$LOCK_FILE"
    trap cleanup_lock EXIT

    local rc
    if command -v timeout >/dev/null 2>&1; then
        set +e
        timeout --signal=TERM --kill-after=60s "$TIMEOUT_VALUE" \
            sts rl train --algo "$ALGO" --config "$CONFIG" >> "$LOG_FILE" 2>&1
        rc=$?
        set -e
    else
        set +e
        sts rl train --algo "$ALGO" --config "$CONFIG" >> "$LOG_FILE" 2>&1
        rc=$?
        set -e
    fi

    if [ "$rc" -eq 0 ]; then
        log "RL training completed successfully."
    elif [ "$rc" -eq 124 ]; then
        log "RL training timed out after $TIMEOUT_VALUE."
        exit 1
    else
        log "RL training failed (exit code: $rc)."
        exit "$rc"
    fi

    log "=== RL Training Batch Complete ==="
}

validate_inputs

case "${1:-run}" in
    run)
        run_training
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 [run|status]"
        exit 1
        ;;
esac
