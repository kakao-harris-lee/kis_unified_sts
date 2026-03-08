#!/bin/bash
# RL Retraining Pipeline - kis_unified_sts
# Automated champion/challenger retraining with model promotion.
# Trains a new RL model, evaluates against current champion, and promotes if thresholds met.
#
# crontab: 0 22 * * 0 /home/deploy/project/kis_unified_sts/scripts/cron/rl_retraining_pipeline.sh
#
# Usage:
#   ./scripts/cron/rl_retraining_pipeline.sh              # run (default)
#   ./scripts/cron/rl_retraining_pipeline.sh status       # lock/process status
#   RL_RETRAIN_CONFIG=ml/retraining_pipeline.yaml ./scripts/cron/rl_retraining_pipeline.sh
#   RL_RETRAIN_DRY_RUN=true ./scripts/cron/rl_retraining_pipeline.sh  # evaluation only

set -euo pipefail

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/rl_retraining_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOCK_FILE="$PROJECT_DIR/pids/rl_retraining.lock"

CONFIG="${RL_RETRAIN_CONFIG:-ml/retraining_pipeline.yaml}"
DRY_RUN="${RL_RETRAIN_DRY_RUN:-false}"
FORCE="${RL_RETRAIN_FORCE:-false}"
TIMEOUT_VALUE="${RL_RETRAIN_TIMEOUT:-12h}"

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
    if [ ! -f "$PROJECT_DIR/config/$CONFIG" ]; then
        log "Config file not found: config/$CONFIG"
        exit 1
    fi
}

run_retraining() {
    if is_locked_running; then
        local old_pid
        old_pid=$(cat "$LOCK_FILE")
        log "Previous run still active (PID: $old_pid). Skipping."
        exit 0
    fi

    log "=== RL Retraining Pipeline Start ==="
    log "config=$CONFIG dry_run=$DRY_RUN force=$FORCE timeout=$TIMEOUT_VALUE"

    cd "$PROJECT_DIR"
    source "$VENV"

    # Load env vars from .env (ClickHouse, Redis, MLflow, Telegram, etc.)
    set -a
    source .env
    set +a

    # Skip holidays/weekends (retraining is typically weekly).
    IS_TRADING_DAY=$(python3 -c "
from datetime import date
from shared.collector.historical.calendar import is_trading_day
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "0")

    if [ "$IS_TRADING_DAY" != "1" ]; then
        log "Not a trading day. Skipping RL retraining pipeline."
        exit 0
    fi

    echo $$ > "$LOCK_FILE"
    trap cleanup_lock EXIT

    # Build command args
    CMD="sts rl retrain --config $CONFIG"
    if [ "$DRY_RUN" = "true" ]; then
        CMD="$CMD --dry-run"
        log "Running in DRY RUN mode (evaluation only, no promotion)"
    fi
    if [ "$FORCE" = "true" ]; then
        CMD="$CMD --force"
        log "Running in FORCE mode (skip threshold validation)"
    fi

    local rc
    if command -v timeout >/dev/null 2>&1; then
        set +e
        timeout --signal=TERM --kill-after=60s "$TIMEOUT_VALUE" \
            $CMD >> "$LOG_FILE" 2>&1
        rc=$?
        set -e
    else
        set +e
        $CMD >> "$LOG_FILE" 2>&1
        rc=$?
        set -e
    fi

    if [ "$rc" -eq 0 ]; then
        log "RL retraining pipeline completed successfully."
    elif [ "$rc" -eq 124 ]; then
        log "RL retraining pipeline timed out after $TIMEOUT_VALUE."
        exit 1
    else
        log "RL retraining pipeline failed (exit code: $rc)."
        exit "$rc"
    fi

    log "=== RL Retraining Pipeline Complete ==="
}

validate_inputs

case "${1:-run}" in
    run)
        run_retraining
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 [run|status]"
        exit 1
        ;;
esac
