"""Tests for orchestrator ClickHouse prewarm connection config."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator


def _make_orchestrator(asset_class: str = "stock") -> TradingOrchestrator:
    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    if asset_class == "futures":
        orch.config = TradingConfig.futures()
    else:
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


@pytest.mark.asyncio
async def test_fetch_candles_from_clickhouse_futures_uses_kospi_mini():
    """Futures prewarm should query kospi.kospi_mini_1m instead of returning []."""
    orch = _make_orchestrator(asset_class="futures")
    captured_query: list[str] = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def execute(self, query, params):
            captured_query.append(query)
            return []

    class FakeCHConfig:
        host = "localhost"
        port = 9000
        user = "default"
        password = ""
        database = "kospi"

    fake_module = types.SimpleNamespace(Client=FakeClient)

    with patch(
        "services.trading.orchestrator.ClickHouseConfig.from_env",
        return_value=FakeCHConfig(),
    ) as from_env_mock, patch.dict(sys.modules, {"clickhouse_driver": fake_module}):
        candles = await orch._fetch_candles_from_clickhouse("A05606", limit=700)

    assert candles == []
    from_env_mock.assert_called_once_with(database="kospi")
    assert len(captured_query) == 1
    assert "kospi_mini_1m" in captured_query[0]
