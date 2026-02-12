"""Test PositionMonitor class."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_monitor_creation():
    """Test PositionMonitor instantiation."""
    from shared.position.monitor import PositionMonitor

    monitor = PositionMonitor(check_interval=1.0)

    assert monitor.check_interval == 1.0
    assert monitor._running is False


@pytest.mark.asyncio
async def test_monitor_add_position():
    """Test adding position to monitor."""
    from shared.position.monitor import PositionMonitor
    from shared.models.position import Position, PositionSide

    monitor = PositionMonitor()

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

    monitor.add_position(pos)

    assert "pos-001" in monitor.positions
    assert monitor.positions["pos-001"] is pos


@pytest.mark.asyncio
async def test_monitor_update_prices():
    """Test price update for all positions."""
    from shared.position.monitor import PositionMonitor
    from shared.models.position import Position, PositionSide

    monitor = PositionMonitor()

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

    monitor.add_position(pos)
    monitor.update_price("005930", 59000.0)

    assert monitor.positions["pos-001"].current_price == 59000.0
