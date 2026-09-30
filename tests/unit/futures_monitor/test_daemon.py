"""F-5 FuturesMonitorDaemon — entry/exit pairing, multiplier PnL, hash writes."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest

from services.futures_monitor.daemon import (
    _CONSUME_ERROR_SLEEP_SECONDS,
    FuturesMonitorDaemon,
)

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


class _StartupStubMixin:
    """The two calls ``MultiStreamStage.run`` makes before its first read.

    ``on_startup`` recovers positions (HGETALL) and the stage then ensures one
    consumer group per input stream. Stubs that only script XREADGROUP would
    otherwise spend their first two log lines on AttributeError warnings that
    have nothing to do with what the test is pinning.
    """

    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []
        self.xautoclaim_calls: list[str] = []

    async def xgroup_create(self, stream, group, *, id="0", mkstream=False):
        self.created.append((stream, group))

    async def hgetall(self, _key):
        return {}

    async def xautoclaim(self, stream, *_args, **_kwargs):
        # Present so the daemon's choice is observable. If it were absent the
        # stage would swallow the AttributeError and disable reclaim anyway,
        # and a daemon that had turned reclaim ON would look identical.
        self.xautoclaim_calls.append(stream)
        return ["0-0", [], []]


class _OneMessageRedis(_StartupStubMixin):
    def __init__(
        self,
        *,
        stream: bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> None:
        super().__init__()
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


class _FailingReadRedis(_StartupStubMixin):
    def __init__(self, *, success_on_call: int | None = None) -> None:
        super().__init__()
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
    keeps failing. ``read_always_fails`` models the reviewer's spin scenario:
    the read keeps reporting a vanished stream while every group is already
    there, so every recreate answers BUSYGROUP and nothing is ever recovered.

    ``vanish_at_read`` is what makes an expiry testable now that the framework
    creates the groups on startup: those streams lose their group immediately
    before the first read, which is the production sequence — the daemon comes
    up healthy and the key's 24h TTL fires later, under a blocked XREADGROUP.
    Seeding ``existing_groups`` empty instead would only prove the startup
    creates work, never the recovery path.
    """

    def __init__(
        self,
        *,
        existing_groups: set[str],
        pending: dict[str, list[tuple[bytes, dict[bytes, bytes]]]],
        recover_fails: bool = False,
        missing_error: str | None = None,
        read_always_fails: bool = False,
        vanish_at_read: set[str] | None = None,
    ) -> None:
        self.groups = set(existing_groups)
        self.pending = dict(pending)
        self.recover_fails = recover_fails
        self.missing_error = missing_error
        self.read_always_fails = read_always_fails
        self.vanish_at_read = set(vanish_at_read or ())
        self.created: list[tuple[str, str]] = []
        self.acks: list[tuple[str, str, bytes]] = []
        self.reads = 0

    async def hgetall(self, _key):
        return {}

    async def xreadgroup(self, *, groupname, consumername, streams, **_kwargs):
        self.reads += 1
        if self.vanish_at_read:
            self.groups -= self.vanish_at_read
            self.vanish_at_read = set()
        missing = [name for name in streams if name not in self.groups]
        if missing or self.read_always_fails:
            default = (
                (
                    f"NOGROUP No such key '{missing[0]}' or consumer group "
                    f"'{groupname}' in XREADGROUP with GROUP option"
                )
                if missing
                else "UNBLOCKED the stream key no longer exists"
            )
            raise RuntimeError(self.missing_error or default)
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


# --------------------------------------------------------------------------- #
# Transport, now MultiStreamStage: the daemon's own `run()` is gone, so every
# test below drives `daemon.run()` — the same entrypoint services/futures_monitor
# /main.py calls. Sleeps and read-error logs come from shared.streaming.stage.
#
# ACKs carry the stream name exactly as Redis returned it (bytes), where the
# hand-rolled loop decoded it to str first. redis-py encodes str keys to utf-8,
# so the two are the same key on the wire; the assertions below quote the bytes
# because that is what the fakes now see.
# --------------------------------------------------------------------------- #

_STAGE_LOGGER = "shared.streaming.stage"
_DAEMON_LOGGER = "services.futures_monitor.daemon"
_FILL_STREAM = "order.fill.futures.shadow"
_SIGNAL_STREAM = "signal.final.futures.shadow"

# Bound before any test can monkeypatch ``asyncio.sleep``: patching
# ``shared.streaming.stage.asyncio.sleep`` sets the attribute on the asyncio
# module itself, so a driver coroutine that yields with the patched name would
# record its own sleeps as if the loop had taken them.
_REAL_SLEEP = asyncio.sleep


class _IdleRedis(_StartupStubMixin):
    """A stream that is up and simply has nothing to deliver."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def xreadgroup(self, **_kwargs):
        self.calls += 1
        await _REAL_SLEEP(0)
        return []


def _stage_sleeps(monkeypatch) -> list[float]:
    """Record what the stage's loop sleeps, without actually waiting."""
    sleeps: list[float] = []

    async def record_sleep(seconds=0):
        sleeps.append(seconds)
        await _REAL_SLEEP(0)

    monkeypatch.setattr("shared.streaming.stage.asyncio.sleep", record_sleep)
    return sleeps


async def _spin_until(predicate, *, timeout=2.0) -> None:
    """Yield until ``predicate()`` holds, failing rather than hanging.

    These loops are driven by a sibling coroutine, so a regression that stops
    the consume loop turning leaves a bare ``while not predicate()`` spinning
    for ever and the suite reports a timeout with no name on it. A deadline
    turns that into a named failure — which is the same argument the daemon
    change itself makes.
    """
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:  # pragma: no cover - guards a hang
            raise AssertionError(f"condition not reached within {timeout}s")
        await _REAL_SLEEP(0)


def _messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def _read_error_logs(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "xreadgroup error" in r.getMessage()]


def _recreate_logs(caplog) -> list[str]:
    return [m for m in _messages(caplog) if "event=consumer_group_recovered" in m]


# -- poison-message policy --------------------------------------------------- #


@pytest.mark.asyncio
async def test_poison_message_is_dropped_and_acked_instead_of_ending_the_loop(caplog):
    """The stage re-raises a handler exception; this daemon must not.

    ``MultiStreamStage._process_messages`` logs ``stream_message_failed`` and
    re-raises, which ends ``run()``. For an observation daemon that trades one
    malformed record for every record after it, so ``handle_message`` catches,
    reports ``stream_message_dropped`` with the traceback, and returns ``True``
    so the framework ACKs.
    """
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
    caplog.set_level(logging.ERROR)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert redis.acks == [
        (b"signal.final.futures.shadow", "futures_monitor", b"1700000000000-1")
    ]
    drop_log = next(m for m in _messages(caplog) if "event=stream_message_dropped" in m)
    assert "stream=signal.final.futures.shadow" in drop_log
    assert "consumer_group=futures_monitor" in drop_log
    assert "worker_id=w1" in drop_log
    assert "msg_id=1700000000000-1" in drop_log
    assert "reason=handler_exception" in drop_log
    assert "signal_id=sig-futures-1" in drop_log
    assert "symbol=A05603" in drop_log
    assert "setup_type=setup_c_event_reaction" in drop_log
    assert "account_number=secret" not in drop_log
    # The stage's own contract — raise on handler error — must not have fired.
    assert not any("event=stream_message_failed" in m for m in _messages(caplog))


@pytest.mark.asyncio
async def test_poison_message_does_not_stop_the_next_message_being_handled(caplog):
    """The point of dropping: record N+1 still arrives."""
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-9",
        fields={b"signal_id": b"sig-poison"},
    )
    redis.fields = {b"signal_id": b"sig-poison"}
    # two records in the one batch: the first blows up, the second must land
    good = {b"signal_id": b"sig-good"}

    async def two_messages(**_kwargs):
        if redis._returned:
            return []
        redis._returned = True
        return [
            (
                redis.stream,
                [(b"1700000000000-9", redis.fields), (b"1700000000000-10", good)],
            )
        ]

    redis.xreadgroup = two_messages
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        if data.get(b"signal_id") == b"sig-poison":
            raise RuntimeError("bad futures signal")
        handled.append(data)
        await d.stop()

    d.handle_signal = handler
    caplog.set_level(logging.ERROR)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert handled == [good]
    assert [msg_id for _s, _g, msg_id in redis.acks] == [
        b"1700000000000-9",
        b"1700000000000-10",
    ]


@pytest.mark.asyncio
async def test_poison_message_drop_does_not_claim_an_ack_the_framework_owns(caplog):
    """The drop line stops asserting ``ack=true``; the framework's line says it.

    Before the migration the daemon ACKed and then logged ``ack=true``, so the
    claim was true by construction. The ACK now happens after ``handle_message``
    returns, so repeating the claim here would be a guess — and a wrong one
    whenever XACK fails. The pair (drop, then the framework's own record for the
    same ``msg_id``) carries strictly more than the single line did.
    """
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-6",
        fields={b"signal_id": b"sig-pair"},
    )
    d = _make_daemon(redis)
    redis.on_ack = d._stop.set

    async def fail_handler(_fields):
        raise RuntimeError("bad futures signal")

    d.handle_signal = fail_handler
    caplog.set_level(logging.INFO)

    await asyncio.wait_for(d.run(), timeout=2.0)

    drop_log = next(m for m in _messages(caplog) if "event=stream_message_dropped" in m)
    assert "ack=" not in drop_log
    processed = next(
        m for m in _messages(caplog) if "event=stream_message_processed" in m
    )
    assert "msg_id=1700000000000-6" in processed
    assert "ack=true" in processed


# -- §1.3: the loop can no longer die quietly -------------------------------- #


@pytest.mark.asyncio
async def test_xack_failure_ends_run_instead_of_dying_as_an_orphan_task(caplog):
    """§1.3, closed: a failing XACK now takes the process down with it.

    The old shape put the consume loop in a task that ``run()`` never awaited
    while ``_stop`` stayed clear, so this exception killed consumption and left
    ``_status_loop`` publishing fresh status keys from a daemon that read
    nothing — ``RestartCount=0``, invisible to every health check. There is one
    loop now, so the exception leaves ``run()``, reaches ``main()``, and the
    container restart policy makes it visible.

    **Promptness is the assertion, not the exception.** ``ConnectionError``
    alone does not distinguish the fix from the defect: against pre-migration
    code ``run()`` parks on ``_stop.wait()`` while the orphaned consume task
    holds the error, a ``wait_for`` timeout cancels ``run()``, and the
    ``finally``'s ``await t`` re-raises the *same* ``ConnectionError`` —
    ``suppress(CancelledError)`` does not catch it. So a bare
    ``pytest.raises(ConnectionError)`` is satisfied at teardown, two seconds
    late, **by the very orphan-task behaviour this test claims is gone**
    (measured: 2.00s pre-migration, 0.01s post). Waiting a bounded 0.5s and
    asserting the task is already ``done`` is what separates "the loop ended"
    from "teardown noticed" — 4x the post-migration time, 4x under the
    pre-migration path.
    """
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-2",
        fields={b"signal_id": b"sig-futures-ack", b"symbol": b"A05603"},
    )
    redis.fail_ack = True
    d = _make_daemon(redis)

    async def fail_handler(_fields):
        raise RuntimeError("bad futures signal")

    d.handle_signal = fail_handler
    caplog.set_level(logging.ERROR)

    task = asyncio.create_task(d.run())
    done, _pending = await asyncio.wait({task}, timeout=0.5)

    assert done, "run() must end with the loop, not at teardown"
    with pytest.raises(ConnectionError):
        task.result()

    ack_log = next(
        m for m in _messages(caplog) if "event=stream_message_ack_failed" in m
    )
    assert "stream=signal.final.futures.shadow" in ack_log
    assert "consumer_group=futures_monitor" in ack_log
    assert "worker_id=w1" in ack_log
    assert "msg_id=1700000000000-2" in ack_log
    assert "signal_id=sig-futures-ack" in ack_log
    assert "symbol=A05603" in ack_log


async def _record_stop(sink: list[bool]) -> None:
    sink.append(True)


@pytest.mark.asyncio
async def test_shutdown_hook_stops_the_feed_even_when_the_loop_raises():
    """``on_shutdown`` runs from the stage's ``finally``, on both exits."""
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-3",
        fields={b"signal_id": b"sig-shutdown"},
    )
    redis.fail_ack = True
    d = _make_daemon(redis)
    stopped: list[bool] = []
    d.feed.stop = lambda: _record_stop(stopped)

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(d.run(), timeout=2.0)

    assert stopped == [True]


# -- startup + liveness ------------------------------------------------------ #


@pytest.mark.asyncio
async def test_run_recovers_open_positions_before_consuming(redis):
    """``on_startup`` keeps the recovery the hand-rolled ``run()`` did."""
    await redis.hset(POS_KEY, "A05603", _position_record("A05603"))
    d = _make_daemon(redis)
    await d.stop()  # the loop exits after startup, which is what this pins

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert d._open["A05603"]["entry_price"] == 400.0


@pytest.mark.asyncio
async def test_pending_entry_reclaim_stays_off():
    """Redelivery is a behaviour change this migration deliberately does not make.

    The hand-rolled loop never reclaimed pending entries, and the stage would
    by default (XAUTOCLAIM after ``pending_retry_idle_ms``). A redelivered entry
    fill is not a free retry here: ``alert_sink.on_entry`` fires a second time
    and ``high_water``/``low_water`` are reset to the entry price, discarding
    the watermark the position has accumulated. Turning it on needs its own
    evidence, so this pins that moving onto the stage did not turn it on by
    inheritance.
    """
    redis = _IdleRedis()
    d = _make_daemon(redis)

    async def stop_after_polls():
        await _spin_until(lambda: not (redis.calls < 3))
        await d.stop()

    await asyncio.gather(d.run(), stop_after_polls())

    assert redis.xautoclaim_calls == []


@pytest.mark.asyncio
async def test_idle_loop_emits_the_liveness_heartbeat(caplog):
    """The f9 gap this migration closes for ``futures-monitor``.

    ``config/f9_observation.yaml`` scores this service on stage-emitted lines
    the hand-rolled loop never produced, so a quiet session was
    indistinguishable from a dead one. The heartbeat now fires from the idle
    path, where there is no other evidence at all.
    """
    redis = _IdleRedis()
    d = _make_daemon(redis)
    # first poll opens the interval, second lands past it; later polls sit at
    # the same instant so exactly one heartbeat is due
    ticks = iter([0.0, 100.0])
    d._heartbeat._clock = lambda: next(ticks, 100.0)
    caplog.set_level(logging.INFO, logger=_STAGE_LOGGER)

    async def stop_after_polls():
        await _spin_until(lambda: not (redis.calls < 3))
        await d.stop()

    await asyncio.gather(d.run(), stop_after_polls())

    alive = [m for m in _messages(caplog) if "event=stream_consumer_alive" in m]
    assert len(alive) == 1
    assert f'streams="{_FILL_STREAM},{_SIGNAL_STREAM}"' in alive[0]
    assert "consumer_group=futures_monitor" in alive[0]
    assert "worker_id=w1" in alive[0]
    assert "messages=0" in alive[0]  # alive, watching, no traffic


# -- status cadence: pre_iteration_gate -------------------------------------- #


@pytest.mark.asyncio
async def test_status_cadence_fires_on_schedule_not_every_iteration(monkeypatch):
    """The gate paces the tick; it does not run it on every poll."""
    _stage_sleeps(monkeypatch)
    now = [0.0]

    def clock() -> float:
        now[0] += 2.0  # one iteration of an idle loop
        return now[0]

    redis = _IdleRedis()
    d = FuturesMonitorDaemon(
        redis=redis,
        feed=_FakeFeed(),
        publisher=MagicMock(),
        alert_sink=None,
        positions_key=POS_KEY,
        fill_stream=_FILL_STREAM,
        signal_stream=_SIGNAL_STREAM,
        consumer_group="futures_monitor",
        worker_id="w1",
        multiplier=MULT,
        status_interval=5.0,
        status_clock=clock,
    )
    ticks: list[float] = []

    async def record_tick():
        ticks.append(now[0])
        if len(ticks) >= 3:
            await d.stop()

    d.publish_status_and_mtm = record_tick

    await asyncio.wait_for(d.run(), timeout=2.0)

    # tick 1 immediately (parity with _status_loop's immediate first tick), then
    # only on the first iteration at or past 5s since the last one
    assert ticks == [2.0, 8.0, 14.0]
    assert redis.calls > len(ticks)  # most iterations published nothing


@pytest.mark.asyncio
async def test_status_cadence_survives_a_raising_publish(caplog):
    """A throwing status tick must not stop the consume loop.

    ``pre_iteration_gate`` returning ``False`` makes ``run()`` return, so an
    exception escaping this hook would blind the daemon — the failure mode the
    migration exists to delete, reintroduced through the hook that replaced the
    status task. ``_status_loop`` logged "status loop error; continuing"; so
    does this.
    """
    redis = _OneMessageRedis(
        stream=b"signal.final.futures.shadow",
        msg_id=b"1700000000000-5",
        fields={b"signal_id": b"sig-after-status-error"},
    )
    d = _make_daemon(redis)
    redis.on_ack = d._stop.set
    handled: list[dict[bytes, bytes]] = []

    async def boom():
        raise RuntimeError("status publish down")

    async def handler(data):
        handled.append(data)

    d.publish_status_and_mtm = boom
    d.handle_signal = handler
    caplog.set_level(logging.ERROR, logger=_DAEMON_LOGGER)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert handled  # the loop kept consuming
    assert any("status loop error; continuing" in m for m in _messages(caplog))


@pytest.mark.asyncio
async def test_status_cadence_keeps_running_while_every_read_fails(monkeypatch):
    """Why the cadence lives on the gate and not on ``post_poll``.

    A failed read ``continue``s before ``post_poll``, so a status tick hung
    there would go silent during exactly the Redis trouble an operator needs
    status for. The old ``_status_loop`` was a separate task and kept ticking;
    the gate runs at the top of every iteration, including after that
    ``continue``.
    """
    _stage_sleeps(monkeypatch)
    redis = _FailingReadRedis()
    d = _make_daemon(redis)  # status_interval 0.01 -> a tick most iterations
    ticks: list[int] = []

    async def record_tick():
        ticks.append(redis.calls)
        if len(ticks) >= 3:
            await d.stop()

    d.publish_status_and_mtm = record_tick

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert len(ticks) >= 3
    assert redis.calls >= 2  # the reads really were failing throughout


# -- read errors ------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_repeated_read_errors_are_rate_limited(monkeypatch, caplog):
    redis = _FailingReadRedis()
    d = _make_daemon(redis)
    caplog.set_level(logging.ERROR, logger=_STAGE_LOGGER)
    _stage_sleeps(monkeypatch)

    async def stop_after_errors():
        await _spin_until(lambda: not (redis.calls < 3))
        await d.stop()

    await asyncio.gather(d.run(), stop_after_errors())

    assert len(_read_error_logs(caplog)) == 1
    assert _read_error_logs(caplog)[0].exc_info is not None


@pytest.mark.asyncio
async def test_read_error_logs_again_after_success(monkeypatch, caplog):
    redis = _FailingReadRedis(success_on_call=2)
    d = _make_daemon(redis)
    caplog.set_level(logging.ERROR, logger=_STAGE_LOGGER)
    _stage_sleeps(monkeypatch)

    async def stop_after_errors():
        await _spin_until(lambda: not (redis.calls < 3))
        await d.stop()

    await asyncio.gather(d.run(), stop_after_errors())

    assert len(_read_error_logs(caplog)) == 2


# -- vanished consumer groups (#739/#741), now via the shared sweep ---------- #


@pytest.mark.asyncio
async def test_nogroup_recreates_both_groups_then_consumes(caplog):
    """#739, still covered after the migration: either stream's key can vanish."""
    fields = {b"signal_id": b"sig-nogroup", b"symbol": b"A05603"}
    redis = _MissingGroupRedis(
        existing_groups={_FILL_STREAM, _SIGNAL_STREAM},
        vanish_at_read={_FILL_STREAM, _SIGNAL_STREAM},
        pending={_SIGNAL_STREAM: [(b"1700000000000-3", fields)]},
    )
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        handled.append(data)
        await d.stop()

    d.handle_signal = handler
    caplog.set_level(logging.WARNING)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert redis.created == [
        (_FILL_STREAM, "futures_monitor"),  # startup
        (_SIGNAL_STREAM, "futures_monitor"),
        (_FILL_STREAM, "futures_monitor"),  # recovery sweep
        (_SIGNAL_STREAM, "futures_monitor"),
    ]
    assert _recreate_logs(caplog) == [
        f"event=consumer_group_recovered stream={_FILL_STREAM} "
        "consumer_group=futures_monitor",
        f"event=consumer_group_recovered stream={_SIGNAL_STREAM} "
        "consumer_group=futures_monitor",
    ]
    assert _read_error_logs(caplog) == []
    assert handled == [fields]
    assert redis.acks == [
        (_SIGNAL_STREAM.encode(), "futures_monitor", b"1700000000000-3")
    ]


@pytest.mark.asyncio
async def test_non_nogroup_error_keeps_error_log_and_backoff(monkeypatch, caplog):
    redis = _FailingReadRedis()
    d = _make_daemon(redis)
    caplog.set_level(logging.WARNING)
    sleeps = _stage_sleeps(monkeypatch)

    async def stop_after_errors():
        await _spin_until(lambda: not (redis.calls < 2))
        await d.stop()

    await asyncio.gather(d.run(), stop_after_errors())

    assert _CONSUME_ERROR_SLEEP_SECONDS in sleeps
    assert _read_error_logs(caplog)
    assert _recreate_logs(caplog) == []


@pytest.mark.asyncio
async def test_all_groups_present_backs_off_instead_of_spinning(monkeypatch, caplog):
    """A vanished-stream read error that recovers nothing must not hot-loop.

    Measured on the shape this replaced: 50 reads, 100 BUSYGROUP recreates,
    every sleep 0, and not one record at or above INFO — the 2026-09-17 silence
    again, this time burning a core. #741 fixed it in the daemon; the fix now
    lives once, in ``sweep_vanished_consumer_groups``, and this pins that the
    daemon still gets it.
    """
    redis = _MissingGroupRedis(
        existing_groups={_FILL_STREAM, _SIGNAL_STREAM},
        pending={},
        read_always_fails=True,
    )
    d = _make_daemon(redis)
    caplog.set_level(logging.WARNING)
    sleeps = _stage_sleeps(monkeypatch)

    async def stop_after_errors():
        await _spin_until(lambda: not (redis.reads < 3))
        await d.stop()

    await asyncio.gather(d.run(), stop_after_errors())

    # every iteration paid the backoff; none took the zero-sleep fast path
    assert sleeps
    assert set(sleeps) == {_CONSUME_ERROR_SLEEP_SECONDS}
    # the recreates all answered BUSYGROUP, so nothing may claim a recovery
    assert _recreate_logs(caplog) == []
    assert redis.created  # the daemon did sweep both streams
    # and the operator gets the read error exactly once, rate-limited
    assert len(_read_error_logs(caplog)) == 1


@pytest.mark.asyncio
async def test_processes_signal_after_fill_stream_expired(monkeypatch, caplog):
    """Regression: the expired fill stream must not blind the signal stream.

    Also the honest-log regression, inverted from the 2026-09-18 13:31:54
    production pair: both streams are swept, only the fill group was actually
    gone, so exactly one recovery WARNING may be emitted and it must name the
    stream that broke. A genuine recreate keeps the zero-sleep retry — the
    backoff belongs to the paths that recovered nothing.
    """
    fields = {b"signal_id": b"sig-survivor", b"symbol": b"A05603"}
    redis = _MissingGroupRedis(
        existing_groups={_FILL_STREAM, _SIGNAL_STREAM},
        vanish_at_read={_FILL_STREAM},
        pending={_SIGNAL_STREAM: [(b"1700000000000-4", fields)]},
    )
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        handled.append(data)
        await d.stop()

    d.handle_signal = handler
    caplog.set_level(logging.WARNING)
    sleeps = _stage_sleeps(monkeypatch)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert _recreate_logs(caplog) == [
        f"event=consumer_group_recovered stream={_FILL_STREAM} "
        "consumer_group=futures_monitor"
    ]
    assert sleeps == [0]
    assert _read_error_logs(caplog) == []
    assert handled == [fields]
    assert redis.acks == [
        (_SIGNAL_STREAM.encode(), "futures_monitor", b"1700000000000-4")
    ]


@pytest.mark.asyncio
async def test_unblocked_key_gone_recovers_like_nogroup(caplog):
    """Production's first error per episode is UNBLOCKED, not NOGROUP.

    Redis sends it to a client already blocked in XREADGROUP when the key
    disappears underneath it — same recoverable condition, different code.
    """
    fields = {b"signal_id": b"sig-unblocked", b"symbol": b"A05603"}
    redis = _MissingGroupRedis(
        existing_groups={_FILL_STREAM, _SIGNAL_STREAM},
        vanish_at_read={_FILL_STREAM, _SIGNAL_STREAM},
        pending={_SIGNAL_STREAM: [(b"1700000000000-5", fields)]},
        missing_error="UNBLOCKED the stream key no longer exists",
    )
    d = _make_daemon(redis)
    handled: list[dict[bytes, bytes]] = []

    async def handler(data):
        handled.append(data)
        await d.stop()

    d.handle_signal = handler
    caplog.set_level(logging.WARNING)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert handled == [fields]
    assert _read_error_logs(caplog) == []


@pytest.mark.asyncio
async def test_failed_recovery_backs_off_instead_of_spinning(monkeypatch, caplog):
    """A recreate that keeps failing must not turn into a hot loop.

    Both recoveries are still attempted, but the loop falls through to the
    rate-limited read-error log and the 0.5s backoff.
    """
    redis = _MissingGroupRedis(existing_groups=set(), pending={}, recover_fails=True)
    d = _make_daemon(redis)
    caplog.set_level(logging.WARNING)
    sleeps: list[float] = []

    async def record_sleep(seconds=0):
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            await d.stop()
        await _REAL_SLEEP(0)

    monkeypatch.setattr("shared.streaming.stage.asyncio.sleep", record_sleep)

    await asyncio.wait_for(d.run(), timeout=2.0)

    assert sleeps == [_CONSUME_ERROR_SLEEP_SECONDS, _CONSUME_ERROR_SLEEP_SECONDS]
    # two startup attempts, then both streams attempted per failing iteration
    assert (
        redis.created
        == [
            (_FILL_STREAM, "futures_monitor"),
            (_SIGNAL_STREAM, "futures_monitor"),
        ]
        * 3
    )
    assert _read_error_logs(caplog)
    assert _recreate_logs(caplog) == []
