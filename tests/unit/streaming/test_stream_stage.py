"""Unit tests for shared.streaming.stage.StreamStage (consume loop)."""

from __future__ import annotations

import asyncio
import logging
import shlex
import time

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
        self.group_created_calls: list[tuple] = []
        self.acked: list[bytes] = []
        self.xreadgroup_calls = 0
        self.xautoclaim_calls = 0

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.group_created = (stream, group, id, mkstream)
        self.group_created_calls.append(self.group_created)

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
            for token in shlex.split(record.getMessage())
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
async def test_audit_log_for_acked_message_requires_successful_xack(caplog):
    class FailingAckRedis(FakeRedis):
        async def xack(self, _stream, _group, _msg_id):
            raise ConnectionError("xack down")

    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = FailingAckRedis([[(b"1-0", {b"signal_id": b"sig-xack"})]])
    stage = _stage(redis, ack_result=True)

    task = asyncio.create_task(stage.run())
    with pytest.raises(ConnectionError):
        await asyncio.wait_for(task, timeout=1.0)

    assert _audit_records(caplog, "stream_message_processed") == []
    records = _audit_records(caplog, "stream_message_ack_failed")
    assert len(records) == 1
    assert records[0]["stream"] == "s:in"
    assert records[0]["consumer_group"] == "g"
    assert records[0]["worker_id"] == "w"
    assert records[0]["msg_id"] == "1-0"
    assert records[0]["signal_id"] == "sig-xack"


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
async def test_reclaimed_pending_audit_log_marks_claimed_true(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    redis = fakeredis.aioredis.FakeRedis(db=1)
    msg_id = await redis.xadd("s:in", {"signal_id": "sig-claimed"})
    await redis.xgroup_create("s:in", "g", id="0")
    await redis.xreadgroup(
        groupname="g", consumername="old-worker", streams={"s:in": ">"}, count=1
    )

    stage = _stage(redis, pending_retry_idle_ms=0)
    await _run_briefly(stage)

    records = _audit_records(caplog, "stream_message_processed")
    assert len(records) == 1
    assert records[0]["msg_id"] == msg_id.decode("utf-8")
    assert records[0]["claimed"] == "true"
    assert records[0]["ack"] == "true"
    assert records[0]["signal_id"] == "sig-claimed"


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
async def test_xreadgroup_nogroup_recreates_group_and_processes_existing_message():
    class MissingGroupRedis(FakeRedis):
        def __init__(self):
            super().__init__([[(b"9-0", {})]])
            self._raised = False

        async def xreadgroup(self, **kw):
            self.xreadgroup_calls += 1
            if not self._raised:
                self._raised = True
                raise RuntimeError("NOGROUP No such key 's:in' or consumer group 'g'")
            return await super().xreadgroup(**kw)

    redis = MissingGroupRedis()
    stage = _stage(redis, xreadgroup_error_sleep_seconds=0.0)

    await _run_briefly(stage)

    assert redis.group_created_calls == [
        ("s:in", "g", "0", True),
        ("s:in", "g", "0", True),
    ]
    assert stage.handled == [b"9-0"]


@pytest.mark.asyncio
async def test_xreadgroup_error_logs_again_after_success(caplog):
    class ErrorSuccessErrorRedis(FakeRedis):
        def __init__(self):
            super().__init__([[(b"9-0", {})]])
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


# --------------------------------------------------------------------------- #
# Vanished-stream recovery: the three-way rule (#741, ported from the monitors)
# --------------------------------------------------------------------------- #

_BACKOFF = 0.25  # distinctive, so a recorded sleep says which path was taken
_NOGROUP = "NOGROUP No such key 's:in' or consumer group 'g' in XREADGROUP"
_UNBLOCKED = "UNBLOCKED the stream key no longer exists"
_CLIENT_UNBLOCK = "UNBLOCKED client unblocked via CLIENT UNBLOCK"


class _RecoveryRedis(FakeRedis):
    """XREADGROUP fails with a scripted error; XGROUP CREATE answers on demand.

    ``group_state`` is what each recreate reports:
    ``"created"`` (the group really was gone), ``"existed"`` (BUSYGROUP —
    nothing was missing after all), or ``"failed"`` (the recreate itself cannot
    run: ACL, or eviction racing it).
    """

    def __init__(
        self,
        *,
        group_state: str,
        read_error: str = _NOGROUP,
        read_fails_forever: bool = True,
        batches=None,
    ) -> None:
        super().__init__(batches or [])
        self.group_state = group_state
        self.read_error = read_error
        self.read_fails_forever = read_fails_forever
        self._read_failed = False

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.group_created_calls.append((stream, group, id, mkstream))
        self.group_created = (stream, group, id, mkstream)
        if self.group_state == "existed":
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")
        if self.group_state == "failed":
            raise RuntimeError("NOPERM this user has no permissions to run 'xgroup'")

    async def xreadgroup(self, **kwargs):
        if self.read_fails_forever or not self._read_failed:
            self._read_failed = True
            self.xreadgroup_calls += 1
            raise RuntimeError(self.read_error)
        return await super().xreadgroup(**kwargs)


# Bound before any test can monkeypatch ``asyncio.sleep``, so the driver below
# keeps a way to yield that the recorder does not see.
_REAL_SLEEP = asyncio.sleep


def _record_sleeps(monkeypatch) -> list[float]:
    """Replace ``asyncio.sleep`` with a recorder that never actually waits.

    The recorded durations are the observable difference between the two paths:
    ``0`` is the fast retry a genuine recreate earns, ``_BACKOFF`` is the
    rate-limited error path. A hot loop shows up as a list with no backoff in it.
    """
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
async def test_vanished_read_that_recreated_the_group_retries_without_backoff(
    monkeypatch, caplog
):
    """A recreate that really happened earns the immediate retry.

    This is the one outcome where skipping the backoff is right: the next read
    now has a reason to succeed.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(
        group_state="created",
        read_fails_forever=False,
        batches=[[(b"9-0", {})]],
    )
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: stage.handled)

    assert stage.handled == [b"9-0"]
    assert _BACKOFF not in sleeps
    assert _read_error_logs(caplog) == []
    assert _audit_records(caplog, "consumer_group_recovered")


@pytest.mark.asyncio
async def test_vanished_read_with_group_already_present_backs_off_instead_of_spinning(
    monkeypatch, caplog
):
    """The hot-loop regression, pinned directly.

    A read that keeps reporting a vanished stream while the group is already
    there recovers nothing, so the read error had some other cause. The shape
    this replaces retried instantly and logged nothing: 33,746 reads/s, 0
    records, 0 log lines in production (#741). Every read must now be paired
    with the backoff, which bounds the loop at 1/backoff reads per second.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(group_state="existed")
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 3)

    # every failing read paid the backoff; none took the zero-sleep fast path
    assert set(sleeps) == {_BACKOFF}
    assert len(sleeps) == redis.xreadgroup_calls
    # nothing was recovered, so nothing may claim a recreate
    assert _audit_records(caplog, "consumer_group_recovered") == []
    assert redis.group_created_calls  # but it did try
    # and the operator sees the read error, once, rate-limited
    errors = _read_error_logs(caplog)
    assert len(errors) == 1
    assert errors[0].levelno == logging.ERROR
    assert errors[0].exc_info is not None


@pytest.mark.asyncio
async def test_vanished_read_with_failed_recreate_backs_off_and_logs(
    monkeypatch, caplog
):
    """A recreate that could not run must not buy an immediate retry either."""
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(group_state="failed")
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 3)

    assert set(sleeps) == {_BACKOFF}
    assert len(sleeps) == redis.xreadgroup_calls
    assert _audit_records(caplog, "consumer_group_recovered") == []
    assert _audit_records(caplog, "consumer_group_ensure_failed")
    assert len(_read_error_logs(caplog)) == 1


@pytest.mark.asyncio
async def test_unblocked_vanished_stream_recovers_like_nogroup(monkeypatch, caplog):
    """The blocking read's own failure shape must reach recovery too.

    All five live consumers read a stream carrying a 24h TTL and block for 2s,
    so the key can expire while this client is already parked in XREADGROUP.
    Redis answers UNBLOCKED rather than NOGROUP for that, and the NOGROUP-only
    predicate would have sent it to the generic error path.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(
        group_state="created",
        read_error=_UNBLOCKED,
        read_fails_forever=False,
        batches=[[(b"9-0", {})]],
    )
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: stage.handled)

    assert stage.handled == [b"9-0"]
    assert _BACKOFF not in sleeps
    assert _audit_records(caplog, "consumer_group_recovered")
    assert _read_error_logs(caplog) == []


@pytest.mark.asyncio
async def test_client_unblock_is_not_treated_as_a_vanished_stream(monkeypatch, caplog):
    """An operator's CLIENT UNBLOCK is not a missing group; do not recreate."""
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")
    redis = _RecoveryRedis(group_state="created", read_error=_CLIENT_UNBLOCK)
    stage = _stage(redis, xreadgroup_error_sleep_seconds=_BACKOFF)
    sleeps = _record_sleeps(monkeypatch)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 3)

    # only the one startup create; the error path never swept the group
    assert redis.group_created_calls == [("s:in", "g", "0", True)]
    assert set(sleeps) == {_BACKOFF}
    assert len(_read_error_logs(caplog)) == 1


@pytest.mark.asyncio
async def test_pending_claim_records_a_failed_recovery_without_taking_the_backoff(
    caplog,
):
    """The claim path stays outcome-independent, and stays observable.

    ``_claim_pending_messages`` returns ``[]`` whatever the recovery answered
    and lets the caller's XREADGROUP decide — it is not a hot loop, so it must
    not grow a backoff. What it must not do is go quiet: a recreate that cannot
    run is already on the record at WARNING, with the traceback.
    """
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")

    class _NoGroupClaimRedis(_RecoveryRedis):
        async def xautoclaim(self, *_args, **_kwargs):
            self.xautoclaim_calls += 1
            raise RuntimeError(_NOGROUP)

    redis = _NoGroupClaimRedis(group_state="failed")
    stage = _stage(
        redis,
        pending_retry_idle_ms=0,
        xreadgroup_error_sleep_seconds=_BACKOFF,
    )

    claimed = await stage._claim_pending_messages()

    assert claimed == []
    assert stage._pending_claim_start_id == "0-0"
    failures = _audit_records(caplog, "consumer_group_ensure_failed")
    assert len(failures) == 1
    assert [
        r.levelno
        for r in caplog.records
        if "consumer_group_ensure_failed" in r.getMessage()
    ] == [logging.WARNING]
