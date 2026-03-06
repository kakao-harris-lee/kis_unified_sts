#!/usr/bin/env python3
"""
HTTP Authentication Verification Script for Dashboard Endpoints

This script verifies that dashboard HTTP endpoints properly enforce
API key authentication via X-API-Key header.

Usage:
    python verify_http_auth.py

Requirements:
    - starlette
    - httpx
    - fastapi

Install:
    pip install starlette httpx fastapi
"""
import os
import sys
from typing import Dict, Tuple


def test_http_auth_with_testclient() -> bool:
    """
    Test HTTP authentication using Starlette TestClient.

    Returns:
        True if all tests pass, False otherwise.
    """
    try:
        from starlette.testclient import TestClient
        from services.dashboard.app import create_app
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Please install required packages: pip install starlette httpx fastapi")
        return False

    print("=" * 80)
    print("HTTP Authentication Verification")
    print("=" * 80)
    print()

    # Test configuration
    test_api_key = "test-secret-key-12345"

    # Create app with authentication enabled
    print("Setting up test app with authentication enabled...")
    os.environ["DASHBOARD_API_KEY"] = test_api_key
    os.environ.pop("DASHBOARD_DEV_MODE", None)  # Ensure dev mode is off

    app = create_app(require_auth=True, api_key=test_api_key)
    client = TestClient(app)

    all_tests_passed = True

    # Test 1: Protected endpoint without API key → 401
    print("\n[Test 1] Protected endpoint without API key")
    print("-" * 80)
    response = client.get("/api/trading/status")
    expected_status = 401
    actual_status = response.status_code

    if actual_status == expected_status:
        print(f"✅ PASS: Returned {actual_status} Unauthorized")
        try:
            error_detail = response.json().get("detail", "")
            print(f"   Error message: '{error_detail}'")
        except:
            pass
    else:
        print(f"❌ FAIL: Expected {expected_status}, got {actual_status}")
        print(f"   Response: {response.text[:200]}")
        all_tests_passed = False

    # Test 2: Protected endpoint with invalid API key → 401
    print("\n[Test 2] Protected endpoint with invalid API key")
    print("-" * 80)
    response = client.get(
        "/api/trading/status",
        headers={"X-API-Key": "wrong-key"}
    )
    expected_status = 401
    actual_status = response.status_code

    if actual_status == expected_status:
        print(f"✅ PASS: Returned {actual_status} Unauthorized")
    else:
        print(f"❌ FAIL: Expected {expected_status}, got {actual_status}")
        print(f"   Response: {response.text[:200]}")
        all_tests_passed = False

    # Test 3: Protected endpoint with valid API key → 200 or 500
    # (500 is acceptable because Redis/dependencies may not be available)
    print("\n[Test 3] Protected endpoint with valid API key")
    print("-" * 80)
    response = client.get(
        "/api/trading/status",
        headers={"X-API-Key": test_api_key}
    )
    actual_status = response.status_code

    # Authentication passed if we get past 401
    if actual_status != 401:
        print(f"✅ PASS: Authentication succeeded (status {actual_status})")
        if actual_status == 200:
            print("   Note: Full endpoint functionality working")
        elif actual_status >= 500:
            print("   Note: Backend service unavailable (expected in test env)")
    else:
        print(f"❌ FAIL: Valid API key rejected with {actual_status}")
        print(f"   Response: {response.text[:200]}")
        all_tests_passed = False

    # Test 4: Public endpoint without API key → 200
    print("\n[Test 4] Public endpoint (/health) without API key")
    print("-" * 80)
    response = client.get("/health")
    expected_status = 200
    actual_status = response.status_code

    if actual_status == expected_status:
        print(f"✅ PASS: Returned {actual_status} OK")
        try:
            health_data = response.json()
            print(f"   Response: {health_data}")
        except:
            pass
    else:
        print(f"❌ FAIL: Expected {expected_status}, got {actual_status}")
        print(f"   Response: {response.text[:200]}")
        all_tests_passed = False

    # Test 5: Public endpoint (/docs) without API key → 200
    print("\n[Test 5] Public endpoint (/docs) without API key")
    print("-" * 80)
    response = client.get("/docs")
    expected_status = 200
    actual_status = response.status_code

    if actual_status == expected_status:
        print(f"✅ PASS: Returned {actual_status} OK")
    else:
        print(f"❌ FAIL: Expected {expected_status}, got {actual_status}")
        all_tests_passed = False

    # Test 6: Root endpoint (/) without API key → 200
    print("\n[Test 6] Public endpoint (/) without API key")
    print("-" * 80)
    response = client.get("/")
    expected_status = 200
    actual_status = response.status_code

    if actual_status == expected_status:
        print(f"✅ PASS: Returned {actual_status} OK (Dashboard HTML)")
    else:
        print(f"❌ FAIL: Expected {expected_status}, got {actual_status}")
        all_tests_passed = False

    # Test 7: Dev mode disables authentication
    print("\n[Test 7] Dev mode disables authentication")
    print("-" * 80)
    os.environ["DASHBOARD_DEV_MODE"] = "true"
    app_dev = create_app()
    client_dev = TestClient(app_dev)

    response = client_dev.get("/api/trading/status")
    actual_status = response.status_code

    # In dev mode, should NOT return 401 (authentication disabled)
    if actual_status != 401:
        print(f"✅ PASS: Dev mode disabled auth (status {actual_status})")
    else:
        print(f"❌ FAIL: Dev mode still requiring authentication")
        all_tests_passed = False

    # Cleanup
    os.environ.pop("DASHBOARD_API_KEY", None)
    os.environ.pop("DASHBOARD_DEV_MODE", None)

    # Summary
    print("\n" + "=" * 80)
    if all_tests_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nConclusion:")
        print("  - Protected endpoints require X-API-Key header")
        print("  - Missing/invalid API key returns 401 Unauthorized")
        print("  - Valid API key allows access")
        print("  - Public endpoints accessible without authentication")
        print("  - Dev mode properly disables authentication")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        return False


def main():
    """Main entry point."""
    print("HTTP Authentication Verification Script")
    print("Subtask: subtask-4-3")
    print()

    success = test_http_auth_with_testclient()

    if success:
        print("\n✅ Verification complete - HTTP authentication working correctly")
        sys.exit(0)
    else:
        print("\n❌ Verification failed - see errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()
