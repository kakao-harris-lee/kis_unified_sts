"""Tests for services/trading/position_tracker.py"""

import pytest
from datetime import datetime
from collections import deque


class TestPositionTrackerConfig:
    """PositionTrackerConfig tests"""

    def test_default_values(self):
        """Test default configuration values"""
        from services.trading.position_tracker import PositionTrackerConfig

        config = PositionTrackerConfig()
        assert config.max_positions == 10
        assert config.max_positions_per_symbol == 1
        assert config.default_breakeven_threshold_pct == 0.015
        assert config.default_maximize_threshold_pct == 0.03

    def test_validation_passes(self):
        """Test valid configuration passes"""
        from services.trading.position_tracker import PositionTrackerConfig

        config = PositionTrackerConfig(
            max_positions=5,
            max_positions_per_symbol=2,
            default_breakeven_threshold_pct=0.02,
            default_maximize_threshold_pct=0.05,
        )
        assert config.max_positions == 5

    def test_validation_max_positions_bounds(self):
        """Test max_positions bounds validation"""
        from services.trading.position_tracker import PositionTrackerConfig

        with pytest.raises(ValueError, match="max_positions"):
            PositionTrackerConfig(max_positions=0)

        with pytest.raises(ValueError, match="max_positions"):
            PositionTrackerConfig(max_positions=200)

    def test_validation_thresholds(self):
        """Test threshold validation"""
        from services.trading.position_tracker import PositionTrackerConfig

        # maximize must be greater than breakeven
        with pytest.raises(ValueError, match="maximize_threshold_pct"):
            PositionTrackerConfig(
                default_breakeven_threshold_pct=0.05,
                default_maximize_threshold_pct=0.03,
            )

    def test_from_dict(self):
        """Test from_dict factory method"""
        from services.trading.position_tracker import PositionTrackerConfig

        config = PositionTrackerConfig.from_dict({
            "max_positions": 5,
            "max_positions_per_symbol": 2,
            "default_fee_rate": 0.002,
        })
        assert config.max_positions == 5
        assert config.default_fee_rate == 0.002

    def test_from_dict_type_validation(self):
        """Test from_dict type validation"""
        from services.trading.position_tracker import PositionTrackerConfig

        with pytest.raises(TypeError, match="max_positions"):
            PositionTrackerConfig.from_dict({"max_positions": "invalid"})


class TestPositionTracker:
    """PositionTracker tests"""

    def test_init_default(self):
        """Test default initialization"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        assert tracker.position_count == 0
        assert tracker.config.max_positions == 10

    def test_can_open_position_empty(self):
        """Test can open when empty"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        assert tracker.can_open_position() is True

    def test_can_open_position_full(self):
        """Test cannot open when full"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        tracker = PositionTracker(config=PositionTrackerConfig(max_positions=1))

        tracker.add_position(
            code="005930",
            name="Samsung",
            entry_price=71000,
            quantity=10,
            strategy="test",
        )

        assert tracker.can_open_position() is False

    def test_can_open_position_per_symbol_limit(self):
        """Test per-symbol limit"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        tracker = PositionTracker(
            config=PositionTrackerConfig(max_positions=10, max_positions_per_symbol=1)
        )

        tracker.add_position(
            code="005930",
            name="Samsung",
            entry_price=71000,
            quantity=10,
            strategy="test",
        )

        # Cannot open another for same symbol
        assert tracker.can_open_position("005930") is False
        # Can open for different symbol
        assert tracker.can_open_position("000660") is True

    def test_add_position(self):
        """Test adding position"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        position = tracker.add_position(
            code="005930",
            name="Samsung",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
        )

        assert position is not None
        assert position.code == "005930"
        assert position.entry_price == 71000
        assert tracker.position_count == 1

    def test_add_position_returns_none_when_full(self):
        """Test add_position returns None when limit reached"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        tracker = PositionTracker(config=PositionTrackerConfig(max_positions=1))

        pos1 = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )
        pos2 = tracker.add_position(
            code="000660", name="Test2", entry_price=100, quantity=1, strategy="test"
        )

        assert pos1 is not None
        assert pos2 is None

    def test_get_position(self):
        """Test getting position by ID"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        added = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )

        retrieved = tracker.get_position(added.id)
        assert retrieved is added

        # Non-existent
        assert tracker.get_position("nonexistent") is None

    def test_get_positions_by_symbol(self):
        """Test getting positions by symbol"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        tracker = PositionTracker(
            config=PositionTrackerConfig(max_positions_per_symbol=2)
        )

        tracker.add_position(
            code="005930", name="A", entry_price=100, quantity=1, strategy="s1"
        )
        tracker.add_position(
            code="005930", name="B", entry_price=110, quantity=1, strategy="s2"
        )
        tracker.add_position(
            code="000660", name="C", entry_price=100, quantity=1, strategy="s1"
        )

        samsung = tracker.get_positions_by_symbol("005930")
        assert len(samsung) == 2

        hynix = tracker.get_positions_by_symbol("000660")
        assert len(hynix) == 1

    def test_get_positions_by_strategy(self):
        """Test getting positions by strategy"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(
            code="005930", name="A", entry_price=100, quantity=1, strategy="bb_reversion"
        )
        tracker.add_position(
            code="000660", name="B", entry_price=100, quantity=1, strategy="bb_reversion"
        )
        tracker.add_position(
            code="035720", name="C", entry_price=100, quantity=1, strategy="momentum"
        )

        bb_positions = tracker.get_positions_by_strategy("bb_reversion")
        assert len(bb_positions) == 2

        momentum_positions = tracker.get_positions_by_strategy("momentum")
        assert len(momentum_positions) == 1

    def test_update_prices(self):
        """Test updating prices"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        position = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )

        tracker.update_prices({"005930": {"close": 110}})

        assert position.current_price == 110
        assert position.highest_price == 110

    def test_update_prices_dict_format(self):
        """Test updating prices with different formats"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        position = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )

        # Test with "price" key
        tracker.update_prices({"005930": {"price": 115}})
        assert position.current_price == 115

    def test_update_prices_invalid_ignored(self):
        """Test invalid prices are ignored"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        position = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )

        # Negative price should be ignored
        tracker.update_prices({"005930": {"close": -10}})
        assert position.current_price == 100  # Unchanged

        # Out of range price should be ignored
        tracker.update_prices({"005930": {"close": 999_999_999}})
        assert position.current_price == 100  # Unchanged

    def test_update_states(self):
        """Test state transitions"""
        from services.trading.position_tracker import PositionTracker
        from shared.models.position import PositionState

        tracker = PositionTracker()
        position = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )

        assert position.state == PositionState.SURVIVAL

        # Update to trigger breakeven (1.5% = price 101.5)
        tracker.update_prices({"005930": {"close": 102}})
        transitions = tracker.update_states()

        assert len(transitions) == 1
        assert transitions[0][2] == PositionState.BREAKEVEN

    def test_close_position(self):
        """Test closing position"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        position = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=10, strategy="test"
        )
        position_id = position.id

        closed = tracker.close_position(position_id, exit_price=110, reason="TEST_EXIT")

        assert closed is not None
        assert closed.exit_price == 110
        assert closed.exit_reason == "TEST_EXIT"
        assert tracker.position_count == 0
        assert tracker.get_position(position_id) is None

    def test_close_position_not_found(self):
        """Test closing non-existent position"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        closed = tracker.close_position("nonexistent", exit_price=100, reason="test")
        assert closed is None

    def test_close_all(self):
        """Test closing all positions"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(
            code="005930", name="A", entry_price=100, quantity=1, strategy="test"
        )
        tracker.add_position(
            code="000660", name="B", entry_price=200, quantity=1, strategy="test"
        )

        market_data = {"005930": {"close": 110}, "000660": {"close": 220}}

        closed = tracker.close_all(market_data, reason="EOD")

        assert len(closed) == 2
        assert tracker.position_count == 0

    def test_uuid_generator_injection(self):
        """Test UUID generator can be injected for testing"""
        from services.trading.position_tracker import PositionTracker

        counter = [0]

        def sequential_id():
            counter[0] += 1
            return f"test-id-{counter[0]}"

        tracker = PositionTracker(uuid_generator=sequential_id)
        pos1 = tracker.add_position(
            code="A", name="A", entry_price=100, quantity=1, strategy="test"
        )
        pos2 = tracker.add_position(
            code="B", name="B", entry_price=100, quantity=1, strategy="test"
        )

        assert pos1.id == "test-id-1"
        assert pos2.id == "test-id-2"

    def test_events_bounded_by_deque(self):
        """Test events history is bounded"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        config = PositionTrackerConfig(max_events=5)
        tracker = PositionTracker(config=config)

        # Add more positions than max_events
        for i in range(10):
            tracker.add_position(
                code=f"TEST{i}", name=f"Test{i}", entry_price=100, quantity=1, strategy="test"
            )

        # Events should be capped
        assert len(tracker._events) <= 5

    def test_closed_positions_bounded_by_deque(self):
        """Test closed positions history is bounded"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        config = PositionTrackerConfig(max_closed_positions=3)
        tracker = PositionTracker(config=config)

        # Add and close positions
        for i in range(5):
            pos = tracker.add_position(
                code=f"TEST{i}", name=f"Test{i}", entry_price=100, quantity=1, strategy="test"
            )
            tracker.close_position(pos.id, exit_price=110, reason="test")

        # Closed positions should be capped
        assert len(tracker._closed_positions) <= 3

    def test_get_stats(self):
        """Test get_stats returns correct info"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=10, strategy="test"
        )
        tracker.update_prices({"005930": {"close": 110}})

        stats = tracker.get_stats()

        assert stats["open_positions"] == 1
        assert stats["unrealized_pnl"] == 100  # (110-100) * 10
        assert "by_strategy" in stats
        assert "by_symbol" in stats

    def test_get_recent_events(self):
        """Test getting recent events"""
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=1, strategy="test"
        )

        events = tracker.get_recent_events(limit=5)

        assert len(events) >= 1
        assert events[0]["type"] == "opened"
        assert "position_id" in events[0]

    def test_events_deque_fifo_order(self):
        """Test events deque maintains FIFO order"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        config = PositionTrackerConfig(max_events=5)
        tracker = PositionTracker(config=config)

        # Add 7 positions (more than max_events=5)
        for i in range(7):
            tracker.add_position(
                code=f"TEST{i}", name=f"Test{i}", entry_price=100, quantity=1, strategy="test"
            )

        # Events should be capped at 5
        assert len(tracker._events) == 5

        # Should contain most recent events (TEST2 through TEST6)
        # The oldest events (TEST0, TEST1) should have been evicted
        events = tracker.get_recent_events(limit=10)
        event_codes = [e["details"].get("code") for e in events]

        # Verify FIFO: oldest evicted first, newest kept
        assert "TEST0" not in event_codes
        assert "TEST1" not in event_codes
        assert "TEST6" in event_codes

    def test_closed_positions_deque_fifo_order(self):
        """Test closed positions deque maintains FIFO order"""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        config = PositionTrackerConfig(max_closed_positions=3)
        tracker = PositionTracker(config=config)

        # Add and close 5 positions
        for i in range(5):
            pos = tracker.add_position(
                code=f"TEST{i}", name=f"Test{i}", entry_price=100, quantity=1, strategy="test"
            )
            tracker.close_position(pos.id, exit_price=110, reason="test")

        # Closed positions should be capped at 3
        assert len(tracker._closed_positions) == 3

        # Should contain most recent closed positions
        closed_codes = [p.code for p in tracker._closed_positions]

        # FIFO: oldest evicted first
        assert "TEST0" not in closed_codes
        assert "TEST1" not in closed_codes
        assert "TEST4" in closed_codes
        assert "TEST3" in closed_codes
        assert "TEST2" in closed_codes


class TestConcurrentOperations:
    """Thread-safety tests for PositionTracker"""

    @pytest.mark.asyncio
    async def test_concurrent_close_same_position(self):
        """Test that concurrent close of same position is handled safely"""
        import asyncio
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()
        pos = tracker.add_position(
            code="005930", name="Test", entry_price=100, quantity=10, strategy="test"
        )

        # Simulate concurrent close attempts
        async def close_position():
            return tracker.close_position(pos.id, exit_price=110, reason="test")

        # Run multiple close attempts concurrently
        results = await asyncio.gather(
            close_position(),
            close_position(),
            close_position(),
        )

        # Only one should succeed (return the position)
        successful = [r for r in results if r is not None]
        failed = [r for r in results if r is None]

        assert len(successful) == 1
        assert len(failed) == 2
        assert tracker.position_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_add_and_close(self):
        """Test concurrent add and close operations"""
        import asyncio
        from services.trading.position_tracker import PositionTracker

        tracker = PositionTracker()

        async def add_and_close(code: str):
            pos = tracker.add_position(
                code=code, name=f"Test-{code}", entry_price=100, quantity=10, strategy="test"
            )
            if pos:
                await asyncio.sleep(0.001)  # Small delay
                return tracker.close_position(pos.id, exit_price=110, reason="test")
            return None

        # Run multiple add/close cycles concurrently
        results = await asyncio.gather(
            *[add_and_close(f"TEST{i}") for i in range(5)]
        )

        # All should succeed
        successful = [r for r in results if r is not None]
        assert len(successful) == 5
        assert tracker.position_count == 0
