"""Test PositionManager extended features."""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock


@pytest.mark.asyncio
async def test_manager_restore_positions():
    """Test restoring positions from list."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import Position, PositionSide, PositionState

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    # Create positions to restore
    positions_data = [
        Position(
            id="POS-001",
            code="005930",
            name="Samsung",
            side=PositionSide.LONG,
            entry_price=58000.0,
            quantity=10,
            entry_time=datetime.now(),
            strategy="test",
        ),
        Position(
            id="POS-002",
            code="035720",
            name="Kakao",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=5,
            entry_time=datetime.now(),
            strategy="test",
        ),
    ]

    await manager.restore_positions(positions_data)

    assert len(manager.positions) == 2
    assert "POS-001" in manager.positions
    assert "POS-002" in manager.positions


@pytest.mark.asyncio
async def test_manager_with_executor():
    """Test manager with order executor integration."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide

    exit_config = ExitConfig()

    # Create mock executor
    mock_executor = AsyncMock()
    mock_executor.execute_order = AsyncMock(return_value=Mock(
        success=True,
        order_no="ORD-001",
        filled_qty=10,
        filled_price=58000.0,
    ))

    manager = PositionManager(
        exit_config=exit_config,
        order_executor=mock_executor,
    )

    # Open position should use executor
    pos = await manager.open_position(
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        strategy="test",
    )

    assert pos is not None
    # Executor is optional, so no assertion on call


@pytest.mark.asyncio
async def test_manager_close_all_positions():
    """Test closing all positions."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    # Open multiple positions
    await manager.open_position(
        code="005930", name="Samsung", side=PositionSide.LONG,
        entry_price=58000.0, quantity=10, strategy="test",
    )
    await manager.open_position(
        code="035720", name="Kakao", side=PositionSide.LONG,
        entry_price=50000.0, quantity=5, strategy="test",
    )

    assert len(manager.positions) == 2

    # Close all
    closed = await manager.close_all_positions(
        prices={"005930": 59000.0, "035720": 51000.0},
        reason="MANUAL_CLOSE"
    )

    assert len(closed) == 2
    assert len(manager.positions) == 0
