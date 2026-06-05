#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Backtest data now uses Parquet under data/market."
echo "Use sts backfill run --sink parquet for collection and sts data validate-parquet for validation."

if command -v sts >/dev/null 2>&1; then
  sts data validate-parquet
else
  uv run --frozen sts data validate-parquet
fi
