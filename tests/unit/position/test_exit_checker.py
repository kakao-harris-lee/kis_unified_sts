"""Test ExitChecker class for 3-Stage state machine."""
from datetime import datetime


def test_exit_checker_creation():
    """Test ExitChecker instantiation with config."""
    from shared.position.exit_checker import ExitChecker, ExitConfig

    config = ExitConfig(
        hard_stop_pct=2.0,
        breakeven_threshold_pct=2.0,
        breakeven_buffer_pct=0.1,
        maximize_threshold_pct=5.0,
        trailing_stop_pct=3.0,
    )

    checker = ExitChecker(config)

    assert checker.config.hard_stop_pct == 2.0
    assert checker.config.breakeven_threshold_pct == 2.0


def test_survival_stage_hard_stop():
    """Test hard stop in SURVIVAL stage."""
    from shared.position.exit_checker import ExitChecker, ExitConfig
    from shared.models.position import Position, PositionSide

    config = ExitConfig(hard_stop_pct=2.0)
    checker = ExitChecker(config)

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

    # Price drops 2.5% -> should trigger hard stop
    pos.update_price(56550.0)  # -2.5%

    should_exit, reason = checker.check(pos)

    assert should_exit is True
    assert "HARD_STOP" in reason


def test_survival_to_breakeven_transition():
    """Test state transition from SURVIVAL to BREAKEVEN."""
    from shared.position.exit_checker import ExitChecker, ExitConfig
    from shared.models.position import Position, PositionSide, PositionState

    config = ExitConfig(
        hard_stop_pct=2.0,
        breakeven_threshold_pct=2.0,
    )
    checker = ExitChecker(config)

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

    # Price increases 2.5% -> should transition to BREAKEVEN
    pos.update_price(59450.0)  # +2.5%

    checker.update_state(pos)

    assert pos.state == PositionState.BREAKEVEN


def test_maximize_stage_trailing_stop():
    """Test trailing stop in MAXIMIZE stage."""
    from shared.position.exit_checker import ExitChecker, ExitConfig
    from shared.models.position import Position, PositionSide, PositionState

    config = ExitConfig(
        hard_stop_pct=2.0,
        breakeven_threshold_pct=2.0,
        maximize_threshold_pct=5.0,
        trailing_stop_pct=3.0,
    )
    checker = ExitChecker(config)

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="test",
        state=PositionState.MAXIMIZE,
    )

    # Set highest price and then drop
    pos.update_price(62000.0)  # New high
    pos.update_price(60000.0)  # Drop 3.2% from high

    should_exit, reason = checker.check(pos)

    assert should_exit is True
    assert "TRAILING" in reason
