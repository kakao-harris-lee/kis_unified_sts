#!/usr/bin/env bash
# Futures cutover rollback (F-9): stop decoupled futures services and restore
# the monolithic trader-futures path. Safe default: dry-run only.
#
#   COMPOSE_ENV_FILE=/home/deploy/project/kis_unified_sts/.env.paper \
#     bash scripts/ops/futures_cutover_rollback.sh
#
# To actually run commands and edit the env file:
#
#   bash scripts/ops/futures_cutover_rollback.sh --execute --confirm
#
# Without both --execute and --confirm, this helper only prints planned actions.
set -euo pipefail

DRY_RUN=1
CONFIRM=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ops/futures_cutover_rollback.sh [--dry-run] [--execute --confirm]

Default is --dry-run. --execute requires --confirm and will:
  1. stop decoupled futures compose services
  2. set FUTURES_ORCHESTRATOR_ENABLED=true in the compose env file
  3. restore safe futures pipeline env knobs to shadow/paper/PAPER
  4. start trader-futures through the trading profile
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --execute)
      DRY_RUN=0
      ;;
    --confirm)
      CONFIRM=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$DRY_RUN" -eq 0 && "$CONFIRM" -ne 1 ]]; then
  echo "ERROR: --execute requires --confirm; rerun with both after reviewing dry-run output." >&2
  exit 2
fi

REPO="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-${FUTURES_ENV_FILE:-${REPO}/.env.paper}}"
PIPELINE_SERVICES=(
  futures-market-ingest
  futures-decision-engine
  futures-risk-filter
  futures-order-router
  futures-monitor
  futures-kill-switch
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

set_env_key() {
  local key="$1"
  local value="$2"

  if [[ ! -f "$COMPOSE_ENV_FILE" ]]; then
    echo "WARN: env file not found: ${COMPOSE_ENV_FILE}; set ${key}=${value} manually"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: set ${key}=${value} in ${COMPOSE_ENV_FILE}"
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { done=0 }
    $0 ~ "^" key "=" {
      print key "=" value
      done=1
      next
    }
    { print }
    END {
      if (done == 0) {
        print key "=" value
      }
    }
  ' "$COMPOSE_ENV_FILE" > "$tmp"
  cp "$tmp" "$COMPOSE_ENV_FILE"
  rm -f "$tmp"
}

echo "== F-9 rollback: decoupled futures pipeline -> trader-futures =="
echo "repo=${REPO}"
echo "compose_env=${COMPOSE_ENV_FILE}"
echo "dry_run=${DRY_RUN}"

# 1. Stop decoupled futures services so the orchestrator can resume ownership.
compose stop "${PIPELINE_SERVICES[@]}" || true

# 2. Re-enable the monolithic futures path and restore safe pipeline defaults.
set_env_key FUTURES_ORCHESTRATOR_ENABLED true
set_env_key FUTURES_PIPELINE_MODE shadow
set_env_key FUTURES_ORDER_ROUTER_MODE paper
set_env_key FUTURES_EXECUTOR_TRADING_MODE PAPER

# 3. Live rollback still needs the operator to disable the live guard in the
# live environment. Do not guess the live Redis topology from this helper.
echo "NOTE: for live rollback, also disable config/futures_live.yaml::enabled or set futures:live:suspended in live Redis DB 1"
echo "NOTE: clear any kill-switch sentinel only after the operator confirms the trip is resolved"

# 4. Restart the compose-managed monolithic futures trading loop.
compose --profile trading up -d trader-futures

# 5. Show restored service status.
compose --profile trading ps trader-futures

echo "== rollback plan complete (dry-run=${DRY_RUN}) =="
