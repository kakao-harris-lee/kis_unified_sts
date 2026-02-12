"""Test PositionManager class."""
import pytest


@pytest.mark.asyncio
async def test_manager_creation():
    """Test PositionManager instantiation."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    assert manager.exit_config == exit_config
    assert len(manager.positions) == 0


@pytest.mark.asyncio
async def test_manager_open_position():
    """Test opening a new position."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    pos = await manager.open_position(
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        strategy="test",
    )

    assert pos is not None
    assert pos.code == "005930"
    assert len(manager.positions) == 1


@pytest.mark.asyncio
async def test_manager_close_position():
    """Test closing a position."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    pos = await manager.open_position(
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        strategy="test",
    )

    closed = await manager.close_position(pos.id, exit_price=59000.0, reason="TEST")

    assert closed is not None
    assert closed.exit_price == 59000.0
    assert closed.exit_reason == "TEST"
    assert len(manager.positions) == 0


@pytest.mark.asyncio
async def test_manager_get_positions_by_code():
    """Test getting positions by stock code."""
    from shared.position.manager import PositionManager
    from shared.position.exit_checker import ExitConfig
    from shared.models.position import PositionSide

    exit_config = ExitConfig()
    manager = PositionManager(exit_config=exit_config)

    await manager.open_position(
        code="005930", name="Samsung", side=PositionSide.LONG,
        entry_price=58000.0, quantity=10, strategy="test",
    )
    await manager.open_position(
        code="035720", name="Kakao", side=PositionSide.LONG,
        entry_price=50000.0, quantity=5, strategy="test",
    )

    samsung_positions = manager.get_positions_by_code("005930")
    assert len(samsung_positions) == 1
    assert samsung_positions[0].code == "005930"
