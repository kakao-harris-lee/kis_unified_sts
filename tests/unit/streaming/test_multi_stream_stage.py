"""Unit tests for shared.streaming.stage.MultiStreamStage."""

from __future__ import annotations

import asyncio

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
async def test_no_ack_when_handle_returns_false():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, ack_result=False)

    await _run_briefly(stage)

    assert stage.handled == [("s:a", b"1-0")]
    assert redis.acked == []


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
async def test_pre_iteration_gate_false_stops_before_read_and_runs_shutdown():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, gate_result=False)

    await _run_briefly(stage)

    assert redis.xreadgroup_calls == 0
    assert stage.handled == []
    assert stage.shutdown_calls == 1
