#!/bin/bash
# Phase D Day-1 verification — runs ~1h35m after orchestrator start (10:30 KST).
# Self-removes from crontab after one execution.
set -uo pipefail

PROJECT_DIR="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
cd "$PROJECT_DIR"
# shellcheck disable=SC1091
set -a && source "$PROJECT_DIR/.env" && set +a

KST_NOW=$(TZ=Asia/Seoul date +"%Y-%m-%d %H:%M:%S %Z")
LOG="$PROJECT_DIR/logs/phase_d_day1_$(date +%Y%m%d).log"
exec >>"$LOG" 2>&1
echo "=== Phase D Day-1 check @ $KST_NOW ==="

ch() {
  clickhouse-client --password="$CLICKHOUSE_PASSWORD" --database=kospi -q "$1"
}

forecast_today=$(ch "SELECT count() FROM vol_forecasts WHERE asof >= toStartOfDay(now())" || echo "?")
setup_c_trades=$(ch "SELECT count() FROM rl_trades WHERE strategy='setup_c_event_reaction' AND toDate(entry_date)=today()" || echo "?")
# exit_date is DateTime (not nullable) — open positions sentinel-encoded as 1970-01-01 (toUnixTimestamp(exit_date)=0).
setup_c_open=$(ch "SELECT count() FROM rl_trades WHERE strategy='setup_c_event_reaction' AND toDate(entry_date)=today() AND toUnixTimestamp(exit_date)=0" 2>/dev/null || echo "?")
har_rv_today=$(ch "SELECT count() FROM har_rv_fits WHERE fit_date=today()" || echo "?")
event_scores_24h=$(ch "SELECT count() FROM event_scores WHERE asof >= now() - INTERVAL 24 HOUR" 2>/dev/null || echo "?")

# Live forecast freshness (age in seconds)
forecast_age=$(redis-cli -n 1 GET forecast:vol:current 2>/dev/null \
  | python3 -c "
import json, sys
from datetime import datetime, timezone
try:
    d = json.loads(sys.stdin.read())
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(d['asof'])).total_seconds()
    print(int(age))
except Exception:
    print('?')
" || echo "?")

container_status=$(docker ps --filter name=kis-forecasting --format "{{.Status}}" 2>/dev/null || echo "?")

REPORT=$(cat <<EOF
Phase D Day-1 Check ($KST_NOW)

forecast publishes today: $forecast_today  (target >= 200, expect ~390)
HAR-RV fits today:        $har_rv_today    (target >= 1)
Setup C trades today:     $setup_c_trades  (signal == anything > 0)
Setup C open positions:   $setup_c_open
Event scores last 24h:    $event_scores_24h
Live forecast age:        ${forecast_age}s (target < 180)
Container:                $container_status
EOF
)

echo "$REPORT"

# Telegram briefing
if [ -n "${TELEGRAM_BRIEFING_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_BRIEFING_CHAT_ID:-}" ]; then
  curl -fsS -X POST \
    "https://api.telegram.org/bot${TELEGRAM_BRIEFING_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_BRIEFING_CHAT_ID}" \
    --data-urlencode "text=${REPORT}" \
    >/dev/null || echo "Telegram send failed"
fi

# Self-remove from crontab
crontab -l 2>/dev/null | grep -v "phase_d_day1_check" | crontab -
echo "=== Self-removed from crontab ==="
