"""Shared Redis consumer-group stage framework.

Extracts the consumer-group loop (XGROUP_CREATE → pending reclaim / XREADGROUP
→ per-message handle → XACK) that news_scorer / risk_filter / order_router each
reimplemented, so every streaming daemon shares one tested loop.

``StreamStage`` handles one input stream. ``MultiStreamStage`` applies the same
contract to several input streams while preserving stream-specific retry and
ACK behavior. Subclasses implement ``handle_message`` (return ``True`` ⇒ the
framework XACKs; ``False`` ⇒ leave the message pending for retry) and may
override the optional hooks ``on_startup`` / ``pre_iteration_gate`` /
``post_poll`` / ``on_shutdown``.

Both loops emit a periodic ``stream_consumer_alive`` heartbeat so that a stage
with no traffic still proves it is running — see :class:`_LivenessHeartbeat`.
That evidence is emitted when a poll *returns*, so ``xread_block_ms`` must be
positive: Redis' ``BLOCK 0`` blocks indefinitely, and an idle stage would then
never come back to say anything. Of the five services only
``services/order_router`` reads that value from config, and its field refuses
``0`` for this reason; the other four pass a literal 2000.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import Any, ClassVar, final

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.streaming.audit import (
    RateLimitedLog,
    decode_stream_id,
    extract_audit_fields,
    format_audit_kv,
)

logger = logging.getLogger(__name__)

#: Mirror of ``config/f9_observation.yaml::observation_max_gap_seconds`` (1800):
#: the largest gap that harvester tolerates between two proofs before it renders
#: a service ``stale_observation``.
#:
#: It lives in code rather than being read from that YAML because a live
#: consumer must not fail to start over an ops harvest config, and because a
#: bound config can raise is not a bound. ``tests/unit/streaming/
#: test_stream_stage_heartbeat.py`` reads both real sources and fails if this
#: copy ever drifts above the harvester's.
#:
#: **This is the gap bound, not the interval ceiling** — see
#: :func:`max_heartbeat_interval_seconds`.
OBSERVATION_MAX_GAP_SECONDS = 1800.0

#: How much a measured gap can exceed the real one, in seconds.
#:
#: ``scripts/ops/f9_observation_harvest.py:769`` parses log timestamps with
#: ``"%Y-%m-%d %H:%M:%S"`` — sub-second parts are dropped — so two lines 1800.4s
#: apart can be stamped 1800 and 1801 and measure as 1801. One second of
#: truncation error is therefore part of the derivation, not padding. (Its
#: comparison at ``:916`` is ``> max_gap_seconds``, so a measured gap of exactly
#: the bound passes, which is why the ceiling below is inclusive.)
TIMESTAMP_RESOLUTION_SECONDS = 1.0


def max_heartbeat_interval_seconds(poll_block_seconds: float) -> float:
    """Largest interval whose worst-case *measured gap* still clears the bound.

    The harvester measures the gap between two emitted lines, not the configured
    interval, and those are not the same number:

    - a heartbeat becomes due *during* a poll and is emitted only when the next
      poll returns, so an idle loop adds a full ``xread_block_ms`` wait, and
    - the measurement itself can round up by :data:`TIMESTAMP_RESOLUTION_SECONDS`.

    An interval of 1799 with the shipped 2s block produces gaps measuring ~1801
    — over the bound, and ``stale_observation`` on a healthy day, which is the
    exact false verdict this heartbeat exists to delete.

    **Why the block is the only wait worth subtracting.** A busy loop also
    spends handler time before the next poll returns, and arithmetically that
    can exceed the bound (ten handlers at 0.5s add 5s: 1797 + 2 + 5 = 1804).
    It cannot move the *verdict*, because a loop busy enough for handler time
    to matter is emitting ``stream_message_processed`` per message — the
    harvester's proof of consumption — right after each handler returns, so the
    long interval is filled with proofs throughout. A long gap requires no
    traffic, and a loop with no traffic spends its time in exactly one place:
    the block this subtracts.
    """
    return (
        OBSERVATION_MAX_GAP_SECONDS - poll_block_seconds - TIMESTAMP_RESOLUTION_SECONDS
    )


class StreamStageConfig(ServiceConfigBase):
    """Consume-loop knobs, from ``config/streaming.yaml`` section ``consumer_stage``.

    Same shape as :class:`shared.streaming.approval_gate.ApprovalGateConfig` in
    this package: a ``ServiceConfigBase`` with a file, a section and an env
    prefix, so an operator changes behaviour by editing YAML or setting
    ``CONSUMER_STAGE_*`` — never by editing Python (CLAUDE.md:
    configuration-driven only).

    The stage constructors keep ``heartbeat_interval_seconds`` as a parameter,
    so a service that wants its own value still injects one; this supplies the
    default when it does not.
    """

    _default_config_file: ClassVar[str] = "streaming.yaml"
    _default_section: ClassVar[str] = "consumer_stage"
    _env_prefix: ClassVar[str] = "CONSUMER_STAGE_"

    # `lt` is the coarse bound: a config cannot know a stage's xread_block_ms,
    # so the exact per-stage ceiling (gap bound minus that block) is enforced
    # where the value lands, in _LivenessHeartbeat.__init__. This catches the
    # obviously-wrong value at the boundary; that catches the subtly-wrong one.
    heartbeat_interval_seconds: float = Field(
        default=60.0,
        gt=0,
        lt=OBSERVATION_MAX_GAP_SECONDS,
        description=(
            "Seconds between stream_consumer_alive heartbeats. The observed gap "
            "is this plus one poll block, and must clear "
            "config/f9_observation.yaml::observation_max_gap_seconds."
        ),
    )

    @classmethod
    def load(cls) -> StreamStageConfig:
        """Load the section, falling back to field defaults with a WARNING.

        Deliberately not ``from_yaml()`` bare: this knob only governs an
        observability line, and refusing to start a live consumer because an
        ops file is missing or holds a bad value would be a worse failure than
        the one it guards. The WARNING carries the traceback, so a typo is
        named rather than swallowed.
        """
        try:
            return cls.from_yaml(apply_env_overrides=True)
        except Exception:
            logger.warning(
                format_audit_kv(
                    event="stream_stage_config_load_failed",
                    config_file=cls._default_config_file,
                    section=cls._default_section,
                ),
                exc_info=True,
            )
            return cls()


def _resolve_heartbeat_interval(
    explicit_seconds: float | None,
    *,
    poll_block_seconds: float,
    consumer_group: str,
) -> float:
    """Pick the interval a stage will use, clamping an *ops* value if needed.

    Two sources, two failure kinds, two answers:

    - **Explicitly passed** (a service supplying its own value in code): left
      exactly as given, so ``_LivenessHeartbeat`` raises on an out-of-range one.
      That is a programming error, and it should stop a test, not a session.
    - **From YAML or env**: clamped to the ceiling with a WARNING, never raised.
      This knob governs one observability line, so killing a live consumer over
      it would be a worse failure than the one the bound guards — the same
      reason :meth:`StreamStageConfig.load` degrades instead of raising. The
      bound added to close the 1799 hole must not reintroduce, through the
      operator lever it ships with, the crash that policy exists to prevent.

    A poll block so large that no positive interval fits (>= ~1799s) is left to
    raise, and — this is the part worth stating — it is left to raise *without*
    a clamp line. There is no honest value to clamp to there: the ceiling is
    zero or negative, so the line would advertise applying an interval that
    cannot be applied and is not even positive. A log that lies on a path nobody
    takes is still a log that lies, which is the whole premise of this file. The
    wrong knob in that case is the block, and the exception says so.
    """
    if explicit_seconds is not None:
        return explicit_seconds

    configured = StreamStageConfig.load().heartbeat_interval_seconds
    ceiling = max_heartbeat_interval_seconds(poll_block_seconds)
    if configured <= ceiling or ceiling <= 0:
        return configured

    logger.warning(
        format_audit_kv(
            event="heartbeat_interval_clamped",
            consumer_group=consumer_group,
            configured_seconds=configured,
            clamped_seconds=ceiling,
            poll_block_seconds=poll_block_seconds,
            observation_max_gap_seconds=OBSERVATION_MAX_GAP_SECONDS,
        )
    )
    return ceiling


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _is_busygroup_error(exc: Exception) -> bool:
    return "busygroup" in str(exc).lower()


def is_missing_consumer_group_error(exc: Exception) -> bool:
    """Whether ``exc`` is Redis' NOGROUP — the stream key or the group is gone.

    Redis answers NOGROUP both when the consumer group was never created and
    when the stream key itself expired, so a consumer that reads an expiring
    stream must treat it as a recoverable condition, not a read failure.
    """
    return "nogroup" in str(exc).lower()


def is_vanished_stream_read_error(exc: Exception) -> bool:
    """Whether ``exc`` says the stream read failed because its key vanished.

    Two Redis error codes report that one condition. NOGROUP comes back when
    the key or the group is already gone at call time; ``UNBLOCKED the stream
    key no longer exists`` is what a client *already blocked* in XREADGROUP
    gets when the key disappears underneath it — which is how each episode on
    the monitor daemons starts. The unrelated ``UNBLOCKED client unblocked via
    CLIENT UNBLOCK`` is deliberately excluded: that is an operator action, not
    a vanished key.

    **Which code you get is version-dependent, so both arms must stay.**
    Measured against a blocking XREADGROUP whose key vanishes underneath it::

        vanish mode      7.0.15 (this deployment)   7.4.9
        DEL              UNBLOCKED                  NOGROUP
        TTL expiry       UNBLOCKED                  NOGROUP
        type change      UNBLOCKED                  NOGROUP
        XGROUP DESTROY   NOGROUP                    NOGROUP

    The consumers run against the host Redis (``REDIS_HOST`` is
    ``host.docker.internal`` in the deployed stack), which is 7.0.15, so three
    of those four modes are carried *only* by the UNBLOCKED arm today. Redis
    7.2+ collapsed the condition into the ordinary NOGROUP message — the
    compose-internal ``redis:7-alpine`` already resolves to 7.4.9 — so after a
    host upgrade or a rewiring the NOGROUP arm becomes the only cover. Drop
    either arm and a vanish mode goes unhandled on one version or the other.

    Sibling of :func:`is_missing_consumer_group_error` rather than a widening
    of it, because only a *blocking* call can be interrupted mid-read and see
    the UNBLOCKED shape. That is the entire restriction — one blocking call
    site reaches both shapes (on 7.0.15, XGROUP DESTROY under the block gives
    NOGROUP while an expiring key gives UNBLOCKED) — so this predicate belongs
    on every ``block=``-bearing XREADGROUP, while XAUTOCLAIM, which never
    blocks, stays on the narrow sibling.
    """
    if is_missing_consumer_group_error(exc):
        return True
    message = str(exc).lower()
    return "unblocked" in message and "no longer exists" in message


class ConsumerGroupEnsure(StrEnum):
    """Outcome of one XGROUP CREATE attempt.

    ``CREATED`` and ``EXISTED`` both leave the group usable, but only the first
    means something was actually missing — collapsing them into one ``True``
    is what made the recovery log claim a recreate on healthy streams, and what
    let a caller retry immediately after recovering nothing.

    Every member is a truthy non-empty string, so ``all(...)`` over these is a
    trap. Compare with ``is``; the ``__bool__`` below exists only so a caller
    who writes ``if not await recover_missing_consumer_group(...)`` still gets
    the honest answer instead of a silently-always-false condition.
    """

    CREATED = "created"
    EXISTED = "existed"
    FAILED = "failed"

    def __bool__(self) -> bool:
        return self is not ConsumerGroupEnsure.FAILED


async def _ensure_consumer_group(
    redis: Any,
    stream: str | bytes,
    consumer_group: str,
) -> ConsumerGroupEnsure:
    try:
        await redis.xgroup_create(stream, consumer_group, id="0", mkstream=True)
        return ConsumerGroupEnsure.CREATED
    except Exception as exc:
        if _is_busygroup_error(exc):
            return ConsumerGroupEnsure.EXISTED
        logger.warning(
            format_audit_kv(
                event="consumer_group_ensure_failed",
                stream=decode_stream_id(stream),
                consumer_group=consumer_group,
            ),
            exc_info=True,
        )
        return ConsumerGroupEnsure.FAILED


async def recover_missing_consumer_group(
    redis: Any,
    stream: str | bytes,
    consumer_group: str,
) -> ConsumerGroupEnsure:
    """Recreate a vanished stream/group (``mkstream``) and log what happened.

    Returns the outcome rather than a bool, because a caller that sweeps every
    stream it reads has to tell "I recreated something" from "nothing was
    missing after all" — the second means the read error had another cause, so
    retrying immediately would spin. Safe to call on a stream whose group never
    went missing, and only the genuine recreate is logged at WARNING.
    """
    ensured = await _ensure_consumer_group(redis, stream, consumer_group)
    if ensured is ConsumerGroupEnsure.CREATED:
        logger.warning(
            format_audit_kv(
                event="consumer_group_recovered",
                stream=decode_stream_id(stream),
                consumer_group=consumer_group,
            )
        )
    elif ensured is ConsumerGroupEnsure.EXISTED:
        # Not an incident: the caller swept a healthy sibling stream, so this
        # stays below the operator's log at the shipped LOG_LEVEL=INFO. Every
        # daemon entrypoint honours LOG_LEVEL (#751, via
        # shared.observability.logging_setup.configure_logging), so surfacing
        # this line is a compose env change, not a code edit and image rebuild.
        # What the daemons actually act on is the returned outcome, not this
        # record.
        logger.debug(
            format_audit_kv(
                event="consumer_group_already_present",
                stream=decode_stream_id(stream),
                consumer_group=consumer_group,
            )
        )
    return ensured


async def sweep_vanished_consumer_groups(
    redis: Any,
    streams: Iterable[str | bytes],
    consumer_group: str,
) -> bool:
    """Recreate the groups a failed read covers; say whether to retry at once.

    A caller that reads several streams in one XREADGROUP fails as a unit, so
    recovery has to sweep all of them (``mkstream`` recreates whichever key
    vanished). The return value is the three-way rule #741 arrived at:

    - something was actually ``CREATED`` and nothing ``FAILED`` → ``True``.
      The next read has a reason to succeed, so the caller skips its backoff.
    - any ``FAILED`` → ``False``. An immediate retry would fail the same way.
    - every group already ``EXISTED`` → ``False``. Nothing was recovered, so
      the read error was not a vanished group after all and the caller must
      fall through to its rate-limited error log and backoff.

    That last case is the one worth stating plainly, because getting it wrong
    is silent: retrying with no backoff and no log measured 33,746 reads/s,
    0 records and 0 log lines in production.

    Compare the outcomes with ``is``. ``ConsumerGroupEnsure`` is a ``StrEnum``
    whose members are all non-empty — therefore truthy — strings, so
    ``all(outcomes)`` and ``if outcome:`` are always true and would restore
    that hot loop while looking like a check.
    """
    outcomes = [
        await recover_missing_consumer_group(redis, stream, consumer_group)
        for stream in streams
    ]
    created = any(outcome is ConsumerGroupEnsure.CREATED for outcome in outcomes)
    failed = any(outcome is ConsumerGroupEnsure.FAILED for outcome in outcomes)
    return created and not failed


def _log_processed_message(
    *,
    stream: str | bytes,
    consumer_group: str,
    worker_id: str,
    msg_id: bytes,
    fields: dict[bytes, bytes],
    ack: bool,
    claimed: bool,
    duration_ms: int,
) -> None:
    logger.info(
        format_audit_kv(
            event="stream_message_processed",
            stream=decode_stream_id(stream),
            consumer_group=consumer_group,
            worker_id=worker_id,
            msg_id=decode_stream_id(msg_id),
            ack=ack,
            claimed=claimed,
            duration_ms=duration_ms,
            **extract_audit_fields(fields),
        )
    )


def _log_failed_message(
    *,
    stream: str | bytes,
    consumer_group: str,
    worker_id: str,
    msg_id: bytes,
    fields: dict[bytes, bytes],
    claimed: bool,
    duration_ms: int,
) -> None:
    logger.error(
        format_audit_kv(
            event="stream_message_failed",
            stream=decode_stream_id(stream),
            consumer_group=consumer_group,
            worker_id=worker_id,
            msg_id=decode_stream_id(msg_id),
            claimed=claimed,
            duration_ms=duration_ms,
            **extract_audit_fields(fields),
        )
    )


def _log_ack_failed_message(
    *,
    stream: str | bytes,
    consumer_group: str,
    worker_id: str,
    msg_id: bytes,
    fields: dict[bytes, bytes],
    claimed: bool,
    duration_ms: int,
) -> None:
    logger.error(
        format_audit_kv(
            event="stream_message_ack_failed",
            stream=decode_stream_id(stream),
            consumer_group=consumer_group,
            worker_id=worker_id,
            msg_id=decode_stream_id(msg_id),
            claimed=claimed,
            duration_ms=duration_ms,
            **extract_audit_fields(fields),
        ),
        exc_info=True,
    )


class _LivenessHeartbeat:
    """Periodic proof that a consume loop is still turning.

    The idle path of a consumer — read, no messages, ``continue`` — emitted
    nothing at any log level, so "healthy but no traffic" and "the consume task
    died hours ago" were the same log: empty. That is how both monitor daemons
    went two days blind (2026-09-17/18) with ``RestartCount=0``, and it is why
    a quiet session harvests as ``PARTIAL`` today. ``LOG_LEVEL=DEBUG`` does not
    help — the gap is in the code path, not the level — so this is INFO:
    evidence, not diagnostics.

    ``polls`` and ``messages`` are both carried because they answer different
    questions. ``polls>0 messages=0`` is "alive, watching, no traffic"; no line
    at all is the alarm, since a loop that is not turning cannot emit one.
    ``polls`` counts *completed* reads only — a failing read never reaches here
    and has its own rate-limited error line, so a heartbeat never launders one.

    **Every count here is about delivery, not about progress.** ``messages``
    and ``seconds_since_delivery`` are recorded when Redis hands this worker
    entries, before ``handle_message`` runs, so a handler that keeps returning
    ``False`` — the supported "transient failure, leave it pending" contract —
    still counts as delivery and still resets the delivery clock. A handler
    stuck that way has the *same* ``msg_id`` redelivered by XAUTOCLAIM every
    ``pending_retry_idle_ms``, and each redelivery counts again, so a wedged
    consumer can sit at ``messages=1 seconds_since_delivery=0`` indefinitely
    with nothing acked. That is deliberate for a *liveness* signal: the loop
    did turn and Redis did answer, which is exactly the claim being made.
    Whether the work succeeded is a different claim with its own evidence
    (``stream_message_processed`` per message, ``stream_message_failed`` on
    error, and the pending-entry list a stuck handler grows). A heartbeat must
    not be read as "this consumer is making progress" — and an alert must not
    be keyed on ``seconds_since_delivery`` staying low, which is precisely what
    that wedged loop looks like; it says only "this consumer is still there".

    Deliberately not built on :class:`RateLimitedLog`. That primitive reports
    an exception with its traceback, counts what it suppressed, and treats
    ``reset()`` as "the guarded operation recovered". A heartbeat has no
    exception to report, and the number of heartbeats it skipped is not news —
    the poll and message counts already describe the interval. What is left of
    that primitive once those are dropped is a "last emitted at" timestamp,
    which is exactly what this holds.
    """

    def __init__(
        self,
        *,
        consumer_group: str,
        worker_id: str,
        streams: Iterable[str | bytes],
        interval_seconds: float,
        poll_block_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        # Checked here, not at the config boundary, because this is where every
        # supplier lands: the YAML default, an env override, and a service that
        # passes its own value at the call site. A bound that only guarded the
        # shipped default would miss the case that actually breaks the harvest —
        # one service configured past it while the default stays innocent.
        #
        # `poll_block_seconds` has no default on purpose: the ceiling depends on
        # it, and a caller that forgot to say how long its poll blocks would get
        # a ceiling that is too loose by exactly the amount it forgot.
        if poll_block_seconds < 0:
            raise ValueError("poll_block_seconds must not be negative")
        ceiling = max_heartbeat_interval_seconds(poll_block_seconds)
        if not 0 < interval_seconds <= ceiling:
            raise ValueError(
                f"heartbeat_interval_seconds must be >0 and <={ceiling} "
                f"(observation_max_gap {OBSERVATION_MAX_GAP_SECONDS} minus the "
                f"{poll_block_seconds}s poll block and "
                f"{TIMESTAMP_RESOLUTION_SECONDS}s of timestamp truncation, "
                "because what is scored is the measured gap, not the interval); "
                f"got {interval_seconds}"
            )
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.streams = ",".join(decode_stream_id(stream) for stream in streams)
        self.interval_seconds = interval_seconds
        self._clock = clock or time.monotonic
        self._interval_started_at: float | None = None
        self._polls = 0
        self._messages = 0
        self._last_delivery_at: float | None = None

    def record_poll(self, message_count: int) -> None:
        """Count one completed poll, emitting the heartbeat when one is due.

        ``message_count`` is what the poll *delivered*, counted before the
        handler runs — see the class docstring on delivery versus progress.

        The first call opens the interval instead of emitting: a heartbeat
        reports what happened over ``interval_seconds``, and the loop has not
        run that long yet. Every later call is free — an integer add and one
        clock read — so it is safe on the block-free path where a busy stage
        polls thousands of times a second.
        """
        now = self._clock()
        self._polls += 1
        self._messages += message_count
        if message_count:
            self._last_delivery_at = now

        if self._interval_started_at is None:
            self._interval_started_at = now
            return
        if now - self._interval_started_at < self.interval_seconds:
            return

        logger.info(
            format_audit_kv(
                event="stream_consumer_alive",
                streams=self.streams,
                consumer_group=self.consumer_group,
                worker_id=self.worker_id,
                polls=self._polls,
                messages=self._messages,
                # Absent until this worker has been *delivered* something: "0
                # seconds since a message that never arrived" would be a lie,
                # and the bare `messages=0` already says the interval was quiet.
                seconds_since_delivery=(
                    None
                    if self._last_delivery_at is None
                    else int(now - self._last_delivery_at)
                ),
            )
        )
        self._interval_started_at = now
        self._polls = 0
        self._messages = 0


class StreamStage(ABC):
    """Abstract base for a Redis consumer-group daemon stage."""

    def __init__(
        self,
        *,
        redis: Any,
        input_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        xreadgroup_error_sleep_seconds: float = 0.5,
        pending_retry_idle_ms: int = 60_000,
        heartbeat_interval_seconds: float | None = None,
        heartbeat_clock: Callable[[], float] | None = None,
    ) -> None:
        self.redis = redis
        self.input_stream = input_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._xreadgroup_error_sleep = xreadgroup_error_sleep_seconds
        self.pending_retry_idle_ms = pending_retry_idle_ms
        self._pending_claim_start_id: str | bytes = "0-0"
        self._pending_claim_disabled = pending_retry_idle_ms < 0
        self._xautoclaim_error_log = RateLimitedLog()
        self._xreadgroup_error_log = RateLimitedLog()
        self._heartbeat = _LivenessHeartbeat(
            consumer_group=consumer_group,
            worker_id=worker_id,
            streams=(input_stream,),
            interval_seconds=_resolve_heartbeat_interval(
                heartbeat_interval_seconds,
                poll_block_seconds=xread_block_ms / 1000,
                consumer_group=consumer_group,
            ),
            # The heartbeat becomes due during a poll and is emitted when the
            # next one returns, so the block is part of every measured gap.
            poll_block_seconds=xread_block_ms / 1000,
            clock=heartbeat_clock,
        )
        self._stop = asyncio.Event()

    # -- subclass contract ------------------------------------------------ #

    @abstractmethod
    async def handle_message(self, msg_id: bytes, fields: dict[bytes, bytes]) -> bool:
        """Process one message.

        Returns:
            ``True``  → the framework XACKs the message after this returns.
            ``False`` → the framework does NOT XACK (stays pending for retry).

        Deliberate skips (poison-pill parse error, gate-blocked) should return
        ``True`` so the message is consumed; transient failures should return
        ``False`` so it is retried. Exceptions raised here propagate out of the
        loop (``on_shutdown`` still runs); subclasses should catch their own
        recoverable errors and map them to a bool.
        """
        ...

    # -- optional hooks (no-op defaults) --------------------------------- #

    async def on_startup(self) -> None:  # noqa: B027 - intentional optional hook
        """Called once before the consume loop. Override for startup guards."""

    async def pre_iteration_gate(self) -> bool:
        """Called at the top of each loop iteration, before XREADGROUP.

        Return ``False`` to abort the loop (e.g. a kill-switch sentinel
        appeared). Default: always proceed.
        """
        return True

    async def post_poll(self, message_count: int) -> None:  # noqa: B027
        """Called after each XREADGROUP returns (``message_count == 0`` when idle).

        Override for per-cycle observability (e.g. backlog gauge update).
        """

    async def on_shutdown(self) -> None:  # noqa: B027 - intentional optional hook
        """Called in the loop's ``finally`` (even on exception).

        Override to flush writers/publishers.
        """

    # -- framework loop (not overridden) --------------------------------- #

    async def _claim_pending_messages(self) -> list[tuple[bytes, dict[bytes, bytes]]]:
        """Claim idle pending messages for retry.

        ``handle_message(False)`` intentionally leaves a record in the consumer
        group's pending-entry list. ``XAUTOCLAIM`` makes that contract real
        across worker restarts and avoids a hot loop by waiting until the entry
        has been idle for ``pending_retry_idle_ms``.
        """
        if self._pending_claim_disabled:
            return []
        try:
            result = await self.redis.xautoclaim(
                self.input_stream,
                self.consumer_group,
                self.worker_id,
                self.pending_retry_idle_ms,
                self._pending_claim_start_id,
                count=self.batch_size,
            )
        except AttributeError:
            logger.warning("redis client lacks XAUTOCLAIM; pending retry disabled")
            self._pending_claim_disabled = True
            return []
        except Exception as exc:
            # NOGROUP-only on purpose: XAUTOCLAIM does not block, so it cannot
            # produce the UNBLOCKED shape that ``is_vanished_stream_read_error``
            # exists for. Unlike ``run()`` below, this path does not branch on
            # the outcome and must not: it returns ``[]`` either way and the
            # caller goes straight to XREADGROUP, which is where a still-broken
            # group is logged and backed off. All three outcomes are already on
            # the record from inside ``recover_missing_consumer_group``
            # (CREATED/FAILED at WARNING), so a second line here would only
            # duplicate it.
            if is_missing_consumer_group_error(exc):
                await recover_missing_consumer_group(
                    self.redis,
                    self.input_stream,
                    self.consumer_group,
                )
                self._pending_claim_start_id = "0-0"
                return []
            message = str(exc).lower()
            if "unknown command" in message or "syntax" in message:
                logger.warning(
                    "redis XAUTOCLAIM unavailable; pending retry disabled",
                    exc_info=True,
                )
                self._pending_claim_disabled = True
                return []
            self._xautoclaim_error_log.exception(
                logger,
                "xautoclaim error; sleeping %.1fs",
                self._xreadgroup_error_sleep,
            )
            await asyncio.sleep(self._xreadgroup_error_sleep)
            return []
        self._xautoclaim_error_log.reset()

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            return []
        next_id = result[0]
        messages = result[1] or []
        self._pending_claim_start_id = next_id or "0-0"
        if self._pending_claim_start_id in {b"0-0", "0-0"}:
            self._pending_claim_start_id = "0-0"
        return list(messages)

    async def _process_messages(
        self,
        messages: list[tuple[bytes, dict[bytes, bytes]]],
        *,
        claimed: bool = False,
    ) -> None:
        for msg_id, data in messages:
            started_at = time.perf_counter()
            try:
                should_ack = await self.handle_message(msg_id, data)
            except Exception:
                _log_failed_message(
                    stream=self.input_stream,
                    consumer_group=self.consumer_group,
                    worker_id=self.worker_id,
                    msg_id=msg_id,
                    fields=data,
                    claimed=claimed,
                    duration_ms=_duration_ms(started_at),
                )
                raise
            if should_ack:
                try:
                    await self.redis.xack(
                        self.input_stream, self.consumer_group, msg_id
                    )
                except Exception:
                    _log_ack_failed_message(
                        stream=self.input_stream,
                        consumer_group=self.consumer_group,
                        worker_id=self.worker_id,
                        msg_id=msg_id,
                        fields=data,
                        claimed=claimed,
                        duration_ms=_duration_ms(started_at),
                    )
                    raise
            _log_processed_message(
                stream=self.input_stream,
                consumer_group=self.consumer_group,
                worker_id=self.worker_id,
                msg_id=msg_id,
                fields=data,
                ack=should_ack,
                claimed=claimed,
                duration_ms=_duration_ms(started_at),
            )

    @final
    async def run(self) -> None:
        try:
            await self.on_startup()

            await _ensure_consumer_group(
                self.redis,
                self.input_stream,
                self.consumer_group,
            )

            while not self._stop.is_set():
                if not await self.pre_iteration_gate():
                    return

                claimed = await self._claim_pending_messages()
                if claimed:
                    # Emitted from the loop, never from ``post_poll``: that hook
                    # is overridden by subclasses (services/news_scorer), and an
                    # override that forgets ``super()`` would silently delete the
                    # only evidence this stage is alive.
                    self._heartbeat.record_poll(len(claimed))
                    await self.post_poll(len(claimed))
                    await self._process_messages(claimed, claimed=True)
                    continue

                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.input_stream: ">"},
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception as exc:
                    if is_vanished_stream_read_error(exc):
                        # One stream, so the sweep takes a one-element
                        # iterable; what its answer means is the helper's
                        # docstring, not a rule re-typed at each call site.
                        if await sweep_vanished_consumer_groups(
                            self.redis,
                            (self.input_stream,),
                            self.consumer_group,
                        ):
                            await asyncio.sleep(0)
                            continue
                    self._xreadgroup_error_log.exception(
                        logger,
                        "xreadgroup error; sleeping %.1fs",
                        self._xreadgroup_error_sleep,
                    )
                    await asyncio.sleep(self._xreadgroup_error_sleep)
                    continue
                self._xreadgroup_error_log.reset()

                count = sum(len(msgs) for _stream, msgs in messages) if messages else 0
                # Before ``post_poll`` and above the idle ``continue``: the idle
                # poll is the case with no other evidence at all, and it is the
                # one this line exists for.
                self._heartbeat.record_poll(count)
                await self.post_poll(count)

                if not messages:
                    await asyncio.sleep(0)
                    continue

                for _stream, msgs in messages:
                    await self._process_messages(list(msgs), claimed=False)
        finally:
            await self.on_shutdown()

    async def stop(self) -> None:
        self._stop.set()


class MultiStreamStage(ABC):
    """Abstract base for a Redis consumer-group daemon stage with many inputs."""

    def __init__(
        self,
        *,
        redis: Any,
        input_streams: list[str],
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        xreadgroup_error_sleep_seconds: float = 0.5,
        pending_retry_idle_ms: int = 60_000,
        heartbeat_interval_seconds: float | None = None,
        heartbeat_clock: Callable[[], float] | None = None,
    ) -> None:
        if not input_streams:
            raise ValueError("input_streams must not be empty")
        self.redis = redis
        self.input_streams = list(input_streams)
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._xreadgroup_error_sleep = xreadgroup_error_sleep_seconds
        self.pending_retry_idle_ms = pending_retry_idle_ms
        self._pending_claim_start_ids: dict[str, str | bytes] = dict.fromkeys(
            self.input_streams, "0-0"
        )
        self._pending_claim_disabled = pending_retry_idle_ms < 0
        self._xautoclaim_error_log = RateLimitedLog()
        self._xreadgroup_error_log = RateLimitedLog()
        self._heartbeat = _LivenessHeartbeat(
            consumer_group=consumer_group,
            worker_id=worker_id,
            # Every input stream is named: one XREADGROUP covers them all, so a
            # heartbeat that quoted only the first would understate what this
            # worker is proving it still reads.
            streams=self.input_streams,
            interval_seconds=_resolve_heartbeat_interval(
                heartbeat_interval_seconds,
                poll_block_seconds=xread_block_ms / 1000,
                consumer_group=consumer_group,
            ),
            # The heartbeat becomes due during a poll and is emitted when the
            # next one returns, so the block is part of every measured gap.
            poll_block_seconds=xread_block_ms / 1000,
            clock=heartbeat_clock,
        )
        self._stop = asyncio.Event()

    # -- subclass contract ------------------------------------------------ #

    @abstractmethod
    async def handle_message(
        self,
        stream: str | bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> bool:
        """Process one message from its source stream.

        Returns:
            ``True``  → the framework XACKs the message on ``stream``.
            ``False`` → the framework does NOT XACK (stays pending for retry).
        """
        ...

    # -- optional hooks (no-op defaults) --------------------------------- #

    async def on_startup(self) -> None:  # noqa: B027 - intentional optional hook
        """Called once before the consume loop. Override for startup guards."""

    async def pre_iteration_gate(self) -> bool:
        """Called at the top of each loop iteration, before XREADGROUP."""
        return True

    async def post_poll(self, message_count: int) -> None:  # noqa: B027
        """Called after each poll/reclaim returns a message count."""

    async def on_shutdown(self) -> None:  # noqa: B027 - intentional optional hook
        """Called in the loop's ``finally`` (even on exception)."""

    # -- framework loop (not overridden) --------------------------------- #

    async def _claim_pending_messages(
        self, stream: str
    ) -> list[tuple[bytes, dict[bytes, bytes]]]:
        """Claim idle pending messages for one source stream."""
        if self._pending_claim_disabled:
            return []
        try:
            result = await self.redis.xautoclaim(
                stream,
                self.consumer_group,
                self.worker_id,
                self.pending_retry_idle_ms,
                self._pending_claim_start_ids[stream],
                count=self.batch_size,
            )
        except AttributeError:
            logger.warning("redis client lacks XAUTOCLAIM; pending retry disabled")
            self._pending_claim_disabled = True
            return []
        except Exception as exc:
            # NOGROUP-only, and deliberately outcome-independent — see the same
            # branch in ``StreamStage._claim_pending_messages``.
            if is_missing_consumer_group_error(exc):
                await recover_missing_consumer_group(
                    self.redis,
                    stream,
                    self.consumer_group,
                )
                self._pending_claim_start_ids[stream] = "0-0"
                return []
            message = str(exc).lower()
            if "unknown command" in message or "syntax" in message:
                logger.warning(
                    "redis XAUTOCLAIM unavailable; pending retry disabled",
                    exc_info=True,
                )
                self._pending_claim_disabled = True
                return []
            self._xautoclaim_error_log.exception(
                logger,
                "xautoclaim error; sleeping %.1fs",
                self._xreadgroup_error_sleep,
            )
            await asyncio.sleep(self._xreadgroup_error_sleep)
            return []
        self._xautoclaim_error_log.reset()

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            return []
        next_id = result[0]
        messages = result[1] or []
        self._pending_claim_start_ids[stream] = next_id or "0-0"
        if self._pending_claim_start_ids[stream] in {b"0-0", "0-0"}:
            self._pending_claim_start_ids[stream] = "0-0"
        return list(messages)

    async def _claim_pending_by_stream(
        self,
    ) -> list[tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]]:
        claimed_by_stream = []
        for stream in self.input_streams:
            claimed = await self._claim_pending_messages(stream)
            if claimed:
                claimed_by_stream.append((stream, claimed))
        return claimed_by_stream

    async def _process_messages(
        self,
        stream: str | bytes,
        messages: list[tuple[bytes, dict[bytes, bytes]]],
        *,
        claimed: bool = False,
    ) -> None:
        for msg_id, data in messages:
            started_at = time.perf_counter()
            try:
                should_ack = await self.handle_message(stream, msg_id, data)
            except Exception:
                _log_failed_message(
                    stream=stream,
                    consumer_group=self.consumer_group,
                    worker_id=self.worker_id,
                    msg_id=msg_id,
                    fields=data,
                    claimed=claimed,
                    duration_ms=_duration_ms(started_at),
                )
                raise
            if should_ack:
                try:
                    await self.redis.xack(stream, self.consumer_group, msg_id)
                except Exception:
                    _log_ack_failed_message(
                        stream=stream,
                        consumer_group=self.consumer_group,
                        worker_id=self.worker_id,
                        msg_id=msg_id,
                        fields=data,
                        claimed=claimed,
                        duration_ms=_duration_ms(started_at),
                    )
                    raise
            _log_processed_message(
                stream=stream,
                consumer_group=self.consumer_group,
                worker_id=self.worker_id,
                msg_id=msg_id,
                fields=data,
                ack=should_ack,
                claimed=claimed,
                duration_ms=_duration_ms(started_at),
            )

    @final
    async def run(self) -> None:
        try:
            await self.on_startup()

            for stream in self.input_streams:
                await _ensure_consumer_group(
                    self.redis,
                    stream,
                    self.consumer_group,
                )

            while not self._stop.is_set():
                if not await self.pre_iteration_gate():
                    return

                claimed_by_stream = await self._claim_pending_by_stream()
                if claimed_by_stream:
                    count = sum(
                        len(messages) for _stream, messages in claimed_by_stream
                    )
                    # From the loop, not ``post_poll`` — see the same call in
                    # ``StreamStage.run``.
                    self._heartbeat.record_poll(count)
                    await self.post_poll(count)
                    for stream, messages in claimed_by_stream:
                        await self._process_messages(stream, messages, claimed=True)
                    continue

                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams=dict.fromkeys(self.input_streams, ">"),
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception as exc:
                    if is_vanished_stream_read_error(exc):
                        # Every input stream is read in one XREADGROUP, so the
                        # read fails as a unit and the sweep covers all of
                        # them; what its answer means is the helper's
                        # docstring, not a rule re-typed at each call site.
                        if await sweep_vanished_consumer_groups(
                            self.redis,
                            self.input_streams,
                            self.consumer_group,
                        ):
                            await asyncio.sleep(0)
                            continue
                    self._xreadgroup_error_log.exception(
                        logger,
                        "xreadgroup error; sleeping %.1fs",
                        self._xreadgroup_error_sleep,
                    )
                    await asyncio.sleep(self._xreadgroup_error_sleep)
                    continue
                self._xreadgroup_error_log.reset()

                count = sum(len(msgs) for _stream, msgs in messages) if messages else 0
                self._heartbeat.record_poll(count)
                await self.post_poll(count)

                if not messages:
                    await asyncio.sleep(0)
                    continue

                for stream, msgs in messages:
                    await self._process_messages(stream, list(msgs), claimed=False)
        finally:
            await self.on_shutdown()

    async def stop(self) -> None:
        self._stop.set()
