"""Test TrendPositionManager."""
import pytest


def test_position_manager_creation():
    """Test TrendPositionManager instantiation."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig()
    manager = TrendPositionManager(config)

    assert manager.config == config


def test_open_long_position():
    """Test opening a long position."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig(
        atr_stop_multiplier=2.0,
        atr_target_multiplier=3.0,
    )
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="LONG",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
        timestamp=1705300800.0,
    )

    assert position.direction == "LONG"
    assert position.entry_price == 330.0
    assert position.stop_loss == 328.0  # 330 - 2*1.0
    assert position.take_profit == 333.0  # 330 + 3*1.0
    assert position.size == 5.0
    assert position.is_open


def test_open_short_position():
    """Test opening a short position."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig(
        atr_stop_multiplier=2.0,
        atr_target_multiplier=3.0,
    )
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="SHORT",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
    )

    assert position.direction == "SHORT"
    assert position.stop_loss == 332.0  # 330 + 2*1.0
    assert position.take_profit == 327.0  # 330 - 3*1.0


def test_trailing_stop_update_long():
    """Test trailing stop updates for long position."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig(atr_stop_multiplier=2.0)
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="LONG",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
    )

    initial_stop = position.stop_loss

    # Price moves up - stop should trail
    manager.update_trailing_stop(position, current_price=332.0, atr=1.0)

    # Stop should have moved up
    assert position.stop_loss > initial_stop
    assert position.stop_loss == 330.0  # 332 - 2*1.0


def test_trailing_stop_no_decrease_long():
    """Test trailing stop never decreases for long."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig(atr_stop_multiplier=2.0)
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="LONG",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
    )

    # Price moves up
    manager.update_trailing_stop(position, current_price=335.0, atr=1.0)
    high_stop = position.stop_loss

    # Price moves down - stop should NOT decrease
    manager.update_trailing_stop(position, current_price=332.0, atr=1.0)

    assert position.stop_loss == high_stop


def test_check_stop_hit():
    """Test stop loss detection."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig(atr_stop_multiplier=2.0)
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="LONG",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
    )

    # Price above stop - not hit
    assert not manager.is_stop_hit(position, current_price=329.0)

    # Price at stop - hit
    assert manager.is_stop_hit(position, current_price=328.0)

    # Price below stop - hit
    assert manager.is_stop_hit(position, current_price=327.0)


def test_check_target_hit():
    """Test take profit detection."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig(atr_target_multiplier=3.0)
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="LONG",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
    )

    # Price below target - not hit
    assert not manager.is_target_hit(position, current_price=332.0)

    # Price at target - hit
    assert manager.is_target_hit(position, current_price=333.0)


def test_close_position():
    """Test closing a position."""
    from shared.trend.position_manager import TrendPositionManager
    from shared.trend.config import TrendConfig

    config = TrendConfig()
    manager = TrendPositionManager(config)

    position = manager.open_position(
        direction="LONG",
        entry_price=330.0,
        atr=1.0,
        size=5.0,
    )

    assert position.is_open

    manager.close_position(position, exit_price=335.0, reason="TARGET_HIT")

    assert not position.is_open
    assert position.exit_price == 335.0
    assert position.exit_reason == "TARGET_HIT"
    assert position.pnl == pytest.approx(5.0 * 5.0)  # (335-330) * 5
