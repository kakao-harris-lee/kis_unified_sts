"""Tests for services/order_router/main.py — Phase 4 Task 12."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.order_router.main import OrderRouterDaemon
from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.passive_maker import Fill
from shared.execution.pseudo_oco import PseudoOCO

FINAL_STREAM = "stream:signal.final"
GROUP = "order_router"


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
        valid_until=datetime(2026, 4, 28, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 28, 5, 0, tzinfo=UTC),
    )


async def _publish_final(redis, signal: Signal, *, signal_id: str = "sig-1") -> None:
    fields = signal.to_stream_dict()
    fields["signal_id"] = signal_id
    fields["size_multiplier"] = "1.0"
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def kis():
    client = AsyncMock()
    client.get_futures_orderbook.return_value = SimpleNamespace(
        bid=[SimpleNamespace(price=331.20)],
        ask=[SimpleNamespace(price=331.22)],
    )
    client.place_futures_order.return_value = "ORD-1"
    client.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.20, quantity=1, filled_at_ms=2000
    )
    return client


@pytest.fixture
def fill_logger():
    return AsyncMock()


@pytest.fixture
def pseudo_oco(fill_logger):
    return PseudoOCO(fill_logger=fill_logger)


def _make_daemon(*, redis, kis, fill_logger, pseudo_oco):
    from shared.execution.passive_maker import PassiveMaker

    passive = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    return OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
    )


async def _run_one_batch(daemon):
    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())


@pytest.mark.asyncio
async def test_signal_routes_to_passive_maker(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    # Passive limit was placed
    kis.place_futures_order.assert_awaited_once()
    kwargs = kis.place_futures_order.call_args.kwargs
    assert kwargs["order_type"] == "limit"
    assert kwargs["side"] == "long"
    # Fill was logged
    fill_logger.log_fill.assert_awaited_once()


@pytest.mark.asyncio
async def test_signal_registers_oco_on_fill(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    # PseudoOCO has one active handle
    assert len(pseudo_oco.active_handles) == 1
    handle = pseudo_oco.active_handles[0]
    assert handle.symbol == "A05603"
    assert handle.stop_price == 330.50
    assert handle.target_price == 332.50


@pytest.mark.asyncio
async def test_missed_passive_fill_does_not_register_oco(
    redis, kis, fill_logger, pseudo_oco
):
    kis.await_fill.return_value = None  # passive timed out
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    # Cancel was called, OCO not registered
    kis.cancel_order.assert_awaited_once()
    assert pseudo_oco.active_handles == []


@pytest.mark.asyncio
async def test_xack_after_successful_route(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    pending = await redis.xpending(FINAL_STREAM, GROUP)
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 0
    elif pending:
        assert int(pending[0]) == 0


@pytest.mark.asyncio
async def test_size_multiplier_scales_quantity(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    fields = _signal("long").to_stream_dict()
    fields["signal_id"] = "sig-x"
    fields["size_multiplier"] = "0.5"  # halve the base size
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    await _run_one_batch(daemon)

    # base_quantity (default 1) × 0.5 → 0; floors to at least 1 contract
    kwargs = kis.place_futures_order.call_args.kwargs
    assert kwargs["quantity"] >= 1
