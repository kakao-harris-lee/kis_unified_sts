"""Integration tests for position management flow.

Tests the complete flow from position opening through exit condition
monitoring and closing.
"""
import pytest
from datetime import datetime


@pytest.mark.integration
@pytest.mark.asyncio
async def test_position_lifecycle():
    """Test complete position lifecycle: open -> monitor -> close."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide, PositionState

    # Setup
    exit_config = ExitConfig(
        hard_stop_pct=2.0,
        breakeven_threshold_pct=2.0,
        breakeven_buffer_pct=0.1,
        maximize_threshold_pct=5.0,
        trailing_stop_pct=3.0,
    )
    manager = PositionManager(exit_config=exit_config)

    # Open position
    position = await manager.open_position(
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        strategy="test",
    )

    assert position is not None
    assert position.state == PositionState.SURVIVAL
    assert len(manager.positions) == 1

    # Update price (profit)
    manager.update_price("005930", 59500.0)  # +2.6% profit
    assert position.state == PositionState.BREAKEVEN

    # Update price more (bigger profit)
    manager.update_price("005930", 61500.0)  # +6% profit
    assert position.state == PositionState.MAXIMIZE

    # Close position
    closed = await manager.close_position(
        position.id,
        exit_price=61000.0,
        reason="MANUAL_CLOSE",
    )

    assert closed is not None
    assert closed.exit_price == 61000.0
    assert len(manager.positions) == 0
    assert len(manager.closed_positions) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_positions():
    """Test managing multiple positions simultaneously."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    # Open multiple positions
    positions = []
    for i, code in enumerate(["005930", "000660", "035720"]):
        pos = await manager.open_position(
            code=code,
            name=f"Stock-{i}",
            side=PositionSide.LONG,
            entry_price=50000.0 + i * 10000,
            quantity=10,
            strategy="multi_test",
        )
        positions.append(pos)

    assert len(manager.positions) == 3

    # Update prices for all
    manager.update_prices({
        "005930": 52000.0,
        "000660": 62000.0,
        "035720": 72000.0,
    })

    # Close all
    prices = {
        "005930": 53000.0,
        "000660": 63000.0,
        "035720": 73000.0,
    }
    closed = await manager.close_all_positions(prices, "BATCH_CLOSE")

    assert len(closed) == 3
    assert len(manager.positions) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_position_restore():
    """Test position restoration after restart."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import Position, PositionSide, PositionState

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    # Simulate saved positions (e.g., from database)
    saved_positions = [
        Position(
            id="RESTORED-001",
            code="005930",
            name="Samsung",
            side=PositionSide.LONG,
            entry_price=58000.0,
            quantity=10,
            entry_time=datetime.now(),
            strategy="restored",
            state=PositionState.BREAKEVEN,
        ),
        Position(
            id="RESTORED-002",
            code="000660",
            name="SK Hynix",
            side=PositionSide.LONG,
            entry_price=120000.0,
            quantity=5,
            entry_time=datetime.now(),
            strategy="restored",
            state=PositionState.MAXIMIZE,
        ),
    ]

    # Restore positions
    await manager.restore_positions(saved_positions)

    assert len(manager.positions) == 2
    assert "RESTORED-001" in manager.positions
    assert "RESTORED-002" in manager.positions
    assert manager.positions["RESTORED-001"].state == PositionState.BREAKEVEN
    assert manager.positions["RESTORED-002"].state == PositionState.MAXIMIZE
