#!/usr/bin/env bash
# Stock cutover rollback (M5d): stop the compose-managed decoupled stock
# pipeline and restore the monolithic compose `trader` service. Idempotent.
#
#   COMPOSE_ENV_FILE=/home/deploy/project/kis_unified_sts/.env.paper \
#     bash scripts/ops/stock_cutover_rollback.sh [--dry-run]
#
# --dry-run echoes every mutating command WITHOUT executing it.
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

REPO="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-${STOCK_ENV_FILE:-${REPO}/.env}}"
PIPELINE_SERVICES=(
  stock-market-ingest
  stock-strategy
  stock-risk-filter
  stock-order-router
  stock-exit
  stock-monitor
)

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: $*"
  else
    echo "RUN: $*"
    "$@"
  fi
}

compose() {
  run docker compose --env-file "$COMPOSE_ENV_FILE" "$@"
}

set_stock_orchestrator_enabled() {
  if [[ ! -f "$COMPOSE_ENV_FILE" ]]; then
    echo "WARN: env file not found: ${COMPOSE_ENV_FILE}; set STOCK_ORCHESTRATOR_ENABLED=true manually"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: set STOCK_ORCHESTRATOR_ENABLED=true in ${COMPOSE_ENV_FILE}"
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
  ' "$COMPOSE_ENV_FILE" > "$tmp"
  cp "$tmp" "$COMPOSE_ENV_FILE"
  rm -f "$tmp"
}

echo "== M5d rollback: compose stock pipeline -> compose trader =="
echo "repo=${REPO}"
echo "compose_env=${COMPOSE_ENV_FILE}"

# 1. Stop decoupled stock services. This also stops stock-market-ingest so the
# restored monolithic trader can own the KIS stock WebSocket feed again.
compose stop "${PIPELINE_SERVICES[@]}" || true

# 2. Re-allow the monolithic stock path before starting trader.
set_stock_orchestrator_enabled

# 3. Abandon decoupled live paper positions and clear the live dashboard snapshot.
compose exec -T redis sh -c \
  'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -n 1 del stock:daemon:positions trading:stock:positions'

# 4. Restore the orchestrator/trader's LLM context publisher.
echo "NOTE: re-enable config/llm.yaml::market_context_publisher.enabled: true"
echo "NOTE: revert the M5b cron entry STOCK_LLM_CONTEXT=live back to =shadow"

# 5. Restart the compose-managed monolithic trading loop.
compose --profile trading up -d trader

# 6. Show service status.
compose --profile trading ps trader

echo "== rollback complete (dry-run=${DRY_RUN}) =="
