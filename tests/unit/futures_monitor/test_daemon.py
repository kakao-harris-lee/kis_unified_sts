"""F-5 FuturesMonitorDaemon — entry/exit pairing, multiplier PnL, hash writes."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest

from services.futures_monitor.daemon import FuturesMonitorDaemon

MULT = 50_000.0
POS_KEY = "futures:monitor:positions"


class _FakeFeed:
    def __init__(self, close: float = 331.20) -> None:
        self._close = close

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_current_price(self, _symbol: str) -> dict:
        return {"close": self._close}

    def get_staleness_seconds(self) -> float | None:
        return 0.0


def _fill(side: str, role: str, price: float, qty: int = 1) -> dict[bytes, bytes]:
    return {
        b"signal_id": b"s1",
        b"order_id": b"O1",
        b"symbol": b"A05603",
        b"side": side.encode(),
        b"filled_price": str(price).encode(),
        b"quantity": str(qty).encode(),
        b"trade_role": role.encode(),
        b"filled_at_ms": b"1700000000000",
    }


def _make_daemon(redis: Any) -> FuturesMonitorDaemon:
    return FuturesMonitorDaemon(
        redis=redis,
        feed=_FakeFeed(),
        publisher=MagicMock(),
        alert_sink=None,
        positions_key=POS_KEY,
        fill_stream="order.fill.futures.shadow",
        signal_stream="signal.final.futures.shadow",
        consumer_group="futures_monitor",
        worker_id="w1",
        multiplier=MULT,
        status_interval=0.01,
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.mark.asyncio
async def test_entry_opens_position_and_writes_hash(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("long", "entry", 331.20))
    assert "A05603" in d._open
    assert d._open["A05603"]["side"] == "long"
    assert await redis.hexists(POS_KEY, "A05603")
    d.publisher.publish_raw_position.assert_called_once()


@pytest.mark.asyncio
async def test_long_take_profit_pnl_and_hdel(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("long", "entry", 331.20))
    await d.handle_fill(_fill("short", "take_profit", 333.00))
    assert "A05603" not in d._open
    assert not await redis.hexists(POS_KEY, "A05603")
    trade = d.publisher.publish_raw_trade.call_args.args[0]
    assert trade["pnl"] == pytest.approx(90_000.0)  # (333.00-331.20)*1*50000
    assert trade["exit_reason"] == "take_profit"
    assert trade["side"] == "long"


@pytest.mark.asyncio
async def test_short_stop_loss_pnl_sign(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("short", "entry", 331.20))
    await d.handle_fill(_fill("long", "stop_loss", 332.40))
    trade = d.publisher.publish_raw_trade.call_args.args[0]
    assert trade["pnl"] == pytest.approx(-60_000.0)  # (332.40-331.20)*(-1)*50000
    assert trade["side"] == "short"


@pytest.mark.asyncio
async def test_orphan_exit_removes_position(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("long", "stop_loss", 330.0))  # no open entry
    d.publisher.remove_position.assert_called_once_with("A05603")
    d.publisher.publish_raw_trade.assert_not_called()


@pytest.mark.asyncio
async def test_recover_from_hash(redis):
    await redis.hset(
        POS_KEY,
        "A05603",
        json.dumps(
            {
                "symbol": "A05603",
                "side": "short",
                "entry_price": 331.20,
                "quantity": 1,
                "opened_at_ms": 1700000000000,
                "setup_type": "A",
                "signal_id": "s1",
                "high_water": 332.0,
                "low_water": 330.0,
            }
        ),
    )
    d = _make_daemon(redis)
    await d.recover_open_positions()
    assert d._open["A05603"]["side"] == "short"
    assert d._open["A05603"]["entry_price"] == 331.20


@pytest.mark.asyncio
async def test_mtm_side_aware_unrealized(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("short", "entry", 331.20))
    d.feed._close = 330.20  # short profits when price falls
    await d.publish_status_and_mtm()
    pos = d.publisher.publish_raw_position.call_args.args[1]
    # short unrealized = (330.20-331.20)*(-1)*1*50000 = +50000
    assert pos["unrealized_pnl"] == pytest.approx(50_000.0)


@pytest.mark.asyncio
async def test_signal_published(redis):
    d = _make_daemon(redis)
    await d.handle_signal(
        {
            b"signal_id": b"s1",
            b"symbol": b"A05603",
            b"setup_type": b"A_gap_reversion",
            b"direction": b"long",
            b"entry_price": b"331.20",
            b"confidence": b"0.85",
            b"generated_at_ms": b"1700000000000",
        }
    )
    d.publisher.publish_raw_signal.assert_called_once()
