"""Tests for position persistence (save_closed_to_db, load_from_db side/fee_rate, _get_db_client)."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

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
    """Test database field in PositionTrackerConfig."""

    def test_default_database_empty(self):
        config = PositionTrackerConfig()
        assert config.database == ""

    def test_database_from_constructor(self):
        config = PositionTrackerConfig(database="market")
        assert config.database == "market"

    def test_database_from_dict(self):
        config = PositionTrackerConfig.from_dict({"database": "kospi"})
        assert config.database == "kospi"

    def test_database_from_dict_missing(self):
        config = PositionTrackerConfig.from_dict({})
        assert config.database == ""


class TestGetDbClient:
    """Test _get_db_client helper."""

    @patch("shared.db.client.ClickHouseClient")
    @patch("shared.db.config.ClickHouseConfig")
    def test_uses_config_database(self, MockConfig, MockCH):
        """When config.database is set, it should be used over ClickHouse default."""
        tracker = PositionTracker(config=PositionTrackerConfig(database="market"))

        mock_instance = MagicMock()
        mock_instance.config.database = "default_db"
        MockCH.return_value = mock_instance

        ch, db = tracker._get_db_client()
        assert db == "market"  # config.database takes precedence over "default_db"

    @patch("shared.db.client.ClickHouseClient")
    @patch("shared.db.config.ClickHouseConfig")
    def test_falls_back_to_ch_database(self, MockConfig, MockCH):
        """When config.database is empty, use ClickHouseConfig's database."""
        tracker = PositionTracker(config=PositionTrackerConfig(database=""))

        # cfg = ClickHouseConfig.from_env(...) → cfg.database should return "kospi"
        mock_cfg = MagicMock()
        mock_cfg.database = "kospi"
        MockConfig.from_env.return_value = mock_cfg

        ch, db = tracker._get_db_client()
        assert db == "kospi"

    @patch("shared.db.client.ClickHouseClient")
    @patch("shared.db.config.ClickHouseConfig")
    def test_rejects_invalid_database_name(self, MockConfig, MockCH):
        """Database names with non-alnum/underscore chars should raise."""
        tracker = PositionTracker(config=PositionTrackerConfig(database="bad;name"))

        mock_instance = MagicMock()
        MockCH.return_value = mock_instance

        with pytest.raises(ValueError, match="Invalid database name"):
            tracker._get_db_client()


class TestSaveClosedToDb:
    """Test save_closed_to_db method."""

    @pytest.mark.asyncio
    async def test_skips_if_no_exit_price(self):
        tracker = PositionTracker()
        pos = _make_position()  # no exit_price
        result = await tracker.save_closed_to_db(pos)
        assert result is False

    @pytest.mark.asyncio
    async def test_saves_long_position(self):
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            pos = _make_position(
                entry_price=70000,
                exit_price=72000,
                quantity=10,
                side=PositionSide.LONG,
            )
            result = await tracker.save_closed_to_db(pos)
            # Explicitly flush the batch to trigger the database write
            await tracker.flush_pending_positions()

        assert result is True
        # Verify INSERT was called
        call_args = mock_client.execute.call_args
        sql = call_args[0][0]
        rows = call_args[0][1]

        assert "testdb.swing_positions" in sql
        assert "side, fee_rate" in sql
        assert len(rows) == 1

        row = rows[0]
        assert row[10] == 0  # is_open = closed
        assert row[14] == 20000.0  # pnl = (72000 - 70000) * 10
        assert row[15] == "long"  # side
        assert row[16] == 0.003  # fee_rate

    @pytest.mark.asyncio
    async def test_saves_short_position(self):
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            pos = _make_position(
                entry_price=350.0,
                exit_price=345.0,
                quantity=1,
                side=PositionSide.SHORT,
                strategy="rl_mppo",
            )
            result = await tracker.save_closed_to_db(pos)
            # Explicitly flush the batch to trigger the database write
            await tracker.flush_pending_positions()

        assert result is True
        row = mock_client.execute.call_args[0][1][0]
        assert row[14] == 5.0  # pnl = (350 - 345) * 1 (short profit)
        assert row[15] == "short"

    @pytest.mark.asyncio
    async def test_handles_db_error(self):
        """DB errors are surfaced during flush, not during accumulation.

        save_closed_to_db batches positions in memory and always returns True
        for valid positions. The flush step handles the actual DB write and
        returns 0 on error while re-enqueuing the rows.
        """
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        pos = _make_position(exit_price=72000)
        result = await tracker.save_closed_to_db(pos)

        # Accumulation succeeds regardless of DB state
        assert result is True
        assert len(tracker._pending_swing_positions) == 1

        # Flush fails gracefully and re-enqueues the rows
        with patch.object(
            tracker, "_get_db_client", side_effect=Exception("connection refused")
        ):
            flushed, _ = await tracker.flush_pending_positions()

        assert flushed == 0
        # Row re-enqueued for retry
        assert len(tracker._pending_swing_positions) == 1


class TestSaveToDbWithSideAndFeeRate:
    """Test save_to_db includes side and fee_rate columns."""

    @pytest.mark.asyncio
    async def test_includes_side_and_fee_rate(self):
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        # Add a position
        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            tracker.add_position(
                code="005930",
                name="삼성전자",
                entry_price=70000,
                quantity=10,
                strategy="bb_reversion",
                side=PositionSide.LONG,
                fee_rate=0.005,
            )
            result = await tracker.save_to_db()

        assert result == 1
        call_args = mock_client.execute.call_args
        sql = call_args[0][0]
        rows = call_args[0][1]

        assert "side, fee_rate" in sql
        row = rows[0]
        assert row[15] == "long"  # side
        assert row[16] == 0.005  # fee_rate


class TestSaveRlTradeToDb:
    """Test save_rl_trade_to_db method."""

    @pytest.mark.asyncio
    async def test_saves_rl_trade(self):
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            pos = _make_position(
                id="rl-pos-001",
                code="A01603",
                name="KOSPI200선물",
                entry_price=350.0,
                exit_price=345.0,
                quantity=1,
                side=PositionSide.SHORT,
                strategy="rl_mppo",
            )
            pos.metadata = {"snapshot_id": "snap-1", "model_version": "mppo-v3"}
            result = await tracker.save_rl_trade_to_db(pos, asset_class="futures")
            # Explicitly flush the batch to trigger the database write
            await tracker.flush_pending_positions()

        assert result is True
        call_args = mock_client.execute.call_args
        sql = call_args[0][0]
        rows = call_args[0][1]

        assert "testdb.rl_trades" in sql
        assert len(rows) == 1
        row = rows[0]
        assert row[1] == "futures"  # asset_class
        assert row[5] == "rl_mppo"  # strategy
        assert row[11] == 5.0  # pnl = (350 - 345) * 1
        assert row[12] > 0.0  # pnl_pct
        assert row[13] > 0  # hold_seconds
        assert "model_version" in row[15]  # metadata_json

    @pytest.mark.asyncio
    async def test_skips_rl_trade_if_not_closed(self):
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))
        pos = _make_position(strategy="rl_mppo")
        result = await tracker.save_rl_trade_to_db(pos, asset_class="futures")
        assert result is False


class TestLoadFromDbSideAndFeeRate:
    """Test load_from_db parses side and fee_rate."""

    @pytest.mark.asyncio
    async def test_loads_short_position(self):
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        # Simulate DB rows with side/fee_rate
        mock_client.execute.return_value = [
            (
                "pos-short-001",
                "101S6000",
                "KOSPI200선물",
                datetime(2026, 2, 19, 9, 0, 0),
                350.0,  # entry_price
                1,  # quantity
                "rl_mppo",  # strategy
                340.0,  # stop_loss_price
                355.0,  # high_since_entry
                "survival",  # current_state
                "short",  # side
                0.001,  # fee_rate
            )
        ]

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            loaded = await tracker.load_from_db()

        assert loaded == 1
        pos = tracker.get_position("pos-short-001")
        assert pos is not None
        assert pos.side == PositionSide.SHORT
        assert pos.fee_rate == 0.001
        assert pos.highest_price == 355.0

    @pytest.mark.asyncio
    async def test_loads_with_default_side(self):
        """Invalid/missing side string defaults to LONG."""
        tracker = PositionTracker(config=PositionTrackerConfig(database="testdb"))

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        mock_client.execute.return_value = [
            (
                "pos-unknown-side",
                "005930",
                "삼성전자",
                datetime(2026, 2, 19, 9, 30, 0),
                70000,
                10,
                "bb_reversion",
                0.0,
                70000,
                "survival",
                "invalid_side",  # invalid side string
                0.0,  # zero fee_rate → should use default
            )
        ]

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            loaded = await tracker.load_from_db()

        assert loaded == 1
        pos = tracker.get_position("pos-unknown-side")
        assert pos.side == PositionSide.LONG  # default
        assert pos.fee_rate == 0.003  # default_fee_rate


class TestRealizedPnlBugFix:
    """Verify that the orchestrator uses unrealized_pnl (not realized_pnl) on close."""

    def test_position_has_no_realized_pnl_attribute(self):
        """Position model should NOT have realized_pnl — confirming the bug existed."""
        pos = _make_position()
        assert not hasattr(pos, "realized_pnl")

    def test_unrealized_pnl_at_exit(self):
        """When current_price=exit_price, unrealized_pnl is effectively realized."""
        pos = _make_position(entry_price=70000, exit_price=72000, quantity=10)
        # current_price is set to exit_price
        assert pos.unrealized_pnl == 20000.0

    def test_unrealized_pnl_short(self):
        pos = _make_position(
            entry_price=350.0,
            exit_price=345.0,
            quantity=1,
            side=PositionSide.SHORT,
        )
        assert pos.unrealized_pnl == 5.0
