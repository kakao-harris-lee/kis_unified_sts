#!/bin/bash
# Phase 2 Daily Verification — kis_unified_sts §10.2 cron wrapper.
#
# Runs after each trading-day market close (15:40 KST + buffer) and
# verifies the four Phase 2 invariants from
# docs/plans/2026-05-03-llm-primary-rl-minimization.md §10.2:
#   1. RL shadow predictions today > 0
#   2. RL trades today == 0 (shadow_mode invariant)
#   3. Setup A signal count today >= 1
#   4. shadow_loggers dropped batches == 0
#
# Posts a PASS/FAIL summary to the Telegram briefing channel and archives
# a JSON report under reports/daily_verification/YYYY-MM-DD.json.
#
# crontab: 0 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/phase2_daily_verification.sh

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/phase2_daily_verification_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Phase 2 Daily Verification Start ==="

cd "$PROJECT_DIR"
source "$VENV"
set -a && source .env && set +a

# Don't propagate exit code 1 (gate fail) as a cron error — the Telegram
# alert already notifies the operator, and we don't want cron-level
# error mail spam on top of that.  Exit code 2 (script error) DOES
# propagate so genuine breakage is visible.
set +e
python3 -m scripts.analysis.phase2_daily_verification >> "$LOG_FILE" 2>&1
status=$?
set -e

if [[ $status -eq 0 ]]; then
    log "=== Phase 2 Daily Verification Complete (PASS) ==="
elif [[ $status -eq 1 ]]; then
    log "=== Phase 2 Daily Verification Complete (FAIL — see Telegram) ==="
    exit 0  # don't trigger cron error mail; Telegram alert is the channel
else
    log "=== Phase 2 Daily Verification ERROR (script failure, exit=$status) ==="
    exit "$status"
fi
