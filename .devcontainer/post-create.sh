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

# Deliberately NOT creating a .env. The dev app and the test suite both run
# fine without one (Redis + ENVIRONMENT come from compose; dashboard auth is off
# by default). A .env copied from .env.example ships production-leaning values
# (DASHBOARD_REQUIRE_AUTH=true, REDIS_HOST=redis) that the suite — which loads
# .env via conftest / cli.main — would pick up and fail on (dashboard 401s,
# wrong Redis host). Create one yourself only for credentialed live/data runs:
#   cp .env.example .env   # then fill in KIS secrets
echo "==> Skipping .env (optional — only needed for live/data; see README)"

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
