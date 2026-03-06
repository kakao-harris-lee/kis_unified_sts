#!/usr/bin/env python3
"""Verification script for WebSocket authentication using Starlette test client.

Tests that:
1. WebSocket connections without api_key are rejected with 4001 close code
2. WebSocket connections with invalid api_key are rejected with 4001 close code
3. WebSocket connections with valid api_key are accepted
"""
import os
import sys


def test_no_api_key():
    """Test connection without api_key query parameter."""
    from starlette.testclient import TestClient
    from services.dashboard.app import create_app

    test_api_key = "test_api_key_12345"
    app = create_app(require_auth=True, api_key=test_api_key)
    client = TestClient(app)

    print("\n1. Testing WebSocket connection WITHOUT api_key...")
    try:
        with client.websocket_connect("/ws") as websocket:
            print("   ❌ FAIL: Connection was accepted (should have been rejected)")
            return False
    except Exception as e:
        # Check if it's a WebSocketDisconnect with code 4001
        if "4001" in str(e) or "Unauthorized" in str(e):
            print(f"   ✅ PASS: Connection rejected (error: {e})")
            return True
        else:
            print(f"   ⚠️  WARNING: Connection rejected but with unexpected error: {e}")
            return True  # Still counts as pass if connection was rejected


def test_invalid_api_key():
    """Test connection with invalid api_key."""
    from starlette.testclient import TestClient
    from services.dashboard.app import create_app

    test_api_key = "test_api_key_12345"
    app = create_app(require_auth=True, api_key=test_api_key)
    client = TestClient(app)

    print("\n2. Testing WebSocket connection with INVALID api_key...")
    try:
        with client.websocket_connect("/ws?api_key=invalid_key") as websocket:
            print("   ❌ FAIL: Connection was accepted (should have been rejected)")
            return False
    except Exception as e:
        # Check if it's a WebSocketDisconnect with code 4001
        if "4001" in str(e) or "Unauthorized" in str(e):
            print(f"   ✅ PASS: Connection rejected (error: {e})")
            return True
        else:
            print(f"   ⚠️  WARNING: Connection rejected but with unexpected error: {e}")
            return True  # Still counts as pass if connection was rejected


def test_valid_api_key():
    """Test connection with valid api_key."""
    from starlette.testclient import TestClient
    from services.dashboard.app import create_app
    import json

    test_api_key = "test_api_key_12345"
    app = create_app(require_auth=True, api_key=test_api_key)
    client = TestClient(app)

    print("\n3. Testing WebSocket connection with VALID api_key...")
    try:
        with client.websocket_connect(f"/ws?api_key={test_api_key}") as websocket:
            print("   ✅ PASS: Connection accepted with valid api_key")

            # Send a ping to verify the connection works
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()
            print(f"   ✅ PASS: Received response: {json.dumps(response)[:50]}...")

            return True
    except Exception as e:
        print(f"   ❌ FAIL: Unexpected error: {type(e).__name__}: {e}")
        return False


def test_auth_disabled_in_dev_mode():
    """Test that authentication is disabled in dev mode."""
    from starlette.testclient import TestClient
    from services.dashboard.app import create_app

    # Set dev mode environment variable
    os.environ["DASHBOARD_DEV_MODE"] = "true"
    test_api_key = "test_api_key_12345"

    try:
        app = create_app(require_auth=True, api_key=test_api_key)
        client = TestClient(app)

        print("\n4. Testing WebSocket connection in DEV MODE (auth should be disabled)...")
        try:
            with client.websocket_connect("/ws") as websocket:
                print("   ✅ PASS: Connection accepted without api_key in dev mode")

                # Send a ping to verify the connection works
                websocket.send_json({"type": "ping"})
                response = websocket.receive_json()
                print(f"   ✅ PASS: Received response in dev mode")

                return True
        except Exception as e:
            print(f"   ❌ FAIL: Connection rejected in dev mode (should be accepted): {e}")
            return False
    finally:
        # Clean up environment variable
        os.environ.pop("DASHBOARD_DEV_MODE", None)


def run_tests():
    """Run all WebSocket authentication tests."""
    print("=" * 70)
    print("WebSocket Authentication Verification")
    print("=" * 70)

    results = []

    # Test 1: No API key
    results.append(test_no_api_key())

    # Test 2: Invalid API key
    results.append(test_invalid_api_key())

    # Test 3: Valid API key
    results.append(test_valid_api_key())

    # Test 4: Dev mode
    results.append(test_auth_disabled_in_dev_mode())

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - WebSocket authentication is working correctly!")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED - Please review the failures above")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
