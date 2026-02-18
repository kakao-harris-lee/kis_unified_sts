"""Unit tests for PositionTracker partial close support.

Tests the new partial_close path in services/trading/position_tracker.py.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from services.trading.position_tracker import PositionTracker
from shared.models.position import Position, PositionSide, PositionState

# =============================================================================
# Helpers
# =============================================================================


def _make_tracker() -> PositionTracker:
    """Create a bare PositionTracker (skip async init if any)."""
    return PositionTracker()


def _add_position(
    tracker: PositionTracker,
    code: str = "005930",
    entry_price: float = 100.0,
    quantity: int = 100,
) -> Position:
    """Add a position to the tracker and return it."""
    return tracker.add_position(
        code=code,
        name="삼성전자",
        entry_price=entry_price,
        quantity=quantity,
        strategy="trix_golden",
    )


# =============================================================================
# Tests
# =============================================================================


class TestFullClose:
    def test_full_close_removes_position(self):
        """Full close (quantity=None) removes position from active tracking."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=100)

        closed = tracker.close_position(pos.id, exit_price=105.0, reason="STOP_LOSS")
        assert closed is not None
        assert closed.exit_triggered is True
        assert closed.exit_price == 105.0
        assert closed.exit_reason == "STOP_LOSS"
        # Position should be removed
        assert tracker.get_position(pos.id) is None

    def test_full_close_explicit_quantity_gte(self):
        """Explicit quantity >= pos.quantity → treated as full close."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=50)

        closed = tracker.close_position(
            pos.id, exit_price=110.0, reason="TRAILING_STOP", quantity=50
        )
        assert closed is not None
        assert closed.exit_triggered is True
        assert tracker.get_position(pos.id) is None

    def test_full_close_quantity_larger_than_held(self):
        """Quantity > pos.quantity → still full close."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=30)

        closed = tracker.close_position(
            pos.id, exit_price=102.0, reason="EOD", quantity=100
        )
        assert closed is not None
        assert tracker.get_position(pos.id) is None


class TestPartialClose:
    def test_partial_close_reduces_quantity(self):
        """Partial close with quantity < pos.quantity keeps position active."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=100)
        pid = pos.id

        closed_portion = tracker.close_position(
            pid, exit_price=105.0, reason="TRIX_PEAK_OUT", quantity=50
        )
        assert closed_portion is not None
        assert closed_portion.quantity == 50
        assert closed_portion.exit_triggered is True
        assert closed_portion.exit_price == 105.0
        assert closed_portion.exit_reason == "TRIX_PEAK_OUT"

        # Original position should still be active with reduced quantity
        remaining = tracker.get_position(pid)
        assert remaining is not None
        assert remaining.quantity == 50

    def test_partial_close_then_full_close(self):
        """Partial close → full close sequence works correctly."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=100)
        pid = pos.id

        # Step 1: Partial close 50
        partial = tracker.close_position(
            pid, exit_price=105.0, reason="PARTIAL", quantity=50
        )
        assert partial is not None
        assert partial.quantity == 50

        remaining = tracker.get_position(pid)
        assert remaining is not None
        assert remaining.quantity == 50

        # Step 2: Full close remaining
        full = tracker.close_position(pid, exit_price=110.0, reason="FULL_EXIT")
        assert full is not None
        assert full.exit_triggered is True

        # Should be removed from active
        assert tracker.get_position(pid) is None

    def test_partial_close_preserves_indices(self):
        """After partial close, position remains in by_symbol and by_strategy indices."""
        tracker = _make_tracker()
        pos = _add_position(tracker, code="005930", quantity=100)
        pid = pos.id

        tracker.close_position(pid, exit_price=105.0, reason="PARTIAL", quantity=30)

        # Position should still be in tracking
        remaining = tracker.get_position(pid)
        assert remaining is not None
        assert remaining.quantity == 70

    def test_partial_close_closed_history(self):
        """Partial close adds entry to closed positions history."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=100)
        pid = pos.id

        tracker.close_position(pid, exit_price=105.0, reason="PARTIAL", quantity=40)

        closed_list = list(tracker._closed_positions)
        assert len(closed_list) == 1
        assert closed_list[0].quantity == 40
        assert closed_list[0].exit_triggered is True


class TestPartialCloseEdgeCases:
    def test_close_nonexistent_position(self):
        """Closing a non-existent position returns None."""
        tracker = _make_tracker()
        result = tracker.close_position("nonexistent", exit_price=100.0, reason="TEST")
        assert result is None

    def test_partial_close_quantity_1(self):
        """Minimum partial close of 1 share."""
        tracker = _make_tracker()
        pos = _add_position(tracker, quantity=10)
        pid = pos.id

        closed = tracker.close_position(
            pid, exit_price=105.0, reason="PARTIAL", quantity=1
        )
        assert closed is not None
        assert closed.quantity == 1

        remaining = tracker.get_position(pid)
        assert remaining.quantity == 9
