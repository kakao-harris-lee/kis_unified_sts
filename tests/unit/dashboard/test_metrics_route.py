"""Tests for dashboard venue metrics route."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_venue_metrics_endpoint_returns_persisted_counts(monkeypatch):
    """Venue metrics endpoint should surface aggregated persisted counts."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import metrics as metrics_route

    monkeypatch.setattr(
        metrics_route,
        "_collect_venue_metrics_sync",
        lambda: {
            "krx_count": 7,
            "ats_count": 3,
            "krx_fill_rate": 1.0,
            "ats_fill_rate": 1.0,
            "avg_price_improvement_bps": 0.0,
            "ats_price_improvement_bps": 0.0,
        },
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/metrics/venue")

    assert response.status_code == 200
    assert response.json()["krx_count"] == 7
    assert response.json()["ats_count"] == 3


def test_collect_venue_metrics_sync_aggregates_multiple_databases(
    monkeypatch, tmp_path
):
    """Helper should combine venue counts across stock/futures RuntimeLedger fills."""
    from services.dashboard.routes import metrics as metrics_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(db_path))
    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_fill(
        {
            "fill_id": "stock-krx-1",
            "asset_class": "stock",
            "symbol": "005930",
            "side": "buy",
            "quantity": 1,
            "price": 100.0,
            "venue": "KRX",
        }
    )
    ledger.record_fill(
        {
            "fill_id": "futures-ats-1",
            "asset_class": "futures",
            "symbol": "101S6000",
            "side": "buy",
            "quantity": 1,
            "price": 350.0,
            "venue": "ATS",
        }
    )
    ledger.close()

    result = metrics_route._collect_venue_metrics_sync()

    assert result["krx_count"] == 1
    assert result["ats_count"] == 1
    assert result["krx_fill_rate"] == 1.0
    assert result["ats_fill_rate"] == 1.0


def test_collect_venue_metrics_sync_returns_zero_on_no_counts(monkeypatch, tmp_path):
    """Helper should degrade gracefully when no persisted venue data exists."""
    from services.dashboard.routes import metrics as metrics_route

    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(tmp_path / "missing.db"))

    result = metrics_route._collect_venue_metrics_sync()

    assert result == {
        "krx_count": 0,
        "ats_count": 0,
        "krx_fill_rate": 0.0,
        "ats_fill_rate": 0.0,
        "avg_price_improvement_bps": 0.0,
        "ats_price_improvement_bps": 0.0,
    }
