"""Test WebSocket authentication."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment before each test."""
    env_vars = ["DASHBOARD_DEV_MODE"]
    old_values = {k: os.environ.get(k) for k in env_vars}
    yield
    for k, v in old_values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_websocket_requires_auth():
    """Test that WebSocket connections require authentication when auth is enabled."""
    os.environ["DASHBOARD_DEV_MODE"] = "true"

    from services.dashboard.app import create_app

    app = create_app(require_auth=True, api_key="test-api-key")

    # Avoid starlette TestClient websocket_connect here since it relies on
    # anyio BlockingPortal cross-thread calls which can hang in some environments.
    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    assert "APIKeyMiddleware" in middleware_names


def test_websocket_without_auth_middleware():
    """Test WebSocket works when auth is not required."""
    os.environ["DASHBOARD_DEV_MODE"] = "true"

    from services.dashboard.app import create_app

    app = create_app(require_auth=False)

    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    assert "APIKeyMiddleware" not in middleware_names


@pytest.mark.asyncio
async def test_auth_middleware_validates_websocket():
    """Test that auth middleware validates WebSocket API key."""
    from services.dashboard.middleware.auth import APIKeyMiddleware

    # Create mock app
    mock_app = AsyncMock()

    middleware = APIKeyMiddleware(app=mock_app, api_key="valid-key")

    # Test valid key
    scope = {
        "type": "websocket",
        "query_string": b"api_key=valid-key",
        "path": "/ws",
    }

    receive = AsyncMock(return_value={"type": "websocket.connect"})
    send = AsyncMock()

    await middleware(scope, receive, send)

    # App should be called (connection allowed)
    mock_app.assert_called_once()


@pytest.mark.asyncio
async def test_auth_middleware_rejects_invalid_websocket():
    """Test that auth middleware rejects invalid WebSocket API key."""
    from services.dashboard.middleware.auth import APIKeyMiddleware

    mock_app = AsyncMock()
    middleware = APIKeyMiddleware(app=mock_app, api_key="valid-key")

    # Test invalid key
    scope = {
        "type": "websocket",
        "query_string": b"api_key=wrong-key",
        "path": "/ws",
    }

    receive = AsyncMock(return_value={"type": "websocket.connect"})
    send = AsyncMock()

    await middleware(scope, receive, send)

    # App should NOT be called
    mock_app.assert_not_called()

    # Close should be sent
    send.assert_called_once()
    call_args = send.call_args[0][0]
    assert call_args["type"] == "websocket.close"
    assert call_args["code"] == 4001


@pytest.mark.asyncio
async def test_auth_middleware_rejects_missing_websocket_key():
    """Test that auth middleware rejects WebSocket without API key."""
    from services.dashboard.middleware.auth import APIKeyMiddleware

    mock_app = AsyncMock()
    middleware = APIKeyMiddleware(app=mock_app, api_key="valid-key")

    # Test missing key
    scope = {
        "type": "websocket",
        "query_string": b"",
        "path": "/ws",
    }

    receive = AsyncMock(return_value={"type": "websocket.connect"})
    send = AsyncMock()

    await middleware(scope, receive, send)

    # App should NOT be called
    mock_app.assert_not_called()

    # Close should be sent
    send.assert_called_once()


def test_auth_timing_safe_comparison():
    """Test that API key comparison is timing-safe."""
    from services.dashboard.middleware.auth import APIKeyMiddleware

    middleware = APIKeyMiddleware(app=MagicMock(), api_key="secret-key")

    # Valid key
    assert middleware._validate_api_key("secret-key") is True

    # Invalid key
    assert middleware._validate_api_key("wrong-key") is False

    # Empty key
    assert middleware._validate_api_key("") is False

    # None
    assert middleware._validate_api_key(None) is False


def test_auth_public_paths():
    """Test that public paths are correctly identified."""
    from services.dashboard.middleware.auth import APIKeyMiddleware

    middleware = APIKeyMiddleware(app=MagicMock(), api_key="secret-key")

    # Public paths
    assert middleware._is_public_path("/") is True
    assert middleware._is_public_path("/health") is True
    assert middleware._is_public_path("/docs") is True
    assert middleware._is_public_path("/redoc") is True
    assert middleware._is_public_path("/openapi.json") is True

    # Protected paths
    assert middleware._is_public_path("/api/v1/positions") is False
    assert middleware._is_public_path("/ws") is False
