"""Tests for Tier-3 PR-C analytics routes: strategy correlation + exposure history."""

from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_pearson_basic():
    from services.dashboard.routes.analytics import _pearson

    assert _pearson([1, 2, 3], [1, 2, 3]) == 1.0
    assert _pearson([1, 2, 3], [3, 2, 1]) == -1.0
    # zero variance → undefined
    assert _pearson([1, 1, 1], [1, 2, 3]) is None
    assert _pearson([1.0], [1.0]) is None  # too short


class _FakeLedger:
    def __init__(self, trades=None, snapshots=None):
        self._trades = trades or []
        self._snapshots = snapshots or []

    def query_trades(self, filters=None):
        return self._trades

    def query_position_snapshots_daily(self, asset_class=None, *, start=None, end=None):
        return self._snapshots


def _client(monkeypatch, ledger):
    from services.dashboard.routes import analytics

    importlib.reload(analytics)
    monkeypatch.setattr(analytics, "_get_runtime_ledger", lambda: ledger)
    app = FastAPI()
    app.include_router(analytics.router)
    return TestClient(app)


def test_strategy_correlation_empty_without_ledger(monkeypatch):
    client = _client(monkeypatch, None)
    resp = client.get("/api/analytics/strategy-correlation")
    assert resp.status_code == 200
    assert resp.json()["status"] == "empty"


def test_strategy_correlation_insufficient_with_one_strategy(monkeypatch):
    ledger = _FakeLedger(
        trades=[
            {"strategy": "a", "exit_time": "2026-07-01T00:00:00", "pnl": 10},
            {"strategy": "a", "exit_time": "2026-07-02T00:00:00", "pnl": -5},
        ]
    )
    client = _client(monkeypatch, ledger)
    resp = client.get("/api/analytics/strategy-correlation")
    assert resp.json()["status"] == "insufficient_data"


def test_strategy_correlation_matrix(monkeypatch):
    # a and b move together across 3 days → positive correlation; diagonal = 1.
    ledger = _FakeLedger(
        trades=[
            {"strategy": "a", "exit_time": "2026-07-01T00:00:00", "pnl": 10},
            {"strategy": "a", "exit_time": "2026-07-02T00:00:00", "pnl": 20},
            {"strategy": "a", "exit_time": "2026-07-03T00:00:00", "pnl": 30},
            {"strategy": "b", "exit_time": "2026-07-01T00:00:00", "pnl": 5},
            {"strategy": "b", "exit_time": "2026-07-02T00:00:00", "pnl": 10},
            {"strategy": "b", "exit_time": "2026-07-03T00:00:00", "pnl": 15},
        ]
    )
    client = _client(monkeypatch, ledger)
    body = client.get("/api/analytics/strategy-correlation").json()
    assert body["status"] == "ok"
    assert body["strategies"] == ["a", "b"]
    assert body["matrix"][0][0] == 1.0
    assert body["matrix"][1][1] == 1.0
    assert body["matrix"][0][1] == 1.0  # perfectly correlated


def test_exposure_history_empty_without_ledger(monkeypatch):
    client = _client(monkeypatch, None)
    resp = client.get("/api/analytics/exposure-history")
    assert resp.json()["status"] == "empty"


def test_exposure_history_stacks_by_symbol(monkeypatch):
    ledger = _FakeLedger(
        snapshots=[
            {
                "snapshot_time": "2026-07-01T09:00:00",
                "symbol": "005930",
                "quantity": 10,
                "current_price": 70000,
            },
            {
                "snapshot_time": "2026-07-01T09:00:00",
                "symbol": "000660",
                "quantity": 5,
                "current_price": 100000,
            },
            {
                "snapshot_time": "2026-07-02T09:00:00",
                "symbol": "005930",
                "quantity": 10,
                "current_price": 71000,
            },
        ]
    )
    client = _client(monkeypatch, ledger)
    body = client.get("/api/analytics/exposure-history").json()
    assert body["status"] == "ok"
    assert body["symbols"] == ["000660", "005930"]
    day1 = next(p for p in body["points"] if p["trade_date"] == "2026-07-01")
    assert day1["005930"] == 700000.0  # 10 * 70000
    assert day1["000660"] == 500000.0  # 5 * 100000
