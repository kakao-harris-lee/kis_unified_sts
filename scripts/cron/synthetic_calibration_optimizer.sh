#!/bin/bash
# Synthetic Calibration Optimizer - kis_unified_sts
# Runs multi-iteration synthetic calibration optimization and writes a markdown summary.
#
# Example crontab:
#   30 21 * * 6 /home/deploy/project/kis_unified_sts/scripts/cron/synthetic_calibration_optimizer.sh

set -euo pipefail

PROJECT_DIR="${SYNTH_CAL_PROJECT_DIR:-/home/deploy/project/kis_unified_sts}"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/synthetic_calibration_optimizer_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOCK_FILE="$PROJECT_DIR/pids/synthetic_calibration_optimizer.lock"

OUTPUT_ROOT="${SYNTH_CAL_OUTPUT_ROOT:-artifacts/datasets/calibration/optimizer_run}"
MAX_ITERATIONS="${SYNTH_CAL_MAX_ITERATIONS:-3}"
PATIENCE="${SYNTH_CAL_PATIENCE:-1}"
MIN_IMPROVEMENT="${SYNTH_CAL_MIN_IMPROVEMENT:-1e-6}"
TIMEOUT_VALUE="${SYNTH_CAL_TIMEOUT:-6h}"

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

run_optimizer() {
    if is_locked_running; then
        local old_pid
        old_pid=$(cat "$LOCK_FILE")
        log "Previous synthetic calibration optimizer run still active (PID: $old_pid). Skipping."
        exit 0
    fi

    log "=== Synthetic Calibration Optimizer Start ==="
    log "output_root=$OUTPUT_ROOT max_iterations=$MAX_ITERATIONS patience=$PATIENCE min_improvement=$MIN_IMPROVEMENT timeout=$TIMEOUT_VALUE"

    cd "$PROJECT_DIR"
    source "$VENV"

    if [ -f .env ]; then
        set -a
        source .env
        set +a
    fi

    echo $$ > "$LOCK_FILE"
    trap cleanup_lock EXIT

    local rc
    if command -v timeout >/dev/null 2>&1; then
        set +e
        timeout --signal=TERM --kill-after=60s "$TIMEOUT_VALUE" \
            python scripts/training/optimize_synthetic_calibration.py \
                --max-iterations "$MAX_ITERATIONS" \
                --patience "$PATIENCE" \
                --min-improvement "$MIN_IMPROVEMENT" \
                --output-root "$OUTPUT_ROOT" >> "$LOG_FILE" 2>&1
        rc=$?
        set -e
    else
        set +e
        python scripts/training/optimize_synthetic_calibration.py \
            --max-iterations "$MAX_ITERATIONS" \
            --patience "$PATIENCE" \
            --min-improvement "$MIN_IMPROVEMENT" \
            --output-root "$OUTPUT_ROOT" >> "$LOG_FILE" 2>&1
        rc=$?
        set -e
    fi

    if [ "$rc" -ne 0 ]; then
        if [ "$rc" -eq 124 ]; then
            log "Synthetic calibration optimizer timed out after $TIMEOUT_VALUE."
        else
            log "Synthetic calibration optimizer failed (exit code: $rc)."
        fi
        exit "$rc"
    fi

    python scripts/training/summarize_synthetic_calibration.py \
        --manifest "$OUTPUT_ROOT/optimizer_manifest.json" \
        --output "$OUTPUT_ROOT/optimizer_summary.md" >> "$LOG_FILE" 2>&1

    log "Synthetic calibration optimizer completed successfully."
    log "Summary written to $OUTPUT_ROOT/optimizer_summary.md"
    log "=== Synthetic Calibration Optimizer Complete ==="
}

case "${1:-run}" in
    run)
        run_optimizer
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 [run|status]"
        exit 1
        ;;
esac