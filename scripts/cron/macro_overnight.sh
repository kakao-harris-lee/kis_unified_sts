#!/usr/bin/env bash
# Macro overnight collector.
# Usage: macro_overnight.sh us|fx
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ ! -d ".venv" ]; then
  echo "venv not found" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
if [ -f .env ]; then
  set -a && source .env && set +a
fi

exec python -m services.macro_overnight_collector.main "$@"
