"""``EngineDriver`` — the ONE place that calls ``EngineCore.handle``/``run`` in this runtime shell"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

from tos.canonical import ArtifactIntegrityError, CanonicalizationScheme
from tos.engine import EngineCore, EventResult
from tos.engine.records import (
    EgressResultPayload,
    EngineEvent,
    event_identity,
)
from tos.engine.vocabulary import (
    EgressResultKind,
    EventKind,
    OrderingAdmission,
    ResultDisposition,
)
from tos.ordering import OrderingEvent
from tos.orthostate import CompositeState

from tos_runtime.engine._timeout_tracker import _TimeoutTracker
from tos_runtime.engine.finality_projection import project_finality
from tos_runtime.engine.flow_fingerprint import FlowFingerprint, flow_fingerprint_for
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import (
    NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
    OrthostateProjector,
)
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import FinalityProducerPort
from tos_runtime.time.sources import MonotonicSource

if TYPE_CHECKING:
    from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer

__all__ = ["EngineDriver", "EngineDriverInvariantError"]


class EngineDriverInvariantError(RuntimeError):
    """A driver-internal type-narrowing invariant turned out false (independent-review"""


_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_EVENT_CONSUMED_RECORD_CLASS = "EVENT_CONSUMED"

_EVENT_HANDLING_STARTED_KIND = "EVENT_HANDLING_STARTED"
_EVENT_HANDLING_STARTED_RECORD_CLASS = "EVENT_HANDLING_STARTED"

_COMPOSITE_STATE_WRITE_FAILED_KIND = "COMPOSITE_STATE_WRITE_FAILED"

_HANDLING_INTERRUPTED_NO_SEND_EVIDENCE_REASON = "HANDLING_INTERRUPTED_NO_SEND_EVIDENCE"

_HANDLING_INTERRUPTED_SEND_POSSIBLY_LIVE_KIND = (
    "HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND"
)

_DECISION_TICK_DROPPED_ON_RECOVERY_KIND = "DECISION_TICK_DROPPED_ON_RECOVERY"

_SEND_EVIDENCE_KINDS: tuple[str, ...] = ("SEND_STARTED", "SEND_HANDED_OFF")


class _YieldOrderCounter:
    """One monotone counter stamping every event this driver yields to the core."""

    def __init__(self, *, continuity_id: str, seed: int) -> None:
        if not continuity_id.strip():
            raise ArtifactIntegrityError(
                "EngineDriver continuity_id must be concrete — source-native sequences are "
                "compared only within the same continuity (tos.ordering.compare_order)"
            )
        if seed < 0:
            raise ArtifactIntegrityError(
                f"EngineDriver yield-order seed must be non-negative (got {seed})"
            )
        self._continuity_id = continuity_id
        self._issued = seed

    def next_reference(self) -> OrderingEvent:
        """Issue the next strictly-greater coordinate; there is no way to obtain one otherwise."""
        self._issued += 1
        sequence = self._issued
        return OrderingEvent(
            event_id=f"{self._continuity_id}-{sequence}",
            source_continuity_id=self._continuity_id,
            source_native_sequence=sequence,
        )


class EngineDriver:
    """Single-threaded, deterministic driver over a durable :class:`SqliteEventInbox`."""

    def __init__(
        self,
        *,
        core: EngineCore,
        inbox: SqliteEventInbox,
        evidence_store: SqliteEvidenceStore,
        emergency_log: EmergencyAppendLog,
        scheme: CanonicalizationScheme,
        continuity_id: str,
        monotonic_source: MonotonicSource,
        max_send_result_wait_ms: int,
        orthostate_projector: OrthostateProjector,
        finality_producer: FinalityProducerPort,
        recovery_composite_writer: Callable[[str, CompositeState], None] | None = None,
    ) -> None:
        """Wire the driver."""
        self._core = core
        self._inbox = inbox
        self._evidence_store = evidence_store
        self._emergency_log = emergency_log
        self._scheme = scheme
        self._counter = _YieldOrderCounter(
            continuity_id=continuity_id, seed=inbox.count
        )
        self._time = monotonic_source
        self._timeouts = _TimeoutTracker(
            max_send_result_wait_ms=max_send_result_wait_ms
        )
        self._orthostate_projector = orthostate_projector
        self._finality_producer = finality_producer
        self._recovery_composite_writer = recovery_composite_writer
        self._release_consumer: FinalityReleaseConsumer | None = None
        self._gateway: object | None = None
        self._drained_results = 0
        self._after_turn: Callable[[], None] | None = None
        self._after_turn_failures = 0
        self._after_turn_last_error: str | None = None
        self._draining = False

    def bind_release_consumer(self, consumer: FinalityReleaseConsumer) -> None:
        """Attach the TOS Phase 5 W2-R finality release consumer this driver's finality-"""
        self._release_consumer = consumer

    def bind_gateway(self, gateway: object) -> None:
        """Attach the send boundary whose retained ``.results`` this driver drains."""
        self._gateway = gateway

    def bind_after_turn(self, callback: Callable[[], None]) -> None:
        """Attach a callback invoked once per PROCESSED turn (plan §2 decision 7): after each"""
        self._after_turn = callback

    def _fire_after_turn(self) -> None:
        """Invoke :attr:`_after_turn` if bound; count and never re-raise a failure."""
        callback = self._after_turn
        if callback is None:
            return
        try:
            callback()
        except Exception as exc:  # noqa: BLE001 - must never halt a drain
            self._after_turn_failures += 1
            self._after_turn_last_error = repr(exc)

    @property
    def after_turn_failures(self) -> int:
        """Count of :meth:`bind_after_turn` callback exceptions."""
        return self._after_turn_failures

    @property
    def after_turn_last_error(self) -> str | None:
        """``repr()`` of the last :meth:`bind_after_turn` exception, or ``None``."""
        return self._after_turn_last_error

    def _stamp(self, event: EngineEvent) -> EngineEvent:
        """Replace ``event``'s reference with the next yield-order coordinate."""
        reference = self._counter.next_reference()
        if event.kind is EventKind.DECISION_TICK:
            tick_payload = event.decision_tick
            assert tick_payload is not None
            stamped_tick = tick_payload.model_copy(update={"reference": reference})
            return EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=stamped_tick)
        egress_payload = event.egress_result
        assert egress_payload is not None
        stamped_egress = egress_payload.model_copy(update={"reference": reference})
        return EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=stamped_egress)

    def _find_consumed_receipt(self, event_id: str) -> tuple[int, int] | None:
        """Scan the evidence store for an existing ``EVENT_CONSUMED`` receipt for ``event_id``."""
        cur = self._evidence_store.connection.execute(
            "SELECT seq, key_generation, payload_json FROM entries "
            "WHERE kind = ? ORDER BY seq ASC",
            (_EVENT_CONSUMED_KIND,),
        )
        for seq, key_generation, payload_json in cur:
            payload = json.loads(payload_json).get("payload", {})
            if payload.get("event_id") == event_id:
                return seq, key_generation
        return None

    def _send_evidence_exists_after(self, marker_seq: int) -> bool:
        """Whether any ``SEND_STARTED``/``SEND_HANDED_OFF`` evidence was durably recorded after"""
        placeholders = ",".join("?" for _ in _SEND_EVIDENCE_KINDS)
        cur = self._evidence_store.connection.execute(
            f"SELECT 1 FROM entries WHERE kind IN ({placeholders}) AND seq > ? LIMIT 1",
            (*_SEND_EVIDENCE_KINDS, marker_seq),
        )
        return cur.fetchone() is not None

    def _handle_interrupted_event(
        self, *, seq: int, event_id: str, event: EngineEvent, marker_seq: int
    ) -> None:
        """Recover a crash between the write-ahead ``EVENT_HANDLING_STARTED`` marker and the"""
        if self._send_evidence_exists_after(marker_seq):
            record_halt(
                self._evidence_store,
                self._emergency_log,
                payload={
                    "event_id": event_id,
                    "handling_started_evidence_seq": marker_seq,
                },
                kind=_HANDLING_INTERRUPTED_SEND_POSSIBLY_LIVE_KIND,
                record_class=_HANDLING_INTERRUPTED_SEND_POSSIBLY_LIVE_KIND,
            )
            halt_reason = _HANDLING_INTERRUPTED_SEND_POSSIBLY_LIVE_KIND
        else:
            self._evidence_store.append(
                {"event_id": event_id, "handling_started_evidence_seq": marker_seq},
                kind=_DECISION_TICK_DROPPED_ON_RECOVERY_KIND,
                record_class=_DECISION_TICK_DROPPED_ON_RECOVERY_KIND,
            )
            halt_reason = _HANDLING_INTERRUPTED_NO_SEND_EVIDENCE_REASON
        payload_digest = self._scheme.compute_digest(event.model_dump(mode="json"))
        evidence_seq, generation = self._record_consumed(
            event_id=event_id,
            payload_digest=payload_digest,
            outcome_digest=None,
            halt_reason=halt_reason,
            flow_fingerprint=None,
        )
        self._inbox.mark_consumed(seq, evidence_seq=evidence_seq, generation=generation)

    def _project_orthostate_and_persist(
        self, event: EngineEvent, result: EventResult, event_id: str
    ) -> None:
        """Project ``event``'s orthostate composite and, if a real recovery composite writer was"""
        composite = self._orthostate_projector.project(event=event, result=result)
        if composite is None or self._recovery_composite_writer is None:
            return
        payload = event.egress_result
        if payload is None:
            raise EngineDriverInvariantError(
                "project() returned non-None but egress_result is None -- project() "
                "returns non-None only for EGRESS_RESULT events"
            )
        try:
            self._recovery_composite_writer(payload.attempt_id, composite)
        except (
            Exception
        ) as exc:  # noqa: BLE001 -- any write failure halts, never swallowed
            record_halt(
                self._evidence_store,
                self._emergency_log,
                payload={
                    "event_id": event_id,
                    "attempt_id": payload.attempt_id,
                    "detail": f"{type(exc).__name__}: {exc}",
                },
                kind=_COMPOSITE_STATE_WRITE_FAILED_KIND,
                record_class=_COMPOSITE_STATE_WRITE_FAILED_KIND,
            )
            raise

    def _record_consumed(
        self,
        *,
        event_id: str,
        payload_digest: str,
        outcome_digest: str | None,
        halt_reason: str | None,
        flow_fingerprint: FlowFingerprint | None,
    ) -> tuple[int, int]:
        """Durably append this driver's own ``EVENT_CONSUMED`` receipt."""
        receipt = self._evidence_store.append(
            {
                "event_id": event_id,
                "payload_digest": payload_digest,
                "outcome_digest": outcome_digest,
                "halt_reason": halt_reason,
                "flow_fingerprint": (
                    None
                    if flow_fingerprint is None
                    else flow_fingerprint.model_dump(mode="json")
                ),
            },
            kind=_EVENT_CONSUMED_KIND,
            record_class=_EVENT_CONSUMED_RECORD_CLASS,
        )
        assert receipt.seq is not None
        assert receipt.key_generation is not None
        return receipt.seq, receipt.key_generation

    def _new_risk_halted_result(
        self, event: EngineEvent, halted: dict[str, object]
    ) -> EventResult:
        """Independent review finding #3: the synthetic ``EventResult`` returned for a"""
        payload = event.decision_tick
        key = payload.instrument_key if payload is not None else event.instrument_key()
        return EventResult(
            kind=EventKind.DECISION_TICK,
            instrument_key=key,
            ordering=OrderingAdmission.MONOTONE,
            detail=(
                f"refused by the durable new-risk halt latch ({NEW_RISK_HALTED_BY_COUPLING_VIOLATION}) "
                f"first recorded for {halted.get('event_id')!r} "
                f"(evidence_seq={halted.get('evidence_seq')!r}); an operator may re-arm via "
                "ComposedRuntime.clear_new_risk_halt(latched_evidence_seq="
                f"{halted.get('evidence_seq')!r}, operator_attestation=...) — no automatic "
                "clearing path exists anywhere in this runtime"
            ),
        )

    def _process_next(self) -> tuple[int, EventResult] | None:
        """Drain crash-window rows, then process exactly one genuinely new event."""
        if self._draining:
            raise ArtifactIntegrityError(
                "EngineDriver._process_next called re-entrantly — this driver is single-threaded "
                "and must complete one event's full bookkeeping (core.handle through the "
                "EVENT_CONSUMED append) before pulling the next; a re-entrant call would break "
                "the soundness invariant _send_evidence_exists_after depends on"
            )
        self._draining = True
        try:
            self._inject_due_timeouts()
            while True:
                pulled = self._inbox.next_unconsumed()
                if pulled is None:
                    return None
                seq, event = pulled
                event_id = event_identity(event, scheme=self._scheme)

                existing = self._find_consumed_receipt(event_id)
                if existing is not None:
                    evidence_seq, generation = existing
                    self._inbox.mark_consumed(
                        seq, evidence_seq=evidence_seq, generation=generation
                    )
                    continue

                interrupted = self._inbox.handling_started_receipt(seq)
                if interrupted is not None:
                    marker_seq, _marker_generation = interrupted
                    self._handle_interrupted_event(
                        seq=seq, event_id=event_id, event=event, marker_seq=marker_seq
                    )
                    continue

                marker_receipt = self._evidence_store.append(
                    {"event_id": event_id},
                    kind=_EVENT_HANDLING_STARTED_KIND,
                    record_class=_EVENT_HANDLING_STARTED_RECORD_CLASS,
                )
                assert marker_receipt.seq is not None
                assert marker_receipt.key_generation is not None
                self._inbox.mark_handling_started(
                    seq,
                    evidence_seq=marker_receipt.seq,
                    generation=marker_receipt.key_generation,
                )

                payload_digest = self._scheme.compute_digest(
                    event.model_dump(mode="json")
                )

                if event.kind is EventKind.DECISION_TICK:
                    halted = self._inbox.new_risk_halt()
                    if halted is not None:
                        result = self._new_risk_halted_result(event, halted)
                        evidence_seq, generation = self._record_consumed(
                            event_id=event_id,
                            payload_digest=payload_digest,
                            outcome_digest=None,
                            halt_reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
                            flow_fingerprint=flow_fingerprint_for(result),
                        )
                        self._inbox.mark_consumed(
                            seq, evidence_seq=evidence_seq, generation=generation
                        )
                        return seq, result

                result = self._core.handle(event)
                halt_reason_str = (
                    None if result.halt_reason is None else result.halt_reason.value
                )
                self._project_orthostate_and_persist(event, result, event_id)
                evidence_seq, generation = self._record_consumed(
                    event_id=event_id,
                    payload_digest=payload_digest,
                    outcome_digest=result.outcome_digest,
                    halt_reason=halt_reason_str,
                    flow_fingerprint=flow_fingerprint_for(result),
                )
                self._inbox.mark_consumed(
                    seq, evidence_seq=evidence_seq, generation=generation
                )

                self._track_timeouts(event, result)
                self._project_finality(event, result)
                if event.kind is EventKind.DECISION_TICK:
                    self._drain_gateway_results()
                return seq, result
        finally:
            self._draining = False

    def run_once(self) -> EventResult | None:
        """Process exactly one pending event to completion, or recover a crash-window row."""
        processed = self._process_next()
        if processed is None:
            return None
        self._fire_after_turn()
        return processed[1]

    def run_until_idle(self) -> tuple[EventResult, ...]:
        """Call :meth:`run_once` until the inbox has nothing left to admit or recover."""
        results: list[EventResult] = []
        while True:
            processed = self._process_next()
            if processed is None:
                return tuple(results)
            results.append(processed[1])
            self._fire_after_turn()

    def enqueue_and_run(self, event: EngineEvent) -> EventResult:
        """Stamp, durably admit, and fully process ``event`` (the compose-root convenience API)."""
        stamped = self._stamp(event)
        receipt = self._inbox.enqueue(stamped)
        target_seq = receipt.seq
        result_for_target: EventResult | None = None
        while True:
            processed = self._process_next()
            if processed is None:
                break
            seq, result = processed
            self._fire_after_turn()
            if seq == target_seq:
                result_for_target = result
        if result_for_target is None:
            raise ArtifactIntegrityError(
                f"EngineDriver.enqueue_and_run could not produce a fresh EventResult for "
                f"event_id={receipt.event_id!r} (duplicate={receipt.duplicate}) — this exact "
                "event was already durably consumed in a prior call"
            )
        return result_for_target

    def _drain_gateway_results(self) -> None:
        """Enqueue every gateway result produced since the last drain as ``EGRESS_RESULT`` events."""
        gateway = self._gateway
        if gateway is None:
            return
        retained: tuple[EgressResultPayload, ...] = gateway.results  # type: ignore[attr-defined]
        newly_produced = retained[self._drained_results :]
        self._drained_results = len(retained)
        for payload in newly_produced:
            event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
            self._inbox.enqueue(self._stamp(event))

    def _track_timeouts(self, event: EngineEvent, result: EventResult) -> None:
        """Update the per-scope pending-attempt tracker after a processed event."""
        if event.kind is EventKind.DECISION_TICK:
            flow = result.flow
            if flow is not None and flow.handed_off and flow.attempt is not None:
                self._timeouts.observe_handoff(
                    result.instrument_key,
                    attempt_id=flow.attempt.attempt_id,
                    now_ms=self._time.now_ms(),
                )
            return
        if result.result_disposition is not ResultDisposition.APPLIED:
            return
        payload = event.egress_result
        assert payload is not None
        self._timeouts.observe_result(
            result.instrument_key, attempt_id=payload.attempt_id
        )

    def _inject_due_timeouts(self) -> None:
        """Enqueue a synthetic ``EGRESS_RESULT(kind=TIMEOUT)`` for every scope past its bound."""
        now_ms = self._time.now_ms()
        for key, attempt_id in self._timeouts.due(now_ms=now_ms):
            payload = EgressResultPayload(
                instrument_key=key, attempt_id=attempt_id, kind=EgressResultKind.TIMEOUT
            )
            event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
            self._inbox.enqueue(self._stamp(event))

    def _project_finality(self, event: EngineEvent, result: EventResult) -> None:
        """Delegates to :func:`~tos_runtime.engine.finality_projection.project_finality` (TOS"""
        project_finality(
            event,
            result,
            inbox=self._inbox,
            evidence_store=self._evidence_store,
            finality_producer=self._finality_producer,
            release_consumer=self._release_consumer,
            ledger=self._core.ledger,
        )
