"""Test CORS configuration security for the dashboard app."""
import os
import pytest
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test."""
    env_vars = ["ENVIRONMENT"]
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
    os.environ["ENVIRONMENT"] = "production"

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
async def test_cors_allows_localhost_origin_in_dev():
    """Test that CORS allows requests from localhost origins in development mode."""
    os.environ["ENVIRONMENT"] = "development"

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
    """Test that CORS allows requests from Vite dev server when using default config."""
    os.environ["ENVIRONMENT"] = "development"

    # Mock config loader to return empty config — tests default origins
    with patch("services.dashboard.app.load_api_config", return_value={}):
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
async def test_cors_dev_mode_uses_explicit_origins():
    """Test that dev mode uses explicit localhost origins, not wildcard."""
    os.environ["ENVIRONMENT"] = "development"

    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://any-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # In dev mode, arbitrary external origins should NOT be allowed
        origin_header = response.headers.get("access-control-allow-origin")
        assert origin_header != "https://any-site.com"


@pytest.mark.asyncio
async def test_cors_methods_restricted():
    """Test that CORS only allows necessary HTTP methods."""
    os.environ["ENVIRONMENT"] = "development"

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
