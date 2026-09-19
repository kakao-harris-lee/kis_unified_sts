"""Unit tests for shared.streaming.stage.MultiStreamStage."""

from __future__ import annotations

import asyncio
import logging
import shlex
import time

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
async def test_xreadgroup_nogroup_recreates_groups_and_processes_existing_message():
    class MissingGroupRedis(FakeRedis):
        def __init__(self):
            super().__init__([("s:a", [(b"9-0", {})])])
            self._raised = False

        async def xreadgroup(self, **kw):
            self.xreadgroup_calls += 1
            if not self._raised:
                self._raised = True
                raise RuntimeError("NOGROUP No such key 's:a' or consumer group 'g'")
            return await super().xreadgroup(**kw)

    redis = MissingGroupRedis()
    stage = _stage(redis, xreadgroup_error_sleep_seconds=0.0)

    await _run_briefly(stage)

    assert redis.created == [
        ("s:a", "g", "0", True),
        ("s:b", "g", "0", True),
        ("s:a", "g", "0", True),
        ("s:b", "g", "0", True),
    ]
    assert stage.handled == [("s:a", b"9-0")]


@pytest.mark.asyncio
async def test_pre_iteration_gate_false_stops_before_read_and_runs_shutdown():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, gate_result=False)

    await _run_briefly(stage)

    assert redis.xreadgroup_calls == 0
    assert stage.handled == []
    assert stage.shutdown_calls == 1


# --------------------------------------------------------------------------- #
# Vanished-stream recovery: the three-way rule (#741, ported from the monitors)
# --------------------------------------------------------------------------- #

_BACKOFF = 0.25  # distinctive, so a recorded sleep says which path was taken
_NOGROUP = "NOGROUP No such key 's:a' or consumer group 'g' in XREADGROUP"
_UNBLOCKED = "UNBLOCKED the stream key no longer exists"
_CLIENT_UNBLOCK = "UNBLOCKED client unblocked via CLIENT UNBLOCK"

# Bound before any test can monkeypatch ``asyncio.sleep``.
_REAL_SLEEP = asyncio.sleep


class _RecoveryRedis(FakeRedis):
    """XREADGROUP fails with a scripted error; XGROUP CREATE answers per stream.

    ``group_states`` maps each input stream to what its recreate reports:
    ``"created"`` (the group really was gone), ``"existed"`` (BUSYGROUP —
    nothing was missing after all), or ``"failed"`` (the recreate itself cannot
    run). Both streams are read in one XREADGROUP, so the read fails as a unit
    and the sweep has to touch every stream — which is exactly why the mixed
    cases below only exist for this class.
    """

    def __init__(
        self,
        *,
        group_states: dict[str, str],
        read_error: str = _NOGROUP,
        read_fails_forever: bool = True,
        batches=None,
    ) -> None:
        super().__init__(batches or [])
        self.group_states = group_states
        self.read_error = read_error
        self.read_fails_forever = read_fails_forever
        self._read_failed = False

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.created.append((stream, group, id, mkstream))
        state = self.group_states.get(stream, "created")
        if state == "existed":
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")
        if state == "failed":
            raise RuntimeError("NOPERM this user has no permissions to run 'xgroup'")

    async def xreadgroup(self, **kwargs):
        if self.read_fails_forever or not self._read_failed:
            self._read_failed = True
            self.xreadgroup_calls += 1
            raise RuntimeError(self.read_error)
        return await super().xreadgroup(**kwargs)


def _record_sleeps(monkeypatch) -> list[float]:
    """Replace ``asyncio.sleep`` with a recorder that never actually waits."""
    sleeps: list[float] = []

    async def record_sleep(seconds=0):
        sleeps.append(seconds)
        await _REAL_SLEEP(0)

    monkeypatch.setattr("shared.streaming.stage.asyncio.sleep", record_sleep)
    return sleeps


async def _drive_until(stage, predicate, *, timeout=2.0) -> None:
    """Run the loop until ``predicate()`` holds, then stop it and await exit."""
    task = asyncio.create_task(stage.run())
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:  # pragma: no cover - guards a hang
            task.cancel()
            raise AssertionError(f"condition not reached within {timeout}s")
        await _REAL_SLEEP(0)
    await stage.stop()
    await asyncio.wait_for(task, timeout=timeout)


def _read_error_logs(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "xreadgroup error" in r.getMessage()]


@pytest.mark.asyncio
async def test_vanished_read_that_recreated_a_group_retries_without_backoff(
    monkeypatch, caplog
):
    """One genuine recreate in the sweep earns the immediate retry.

    ``s:a`` expired and took the shared read down with it; ``s:b`` was healthy
    and answers BUSYGROUP. Something really was recovered, so the next read has
    a reason to succeed and must not be delayed — and only the stream that
    broke may be reported as recovered.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(
        group_states={"s:a": "created", "s:b": "existed"},
        read_fails_forever=False,
        batches=[("s:a", [(b"9-0", {})])],
    )
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: stage.handled)

    assert stage.handled == [("s:a", b"9-0")]
    assert _BACKOFF not in sleeps
    assert _read_error_logs(caplog) == []
    recovered = _audit_records(caplog, "consumer_group_recovered")
    assert [r["stream"] for r in recovered] == ["s:a"]


@pytest.mark.asyncio
async def test_vanished_read_with_every_group_present_backs_off_instead_of_spinning(
    monkeypatch, caplog
):
    """The hot-loop regression, pinned directly.

    Every recreate answers BUSYGROUP, so the sweep recovered nothing and the
    read error had some other cause. The shape this replaces retried instantly
    and logged nothing: 33,746 reads/s, 0 records, 0 log lines in production
    (#741). Every read must now be paired with the backoff, which bounds the
    loop at 1/backoff reads per second.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(group_states={"s:a": "existed", "s:b": "existed"})
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 3)

    assert set(sleeps) == {_BACKOFF}
    assert len(sleeps) == redis.xreadgroup_calls
    assert _audit_records(caplog, "consumer_group_recovered") == []
    assert redis.created  # but it did sweep both streams
    errors = _read_error_logs(caplog)
    assert len(errors) == 1
    assert errors[0].levelno == logging.ERROR
    assert errors[0].exc_info is not None


@pytest.mark.asyncio
async def test_vanished_read_with_one_failed_recreate_backs_off_and_logs(
    monkeypatch, caplog
):
    """A failure anywhere in the sweep loses the fast path for the whole read.

    ``s:a`` was recreated, but ``s:b`` could not be — and the two are read
    together, so retrying immediately would fail on ``s:b`` again. This is the
    case ``any(created)`` alone would get wrong.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(group_states={"s:a": "created", "s:b": "failed"})
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 3)

    assert set(sleeps) == {_BACKOFF}
    assert len(sleeps) == redis.xreadgroup_calls
    assert _audit_records(caplog, "consumer_group_ensure_failed")
    assert len(_read_error_logs(caplog)) == 1


@pytest.mark.asyncio
async def test_unblocked_vanished_stream_recovers_like_nogroup(monkeypatch, caplog):
    """The blocking read's own failure shape must reach recovery too.

    A key carrying a TTL can expire while this client is already parked in
    XREADGROUP; Redis answers UNBLOCKED rather than NOGROUP for that, and the
    NOGROUP-only predicate would have sent it to the generic error path.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(
        group_states={"s:a": "created", "s:b": "existed"},
        read_error=_UNBLOCKED,
        read_fails_forever=False,
        batches=[("s:a", [(b"9-0", {})])],
    )
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: stage.handled)

    assert stage.handled == [("s:a", b"9-0")]
    assert _BACKOFF not in sleeps
    assert _audit_records(caplog, "consumer_group_recovered")
    assert _read_error_logs(caplog) == []


@pytest.mark.asyncio
async def test_client_unblock_is_not_treated_as_a_vanished_stream(monkeypatch, caplog):
    """An operator's CLIENT UNBLOCK is not a missing group; do not recreate."""
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(
        group_states={"s:a": "created", "s:b": "created"},
        read_error=_CLIENT_UNBLOCK,
    )
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 3)

    # only the two startup creates; the error path never swept the groups
    assert redis.created == [
        ("s:a", "g", "0", True),
        ("s:b", "g", "0", True),
    ]
    assert set(sleeps) == {_BACKOFF}
    assert len(_read_error_logs(caplog)) == 1


@pytest.mark.asyncio
async def test_pending_claim_records_a_failed_recovery_without_taking_the_backoff(
    caplog,
):
    """The per-stream claim path stays outcome-independent, and stays observable.

    ``_claim_pending_messages`` returns ``[]`` whatever the recovery answered
    and lets the caller's XREADGROUP decide — it is not a hot loop, so it must
    not grow a backoff. What it must not do is go quiet: a recreate that cannot
    run is already on the record at WARNING, with the traceback.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")

    class _NoGroupClaimRedis(_RecoveryRedis):
        async def xautoclaim(self, stream, *_args, **_kwargs):
            self.xautoclaim_calls.append(stream)
            raise RuntimeError(_NOGROUP)

    redis = _NoGroupClaimRedis(
        group_states={"s:a": "failed", "s:b": "failed"},
        read_fails_forever=False,
    )
    stage = _stage(
        redis,
        pending_retry_idle_ms=0,
        xreadgroup_error_sleep_seconds=_BACKOFF,
    )

    claimed = await stage._claim_pending_messages("s:a")

    assert claimed == []
    assert stage._pending_claim_start_ids["s:a"] == "0-0"
    assert len(_audit_records(caplog, "consumer_group_ensure_failed")) == 1
    assert [
        r.levelno
        for r in caplog.records
        if "consumer_group_ensure_failed" in r.getMessage()
    ] == [logging.WARNING]
