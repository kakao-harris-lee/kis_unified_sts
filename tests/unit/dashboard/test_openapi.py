"""Test OpenAPI documentation."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_openapi_json_available():
    """Test OpenAPI JSON schema is available."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "KIS Unified Trading Dashboard"


@pytest.mark.asyncio
async def test_openapi_has_tags():
    """Test OpenAPI schema includes tags for organization."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    data = response.json()
    assert "tags" in data
    tag_names = [tag["name"] for tag in data["tags"]]
    assert "trading" in tag_names
    assert "signals" in tag_names
    assert "trades" in tag_names


@pytest.mark.asyncio
async def test_docs_endpoint_available():
    """Test Swagger UI docs endpoint is available."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/docs")

    # Should redirect or return HTML
    assert response.status_code in [200, 307]


@pytest.mark.asyncio
async def test_redoc_endpoint_available():
    """Test ReDoc endpoint is available."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/redoc")

    assert response.status_code in [200, 307]
