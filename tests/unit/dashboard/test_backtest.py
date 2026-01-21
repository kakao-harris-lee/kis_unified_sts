"""Test backtest endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_backtest_list():
    """Test backtest list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/backtest")

    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_backtest_run():
    """Test backtest run endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/backtest/run",
            json={
                "strategy": "v35_optimized",
                "symbol": "005930",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_backtest_result():
    """Test backtest result endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/backtest/test-run-id")

    # Returns 404 for non-existent run
    assert response.status_code in [200, 404]
