"""Test PaperTradingEngine."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_engine_initialization():
    """Test engine initialization."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig(initial_balance=5_000_000)
    engine = PaperTradingEngine(config)

    assert engine.broker.balance == 5_000_000
    assert engine.is_running is False


@pytest.mark.asyncio
async def test_engine_start_stop():
    """Test engine lifecycle."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig()
    engine = PaperTradingEngine(config)

    await engine.start()
    assert engine.is_running is True

    await engine.stop()
    assert engine.is_running is False


@pytest.mark.asyncio
async def test_engine_process_signal():
    """Test signal processing."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    config = PaperTradingConfig()
    engine = PaperTradingEngine(config)

    # Process buy signal
    order = await engine.process_signal(
        symbol="005930",
        side=OrderSide.BUY,
        price=58000,
        quantity=10,
    )

    assert order is not None
    assert order.filled is True


@pytest.mark.asyncio
async def test_engine_equity_curve_circular_buffer():
    """Test equity curve respects max_equity_points limit."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    # Create config with small buffer size for testing
    config = PaperTradingConfig(max_equity_points=5)
    engine = PaperTradingEngine(config)

    await engine.start()  # Records 1 point

    # Process multiple signals to add more equity points
    for i in range(10):
        await engine.process_signal(
            symbol=f"TEST{i:02d}",
            side=OrderSide.BUY,
            price=100,
            quantity=1,
        )

    # Should have at most max_equity_points
    assert len(engine.equity_curve) <= config.max_equity_points


@pytest.mark.asyncio
async def test_engine_equity_curve_records_on_start():
    """Test that equity is recorded on engine start."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig()
    engine = PaperTradingEngine(config)

    assert len(engine.equity_curve) == 0

    await engine.start()

    assert len(engine.equity_curve) == 1
    assert engine.equity_curve[0]["equity"] == config.initial_balance
