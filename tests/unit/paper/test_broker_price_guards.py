"""VirtualBroker price guard — freshness + deviation 회귀 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.paper.broker import VirtualBroker
from shared.paper.config import PaperTradingConfig
from shared.paper.models import OrderSide, OrderType


@pytest.fixture
def broker():
    config = PaperTradingConfig(
        initial_balance=100_000_000.0,
        commission_rate=0.0015,
        slippage_rate=0.001,
        max_price_staleness_seconds=30.0,
        max_price_deviation_pct=0.10,
        reference_price_lookback_minutes=5,
    )
    return VirtualBroker(config=config)


@pytest.mark.asyncio
async def test_fresh_price_accepted(broker):
    """price_source_time이 현재 시각 기준 30초 이내면 체결 성공."""
    now = datetime.now(timezone.utc)
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=70000.0,
        price_source_time=now - timedelta(seconds=5),
    )
    assert order.filled is True
    assert order.fill_price == pytest.approx(70000.0 * 1.001, rel=1e-6)


@pytest.mark.asyncio
async def test_stale_price_rejected(broker):
    """price_source_time이 30초를 초과하면 체결 거부 (reason='stale_price')."""
    now = datetime.now(timezone.utc)
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=70000.0,
        price_source_time=now - timedelta(seconds=45),
    )
    assert order.filled is False
    assert order.rejection_reason == "stale_price"


@pytest.mark.asyncio
async def test_missing_source_time_rejected_in_strict_mode(broker):
    """price_source_time이 None이면 체결 거부(strict 기본값)."""
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=70000.0,
        price_source_time=None,
    )
    assert order.filled is False
    assert order.rejection_reason == "missing_price_source_time"
