#!/bin/bash
# RL Paper Trading Service - kis_unified_sts
# 기본 동작: RL profile matrix paper trading (장중 후보 비교)
# fallback: single profile rl paper 실행
#
# crontab: 55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh start
#          40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh stop

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/rl_paper_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
PID_FILE="$PROJECT_DIR/pids/rl_paper.pid"
MATRIX_RUN_DIR_FILE="$PROJECT_DIR/pids/rl_paper_matrix_run_dir.txt"
PROC_PATTERN_STS="/home/deploy/project/kis_unified_sts/.venv/bin/sts rl paper"
PROC_PATTERN_MATRIX="/home/deploy/project/kis_unified_sts/.venv/bin/python /home/deploy/project/kis_unified_sts/scripts/analysis/rl_paper_profile_matrix.py"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

detect_running_pid() {
    pgrep -f "$PROC_PATTERN_MATRIX" 2>/dev/null | head -n 1 || \
        pgrep -f "$PROC_PATTERN_STS" 2>/dev/null | head -n 1 || true
}

get_process_group_id() {
    local pid="$1"
    ps -o pgid= -p "$pid" 2>/dev/null | tr -d '[:space:]'
}

cleanup_orphan_children() {
    # Matrix parent가 먼저 종료되어도 timeout/sts 자식이 남는 경우가 있어 정리한다.
    pkill -TERM -f "$PROC_PATTERN_STS" 2>/dev/null || true
    pkill -TERM -f "timeout --signal=TERM --kill-after .* $PROJECT_DIR/.venv/bin/sts rl paper" 2>/dev/null || true
    sleep 1
    pkill -KILL -f "$PROC_PATTERN_STS" 2>/dev/null || true
    pkill -KILL -f "timeout --signal=TERM --kill-after .* $PROJECT_DIR/.venv/bin/sts rl paper" 2>/dev/null || true
}

run_matrix_post_analysis() {
    # Ensure DB/Redis credentials are available for post-analysis scripts.
    if [ -f "$PROJECT_DIR/.env" ]; then
        set -a
        source "$PROJECT_DIR/.env"
        set +a
    fi

    if [ ! -f "$MATRIX_RUN_DIR_FILE" ]; then
        return
    fi

    RUN_DIR=$(cat "$MATRIX_RUN_DIR_FILE" 2>/dev/null || true)
    rm -f "$MATRIX_RUN_DIR_FILE"

    if [ -z "$RUN_DIR" ] || [ ! -d "$RUN_DIR" ]; then
        log "Matrix run directory not found. Skip post-market summary."
        return
    fi

    LOGS=$(ls -1 "$RUN_DIR"/*.log 2>/dev/null | paste -sd, - || true)
    if [ -z "$LOGS" ]; then
        log "No matrix logs found in $RUN_DIR. Skip post-market summary."
        return
    fi

    log "Generating post-market matrix summary from $RUN_DIR"
    if "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/analysis/rl_paper_profile_matrix.py" \
        --analyze-only \
        --logs "$LOGS" \
        --output-dir "$RUN_DIR" >> "$LOG_FILE" 2>&1; then
        SUMMARY_CSV=$(ls -1t "$RUN_DIR"/paper_profile_matrix_summary_*.csv 2>/dev/null | head -n 1 || true)
        SUMMARY_JSON=$(ls -1t "$RUN_DIR"/paper_profile_matrix_summary_*.json 2>/dev/null | head -n 1 || true)
        [ -n "$SUMMARY_CSV" ] && log "Matrix summary CSV: $SUMMARY_CSV"
        [ -n "$SUMMARY_JSON" ] && log "Matrix summary JSON: $SUMMARY_JSON"
    else
        log "Post-market matrix summary generation failed"
    fi

    log "Generating futures session health report from $RUN_DIR"
    if "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/analysis/futures_session_health_report.py" \
        --date "$(date +%F)" \
        --run-dir "$RUN_DIR" \
        --notify-on-issues \
        --output-dir "$RUN_DIR" >> "$LOG_FILE" 2>&1; then
        HEALTH_JSON=$(ls -1t "$RUN_DIR"/futures_session_health_*.json 2>/dev/null | head -n 1 || true)
        HEALTH_MD=$(ls -1t "$RUN_DIR"/futures_session_health_*.md 2>/dev/null | head -n 1 || true)
        [ -n "$HEALTH_JSON" ] && log "Futures health JSON: $HEALTH_JSON"
        [ -n "$HEALTH_MD" ] && log "Futures health MD: $HEALTH_MD"
    else
        log "Futures session health report generation failed"
    fi
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

    # Force futures metrics endpoint to match Prometheus scrape target.
    # Prevent inherited shell env (e.g. PROMETHEUS_PORT=8080) from hiding RL metrics.
    export PROMETHEUS_PORT="${RL_PAPER_PROMETHEUS_PORT:-9092}"
    log "Prometheus metrics port: $PROMETHEUS_PORT"

    # Matrix mode defaults to disabled (2026-04-14: 30-day PnL audit showed all profile
    # variants net-negative with win rates 3-4% vs baseline 15.9%; matrix was primary
    # noise source. Revert to single rl_mppo until a profile beats baseline).
    RL_PAPER_MATRIX_ENABLED=${RL_PAPER_MATRIX_ENABLED:-0}
    RL_PAPER_MATRIX_MODEL=${RL_PAPER_MATRIX_MODEL:-mppo_best}
    RL_PAPER_MATRIX_PROFILES=${RL_PAPER_MATRIX_PROFILES:-"rl_mppo_spread6,rl_mppo_spread7,rl_mppo_spread8,rl_mppo_profile_asym_long_strict,rl_mppo_profile_uptrend_spike_guard"}
    if [ -z "${RL_PAPER_MATRIX_DURATION_MINUTES:-}" ]; then
        PROFILE_COUNT=$(echo "$RL_PAPER_MATRIX_PROFILES" | awk -F',' '{print NF}')
        NOW_MINUTES=$((10#$(date +%H) * 60 + 10#$(date +%M)))
        # cron stop is 15:40; reserve ~5 minutes for shutdown/summary.
        TARGET_END_MINUTES=$((15 * 60 + 35))
        REMAIN_MINUTES=$((TARGET_END_MINUTES - NOW_MINUTES))
        if [ "$PROFILE_COUNT" -gt 0 ] && [ "$REMAIN_MINUTES" -gt "$PROFILE_COUNT" ]; then
            RL_PAPER_MATRIX_DURATION_MINUTES=$((REMAIN_MINUTES / PROFILE_COUNT))
            if [ "$RL_PAPER_MATRIX_DURATION_MINUTES" -lt 20 ]; then
                RL_PAPER_MATRIX_DURATION_MINUTES=20
            fi
        else
            RL_PAPER_MATRIX_DURATION_MINUTES=75
        fi
    fi
    RL_PAPER_MATRIX_COOLDOWN_SECONDS=${RL_PAPER_MATRIX_COOLDOWN_SECONDS:-8}
    MATRIX_RUN_DIR="$PROJECT_DIR/output/paper_matrix/$(date +%Y%m%d)_session"

    if [ "$RL_PAPER_MATRIX_ENABLED" = "1" ]; then
        mkdir -p "$MATRIX_RUN_DIR"
        echo "$MATRIX_RUN_DIR" > "$MATRIX_RUN_DIR_FILE"
        log "Matrix mode ON: profiles=$RL_PAPER_MATRIX_PROFILES, duration=${RL_PAPER_MATRIX_DURATION_MINUTES}m, model=$RL_PAPER_MATRIX_MODEL"

        # Start matrix runner in detached session.
        setsid bash -c "exec '$PROJECT_DIR/.venv/bin/python' '$PROJECT_DIR/scripts/analysis/rl_paper_profile_matrix.py' \
            --profiles '$RL_PAPER_MATRIX_PROFILES' \
            --model '$RL_PAPER_MATRIX_MODEL' \
            --duration-minutes '$RL_PAPER_MATRIX_DURATION_MINUTES' \
            --cooldown-seconds '$RL_PAPER_MATRIX_COOLDOWN_SECONDS' \
            --output-dir '$PROJECT_DIR/output/paper_matrix' \
            --run-dir '$MATRIX_RUN_DIR'" >> "$LOG_FILE" 2>&1 < /dev/null &
    else
        rm -f "$MATRIX_RUN_DIR_FILE"
        log "Matrix mode OFF: fallback to single rl paper process"
        # Start RL paper trading in a detached session.
        setsid bash -c 'exec sts rl paper --no-daemon' \
            >> "$LOG_FILE" 2>&1 < /dev/null &
    fi

    PID=$!
    echo "$PID" > "$PID_FILE"

    # Early liveness check to avoid stale PID files on immediate startup failure.
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        log "RL paper trading started (PID: $PID)"
    else
        rm -f "$PID_FILE"
        if [ "$RL_PAPER_MATRIX_ENABLED" = "1" ]; then
            rm -f "$MATRIX_RUN_DIR_FILE"
        fi
        log "Failed to start RL paper trading (process exited early)"
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
                log "Stopping RL paper trading (PID: $PID, PGID: $PGID)"
                kill -TERM -- "-$PGID" 2>/dev/null || true
            else
                log "Stopping RL paper trading (PID: $PID)"
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
            cleanup_orphan_children
            rm -f "$PID_FILE"
            run_matrix_post_analysis
            log "RL paper trading stopped"
        else
            rm -f "$PID_FILE"
            cleanup_orphan_children
            log "Process not running, cleaned up PID file"
            run_matrix_post_analysis
        fi
    else
        cleanup_orphan_children
        log "No PID file found"
        run_matrix_post_analysis
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Running (PID: $PID)"
            exit 0
        else
            PID=$(detect_running_pid)
            if [ -n "$PID" ]; then
                echo "$PID" > "$PID_FILE"
                echo "Running (PID: $PID, recovered from stale PID file)"
                exit 0
            fi
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
