"""Test CORS configuration security for the dashboard app."""
import os
import pytest
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient


def _reset_config_loader() -> None:
    """Drop the ConfigLoader singleton so the next load re-resolves its dir."""
    try:
        from shared.config.loader import ConfigLoader

        ConfigLoader._instance = None
        ConfigLoader._config_dir = None
        ConfigLoader._cache.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def clean_env():
    """Isolate CORS tests from full-suite config pollution.

    ``create_app()`` resolves CORS origins through ``ConfigLoader``. A prior
    test in the full suite that leaves ``KIS_CONFIG_DIR`` pointing at a fixture
    config lacking the ``development`` overlay makes ``load_api_config()`` skip
    the dev merge and serve production origins, so the localhost CORS header
    silently disappears (these tests pass in isolation but fail in the full
    suite). Clear that override and reset the ConfigLoader singleton so
    create_app() always loads the repo's real config/api.yaml.
    """
    env_vars = ["ENVIRONMENT", "KIS_CONFIG_DIR"]
    old_values = {k: os.environ.get(k) for k in env_vars}
    # Drop any leaked config-dir override so ConfigLoader falls back to the
    # repo's config/ (which carries the development overlay).
    os.environ.pop("KIS_CONFIG_DIR", None)
    _reset_config_loader()
    yield
    for k, v in old_values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _reset_config_loader()


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
                "Origin": "http://localhost:5080",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should allow localhost:5080 (canonical dashboard port; see CLAUDE.md)
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5080"


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
