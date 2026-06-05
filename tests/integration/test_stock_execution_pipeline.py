"""e2e: candidate.stock.shadow -> M4-R -> final.stock.shadow -> M4-O -> fill + position.

Also asserts OpenPositionFilter blocks re-entry once M4-O has recorded a position.
"""

from __future__ import annotations

from datetime import UTC, datetime

import fakeredis
import fakeredis.aioredis
import pytest

from services.stock_order_router.main import StockOrderRouterDaemon
from services.stock_risk_filter.main import StockRiskFilterDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.config import StockRiskConfig
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _candidate(code: str) -> dict[str, str]:
    # 09:30 KST -> inside 09:00-15:30 stock window.
    gen = str(int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000))
    return {
        "signal_id": f"sig-{code}",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": gen,
        "metadata_json": "{}",
    }


@pytest.mark.asyncio
async def test_candidate_to_fill_and_reentry_blocked() -> None:
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server)
    sync_redis = fakeredis.FakeStrictRedis(server=server)
    positions_key = "trading:stock:positions"

    def _has_open_position(code: str) -> bool:
        return bool(sync_redis.hexists(positions_key, code))

    risk = StockRiskFilterDaemon(
        redis=redis,
        layer=RiskFilterLayer.from_config(
            config=StockRiskConfig(),
            trading_windows=["09:00-15:30"],
            has_open_position_provider=_has_open_position,
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        candidate_stream="signal.candidate.stock.shadow",
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_risk_filter",
        worker_id="risk-w",
        final_maxlen=1000,
        xread_block_ms=100,
        batch_size=10,
    )
    order = StockOrderRouterDaemon(
        redis=redis,
        broker=VirtualBroker(slippage_rate=0.0001),
        fill_logger=FillLogger(
            redis=redis,
            stream="order.fill.stock.shadow",
            maxlen=1000,
            asset_class="stock",
        ),
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_order_router",
        worker_id="order-w",
        positions_key=positions_key,
        xread_block_ms=100,
        batch_size=10,
    )

    # 1st candidate -> passes risk -> final -> fill -> position recorded.
    assert await risk.handle_message(b"c1", _encode(_candidate("005930"))) is True
    final_entries = await redis.xrange("signal.final.stock.shadow")
    assert len(final_entries) == 1
    assert await order.handle_message(final_entries[0][0], final_entries[0][1]) is True

    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    assert await redis.hexists(positions_key, "005930")

    # 2nd candidate, same code -> OpenPositionFilter rejects -> no new final.
    assert await risk.handle_message(b"c2", _encode(_candidate("005930"))) is True
    final_after = await redis.xrange("signal.final.stock.shadow")
    assert len(final_after) == 1  # unchanged — re-entry blocked
