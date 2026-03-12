#!/bin/bash
# Development runner for synthetic calibration optimizer.
#
# Usage:
#   ./scripts/run_synthetic_calibration_optimizer.sh
#   MAX_ITERATIONS=5 PATIENCE=2 ./scripts/run_synthetic_calibration_optimizer.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
OUTPUT_ROOT="${OUTPUT_ROOT:-artifacts/datasets/calibration/optimizer_run}"
MAX_ITERATIONS="${MAX_ITERATIONS:-3}"
PATIENCE="${PATIENCE:-1}"
MIN_IMPROVEMENT="${MIN_IMPROVEMENT:-1e-6}"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Python virtualenv not found at $VENV_PYTHON" >&2
    exit 1
fi

cd "$PROJECT_DIR"

"$VENV_PYTHON" scripts/training/optimize_synthetic_calibration.py \
    --max-iterations "$MAX_ITERATIONS" \
    --patience "$PATIENCE" \
    --min-improvement "$MIN_IMPROVEMENT" \
    --output-root "$OUTPUT_ROOT"

"$VENV_PYTHON" scripts/training/summarize_synthetic_calibration.py \
    --manifest "${OUTPUT_ROOT}/optimizer_manifest.json" \
    --output "${OUTPUT_ROOT}/optimizer_summary.md"

echo "Synthetic calibration optimizer run complete."
echo "- manifest: ${PROJECT_DIR}/${OUTPUT_ROOT}/optimizer_manifest.json"
echo "- summary:  ${PROJECT_DIR}/${OUTPUT_ROOT}/optimizer_summary.md"