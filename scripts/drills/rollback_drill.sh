#!/bin/bash
# Rollback drill — Phase 5 Task 8.
#
# Dry-run automation of docs/runbooks/futures-paradigm-rollback.md
# steps 1–7 with per-step timing. Cadence: twice yearly, weekend
# (no-trading day). Output written to reports/drills/rollback_YYYYMMDD.txt
# committed for audit.
#
# Per spec docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md §6.3
# "모의 롤백 훈련 (실거래 없는 주말) — 전체 단계 수행 시간 측정".
#
# This script:
#   - Runs flatten_all DRY-RUN (without --confirm — never closes real positions)
#   - Inspects systemd units WITHOUT stopping them (uses `systemctl status`)
#   - Inspects config WITHOUT editing
#   - Runs ClickHouse + Redis state-snapshot queries
#   - Records each step's wallclock duration
#
# It does NOT actually stop services or close positions. It exists to
# exercise the muscle memory of running each step + measure timing so
# real-incident rollback is predictable.

set -uo pipefail
# NOT `set -e` — drill should keep going even if a step fails so the
# operator sees the full picture.

PROJECT_DIR="${PROJECT_DIR:-/home/deploy/project/kis_unified_sts}"
DRILL_DATE="$(date +%Y%m%d_%H%M%S)"
DRILL_DAY="$(date +%Y%m%d)"
OUTPUT_DIR="${PROJECT_DIR}/reports/drills"
OUTPUT_FILE="${OUTPUT_DIR}/rollback_${DRILL_DAY}.txt"

mkdir -p "${OUTPUT_DIR}"

cd "${PROJECT_DIR}"

# Use the project venv if available — falls back to system python otherwise.
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="$(command -v python3 || command -v python)"
fi

UNITS=(
    kis-decision-engine
    kis-risk-filter
    kis-order-router
    kis-kill-switch
    kis-news-collector
    kis-news-scorer
)

now_ms() { date +%s%3N; }

run_step() {
    local step_num="$1"
    local step_name="$2"
    shift 2
    local start_ms end_ms duration_ms rc
    echo "" | tee -a "${OUTPUT_FILE}"
    echo "=== Step ${step_num}: ${step_name} ===" | tee -a "${OUTPUT_FILE}"
    start_ms="$(now_ms)"
    "$@" 2>&1 | tee -a "${OUTPUT_FILE}"
    rc="${PIPESTATUS[0]}"
    end_ms="$(now_ms)"
    duration_ms="$(( end_ms - start_ms ))"
    echo "--- Step ${step_num} completed: rc=${rc} duration=${duration_ms}ms ---" \
        | tee -a "${OUTPUT_FILE}"
}

# ---- Step 1: flatten_all dry-run ---------------------------------------------
step1_flatten_dryrun() {
    echo "Running: ${PYTHON_BIN} -m scripts.trading.flatten_all"
    echo "(NO --confirm flag — drill does not close real positions)"
    "${PYTHON_BIN}" -m scripts.trading.flatten_all || true
}

# ---- Step 2: inspect systemd units (no stop) ---------------------------------
step2_inspect_units() {
    for unit in "${UNITS[@]}"; do
        echo ""
        echo "--- ${unit} ---"
        systemctl is-active "${unit}" 2>/dev/null || echo "is-active: query failed"
        systemctl show "${unit}" -p NRestarts,ActiveState,SubState,LoadState 2>/dev/null \
            || echo "show: query failed"
    done
}

# ---- Step 3: inspect decision_engine.yaml ------------------------------------
step3_inspect_config() {
    local cfg="${PROJECT_DIR}/config/decision_engine.yaml"
    if [[ -f "${cfg}" ]]; then
        echo "Current decision_engine.yaml:"
        grep -E "^enabled:|^name:|^[a-z_]+:" "${cfg}" | head -20
    else
        echo "WARNING: ${cfg} not found"
    fi
}

# ---- Step 4: trading process status ------------------------------------------
step4_trading_status() {
    for unit in kis-futures-trading kis-stock-trading; do
        echo "--- ${unit} ---"
        systemctl is-active "${unit}" 2>/dev/null || echo "is-active: query failed"
    done
    echo ""
    echo "Live trading processes:"
    ps -eo pid,etime,cmd | grep -E "sts trade start|services.trading" | grep -v grep || echo "(none found)"
}

# ---- Step 5: log/ledger snapshot ---------------------------------------------
step5_log_snapshot() {
    echo "ClickHouse fills last 4h:"
    if command -v clickhouse-client >/dev/null 2>&1; then
        clickhouse-client --query \
            "SELECT count() FROM kospi.order_fills WHERE filled_at >= now() - INTERVAL 4 HOUR" \
            2>&1 || echo "  (clickhouse-client query failed)"
        clickhouse-client --query \
            "SELECT count() FROM kospi.rl_signals WHERE generated_at >= now() - INTERVAL 4 HOUR" \
            2>&1 || echo "  (clickhouse-client query failed)"
    else
        echo "  (clickhouse-client not on PATH — drill cannot snapshot ledger)"
    fi

    echo ""
    echo "Redis stream lengths:"
    if command -v redis-cli >/dev/null 2>&1; then
        for stream in stream:signal.candidate stream:signal.scored stream:signal.final stream:order.fill; do
            local n
            n="$(redis-cli -n 1 XLEN "${stream}" 2>/dev/null || echo "?")"
            echo "  ${stream}: ${n}"
        done
    else
        echo "  (redis-cli not on PATH — drill cannot snapshot streams)"
    fi
}

# ---- Step 6: cooldown rule reminder (text-only) ------------------------------
step6_cooldown_note() {
    cat <<'NOTE'
Per docs/runbooks/futures-paradigm-rollback.md §6:
  - 24-hour cooldown before any restart attempt
  - Root-cause analysis required (PR with fix merged)
  - Telegram briefing posted to incident channel

Per docs/runbooks/futures-paradigm-rollback.md §7:
  - 3-day paper re-validation BEFORE live order_router restart
  - Operator written sign-off before flipping futures_live.enabled: true

(This drill exercises the procedure. No real cooldown applies — drill
is on a no-trading day with no positions outstanding.)
NOTE
}

# ---- Step 7: incident bundle dir layout (drill dry-run) ----------------------
step7_incident_bundle_layout() {
    local bundle="${PROJECT_DIR}/reports/incidents/drill_${DRILL_DATE}"
    mkdir -p "${bundle}"
    echo "Drill bundle dir created at: ${bundle}"
    echo "(In a real incident, journalctl/clickhouse-client/redis-cli output would land here.)"
    {
        echo "DRILL run on $(date -Is)"
        echo "Triggered by: $(whoami)"
        echo "Hostname: $(hostname)"
    } > "${bundle}/drill_marker.txt"
    ls -la "${bundle}"
}

# -----------------------------------------------------------------------------
# Drill main
# -----------------------------------------------------------------------------
{
    echo "=================================================================="
    echo "Phase 5 Rollback Drill — DRY RUN"
    echo "=================================================================="
    echo "Started:  $(date -Is)"
    echo "User:     $(whoami)"
    echo "Host:     $(hostname)"
    echo "Project:  ${PROJECT_DIR}"
    echo "Output:   ${OUTPUT_FILE}"
    echo ""
    echo "This is a DRY RUN of futures-paradigm-rollback.md steps 1-7."
    echo "No services are stopped. No positions are closed. No config is changed."
    echo "Per-step wallclock durations are recorded for ops time-budget tracking."
} | tee "${OUTPUT_FILE}"

DRILL_START_MS="$(now_ms)"

run_step 1 "flatten_all dry-run"            step1_flatten_dryrun
run_step 2 "Inspect systemd units (no stop)" step2_inspect_units
run_step 3 "Inspect decision_engine.yaml"    step3_inspect_config
run_step 4 "Trading process status"          step4_trading_status
run_step 5 "Log/ledger snapshot"             step5_log_snapshot
run_step 6 "Cooldown rule reminder"          step6_cooldown_note
run_step 7 "Incident bundle dir layout"      step7_incident_bundle_layout

DRILL_END_MS="$(now_ms)"
TOTAL_MS="$(( DRILL_END_MS - DRILL_START_MS ))"

{
    echo ""
    echo "=================================================================="
    echo "Drill complete"
    echo "=================================================================="
    echo "Total wallclock: ${TOTAL_MS}ms"
    echo ""
    echo "Next actions:"
    echo "  - Commit ${OUTPUT_FILE} to repo"
    echo "  - If any step took > 2× expected (target < 5s/step), investigate"
    echo "  - Calendar reminder for next drill (~6 months)"
} | tee -a "${OUTPUT_FILE}"

echo ""
echo "Drill output saved to ${OUTPUT_FILE}"
exit 0
