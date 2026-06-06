#!/usr/bin/env bash
# Stock cutover rollback (M5d): stop the decoupled stock pipeline and restore the
# monolithic orchestrator. Idempotent. Paper-only — no real-money side effects.
#
#   bash scripts/ops/stock_cutover_rollback.sh [--dry-run]
#
# --dry-run echoes every mutating command WITHOUT executing it (operator preview).
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

REPO="/home/deploy/project/kis_unified_sts"
REDIS_DB="${REDIS_DB:-1}"
UNITS=(
  kis-stock-strategy-daemon
  kis-stock-risk-filter
  kis-stock-order-router
  kis-stock-exit-daemon
  kis-stock-monitor-daemon
)

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: $*"
  else
    echo "RUN: $*"
    "$@"
  fi
}

echo "== M5d rollback: decoupled stock pipeline -> orchestrator =="

# 1. Stop the decoupled daemons (idempotent; ignore not-loaded units).
for unit in "${UNITS[@]}"; do
  run systemctl stop "${unit}.service" || true
done

# 2. Abandon decoupled live positions (paper — the data is disposable).
run redis-cli -n "$REDIS_DB" del trading:stock:positions

# 3. Restore the orchestrator's LLM context publisher (it owns it again).
echo "NOTE: re-enable config/llm.yaml::market_context_publisher.enabled: true"
echo "NOTE: revert the M5b crontab entry STOCK_LLM_CONTEXT=live back to =shadow"

# 4. Restart the orchestrator stock process.
run bash "${REPO}/scripts/cron/stock_trading.sh" start

# 5. Verify the orchestrator came up.
if [[ "$DRY_RUN" -eq 0 ]]; then
  sleep 2
  if [[ -f "${REPO}/pids/stock_trading.pid" ]] && kill -0 "$(cat "${REPO}/pids/stock_trading.pid")" 2>/dev/null; then
    echo "OK: orchestrator stock process is up (pid $(cat "${REPO}/pids/stock_trading.pid"))"
  else
    echo "WARN: orchestrator pid not found/alive — check scripts/cron/stock_trading.sh logs"
  fi
fi

echo "== rollback complete (dry-run=${DRY_RUN}) =="
