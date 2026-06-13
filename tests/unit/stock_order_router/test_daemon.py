"""StockOrderRouterDaemon.handle_message: final -> paper fill -> fill stream + position record."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import fakeredis.aioredis
import pytest

from services.stock_order_router.main import StockOrderRouterDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.paper.models import OrderSide, OrderType, VirtualOrder


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _final(
    code: str = "005930", size_multiplier: str = "1.0", qty: str = "10"
) -> dict[str, str]:
    return {
        "signal_id": "sig-1",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": qty,
        "confidence": "0.62",
        "generated_at_ms": "1000",
        "metadata_json": "{}",
        "size_multiplier": size_multiplier,
        "filtered_at_ms": "2000",
    }


def _build_daemon(redis: fakeredis.aioredis.FakeRedis) -> StockOrderRouterDaemon:
    fill_logger = FillLogger(
        redis=redis,
        stream="order.fill.stock.shadow",
        maxlen=1000,
        asset_class="stock",
    )
    return StockOrderRouterDaemon(
        redis=redis,
        broker=VirtualBroker(slippage_rate=0.001),
        fill_logger=fill_logger,
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_order_router",
        worker_id="test-worker",
        positions_key="trading:stock:positions",
        xread_block_ms=100,
        batch_size=10,
    )


@pytest.mark.asyncio
async def test_fill_published_and_position_recorded() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_final()))
    assert ack is True

    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    _id, f = fills[0]
    assert f[b"symbol"] == b"005930"
    assert f[b"side"] == b"BUY"
    assert f[b"venue"] == b"KRX"
    assert f[b"trade_role"] == b"entry"
    assert int(f[b"quantity"]) == 10
    # Strategy attribution rides the fill stream too (for ledger fill payload).
    assert f[b"strategy"] == b"vr_composite"

    raw = await redis.hget("trading:stock:positions", "005930")
    assert raw is not None
    pos = json.loads(raw)
    assert pos["quantity"] == 10
    assert pos["entry_price"] > 0
    assert pos["state"] == "SURVIVAL"
    # Strategy + name are persisted on the position record so restart recovery
    # and the closed-trade ledger row stay attributed (not just live fills).
    assert pos["strategy"] == "vr_composite"
    assert pos["name"] == "n"


@pytest.mark.asyncio
async def test_size_multiplier_scales_quantity_floored_at_one() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await daemon.handle_message(
        b"1-0", _encode(_final(size_multiplier="0.5", qty="10"))
    )
    fills = await redis.xrange("order.fill.stock.shadow")
    assert int(fills[0][1][b"quantity"]) == 5


@pytest.mark.asyncio
async def test_unparseable_is_poison_pill_drop() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", {b"price": b"NaNaN", b"code": b"x"})
    assert ack is True
    assert await redis.xrange("order.fill.stock.shadow") == []


class _UnfilledBroker:
    """Broker whose order is rejected (``filled=False``)."""

    async def submit_order(self, **kwargs: Any) -> VirtualOrder:
        return VirtualOrder(
            order_id="VO-REJECT",
            symbol=kwargs["symbol"],
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=kwargs["quantity"],
            price=kwargs["price"],
            timestamp=datetime.now(UTC),
            filled=False,
            fill_price=None,
            rejection_reason="insufficient_balance",
        )


class _RaisingFillLogger(FillLogger):
    """FillLogger whose ``log_fill`` raises (simulates a ledger/stream fault)."""

    async def log_fill(self, **kwargs: Any) -> None:  # noqa: ARG002
        raise RuntimeError("fill stream down")


@pytest.mark.asyncio
async def test_unfilled_order_acks_without_fill_or_position() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    daemon.broker = _UnfilledBroker()  # type: ignore[assignment]

    ack = await daemon.handle_message(b"1-0", _encode(_final()))

    assert ack is True  # final state — consumed, not retried
    assert await redis.xrange("order.fill.stock.shadow") == []
    assert await redis.hget("trading:stock:positions", "005930") is None


@pytest.mark.asyncio
async def test_fill_logging_failure_leaves_pending_and_no_position() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    daemon.fill_logger = _RaisingFillLogger(
        redis=redis,
        stream="order.fill.stock.shadow",
        maxlen=1000,
        asset_class="stock",
    )

    ack = await daemon.handle_message(b"1-0", _encode(_final()))

    assert ack is False  # NO XACK — retry
    # Position must NOT be recorded when the fill could not be logged.
    assert await redis.hget("trading:stock:positions", "005930") is None


@pytest.mark.asyncio
async def test_short_direction_is_dropped_no_order() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    fields = _final()
    fields["direction"] = "short"

    ack = await daemon.handle_message(b"1-0", _encode(fields))

    assert ack is True  # consumed (stock is long-only), no order placed
    assert await redis.xrange("order.fill.stock.shadow") == []
    assert await redis.hget("trading:stock:positions", "005930") is None
