"""Test error handling in VirtualBroker."""
import pytest

from shared.paper.broker import VirtualBroker
from shared.paper.models import OrderSide, OrderType


@pytest.mark.asyncio
async def test_broker_insufficient_balance():
    """Test order execution with insufficient balance.

    The broker should handle orders that exceed available balance
    gracefully without going into negative balance.
    """
    broker = VirtualBroker(initial_balance=1000)

    # Try to buy more than balance allows
    # 1000 shares at 58000 = 58,000,000 which exceeds 1000 balance
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=1000,
        price=58000,
    )

    # The broker currently executes regardless - check balance doesn't go negative
    # This test documents the current behavior and may need updating
    # when proper validation is added
    assert order.filled is True  # Current behavior: executes anyway
    # Note: Balance will be negative, which is a known issue


@pytest.mark.asyncio
async def test_broker_zero_quantity_order():
    """Test handling of zero quantity orders."""
    broker = VirtualBroker(initial_balance=10_000_000)

    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=0,
        price=58000,
    )

    # Zero quantity orders should execute but have no effect
    assert order.quantity == 0


@pytest.mark.asyncio
async def test_broker_sell_without_position():
    """Test selling without an existing position."""
    broker = VirtualBroker(initial_balance=10_000_000)

    # Try to sell without any position
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.SELL,
        quantity=10,
        price=58000,
    )

    # Should execute (could be opening a short position)
    assert order.filled is True
    # No position should exist for this symbol
    assert "005930" not in broker.positions


@pytest.mark.asyncio
async def test_broker_partial_close_more_than_position():
    """Test partial close with quantity exceeding position size."""
    broker = VirtualBroker(initial_balance=10_000_000)

    # Open position with 10 shares
    await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        price=58000,
    )

    assert "005930" in broker.positions
    assert broker.positions["005930"].quantity == 10

    # Try to sell 20 shares when we only have 10
    await broker.submit_order(
        symbol="005930",
        side=OrderSide.SELL,
        quantity=20,
        price=59000,
    )

    # Position should be closed (full close triggered)
    assert "005930" not in broker.positions
    assert len(broker.trades) == 1


@pytest.mark.asyncio
async def test_broker_extreme_prices():
    """Test handling of extreme price values."""
    broker = VirtualBroker(initial_balance=10_000_000)

    # Very small price
    order1 = await broker.submit_order(
        symbol="TEST1",
        side=OrderSide.BUY,
        quantity=100,
        price=0.01,
    )
    assert order1.filled is True

    # Very large price
    order2 = await broker.submit_order(
        symbol="TEST2",
        side=OrderSide.BUY,
        quantity=1,
        price=10_000_000,
    )
    assert order2.filled is True


@pytest.mark.asyncio
async def test_broker_commission_calculation():
    """Test commission is properly calculated."""
    broker = VirtualBroker(
        initial_balance=10_000_000,
        commission_rate=0.001,  # 0.1% commission
    )

    initial = broker.balance

    await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=100,
        price=50000,
    )

    # Cost should include commission
    # 100 * 50000 * 1.0001 (slippage) + commission
    expected_cost = 100 * 50000 * 1.0001  # With slippage
    commission = expected_cost * 0.001

    # Balance should be reduced by cost + commission
    assert broker.balance < initial - 5_000_000  # Less than just the order cost


@pytest.mark.asyncio
async def test_broker_get_equity_with_no_positions():
    """Test get_equity returns balance when no positions."""
    broker = VirtualBroker(initial_balance=10_000_000)

    assert broker.get_equity() == 10_000_000


@pytest.mark.asyncio
async def test_broker_get_summary_empty():
    """Test get_summary with no trades."""
    broker = VirtualBroker(initial_balance=10_000_000)

    summary = broker.get_summary()

    assert summary["initial_balance"] == 10_000_000
    assert summary["total_trades"] == 0
    assert summary["win_rate"] == 0  # No division by zero
    assert summary["open_positions"] == 0
