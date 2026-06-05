#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Verifying daily scanner prerequisites (Redis DB 1 + Parquet market data)."

if [[ "${REDIS_URL:-}" == *"/0" ]]; then
  echo "ERROR: REDIS_URL must use DB 1, not DB 0" >&2
  exit 1
fi

uv run --frozen sts data validate-parquet
uv run --frozen python -m services.daily_scanner --help >/dev/null

echo "Daily scanner cron prerequisites look valid."
