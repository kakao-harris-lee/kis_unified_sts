#!/bin/bash
# Verify no remaining references to modules deleted in Phase 5.
set -e

DELETED=(
  "services.dashboard.routes.backtest"
  "services.dashboard.routes.experiments"
  "from services.dashboard.routes import backtest"
  "from services.dashboard.routes import experiments"
  "pages/Backtest"
  "pages/Experiments"
  "pages/StrategyConfig"
  "pages/StrategyCreate"
  "pages/Dashboard"
  "components/VenueMetrics"
  "components/ExperimentComparison"
  "components/StrategyForm"
  "backtestApi"
  "experimentsApi"
)

FOUND=0
for pattern in "${DELETED[@]}"; do
  hits=$(grep -rn "$pattern" \
    --include="*.py" \
    --include="*.ts" \
    --include="*.tsx" \
    --exclude-dir="archive" \
    --exclude-dir="node_modules" \
    --exclude-dir="__pycache__" \
    --exclude-dir=".worktrees" \
    . 2>/dev/null | grep -v "scripts/dev/check_no_dead_imports.sh" | grep -v "docs/superpowers/" || true)
  if [ -n "$hits" ]; then
    echo "FAIL: '$pattern' still referenced:"
    echo "$hits"
    FOUND=1
  fi
done

if [ "$FOUND" -eq 1 ]; then
  exit 1
fi
echo "OK: no dead imports detected"
