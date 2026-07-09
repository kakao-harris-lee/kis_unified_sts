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


# -----------------------------------------------------------------------------
# Telegram interactive-alerts — intent=close branch
# -----------------------------------------------------------------------------

POSITIONS_KEY = "trading:stock:positions"


def _open_position(
    *,
    code: str = "005930",
    quantity: int = 10,
    entry_price: float = 71000.0,
    signal_id: str = "sig-open-1",
    strategy: str = "vr_composite",
) -> str:
    return json.dumps(
        {
            "code": code,
            "name": "n",
            "entry_price": entry_price,
            "quantity": quantity,
            "opened_at_ms": 1000,
            "state": "SURVIVAL",
            "signal_id": signal_id,
            "strategy": strategy,
        }
    )


def _close_fields(code: str = "005930") -> dict[str, str]:
    return {"intent": "close", "code": code, "signal_id": "close-req-1"}


@pytest.mark.asyncio
async def test_close_sells_held_quantity_and_hdels_position() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset(POSITIONS_KEY, "005930", _open_position(quantity=10))

    ack = await daemon.handle_message(b"1-0", _encode(_close_fields()))

    assert ack is True
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    _id, f = fills[0]
    assert f[b"symbol"] == b"005930"
    assert f[b"side"] == b"SELL"
    assert f[b"trade_role"] == b"exit"
    assert int(f[b"quantity"]) == 10
    assert f[b"strategy"] == b"vr_composite"
    assert await redis.hget(POSITIONS_KEY, "005930") is None
    assert daemon.close_count == 1


@pytest.mark.asyncio
async def test_close_reads_quantity_from_hash_not_message() -> None:
    """Quantity must come from the positions hash, never the inbound message."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset(POSITIONS_KEY, "005930", _open_position(quantity=7))
    fields = _close_fields()
    fields["quantity"] = "999"  # attacker/bug-controlled field must be ignored

    await daemon.handle_message(b"1-0", _encode(fields))

    fills = await redis.xrange("order.fill.stock.shadow")
    assert int(fills[0][1][b"quantity"]) == 7


@pytest.mark.asyncio
async def test_close_no_open_position_is_noop_consumed() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)

    ack = await daemon.handle_message(b"1-0", _encode(_close_fields()))

    assert ack is True  # final state: nothing to sell, consumed
    assert await redis.xrange("order.fill.stock.shadow") == []
    assert daemon.close_count == 0


@pytest.mark.asyncio
async def test_close_missing_code_is_poison_pill() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)

    ack = await daemon.handle_message(b"1-0", _encode({"intent": "close"}))

    assert ack is True
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_close_broker_raises_leaves_position_and_retries() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset(POSITIONS_KEY, "005930", _open_position(quantity=10))

    class _RaisingBroker:
        async def submit_order(self, **kwargs: Any) -> VirtualOrder:  # noqa: ARG002
            raise RuntimeError("broker down")

    daemon.broker = _RaisingBroker()  # type: ignore[assignment]

    ack = await daemon.handle_message(b"1-0", _encode(_close_fields()))

    assert ack is False  # NO XACK — retry
    assert await redis.hget(POSITIONS_KEY, "005930") is not None  # position kept


@pytest.mark.asyncio
async def test_close_unfilled_sell_keeps_position_open() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    daemon.broker = _UnfilledBroker()  # type: ignore[assignment]
    await redis.hset(POSITIONS_KEY, "005930", _open_position(quantity=10))

    ack = await daemon.handle_message(b"1-0", _encode(_close_fields()))

    assert ack is True  # final state, consumed — retried close would resubmit
    assert await redis.hget(POSITIONS_KEY, "005930") is not None
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_close_fill_log_failure_leaves_position_for_retry() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    daemon.fill_logger = _RaisingFillLogger(
        redis=redis,
        stream="order.fill.stock.shadow",
        maxlen=1000,
        asset_class="stock",
    )
    await redis.hset(POSITIONS_KEY, "005930", _open_position(quantity=10))

    ack = await daemon.handle_message(b"1-0", _encode(_close_fields()))

    assert ack is False  # NO XACK — retry
    # Position must NOT be removed when the fill could not be logged.
    assert await redis.hget(POSITIONS_KEY, "005930") is not None
