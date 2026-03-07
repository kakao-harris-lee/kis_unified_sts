"""Test VirtualBroker slippage model integration."""
import pytest


@pytest.mark.asyncio
async def test_market_order_with_slippage_model():
    """Test market order uses slippage model when available."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    # Create slippage model with known configuration
    config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=1.5,
        depth_impact_factor=0.8,
        min_slippage_bps=0.5,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(config)

    # Create broker with slippage model
    broker = VirtualBroker(
        initial_balance=10000000,
        slippage_model=slippage_model,
    )

    # Execute BUY order
    market_price = 330.50
    order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
    )

    assert order.filled is True
    assert order.fill_price is not None
    # BUY orders should pay slippage (fill_price > market_price)
    assert order.fill_price > market_price

    # Calculate expected slippage
    slippage_bps = slippage_model.calculate_slippage(
        order_size=1.0,
        current_spread=0.05,  # Default spread
        available_depth=10.0,  # Default depth
        timestamp=order.timestamp,
    )
    slippage_rate = slippage_bps / 10000.0
    expected_fill_price = market_price * (1 + slippage_rate)

    assert order.fill_price == pytest.approx(expected_fill_price, rel=1e-5)


@pytest.mark.asyncio
async def test_market_order_sell_with_slippage_model():
    """Test SELL market order uses slippage model."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=1.5,
        depth_impact_factor=0.8,
        min_slippage_bps=0.5,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(config)

    broker = VirtualBroker(
        initial_balance=10000000,
        slippage_model=slippage_model,
    )

    # First, create a position to sell
    market_price = 330.50
    await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=2,
        price=market_price,
    )

    # Now SELL with slippage model
    sell_price = 331.00
    sell_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.SELL,
        quantity=1,
        price=sell_price,
    )

    assert sell_order.filled is True
    assert sell_order.fill_price is not None
    # SELL orders should receive less (fill_price < market_price)
    assert sell_order.fill_price < sell_price

    # Calculate expected slippage
    slippage_bps = slippage_model.calculate_slippage(
        order_size=1.0,
        current_spread=0.05,
        available_depth=10.0,
        timestamp=sell_order.timestamp,
    )
    slippage_rate = slippage_bps / 10000.0
    expected_fill_price = sell_price * (1 - slippage_rate)

    assert sell_order.fill_price == pytest.approx(expected_fill_price, rel=1e-5)


@pytest.mark.asyncio
async def test_market_order_without_slippage_model():
    """Test market order falls back to slippage_rate when model is disabled."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    # Create disabled slippage model
    config = SlippageModelConfig(enabled=False)
    slippage_model = SlippageModel(config)

    broker = VirtualBroker(
        initial_balance=10000000,
        slippage_rate=0.0001,  # 0.01%
        slippage_model=slippage_model,
    )

    market_price = 330.50
    order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
    )

    assert order.filled is True
    # Should use simple slippage_rate when model is disabled
    expected_fill_price = market_price * (1 + 0.0001)
    assert order.fill_price == pytest.approx(expected_fill_price, rel=1e-5)


@pytest.mark.asyncio
async def test_market_order_no_slippage_model():
    """Test market order works when no slippage model is provided."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide

    broker = VirtualBroker(
        initial_balance=10000000,
        slippage_rate=0.0002,  # 0.02%
    )

    market_price = 330.50
    order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
    )

    assert order.filled is True
    # Should use simple slippage_rate
    expected_fill_price = market_price * (1 + 0.0002)
    assert order.fill_price == pytest.approx(expected_fill_price, rel=1e-5)
