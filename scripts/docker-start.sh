#!/bin/bash
# scripts/docker-start.sh
# Start Docker services with proper initialization

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_HOST_PORT="${DASHBOARD_HOST_PORT:-5081}"

cd "$PROJECT_DIR"

echo "=== Starting KIS Unified Trading Platform ==="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo ""
    echo "Please create .env file:"
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your configuration"
    exit 1
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    exit 1
fi

# Start services
echo "Starting Docker services..."
docker compose up -d

# Wait for services
echo ""
echo "Waiting for services to be ready..."
sleep 15

# Run health check
echo ""
"$SCRIPT_DIR/docker-health.sh"

echo ""
echo "=== Platform Started Successfully ==="
echo ""
echo "Access points:"
echo "  - Dashboard:    http://localhost:${DASHBOARD_HOST_PORT}"
echo "  - Prometheus:   http://localhost:9090"
echo ""
echo "View logs:"
echo "  docker compose logs -f"
echo ""
echo "Stop services:"
echo "  docker compose down"
