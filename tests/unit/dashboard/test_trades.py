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


def _seed_runtime_ledger(db_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_trade(
        {
            "id": "trade-stock-1",
            "asset_class": "stock",
            "code": "005930",
            "name": "Samsung",
            "side": "long",
            "strategy": "bb_reversion",
            "entry_time": "2026-06-03T09:00:00+09:00",
            "entry_price": 71000.0,
            "exit_time": "2026-06-03T10:00:00+09:00",
            "exit_price": 72000.0,
            "quantity": 10,
            "exit_reason": "signal_exit",
        }
    )
    ledger.record_trade(
        {
            "id": "trade-futures-1",
            "asset_class": "futures",
            "code": "101S6000",
            "name": "KOSPI200 Futures",
            "side": "short",
            "strategy": "rl_mppo",
            "entry_time": "2026-06-03T09:00:00+09:00",
            "entry_price": 350.0,
            "exit_time": "2026-06-03T09:30:00+09:00",
            "exit_price": 345.0,
            "quantity": 1,
            "exit_reason": "model_exit",
        }
    )
    ledger.close()


def _seed_runtime_ledger_fill(db_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_fill(
        {
            "id": "fill-futures-1",
            "idempotency_key": "fill-futures-1",
            "fill_id": "broker-fill-1",
            "signal_id": "signal-futures-1",
            "order_id": "order-futures-1",
            "asset_class": "futures",
            "code": "101S6000",
            "side": "BUY",
            "filled_qty": 1,
            "filled_price": 350.25,
            "filled_at": "2026-06-03T09:01:00+09:00",
            "trade_role": "entry",
            "venue": "KIS",
        }
    )
    ledger.close()


def _create_empty_runtime_ledger(db_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    ledger = SQLiteRuntimeLedger(db_path)
    ledger.close()


def _configure_runtime_ledger_env(monkeypatch, db_path):
    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("DASHBOARD_TRADE_STATS_SOURCE", "runtime_ledger")


@pytest.mark.asyncio
async def test_trades_list_reads_runtime_ledger(monkeypatch, tmp_path):
    """``/api/trades`` should prefer RuntimeLedger when SQLite DB exists."""
    from services.dashboard.app import create_app

    db_path = tmp_path / "runtime.db"
    _seed_runtime_ledger(db_path)
    _configure_runtime_ledger_env(monkeypatch, db_path)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades?asset_class=stock")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["trades"][0]["id"] == "trade-stock-1"
    assert data["trades"][0]["symbol"] == "005930"
    assert data["trades"][0]["pnl"] == 10000.0


@pytest.mark.asyncio
async def test_trades_list_empty_ledger_does_not_fallback_to_redis(
    monkeypatch, tmp_path
):
    """An available empty ledger is authoritative for filtered list responses."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trades as trades_route

    db_path = tmp_path / "runtime.db"
    _create_empty_runtime_ledger(db_path)
    _configure_runtime_ledger_env(monkeypatch, db_path)

    def _stale_redis_trades(_asset):
        return [
            {
                "id": "stale-redis",
                "asset_class": "stock",
                "symbol": "005930",
                "strategy": "missing",
                "entry_time": "2026-06-03T09:00:00+09:00",
                "exit_time": "2026-06-03T10:00:00+09:00",
                "quantity": 1,
                "entry_price": 1,
                "exit_price": 2,
                "pnl": 1,
                "pnl_pct": 1,
            }
        ]

    monkeypatch.setattr(trades_route, "_load_trades", _stale_redis_trades)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/trades?asset_class=stock&strategy=missing"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["trades"] == []


@pytest.mark.asyncio
async def test_trade_statistics_empty_ledger_does_not_fallback_to_redis(
    monkeypatch, tmp_path
):
    """Statistics should use an available ledger even when it has zero rows."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trades as trades_route

    db_path = tmp_path / "runtime.db"
    _create_empty_runtime_ledger(db_path)
    _configure_runtime_ledger_env(monkeypatch, db_path)

    monkeypatch.setattr(
        trades_route,
        "_load_trades",
        lambda _asset: [
            {
                "id": "stale-redis",
                "asset_class": "stock",
                "symbol": "005930",
                "strategy": "bb_reversion",
                "entry_time": "2026-06-03T09:00:00+09:00",
                "exit_time": "2026-06-03T10:00:00+09:00",
                "quantity": 1,
                "entry_price": 1,
                "exit_price": 2,
                "pnl": 1,
                "pnl_pct": 1,
            }
        ],
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        stats = await client.get("/api/trades/statistics")
        by_strategy = await client.get("/api/trades/by-strategy")

    assert stats.status_code == 200
    assert stats.json()["total_trades"] == 0
    assert by_strategy.status_code == 200
    assert by_strategy.json() == []


@pytest.mark.asyncio
async def test_trades_rl_reads_runtime_ledger_without_clickhouse(monkeypatch, tmp_path):
    """``/api/trades/rl`` should not call ClickHouse when RuntimeLedger is configured."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trades as trades_route

    db_path = tmp_path / "runtime.db"
    _seed_runtime_ledger(db_path)
    _configure_runtime_ledger_env(monkeypatch, db_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("ClickHouse should not be queried")

    monkeypatch.setattr(trades_route, "_query_ch", _boom)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/rl?asset_class=futures")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "trade-futures-1"
    assert data[0]["code"] == "101S6000"
    assert data[0]["pnl"] == 5.0


@pytest.mark.asyncio
async def test_trades_rl_statistics_reads_runtime_ledger_without_clickhouse(
    monkeypatch, tmp_path
):
    """``/api/trades/rl/statistics`` should aggregate from RuntimeLedger."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trades as trades_route

    db_path = tmp_path / "runtime.db"
    _seed_runtime_ledger(db_path)
    _configure_runtime_ledger_env(monkeypatch, db_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("ClickHouse should not be queried")

    monkeypatch.setattr(trades_route, "_query_ch", _boom)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/rl/statistics?asset_class=all")

    assert response.status_code == 200
    data = response.json()
    assert data["total_trades"] == 2
    assert data["winning_trades"] == 2
    assert data["total_pnl"] == 10005.0


@pytest.mark.asyncio
async def test_trades_fills_reads_runtime_ledger_without_clickhouse(
    monkeypatch, tmp_path
):
    """``/api/trades/fills`` should prefer RuntimeLedger when configured."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import trades as trades_route

    db_path = tmp_path / "runtime.db"
    _seed_runtime_ledger_fill(db_path)
    _configure_runtime_ledger_env(monkeypatch, db_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("ClickHouse should not be queried")

    monkeypatch.setattr(trades_route, "_query_ch", _boom)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/fills?asset_class=futures")

    assert response.status_code == 200
    data = response.json()
    assert len(data["fills"]) == 1
    fill = data["fills"][0]
    assert fill["signal_id"] == "signal-futures-1"
    assert fill["symbol"] == "101S6000"
    assert fill["filled_price"] == 350.25
    assert fill["quantity"] == 1
    assert fill["trade_role"] == "entry"
    assert fill["asset_class"] == "futures"
    assert fill["order_id"] == "order-futures-1"


@pytest.mark.asyncio
async def test_trades_fills_returns_empty_on_ch_failure(monkeypatch):
    """``/api/trades/fills`` returns ``{"fills": []}`` when ClickHouse is unavailable.

    The route swallows any ClickHouse failure so the cockpit panel degrades
    gracefully instead of surfacing a 503. We patch the sync ``_query_ch``
    helper to raise — this exercises the except branch without needing a
    real ClickHouse cluster in CI.
    """
    from services.dashboard import routes as _routes  # noqa: F401  (force import)
    from services.dashboard.app import create_app
    from services.dashboard.routes import trades as trades_route

    def _boom(*_args, **_kwargs):
        raise RuntimeError("ClickHouse unavailable")

    monkeypatch.setattr(trades_route, "_query_ch", _boom)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/fills")

    assert response.status_code == 200
    data = response.json()
    assert data == {"fills": []}


@pytest.mark.asyncio
async def test_trades_fills_stock_short_circuits():
    """``asset_class=stock`` returns empty without touching ClickHouse.

    The ``order_fills`` table only contains futures fills (Phase 4 scope),
    so the route short-circuits non-futures asset classes.
    """
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/fills?asset_class=stock")

    assert response.status_code == 200
    assert response.json() == {"fills": []}


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
