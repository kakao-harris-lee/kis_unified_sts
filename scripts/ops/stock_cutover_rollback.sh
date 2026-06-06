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
ENV_FILE="${STOCK_ENV_FILE:-${REPO}/.env}"
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

set_stock_orchestrator_enabled() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "WARN: env file not found: ${ENV_FILE}; set STOCK_ORCHESTRATOR_ENABLED=true manually"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: set STOCK_ORCHESTRATOR_ENABLED=true in ${ENV_FILE}"
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  awk '
    BEGIN { done=0 }
    /^STOCK_ORCHESTRATOR_ENABLED=/ {
      print "STOCK_ORCHESTRATOR_ENABLED=true"
      done=1
      next
    }
    { print }
    END {
      if (done == 0) {
        print "STOCK_ORCHESTRATOR_ENABLED=true"
      }
    }
  ' "$ENV_FILE" > "$tmp"
  cp "$tmp" "$ENV_FILE"
  rm -f "$tmp"
}

echo "== M5d rollback: decoupled stock pipeline -> orchestrator =="

# 1. Stop the decoupled daemons (idempotent; ignore not-loaded units).
for unit in "${UNITS[@]}"; do
  run systemctl stop "${unit}.service" || true
done

# 2. Disable decoupled daemon units and remove live-mode drop-ins so they do not
# resurrect on reboot while the orchestrator is restored.
for unit in "${UNITS[@]}"; do
  run systemctl disable "${unit}.service" || true
  run rm -f "/etc/systemd/system/${unit}.service.d/live.conf" || true
done
run systemctl daemon-reload

# 3. Re-allow the monolithic stock orchestrator before invoking its cron wrapper.
set_stock_orchestrator_enabled

# 4. Abandon decoupled live paper positions and clear the dashboard live snapshot.
run redis-cli -n "$REDIS_DB" del stock:daemon:positions trading:stock:positions

# 5. Restore the orchestrator's LLM context publisher (it owns it again).
echo "NOTE: re-enable config/llm.yaml::market_context_publisher.enabled: true"
echo "NOTE: revert the M5b crontab entry STOCK_LLM_CONTEXT=live back to =shadow"
echo "NOTE: re-enable the stock_trading.sh + watchdog crontab lines if they were commented out"

# 6. Restart the orchestrator stock process.
run bash "${REPO}/scripts/cron/stock_trading.sh" start

# 7. Verify the orchestrator came up.
if [[ "$DRY_RUN" -eq 0 ]]; then
  sleep 2
  if [[ -f "${REPO}/pids/stock_trading.pid" ]] && kill -0 "$(cat "${REPO}/pids/stock_trading.pid")" 2>/dev/null; then
    echo "OK: orchestrator stock process is up (pid $(cat "${REPO}/pids/stock_trading.pid"))"
  else
    echo "WARN: orchestrator pid not found/alive — check scripts/cron/stock_trading.sh logs"
  fi
fi

echo "== rollback complete (dry-run=${DRY_RUN}) =="
