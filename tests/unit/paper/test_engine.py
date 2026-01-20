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
