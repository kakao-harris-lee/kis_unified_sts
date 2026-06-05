#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${1:-reports/rollback_drill/$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT_DIR"

{
  echo "Rollback drill snapshot"
  echo "generated_at=$(date -Is)"
  echo
  echo "RuntimeLedger"
  uv run --frozen python - <<'PY'
from shared.storage import SQLiteRuntimeLedger, StorageConfig

cfg = StorageConfig.load_or_default()
ledger = SQLiteRuntimeLedger(cfg.runtime_storage.sqlite)
try:
    print("open_stock_positions", len(ledger.load_open_positions("stock")))
    print("open_futures_positions", len(ledger.load_open_positions("futures")))
    print("recent_stock_trades", len(ledger.query_trades({"asset_class": "stock", "limit": 20})))
    print("recent_futures_trades", len(ledger.query_trades({"asset_class": "futures", "limit": 20})))
finally:
    ledger.close()
PY
  echo
  echo "Parquet"
  uv run --frozen sts data validate-parquet || true
} | tee "$OUT_DIR/snapshot.txt"

echo "Wrote $OUT_DIR/snapshot.txt"
