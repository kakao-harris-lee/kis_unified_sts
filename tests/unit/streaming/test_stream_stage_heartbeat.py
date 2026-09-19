"""Liveness heartbeat for the shared consumer-group stages.

A consumer that is alive but idle used to emit nothing at any log level
(``xreadgroup`` -> no messages -> ``post_poll(0)`` -> ``sleep(0)`` ->
``continue``), so a quiet session and a dead daemon left identical logs. These
tests pin the line that tells them apart, and the three properties that make it
worth trusting: it fires on the *idle* path, it survives a subclass that
overrides ``post_poll``, and no supplier of the interval — YAML, env, or a
service's own call site — can push it past the gap bound
``scripts/ops/f9_observation_harvest.py`` scores against.

Time is injected, never slept: the clock is stepped by the fake Redis at a
chosen poll, so "one interval elapsed" is an exact fact rather than a wall-clock
race (the failure mode #592 recorded).
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import time

import pytest

import scripts.ops.f9_observation_harvest as harvest
from shared.streaming.stage import (
    MAX_HEARTBEAT_INTERVAL_SECONDS,
    MultiStreamStage,
    StreamStage,
    StreamStageConfig,
    _LivenessHeartbeat,
)

_INTERVAL = 60.0

_REAL_SLEEP = asyncio.sleep


class _Clock:
    """A clock that only moves when a test moves it."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeRedis:
    """Idle-by-default consume loop double that can step the clock.

    ``advance_before_call`` is the XREADGROUP call number that finishes one
    heartbeat interval. Every later poll reads the same instant, so a test can
    assert an exact heartbeat count however many extra loop turns the event
    loop fits in before ``stop()`` lands.
    """

    def __init__(
        self,
        batches: list[list[tuple[bytes, dict[bytes, bytes]]]] | None = None,
        *,
        clock: _Clock | None = None,
        advance_before_call: int | None = None,
        advance_by: float = _INTERVAL,
        claimed_batches: list[list[tuple[bytes, dict[bytes, bytes]]]] | None = None,
    ) -> None:
        self._batches = list(batches or [])
        self._claimed_batches = list(claimed_batches or [])
        self._clock = clock
        self._advance_before_call = advance_before_call
        self._advance_by = advance_by
        self.acked: list[bytes] = []
        self.xreadgroup_calls = 0

    async def xgroup_create(self, _stream, _group, id="0", mkstream=False):
        return None

    async def xreadgroup(self, *, streams, **_kwargs):
        self.xreadgroup_calls += 1
        if (
            self._clock is not None
            and self.xreadgroup_calls == self._advance_before_call
        ):
            self._clock.advance(self._advance_by)
        if self._batches:
            stream_key = next(iter(streams))
            return [(stream_key, self._batches.pop(0))]
        await _REAL_SLEEP(0)
        return []

    async def xautoclaim(self, *_args, **_kwargs):
        if self._claimed_batches:
            return [b"0-0", self._claimed_batches.pop(0), []]
        return [b"0-0", [], []]

    async def xack(self, _stream, _group, msg_id):
        self.acked.append(msg_id)


class _Stage(StreamStage):
    async def handle_message(self, _msg_id, _fields):
        return True


class _MultiStage(MultiStreamStage):
    async def handle_message(self, _stream, _msg_id, _fields):
        return True


def _stage(redis, clock, cls=_Stage, **kwargs):
    params = {
        "redis": redis,
        "input_stream": "s:in",
        "consumer_group": "g",
        "worker_id": "w",
        "xread_block_ms": 5,
        "batch_size": 10,
        "heartbeat_interval_seconds": _INTERVAL,
        "heartbeat_clock": clock,
    }
    params.update(kwargs)
    return cls(**params)


def _multi_stage(redis, clock, **kwargs):
    params = {
        "redis": redis,
        "input_streams": ["s:a", "s:b"],
        "consumer_group": "g",
        "worker_id": "w",
        "xread_block_ms": 5,
        "batch_size": 10,
        "heartbeat_interval_seconds": _INTERVAL,
        "heartbeat_clock": clock,
    }
    params.update(kwargs)
    return _MultiStage(**params)


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


def _heartbeats(caplog) -> list[dict[str, str]]:
    return _audit_records(caplog, "stream_consumer_alive")


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


# --------------------------------------------------------------------------- #
# The loop: where the heartbeat fires
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_idle_loop_emits_heartbeat_proving_liveness_without_traffic(caplog):
    """The case with no other evidence: polling, consuming nothing, alive."""
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    redis = FakeRedis(clock=clock, advance_before_call=2)
    stage = _stage(redis, clock)

    await _drive_until(stage, lambda: _heartbeats(caplog))

    records = _heartbeats(caplog)
    assert len(records) == 1
    assert records[0]["streams"] == "s:in"
    assert records[0]["consumer_group"] == "g"
    assert records[0]["worker_id"] == "w"
    assert records[0]["messages"] == "0"
    assert records[0]["polls"] == "2"
    # Nothing was ever consumed, so there is no honest "idle since" instant.
    assert "seconds_since_delivery" not in records[0]


@pytest.mark.asyncio
async def test_message_path_heartbeat_reports_what_was_consumed(caplog):
    """A busy interval carries the real count, not just ``polls``."""
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    redis = FakeRedis(
        [[(b"1-0", {}), (b"2-0", {})]],
        clock=clock,
        advance_before_call=2,
    )
    stage = _stage(redis, clock)

    await _drive_until(stage, lambda: _heartbeats(caplog))

    records = _heartbeats(caplog)
    assert len(records) == 1
    assert records[0]["messages"] == "2"
    assert records[0]["polls"] == "2"
    assert records[0]["seconds_since_delivery"] == str(int(_INTERVAL))


@pytest.mark.asyncio
async def test_heartbeat_reports_delivery_not_successful_processing(caplog):
    """A handler that leaves messages pending still counts as delivery.

    ``handle_message`` returning ``False`` is the supported "transient failure,
    leave it pending for retry" contract, and the counts here are taken before
    the handler runs. That is deliberate: this line claims the loop turned and
    Redis answered — which it did — not that work completed. Progress has its
    own evidence (``stream_message_processed`` / ``stream_message_failed`` and
    the pending-entry list a stuck handler grows).
    """
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")

    class _NeverAcks(_Stage):
        async def handle_message(self, _msg_id, _fields):
            return False

    clock = _Clock()
    redis = FakeRedis([[(b"1-0", {})]], clock=clock, advance_before_call=2)
    stage = _stage(redis, clock, cls=_NeverAcks)

    await _drive_until(stage, lambda: _heartbeats(caplog))

    records = _heartbeats(caplog)
    assert records[0]["messages"] == "1"
    assert records[0]["seconds_since_delivery"] == str(int(_INTERVAL))
    assert redis.acked == []  # nothing progressed; delivery is what is claimed


@pytest.mark.asyncio
async def test_reclaimed_pending_poll_counts_toward_the_heartbeat(caplog):
    """The XAUTOCLAIM path is a loop turn too, and says so."""
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    redis = FakeRedis(
        clock=clock,
        advance_before_call=1,
        claimed_batches=[[(b"1-0", {})]],
    )
    stage = _stage(redis, clock, pending_retry_idle_ms=0)

    await _drive_until(stage, lambda: _heartbeats(caplog))

    records = _heartbeats(caplog)
    assert len(records) == 1
    assert records[0]["messages"] == "1"


@pytest.mark.asyncio
async def test_heartbeat_survives_a_subclass_that_overrides_post_poll(caplog):
    """``services/news_scorer`` replaces ``post_poll`` without calling super.

    The heartbeat is emitted from ``run()`` precisely so that shape cannot
    delete the liveness evidence — the failure this work exists to prevent.
    """
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")

    class _NewsScorerShaped(_Stage):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.post_poll_counts: list[int] = []

        async def post_poll(self, message_count: int) -> None:
            # Verbatim shape of services/news_scorer/main.py: an override that
            # does its own thing and never reaches the base implementation.
            self.post_poll_counts.append(message_count)

    clock = _Clock()
    redis = FakeRedis(clock=clock, advance_before_call=2)
    stage = _stage(redis, clock, cls=_NewsScorerShaped)

    await _drive_until(stage, lambda: _heartbeats(caplog))

    assert len(_heartbeats(caplog)) == 1
    assert stage.post_poll_counts  # the override still ran


@pytest.mark.asyncio
async def test_no_heartbeat_before_the_interval_elapses(caplog):
    """Many polls inside one interval produce no line at all."""
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    redis = FakeRedis(clock=clock)  # clock never moves
    stage = _stage(redis, clock)

    await _drive_until(stage, lambda: redis.xreadgroup_calls >= 5)

    assert _heartbeats(caplog) == []


@pytest.mark.asyncio
async def test_multi_stream_heartbeat_names_every_input_stream(caplog):
    """One XREADGROUP covers all inputs, so all of them are on the record."""
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    redis = FakeRedis(clock=clock, advance_before_call=2)
    stage = _multi_stage(redis, clock)

    await _drive_until(stage, lambda: _heartbeats(caplog))

    records = _heartbeats(caplog)
    assert len(records) == 1
    assert records[0]["streams"] == "s:a,s:b"
    assert records[0]["messages"] == "0"


# --------------------------------------------------------------------------- #
# The primitive: rate limiting and per-interval counts
# --------------------------------------------------------------------------- #


def _heartbeat(clock: _Clock, **kwargs) -> _LivenessHeartbeat:
    params = {
        "consumer_group": "g",
        "worker_id": "w",
        "streams": ("s:in",),
        "interval_seconds": _INTERVAL,
        "clock": clock,
    }
    params.update(kwargs)
    return _LivenessHeartbeat(**params)


def test_first_poll_opens_the_interval_instead_of_emitting(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    beat = _heartbeat(_Clock())

    beat.record_poll(0)

    assert _heartbeats(caplog) == []


def test_at_most_one_heartbeat_per_interval(caplog):
    """Sixty polls in one interval are one line; ten intervals are ten lines."""
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    beat = _heartbeat(clock)

    beat.record_poll(0)
    for _ in range(600):  # one poll a second, ten heartbeat intervals
        clock.advance(1.0)
        beat.record_poll(0)

    records = _heartbeats(caplog)
    assert len(records) == 10
    # Every poll is reported exactly once. The poll that opened the interval
    # lands in the first one, so the counts read 61 then 60 nine times — and
    # they sum to the 601 polls that really happened.
    assert [record["polls"] for record in records] == ["61"] + ["60"] * 9
    assert sum(int(record["polls"]) for record in records) == 601


def test_counts_cover_one_interval_not_the_whole_run(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    beat = _heartbeat(clock)

    beat.record_poll(3)  # opens the interval
    clock.advance(_INTERVAL)
    beat.record_poll(4)  # first line: 2 polls, 7 messages
    clock.advance(_INTERVAL)
    beat.record_poll(0)  # second line: 1 poll, 0 messages

    records = _heartbeats(caplog)
    assert [(r["polls"], r["messages"]) for r in records] == [("2", "7"), ("1", "0")]


def test_seconds_since_delivery_measures_the_silence_since_the_last_message(caplog):
    caplog.set_level(logging.INFO, logger="shared.streaming.stage")
    clock = _Clock()
    beat = _heartbeat(clock)

    beat.record_poll(1)
    clock.advance(_INTERVAL)
    beat.record_poll(0)
    clock.advance(_INTERVAL)
    beat.record_poll(0)

    records = _heartbeats(caplog)
    assert [record["seconds_since_delivery"] for record in records] == ["60", "120"]


def test_default_clock_is_monotonic():
    """The un-injected path is the one that ships, so pin it.

    Every other test here supplies a clock, which means a default of
    ``time.time`` would leave the whole suite green while an NTP step or a DST
    change moved the interval under a live consumer. A heartbeat measures a
    duration; only a monotonic source measures durations.
    """
    beat = _LivenessHeartbeat(
        consumer_group="g",
        worker_id="w",
        streams=("s:in",),
        interval_seconds=_INTERVAL,
    )

    assert beat._clock is time.monotonic


@pytest.mark.parametrize("interval", [0.0, -1.0])
def test_non_positive_interval_is_refused(interval):
    """0 would emit on every poll — thousands of lines a second on a busy stage."""
    with pytest.raises(ValueError, match="heartbeat_interval_seconds"):
        _heartbeat(_Clock(), interval_seconds=interval)


# --------------------------------------------------------------------------- #
# The cross-constraint that binds this knob to the harvester
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "interval",
    [
        MAX_HEARTBEAT_INTERVAL_SECONDS,  # equal is already too loose: real gaps
        MAX_HEARTBEAT_INTERVAL_SECONDS + 1,  # are the interval plus poll jitter
        2400.0,  # the value a service could plausibly configure
    ],
)
def test_interval_at_or_above_the_observation_bound_is_refused(interval):
    """The bound is enforced where every supplier lands, not on the default.

    A service adding ``heartbeat_interval_seconds: 2400`` to its config and
    passing it at its call site would leave the shipped default innocent while
    every healthy quiet day for that service read ``stale_observation``. The
    check lives in ``_LivenessHeartbeat.__init__``, so config, env and a direct
    constructor call are all caught.
    """
    with pytest.raises(ValueError, match="heartbeat_interval_seconds"):
        _heartbeat(_Clock(), interval_seconds=interval)


@pytest.mark.asyncio
async def test_stage_refuses_a_configured_interval_above_the_bound():
    """The seam services actually use is guarded, not just the primitive."""
    with pytest.raises(ValueError, match="heartbeat_interval_seconds"):
        _stage(FakeRedis(), _Clock(), heartbeat_interval_seconds=2400.0)


@pytest.mark.asyncio
async def test_stage_takes_its_default_interval_from_config_not_from_code(monkeypatch):
    """An operator changes this by editing YAML/env, never Python.

    Driven through an env override rather than compared against the shipped
    value: a stage that had quietly gone back to a hardcoded ``60.0`` would
    match the shipped ``60`` and this test would pass while proving nothing.
    A value only config can produce is the one that distinguishes them.
    """
    monkeypatch.setenv("CONSUMER_STAGE_HEARTBEAT_INTERVAL_SECONDS", "90")

    stage = _stage(FakeRedis(), _Clock(), heartbeat_interval_seconds=None)

    assert stage._heartbeat.interval_seconds == 90.0


def test_env_override_reaches_the_configured_interval(monkeypatch):
    """``CONSUMER_STAGE_*`` is the operator's second lever, so prove it works."""
    monkeypatch.setenv("CONSUMER_STAGE_HEARTBEAT_INTERVAL_SECONDS", "90")

    assert StreamStageConfig.load().heartbeat_interval_seconds == 90.0


def test_out_of_bound_config_falls_back_to_the_field_default_with_a_warning(
    monkeypatch, caplog
):
    """A config past the ceiling is refused at the boundary, not obeyed.

    The fallback is deliberate: this knob only governs an observability line, so
    a live consumer must not fail to start over it. The WARNING with its
    traceback is what names the bad value.
    """
    caplog.set_level(logging.WARNING, logger="shared.streaming.stage")
    monkeypatch.setenv("CONSUMER_STAGE_HEARTBEAT_INTERVAL_SECONDS", "2400")

    config = StreamStageConfig.load()

    assert (
        config.heartbeat_interval_seconds
        == StreamStageConfig.model_fields["heartbeat_interval_seconds"].default
    )
    assert config.heartbeat_interval_seconds < MAX_HEARTBEAT_INTERVAL_SECONDS
    assert _audit_records(caplog, "stream_stage_config_load_failed")


def test_configured_interval_stays_under_the_observation_gap_bound():
    """The two knobs have to know about each other, so pin them together.

    ``scripts/ops/f9_observation_harvest.py`` scores a session by the largest
    gap between two proofs and fails a service whose gap exceeds
    ``observation_max_gap_seconds``. A heartbeat interval at or above that bound
    would make healthy quiet sessions read ``stale_observation`` — the heartbeat
    manufacturing the false verdict it was added to remove.

    Three real sources, no literals: the harvester's YAML, this package's code
    ceiling, and the shipped value in ``config/streaming.yaml``. The middle
    assertion is the one that keeps the ceiling honest — it is a copy of the
    harvester's number, and a copy that may not drift upward.

    ``from_yaml()`` rather than ``load()``: the shipped file is what this test
    guards, and ``load()``'s fallback would answer with the field default and
    hide a bad value in the file behind it. Here an out-of-bound file raises.
    """
    max_gap = harvest.load_observation_config().observation_max_gap_seconds
    shipped = StreamStageConfig.from_yaml().heartbeat_interval_seconds

    assert max_gap >= MAX_HEARTBEAT_INTERVAL_SECONDS
    assert shipped < MAX_HEARTBEAT_INTERVAL_SECONDS
