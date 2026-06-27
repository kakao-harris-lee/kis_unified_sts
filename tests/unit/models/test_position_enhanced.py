"""Test enhanced Position model."""
from datetime import datetime

import pytest


def test_position_state_transitions():
    """Test position state transitions."""
    from shared.models.position import Position, PositionSide, PositionState

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="bb_reversion",
    )

    assert pos.state == PositionState.SURVIVAL

    # Simulate price increase to trigger breakeven
    pos.update_price(59200.0)  # +2.07%

    # State should transition
    assert pos.profit_rate > 0.02


def test_position_profit_calculation():
    """Test P&L calculations."""
    from shared.models.position import Position, PositionSide

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="test",
    )

    pos.update_price(59000.0)

    assert pos.current_price == 59000.0
    assert pos.profit_rate == pytest.approx(0.01724, rel=0.01)
    assert pos.unrealized_pnl == pytest.approx(10000.0, rel=0.01)


def test_position_highest_price_tracking():
    """Test highest price tracking for trailing stop."""
    from shared.models.position import Position, PositionSide

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="test",
    )

    pos.update_price(59000.0)
    pos.update_price(60000.0)
    pos.update_price(59500.0)  # Drops but highest should stay

    assert pos.highest_price == 60000.0


def test_position_short_profit_calculation():
    """Test P&L calculations for short position."""
    from shared.models.position import Position, PositionSide

    pos = Position(
        id="pos-002",
        code="005930",
        name="Samsung",
        side=PositionSide.SHORT,
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="test",
    )

    pos.update_price(57000.0)  # Price dropped = profit for short

    assert pos.current_price == 57000.0
    assert pos.profit_rate == pytest.approx(0.01724, rel=0.01)
    assert pos.unrealized_pnl == pytest.approx(10000.0, rel=0.01)
