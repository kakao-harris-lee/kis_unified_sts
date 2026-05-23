#!/bin/bash
# LLM Intraday Refresh - kis_unified_sts
# Lightweight stock scoring to keep Redis LLM quality snapshot fresh.
#
# crontab: 0 9,11,13,15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_intraday.sh

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/llm_intraday_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOCK_FILE="$PROJECT_DIR/pids/llm_intraday.lock"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/pids"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null 2>&1; then
        log "Previous run still active (PID: $OLD_PID). Skipping."
        exit 0
    else
        rm -f "$LOCK_FILE"
    fi
fi

log "=== LLM Intraday Refresh Start ==="

cd "$PROJECT_DIR"
source "$VENV"
set -a && source .env && set +a

echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

python3 -m scripts.analysis.llm_intraday_refresh >> "$LOG_FILE" 2>&1

if [ "${STOCK_LLM_REFRESH_DAILY_INDICATORS:-1}" != "0" ]; then
    LLM_CODES=$(python3 - <<'PY'
import json
from shared.streaming.client import RedisClient

raw = RedisClient.get_client().get("system:llm_quality:latest")
payload = json.loads(raw or "{}")
codes = payload.get("final_codes") or []
print(" ".join(str(code).strip() for code in codes if str(code).strip()))
PY
)
    if [ -n "$LLM_CODES" ]; then
        log "Backfilling daily candles for LLM final codes: $LLM_CODES"
        BACKFILL_ARGS=()
        for code in $LLM_CODES; do
            BACKFILL_ARGS+=("-c" "$code")
        done
        export STOCK_DAILY_MAX_DAYS="${STOCK_LLM_DAILY_MAX_DAYS:-280}"
        sts stock-backfill daily \
            --days "${STOCK_LLM_DAILY_BACKFILL_DAYS:-280}" \
            "${BACKFILL_ARGS[@]}" >> "$LOG_FILE" 2>&1 || \
            log "Daily candle backfill for LLM final codes failed"
    fi
    log "Refreshing daily indicators after LLM quality update..."
    python3 scripts/daily_indicator_scanner.py >> "$LOG_FILE" 2>&1
fi

log "=== LLM Intraday Refresh Complete ==="
