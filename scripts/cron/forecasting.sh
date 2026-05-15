#!/bin/bash
# Forecasting service control wrapper.
#
# Usage:
#   scripts/cron/forecasting.sh start    # start daemon (idempotent)
#   scripts/cron/forecasting.sh refit    # trigger daily HAR-RV refit
#   scripts/cron/forecasting.sh stop     # stop daemon
#   scripts/cron/forecasting.sh status

set -euo pipefail

PROJECT_DIR="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
LOG_DIR="${KIS_LOG_DIR:-$PROJECT_DIR/logs}"
LOG_FILE="$LOG_DIR/forecasting_$(date +%Y%m%d).log"
PID_FILE="$PROJECT_DIR/pids/forecasting.pid"

mkdir -p "$LOG_DIR" "$(dirname "$PID_FILE")"

# Load .env so cron-spawned runs see CLICKHOUSE_*, REDIS_*, OPENAI_API_KEY etc.
# Without this the host fallback path (.venv/bin/python refit_har_rv.py) hits
# ClickHouse with empty CLICKHOUSE_PASSWORD → "Authentication failed" (Code 516)
# and HAR-RV refit silently fails every trading day.
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# Idempotent — uses container state. The legacy PID_FILE held a docker
# container ID (not a process PID), so the `kill -0` check always failed and
# every invocation re-ran `docker-compose up`. Querying `docker ps` is both
# correct and cheaper.
start_service() {
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -n "$CID" ]; then
    log "Already running (container $CID)"
    echo "$CID" > "$PID_FILE"
    return 0
  fi
  log "Starting kis-forecasting via docker-compose"
  cd "$PROJECT_DIR"
  docker-compose up -d forecasting >> "$LOG_FILE" 2>&1
  sleep 3
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -n "$CID" ]; then
    echo "$CID" > "$PID_FILE"
    log "Started container $CID"
  else
    log "ERROR: container did not start"
    exit 1
  fi
}

refit_service() {
  cd "$PROJECT_DIR"
  log "Running standalone HAR-RV refit"
  # The container shares the same shared/ modules; run the fit in-container so
  # it reads the same config and writes to the same Redis/ClickHouse instances
  # the daemon will read back.
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -n "$CID" ]; then
    docker exec "$CID" python /app/scripts/forecasting/refit_har_rv.py \
      >> "$LOG_FILE" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
      log "ERROR: refit script exited $rc"
      exit "$rc"
    fi
    log "Refit completed — signalling daemon to reload model"
    docker kill -s SIGUSR1 "$CID" >> "$LOG_FILE" 2>&1
  else
    # No daemon — run via venv on host so the cron job still produces a model
    # in Redis/ClickHouse. Daemon will load it on next start.
    "$PROJECT_DIR/.venv/bin/python" \
      "$PROJECT_DIR/scripts/forecasting/refit_har_rv.py" >> "$LOG_FILE" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
      log "ERROR: host refit script exited $rc"
      exit "$rc"
    fi
    log "Refit completed (daemon offline — model saved to Redis)"
  fi
}

stop_service() {
  log "Stopping kis-forecasting"
  cd "$PROJECT_DIR"
  docker-compose stop forecasting >> "$LOG_FILE" 2>&1
  rm -f "$PID_FILE"
}

status_service() {
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -n "$CID" ]; then
    echo "Running ($CID)"
    docker inspect --format='{{.State.Health.Status}}' "$CID" 2>/dev/null || true
  else
    echo "Not running"
  fi
}

case "${1:-status}" in
  start)  start_service ;;
  refit)  refit_service ;;
  stop)   stop_service ;;
  status) status_service ;;
  *)      echo "Usage: $0 {start|refit|stop|status}"; exit 1 ;;
esac
