"""Tests for PositionTracker RuntimeLedger persistence compatibility methods."""

from datetime import datetime

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide, PositionState


def _make_position(
    *,
    id="test-pos-001",
    code="005930",
    name="삼성전자",
    side=PositionSide.LONG,
    quantity=10,
    entry_price=70000,
    strategy="bb_reversion",
    fee_rate=0.003,
    exit_price=None,
    exit_time=None,
    exit_reason=None,
):
    pos = Position(
        id=id,
        code=code,
        name=name,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime(2026, 2, 19, 9, 30, 0),
        current_price=exit_price or entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=PositionState.SURVIVAL,
        strategy=strategy,
        fee_rate=fee_rate,
    )
    if exit_price is not None:
        pos.exit_price = exit_price
        pos.exit_time = exit_time or datetime(2026, 2, 19, 14, 0, 0)
        pos.exit_reason = exit_reason or "TRAILING_STOP"
        pos.current_price = exit_price
    return pos


class TestPositionTrackerConfigDatabase:
    """Legacy database field remains inert for config compatibility."""

    def test_default_database_empty(self):
        config = PositionTrackerConfig()
        assert config.database == ""

    def test_database_from_constructor(self):
        config = PositionTrackerConfig(database="market")
        assert config.database == "market"

    def test_database_from_dict(self):
        config = PositionTrackerConfig.from_dict({"database": "kospi"})
        assert config.database == "kospi"


class TestSaveClosedToRuntimeLedger:
    @pytest.mark.asyncio
    async def test_skips_if_no_exit_price(self):
        tracker = PositionTracker()
        pos = _make_position()
        result = await tracker.save_closed_to_db(pos)
        assert result is False

    @pytest.mark.asyncio
    async def test_saves_closed_position_to_runtime_ledger(self, tmp_path, monkeypatch):
        db_path = tmp_path / "runtime.db"
        monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(db_path))

        tracker = PositionTracker(
            config=PositionTrackerConfig(runtime_ledger_backend="sqlite")
        )
        pos = _make_position(
            entry_price=70000,
            exit_price=72000,
            quantity=10,
            side=PositionSide.LONG,
        )

        result = await tracker.save_closed_to_db(pos)
        await tracker.flush_pending_positions()

        assert result is True
        assert db_path.exists()


def test_removed_db_client_raises_clear_error():
    from shared.db.client import ClickHouseRemovedError

    tracker = PositionTracker()

    with pytest.raises(ClickHouseRemovedError, match="RuntimeLedger"):
        tracker._get_db_client()
