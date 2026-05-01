"""Test trades endpoints."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient


def test_parse_tz_aware_naive_iso_attaches_utc():
    """Naive ISO string → tz-aware UTC (matches signals.py / trading.py)."""
    from services.dashboard.routes.trades import _parse_tz_aware

    result = _parse_tz_aware("2026-05-01T09:00:00")
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_parse_tz_aware_aware_iso_converts_to_utc():
    """Aware ISO string with non-UTC offset → converted to UTC."""
    from services.dashboard.routes.trades import _parse_tz_aware

    # 2026-05-01 18:00 KST = 2026-05-01 09:00 UTC
    result = _parse_tz_aware("2026-05-01T18:00:00+09:00")
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)
    assert result.hour == 9


def test_parse_tz_aware_none_falls_back_to_now_utc():
    """None input → datetime.now(UTC) (tz-aware, never naive)."""
    from services.dashboard.routes.trades import _parse_tz_aware

    result = _parse_tz_aware(None)
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_parse_tz_aware_invalid_iso_falls_back_to_now_utc():
    """Garbage input → fallback (no crash)."""
    from services.dashboard.routes.trades import _parse_tz_aware

    result = _parse_tz_aware("not-a-date")
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_trades_list():
    """Test trades list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades")

    assert response.status_code == 200
    data = response.json()
    assert "trades" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_trades_statistics():
    """Test trades statistics endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/statistics")

    assert response.status_code == 200
    data = response.json()
    assert "total_trades" in data
    assert "win_rate" in data
    assert "total_pnl" in data


@pytest.mark.asyncio
async def test_trades_by_strategy():
    """Test trades by strategy endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/by-strategy")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
