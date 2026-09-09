"""``EngineDriver`` — the ONE place that calls ``EngineCore.handle``/``run`` in this runtime shell
(TOS Phase 3 Wave 1 Lane A-R; plan §1.1).

Before this module existed, the survey (plan §0) measured: **zero** runtime call sites for
``EngineCore.handle``/``run`` — every compose end-to-end test built an
:class:`~tos.engine.EngineEvent` directly and fed it to the core itself, and a send boundary's
retained results (:attr:`tos.egressgw.BrokerEgressGateway.results`) were never re-injected as
``EGRESS_RESULT`` events anywhere in the runtime. This module closes both gaps.

Four responsibilities, each load-bearing:

1. **Yield-order coordinate stamping.** :class:`tos.backtest.driver.YieldOrderCounter` establishes
   why a coordinate scheme decoupled from any external index is required: the engine's causal gate
   holds one global ``_last_reference`` and updates it for every non-``REVERSED`` event
   (``tos/src/tos/engine/core.py``), so an externally-supplied reference cannot be trusted to
   compose correctly with a re-injected result's reference. This driver reimplements that same
   "one monotone counter stamps every yielded event, tick or egress result alike" discipline
   LOCALLY (:class:`_YieldOrderCounter` below) rather than importing ``tos.backtest`` — a harness
   package, not a production dependency (plan §1.1 "GatewayResultReinjector... mirror its shape,
   do not import backtest into the runtime"). The counter is durably re-seeded from
   :attr:`~tos_runtime.engine.inbox.SqliteEventInbox.count` at construction, since every admitted
   event corresponds to exactly one issued coordinate.
2. **Crash-window idempotency.** Draining (:meth:`_process_next`) checks, BEFORE calling
   ``core.handle``, whether the Evidence Store already carries an ``EVENT_CONSUMED`` record for
   the pulled event's content-addressed identity. If so, the event was already handled in a prior
   process life that crashed after the evidence commit but before the inbox mark — re-handling
   would re-invoke every side effect the flow had (including a real send to the gateway), so this
   path marks the inbox row consumed and moves on, WITHOUT calling ``core.handle`` again.
3. **Egress-result re-injection.** After a ``DECISION_TICK`` is handled, the driver drains any NEW
   results the wired :class:`~tos.egressgw.BrokerEgressGateway` retained (``gateway.results``) and
   ENQUEUES each as a stamped ``EGRESS_RESULT`` event — it never calls ``core.handle`` on a
   drained result directly; the very next drain iteration picks it up through the normal admit
   path, so crash-window idempotency and yield-order stamping apply to it exactly like any other
   event (the pinned grep in ``tos/runtime/tests/engine/test_no_direct_core_calls.py`` enforces
   "no ``.handle(``/``.run(`` outside this module and ``replay.py``").
4. **Timeout injection.** :class:`_TimeoutTracker` tracks, per scope, the monotonic reading at
   which a hand-off went ``POTENTIALLY_LIVE``/``SENT_UNCONFIRMED`` with no result yet; once the
   injected ``max_send_result_wait_ms`` bound elapses with no result, a synthetic
   ``EGRESS_RESULT(kind=TIMEOUT)`` is enqueued (RFC-005 §11 "timeout = UNKNOWN, never rejection").
   The synthetic paper transport is synchronous, so in practice this only fires when a test injects
   a stalled fake transport and advances the injected clock past the bound.

**Outcome digest.** ``EVENT_CONSUMED`` receipts record ``result.outcome_digest`` directly
(Phase 3 A-K-3, landed during this wave — ``tos/src/tos/engine/core.py``'s ``EventResult.outcome_digest``
property). It is the emitted Decision/Proposal's own canonical digest for a ``DECISION_TICK``
that produced one, and honestly ``None`` for every ``EGRESS_RESULT`` (a mutable, non-authoritative
reservation-projection transition has no outcome identity of its own to hash — the kernel's own
choice, not a runtime stand-in). An earlier revision of this module computed its own digest
surrogate before A-K-3 landed; that surrogate is retired now that the real field exists.

**Result application.** Phase 3 A-K-2 (``ResultDisposition``/``ResultApplication`` on
``tos.engine.state.ProvisionalReservationLedger.apply_egress_result``) landed during this wave
too: an orphaned/mismatched/duplicate egress result is a recorded conservative outcome
(``EventResult.result_disposition``), never an ``ArtifactIntegrityError`` crash. This driver's
crash-window/re-injection loop never touches ``apply_egress_result`` directly — it only calls
``core.handle`` and reads the returned ``EventResult`` — so it needed no change either way.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pydantic`` +
``tos.canonical``/``tos.engine``/``tos.egressgw`` + ``tos_runtime.*`` only. No ``shared.*``, no
``tos.backtest``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tos.canonical import ArtifactIntegrityError, CanonicalizationScheme
from tos.engine import EngineCore, EventResult
from tos.engine.records import (
    EgressResultPayload,
    EngineEvent,
    InstrumentKey,
    event_identity,
)
from tos.engine.vocabulary import EgressResultKind, EventKind
from tos.ordering import OrderingEvent

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.sources import MonotonicSource

__all__ = ["EngineDriver"]

#: The runtime-local evidence kind for a driver-recorded consumption receipt. Not a
#: ``tos.engine.vocabulary.EvidenceKind`` member — this is runtime-level evidence about the
#: DURABLE ADMISSION of an event, alongside (never instead of) whatever engine-local evidence
#: ``core.handle`` itself already wrote through its own injected ``EvidenceSink``.
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_EVENT_CONSUMED_RECORD_CLASS = "EVENT_CONSUMED"


class _YieldOrderCounter:
    """One monotone counter stamping every event this driver yields to the core.

    Reimplements ``tos.backtest.driver.YieldOrderCounter``'s documented reasoning locally (see
    module docstring item 1) rather than importing the backtest harness package.
    """

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


@dataclass
class _PendingAttempt:
    """One outstanding, not-yet-resulted attempt this driver is timing (item 4)."""

    attempt_id: str
    started_at_ms: int
    timed_out: bool = False


@dataclass
class _TimeoutTracker:
    """Per-scope pending-attempt bookkeeping for :class:`EngineDriver`'s timeout injection."""

    max_send_result_wait_ms: int | None
    pending: dict[tuple[str, str], _PendingAttempt] = field(default_factory=dict)

    @staticmethod
    def _key(key: InstrumentKey) -> tuple[str, str]:
        return (key.account, key.instrument)

    def observe_handoff(
        self, key: InstrumentKey, *, attempt_id: str, now_ms: int
    ) -> None:
        """Record a fresh SENT_UNCONFIRMED hand-off as pending a result."""
        self.pending[self._key(key)] = _PendingAttempt(
            attempt_id=attempt_id, started_at_ms=now_ms
        )

    def observe_result(self, key: InstrumentKey) -> None:
        """Clear the pending entry once ANY result lands for this scope (at-most-one exposure)."""
        self.pending.pop(self._key(key), None)

    def due(self, *, now_ms: int) -> tuple[tuple[InstrumentKey, str], ...]:
        """Return ``(instrument_key, attempt_id)`` pairs whose wait bound has elapsed and have
        not already been timed out."""
        if self.max_send_result_wait_ms is None:
            return ()
        due: list[tuple[InstrumentKey, str]] = []
        for (account, instrument), pending in self.pending.items():
            if pending.timed_out:
                continue
            if now_ms - pending.started_at_ms >= self.max_send_result_wait_ms:
                pending.timed_out = True
                due.append(
                    (
                        InstrumentKey(account=account, instrument=instrument),
                        pending.attempt_id,
                    )
                )
        return tuple(due)


class EngineDriver:
    """Single-threaded, deterministic driver over a durable :class:`SqliteEventInbox`.

    Owns the yield-order counter, the crash-window idempotency check, the egress-result
    re-injection loop, and timeout injection. This is the ONLY module (besides
    :mod:`tos_runtime.engine.replay`) that may call ``EngineCore.handle``/``run`` in this runtime
    shell — see ``tos/runtime/tests/engine/test_no_direct_core_calls.py``.
    """

    def __init__(
        self,
        *,
        core: EngineCore,
        inbox: SqliteEventInbox,
        evidence_store: SqliteEvidenceStore,
        scheme: CanonicalizationScheme,
        continuity_id: str,
        monotonic_source: MonotonicSource,
        max_send_result_wait_ms: int | None,
    ) -> None:
        """Wire the driver.

        Args:
            core: The composed :class:`~tos.engine.EngineCore` — the SAME core instance for the
                whole process lifetime (the ledger-reinstantiation prohibition
                ``tos.backtest.driver`` documents applies here too, for the same reason).
            inbox: The durable event admission queue.
            evidence_store: The durable evidence store — used both to append this driver's own
                ``EVENT_CONSUMED`` receipts and to detect the crash-window "evidence exists,
                inbox unmarked" condition.
            scheme: The canonicalization scheme used for event identity and the outcome-digest
                stand-in.
            continuity_id: The single stream continuity every coordinate this driver issues
                carries (:class:`_YieldOrderCounter`).
            monotonic_source: The injected monotonic clock for timeout injection (never a direct
                ``time.monotonic()`` read — design #40 D1.1).
            max_send_result_wait_ms: The injected wait bound before a SENT_UNCONFIRMED hand-off is
                timed out; ``None`` disables timeout injection entirely (fail-closed default is
                "never inject", not a hidden numeric default).
        """
        self._core = core
        self._inbox = inbox
        self._evidence_store = evidence_store
        self._scheme = scheme
        self._counter = _YieldOrderCounter(
            continuity_id=continuity_id, seed=inbox.count
        )
        self._time = monotonic_source
        self._timeouts = _TimeoutTracker(
            max_send_result_wait_ms=max_send_result_wait_ms
        )
        #: The send boundary whose retained ``.results`` this driver drains — bound separately
        #: (see :meth:`bind_gateway`) because it does not exist until compose finishes wiring the
        #: rest of the chain that reads from THIS core's own ``transmit`` slot.
        self._gateway: object | None = None
        #: How many of the gateway's retained results this driver has already drained.
        self._drained_results = 0

    def bind_gateway(self, gateway: object) -> None:
        """Attach the send boundary whose retained ``.results`` this driver drains.

        Args:
            gateway: Anything exposing a ``results: tuple[EgressResultPayload, ...]`` attribute in
                production order (:class:`tos.egressgw.BrokerEgressGateway` satisfies this
                structurally — never imported by type here, mirroring
                ``tos.backtest.fills.RetainedEgressResults``'s own "declared locally" seam).
        """
        self._gateway = gateway

    # -- stamping ------------------------------------------------------------

    def _stamp(self, event: EngineEvent) -> EngineEvent:
        """Replace ``event``'s reference with the next yield-order coordinate.

        Mirrors ``tos.backtest.driver._stamped_tick``/``_stamped_egress``: the caller-supplied
        reference is discarded entirely, because only the driver's own single monotone counter
        can guarantee "coordinate order == processing order" across both event kinds.
        """
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

    # -- crash-window recovery ------------------------------------------------

    def _find_consumed_receipt(self, event_id: str) -> tuple[int, int] | None:
        """Scan the evidence store for an existing ``EVENT_CONSUMED`` receipt for ``event_id``.

        Returns:
            ``(evidence_seq, key_generation)`` of the FIRST matching receipt, or ``None``. A
            linear scan over the whole evidence store — acceptable at this wave's scale (hermetic
            tests); a durable index is future work if this ever needs to run against a
            long-lived production store.
        """
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

    def _record_consumed(
        self,
        *,
        event_id: str,
        payload_digest: str,
        outcome_digest: str | None,
        halt_reason: str | None,
    ) -> tuple[int, int]:
        """Durably append this driver's own ``EVENT_CONSUMED`` receipt.

        Returns:
            ``(evidence_seq, key_generation)`` for :meth:`SqliteEventInbox.mark_consumed`.
        """
        receipt = self._evidence_store.append(
            {
                "event_id": event_id,
                "payload_digest": payload_digest,
                "outcome_digest": outcome_digest,
                "halt_reason": halt_reason,
            },
            kind=_EVENT_CONSUMED_KIND,
            record_class=_EVENT_CONSUMED_RECORD_CLASS,
        )
        # A successful SqliteEvidenceStore.append() never returns a receipt with a None seq/
        # key_generation (module docstring's own "a failed or partial append never returns this
        # type") — the type itself stays nullable only because EvidenceAppendReceipt is shared
        # with the pre-durability DRAFT shape elsewhere in tos.evidence.
        assert receipt.seq is not None
        assert receipt.key_generation is not None
        return receipt.seq, receipt.key_generation

    # -- the drain loop --------------------------------------------------------

    def _process_next(self) -> tuple[int, EventResult] | None:
        """Drain crash-window rows, then process exactly one genuinely new event.

        Returns:
            ``(seq, EventResult)`` for the newly handled event, or ``None`` once the inbox has
            nothing left — every already-consumed / crash-window row was already skipped
            internally by this call, so ``None`` always means "genuinely idle".
        """
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
                continue  # crash-window recovery — keep draining, nothing new happened

            result = self._core.handle(event)
            payload_digest = self._scheme.compute_digest(event.model_dump(mode="json"))
            evidence_seq, generation = self._record_consumed(
                event_id=event_id,
                payload_digest=payload_digest,
                outcome_digest=result.outcome_digest,
                halt_reason=(
                    result.halt_reason.value if result.halt_reason is not None else None
                ),
            )
            self._inbox.mark_consumed(
                seq, evidence_seq=evidence_seq, generation=generation
            )

            self._track_timeouts(event, result)
            if event.kind is EventKind.DECISION_TICK:
                self._drain_gateway_results()
            return seq, result

    def run_once(self) -> EventResult | None:
        """Process exactly one pending event to completion, or recover a crash-window row.

        Returns:
            The :class:`~tos.engine.EventResult` for a NEWLY handled event; ``None`` when the
            inbox is idle, OR when the pulled row(s) were already durably consumed in a prior
            process life (crash-window recovery — see module docstring item 2).
        """
        processed = self._process_next()
        return None if processed is None else processed[1]

    def run_until_idle(self) -> tuple[EventResult, ...]:
        """Call :meth:`run_once` until the inbox has nothing left to admit or recover."""
        results: list[EventResult] = []
        while True:
            processed = self._process_next()
            if processed is None:
                return tuple(results)
            results.append(processed[1])

    def enqueue_and_run(self, event: EngineEvent) -> EventResult:
        """Stamp, durably admit, and fully process ``event`` (the compose-root convenience API).

        Returns:
            The :class:`~tos.engine.EventResult` for ``event`` specifically — any re-injected
            follow-on ``EGRESS_RESULT`` events this call triggers are processed too (as a side
            effect, durably recorded) but are not what this call returns.

        Raises:
            ArtifactIntegrityError: If ``event`` is a byte-for-byte duplicate of one already fully
                consumed in a prior call — an idempotent no-op with nothing new to report (module
                docstring item 2's crash-window contract, reachable here only when a caller
                deliberately re-submits identical bytes).
        """
        stamped = self._stamp(event)
        receipt = self._inbox.enqueue(stamped)
        target_seq = receipt.seq
        result_for_target: EventResult | None = None
        while True:
            processed = self._process_next()
            if processed is None:
                break
            seq, result = processed
            if seq == target_seq:
                result_for_target = result
        if result_for_target is None:
            raise ArtifactIntegrityError(
                f"EngineDriver.enqueue_and_run could not produce a fresh EventResult for "
                f"event_id={receipt.event_id!r} (duplicate={receipt.duplicate}) — this exact "
                "event was already durably consumed in a prior call"
            )
        return result_for_target

    # -- egress-result re-injection --------------------------------------------

    def _drain_gateway_results(self) -> None:
        """Enqueue every gateway result produced since the last drain as ``EGRESS_RESULT`` events.

        Only ENQUEUES — it never calls ``core.handle`` itself. The enclosing drain loop
        (:meth:`_process_next`'s caller) picks the newly enqueued row up on its very next
        iteration, exactly like any other admitted event (design plan §1.1).
        """
        gateway = self._gateway
        if gateway is None:
            return
        retained: tuple[EgressResultPayload, ...] = gateway.results  # type: ignore[attr-defined]
        newly_produced = retained[self._drained_results :]
        self._drained_results = len(retained)
        for payload in newly_produced:
            event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
            self._inbox.enqueue(self._stamp(event))

    # -- timeout tracking --------------------------------------------------------

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
        # An EGRESS_RESULT landed for this scope (applied or not) — any pending timeout watch for
        # it is cleared: a late real result is exactly the "TIMEOUT then FILL" scenario the plan
        # requires capacity to stay unchanged for; watching further would only ever re-fire.
        self._timeouts.observe_result(result.instrument_key)

    def _inject_due_timeouts(self) -> None:
        """Enqueue a synthetic ``EGRESS_RESULT(kind=TIMEOUT)`` for every scope past its bound."""
        now_ms = self._time.now_ms()
        for key, attempt_id in self._timeouts.due(now_ms=now_ms):
            payload = EgressResultPayload(
                instrument_key=key, attempt_id=attempt_id, kind=EgressResultKind.TIMEOUT
            )
            event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
            self._inbox.enqueue(self._stamp(event))
