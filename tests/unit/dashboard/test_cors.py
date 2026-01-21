"""Test CORS configuration security."""
import os
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test."""
    env_vars = ["DASHBOARD_DEV_MODE"]
    old_values = {k: os.environ.get(k) for k in env_vars}
    yield
    for k, v in old_values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin():
    """Test that CORS rejects requests from unknown origins in production mode."""
    os.environ["DASHBOARD_DEV_MODE"] = "false"

    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should not have Access-Control-Allow-Origin for unknown origin
        origin_header = response.headers.get("access-control-allow-origin")
        assert origin_header != "https://malicious-site.com"


@pytest.mark.asyncio
async def test_cors_allows_localhost_origin():
    """Test that CORS allows requests from localhost origins."""
    os.environ["DASHBOARD_DEV_MODE"] = "false"

    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should allow localhost:3000
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_allows_vite_dev_server():
    """Test that CORS allows requests from Vite dev server."""
    os.environ["DASHBOARD_DEV_MODE"] = "false"

    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_dev_mode_allows_any_origin():
    """Test that dev mode allows any origin for development convenience."""
    os.environ["DASHBOARD_DEV_MODE"] = "true"

    # Need to reimport to pick up new env
    import importlib
    import services.dashboard.app as app_module

    importlib.reload(app_module)

    app = app_module.create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://any-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # In dev mode, any origin should be allowed
        assert response.headers.get("access-control-allow-origin") == "https://any-site.com"


@pytest.mark.asyncio
async def test_cors_methods_restricted():
    """Test that CORS only allows necessary HTTP methods."""
    os.environ["DASHBOARD_DEV_MODE"] = "false"

    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        allowed_methods = response.headers.get("access-control-allow-methods", "")
        # Should have specific methods, not wildcard
        assert "GET" in allowed_methods
        assert "POST" in allowed_methods
