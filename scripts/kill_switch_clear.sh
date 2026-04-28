#!/usr/bin/env bash
# kill_switch_clear.sh — operator-only sentinel clear.
#
# Phase 4 Task 13/19. After a kill switch trip, the order_router daemon
# refuses to start until this script removes the sentinel file. Operator
# must verify (a) PnL state, (b) any open positions are flat, (c) root
# cause investigated — BEFORE running this.
#
# Usage:
#   sudo ./scripts/kill_switch_clear.sh                # interactive prompt
#   sudo ./scripts/kill_switch_clear.sh --confirm      # non-interactive
#
# After clearing:
#   sudo systemctl start kis-kill-switch kis-order-router

set -euo pipefail

SENTINEL="${KILL_SWITCH_SENTINEL_PATH:-/var/run/kis_kill_switch.tripped}"

if [[ ! -f "$SENTINEL" ]]; then
    echo "No kill switch sentinel at $SENTINEL — nothing to clear."
    exit 0
fi

echo "==== KILL SWITCH SENTINEL CONTENT ===="
cat "$SENTINEL"
echo "======================================"
echo

if [[ "${1:-}" != "--confirm" ]]; then
    read -r -p "Have you (a) verified PnL state, (b) flattened any open positions, (c) investigated root cause? [yes/NO]: " ack
    if [[ "$ack" != "yes" ]]; then
        echo "Aborted — sentinel left in place."
        exit 1
    fi
fi

# Snapshot to journal before delete (audit trail).
LOG_DIR="${KIS_KILL_SWITCH_LOG_DIR:-/home/deploy/project/kis_unified_sts/logs/kill_switch}"
mkdir -p "$LOG_DIR"
cp "$SENTINEL" "$LOG_DIR/cleared_$(date +%Y%m%d_%H%M%S).log"

rm -f "$SENTINEL"
echo "Sentinel cleared at $(date -Iseconds)."
echo "Restart with:"
echo "  sudo systemctl start kis-kill-switch kis-order-router"
