#!/bin/bash
# Phase 2 Pre-flight Check — operator wrapper.
#
# Runs the 8-check verification documented in
# docs/runbooks/phase2-startup.md § "Pre-flight check".  Operator runs
# this manually on Friday EOD before the Monday cutover; one command
# replaces 5+ manual cli invocations.
#
# Exit code 0 = all critical checks PASS, 1 = at least one FAIL,
# 2 = script-level error.
#
# Optional cron schedule (Fri 17:00 KST as a reminder):
#   0 17 * * 5 /home/deploy/project/kis_unified_sts/scripts/cron/phase2_preflight_check.sh

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/phase2_preflight_$(date +%Y%m%d_%H%M%S).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
source "$VENV"
set -a && source .env && set +a

set +e
python3 -m scripts.analysis.phase2_preflight_check | tee -a "$LOG_FILE"
status=$?
set -e

exit "$status"
