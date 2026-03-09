#!/bin/bash
# Verification script for strategies endpoint
# Run this when the dashboard service is running

set -e

PORT=${DASHBOARD_PORT:-8001}
BASE_URL="http://localhost:${PORT}"

echo "======================================"
echo "Strategies Endpoint Verification"
echo "======================================"
echo ""

# Check if service is running
echo "1. Health check..."
if ! curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
    echo "✗ Dashboard service is not running on port ${PORT}"
    echo "  Start it with: docker-compose up dashboard"
    echo "  Or run: python -m uvicorn services.dashboard.app:create_app --factory --host 0.0.0.0 --port ${PORT}"
    exit 1
fi
echo "✓ Service is healthy"
echo ""

# Test 1: List all strategies
echo "2. Test GET /api/strategies (all strategies)..."
response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/strategies")
status=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$status" = "200" ]; then
    echo "✓ Status: 200 OK"
    total=$(echo "$body" | grep -o '"total":[0-9]*' | cut -d: -f2)
    echo "  Total strategies: ${total}"
else
    echo "✗ Status: ${status}"
    echo "  Response: ${body}"
    exit 1
fi
echo ""

# Test 2: Filter by asset_class=stock
echo "3. Test GET /api/strategies?asset_class=stock..."
response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/strategies?asset_class=stock")
status=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$status" = "200" ]; then
    echo "✓ Status: 200 OK"
    total=$(echo "$body" | grep -o '"total":[0-9]*' | cut -d: -f2)
    echo "  Stock strategies: ${total}"
else
    echo "✗ Status: ${status}"
    echo "  Response: ${body}"
    exit 1
fi
echo ""

# Test 3: Filter by asset_class=futures
echo "4. Test GET /api/strategies?asset_class=futures..."
response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/strategies?asset_class=futures")
status=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$status" = "200" ]; then
    echo "✓ Status: 200 OK"
    total=$(echo "$body" | grep -o '"total":[0-9]*' | cut -d: -f2)
    echo "  Futures strategies: ${total}"
else
    echo "✗ Status: ${status}"
    echo "  Response: ${body}"
    exit 1
fi
echo ""

# Test 4: Invalid asset_class
echo "5. Test GET /api/strategies?asset_class=invalid (should fail with 400)..."
response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/strategies?asset_class=invalid")
status=$(echo "$response" | tail -n1)

if [ "$status" = "400" ]; then
    echo "✓ Status: 400 (correctly rejected)"
else
    echo "✗ Expected 400, got: ${status}"
    exit 1
fi
echo ""

# Test 5: Include disabled strategies
echo "6. Test GET /api/strategies?enabled_only=false..."
response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/strategies?enabled_only=false")
status=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$status" = "200" ]; then
    echo "✓ Status: 200 OK"
    total=$(echo "$body" | grep -o '"total":[0-9]*' | cut -d: -f2)
    echo "  Total strategies (including disabled): ${total}"
else
    echo "✗ Status: ${status}"
    echo "  Response: ${body}"
    exit 1
fi
echo ""

echo "======================================"
echo "✓ All tests passed!"
echo "======================================"
