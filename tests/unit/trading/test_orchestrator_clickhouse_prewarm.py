"""Tests for orchestrator ClickHouse prewarm connection config."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator


def _make_orchestrator() -> TradingOrchestrator:
    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = TradingConfig.stock()
    return orch


@pytest.mark.asyncio
async def test_fetch_candles_from_clickhouse_uses_shared_native_port_config():
    """Prewarm should use ClickHouseConfig.from_env so the native client avoids HTTP 8123."""
    orch = _make_orchestrator()
    captured: dict[str, int | str] = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def execute(self, _query, _params):
            return []

    class FakeCHConfig:
        host = "localhost"
        port = 9000
        user = "default"
        password = ""
        database = "market"

    fake_module = types.SimpleNamespace(Client=FakeClient)

    with patch(
        "services.trading.orchestrator.ClickHouseConfig.from_env",
        return_value=FakeCHConfig(),
    ) as from_env_mock, patch.dict(sys.modules, {"clickhouse_driver": fake_module}):
        candles = await orch._fetch_candles_from_clickhouse("005930", limit=5)

    assert candles == []
    from_env_mock.assert_called_once_with(database="market")
    assert captured["port"] == 9000
    assert captured["database"] == "market"
