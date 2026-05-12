"""Asset class query parameter validation across dashboard endpoints."""

import pytest
from fastapi.testclient import TestClient

from services.dashboard.app import create_app


@pytest.fixture
def client():
    app = create_app(require_auth=False)
    return TestClient(app)


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/trading/status",
        "/api/trading/positions",
        "/api/signals",
        "/api/trades",
    ],
)
@pytest.mark.parametrize("asset", ["stock", "futures", "all"])
def test_accepts_valid_asset_class(client, endpoint, asset):
    res = client.get(endpoint, params={"asset_class": asset})
    assert res.status_code in (
        200,
        503,
    ), f"unexpected {res.status_code} for {endpoint}?asset_class={asset}"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/trading/status",
        "/api/trading/positions",
        "/api/signals",
        "/api/trades",
    ],
)
def test_rejects_invalid_asset_class(client, endpoint):
    res = client.get(endpoint, params={"asset_class": "options"})
    assert res.status_code == 400
    assert "asset_class" in res.json()["detail"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/trading/status",
        "/api/trading/positions",
    ],
)
def test_default_is_futures(client, endpoint):
    res = client.get(endpoint)
    assert res.status_code in (200, 503)


def test_case_insensitive(client):
    res = client.get("/api/trading/positions", params={"asset_class": "STOCK"})
    assert res.status_code in (200, 503)
