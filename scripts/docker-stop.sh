#!/bin/bash
# scripts/docker-stop.sh
# Stop Docker services gracefully

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Stopping KIS Unified Trading Platform ==="
echo ""

# Stop services
docker compose down

echo ""
echo "=== All services stopped ==="
