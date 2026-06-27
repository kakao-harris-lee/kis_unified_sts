"""Test paper trading models."""
from datetime import datetime

import pytest


def test_virtual_order_creation():
    """Test VirtualOrder model."""
    from shared.paper.models import OrderSide, OrderType, VirtualOrder

    order = VirtualOrder(
        order_id="ORD-001",
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        price=None,
        timestamp=datetime.now(),
    )

    assert order.symbol == "005930"
    assert order.side == OrderSide.BUY
    assert order.is_market_order


def test_trade_record_pnl():
    """Test TradeRecord P&L calculation."""
    from shared.paper.models import OrderSide, TradeRecord

    record = TradeRecord(
        trade_id="TRD-001",
        symbol="005930",
        side=OrderSide.BUY,
        entry_price=58000,
        exit_price=59000,
        quantity=10,
        entry_time=datetime.now(),
        exit_time=datetime.now(),
    )

    assert record.pnl == 10000  # (59000 - 58000) * 10
    assert record.pnl_pct == pytest.approx(1.72, rel=0.01)
