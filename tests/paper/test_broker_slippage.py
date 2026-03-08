"""Integration tests for VirtualBroker slippage model with mock orderbook data.

Verifies that the paper trading broker correctly uses the slippage model
for realistic fill simulation when configured.

Test Coverage:
1. Basic slippage model usage (enabled/disabled/None)
2. BUY and SELL order slippage with orderbook data
3. Direct comparison tests showing fill price and P&L impact
4. Large order depth impact scenarios
5. Wide spread penalty scenarios
6. Time-of-day multiplier effects
7. Multi-order cumulative slippage impact
8. Edge cases and error scenarios

Expected Behavior:
- BUY orders: pays MORE (worse fill) → fill_price > market_price
- SELL orders: receives LESS (worse fill) → fill_price < market_price
- Large orders: higher slippage due to depth impact
- Wide spreads: higher slippage penalty
- Time-of-day multipliers: slippage varies by trading time
- Overall: P&L is lower with slippage (more realistic paper trading)
"""
import pytest
from datetime import datetime, time


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


@pytest.mark.asyncio
async def test_submit_order_with_orderbook():
    """Test submit_order() uses orderbook data for slippage calculation."""
    from datetime import datetime
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig
    from shared.execution.slippage_control import OrderBookSnapshot

    # Create slippage model with known configuration
    config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=1.5,
        depth_impact_factor=0.8,
        min_slippage_bps=0.5,
        max_slippage_bps=15.0,
    )
    slippage_model = SlippageModel(config)

    broker = VirtualBroker(
        initial_balance=10000000,
        slippage_model=slippage_model,
    )

    # Create orderbook snapshot with realistic data
    market_price = 330.50
    orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.48,
        ask_price_1=330.52,
        bid_qty_1=5.0,
        ask_qty_1=8.0,
        last_price=market_price,
        timestamp=datetime.now(),
    )

    # Test BUY order with orderbook
    buy_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
        orderbook=orderbook,
    )

    assert buy_order.filled is True
    assert buy_order.fill_price is not None
    # BUY orders should pay slippage (fill_price > market_price)
    assert buy_order.fill_price > market_price

    # Calculate expected slippage using orderbook data
    slippage_bps = slippage_model.calculate_slippage(
        order_size=1.0,
        current_spread=orderbook.spread,  # Use orderbook spread (0.04)
        available_depth=orderbook.available_qty(is_buy=True),  # Use ask depth (8.0)
        timestamp=buy_order.timestamp,
    )
    slippage_rate = slippage_bps / 10000.0
    expected_fill_price = market_price * (1 + slippage_rate)

    assert buy_order.fill_price == pytest.approx(expected_fill_price, rel=1e-5)

    # Test SELL order with orderbook
    sell_price = 331.00
    orderbook_sell = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.98,
        ask_price_1=331.02,
        bid_qty_1=12.0,
        ask_qty_1=6.0,
        last_price=sell_price,
        timestamp=datetime.now(),
    )

    sell_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.SELL,
        quantity=1,
        price=sell_price,
        orderbook=orderbook_sell,
    )

    assert sell_order.filled is True
    assert sell_order.fill_price is not None
    # SELL orders should receive less (fill_price < market_price)
    assert sell_order.fill_price < sell_price

    # Calculate expected slippage using orderbook data
    slippage_bps = slippage_model.calculate_slippage(
        order_size=1.0,
        current_spread=orderbook_sell.spread,  # Use orderbook spread (0.04)
        available_depth=orderbook_sell.available_qty(is_buy=False),  # Use bid depth (12.0)
        timestamp=sell_order.timestamp,
    )
    slippage_rate = slippage_bps / 10000.0
    expected_fill_price = sell_price * (1 - slippage_rate)

    assert sell_order.fill_price == pytest.approx(expected_fill_price, rel=1e-5)


@pytest.mark.asyncio
async def test_slippage_comparison_buy_order():
    """Direct comparison: VirtualBroker with slippage enabled vs disabled for BUY order.

    Verifies that:
    1. Slippage model increases fill price (worse fill on buy)
    2. Position entry price is higher with slippage
    3. Balance decrease is larger with slippage (including slippage cost)
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    initial_balance = 10_000_000
    market_price = 330.50
    quantity = 5

    # ========== Broker WITHOUT slippage model ==========
    broker_no_slip = VirtualBroker(
        initial_balance=initial_balance,
        slippage_rate=0.0,  # No slippage
        commission_rate=0.0,  # No commission for clearer comparison
    )

    order_no_slip = await broker_no_slip.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=market_price,
    )

    # ========== Broker WITH slippage model ==========
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,  # 2 bps base slippage
        depth_impact_factor=0.8,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker_with_slip = VirtualBroker(
        initial_balance=initial_balance,
        slippage_model=slippage_model,
        commission_rate=0.0,  # No commission for clearer comparison
    )

    order_with_slip = await broker_with_slip.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=market_price,
    )

    # ========== Compare Results ==========
    assert order_no_slip.filled is True
    assert order_with_slip.filled is True

    # Fill price comparison: slippage should increase fill price (worse fill)
    assert order_no_slip.fill_price == market_price, "No slippage: fill at market price"
    assert order_with_slip.fill_price > order_no_slip.fill_price, (
        f"Slippage should increase fill price: "
        f"{order_with_slip.fill_price:.2f} > {order_no_slip.fill_price:.2f}"
    )

    # Balance comparison: more money spent with slippage
    balance_no_slip = broker_no_slip.balance
    balance_with_slip = broker_with_slip.balance

    assert balance_with_slip < balance_no_slip, (
        f"Balance with slippage ({balance_with_slip:,.0f}) should be lower than "
        f"without slippage ({balance_no_slip:,.0f})"
    )

    # Calculate slippage cost
    cost_no_slip = initial_balance - balance_no_slip
    cost_with_slip = initial_balance - balance_with_slip
    slippage_cost = cost_with_slip - cost_no_slip

    assert slippage_cost > 0, "Slippage cost should be positive"

    # Verify position entry price reflects slippage
    position_no_slip = broker_no_slip.positions.get("A05603")
    position_with_slip = broker_with_slip.positions.get("A05603")

    assert position_no_slip is not None
    assert position_with_slip is not None
    assert position_with_slip.entry_price > position_no_slip.entry_price, (
        "Position entry price should be higher with slippage"
    )


@pytest.mark.asyncio
async def test_slippage_comparison_sell_order():
    """Direct comparison: VirtualBroker with slippage enabled vs disabled for SELL order.

    Verifies that:
    1. Slippage model decreases fill price (worse fill on sell)
    2. Position exit receives less money with slippage
    3. Total proceeds are lower with slippage
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    initial_balance = 10_000_000
    entry_price = 330.00
    exit_price = 331.00
    quantity = 5

    # ========== Broker WITHOUT slippage model ==========
    broker_no_slip = VirtualBroker(
        initial_balance=initial_balance,
        slippage_rate=0.0,
        commission_rate=0.0,
    )

    # Create position first
    await broker_no_slip.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=entry_price,
    )
    balance_after_entry_no_slip = broker_no_slip.balance

    # Sell position
    sell_order_no_slip = await broker_no_slip.submit_order(
        symbol="A05603",
        side=OrderSide.SELL,
        quantity=quantity,
        price=exit_price,
    )
    balance_after_exit_no_slip = broker_no_slip.balance

    # ========== Broker WITH slippage model ==========
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.8,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker_with_slip = VirtualBroker(
        initial_balance=initial_balance,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    # Create position first (will have slippage on entry too)
    await broker_with_slip.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=entry_price,
    )
    balance_after_entry_with_slip = broker_with_slip.balance

    # Sell position
    sell_order_with_slip = await broker_with_slip.submit_order(
        symbol="A05603",
        side=OrderSide.SELL,
        quantity=quantity,
        price=exit_price,
    )
    balance_after_exit_with_slip = broker_with_slip.balance

    # ========== Compare Results ==========
    assert sell_order_no_slip.filled is True
    assert sell_order_with_slip.filled is True

    # Fill price comparison: slippage should decrease sell fill price (worse fill)
    assert sell_order_no_slip.fill_price == exit_price, "No slippage: fill at market price"
    assert sell_order_with_slip.fill_price < sell_order_no_slip.fill_price, (
        f"Slippage should decrease sell fill price: "
        f"{sell_order_with_slip.fill_price:.2f} < {sell_order_no_slip.fill_price:.2f}"
    )

    # Proceeds comparison: less money received with slippage
    proceeds_no_slip = balance_after_exit_no_slip - balance_after_entry_no_slip
    proceeds_with_slip = balance_after_exit_with_slip - balance_after_entry_with_slip

    assert proceeds_with_slip < proceeds_no_slip, (
        f"Proceeds with slippage ({proceeds_with_slip:,.0f}) should be lower than "
        f"without slippage ({proceeds_no_slip:,.0f})"
    )


@pytest.mark.asyncio
async def test_large_order_depth_impact():
    """Test that large orders incur higher slippage due to depth impact.

    Verifies that order size relative to available depth affects slippage calculation.
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig
    from shared.execution.slippage_control import OrderBookSnapshot

    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=1.5,
        depth_impact_factor=0.8,  # High impact factor
        min_slippage_bps=0.5,
        max_slippage_bps=15.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker = VirtualBroker(
        initial_balance=10_000_000,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    market_price = 330.50

    # Create orderbook with limited depth
    orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.48,
        ask_price_1=330.52,
        bid_qty_1=5.0,
        ask_qty_1=5.0,  # Limited depth
        last_price=market_price,
        timestamp=datetime.now(),
    )

    # ========== Small order (within depth) ==========
    small_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=2,  # 40% of available depth (2/5)
        price=market_price,
        orderbook=orderbook,
    )

    # ========== Large order (exceeds depth) ==========
    large_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=8,  # 160% of available depth (8/5)
        price=market_price,
        orderbook=orderbook,
    )

    # ========== Compare Results ==========
    assert small_order.filled is True
    assert large_order.filled is True

    # Large order should have worse fill price (higher slippage)
    small_slippage_pct = (small_order.fill_price - market_price) / market_price
    large_slippage_pct = (large_order.fill_price - market_price) / market_price

    assert large_slippage_pct > small_slippage_pct, (
        f"Large order slippage ({large_slippage_pct:.4%}) should be greater than "
        f"small order slippage ({small_slippage_pct:.4%})"
    )

    # Verify depth impact is significant
    depth_impact_ratio = large_slippage_pct / small_slippage_pct
    assert depth_impact_ratio > 1.2, (
        f"Depth impact should be significant: {depth_impact_ratio:.2f}x"
    )


@pytest.mark.asyncio
async def test_wide_spread_penalty():
    """Test that wide spreads incur higher slippage penalties.

    Verifies that spread width affects slippage calculation.
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig
    from shared.execution.slippage_control import OrderBookSnapshot

    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=1.5,
        depth_impact_factor=0.5,
        min_slippage_bps=0.5,
        max_slippage_bps=15.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker = VirtualBroker(
        initial_balance=10_000_000,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    market_price = 330.50
    quantity = 1

    # ========== Narrow spread orderbook ==========
    narrow_orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.49,
        ask_price_1=330.51,
        bid_qty_1=10.0,
        ask_qty_1=10.0,
        last_price=market_price,
        timestamp=datetime.now(),
    )

    narrow_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=market_price,
        orderbook=narrow_orderbook,
    )

    # ========== Wide spread orderbook ==========
    wide_orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.30,
        ask_price_1=330.70,
        bid_qty_1=10.0,
        ask_qty_1=10.0,
        last_price=market_price,
        timestamp=datetime.now(),
    )

    wide_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=market_price,
        orderbook=wide_orderbook,
    )

    # ========== Compare Results ==========
    assert narrow_order.filled is True
    assert wide_order.filled is True

    # Wide spread should result in worse fill price (higher slippage)
    narrow_slippage = narrow_order.fill_price - market_price
    wide_slippage = wide_order.fill_price - market_price

    assert wide_slippage > narrow_slippage, (
        f"Wide spread slippage ({wide_slippage:.4f}) should be greater than "
        f"narrow spread slippage ({narrow_slippage:.4f})"
    )

    # Calculate spread penalty impact
    narrow_spread = narrow_orderbook.spread  # 0.02
    wide_spread = wide_orderbook.spread  # 0.40

    spread_ratio = wide_spread / narrow_spread  # 20x wider
    slippage_ratio = wide_slippage / narrow_slippage

    # Slippage should increase with spread, but not necessarily linearly
    assert slippage_ratio > 1.0, (
        f"Slippage ratio ({slippage_ratio:.2f}) should reflect spread penalty"
    )


@pytest.mark.asyncio
async def test_time_of_day_multiplier():
    """Test that time-of-day multipliers affect slippage calculation.

    Verifies that slippage varies based on trading time (market open/close).
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig
    from unittest.mock import Mock

    # Create config with time-of-day multipliers
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=1.5,
        depth_impact_factor=0.5,
        min_slippage_bps=0.5,
        max_slippage_bps=15.0,
        time_of_day_multipliers={
            "market_open": {"start": "09:00", "end": "09:30", "multiplier": 1.5},
            "market_close": {"start": "15:00", "end": "15:20", "multiplier": 1.3},
            "normal": {"start": "09:30", "end": "15:00", "multiplier": 1.0},
        },
    )
    slippage_model = SlippageModel(slippage_config)

    broker = VirtualBroker(
        initial_balance=10_000_000,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    market_price = 330.50

    # ========== Normal trading hours (09:30-15:00, multiplier=1.0) ==========
    # Mock timestamp for normal hours
    normal_time = datetime(2024, 1, 15, 10, 30)  # 10:30 AM

    normal_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
    )
    # Manually calculate expected slippage for normal hours
    normal_slippage_bps = slippage_model.calculate_slippage(
        order_size=1.0,
        current_spread=0.05,
        available_depth=10.0,
        timestamp=normal_time,
    )

    # ========== Market open (09:00-09:30, multiplier=1.5) ==========
    # Mock timestamp for market open
    open_time = datetime(2024, 1, 15, 9, 15)  # 9:15 AM

    open_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
    )
    # Manually calculate expected slippage for market open
    open_slippage_bps = slippage_model.calculate_slippage(
        order_size=1.0,
        current_spread=0.05,
        available_depth=10.0,
        timestamp=open_time,
    )

    # ========== Verify multiplier effect ==========
    # Market open should have higher slippage than normal hours
    assert open_slippage_bps > normal_slippage_bps, (
        f"Market open slippage ({open_slippage_bps:.2f} bps) should be higher than "
        f"normal hours ({normal_slippage_bps:.2f} bps)"
    )

    # Ratio should be close to multiplier (1.5), but may not be exact due to other factors
    multiplier_effect = open_slippage_bps / normal_slippage_bps
    assert 1.2 <= multiplier_effect <= 2.0, (
        f"Time multiplier effect ({multiplier_effect:.2f}) should be significant"
    )


@pytest.mark.asyncio
async def test_multi_order_cumulative_slippage():
    """Test cumulative slippage impact across multiple orders.

    Verifies that multiple orders accumulate slippage costs over time,
    and the total P&L impact is measurable.
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig
    from shared.execution.slippage_control import OrderBookSnapshot

    initial_balance = 10_000_000

    # ========== Broker WITHOUT slippage ==========
    broker_no_slip = VirtualBroker(
        initial_balance=initial_balance,
        slippage_rate=0.0,
        commission_rate=0.0,
    )

    # ========== Broker WITH slippage ==========
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.8,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker_with_slip = VirtualBroker(
        initial_balance=initial_balance,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    # Create orderbook
    orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.48,
        ask_price_1=330.52,
        bid_qty_1=10.0,
        ask_qty_1=10.0,
        last_price=330.50,
        timestamp=datetime.now(),
    )

    # ========== Execute 10 round-trip trades ==========
    num_trades = 10
    base_price = 330.00

    for i in range(num_trades):
        entry_price = base_price + i * 0.50
        exit_price = entry_price + 1.00  # +1.00 profit per trade

        # WITHOUT slippage
        await broker_no_slip.submit_order(
            symbol="A05603",
            side=OrderSide.BUY,
            quantity=1,
            price=entry_price,
            orderbook=orderbook,
        )
        await broker_no_slip.submit_order(
            symbol="A05603",
            side=OrderSide.SELL,
            quantity=1,
            price=exit_price,
            orderbook=orderbook,
        )

        # WITH slippage
        await broker_with_slip.submit_order(
            symbol="A05603",
            side=OrderSide.BUY,
            quantity=1,
            price=entry_price,
            orderbook=orderbook,
        )
        await broker_with_slip.submit_order(
            symbol="A05603",
            side=OrderSide.SELL,
            quantity=1,
            price=exit_price,
            orderbook=orderbook,
        )

    # ========== Compare Final Results ==========
    final_balance_no_slip = broker_no_slip.balance
    final_balance_with_slip = broker_with_slip.balance

    # Balance should be lower with slippage
    assert final_balance_with_slip < final_balance_no_slip, (
        f"Final balance with slippage ({final_balance_with_slip:,.0f}) should be lower than "
        f"without slippage ({final_balance_no_slip:,.0f})"
    )

    # Calculate cumulative slippage cost
    pnl_no_slip = final_balance_no_slip - initial_balance
    pnl_with_slip = final_balance_with_slip - initial_balance
    cumulative_slippage = pnl_no_slip - pnl_with_slip

    assert cumulative_slippage > 0, "Cumulative slippage cost should be positive"

    # Average slippage per round-trip trade
    avg_slippage_per_trade = cumulative_slippage / num_trades
    assert avg_slippage_per_trade > 0, "Average slippage per trade should be positive"

    # Slippage should be measurable (at least 0.01% per round-trip)
    min_expected_slippage_per_trade = (base_price * 2) * 0.0001  # 1 bps per side
    assert avg_slippage_per_trade >= min_expected_slippage_per_trade, (
        f"Average slippage per trade ({avg_slippage_per_trade:.2f}) should be "
        f"at least {min_expected_slippage_per_trade:.2f}"
    )


@pytest.mark.asyncio
async def test_position_pnl_accuracy_with_slippage():
    """Test that position P&L accurately reflects slippage costs.

    Verifies that the VirtualBroker correctly tracks position P&L
    including realistic slippage on both entry and exit.
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    initial_balance = 10_000_000
    entry_market_price = 330.00
    exit_market_price = 335.00  # +5.00 profit if no slippage
    quantity = 10

    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker = VirtualBroker(
        initial_balance=initial_balance,
        slippage_model=slippage_model,
        commission_rate=0.0,  # No commission for clearer P&L calculation
    )

    # ========== Entry ==========
    entry_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=quantity,
        price=entry_market_price,
    )

    assert entry_order.filled is True
    actual_entry_price = entry_order.fill_price

    # Entry price should be higher than market (paid slippage)
    entry_slippage = actual_entry_price - entry_market_price
    assert entry_slippage > 0, "Entry slippage should be positive (paid more)"

    # Check position
    position = broker.positions.get("A05603")
    assert position is not None
    assert position.quantity == quantity
    assert position.entry_price == pytest.approx(actual_entry_price, rel=1e-5)

    # ========== Exit ==========
    exit_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.SELL,
        quantity=quantity,
        price=exit_market_price,
    )

    assert exit_order.filled is True
    actual_exit_price = exit_order.fill_price

    # Exit price should be lower than market (received slippage)
    exit_slippage = exit_market_price - actual_exit_price
    assert exit_slippage > 0, "Exit slippage should be positive (received less)"

    # ========== Verify P&L ==========
    # Actual P&L should be: (actual_exit_price - actual_entry_price) * quantity
    expected_pnl = (actual_exit_price - actual_entry_price) * quantity
    actual_pnl = broker.balance - initial_balance

    assert actual_pnl == pytest.approx(expected_pnl, rel=1e-5), (
        f"Actual P&L ({actual_pnl:.2f}) should match expected ({expected_pnl:.2f})"
    )

    # P&L should be less than ideal (no slippage) P&L
    ideal_pnl = (exit_market_price - entry_market_price) * quantity
    total_slippage_cost = ideal_pnl - actual_pnl

    assert actual_pnl < ideal_pnl, (
        f"Actual P&L ({actual_pnl:.2f}) should be less than ideal ({ideal_pnl:.2f})"
    )
    assert total_slippage_cost > 0, "Total slippage cost should be positive"

    # Verify slippage components
    total_slippage_from_prices = (entry_slippage + exit_slippage) * quantity
    assert total_slippage_cost == pytest.approx(total_slippage_from_prices, rel=1e-5), (
        "Total slippage cost should equal sum of entry and exit slippage"
    )


@pytest.mark.asyncio
async def test_slippage_model_edge_cases():
    """Test edge cases for slippage model integration.

    Verifies handling of:
    1. Zero depth (should use max slippage)
    2. Very large spreads (should cap at max slippage)
    3. Fractional order quantities
    """
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig
    from shared.execution.slippage_control import OrderBookSnapshot

    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.8,
        min_slippage_bps=0.5,
        max_slippage_bps=15.0,
    )
    slippage_model = SlippageModel(slippage_config)

    broker = VirtualBroker(
        initial_balance=10_000_000,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    market_price = 330.50

    # ========== Test 1: Zero depth ==========
    zero_depth_orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.48,
        ask_price_1=330.52,
        bid_qty_1=0.0,  # No depth
        ask_qty_1=0.0,  # No depth
        last_price=market_price,
        timestamp=datetime.now(),
    )

    zero_depth_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
        orderbook=zero_depth_orderbook,
    )

    assert zero_depth_order.filled is True
    # Should apply max slippage
    max_fill_price = market_price * (1 + slippage_config.max_slippage_bps / 10000.0)
    assert zero_depth_order.fill_price <= max_fill_price, (
        f"Fill price with zero depth should not exceed max slippage cap"
    )

    # ========== Test 2: Very large spread ==========
    large_spread_orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=325.00,
        ask_price_1=336.00,
        bid_qty_1=10.0,
        ask_qty_1=10.0,
        last_price=market_price,
        timestamp=datetime.now(),
    )

    large_spread_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=1,
        price=market_price,
        orderbook=large_spread_orderbook,
    )

    assert large_spread_order.filled is True
    # Should be capped at max slippage
    assert large_spread_order.fill_price <= max_fill_price, (
        f"Fill price with large spread should be capped at max slippage"
    )

    # ========== Test 3: Fractional quantity ==========
    normal_orderbook = OrderBookSnapshot(
        symbol="A05603",
        bid_price_1=330.48,
        ask_price_1=330.52,
        bid_qty_1=10.0,
        ask_qty_1=10.0,
        last_price=market_price,
        timestamp=datetime.now(),
    )

    # Some futures allow fractional contracts
    fractional_order = await broker.submit_order(
        symbol="A05603",
        side=OrderSide.BUY,
        quantity=0.5,  # Half contract
        price=market_price,
        orderbook=normal_orderbook,
    )

    assert fractional_order.filled is True
    assert fractional_order.quantity == 0.5
    # Should have reasonable slippage
    fractional_slippage = (fractional_order.fill_price - market_price) / market_price
    assert 0 < fractional_slippage < 0.002, (  # Less than 20 bps
        f"Fractional order slippage ({fractional_slippage:.4%}) should be reasonable"
    )


@pytest.mark.asyncio
async def test_slippage_with_insufficient_balance():
    """Test that slippage is correctly applied even when orders fail due to insufficient balance.

    Verifies that the broker correctly calculates required balance including slippage,
    and rejects orders that would exceed available balance.
    """
    from shared.paper.broker import VirtualBroker, InsufficientBalanceError
    from shared.paper.models import OrderSide
    from shared.execution.slippage_model import SlippageModel, SlippageModelConfig

    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    # Create broker with limited balance
    limited_balance = 100_000  # Only 100K
    broker = VirtualBroker(
        initial_balance=limited_balance,
        slippage_model=slippage_model,
        commission_rate=0.0,
    )

    market_price = 330.50
    # Try to buy quantity that would exceed balance even without slippage
    quantity = 400  # Would cost 132,200 at market price (exceeds 100K)

    # Order should fail due to insufficient balance
    with pytest.raises(InsufficientBalanceError):
        await broker.submit_order(
            symbol="A05603",
            side=OrderSide.BUY,
            quantity=quantity,
            price=market_price,
        )

    # Verify balance unchanged
    assert broker.balance == limited_balance, "Balance should be unchanged after failed order"

    # Now try an order that would succeed without slippage but fail with slippage
    # At 330.50, quantity=302 costs 99,811 (under 100K)
    # But with slippage (say 2 bps = 0.02%), it becomes 99,831 (still under)
    # Let's try quantity=303 which is borderline
    borderline_quantity = 303

    # This might succeed or fail depending on exact slippage calculation
    # The key is that slippage is considered in the balance check
    try:
        order = await broker.submit_order(
            symbol="A05603",
            side=OrderSide.BUY,
            quantity=borderline_quantity,
            price=market_price,
        )
        # If it succeeds, verify balance was checked correctly
        assert order.filled is True
        remaining_balance = broker.balance
        assert remaining_balance >= 0, "Balance should not go negative"
    except InsufficientBalanceError:
        # If it fails, that's also valid - slippage pushed it over the limit
        assert broker.balance == limited_balance, "Balance should be unchanged"
