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


@pytest.mark.asyncio
async def test_orchestrator_passes_price_source_time_to_broker(monkeypatch):
    """_place_entry_order passes price_source_time to broker.submit_order."""
    from unittest.mock import AsyncMock, MagicMock

    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    cfg = TradingConfig(
        asset_class="stock",
        strategy_name="momentum_breakout",
        initial_capital=100_000_000.0,
        order_amount_per_trade=1_000_000.0,
        paper_trading=True,
    )
    orch = TradingOrchestrator(cfg)

    # Inject a mock broker (so we don't rely on real VirtualBroker init side-effects)
    broker = MagicMock()
    fake_order = MagicMock()
    fake_order.filled = True
    fake_order.fill_price = 70000.0
    fake_order.venue = "KRX"
    broker.submit_order = AsyncMock(return_value=fake_order)
    orch._paper_broker = broker

    source_time = datetime(2026, 4, 15, 10, 0, 0, tzinfo=timezone.utc)

    await orch._place_entry_order(
        code="005930",
        is_short=False,
        quantity=10,
        order_type="market",
        limit_price=None,
        market_price=70000.0,
        price_source_time=source_time,
    )

    broker.submit_order.assert_awaited_once()
    kwargs = broker.submit_order.await_args.kwargs
    assert kwargs["price_source_time"] == source_time


@pytest.mark.asyncio
async def test_price_deviation_rejected_when_above_threshold(broker):
    """Reference median 대비 10% 초과 편차 시 체결 거부."""
    now = datetime.now(timezone.utc)
    # Seed history with prices near 70000
    broker.record_price_observation("005930", 70000.0, now - timedelta(seconds=30))
    broker.record_price_observation("005930", 70100.0, now - timedelta(seconds=20))
    broker.record_price_observation("005930", 69900.0, now - timedelta(seconds=10))

    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=50000.0,  # ~28.6% below median 70000
        price_source_time=now,
    )
    assert order.filled is False
    assert order.rejection_reason == "price_deviation"


@pytest.mark.asyncio
async def test_price_deviation_accepted_without_history(broker):
    """Reference history가 없으면 guard 적용 불가 → 통과."""
    now = datetime.now(timezone.utc)
    order = await broker.submit_order(
        symbol="NEWCODE",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=50000.0,
        price_source_time=now,
    )
    assert order.filled is True


@pytest.mark.asyncio
async def test_price_deviation_ignores_stale_observations(broker):
    """Lookback window 바깥 관측은 무시."""
    now = datetime.now(timezone.utc)
    # Only stale observations (older than reference_price_lookback_minutes=5)
    broker.record_price_observation("005930", 70000.0, now - timedelta(minutes=10))
    broker.record_price_observation("005930", 70000.0, now - timedelta(minutes=7))

    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=50000.0,  # would deviate if history was used
        price_source_time=now,
    )
    # No fresh reference → guard allows
    assert order.filled is True
