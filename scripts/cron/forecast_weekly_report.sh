#!/bin/bash
# Phase F weekly validation report — Sun 23:00 KST.
set -euo pipefail
PROJECT_DIR="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/forecast_weekly_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"
set -a && source .env && set +a
FORECAST_REPORT_WINDOW_DAYS=7 \
  ".venv/bin/python" scripts/analysis/forecast_vs_rl_comparison.py \
  >> "$LOG_FILE" 2>&1
