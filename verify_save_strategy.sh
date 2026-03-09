#!/bin/bash
# Verification script for POST /api/strategies endpoint
# This script requires the FastAPI server to be running

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Testing POST /api/strategies endpoint"
echo "=========================================="
echo ""

# Test 1: Valid strategy save
echo "Test 1: Save valid strategy configuration"
curl -X POST "${BASE_URL}/api/strategies" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_class": "stock",
    "name": "test_strategy",
    "config": {
      "strategy": {
        "name": "test_strategy",
        "asset_class": "stock",
        "enabled": true,
        "description": "Test strategy for validation",
        "entry": {
          "type": "mean_reversion",
          "params": {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 30
          }
        },
        "exit": {
          "type": "three_stage",
          "params": {
            "stop_loss_pct": -0.015,
            "breakeven_threshold_pct": 0.02,
            "breakeven_stop_offset_pct": 0.005
          }
        },
        "position": {
          "type": "fixed",
          "params": {
            "quantity": 100
          }
        }
      }
    }
  }'

echo -e "\n\n"

# Test 2: Invalid asset class
echo "Test 2: Invalid asset class (should return 422 validation error)"
curl -X POST "${BASE_URL}/api/strategies" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_class": "crypto",
    "name": "test_invalid",
    "config": {"strategy": {}}
  }'

echo -e "\n\n"

# Test 3: Missing strategy key
echo "Test 3: Missing strategy key (should return 400)"
curl -X POST "${BASE_URL}/api/strategies" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_class": "stock",
    "name": "test_missing",
    "config": {}
  }'

echo -e "\n\n"

# Test 4: Invalid strategy name (path traversal attempt)
echo "Test 4: Invalid strategy name with path traversal (should return 422)"
curl -X POST "${BASE_URL}/api/strategies" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_class": "stock",
    "name": "../../../etc/passwd",
    "config": {"strategy": {}}
  }'

echo -e "\n\n"

# Test 5: Unknown entry type
echo "Test 5: Unknown entry type (should return 400)"
curl -X POST "${BASE_URL}/api/strategies" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_class": "stock",
    "name": "test_unknown_entry",
    "config": {
      "strategy": {
        "name": "test_unknown_entry",
        "asset_class": "stock",
        "enabled": true,
        "entry": {
          "type": "unknown_entry_type",
          "params": {}
        },
        "exit": {
          "type": "three_stage",
          "params": {}
        },
        "position": {
          "type": "fixed",
          "params": {}
        }
      }
    }
  }'

echo -e "\n\n"

echo "=========================================="
echo "Expected Results:"
echo "Test 1: 201 Created with success message and file_path"
echo "Test 2: 422 Unprocessable Entity (Pydantic validation)"
echo "Test 3: 400 Bad Request (missing 'strategy' key)"
echo "Test 4: 422 Unprocessable Entity (invalid name format)"
echo "Test 5: 400 Bad Request (unknown entry type)"
echo "=========================================="
