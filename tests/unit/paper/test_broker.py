"""Test VirtualBroker."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_broker_buy_order():
    """Test market buy order execution."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide

    broker = VirtualBroker(initial_balance=1000000)

    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        price=58000  # Simulated market price
    )

    assert order.filled is True
    assert broker.get_position("005930") is not None
    assert broker.balance < 1000000  # Reduced by purchase


@pytest.mark.asyncio
async def test_broker_position_tracking():
    """Test position tracking."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide

    broker = VirtualBroker(initial_balance=1000000)

    # Buy
    await broker.submit_order("005930", OrderSide.BUY, 10, 58000)

    position = broker.get_position("005930")
    assert position.quantity == 10

    # Sell half
    await broker.submit_order("005930", OrderSide.SELL, 5, 59000)

    position = broker.get_position("005930")
    assert position.quantity == 5
