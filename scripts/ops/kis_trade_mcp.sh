#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

KIS_MCP_REPO_DIR="${KIS_MCP_REPO_DIR:-${HOME}/.local/share/kis-mcp/open-trading-api}"
KIS_TRADE_MCP_DIR="${KIS_TRADE_MCP_DIR:-${KIS_MCP_REPO_DIR}/MCP/Kis Trading MCP}"
KIS_TRADE_MCP_IMAGE="${KIS_TRADE_MCP_IMAGE:-kis-trade-mcp:latest}"
KIS_TRADE_MCP_CONTAINER="${KIS_TRADE_MCP_CONTAINER:-kis-trade-mcp}"
KIS_TRADE_MCP_PORT="${KIS_TRADE_MCP_PORT:-3101}"
KIS_TRADE_MCP_ENV_FILE="${KIS_TRADE_MCP_ENV_FILE:-${REPO_ROOT}/.env}"

usage() {
  cat <<'EOF'
Usage: scripts/ops/kis_trade_mcp.sh <build|start|stop|restart|status|logs>

Environment overrides:
  KIS_MCP_REPO_DIR          Official open-trading-api checkout path
  KIS_TRADE_MCP_PORT       Host port for SSE, default 3101
  KIS_TRADE_MCP_ENV_FILE   Env file to load, default repo .env
EOF
}

load_repo_env() {
  if [[ -f "${KIS_TRADE_MCP_ENV_FILE}" ]]; then
    set +u
    set -a
    # shellcheck disable=SC1090
    source "${KIS_TRADE_MCP_ENV_FILE}"
    set +a
    set -u
  fi
}

account_prefix() {
  local value="${1:-}"
  value="${value%%-*}"
  printf '%s' "${value}"
}

account_product() {
  local value="${1:-}"
  if [[ "${value}" == *-* ]]; then
    printf '%s' "${value##*-}"
  else
    printf '%s' ""
  fi
}

require_nonempty() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    echo "Missing required environment value: ${name}" >&2
    exit 2
  fi
}

ensure_checkout() {
  if [[ ! -d "${KIS_TRADE_MCP_DIR}" ]]; then
    cat >&2 <<EOF
KIS Trade MCP checkout not found:
  ${KIS_TRADE_MCP_DIR}

Clone the official repository first:
  git clone https://github.com/koreainvestment/open-trading-api.git "${KIS_MCP_REPO_DIR}"
EOF
    exit 2
  fi
}

apply_trade_mcp_compat_patch() {
  local pyproject="${KIS_TRADE_MCP_DIR}/pyproject.toml"
  if [[ -f "${pyproject}" ]] && grep -q '"fastmcp>=2.11.2",' "${pyproject}"; then
    sed -i 's/"fastmcp>=2.11.2",/"fastmcp>=2.11.2,<3",/' "${pyproject}"
  fi
}

build_image() {
  ensure_checkout
  apply_trade_mcp_compat_patch
  docker build -t "${KIS_TRADE_MCP_IMAGE}" "${KIS_TRADE_MCP_DIR}"
}

start_container() {
  ensure_checkout
  load_repo_env

  local stock_account="${KIS_STOCK_ACCOUNT_NO:-${KIS_ACCOUNT_NO:-}}"
  local futures_account="${KIS_FUTURES_ACCOUNT_NO:-${stock_account}}"
  local stock_prefix
  local futures_prefix
  local product_code

  stock_prefix="$(account_prefix "${stock_account}")"
  futures_prefix="$(account_prefix "${futures_account}")"
  product_code="${KIS_PROD_TYPE:-${KIS_ACCOUNT_PRODUCT_CODE:-$(account_product "${stock_account}")}}"
  product_code="${product_code:-01}"

  local app_key="${KIS_APP_KEY:-${KIS_STOCK_APP_KEY:-}}"
  local app_secret="${KIS_APP_SECRET:-${KIS_STOCK_APP_SECRET:-}}"
  local paper_app_key="${KIS_PAPER_APP_KEY:-${KIS_STOCK_PAPER_APP_KEY:-${app_key}}}"
  local paper_app_secret="${KIS_PAPER_APP_SECRET:-${KIS_STOCK_PAPER_APP_SECRET:-${app_secret}}}"
  local paper_stock="${KIS_PAPER_STOCK:-${stock_prefix}}"
  local paper_future="${KIS_PAPER_FUTURE:-${futures_prefix}}"

  require_nonempty "KIS_APP_KEY or KIS_STOCK_APP_KEY" "${app_key}"
  require_nonempty "KIS_APP_SECRET or KIS_STOCK_APP_SECRET" "${app_secret}"
  require_nonempty "KIS_STOCK_ACCOUNT_NO or KIS_ACCOUNT_NO" "${stock_prefix}"

  if ! docker image inspect "${KIS_TRADE_MCP_IMAGE}" >/dev/null 2>&1; then
    build_image
  fi

  docker rm -f "${KIS_TRADE_MCP_CONTAINER}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${KIS_TRADE_MCP_CONTAINER}" \
    -p "127.0.0.1:${KIS_TRADE_MCP_PORT}:3000" \
    -e KIS_APP_KEY="${app_key}" \
    -e KIS_APP_SECRET="${app_secret}" \
    -e KIS_PAPER_APP_KEY="${paper_app_key}" \
    -e KIS_PAPER_APP_SECRET="${paper_app_secret}" \
    -e KIS_HTS_ID="${KIS_HTS_ID:-}" \
    -e KIS_ACCT_STOCK="${stock_prefix}" \
    -e KIS_ACCT_FUTURE="${futures_prefix}" \
    -e KIS_PAPER_STOCK="${paper_stock}" \
    -e KIS_PAPER_FUTURE="${paper_future}" \
    -e KIS_PROD_TYPE="${product_code}" \
    "${KIS_TRADE_MCP_IMAGE}"
}

stop_container() {
  docker rm -f "${KIS_TRADE_MCP_CONTAINER}" >/dev/null 2>&1 || true
}

status_container() {
  local headers
  local curl_status
  headers="$(mktemp)"
  trap 'rm -f "${headers}"' RETURN

  docker ps --filter "name=${KIS_TRADE_MCP_CONTAINER}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  echo
  set +e
  curl --max-time 3 -fsS -D "${headers}" "http://127.0.0.1:${KIS_TRADE_MCP_PORT}/sse" >/dev/null 2>&1
  curl_status=$?
  set -e

  if grep -qE '^HTTP/[0-9.]+ 200' "${headers}" || [[ "${curl_status}" == "0" ]]; then
    echo "SSE endpoint reachable: http://127.0.0.1:${KIS_TRADE_MCP_PORT}/sse"
  else
    echo "SSE endpoint not reachable: http://127.0.0.1:${KIS_TRADE_MCP_PORT}/sse"
  fi
}

case "${1:-}" in
  build)
    build_image
    ;;
  start)
    start_container
    ;;
  stop)
    stop_container
    ;;
  restart)
    stop_container
    start_container
    ;;
  status)
    status_container
    ;;
  logs)
    docker logs --tail "${KIS_TRADE_MCP_LOG_LINES:-120}" "${KIS_TRADE_MCP_CONTAINER}"
    ;;
  *)
    usage
    exit 2
    ;;
esac
