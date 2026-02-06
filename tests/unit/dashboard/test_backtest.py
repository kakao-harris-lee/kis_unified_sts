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
async def test_backtest_run(monkeypatch):
    """Test backtest run endpoint."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import backtest as backtest_routes

    import pandas as pd
    from datetime import datetime, timedelta

    base = datetime(2024, 1, 1, 9, 0)
    rows = []
    price = 100.0
    for i in range(60):
        price += 0.1
        rows.append(
            {
                "code": "005930",
                "name": "005930",
                "datetime": base + timedelta(minutes=i),
                "open": price - 0.2,
                "high": price + 0.3,
                "low": price - 0.4,
                "close": price,
                "volume": 1000 + i,
            }
        )
    df = pd.DataFrame(rows)

    monkeypatch.setattr(backtest_routes, "_fetch_ohlcv", lambda *args, **kwargs: df)
    monkeypatch.setattr(backtest_routes, "_generate_chart", lambda *args, **kwargs: None)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/backtest/run",
            json={
                "asset_class": "stock",
                "strategy": "bb_reversion",
                "symbol": "005930",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 10000000,
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
