#!/bin/bash
# Setup A/C intra-session signal-timing monitor — cron wrapper.
#
# Runs after market close (daily verification is 16:00 KST; this is 16:05 to
# avoid contending for the same minute). Parses the orchestrator log and
# posts a PASS/WARN/FAIL Telegram briefing on whether Setup A/C generated
# signals throughout the session (validates PR #252 cache-staleness fix).
#
# crontab: 5 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/setup_ac_signal_timing.sh

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/setup_ac_signal_timing_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "=== Setup A/C signal-timing monitor start ==="

cd "$PROJECT_DIR"
# shellcheck disable=SC1090
source "$VENV"
set -a
# shellcheck disable=SC1091
[ -f .env ] && source .env
set +a

# Exit 1 (WARN/FAIL) must NOT propagate as a cron error — the Telegram
# briefing already notifies the operator. Exit 2 (script error) DOES
# propagate so genuine breakage surfaces.
set +e
"$PROJECT_DIR/.venv/bin/python" scripts/analysis/setup_ac_signal_timing.py \
    >> "$LOG_FILE" 2>&1
rc=$?
set -e

if [ "$rc" -eq 2 ]; then
    log "ERROR: monitor script error (rc=2)"
    exit 2
fi
log "=== done (verdict rc=$rc; 0=PASS 1=WARN/FAIL) ==="
exit 0
