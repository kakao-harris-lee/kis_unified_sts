"""Tests for managed trading-universe dashboard endpoints."""

from __future__ import annotations

import importlib
import json
import sys
import types

import pytest


class _FakeRedis:
    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads
        self.expirations: dict[str, int] = {}
        self.lists: dict[str, list[str]] = {}

    def get(self, key: str) -> str | None:
        payload = self.payloads.get(key)
        if payload is None:
            return None
        return payload if isinstance(payload, str) else json.dumps(payload)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.payloads[key] = value
        if ex is not None:
            self.expirations[key] = ex

    def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key: str, start: int, stop: int) -> None:
        self.lists[key] = self.lists.get(key, [])[start : stop + 1]

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        return self.lists.get(key, [])[start : stop + 1]


def _client(monkeypatch, payloads: dict[str, object]):
    fake_fastapi = types.ModuleType("fastapi")

    class _Router:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

        def post(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def _query(default=None, **kwargs):
        return default

    fake_fastapi.APIRouter = _Router
    fake_fastapi.HTTPException = _HTTPException
    fake_fastapi.Query = _query
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)

    from services.dashboard.routes import universe

    importlib.reload(universe)
    fake = _FakeRedis(payloads)
    monkeypatch.setattr(universe, "_get_redis_client", lambda: fake)
    monkeypatch.setattr(universe, "_read_open_positions", lambda: ([], {}))
    return universe, fake


@pytest.mark.asyncio
async def test_universe_endpoint_builds_effective_snapshot(monkeypatch):
    universe, _fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930", "000660"],
                "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
            },
            "system:daily_watchlist:latest": {
                "strategies": {"pattern_pullback": ["035720"]}
            },
            "system:daily_indicators:latest": {
                "indicators": {"005930": {}, "035720": {}}
            },
        },
    )

    body = await universe.get_trading_universe()

    assert body["codes"] == ["005930", "000660", "035720"]
    rows = {row["code"]: row for row in body["rows"]}
    assert rows["005930"]["name"] == "삼성전자"
    assert rows["000660"]["daily_indicator"] == "missing"


@pytest.mark.asyncio
async def test_universe_override_publishes_snapshot_and_audit(monkeypatch):
    universe, fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930", "000660"],
                "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
            },
        },
    )

    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="exclude",
            symbol="000660",
            name="SK하이닉스",
            reason="manual risk block",
            ttl_seconds=3600,
        )
    )

    assert body["codes"] == ["005930"]

    overrides = json.loads(fake.payloads["stock:universe:overrides"])
    assert "000660" in overrides["manual_exclude"]
    effective = json.loads(fake.payloads["stock:universe:effective:latest"])
    assert effective["codes"] == ["005930"]
    assert 0 < fake.expirations["stock:universe:effective:latest"] <= 3600
    assert fake.lists["stock:universe:audit"]

    audit_response = await universe.get_trading_universe_audit()
    assert audit_response["events"][0]["symbol"] == "000660"
