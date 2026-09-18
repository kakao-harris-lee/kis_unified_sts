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


class _MissingGroupRedis:
    """Stub where a group-less stream fails the whole multi-stream XREADGROUP.

    Models the live defect: both monitor streams are read in one call, so
    whichever one expired takes the surviving one down with it until the
    consumer group is recreated on both. ``recover_fails`` models the split
    failure (ACL, or eviction racing the recreate) where the recreate itself
    keeps failing.
    """

    def __init__(
        self,
        *,
        existing_groups: set[str],
        pending: dict[str, list[tuple[bytes, dict[bytes, bytes]]]],
        recover_fails: bool = False,
        missing_error: str | None = None,
    ) -> None:
        self.groups = set(existing_groups)
        self.pending = dict(pending)
        self.recover_fails = recover_fails
        self.missing_error = missing_error
        self.created: list[tuple[str, str]] = []
        self.acks: list[tuple[str, str, bytes]] = []
        self.reads = 0

    async def xreadgroup(self, *, groupname, consumername, streams, **_kwargs):
        self.reads += 1
        missing = [name for name in streams if name not in self.groups]
        if missing:
            raise RuntimeError(
                self.missing_error
                or (
                    f"NOGROUP No such key '{missing[0]}' or consumer group "
                    f"'{groupname}' in XREADGROUP with GROUP option"
                )
            )
        delivered = []
        for name in streams:
            msgs = self.pending.pop(name, [])
            if msgs:
                delivered.append((name.encode(), msgs))
        return delivered

    async def xgroup_create(self, stream, group, *, id="0", mkstream=False):
        self.created.append((stream, group))
        if self.recover_fails:
            raise RuntimeError("NOPERM this user has no permissions to run 'xgroup'")
        if stream in self.groups:
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")
        self.groups.add(stream)

    async def xack(self, stream: str, group: str, msg_id: bytes) -> None:
        self.acks.append((stream, group, msg_id))


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


def _position_record(symbol: str) -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "side": "long",
            "entry_price": 400.0,
            "quantity": 1,
            "opened_at_ms": 1757462400000,
            "setup_type": "setup_a_gap_reversion",
            "signal_id": "s-roll",
        }
    )


@pytest.mark.asyncio
async def test_recover_warns_for_position_on_a_rolled_out_contract(redis, caplog):
    """Review F5 on PR #689: flag a pre-roll record, but still recover it."""
    await redis.hset(POS_KEY, "A01609", _position_record("A01609"))
    await redis.hset(POS_KEY, "A01612", _position_record("A01612"))
    d = _make_daemon(redis)
    d.contract_symbol = "A01612"

    with caplog.at_level(logging.WARNING, logger="services.futures_monitor.daemon"):
        await d.recover_open_positions()

    assert set(d._open) == {"A01609", "A01612"}  # behaviour unchanged
    warnings = [r.getMessage() for r in caplog.records]
    assert len(warnings) == 1
    assert "A01609 is not on the current contract A01612" in warnings[0]


@pytest.mark.asyncio
async def test_recover_without_contract_symbol_does_not_warn(redis, caplog):
    await redis.hset(POS_KEY, "A01609", _position_record("A01609"))
    d = _make_daemon(redis)  # contract_symbol defaults to None

    with caplog.at_level(logging.WARNING, logger="services.futures_monitor.daemon"):
        await d.recover_open_positions()

    assert set(d._open) == {"A01609"}
    assert caplog.records == []


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
        message for message in messages if "event=stream_message_dropped" in message
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
        message for message in messages if "event=stream_message_ack_failed" in message
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


_FILL_STREAM = "order.fill.futures.shadow"
_SIGNAL_STREAM = "signal.final.futures.shadow"


def _recreate_logs(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "event=consumer_group_recovered" in record.getMessage()
    ]


@pytest.mark.asyncio
async def test_consume_loop_nogroup_recreates_both_groups_then_consumes(caplog):
    fields = {b"signal_id": b"sig-nogroup", b"symbol": b"A05603"}
    redis = _MissingGroupRedis(
        existing_groups=set(),
        pending={_SIGNAL_STREAM: [(b"1700000000000-3", fields)]},
    )
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        handled.append(data)
        d._stop.set()

    d.handle_signal = handler
    caplog.set_level(logging.WARNING)

    await asyncio.wait_for(d._consume_loop(), timeout=2.0)

    assert redis.created == [
        (_FILL_STREAM, "futures_monitor"),
        (_SIGNAL_STREAM, "futures_monitor"),
    ]
    assert _recreate_logs(caplog) == [
        f"event=consumer_group_recovered stream={_FILL_STREAM} "
        "consumer_group=futures_monitor",
        f"event=consumer_group_recovered stream={_SIGNAL_STREAM} "
        "consumer_group=futures_monitor",
    ]
    assert not any(
        "monitor_stream_read_error" in record.getMessage() for record in caplog.records
    )
    assert handled == [fields]
    assert redis.acks == [(_SIGNAL_STREAM, "futures_monitor", b"1700000000000-3")]


@pytest.mark.asyncio
async def test_consume_loop_non_nogroup_error_keeps_error_log_and_backoff(
    monkeypatch, caplog
):
    redis = _FailingReadRedis()
    d = _make_daemon(redis)
    caplog.set_level(logging.WARNING)
    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def record_sleep(seconds=0):
        sleeps.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr("services.futures_monitor.daemon.asyncio.sleep", record_sleep)

    async def stop_after_errors():
        while redis.calls < 2:
            await asyncio.sleep(0)
        await d.stop()

    await asyncio.gather(d._consume_loop(), stop_after_errors())

    assert 0.5 in sleeps
    assert any(
        "event=monitor_stream_read_error" in record.getMessage()
        for record in caplog.records
    )
    assert _recreate_logs(caplog) == []


@pytest.mark.asyncio
async def test_consume_loop_processes_signal_after_fill_stream_expired(caplog):
    """Regression: the expired fill stream must not blind the signal stream.

    Also the honest-log regression, inverted from the 2026-09-18 13:31:54
    production pair: both streams are swept, only the fill group was actually
    gone, so exactly one recovery WARNING may be emitted and it must name the
    stream that broke.
    """
    fields = {b"signal_id": b"sig-survivor", b"symbol": b"A05603"}
    redis = _MissingGroupRedis(
        existing_groups={_SIGNAL_STREAM},
        pending={_SIGNAL_STREAM: [(b"1700000000000-4", fields)]},
    )
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        handled.append(data)
        d._stop.set()

    d.handle_signal = handler
    caplog.set_level(logging.WARNING)

    await asyncio.wait_for(d._consume_loop(), timeout=2.0)

    assert redis.created == [
        (_FILL_STREAM, "futures_monitor"),
        (_SIGNAL_STREAM, "futures_monitor"),
    ]
    assert _recreate_logs(caplog) == [
        f"event=consumer_group_recovered stream={_FILL_STREAM} "
        "consumer_group=futures_monitor"
    ]
    assert handled == [fields]
    assert redis.acks == [(_SIGNAL_STREAM, "futures_monitor", b"1700000000000-4")]


@pytest.mark.asyncio
async def test_consume_loop_unblocked_key_gone_recovers_like_nogroup(caplog):
    """Production's first error per episode is UNBLOCKED, not NOGROUP.

    Redis sends it to a client already blocked in XREADGROUP when the key
    disappears underneath it — same recoverable condition, different code.
    """
    fields = {b"signal_id": b"sig-unblocked", b"symbol": b"A05603"}
    redis = _MissingGroupRedis(
        existing_groups=set(),
        pending={_SIGNAL_STREAM: [(b"1700000000000-5", fields)]},
        missing_error="UNBLOCKED the stream key no longer exists",
    )
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        handled.append(data)
        d._stop.set()

    d.handle_signal = handler
    caplog.set_level(logging.WARNING)

    await asyncio.wait_for(d._consume_loop(), timeout=2.0)

    assert redis.created == [
        (_FILL_STREAM, "futures_monitor"),
        (_SIGNAL_STREAM, "futures_monitor"),
    ]
    assert handled == [fields]
    assert not any(
        "monitor_stream_read_error" in record.getMessage() for record in caplog.records
    )


@pytest.mark.asyncio
async def test_consume_loop_failed_recovery_backs_off_instead_of_spinning(
    monkeypatch, caplog
):
    """A recreate that keeps failing must not turn into a hot loop.

    Both recoveries are still attempted, but the loop falls through to the
    rate-limited ``monitor_stream_read_error`` log and the 0.5s backoff.
    """
    redis = _MissingGroupRedis(existing_groups=set(), pending={}, recover_fails=True)
    d = _make_daemon(redis)
    caplog.set_level(logging.WARNING)
    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def record_sleep(seconds=0):
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            await d.stop()
        await real_sleep(0)

    monkeypatch.setattr("services.futures_monitor.daemon.asyncio.sleep", record_sleep)

    await asyncio.wait_for(d._consume_loop(), timeout=2.0)

    assert sleeps == [0.5, 0.5]
    # both streams attempted per iteration, despite the first one failing
    assert redis.created == [
        (_FILL_STREAM, "futures_monitor"),
        (_SIGNAL_STREAM, "futures_monitor"),
        (_FILL_STREAM, "futures_monitor"),
        (_SIGNAL_STREAM, "futures_monitor"),
    ]
    assert any(
        "event=monitor_stream_read_error" in record.getMessage()
        for record in caplog.records
    )
    assert _recreate_logs(caplog) == []
