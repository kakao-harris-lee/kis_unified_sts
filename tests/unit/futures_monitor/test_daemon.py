"""F-5 FuturesMonitorDaemon — entry/exit pairing, multiplier PnL, hash writes."""

from __future__ import annotations

import asyncio
import json
import logging
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


class _OneMessageRedis:
    def __init__(
        self,
        *,
        stream: bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> None:
        self.stream = stream
        self.msg_id = msg_id
        self.fields = fields
        self.acks: list[tuple[str, str, bytes]] = []
        self.on_ack = lambda: None
        self.fail_ack = False
        self._returned = False

    async def xreadgroup(self, **_kwargs):
        if self._returned:
            return []
        self._returned = True
        return [(self.stream, [(self.msg_id, self.fields)])]

    async def xack(self, stream: str, group: str, msg_id: bytes) -> None:
        self.acks.append((stream, group, msg_id))
        if self.fail_ack:
            raise ConnectionError("xack down")
        self.on_ack()


class _FailingReadRedis:
    def __init__(self, *, success_on_call: int | None = None) -> None:
        self.calls = 0
        self.success_on_call = success_on_call

    async def xreadgroup(self, **_kwargs):
        self.calls += 1
        if self.success_on_call is not None and self.calls == self.success_on_call:
            return []
        raise ConnectionError("redis down")


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


@pytest.mark.asyncio
async def test_consume_loop_logs_audit_context_before_poison_pill_ack(caplog):
    fields = {
        b"signal_id": b"sig-futures-1",
        b"symbol": b"A05603",
        b"setup_type": b"setup_c_event_reaction",
        b"account_number": b"secret",
    }
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-1",
        fields=fields,
    )
    d = _make_daemon(redis)
    redis.on_ack = d._stop.set

    async def fail_handler(_fields):
        raise RuntimeError("bad futures signal")

    d.handle_signal = fail_handler
    caplog.set_level(logging.ERROR, logger="services.futures_monitor.daemon")

    await d._consume_loop()

    assert redis.acks == [
        ("signal.final.futures.shadow", "futures_monitor", b"1700000000000-1")
    ]
    messages = [record.getMessage() for record in caplog.records]
    drop_log = next(
        message
        for message in messages
        if "event=stream_message_dropped" in message
    )
    assert "stream=signal.final.futures.shadow" in drop_log
    assert "consumer_group=futures_monitor" in drop_log
    assert "worker_id=w1" in drop_log
    assert "msg_id=1700000000000-1" in drop_log
    assert "ack=true" in drop_log
    assert "reason=handler_exception" in drop_log
    assert "signal_id=sig-futures-1" in drop_log
    assert "symbol=A05603" in drop_log
    assert "setup_type=setup_c_event_reaction" in drop_log
    assert "account_number=secret" not in drop_log


@pytest.mark.asyncio
async def test_consume_loop_logs_ack_failed_when_poison_pill_xack_fails(caplog):
    fields = {
        b"signal_id": b"sig-futures-ack",
        b"symbol": b"A05603",
        b"setup_type": b"setup_c_event_reaction",
    }
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-2",
        fields=fields,
    )
    redis.fail_ack = True
    d = _make_daemon(redis)

    async def fail_handler(_fields):
        raise RuntimeError("bad futures signal")

    d.handle_signal = fail_handler
    caplog.set_level(logging.ERROR, logger="services.futures_monitor.daemon")

    with pytest.raises(ConnectionError):
        await d._consume_loop()

    messages = [record.getMessage() for record in caplog.records]
    assert not any("event=stream_message_dropped" in message for message in messages)
    ack_log = next(
        message
        for message in messages
        if "event=stream_message_ack_failed" in message
    )
    assert "stream=signal.final.futures.shadow" in ack_log
    assert "consumer_group=futures_monitor" in ack_log
    assert "worker_id=w1" in ack_log
    assert "msg_id=1700000000000-2" in ack_log
    assert "reason=handler_exception" in ack_log
    assert "signal_id=sig-futures-ack" in ack_log
    assert "symbol=A05603" in ack_log
    assert "setup_type=setup_c_event_reaction" in ack_log


@pytest.mark.asyncio
async def test_consume_loop_rate_limits_repeated_read_errors(monkeypatch, caplog):
    redis = _FailingReadRedis()
    d = _make_daemon(redis)
    caplog.set_level(logging.ERROR, logger="services.futures_monitor.daemon")
    real_sleep = asyncio.sleep

    async def fast_sleep(_seconds=0):
        await real_sleep(0)

    monkeypatch.setattr("services.futures_monitor.daemon.asyncio.sleep", fast_sleep)

    async def stop_after_errors():
        while redis.calls < 3:
            await asyncio.sleep(0)
        await d.stop()

    await asyncio.gather(d._consume_loop(), stop_after_errors())

    messages = [
        record.getMessage()
        for record in caplog.records
        if "event=monitor_stream_read_error" in record.getMessage()
    ]
    assert messages == [
        'event=monitor_stream_read_error streams="order.fill.futures.shadow,signal.final.futures.shadow" consumer_group=futures_monitor worker_id=w1 sleep_seconds=0.5'
    ]


@pytest.mark.asyncio
async def test_consume_loop_read_error_logs_again_after_success(monkeypatch, caplog):
    redis = _FailingReadRedis(success_on_call=2)
    d = _make_daemon(redis)
    caplog.set_level(logging.ERROR, logger="services.futures_monitor.daemon")
    real_sleep = asyncio.sleep

    async def fast_sleep(_seconds=0):
        await real_sleep(0)

    monkeypatch.setattr("services.futures_monitor.daemon.asyncio.sleep", fast_sleep)

    async def stop_after_errors():
        while redis.calls < 3:
            await asyncio.sleep(0)
        await d.stop()

    await asyncio.gather(d._consume_loop(), stop_after_errors())

    messages = [
        record.getMessage()
        for record in caplog.records
        if "event=monitor_stream_read_error" in record.getMessage()
    ]
    assert messages == [
        'event=monitor_stream_read_error streams="order.fill.futures.shadow,signal.final.futures.shadow" consumer_group=futures_monitor worker_id=w1 sleep_seconds=0.5',
        'event=monitor_stream_read_error streams="order.fill.futures.shadow,signal.final.futures.shadow" consumer_group=futures_monitor worker_id=w1 sleep_seconds=0.5',
    ]
