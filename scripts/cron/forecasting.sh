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

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

start_service() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    log "Already running (PID $(cat "$PID_FILE"))"
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
  log "Triggering HAR-RV refit (signal SIGUSR1 to container)"
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -z "$CID" ]; then
    log "ERROR: container not running; cannot refit"
    exit 1
  fi
  # Service main listens for SIGUSR1 to refit immediately
  docker kill -s SIGUSR1 "$CID" >> "$LOG_FILE" 2>&1
  log "Refit signal sent"
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
