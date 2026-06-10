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


def _futures_orchestrator_with_ledger(tmp_path):
    """Futures orchestrator with a real position tracker + SQLite ledger."""
    from datetime import datetime

    from services.trading.orchestrator import TradingConfig, TradingOrchestrator
    from services.trading.position_tracker import (
        PositionTracker,
        PositionTrackerConfig,
    )
    from shared.models.position import PositionSide
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    tracker = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="futures",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = TradingConfig.futures()
    orch._position_tracker = tracker

    position = tracker.add_position(
        code="101S6000",
        name="KOSPI200 F",
        entry_price=350.0,
        quantity=1,
        strategy="setup_a_gap_reversion",
        side=PositionSide.LONG,
    )
    return orch, tracker, ledger, position, datetime


@pytest.mark.asyncio
async def test_persist_closed_futures_position_supersedes_open_snapshot(tmp_path):
    """Closing a futures position flips its durable open snapshot to is_open=0."""
    orch, tracker, ledger, position, datetime = _futures_orchestrator_with_ledger(
        tmp_path
    )

    # Durable open snapshot mirror (as the auto-flush loop would do).
    assert await tracker.save_to_db() == 1
    assert len(ledger.load_open_positions("futures")) == 1

    # Close it and persist via the orchestrator routing path.
    position.exit_price = 360.0
    position.exit_time = datetime.now()
    position.exit_reason = "take_profit"
    await orch._persist_closed_position(position, "setup_a_gap_reversion")

    # Open snapshot superseded in place => no open rows, futures trade recorded.
    assert ledger.load_open_positions("futures") == []
    trades = ledger.query_trades({"asset_class": "futures"})
    assert len(trades) == 1
    assert trades[0]["id"] == position.id
