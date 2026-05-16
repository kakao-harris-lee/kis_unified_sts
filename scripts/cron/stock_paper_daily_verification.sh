#!/usr/bin/env bash
# Stock paper after-close verification gate.
#
# crontab: 10 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_paper_daily_verification.sh

set -euo pipefail

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/stock_paper_daily_verification_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "=== Stock paper daily verification start ==="

cd "$PROJECT_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

set +e
.venv/bin/python scripts/analysis/stock_paper_daily_verification.py >> "$LOG_FILE" 2>&1
rc=$?
set -e

log "=== done (rc=$rc; 0=PASS 1=gate issues 2=script error) ==="
exit "$rc"
