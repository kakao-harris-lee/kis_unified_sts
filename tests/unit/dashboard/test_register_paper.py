"""Tests for the builder→paper registration endpoints (Phase 2)."""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient


def _minimal_state(asset_class: str = "stock", strategy_id: str = "test_built") -> dict:
    """Smallest valid BuilderState (matches schema.py)."""
    return {
        "metadata": {
            "id": strategy_id,
            "name": "Test Built Strategy",
            "description": "Smoke",
            "category": "custom",
            "tags": ["test"],
            "author": "test",
        },
        "asset_class": asset_class,
        "indicators": [
            {
                "indicator_id": "rsi",
                "alias": "rsi",
                "params": {},
                "output": "value",
            }
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "left": {
                        "type": "indicator",
                        "indicator_alias": "rsi",
                        "indicator_output": "value",
                    },
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {
            "logic": "AND",
            "conditions": [
                {
                    "left": {
                        "type": "indicator",
                        "indicator_alias": "rsi",
                        "indicator_output": "value",
                    },
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 70.0},
                }
            ],
        },
        "risk": {
            "order_amount": 1_000_000,
            "stop_loss": {"enabled": True, "percent": 5.0},
            "take_profit": {"enabled": False, "percent": 10.0},
            "trailing_stop": {"enabled": False, "percent": 3.0},
        },
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Spin a TestClient with the built-strategies dir pinned to tmp_path."""
    monkeypatch.setenv("KIS_BUILT_STRATEGIES_DIR", str(tmp_path / "built"))
    # Re-import after env var is set so the module picks up the new dir.
    import importlib

    from services.dashboard.routes import kis_builder

    importlib.reload(kis_builder)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(kis_builder.router)
    return TestClient(app), tmp_path / "built"


def test_register_paper_creates_yaml(client) -> None:
    tc, built_dir = client
    resp = tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state()},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "test_built"
    assert body["enabled"] is False
    assert body["asset_class"] == "stock"

    # File on disk + structure
    path = built_dir / "test_built.yaml"
    assert path.exists()
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    strategy = doc["strategy"]
    assert strategy["name"] == "test_built"
    assert strategy["enabled"] is False
    assert strategy["entry"]["type"] == "builder_v1"
    assert strategy["exit"]["type"] == "builder_v1_exit"
    assert strategy["position"]["type"] == "fixed"
    assert (
        strategy["entry"]["params"]["builder_state"]["metadata"]["id"] == "test_built"
    )


def test_register_paper_trailing_from_draft(client) -> None:
    """Trailing stop derives from the builder draft's risk.trailing_stop toggle."""
    tc, built_dir = client
    state = _minimal_state(strategy_id="trail_on")
    state["risk"]["trailing_stop"] = {"enabled": True, "percent": 3.0}
    resp = tc.post("/api/kis-builder/register-paper", json={"builder_state": state})
    assert resp.status_code == 200, resp.text
    doc = yaml.safe_load((built_dir / "trail_on.yaml").read_text(encoding="utf-8"))
    assert doc["strategy"]["exit"]["params"]["trailing_stop_pct"] == 3.0


def test_register_paper_trailing_disabled_default(client) -> None:
    """Draft trailing disabled and no override → trailing_stop_pct is 0 (off)."""
    tc, built_dir = client
    resp = tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state(strategy_id="trail_off")},
    )
    assert resp.status_code == 200, resp.text
    doc = yaml.safe_load((built_dir / "trail_off.yaml").read_text(encoding="utf-8"))
    assert doc["strategy"]["exit"]["params"]["trailing_stop_pct"] == 0.0


def test_register_paper_trailing_explicit_override(client) -> None:
    """An explicit request trailing_stop_pct wins over the draft toggle."""
    tc, built_dir = client
    state = _minimal_state(strategy_id="trail_override")
    state["risk"]["trailing_stop"] = {"enabled": False, "percent": 3.0}
    resp = tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": state, "trailing_stop_pct": 2.0},
    )
    assert resp.status_code == 200, resp.text
    doc = yaml.safe_load(
        (built_dir / "trail_override.yaml").read_text(encoding="utf-8")
    )
    assert doc["strategy"]["exit"]["params"]["trailing_stop_pct"] == 2.0


def test_register_paper_rejects_futures(client) -> None:
    tc, _ = client
    resp = tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state(asset_class="futures")},
    )
    assert resp.status_code == 400
    assert "stock-only" in resp.json()["detail"]


def test_register_paper_rejects_invalid_state(client) -> None:
    tc, _ = client
    resp = tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": {"metadata": {"id": "x"}}},  # missing fields
    )
    assert resp.status_code == 400


def test_register_paper_rejects_bad_id(client) -> None:
    tc, _ = client
    state = _minimal_state(strategy_id="../escape")
    resp = tc.post("/api/kis-builder/register-paper", json={"builder_state": state})
    assert resp.status_code == 400
    assert "Invalid strategy id" in resp.json()["detail"]


def test_list_registered_returns_built_strategies(client) -> None:
    tc, _ = client
    tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state(strategy_id="alpha")},
    )
    tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state(strategy_id="beta")},
    )
    resp = tc.get("/api/kis-builder/registered")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = sorted(s["id"] for s in body["strategies"])
    assert ids == ["alpha", "beta"]
    for s in body["strategies"]:
        assert s["enabled"] is False


def test_toggle_registered_strategy_flips_enabled(client) -> None:
    tc, built_dir = client
    tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state(strategy_id="alpha")},
    )
    # Enable
    resp = tc.post("/api/kis-builder/registered/alpha/enable", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    # Persisted
    doc = yaml.safe_load((built_dir / "alpha.yaml").read_text(encoding="utf-8"))
    assert doc["strategy"]["enabled"] is True
    # Disable
    resp = tc.post("/api/kis-builder/registered/alpha/enable", json={"enabled": False})
    assert resp.json()["enabled"] is False


def test_toggle_missing_strategy_returns_404(client) -> None:
    tc, _ = client
    resp = tc.post("/api/kis-builder/registered/nope/enable", json={"enabled": True})
    assert resp.status_code == 404


def test_unregister_deletes_file(client) -> None:
    tc, built_dir = client
    tc.post(
        "/api/kis-builder/register-paper",
        json={"builder_state": _minimal_state(strategy_id="alpha")},
    )
    assert (built_dir / "alpha.yaml").exists()
    resp = tc.delete("/api/kis-builder/registered/alpha")
    assert resp.status_code == 200
    assert resp.json() == {"id": "alpha", "deleted": True}
    assert not (built_dir / "alpha.yaml").exists()


def test_unregister_missing_returns_404(client) -> None:
    tc, _ = client
    resp = tc.delete("/api/kis-builder/registered/missing")
    assert resp.status_code == 404
