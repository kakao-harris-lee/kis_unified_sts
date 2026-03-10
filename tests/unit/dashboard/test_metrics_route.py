"""Tests for dashboard venue metrics route."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_venue_metrics_endpoint_returns_clickhouse_counts(monkeypatch):
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


def test_collect_venue_metrics_sync_aggregates_multiple_databases(monkeypatch):
    """Helper should combine venue counts across unique stock/futures databases."""
    from services.dashboard.routes import metrics as metrics_route

    monkeypatch.setattr(
        metrics_route,
        "_candidate_databases",
        lambda: ["market", "kospi"],
    )

    def fake_query(database: str) -> dict[str, int]:
        return {
            "market": {"KRX": 2, "ATS": 1},
            "kospi": {"KRX": 4, "ATS": 3},
        }[database]

    monkeypatch.setattr(metrics_route, "_query_venue_counts_for_database", fake_query)

    result = metrics_route._collect_venue_metrics_sync()

    assert result["krx_count"] == 6
    assert result["ats_count"] == 4
    assert result["krx_fill_rate"] == 1.0
    assert result["ats_fill_rate"] == 1.0


def test_collect_venue_metrics_sync_returns_zero_on_no_counts(monkeypatch):
    """Helper should degrade gracefully when no persisted venue data exists."""
    from services.dashboard.routes import metrics as metrics_route

    monkeypatch.setattr(metrics_route, "_candidate_databases", lambda: ["market"])
    monkeypatch.setattr(
        metrics_route,
        "_query_venue_counts_for_database",
        lambda database: {"KRX": 0, "ATS": 0},
    )

    result = metrics_route._collect_venue_metrics_sync()

    assert result == {
        "krx_count": 0,
        "ats_count": 0,
        "krx_fill_rate": 0.0,
        "ats_fill_rate": 0.0,
        "avg_price_improvement_bps": 0.0,
        "ats_price_improvement_bps": 0.0,
    }