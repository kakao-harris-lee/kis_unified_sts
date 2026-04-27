"""Tests for shared/execution/passive_maker.py — Phase 4 Task 5."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.order_result import OrderState
from shared.execution.passive_maker import Fill, PassiveMaker


def _spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50_000,
        tick_size_points=0.02,
        tick_value_krw=1_000,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


def _signal(direction: str = "long") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 4, 27, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 27, 5, 0, tzinfo=UTC),
    )


def _orderbook(*, bid: float, ask: float) -> SimpleNamespace:
    return SimpleNamespace(
        bid=[SimpleNamespace(price=bid)],
        ask=[SimpleNamespace(price=ask)],
    )


@pytest.fixture
def kis():
    client = AsyncMock()
    client.get_futures_orderbook.return_value = _orderbook(bid=331.20, ask=331.22)
    client.place_futures_order.return_value = "ORD-1"
    return client


@pytest.fixture
def fill_logger():
    return AsyncMock()


@pytest.mark.asyncio
async def test_happy_path_long_fills_at_bid(kis, fill_logger):
    kis.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.20, quantity=1, filled_at_ms=1000
    )

    pm = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    result = await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="sig-1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=30,
    )

    assert result.is_filled
    assert result.state is OrderState.FILLED
    assert result.order_id == "ORD-1"
    assert result.filled_price == 331.20
    assert result.slippage_ticks == pytest.approx(0.0)

    # Order placed with rounded bid for long
    args, kwargs = kis.place_futures_order.call_args
    assert kwargs["symbol"] == "A05603"
    assert kwargs["side"] == "long"
    assert kwargs["price"] == 331.20

    fill_logger.log_fill.assert_awaited_once()


@pytest.mark.asyncio
async def test_happy_path_short_fills_at_ask(kis, fill_logger):
    kis.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.22, quantity=1, filled_at_ms=1000
    )

    pm = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    result = await pm.place_passive_limit_futures(
        signal=_signal("short"),
        signal_id="sig-1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=30,
    )

    assert result.is_filled
    args, kwargs = kis.place_futures_order.call_args
    assert kwargs["price"] == 331.22  # ask
    assert kwargs["side"] == "short"


@pytest.mark.asyncio
async def test_timeout_cancels_and_returns_missed(kis, fill_logger):
    kis.await_fill.return_value = None  # timeout

    pm = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    result = await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="sig-1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=30,
    )

    assert result.is_missed
    assert result.state is OrderState.MISSED
    assert result.reason == "passive_not_filled"
    assert result.order_id == "ORD-1"
    kis.cancel_order.assert_awaited_once_with("ORD-1")
    fill_logger.log_fill.assert_not_awaited()


@pytest.mark.asyncio
async def test_slippage_long_positive_when_filled_above_request(kis, fill_logger):
    # bid 331.20, filled at 331.24 → 2 ticks of slip against long
    kis.get_futures_orderbook.return_value = _orderbook(bid=331.20, ask=331.22)
    kis.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.24, quantity=1, filled_at_ms=1000
    )

    pm = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    result = await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="sig-1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=30,
    )

    assert result.is_filled
    assert result.slippage_ticks == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_limit_price_rounded_to_tick(kis, fill_logger):
    # Off-tick bid → must be rounded
    kis.get_futures_orderbook.return_value = _orderbook(bid=331.211, ask=331.231)
    kis.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.22, quantity=1, filled_at_ms=1000
    )

    pm = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="sig-1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=30,
    )

    kwargs = kis.place_futures_order.call_args.kwargs
    assert kwargs["price"] == 331.22  # rounded


@pytest.mark.asyncio
async def test_log_fill_passes_correct_payload(kis, fill_logger):
    kis.get_futures_orderbook.return_value = _orderbook(bid=331.20, ask=331.22)
    kis.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.22, quantity=1, filled_at_ms=2000
    )

    pm = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="sig-99",
        quantity=2,
        spec=_spec(),
        timeout_seconds=30,
    )

    kwargs = fill_logger.log_fill.call_args.kwargs
    assert kwargs["signal_id"] == "sig-99"
    assert kwargs["order_id"] == "ORD-1"
    assert kwargs["symbol"] == "A05603"
    assert kwargs["side"] == "long"
    assert kwargs["order_type"] == "limit_passive"
    assert kwargs["requested_price"] == 331.20
    assert kwargs["filled_price"] == 331.22
    assert kwargs["tick_size_points"] == 0.02
    assert kwargs["slippage_ticks"] == pytest.approx(1.0)  # 1 tick
    assert kwargs["quantity"] == 2
    assert kwargs["filled_at_ms"] == 2000
    assert kwargs["venue"] == "KRX"
    assert kwargs["trade_role"] == "entry"
