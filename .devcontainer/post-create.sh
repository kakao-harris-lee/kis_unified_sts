#!/usr/bin/env bash
# Dev Container bootstrap — runs once after the container is created. Idempotent;
# safe to re-run (e.g. "Rebuild Container").
set -euo pipefail

# Repo root = parent of this script's directory.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Python: $(python --version)"
echo "==> Installing project (editable) + dev extras"
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" prometheus-client

echo "==> Seeding .env from template (only if missing)"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from .env.example (fill KIS creds for live/data paths)"
fi

echo "==> Installing frontend deps (strategy-builder-ui)"
if [ -d strategy-builder-ui ] && command -v npm >/dev/null 2>&1; then
  # Non-fatal: a frontend dep hiccup must not break the backend dev environment.
  (cd strategy-builder-ui && npm install) || echo "    npm install failed — run 'make ui' later"
else
  echo "    skipped (npm not ready yet — run 'make ui' later)"
fi

echo ""
echo "==> Ready. Redis is at localhost:6379 (DB 1). Next:"
echo "      pytest tests/unit -q        # quick check"
echo "      make help                   # all dev commands"
