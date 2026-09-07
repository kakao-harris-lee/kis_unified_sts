#!/usr/bin/env bash
# kill_switch_clear.sh — operator-only sentinel clear (Docker Compose runtime).
#
# After a kill switch trip, futures-order-router refuses to start (or
# continue) until this script removes the tripped sentinel. A second,
# independent sentinel — the position-recovery sentinel written by
# scripts/trading/recover_positions.py on a broker/ledger divergence — has
# the same fail-closed effect on futures-order-router and is cleared with
# --recovery instead.
#
# Sentinel paths are derived from config/kill_switch.yaml (via
# services.kill_switch.config.KillSwitchConfig and
# shared.config.runtime_defaults.host_path_for_container_runtime_path), not
# hardcoded here, so this script and the containerized consumers never
# disagree on which file they mean. Override for tests/ops with
# KILL_SWITCH_SENTINEL_PATH / KILL_SWITCH_RECOVERY_SENTINEL_PATH.
#
# Operator must verify, BEFORE clearing the kill-switch sentinel: (a) PnL
# state, (b) any open positions are flat, (c) root cause investigated.
# Before clearing the recovery sentinel, review the divergence report from
# scripts/trading/recover_positions.py and resolve it.
#
# Usage:
#   ./scripts/kill_switch_clear.sh                          # kill-switch sentinel, interactive prompt
#   ./scripts/kill_switch_clear.sh --confirm                 # non-interactive
#   ./scripts/kill_switch_clear.sh --recovery [--confirm]     # position-recovery sentinel instead
#   ./scripts/kill_switch_clear.sh --print-path [--recovery]  # print the resolved sentinel path, exit 0
#
# After clearing (docker compose, not systemd — see
# docs/runbooks/futures-pipeline-cutover-f9.md "Compose Profiles"):
#   docker compose --env-file .env.paper --profile futures-pipeline up -d futures-order-router
#   # futures-kill-switch is live-only (config/kill_switch.yaml::enabled) —
#   # only bring it up as part of a live cutover, not for paper:
#   docker compose --env-file .env.live --profile futures-killswitch up -d futures-kill-switch

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RECOVERY=0
CONFIRM=0
PRINT_PATH=0

for arg in "$@"; do
    case "$arg" in
        --recovery)
            RECOVERY=1
            ;;
        --confirm)
            CONFIRM=1
            ;;
        --print-path)
            PRINT_PATH=1
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: $0 [--recovery] [--confirm] [--print-path]" >&2
            exit 2
            ;;
    esac
done

resolve_python() {
    if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
        echo "$REPO_ROOT/.venv/bin/python"
    elif command -v python3 &>/dev/null; then
        command -v python3
    else
        command -v python
    fi
}

# Resolve a config/kill_switch.yaml sentinel attribute to its host path via
# the single source of truth also used by scripts/trading/recover_positions.py
# (see shared/config/runtime_defaults.py::host_path_for_container_runtime_path).
resolve_sentinel_path() {
    local attr="$1"
    local py
    py="$(resolve_python)"
    (
        cd "$REPO_ROOT"
        "$py" -c "
from services.kill_switch.config import KillSwitchConfig
from shared.config.runtime_defaults import host_path_for_container_runtime_path

cfg = KillSwitchConfig.from_yaml()
print(host_path_for_container_runtime_path(getattr(cfg, '$attr')))
"
    )
}

if [[ "$RECOVERY" -eq 1 ]]; then
    SENTINEL="${KILL_SWITCH_RECOVERY_SENTINEL_PATH:-$(resolve_sentinel_path recovery_sentinel_path)}"
else
    SENTINEL="${KILL_SWITCH_SENTINEL_PATH:-$(resolve_sentinel_path sentinel_path)}"
fi

if [[ "$PRINT_PATH" -eq 1 ]]; then
    echo "$SENTINEL"
    exit 0
fi

if [[ ! -f "$SENTINEL" ]]; then
    echo "No kill switch sentinel at $SENTINEL — nothing to clear."
    exit 0
fi

echo "==== KILL SWITCH SENTINEL CONTENT ===="
cat "$SENTINEL"
echo "======================================"
echo

if [[ "$CONFIRM" -ne 1 ]]; then
    if [[ "$RECOVERY" -eq 1 ]]; then
        read -r -p "Have you reviewed the divergence report from scripts/trading/recover_positions.py and resolved it? [yes/NO]: " ack
    else
        read -r -p "Have you (a) verified PnL state, (b) flattened any open positions, (c) investigated root cause? [yes/NO]: " ack
    fi
    if [[ "$ack" != "yes" ]]; then
        echo "Aborted — sentinel left in place."
        exit 1
    fi
fi

# Snapshot to journal before delete (audit trail).
LOG_DIR="${KIS_KILL_SWITCH_LOG_DIR:-$REPO_ROOT/logs/kill_switch}"
mkdir -p "$LOG_DIR"
if [[ "$RECOVERY" -eq 1 ]]; then
    JOURNAL_PREFIX="cleared_recovery"
else
    JOURNAL_PREFIX="cleared"
fi
cp "$SENTINEL" "$LOG_DIR/${JOURNAL_PREFIX}_$(date +%Y%m%d_%H%M%S).log"

rm -f "$SENTINEL"
echo "Sentinel cleared at $(date -Iseconds)."
echo

if [[ "$RECOVERY" -eq 1 ]]; then
    echo "futures-order-router will pick this up on its next loop iteration,"
    echo "or start it if it isn't already running:"
    echo "  docker compose --env-file .env.paper --profile futures-pipeline up -d futures-order-router"
else
    echo "Restart with:"
    echo "  docker compose --env-file .env.paper --profile futures-pipeline up -d futures-order-router"
    echo "  # futures-kill-switch is live-only (config/kill_switch.yaml::enabled) —"
    echo "  # only bring it up as part of a live cutover:"
    echo "  docker compose --env-file .env.live --profile futures-killswitch up -d futures-kill-switch"
fi
