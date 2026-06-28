"""Unit tests for shared.streaming.stage.MultiStreamStage."""

from __future__ import annotations

import asyncio
import logging
import shlex

import pytest

from shared.streaming.stage import MultiStreamStage


class FakeRedis:
    def __init__(
        self,
        batches: list[tuple[str | bytes, list[tuple[bytes, dict[bytes, bytes]]]]],
        claimed: dict[str, list[list[tuple[bytes, dict[bytes, bytes]]]]] | None = None,
    ) -> None:
        self._batches = list(batches)
        self._claimed = {key: list(value) for key, value in (claimed or {}).items()}
        self.created: list[tuple[str | bytes, str, str, bool]] = []
        self.acked: list[tuple[str | bytes, bytes]] = []
        self.xreadgroup_calls = 0
        self.xautoclaim_calls: list[str] = []

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.created.append((stream, group, id, mkstream))

    async def xreadgroup(self, *, streams, **_kwargs):
        self.xreadgroup_calls += 1
        if self._batches:
            stream, messages = self._batches.pop(0)
            if isinstance(stream, bytes):
                assert stream.decode("utf-8") in streams
            else:
                assert stream in streams
            return [(stream, messages)]
        await asyncio.sleep(0)
        return []

    async def xautoclaim(self, stream, _group, _worker, _idle_ms, _start_id, *, count):
        self.xautoclaim_calls.append(stream)
        batches = self._claimed.get(stream, [])
        if batches:
            return ["0-0", batches.pop(0)[:count], []]
        return ["0-0", [], []]

    async def xack(self, stream, _group, msg_id):
        self.acked.append((stream, msg_id))


class RecordingMultiStage(MultiStreamStage):
    def __init__(self, *, ack_result=True, gate_result=True, **kwargs):
        super().__init__(**kwargs)
        self.ack_result = ack_result
        self.gate_result = gate_result
        self.handled: list[tuple[str | bytes, bytes]] = []
        self.post_poll_counts: list[int] = []
        self.shutdown_calls = 0

    async def handle_message(self, stream, msg_id, _fields):
        self.handled.append((stream, msg_id))
        return self.ack_result

    async def pre_iteration_gate(self):
        return self.gate_result

    async def post_poll(self, message_count):
        self.post_poll_counts.append(message_count)

    async def on_shutdown(self):
        self.shutdown_calls += 1


def _stage(redis, **kwargs):
    params = {
        "redis": redis,
        "input_streams": ["s:a", "s:b"],
        "consumer_group": "g",
        "worker_id": "w",
        "xread_block_ms": 5,
        "batch_size": 10,
    }
    params.update(kwargs)
    return RecordingMultiStage(**params)


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
            for token in shlex.split(record.getMessage())
            if "=" in token
        )
        if values.get("event") == event:
            records.append(values)
    return records


@pytest.mark.asyncio
async def test_creates_consumer_group_for_each_stream():
    redis = FakeRedis([])
    stage = _stage(redis)

    await _run_briefly(stage)

    assert redis.created == [
        ("s:a", "g", "0", True),
        ("s:b", "g", "0", True),
    ]


@pytest.mark.asyncio
async def test_processes_and_acks_each_message_on_its_source_stream():
    redis = FakeRedis(
        [
            ("s:a", [(b"1-0", {b"k": b"a"})]),
            ("s:b", [(b"2-0", {b"k": b"b"})]),
        ]
    )
    stage = _stage(redis)

    await _run_briefly(stage)

    assert stage.handled == [("s:a", b"1-0"), ("s:b", b"2-0")]
    assert redis.acked == [("s:a", b"1-0"), ("s:b", b"2-0")]


@pytest.mark.asyncio
async def test_audit_log_for_processed_messages_uses_source_stream(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FakeRedis([("s:a", [(b"1-0", {b"code": b"005930"})])])
    stage = _stage(redis)

    await _run_briefly(stage)

    records = _audit_records(caplog, "stream_message_processed")
    assert len(records) == 1
    assert records[0] == {
        "event": "stream_message_processed",
        "stream": "s:a",
        "consumer_group": "g",
        "worker_id": "w",
        "msg_id": "1-0",
        "ack": "true",
        "claimed": "false",
        "duration_ms": records[0]["duration_ms"],
        "code": "005930",
    }
    assert records[0]["duration_ms"].isdigit()


@pytest.mark.asyncio
async def test_no_ack_when_handle_returns_false():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, ack_result=False)

    await _run_briefly(stage)

    assert stage.handled == [("s:a", b"1-0")]
    assert redis.acked == []


@pytest.mark.asyncio
async def test_audit_log_for_acked_message_requires_successful_xack(caplog):
    class FailingAckRedis(FakeRedis):
        async def xack(self, _stream, _group, _msg_id):
            raise ConnectionError("xack down")

    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FailingAckRedis([("s:a", [(b"1-0", {b"code": b"005930"})])])
    stage = _stage(redis)

    task = asyncio.create_task(stage.run())
    with pytest.raises(ConnectionError):
        await asyncio.wait_for(task, timeout=1.0)

    assert _audit_records(caplog, "stream_message_processed") == []
    records = _audit_records(caplog, "stream_message_ack_failed")
    assert len(records) == 1
    assert records[0]["stream"] == "s:a"
    assert records[0]["consumer_group"] == "g"
    assert records[0]["worker_id"] == "w"
    assert records[0]["msg_id"] == "1-0"
    assert records[0]["code"] == "005930"


@pytest.mark.asyncio
async def test_processes_bytes_stream_names_from_redis():
    redis = FakeRedis([(b"s:a", [(b"1-0", {})])])
    stage = _stage(redis)

    await _run_briefly(stage)

    assert stage.handled == [(b"s:a", b"1-0")]
    assert redis.acked == [(b"s:a", b"1-0")]


@pytest.mark.asyncio
async def test_reclaims_idle_pending_per_stream_before_new_reads():
    redis = FakeRedis(
        batches=[("s:b", [(b"2-0", {})])],
        claimed={"s:a": [[(b"1-0", {})]], "s:b": []},
    )
    stage = _stage(redis, pending_retry_idle_ms=0)

    await _run_briefly(stage)

    assert stage.handled[:2] == [("s:a", b"1-0"), ("s:b", b"2-0")]
    assert redis.acked[:2] == [("s:a", b"1-0"), ("s:b", b"2-0")]
    assert "s:a" in redis.xautoclaim_calls
    assert "s:b" in redis.xautoclaim_calls


@pytest.mark.asyncio
async def test_audit_log_for_reclaimed_message_marks_claimed_true(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FakeRedis(
        batches=[],
        claimed={"s:a": [[(b"1-0", {b"signal_id": b"sig-claimed"})]], "s:b": []},
    )
    stage = _stage(redis, pending_retry_idle_ms=0)

    await _run_briefly(stage)

    records = _audit_records(caplog, "stream_message_processed")
    assert len(records) == 1
    assert records[0]["stream"] == "s:a"
    assert records[0]["claimed"] == "true"
    assert records[0]["ack"] == "true"
    assert records[0]["signal_id"] == "sig-claimed"


@pytest.mark.asyncio
async def test_handle_message_exception_logs_failure_source_stream(caplog):
    class Boom(RecordingMultiStage):
        async def handle_message(self, _stream, _msg_id, _fields):
            raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger="shared.streaming.stage")
    redis = FakeRedis([("s:a", [(b"1-0", {b"signal_id": b"sig-fail"})])])
    stage = Boom(
        redis=redis,
        input_streams=["s:a", "s:b"],
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
    assert records[0]["stream"] == "s:a"
    assert records[0]["consumer_group"] == "g"
    assert records[0]["worker_id"] == "w"
    assert records[0]["msg_id"] == "1-0"
    assert records[0]["signal_id"] == "sig-fail"


@pytest.mark.asyncio
async def test_xreadgroup_error_logs_again_after_success(caplog):
    class ErrorSuccessErrorRedis(FakeRedis):
        def __init__(self):
            super().__init__([("s:a", [(b"9-0", {})])])
            self._calls = 0

        async def xreadgroup(self, **kw):
            self._calls += 1
            if self._calls in {1, 3}:
                raise ConnectionError("transient")
            return await super().xreadgroup(**kw)

    caplog.set_level(logging.ERROR, logger="shared.streaming.stage")
    redis = ErrorSuccessErrorRedis()
    stage = _stage(redis, xreadgroup_error_sleep_seconds=0.0)

    await _run_briefly(stage, seconds=0.02)

    messages = [
        record.getMessage()
        for record in caplog.records
        if "xreadgroup error" in record.getMessage()
    ]
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_pre_iteration_gate_false_stops_before_read_and_runs_shutdown():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, gate_result=False)

    await _run_briefly(stage)

    assert redis.xreadgroup_calls == 0
    assert stage.handled == []
    assert stage.shutdown_calls == 1
