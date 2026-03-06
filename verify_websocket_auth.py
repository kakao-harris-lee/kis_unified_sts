#!/usr/bin/env python3
"""Verification script for WebSocket authentication.

Tests that:
1. WebSocket connections without api_key are rejected with 4001 close code
2. WebSocket connections with invalid api_key are rejected with 4001 close code
3. WebSocket connections with valid api_key are accepted
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager

import websockets
from websockets.exceptions import ConnectionClosedError


async def test_no_api_key(base_url: str) -> bool:
    """Test connection without api_key query parameter."""
    print("\n1. Testing WebSocket connection WITHOUT api_key...")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

    try:
        async with websockets.connect(f"{ws_url}/ws", close_timeout=2) as websocket:
            print("   ❌ FAIL: Connection was accepted (should have been rejected)")
            return False
    except ConnectionClosedError as e:
        if e.code == 4001:
            print(f"   ✅ PASS: Connection rejected with code 4001 (reason: {e.reason})")
            return True
        else:
            print(f"   ❌ FAIL: Connection closed with unexpected code {e.code} (expected 4001)")
            return False
    except Exception as e:
        print(f"   ❌ FAIL: Unexpected error: {type(e).__name__}: {e}")
        return False


async def test_invalid_api_key(base_url: str) -> bool:
    """Test connection with invalid api_key."""
    print("\n2. Testing WebSocket connection with INVALID api_key...")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

    try:
        async with websockets.connect(f"{ws_url}/ws?api_key=invalid_key", close_timeout=2) as websocket:
            print("   ❌ FAIL: Connection was accepted (should have been rejected)")
            return False
    except ConnectionClosedError as e:
        if e.code == 4001:
            print(f"   ✅ PASS: Connection rejected with code 4001 (reason: {e.reason})")
            return True
        else:
            print(f"   ❌ FAIL: Connection closed with unexpected code {e.code} (expected 4001)")
            return False
    except Exception as e:
        print(f"   ❌ FAIL: Unexpected error: {type(e).__name__}: {e}")
        return False


async def test_valid_api_key(base_url: str, api_key: str) -> bool:
    """Test connection with valid api_key."""
    print("\n3. Testing WebSocket connection with VALID api_key...")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

    try:
        async with websockets.connect(f"{ws_url}/ws?api_key={api_key}", close_timeout=2) as websocket:
            print("   ✅ PASS: Connection accepted with valid api_key")

            # Send a ping to verify the connection works
            await websocket.send('{"type": "ping"}')
            response = await asyncio.wait_for(websocket.recv(), timeout=2)
            print(f"   ✅ PASS: Received response: {response[:50]}...")

            return True
    except ConnectionClosedError as e:
        print(f"   ❌ FAIL: Connection closed unexpectedly with code {e.code}")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Unexpected error: {type(e).__name__}: {e}")
        return False


async def run_tests(base_url: str, api_key: str):
    """Run all WebSocket authentication tests."""
    print("=" * 70)
    print("WebSocket Authentication Verification")
    print("=" * 70)
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:8]}...")

    results = []

    # Test 1: No API key
    results.append(await test_no_api_key(base_url))

    # Test 2: Invalid API key
    results.append(await test_invalid_api_key(base_url))

    # Test 3: Valid API key
    results.append(await test_valid_api_key(base_url, api_key))

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
        print("\n❌ SOME TESTS FAILED - Please review the failures above")
        return 1


async def start_test_server():
    """Start a test dashboard server with authentication enabled."""
    from services.dashboard.app import create_app
    import uvicorn

    # Generate a test API key
    test_api_key = "test_api_key_12345"

    # Create app with authentication enabled
    app = create_app(
        title="Test Dashboard",
        debug=True,
        require_auth=True,
        api_key=test_api_key,
    )

    # Start server in background
    config = uvicorn.Config(app, host="127.0.0.1", port=8888, log_level="warning")
    server = uvicorn.Server(config)

    return server, test_api_key


async def main():
    """Main entry point."""
    # Check if we should start our own server or use an existing one
    base_url = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8888")
    api_key = os.environ.get("DASHBOARD_API_KEY")

    if api_key:
        # Use existing server
        print(f"Using existing dashboard at {base_url}")
        return await run_tests(base_url, api_key)
    else:
        # Start our own test server
        print("Starting test dashboard server...")
        server, test_api_key = await start_test_server()

        # Run server in background
        server_task = asyncio.create_task(server.serve())

        # Wait a bit for server to start
        await asyncio.sleep(1)

        try:
            result = await run_tests(base_url, test_api_key)
            return result
        finally:
            # Shutdown server
            print("\nShutting down test server...")
            server.should_exit = True
            await server_task


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
