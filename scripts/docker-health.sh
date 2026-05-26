#!/bin/bash
# scripts/docker-health.sh
# Check health of all Docker services

set -e

echo "=== KIS Unified Trading Platform - Health Check ==="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

check_service() {
    local name=$1
    local url=$2

    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} $name is unhealthy"
        FAILED=1
        return 1
    fi
}

check_redis() {
    if command -v redis-cli &> /dev/null; then
        if redis-cli -h localhost ping > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Redis is healthy"
            return 0
        fi
    fi
    # Fallback to docker
    if docker exec kis-redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis is healthy"
        return 0
    fi
    echo -e "${RED}✗${NC} Redis is unhealthy"
    FAILED=1
    return 1
}

echo ""
echo "Checking services..."
echo ""

# Check each host-exposed service
check_service "Dashboard API" "http://localhost:8001/health" || true
check_redis || true
check_service "Prometheus" "http://localhost:9090/-/healthy" || true

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}=== All services healthy ===${NC}"
    exit 0
else
    echo -e "${YELLOW}=== Some services unhealthy ===${NC}"
    exit 1
fi
