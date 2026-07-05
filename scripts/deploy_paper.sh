#!/usr/bin/env bash
# scripts/deploy_paper.sh
# One-shot paper-stack deploy: build -> recreate (never `down`) -> verify -> cleanup.
#
# Why a paper-specific script (vs docker-start.sh): the paper stack MUST run with
#   --env-file .env.paper   (sets COMPOSE_PROJECT_NAME=kis_paper, STOCK_PIPELINE_MODE=live,
#                            REDIS host, real KIS market key). Omitting it silently drops the
#                            pipeline to shadow streams + localhost redis.
# and MUST be recreated with `up -d --no-deps` (NEVER `docker compose down`) so paper trading
# state/streams are not torn down. See CLAUDE.md + docs/runbooks/paper-live-code-separation.md.
#
# Safety:
#   * Services to (re)build/recreate are AUTO-DETECTED from the currently-running project
#     topology, so the disabled monolith `trader` is never accidentally started. Override
#     with DEPLOY_SERVICES="svc1 svc2".
#   * Cleanup only prunes DANGLING (untagged) images — it never removes other projects'
#     images (e.g. bid_vector_*) and never runs `docker system prune`.
#
# Usage:
#   scripts/deploy_paper.sh [deploy|verify|cleanup]   (default: deploy = build+recreate+verify+cleanup)
#   scripts/deploy_paper.sh --dry-run                 # print the commands, run nothing
#   scripts/deploy_paper.sh --services "stock-market-ingest dashboard"
#   scripts/deploy_paper.sh --no-build                # recreate current images only
#   scripts/deploy_paper.sh --no-cleanup              # skip image prune
#   scripts/deploy_paper.sh -y                        # non-interactive (skip confirmation)
#
# Env overrides (config-driven, no hardcoded creds):
#   DEPLOY_ENV_FILE     (default .env.paper)
#   DEPLOY_SERVICES     (default: auto-detected running services)
#   DEPLOY_PROFILES     (default: "stock-ingest stock-pipeline research trading news producers scheduler")
#   DASHBOARD_HOST_PORT (default 5081)
#   DEPLOY_VERIFY_WAIT  (default 12)  seconds to wait before verifying
#   DEPLOY_RESTART_WATCH(default 20)  seconds to watch RestartCount for a crash-loop
#   DEPLOY_ASSUME_YES=1               same as -y

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV_FILE="${DEPLOY_ENV_FILE:-.env.paper}"
DASHBOARD_HOST_PORT="${DASHBOARD_HOST_PORT:-5081}"
VERIFY_WAIT_SECONDS="${DEPLOY_VERIFY_WAIT:-12}"
RESTART_WATCH_SECONDS="${DEPLOY_RESTART_WATCH:-20}"
DEFAULT_PROFILES="stock-ingest stock-pipeline research trading news producers scheduler"
PROFILES="${DEPLOY_PROFILES:-$DEFAULT_PROFILES}"

CMD="deploy"
DO_BUILD=1
DO_CLEANUP=1
DRY_RUN=0
ASSUME_YES="${DEPLOY_ASSUME_YES:-0}"
SERVICES_OVERRIDE="${DEPLOY_SERVICES:-}"

# ---------------------------------------------------------------------------
# Pretty logging
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
else
  GREEN=''; RED=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi
log()  { echo -e "${BLUE}==>${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }
die()  { err "$*"; exit 1; }

# Run a command, honouring --dry-run. Prints the command for transparency.
run() {
  echo -e "   ${BOLD}\$ $*${NC}"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@"
  fi
}

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    deploy|verify|cleanup) CMD="$1" ;;
    --env-file) [ $# -ge 2 ] || die "--env-file requires a value"; ENV_FILE="$2"; shift ;;
    --services) [ $# -ge 2 ] || die "--services requires a value"; SERVICES_OVERRIDE="$2"; shift ;;
    --profiles) [ $# -ge 2 ] || die "--profiles requires a value"; PROFILES="$2"; shift ;;
    --no-build) DO_BUILD=0 ;;
    --no-cleanup) DO_CLEANUP=0 ;;
    --dry-run) DRY_RUN=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) awk 'NR>=2 && /^#/{sub(/^# ?/,"");print;next} NR>=2{exit}' "$0"; exit 0 ;;
    *) die "Unknown argument: $1 (see --help)" ;;
  esac
  shift
done

# Build the repeated `--profile X` flag list.
PROFILE_ARGS=()
for p in $PROFILES; do PROFILE_ARGS+=(--profile "$p"); done

# `docker compose` wrapper bound to the paper env-file + profiles.
dc() { docker compose --env-file "$ENV_FILE" "${PROFILE_ARGS[@]}" "$@"; }

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
preflight() {
  log "Preflight"
  docker info >/dev/null 2>&1 || die "Docker is not running."
  [ -f "$ENV_FILE" ] || die "Env file '$ENV_FILE' not found (paper deploy requires it)."
  ok "Docker up, using env-file: $ENV_FILE"

  local proj; proj="$(grep -E '^COMPOSE_PROJECT_NAME=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  PROJECT_NAME="${proj:-kis_paper}"
  ok "Compose project: $PROJECT_NAME"

  # The published dashboard port is decided by the env-file, not the shell — read it so the
  # verify probe hits the real port even if only .env.paper sets it.
  local port; port="$(grep -E '^DASHBOARD_HOST_PORT=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  [ -n "$port" ] && DASHBOARD_HOST_PORT="$port"

  # Informational only — deploying a non-main branch is allowed (never blocks).
  local branch; branch="$(git branch --show-current 2>/dev/null || echo '?')"
  if [ "$branch" != "main" ]; then
    warn "On branch '$branch' (not main). Deploying whatever is checked out."
  else
    git fetch origin -q 2>/dev/null || true
    if [ -n "$(git rev-list "HEAD..origin/main" 2>/dev/null)" ]; then
      warn "Local main is behind origin/main — you may be deploying stale code (git pull --ff-only)."
    else
      ok "On main, in sync with origin."
    fi
  fi
}

# Resolve the service list: override, else auto-detect running services of the project.
resolve_services() {
  if [ -n "$SERVICES_OVERRIDE" ]; then
    SERVICES=( $SERVICES_OVERRIDE )
    log "Services (override): ${SERVICES[*]}"
    return
  fi
  # Include `restarting` — a crash-looping service is exactly what a redeploy must reach.
  mapfile -t SERVICES < <(dc ps --services --status running --status restarting 2>/dev/null | sort -u)
  [ "${#SERVICES[@]}" -gt 0 ] || die "No running/restarting services for project '$PROJECT_NAME'. Start the stack first, or pass --services."
  # Surface (but never auto-start) services that have a container yet aren't running (e.g. exited).
  local not_running
  not_running="$(dc ps -a --services 2>/dev/null | sort -u | comm -23 - <(printf '%s\n' "${SERVICES[@]}") | tr '\n' ' ')"
  [ -n "${not_running// /}" ] && warn "Have a container but not running (excluded — pass --services to include): $not_running"
  log "Services (auto-detected, ${#SERVICES[@]}): ${SERVICES[*]}"
}

confirm() {
  [ "$ASSUME_YES" -eq 1 ] && return 0
  [ "$DRY_RUN" -eq 1 ] && return 0
  [ -t 0 ] || return 0   # non-interactive shell: proceed
  echo
  read -r -p "$(echo -e "${BOLD}Rebuild & recreate ${#SERVICES[@]} paper services? [y/N] ${NC}")" ans
  case "$ans" in y|Y|yes|YES) return 0 ;; *) die "Aborted by user." ;; esac
}

# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------
build_phase() {
  [ "$DO_BUILD" -eq 1 ] || { warn "Skipping build (--no-build)."; return; }
  log "Building images (shared/ changes propagate to every service)"
  run dc build "${SERVICES[@]}"
  ok "Build complete."
}

recreate_phase() {
  log "Recreating services (up -d --no-deps — never 'down')"
  run dc up -d --no-deps "${SERVICES[@]}"
  ok "Recreate issued."
}

# Return the container id for a compose service (empty if none).
cid_of() { dc ps -q "$1" 2>/dev/null | head -1; }

verify_phase() {
  log "Verify (waiting ${VERIFY_WAIT_SECONDS}s for startup)"
  [ "$DRY_RUN" -eq 0 ] && sleep "$VERIFY_WAIT_SECONDS"

  echo
  dc ps 2>/dev/null || true
  echo

  # Snapshot RestartCount per service, then re-check after a watch window to catch crash-loops.
  declare -A rc0
  for svc in "${SERVICES[@]}"; do
    local id; id="$(cid_of "$svc")"
    [ -n "$id" ] && rc0["$svc"]="$(docker inspect "$id" --format '{{.RestartCount}}' 2>/dev/null || echo -1)"
  done

  log "Watching RestartCount for ${RESTART_WATCH_SECONDS}s to detect crash-loops..."
  [ "$DRY_RUN" -eq 0 ] && sleep "$RESTART_WATCH_SECONDS"

  local failed=0
  for svc in "${SERVICES[@]}"; do
    local id; id="$(cid_of "$svc")"
    if [ -z "$id" ]; then err "$svc: no container"; failed=1; continue; fi
    local running health rc1
    running="$(docker inspect "$id" --format '{{.State.Running}}' 2>/dev/null || echo false)"
    health="$(docker inspect "$id" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}' 2>/dev/null || echo '-')"
    rc1="$(docker inspect "$id" --format '{{.RestartCount}}' 2>/dev/null || echo -1)"
    local rc_prev="${rc0[$svc]:--1}"

    if [ "$running" != "true" ]; then
      err "$svc: NOT running (health=$health, restarts=$rc1)"; failed=1
    elif [ "$DRY_RUN" -eq 0 ] && [ "$rc_prev" -ge 0 ] && [ "$rc1" -gt "$rc_prev" ]; then
      err "$svc: RESTARTING ($rc_prev -> $rc1) — crash-loop; check: docker logs ${PROJECT_NAME}-$svc"; failed=1
    elif [ "$health" = "unhealthy" ]; then
      err "$svc: unhealthy"; failed=1
    else
      ok "$svc: running (health=$health, restarts=$rc1)"
    fi
  done

  # Host-exposed dashboard probe (tolerant — behind Caddy on $DASHBOARD_HOST_PORT).
  if curl -sf -o /dev/null "http://localhost:${DASHBOARD_HOST_PORT}/" 2>/dev/null; then
    ok "Dashboard reachable on :${DASHBOARD_HOST_PORT}"
  else
    warn "Dashboard not answering on :${DASHBOARD_HOST_PORT} yet (may still be warming up)."
  fi

  # Redis DB1 ping (host redis; tolerant if redis-cli absent).
  if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli -h localhost -p 6379 -n 1 ping >/dev/null 2>&1; then
      ok "Redis DB1 reachable (localhost:6379)"
    else
      warn "Redis DB1 not answering on localhost:6379."
    fi
  fi

  echo
  if [ "$failed" -eq 0 ]; then
    ok "${BOLD}Verify PASSED${NC}"
    return 0
  else
    err "${BOLD}Verify FAILED — see errors above${NC}"
    return 1
  fi
}

cleanup_phase() {
  [ "$DO_CLEANUP" -eq 1 ] || { warn "Skipping cleanup (--no-cleanup)."; return; }
  log "Cleanup (dangling images only — other projects' images are untouched)"
  run docker image prune -f
  ok "Cleanup complete."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo -e "${BOLD}=== KIS paper deploy (${CMD}) ===${NC}"
preflight

case "$CMD" in
  deploy)
    resolve_services
    confirm
    build_phase
    recreate_phase
    if verify_phase; then
      cleanup_phase
      echo
      ok "${BOLD}Deploy done.${NC}  Dashboard: http://localhost:${DASHBOARD_HOST_PORT}  (toggle asset -> Stock)"
      echo "   Logs:  docker compose --env-file $ENV_FILE logs -f <service>"
    else
      cleanup_phase
      die "Deploy verification failed — stack left running; inspect logs above."
    fi
    ;;
  verify)
    resolve_services
    verify_phase
    ;;
  cleanup)
    cleanup_phase
    ;;
esac
