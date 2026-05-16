"""Tests for Redis-based position recovery.

Tests cover:
- Stock/futures position recovery from Redis
- Strategy-based freshness filtering (swing vs intraday)
- Missing fields fallback
- Duplicate position ID handling
- Empty Redis graceful handling
- WebSocket subscription for recovered symbols
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide, PositionState

# -- Fixtures --


@pytest.fixture
def tracker():
    config = PositionTrackerConfig(max_positions=20)
    return PositionTracker(config)


def _make_redis_position(
    *,
    pos_id="abc-123",
    code="005930",
    name="삼성전자",
    side="long",
    quantity=100,
    entry_price=70000.0,
    current_price=71000.0,
    strategy="bb_reversion",
    state="survival",
    entry_time=None,
    highest_price=None,
    lowest_price=None,
    fee_rate=None,
    stop_price=None,
):
    """Build a dict matching the Redis serialization format."""
    if entry_time is None:
        entry_time = datetime.now().isoformat()
    elif isinstance(entry_time, datetime):
        entry_time = entry_time.isoformat()

    d = {
        "id": pos_id,
        "code": code,
        "name": name,
        "side": side,
        "quantity": quantity,
        "entry_price": entry_price,
        "current_price": current_price,
        "strategy": strategy,
        "state": state,
        "entry_time": entry_time,
    }
    if highest_price is not None:
        d["highest_price"] = highest_price
    if lowest_price is not None:
        d["lowest_price"] = lowest_price
    if fee_rate is not None:
        d["fee_rate"] = fee_rate
    if stop_price is not None:
        d["stop_price"] = stop_price
    return d


# -- PositionTracker.add_recovered_position tests --


class TestAddRecoveredPosition:
    def test_basic_recovery(self, tracker):
        pos = Position(
            id="test-001",
            code="005930",
            name="삼성전자",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=70000.0,
            entry_time=datetime.now(),
            current_price=71000.0,
            state=PositionState.BREAKEVEN,
            strategy="bb_reversion",
        )
        assert tracker.add_recovered_position(pos) is True
        assert tracker.position_count == 1
        assert tracker.get_position("test-001") is pos

    def test_indices_updated(self, tracker):
        pos = Position(
            id="test-002",
            code="A01603",
            name="KOSPI200선물",
            side=PositionSide.SHORT,
            quantity=1,
            entry_price=837.0,
            entry_time=datetime.now(),
            strategy="rl_mppo",
        )
        tracker.add_recovered_position(pos)
        assert len(tracker.get_positions_by_symbol("A01603")) == 1
        assert len(tracker.get_positions_by_strategy("rl_mppo")) == 1

    def test_duplicate_id_rejected(self, tracker):
        pos = Position(
            id="dup-id",
            code="005930",
            name="삼성전자",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=70000.0,
            entry_time=datetime.now(),
            strategy="bb_reversion",
        )
        assert tracker.add_recovered_position(pos) is True
        assert tracker.add_recovered_position(pos) is False
        assert tracker.position_count == 1

    def test_state_preserved(self, tracker):
        pos = Position(
            id="state-test",
            code="034020",
            name="두산에너빌리티",
            side=PositionSide.LONG,
            quantity=50,
            entry_price=95000.0,
            entry_time=datetime.now(),
            state=PositionState.MAXIMIZE,
            strategy="bb_reversion",
        )
        tracker.add_recovered_position(pos)
        recovered = tracker.get_position("state-test")
        assert recovered.state == PositionState.MAXIMIZE

    def test_short_position_recovery(self, tracker):
        pos = Position(
            id="short-001",
            code="A01603",
            name="KOSPI200선물",
            side=PositionSide.SHORT,
            quantity=1,
            entry_price=837.0,
            entry_time=datetime.now(),
            current_price=835.0,
            strategy="rl_mppo",
        )
        tracker.add_recovered_position(pos)
        recovered = tracker.get_position("short-001")
        assert recovered.side == PositionSide.SHORT
        assert recovered.profit_pct > 0  # short + price down = profit


# -- Orchestrator recovery logic tests --


class TestRecoverPositionsFromRedis:
    """Test _recover_positions_from_redis via orchestrator mock."""

    @pytest.fixture
    def mock_orchestrator(self, tracker):
        """Minimal mock of TradingOrchestrator for testing recovery."""
        from services.trading.orchestrator import TradingOrchestrator

        orch = MagicMock(spec=TradingOrchestrator)
        orch._position_tracker = tracker
        orch.config = MagicMock()
        orch.config.asset_class = "stock"
        orch.config.symbols = ["005930", "000660"]
        orch.config.swing_recovery_max_age_days = 7
        orch._symbol_last_seen = {}
        orch.SWING_STRATEGIES = TradingOrchestrator.SWING_STRATEGIES
        # Bind the real method
        orch._recover_positions_from_redis = (
            TradingOrchestrator._recover_positions_from_redis.__get__(orch)
        )
        return orch

    @pytest.mark.asyncio
    async def test_recover_stock_positions(self, mock_orchestrator):
        today_pos = _make_redis_position(
            pos_id="today-001",
            code="003530",
            strategy="bb_reversion",
            entry_time=datetime.now(),
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [today_pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 1
        assert mock_orchestrator._position_tracker.position_count == 1

    @pytest.mark.asyncio
    async def test_recover_futures_short(self, mock_orchestrator):
        mock_orchestrator.config.asset_class = "futures"
        today_pos = _make_redis_position(
            pos_id="fut-001",
            code="A01603",
            name="KOSPI200선물",
            side="short",
            quantity=1,
            entry_price=837.0,
            current_price=835.0,
            strategy="rl_mppo",
            entry_time=datetime.now(),
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [today_pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 1
        pos = mock_orchestrator._position_tracker.positions[0]
        assert pos.side == PositionSide.SHORT
        assert pos.code == "A01603"

    @pytest.mark.asyncio
    async def test_filter_stale_intraday(self, mock_orchestrator):
        """Intraday strategy positions from yesterday should be filtered out."""
        yesterday = datetime.now() - timedelta(days=1)
        stale_pos = _make_redis_position(
            pos_id="stale-001",
            strategy="rl_mppo",  # not in SWING_STRATEGIES
            entry_time=yesterday,
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [stale_pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 0
        reader_inst.remove_position.assert_called_once_with("stale-001")

    @pytest.mark.asyncio
    async def test_filter_stale_swing(self, mock_orchestrator):
        """Swing positions older than 7 days should be filtered out."""
        old = datetime.now() - timedelta(days=10)
        stale_pos = _make_redis_position(
            pos_id="old-swing",
            strategy="bb_reversion",  # in SWING_STRATEGIES
            entry_time=old,
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [stale_pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 0
        reader_inst.remove_position.assert_called_once_with("old-swing")

    @pytest.mark.asyncio
    async def test_keep_swing_within_age(self, mock_orchestrator):
        """Swing positions within 7 days should be recovered."""
        three_days_ago = datetime.now() - timedelta(days=3)
        pos = _make_redis_position(
            pos_id="swing-ok",
            strategy="bb_reversion",
            entry_time=three_days_ago,
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 1
        reader_inst.remove_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_keep_pattern_pullback_within_swing_age(self, mock_orchestrator):
        """pattern_pullback is a daily swing strategy and must survive restart."""
        three_days_ago = datetime.now() - timedelta(days=3)
        pos = _make_redis_position(
            pos_id="pattern-swing-ok",
            strategy="pattern_pullback",
            entry_time=three_days_ago,
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 1
        reader_inst.remove_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_recover_with_missing_fields(self, mock_orchestrator):
        """Positions without highest_price/lowest_price should use fallbacks."""
        pos = _make_redis_position(
            pos_id="legacy-001",
            entry_price=10000.0,
            current_price=10500.0,
            entry_time=datetime.now(),
            # No highest_price, lowest_price, fee_rate, stop_price
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [pos]
            reader_inst.remove_position = MagicMock()

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 1
        recovered = mock_orchestrator._position_tracker.positions[0]
        assert recovered.highest_price == 10500.0  # max(entry, current)
        assert recovered.lowest_price == 10000.0  # min(entry, current)
        assert recovered.fee_rate == 0.003  # default

    @pytest.mark.asyncio
    async def test_empty_redis(self, mock_orchestrator):
        """Empty Redis should return 0 gracefully."""
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = []

            count = await mock_orchestrator._recover_positions_from_redis()

        assert count == 0

    @pytest.mark.asyncio
    async def test_websocket_subscription_added(self, mock_orchestrator):
        """Recovered position symbols should be added to config.symbols."""
        pos = _make_redis_position(
            pos_id="ws-test",
            code="003530",  # not in initial symbols
            entry_time=datetime.now(),
        )
        with patch("shared.streaming.trading_state.TradingStateReader") as MockReader:
            reader_inst = MockReader.return_value
            reader_inst.get_positions.return_value = [pos]
            reader_inst.remove_position = MagicMock()

            await mock_orchestrator._recover_positions_from_redis()

        assert "003530" in mock_orchestrator.config.symbols


# -- Serialization roundtrip test --


class TestSerializationRoundtrip:
    def test_serialize_includes_recovery_fields(self):
        """_serialize_position should include highest/lowest/fee/stop."""
        from shared.streaming.trading_state import TradingStatePublisher

        pos = Position(
            id="rt-001",
            code="005930",
            name="삼성전자",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=70000.0,
            entry_time=datetime.now(),
            current_price=72000.0,
            highest_price=73000.0,
            lowest_price=69000.0,
            stop_price=68000.0,
            fee_rate=0.00015,
            strategy="bb_reversion",
            state=PositionState.MAXIMIZE,
        )
        data = TradingStatePublisher._serialize_position(pos)

        assert data["highest_price"] == 73000.0
        assert data["lowest_price"] == 69000.0
        assert data["fee_rate"] == 0.00015
        assert data["stop_price"] == 68000.0
        assert data["state"] == "maximize"
        assert data["side"] == "long"
