"""Test trading status endpoints."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def test_parse_tz_aware_round_trip_through_naive():
    """Same contract as trades.py: tz-aware UTC out, regardless of input."""
    from services.dashboard.routes.trading import _parse_tz_aware

    naive = _parse_tz_aware("2026-05-01T09:00:00")
    assert naive.tzinfo is not None and naive.utcoffset() == timedelta(0)

    aware = _parse_tz_aware("2026-05-01T18:00:00+09:00")
    assert aware.tzinfo is not None and aware.hour == 9

    fallback = _parse_tz_aware(None)
    assert fallback.tzinfo is not None and fallback.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_trading_status():
    """Test trading status endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/status")

    assert response.status_code == 200
    data = response.json()
    assert "is_running" in data
    assert "market_status" in data


@pytest.mark.asyncio
async def test_trading_status_account_passthrough():
    """`account` block from orchestrator status survives Redis → dashboard route.

    Without this passthrough, Cockpit's EquityCashCard would never render
    (account would be stripped by Pydantic response model).
    """
    from services.dashboard.app import create_app
    from services.dashboard.routes import trading as _trading_route

    mock_reader = MagicMock()
    mock_reader.get_status.return_value = {
        "state": "running",
        "config": {"strategy": "rl_mppo", "asset_class": "futures"},
        "stats": {"total_pnl": 1234.0, "start_time": "2026-05-15T00:00:00+00:00"},
        "positions": {"open_positions": 2, "unrealized_pnl": 2500000.0},
        "regime": "neutral",
        "account": {
            "initial_balance": 100_000_000.0,
            "balance": 95_000_000.0,
            "equity": 97_500_000.0,
            "realized_pnl": -3_000_000.0,
            "unrealized_pnl": 2_500_000.0,
            "open_positions": 2,
        },
    }
    with patch.object(_trading_route, "_get_reader", return_value=mock_reader):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/trading/status")

    assert response.status_code == 200
    body = response.json()
    assert body["account"] is not None
    acct = body["account"]
    assert acct["initial_balance"] == pytest.approx(100_000_000.0)
    assert acct["balance"] == pytest.approx(95_000_000.0)
    assert acct["equity"] == pytest.approx(97_500_000.0)
    assert acct["realized_pnl"] == pytest.approx(-3_000_000.0)
    assert acct["unrealized_pnl"] == pytest.approx(2_500_000.0)
    assert acct["open_positions"] == 2


@pytest.mark.asyncio
async def test_trading_status_account_null_when_absent():
    """status에 account가 없으면(live 모드 등) account 필드는 null."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trading as _trading_route

    mock_reader = MagicMock()
    mock_reader.get_status.return_value = {
        "state": "running",
        "config": {"strategy": "rl_mppo"},
        "stats": {"start_time": "2026-05-15T00:00:00+00:00"},
        "positions": {},
        "regime": "neutral",
        # no account key
    }
    with patch.object(_trading_route, "_get_reader", return_value=mock_reader):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/trading/status")

    assert response.status_code == 200
    assert response.json()["account"] is None


@pytest.mark.asyncio
async def test_trading_status_account_decodes_json_string():
    """account가 JSON string으로 들어와도 디코딩하여 통과 (defensive path).

    Redis HASH 직접 조작이나 reader 일부 경로에서 string으로 들어올 수 있다.
    """
    import json as _json

    from services.dashboard.app import create_app
    from services.dashboard.routes import trading as _trading_route

    mock_reader = MagicMock()
    mock_reader.get_status.return_value = {
        "state": "running",
        "config": {},
        "stats": {"start_time": "2026-05-15T00:00:00+00:00"},
        "positions": {},
        "regime": "neutral",
        "account": _json.dumps(
            {
                "initial_balance": 100_000_000.0,
                "balance": 99_000_000.0,
                "equity": 99_000_000.0,
                "realized_pnl": -1_000_000.0,
                "unrealized_pnl": 0.0,
                "open_positions": 0,
            }
        ),
    }
    with patch.object(_trading_route, "_get_reader", return_value=mock_reader):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/trading/status")

    assert response.status_code == 200
    acct = response.json()["account"]
    assert acct is not None
    assert acct["balance"] == pytest.approx(99_000_000.0)
    assert acct["realized_pnl"] == pytest.approx(-1_000_000.0)


@pytest.mark.asyncio
async def test_trading_status_last_update_uses_status_updated_at():
    """Dashboard freshness should reflect the Redis publish time, not session start."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trading as _trading_route

    mock_reader = MagicMock()
    mock_reader.get_status.return_value = {
        "state": "running",
        "config": {},
        "stats": {"start_time": "2026-05-15T00:00:00+00:00"},
        "positions": {},
        "regime": "neutral",
        "updated_at": "2026-05-15T00:05:00+00:00",
    }
    with patch.object(_trading_route, "_get_reader", return_value=mock_reader):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/trading/status")

    assert response.status_code == 200
    assert response.json()["last_update"].startswith("2026-05-15T00:05:00")


@pytest.mark.asyncio
async def test_positions_list():
    """Test positions list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/positions")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_start_trading():
    """Test start trading endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/trading/start")

    assert response.status_code == 200
    assert response.json()["status"] == "use CLI: sts trade start"


@pytest.mark.asyncio
async def test_stop_trading():
    """Test stop trading endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/trading/stop")

    assert response.status_code == 200
    assert response.json()["status"] == "use CLI: sts trade stop"


@pytest.mark.asyncio
async def test_kill_switch_success():
    """Successful kill-switch publishes to Redis and returns triggered=true."""
    from services.dashboard.app import create_app

    mock_redis = MagicMock()
    with patch(
        "shared.streaming.client.RedisClient.get_client",
        return_value=mock_redis,
    ):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/trading/kill-switch")

    assert response.status_code == 200
    body = response.json()
    assert body["triggered"] is True
    assert "at" in body
    mock_redis.publish.assert_called_once_with(
        "kill_switch:force_flatten:requested", "manual_dashboard"
    )


@pytest.mark.asyncio
async def test_kill_switch_redis_down_graceful():
    """Redis-down path returns 200 with triggered=false (no 500)."""
    from services.dashboard.app import create_app

    with patch(
        "shared.streaming.client.RedisClient.get_client",
        side_effect=RuntimeError("redis unavailable"),
    ):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/trading/kill-switch")

    assert response.status_code == 200
    body = response.json()
    assert body["triggered"] is False
    assert "error" in body
    assert "redis unavailable" in body["error"]
    assert "at" in body
