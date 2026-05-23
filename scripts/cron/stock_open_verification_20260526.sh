#!/usr/bin/env bash
# One-shot stock paper verification after the 2026-05-26 market open.

set -euo pipefail

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/stock_open_verification_20260526.log"
CRON_BEGIN="# BEGIN STOCK_OPEN_VERIFICATION_20260526"
CRON_END="# END STOCK_OPEN_VERIFICATION_20260526"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" | tee -a "$LOG_FILE"
}

remove_cron_block() {
    local tmp
    tmp="$(mktemp)"
    if crontab -l > "$tmp" 2>/dev/null; then
        awk -v begin="$CRON_BEGIN" -v end="$CRON_END" '
            $0 == begin {skip=1; next}
            $0 == end {skip=0; next}
            skip != 1 {print}
        ' "$tmp" | crontab -
    fi
    rm -f "$tmp"
}

trap remove_cron_block EXIT

cd "$PROJECT_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

log "=== stock open verification start ==="
log "Ensuring stock paper runtime is started"
set +e
scripts/cron/stock_trading.sh start >> "$LOG_FILE" 2>&1
start_rc=$?
scripts/cron/stock_trading.sh status >> "$LOG_FILE" 2>&1
status_rc=$?
set -e
log "stock_trading start_rc=$start_rc status_rc=$status_rc"

log "Redis runtime snapshot before verifier"
.venv/bin/python - <<'PY' >> "$LOG_FILE" 2>&1
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import redis

r = redis.Redis.from_url("redis://localhost:6379/1", decode_responses=True)
status = r.hgetall("trading:stock:status") or {}
provider = {}
raw_provider = status.get("data_provider")
if raw_provider:
    try:
        provider = json.loads(raw_provider)
    except json.JSONDecodeError:
        provider = {}
total = int(provider.get("total_symbols") or 0)
fresh = int(provider.get("fresh_count") or 0)
fresh_ratio = fresh / total if total else None
daily = json.loads(r.get("system:daily_indicators:latest") or "{}")
watch = json.loads(r.get("system:daily_watchlist:latest") or "{}")
llm = json.loads(r.get("system:llm_quality:latest") or "{}")
signals = r.lrange("trading:stock:signals", 0, 199) or []
today = datetime.now(ZoneInfo("Asia/Seoul")).date()
today_signals = 0
for raw in signals:
    try:
        item = json.loads(raw)
        ts = datetime.fromisoformat(str(item.get("timestamp", "")).replace("Z", "+00:00"))
        if ts.astimezone(ZoneInfo("Asia/Seoul")).date() == today:
            today_signals += 1
    except (TypeError, ValueError, json.JSONDecodeError):
        continue
print(json.dumps({
    "state": status.get("state"),
    "updated_at": status.get("updated_at"),
    "publisher_pid": status.get("publisher_pid"),
    "fresh_count": fresh,
    "total_symbols": total,
    "fresh_ratio": fresh_ratio,
    "open_positions": r.hlen("trading:stock:positions"),
    "today_signals": today_signals,
    "daily_indicator_count": len(daily.get("indicators") or {}),
    "daily_strategy_counts": daily.get("strategy_counts") or watch.get("strategy_counts") or {},
    "llm_final_codes": llm.get("final_codes") or [],
}, ensure_ascii=False, indent=2))
PY

log "Running stock paper verifier"
set +e
.venv/bin/python scripts/analysis/stock_paper_daily_verification.py \
    --date 2026-05-26 \
    --no-telegram \
    --print-json >> "$LOG_FILE" 2>&1
verify_rc=$?
set -e
log "verifier_rc=$verify_rc (0=PASS, 1=WARN/FAIL gate, 2=script error)"
log "report_json=$PROJECT_DIR/reports/daily_verification/stock/2026-05-26.json"
log "report_markdown=$PROJECT_DIR/reports/daily_verification/stock/2026-05-26.md"
log "=== stock open verification done ==="

exit "$verify_rc"
