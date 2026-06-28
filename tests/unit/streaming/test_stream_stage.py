"""Unit tests for shared.streaming.stage.StreamStage (consume loop)."""

from __future__ import annotations

import asyncio
import logging

import fakeredis.aioredis
import pytest

from shared.streaming.stage import StreamStage


class FakeRedis:
    """Minimal async Redis double for the consume loop.

    `xreadgroup` serves each queued batch once (FIFO), then returns [] forever.
    Records xgroup_create args and xack calls.
    """

    def __init__(
        self,
        batches: list[list[tuple[bytes, dict[bytes, bytes]]]],
        claimed_batches: list[list[tuple[bytes, dict[bytes, bytes]]]] | None = None,
    ):
        self._batches = list(batches)
        self._claimed_batches = list(claimed_batches or [])
        self.group_created: tuple | None = None
        self.acked: list[bytes] = []
        self.xreadgroup_calls = 0
        self.xautoclaim_calls = 0

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.group_created = (stream, group, id, mkstream)

    async def xreadgroup(self, *, streams, **_kwargs):
        self.xreadgroup_calls += 1
        if self._batches:
            msgs = self._batches.pop(0)
            stream_key = next(iter(streams))
            return [(stream_key, msgs)]
        await asyncio.sleep(0)
        return []

    async def xautoclaim(self, *_args, **_kwargs):
        self.xautoclaim_calls += 1
        if self._claimed_batches:
            return [b"0-0", self._claimed_batches.pop(0), []]
        return [b"0-0", [], []]

    async def xack(self, _stream, _group, msg_id):
        self.acked.append(msg_id)


class RecordingStage(StreamStage):
    """Concrete stage that records hook calls; handle_message return is configurable."""

    def __init__(self, *, ack_result=True, gate_result=True, **kw):
        super().__init__(**kw)
        self._ack_result = ack_result
        self._gate_result = gate_result
        self.handled: list[bytes] = []
        self.startup_calls = 0
        self.shutdown_calls = 0
        self.post_poll_counts: list[int] = []
        self.gate_calls = 0

    async def handle_message(self, msg_id, _fields):
        self.handled.append(msg_id)
        return self._ack_result

    async def on_startup(self):
        self.startup_calls += 1

    async def pre_iteration_gate(self):
        self.gate_calls += 1
        return self._gate_result

    async def post_poll(self, message_count):
        self.post_poll_counts.append(message_count)

    async def on_shutdown(self):
        self.shutdown_calls += 1


def _stage(redis, **kw):
    params = {
        "redis": redis,
        "input_stream": "s:in",
        "consumer_group": "g",
        "worker_id": "w",
        "xread_block_ms": 5,
        "batch_size": 10,
    }
    params.update(kw)
    return RecordingStage(**params)


async def _run_briefly(stage, seconds=0.05):
    task = asyncio.create_task(stage.run())
    await asyncio.sleep(seconds)
    await stage.stop()
    await asyncio.wait_for(task, timeout=1.0)


def _audit_records(caplog, event: str) -> list[dict[str, str]]:
    records = []
    for record in caplog.records:
        values = dict(
            token.split("=", 1)
            for token in record.getMessage().split()
            if "=" in token
        )
        if values.get("event") == event:
            records.append(values)
    return records


@pytest.mark.asyncio
async def test_creates_consumer_group_with_mkstream():
    redis = FakeRedis([])
    stage = _stage(redis)
    await _run_briefly(stage)
    assert redis.group_created == ("s:in", "g", "0", True)


@pytest.mark.asyncio
async def test_handle_message_called_and_acks_on_true():
    redis = FakeRedis([[(b"1-0", {b"k": b"v"})]])
    stage = _stage(redis, ack_result=True)
    await _run_briefly(stage)
    assert stage.handled == [b"1-0"]
    assert redis.acked == [b"1-0"]


@pytest.mark.asyncio
async def test_no_ack_when_handle_returns_false():
    redis = FakeRedis([[(b"1-0", {b"k": b"v"})]])
    stage = _stage(redis, ack_result=False)
    await _run_briefly(stage)
    assert stage.handled == [b"1-0"]
    assert redis.acked == []


@pytest.mark.asyncio
async def test_audit_log_for_acked_message_includes_context_and_signal(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FakeRedis([[(b"1-0", {b"signal_id": b"sig-1"})]])
    stage = _stage(redis, ack_result=True)

    await _run_briefly(stage)

    records = _audit_records(caplog, "stream_message_processed")
    assert len(records) == 1
    assert records[0] == {
        "event": "stream_message_processed",
        "stream": "s:in",
        "consumer_group": "g",
        "worker_id": "w",
        "msg_id": "1-0",
        "ack": "true",
        "claimed": "false",
        "duration_ms": records[0]["duration_ms"],
        "signal_id": "sig-1",
    }
    assert records[0]["duration_ms"].isdigit()


@pytest.mark.asyncio
async def test_audit_log_for_unacked_message_marks_ack_false(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FakeRedis([[(b"1-0", {b"signal_id": b"sig-2"})]])
    stage = _stage(redis, ack_result=False)

    await _run_briefly(stage)

    records = _audit_records(caplog, "stream_message_processed")
    assert len(records) == 1
    assert records[0]["ack"] == "false"
    assert records[0]["claimed"] == "false"
    assert records[0]["signal_id"] == "sig-2"


@pytest.mark.asyncio
async def test_no_audit_log_for_idle_polls(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FakeRedis([])
    stage = _stage(redis)

    await _run_briefly(stage)

    assert _audit_records(caplog, "stream_message_processed") == []


@pytest.mark.asyncio
async def test_reclaims_idle_pending_from_previous_consumer():
    redis = fakeredis.aioredis.FakeRedis(db=1)
    msg_id = await redis.xadd("s:in", {"k": "v"})
    await redis.xgroup_create("s:in", "g", id="0")
    await redis.xreadgroup(
        groupname="g", consumername="old-worker", streams={"s:in": ">"}, count=1
    )

    stage = _stage(redis, pending_retry_idle_ms=0)
    await _run_briefly(stage)

    assert stage.handled == [msg_id]
    pending = await redis.xpending("s:in", "g")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_pre_iteration_gate_false_stops_loop_before_read():
    redis = FakeRedis([[(b"1-0", {b"k": b"v"})]])
    stage = _stage(redis, gate_result=False)
    await _run_briefly(stage)
    assert redis.xreadgroup_calls == 0  # gate aborted before any read
    assert stage.handled == []
    assert stage.shutdown_calls == 1  # on_shutdown still runs (finally)


@pytest.mark.asyncio
async def test_on_startup_runs_before_loop_and_shutdown_in_finally():
    redis = FakeRedis([])
    stage = _stage(redis)
    await _run_briefly(stage)
    assert stage.startup_calls == 1
    assert stage.shutdown_calls == 1


@pytest.mark.asyncio
async def test_post_poll_receives_message_count_including_idle():
    redis = FakeRedis([[(b"1-0", {}), (b"2-0", {})]])
    stage = _stage(redis)
    await _run_briefly(stage)
    # first poll returns 2 messages, later polls are idle (0)
    assert stage.post_poll_counts[0] == 2
    assert 0 in stage.post_poll_counts[1:]


@pytest.mark.asyncio
async def test_handle_message_exception_propagates_but_shutdown_runs():
    class Boom(RecordingStage):
        async def handle_message(self, _msg_id, _fields):
            raise RuntimeError("boom")

    redis = FakeRedis([[(b"1-0", {})]])
    stage = Boom(
        redis=redis,
        input_stream="s:in",
        consumer_group="g",
        worker_id="w",
        xread_block_ms=5,
        batch_size=10,
    )
    task = asyncio.create_task(stage.run())
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(task, timeout=1.0)
    assert stage.shutdown_calls == 1


@pytest.mark.asyncio
async def test_handle_message_exception_logs_failure_context(caplog):
    class Boom(RecordingStage):
        async def handle_message(self, _msg_id, _fields):
            raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger="shared.streaming.stage")
    redis = FakeRedis([[(b"1-0", {b"signal_id": b"sig-fail"})]])
    stage = Boom(
        redis=redis,
        input_stream="s:in",
        consumer_group="g",
        worker_id="w",
        xread_block_ms=5,
        batch_size=10,
    )

    task = asyncio.create_task(stage.run())
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(task, timeout=1.0)

    records = _audit_records(caplog, "stream_message_failed")
    assert len(records) == 1
    assert records[0]["stream"] == "s:in"
    assert records[0]["consumer_group"] == "g"
    assert records[0]["worker_id"] == "w"
    assert records[0]["msg_id"] == "1-0"
    assert records[0]["signal_id"] == "sig-fail"


@pytest.mark.asyncio
async def test_xreadgroup_error_sleeps_and_continues():
    class FlakyRedis(FakeRedis):
        def __init__(self):
            super().__init__([[(b"9-0", {})]])
            self._raised = False

        async def xreadgroup(self, **kw):
            if not self._raised:
                self._raised = True
                raise ConnectionError("transient")
            return await super().xreadgroup(**kw)

    redis = FlakyRedis()
    stage = _stage(redis, xreadgroup_error_sleep_seconds=0.0)
    await _run_briefly(stage)
    # survived the transient error and still processed the message afterwards
    assert stage.handled == [b"9-0"]


@pytest.mark.asyncio
async def test_repeated_xreadgroup_errors_are_rate_limited(caplog):
    class FailingReadRedis(FakeRedis):
        async def xreadgroup(self, **_kw):
            self.xreadgroup_calls += 1
            raise ConnectionError("redis down")

    caplog.set_level(logging.ERROR, logger="shared.streaming.stage")
    redis = FailingReadRedis([])
    stage = _stage(redis, xreadgroup_error_sleep_seconds=0.0)

    await _run_briefly(stage, seconds=0.01)

    messages = [
        record.getMessage()
        for record in caplog.records
        if "xreadgroup error" in record.getMessage()
    ]
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_repeated_xautoclaim_errors_are_rate_limited(caplog):
    class FailingClaimRedis(FakeRedis):
        async def xautoclaim(self, *_args, **_kwargs):
            self.xautoclaim_calls += 1
            raise ConnectionError("redis down")

    caplog.set_level(logging.ERROR, logger="shared.streaming.stage")
    redis = FailingClaimRedis([])
    stage = _stage(
        redis,
        pending_retry_idle_ms=0,
        xreadgroup_error_sleep_seconds=0.0,
    )

    await _run_briefly(stage, seconds=0.01)

    messages = [
        record.getMessage()
        for record in caplog.records
        if "xautoclaim error" in record.getMessage()
    ]
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_on_startup_exception_still_runs_shutdown():
    class StartupBoom(RecordingStage):
        async def on_startup(self):
            await super().on_startup()
            raise RuntimeError("startup failed")

    redis = FakeRedis([])
    stage = StartupBoom(
        redis=redis,
        input_stream="s:in",
        consumer_group="g",
        worker_id="w",
        xread_block_ms=5,
        batch_size=10,
    )
    task = asyncio.create_task(stage.run())
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(task, timeout=1.0)
    assert stage.shutdown_calls == 1
