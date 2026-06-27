"""Tests for close_all price=0 guard in PositionTracker."""

from __future__ import annotations

import pytest

from services.trading.position_tracker import PositionTracker


@pytest.fixture
def tracker():
    """Create a PositionTracker with one open position."""
    t = PositionTracker()
    pos = t.add_position(
        code="005930",
        name="삼성전자",
        entry_price=70000,
        quantity=10,
        strategy="test",
    )
    assert pos is not None
    assert t.position_count == 1
    return t


class TestCloseAllPriceGuard:

    def test_close_all_falls_back_on_zero_close(self, tracker):
        """When close=0, falls back to current_price (entry_price). Close succeeds."""
        closed = tracker.close_all(
            market_data={"005930": {"close": 0}},
            reason="EOD",
        )
        # Fallback to current_price=70000, which is valid → closes
        assert len(closed) == 1
        assert closed[0].exit_price == 70000

    def test_close_all_skips_when_both_zero(self, tracker):
        """When close=0 AND current_price=0, position must not be closed."""
        pos = list(tracker._positions.values())[0]
        pos.current_price = 0

        closed = tracker.close_all(
            market_data={"005930": {"close": 0}},
            reason="EOD",
        )
        assert len(closed) == 0
        assert tracker.position_count == 1

    def test_close_all_skips_negative_price(self, tracker):
        """Positions with negative price must not be closed."""
        closed = tracker.close_all(
            market_data={"005930": {"close": -100}},
            reason="EOD",
        )
        assert len(closed) == 0
        assert tracker.position_count == 1

    def test_close_all_skips_none_price_zero_fallback(self, tracker):
        """Positions with None price and current_price=0 must not be closed."""
        pos = list(tracker._positions.values())[0]
        pos.current_price = 0

        closed = tracker.close_all(
            market_data={"005930": {"close": None}},
            reason="EOD",
        )
        assert len(closed) == 0
        assert tracker.position_count == 1

    def test_close_all_succeeds_with_valid_price(self, tracker):
        """Positions with valid price should be closed normally."""
        closed = tracker.close_all(
            market_data={"005930": {"close": 71000}},
            reason="EOD",
        )
        assert len(closed) == 1
        assert tracker.position_count == 0

    def test_close_all_uses_fallback_current_price(self, tracker):
        """If market data has no close, falls back to position.current_price."""
        pos = list(tracker._positions.values())[0]
        pos.current_price = 69000

        closed = tracker.close_all(
            market_data={"005930": {}},
            reason="EOD",
        )
        assert len(closed) == 1
        assert closed[0].exit_price == 69000
