"""StockOrderRouterDaemon.handle_message: final -> paper fill -> fill stream + position record."""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from services.stock_order_router.main import StockOrderRouterDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker


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

    raw = await redis.hget("trading:stock:positions", "005930")
    assert raw is not None
    pos = json.loads(raw)
    assert pos["quantity"] == 10
    assert pos["entry_price"] > 0
    assert pos["state"] == "SURVIVAL"


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
