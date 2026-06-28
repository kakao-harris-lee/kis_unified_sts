from __future__ import annotations

from fastapi.testclient import TestClient

from services.dashboard.app import create_app


def test_evidence_summary_returns_asset_and_strategy_groups(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DEV_MODE", "true")
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/evidence/summary?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_class"] == "futures"
    assert "strategies" in body
    assert "generated_at" in body
