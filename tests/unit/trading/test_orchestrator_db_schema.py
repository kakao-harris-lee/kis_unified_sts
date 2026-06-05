"""Tests for orchestrator storage schema initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_orchestrator():
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = TradingConfig.stock()
    orch._position_tracker = None
    return orch


@pytest.mark.asyncio
async def test_initialize_components_keeps_schema_step_before_position_recovery():
    orch = _make_orchestrator()
    calls: list[str] = []

    orch._init_kis_client = MagicMock(return_value=None)
    orch._init_futures_slippage_controller = MagicMock()
    orch._init_price_feeds = MagicMock(return_value=None)
    orch._init_data_provider = MagicMock()
    orch._init_tick_stream_publisher = MagicMock()
    orch._init_strategy_infrastructure = MagicMock()
    orch._init_indicator_engine = MagicMock()
    orch._init_execution_layer = AsyncMock()
    orch._ensure_db_schema = AsyncMock(side_effect=lambda: calls.append("schema"))
    orch._load_swing_positions = AsyncMock(
        side_effect=lambda: calls.append("positions")
    )
    orch._init_llm_context_publisher = MagicMock()

    await orch._initialize_components()

    assert calls == ["schema", "positions"]


@pytest.mark.asyncio
async def test_ensure_db_schema_is_runtime_ledger_noop():
    orch = _make_orchestrator()

    assert await orch._ensure_db_schema() is None
