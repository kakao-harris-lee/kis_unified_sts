"""Orchestrator redis hot-path error metric wiring (Increment 1 observability).

Two best-effort catch sites record `record_error("redis")` (metric only, no new
log line):

- candle-cache save failure inside `_handle_monitoring` (was a silent ``pass``).
- market-data refresh failure inside `_market_data_loop` (already WARNs).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from shared.exceptions import InfrastructureError


def _make_orchestrator() -> TradingOrchestrator:
    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = TradingConfig()
    orch._metrics = MagicMock()
    return orch


class TestCandleCacheRedisError:
    """`_handle_monitoring` records record_error('redis') on candle-cache fail."""

    @pytest.mark.asyncio
    async def test_candle_cache_save_failure_records_redis_error(self):
        orch = _make_orchestrator()
        # publish-due state_publisher (last publish far in the past)
        orch._state_publisher = SimpleNamespace(
            _last_status_publish=0.0,
            publish_status=MagicMock(),
            publish_positions_update=MagicMock(),
        )
        orch._last_candle_cache_save = 0.0  # cache-save is due
        orch.config.candle_cache_save_interval = 0.0
        orch.get_status = MagicMock(return_value={})
        orch._save_candle_cache_to_redis = MagicMock(
            side_effect=InfrastructureError("redis down")
        )
        # No positions → method returns cleanly after the candle block
        orch._position_tracker = SimpleNamespace(positions=[])
        orch._data_provider = SimpleNamespace()

        result = await orch._handle_monitoring()

        assert result is None
        orch._metrics.record_error.assert_called_once_with("redis")

    @pytest.mark.asyncio
    async def test_candle_cache_save_failure_no_metrics_does_not_raise(self):
        orch = _make_orchestrator()
        orch._metrics = None  # best-effort guard: must not raise
        orch._state_publisher = SimpleNamespace(
            _last_status_publish=0.0,
            publish_status=MagicMock(),
            publish_positions_update=MagicMock(),
        )
        orch._last_candle_cache_save = 0.0
        orch.config.candle_cache_save_interval = 0.0
        orch.get_status = MagicMock(return_value={})
        orch._save_candle_cache_to_redis = MagicMock(
            side_effect=InfrastructureError("redis down")
        )
        orch._position_tracker = SimpleNamespace(positions=[])
        orch._data_provider = SimpleNamespace()

        # must not raise even with no collector
        result = await orch._handle_monitoring()
        assert result is None


class TestMarketDataRefreshRedisError:
    """`_market_data_loop` records record_error('redis') on refresh failure."""

    @pytest.mark.asyncio
    async def test_refresh_failure_records_redis_error(self):
        orch = _make_orchestrator()
        orch._get_market_symbols = MagicMock(return_value=[])
        orch._market_data_running = True

        async def _refresh_then_stop():
            # Break the loop after this single failing iteration.
            orch._market_data_running = False
            raise InfrastructureError("redis refresh down")

        orch._refresh_market_data_once = AsyncMock(side_effect=_refresh_then_stop)

        await orch._market_data_loop(interval=0.01)

        orch._metrics.record_error.assert_called_once_with("redis")
