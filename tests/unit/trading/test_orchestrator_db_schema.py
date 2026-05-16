"""Tests for orchestrator ClickHouse schema initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_orchestrator():
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = TradingConfig.stock()
    orch._position_tracker = None
    return orch


@pytest.mark.asyncio
async def test_initialize_components_ensures_db_schema_before_position_recovery():
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
async def test_ensure_db_schema_migrates_swing_execution_venue_column():
    orch = _make_orchestrator()

    sync_client = MagicMock()
    temp_client = MagicMock()
    clickhouse = MagicMock()
    clickhouse.config.host = "localhost"
    clickhouse.config.port = 9000
    clickhouse.config.user = "default"
    clickhouse.config.password = ""
    clickhouse.get_sync_client.return_value = sync_client

    tracker = MagicMock()
    tracker._get_db_client.return_value = (clickhouse, "market")
    orch._position_tracker = tracker

    with patch("shared.db.client.SyncClient", return_value=temp_client):
        await orch._ensure_db_schema()

    executed_sql = [call.args[0] for call in sync_client.execute.call_args_list]

    assert any(
        "CREATE TABLE IF NOT EXISTS market.swing_positions" in sql
        for sql in executed_sql
    )
    assert any(
        "CREATE TABLE IF NOT EXISTS market.rl_trades" in sql for sql in executed_sql
    )
    assert any(
        "ALTER TABLE market.swing_positions ADD COLUMN IF NOT EXISTS execution_venue"
        in sql
        for sql in executed_sql
    )
    temp_client.execute.assert_called_once_with("CREATE DATABASE IF NOT EXISTS market")
    temp_client.disconnect.assert_called_once()
