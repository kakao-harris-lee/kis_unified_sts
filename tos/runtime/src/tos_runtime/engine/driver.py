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
2. **Crash-window idempotency, over BOTH windows (independent review finding #3, 2026-09-09).**
   Draining (:meth:`_process_next`) checks, BEFORE calling ``core.handle``, two things: (a)
   whether the Evidence Store already carries an ``EVENT_CONSUMED`` record for the pulled event's
   content-addressed identity — the narrower window, evidence committed but the inbox mark never
   happened; and (b) whether the inbox row itself carries a write-ahead
   ``EVENT_HANDLING_STARTED`` marker with no matching ``EVENT_CONSUMED`` at all — the WIDER
   window: ``core.handle`` may have already run the real flow, including a real send, before the
   crash. Before this fix, only (a) was checked, so a crash strictly between ``core.handle``
   returning and the ``EVENT_CONSUMED`` append (the widest window of the three the module used to
   document) went undetected on restart and the event was silently re-handled — re-invoking every
   side effect the flow had, including re-sending an attempt already handed off (a blind
   resubmit). Case (b) now marks the event durably interrupted (``HANDLING_INTERRUPTED_
   NO_SEND_EVIDENCE`` or, when the flow's own evidence proves it reached the send boundary first,
   ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` — split by re-review finding N1, 2026-09-09)
   instead, never calling ``core.handle`` again — see ``_handle_interrupted_event`` for the split
   and for the residual this does NOT solve (no ledger rebuild; Phase 5 / J3).
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
from tos.engine.vocabulary import (
    EgressResultKind,
    EventKind,
    OrderingAdmission,
    ResultDisposition,
)
from tos.ordering import OrderingEvent

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import (
    NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
    OrthostateProjector,
)
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.rcl.finality_witness import finality_witness_for
from tos_runtime.time.sources import MonotonicSource

__all__ = ["EngineDriver"]

#: The runtime-local evidence kind for a driver-recorded consumption receipt. Not a
#: ``tos.engine.vocabulary.EvidenceKind`` member — this is runtime-level evidence about the
#: DURABLE ADMISSION of an event, alongside (never instead of) whatever engine-local evidence
#: ``core.handle`` itself already wrote through its own injected ``EvidenceSink``.
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_EVENT_CONSUMED_RECORD_CLASS = "EVENT_CONSUMED"

#: The write-ahead marker (independent review finding #3, 2026-09-09): durably recorded BEFORE
#: ``core.handle`` is ever called for a genuinely new event, so a crash between the call and the
#: ``EVENT_CONSUMED`` receipt is distinguishable, on restart, from "never started" — see
#: ``_handle_interrupted_event`` below.
_EVENT_HANDLING_STARTED_KIND = "EVENT_HANDLING_STARTED"
_EVENT_HANDLING_STARTED_RECORD_CLASS = "EVENT_HANDLING_STARTED"

#: The halt reason recorded on the durable ``EVENT_CONSUMED`` receipt when an interrupted
#: event's OWN durable evidence proves the flow never reached (or could not be proven to have
#: reached) the send boundary before the crash (re-review finding N1, 2026-09-09). Before N1,
#: this branch shared the ambiguous, mis-scoped ``HANDLING_INTERRUPTED_POSSIBLY_LIVE`` name with
#: the genuinely-possibly-live case below — a name that overclaimed risk for the strictly SAFER
#: of the two windows (marker recorded, then a crash before ``core.handle`` ever ran, so the
#: DECISION_TICK that was interrupted is simply never evaluated) while giving no durable,
#: non-scanning signal that a tick was silently dropped. Never reachable from inside the kernel
#: — this is runtime-local vocabulary, not a ``tos.engine.vocabulary.HaltReason`` member.
_HANDLING_INTERRUPTED_NO_SEND_EVIDENCE_REASON = "HANDLING_INTERRUPTED_NO_SEND_EVIDENCE"

#: The additional, dual-path (sqlite + emergency-log) HALT kind — and, since N1, the durable
#: ``EVENT_CONSUMED`` receipt's own ``halt_reason`` too — recorded when the flow that was
#: interrupted had ALREADY reached the send boundary (the genuinely dangerous case): an attempt
#: whose broker-side fate is genuinely unknown, not merely an interrupted no-op.
_HANDLING_INTERRUPTED_SEND_POSSIBLY_LIVE_KIND = (
    "HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND"
)

#: Re-review finding N1 (2026-09-09): a non-halt, durably-queryable evidence row appended
#: alongside the ``HANDLING_INTERRUPTED_NO_SEND_EVIDENCE`` receipt above, so "a DECISION_TICK
#: was interrupted before evaluation and will never be evaluated" is visible directly (by
#: ``kind``) rather than requiring an operator to scan for the specific halt-reason STRING
#: buried inside an ``EVENT_CONSUMED`` receipt's payload. This is evidence about a fact, not a
#: halt: the driver's own crash-window contract (module docstring item 2) already treats this
#: window as conservatively closed out (never re-handled), so nothing further blocks progress —
#: the row exists purely for operator visibility of the silent loss.
_DECISION_TICK_DROPPED_ON_RECOVERY_KIND = "DECISION_TICK_DROPPED_ON_RECOVERY"

#: Evidence kinds that prove the interrupted flow reached (or passed) the send boundary before
#: the crash: the gateway's own pre-``SEND_STARTED`` write (``tos.egressgw.gateway`` — a raw
#: string kind, not a kernel ``EvidenceKind`` member) and the engine sequencer's own
#: ``EvidenceKind.SEND_HANDED_OFF`` (``tos.engine.sequencer``). Both are written by stages/sinks
#: bound to the SAME durable evidence store this driver reads (independent review finding #2's
#: own measurement: "each stage carries its own sink bound to the real SqliteEvidenceStore").
_SEND_EVIDENCE_KINDS: tuple[str, ...] = ("SEND_STARTED", "SEND_HANDED_OFF")

#: Evidence kinds this driver appends when :class:`~tos_runtime.posttrade.finality
#: .SyntheticFinalityProducer` produces a proof for a genuinely-``APPLIED`` ``EGRESS_RESULT``
#: (team-lead CR-4 dispatch, plan §2.2). Not kernel ``EvidenceKind`` members — this is
#: runtime-level evidence about a SYNTHETIC-transport artifact the kernel's own posttrade
#: package never emits itself (``tos_runtime.posttrade.finality``'s own module docstring).
_ECONOMIC_OBLIGATION_KIND = "ECONOMIC_OBLIGATION"
_POSTTRADE_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"


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

    #: The injected wait bound; always a concrete positive int (independent review finding #14
    #: — a ``None`` "disable injection entirely" escape hatch read as a fail-CLOSED default in
    #: the docstring it used to carry, but never injecting a TIMEOUT for a lost result is
    #: fail-SILENT (the attempt just sits ``SENT_UNCONFIRMED`` forever with no further evidence),
    #: not fail-closed. Compose has always supplied a concrete value anyway
    #: (``TrustworthyTimeConfig.max_send_result_wait_ms`` is itself non-optional and
    #: ``load_time_config`` refuses a null — ``time/config.py``), so this only removes an
    #: escape hatch nothing production-shaped ever used; a test that wants "never fires" now
    #: passes a very large bound instead of ``None``.
    max_send_result_wait_ms: int
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

    def observe_result(self, key: InstrumentKey, *, attempt_id: str) -> None:
        """Clear the pending entry ONLY when it names the SAME attempt (independent review
        finding #7).

        Before this fix, ANY ``EGRESS_RESULT`` landing for the scope popped the pending entry —
        "applied or not", including a result naming a completely different (foreign/mismatched)
        attempt. The kernel itself refuses to apply such a result
        (``ResultDisposition.MISMATCHED_ATTEMPT`` / ``ORPHAN_NO_RESERVATION``), but the timeout
        watch for the GENUINELY pending attempt was silenced anyway — a lost result for the real
        attempt would then never surface as a ``TIMEOUT``, defeating the "결과 유실 ⇒ TIMEOUT"
        guarantee (plan §1.1) via any wrong-attempt-id result. Only an exact ``attempt_id`` match
        clears the watch now.
        """
        tracker_key = self._key(key)
        pending = self.pending.get(tracker_key)
        if pending is not None and pending.attempt_id == attempt_id:
            del self.pending[tracker_key]

    def due(self, *, now_ms: int) -> tuple[tuple[InstrumentKey, str], ...]:
        """Return ``(instrument_key, attempt_id)`` pairs whose wait bound has elapsed and have
        not already been timed out."""
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
        emergency_log: EmergencyAppendLog,
        scheme: CanonicalizationScheme,
        continuity_id: str,
        monotonic_source: MonotonicSource,
        max_send_result_wait_ms: int,
        orthostate_projector: OrthostateProjector,
        finality_producer: SyntheticFinalityProducer,
    ) -> None:
        """Wire the driver.

        Args:
            core: The composed :class:`~tos.engine.EngineCore` — the SAME core instance for the
                whole process lifetime (the ledger-reinstantiation prohibition
                ``tos.backtest.driver`` documents applies here too, for the same reason).
            inbox: The durable event admission queue.
            evidence_store: The durable evidence store — used both to append this driver's own
                ``EVENT_HANDLING_STARTED``/``EVENT_CONSUMED`` receipts and to detect the two
                crash-window conditions (see ``_process_next``'s own docstring).
            emergency_log: The sqlite-independent dual-path HALT log (independent review
                finding #3) — used only for the "possibly live" crash-window case, where the
                interrupted flow had already reached the send boundary before the crash.
            scheme: The canonicalization scheme used for event identity and the outcome-digest
                stand-in.
            continuity_id: The single stream continuity every coordinate this driver issues
                carries (:class:`_YieldOrderCounter`).
            monotonic_source: The injected monotonic clock for timeout injection (never a direct
                ``time.monotonic()`` read — design #40 D1.1).
            max_send_result_wait_ms: The injected wait bound before a SENT_UNCONFIRMED hand-off is
                timed out (independent review finding #14: this used to be ``int | None`` with a
                ``None`` "disable injection" escape hatch documented as a "fail-closed default" —
                never injecting a TIMEOUT for a lost result is fail-SILENT, not fail-closed, and
                compose has always supplied a concrete value anyway. A caller that genuinely wants
                "never fires within this test" now passes a very large bound instead.
            orthostate_projector: Projects every genuinely-``APPLIED`` ``EGRESS_RESULT`` onto the
                ADR-002-005 orthostate dimensions (team-lead CR-4 dispatch, plan §2.2) — REQUIRED
                (no default): an omitted projector is a silent absence, not a valid "off" mode
                (:mod:`tos_runtime.engine.orthostate_projection`'s own coupling-safety property
                only holds if this actually runs on every applied result).
            finality_producer: Produces a SYNTHETIC post-trade finality proof for a ``FULL_FILL``
                (team-lead CR-4 dispatch, plan §2.2) — REQUIRED (no default), for the same reason
                as ``orthostate_projector`` (:mod:`tos_runtime.posttrade.finality`).
        """
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
        #: The send boundary whose retained ``.results`` this driver drains — bound separately
        #: (see :meth:`bind_gateway`) because it does not exist until compose finishes wiring the
        #: rest of the chain that reads from THIS core's own ``transmit`` slot.
        self._gateway: object | None = None
        #: How many of the gateway's retained results this driver has already drained.
        self._drained_results = 0
        #: Re-entrancy guard (re-review finding N3, 2026-09-09): ``True`` for the entire duration
        #: of one :meth:`_process_next` call. ``_send_evidence_exists_after``'s soundness (see its
        #: own docstring) depends on this driver never pulling a second event while the first
        #: one's bookkeeping is still in flight — a re-entrant call (e.g. something reachable from
        #: ``core.handle`` itself calling back into ``run_once``/``run_until_idle``/
        #: ``enqueue_and_run``) would let a second event's own send evidence be misattributed to
        #: the first. Structurally unreachable, not merely undocumented: the guard raises rather
        #: than silently nesting.
        self._draining = False

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
            tests). Independent review finding #13: this specific lookup cannot be made O(1) the
            way :meth:`SqliteEventInbox.handling_started_receipt` now is for the NEW
            ``EVENT_HANDLING_STARTED`` marker below, because the whole reason this path runs is
            that the inbox row's OWN ``consumed_evidence_seq`` column is still ``NULL`` (the
            crash happened between the evidence commit and the inbox mark) — there is nothing on
            the inbox row itself to index against yet. Genuinely indexing this would mean adding
            an ``event_id``-keyed column to ``tos_runtime.evidence.store``'s ``entries`` table,
            which is out of this lane's file ownership for this review round; a durable index
            there is future work if this ever needs to run against a long-lived production store.
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

    def _send_evidence_exists_after(self, marker_seq: int) -> bool:
        """Whether any ``SEND_STARTED``/``SEND_HANDED_OFF`` evidence was durably recorded after
        ``marker_seq`` (the interrupted event's own ``EVENT_HANDLING_STARTED`` receipt) — proof
        that the interrupted flow reached the send boundary before the crash (finding #3).

        **Soundness invariant (re-review finding N3, 2026-09-09).** This is a ``seq >
        marker_seq`` scan, not a query keyed to the specific event/attempt that owns
        ``marker_seq`` — it is sound ONLY because :class:`EngineDriver` is single-threaded and
        completes one event's full bookkeeping (``core.handle`` through the ``EVENT_CONSUMED``
        append) before ever pulling the next row (module docstring item 2; :meth:`_process_next`
        is the sole drain entry point, guarded non-reentrant by :attr:`_draining` below). Under
        that invariant, any send evidence appended after this marker's own seq can only belong to
        the SAME in-flight event this marker was written for — nothing else could have run
        concurrently to append unrelated send evidence in between. A concurrent or re-entrant
        driver would break this reasoning (a second event's own send evidence could be
        misattributed to this one), which is exactly what :attr:`_draining` exists to make
        structurally unreachable rather than merely undocumented.
        """
        placeholders = ",".join("?" for _ in _SEND_EVIDENCE_KINDS)
        cur = self._evidence_store.connection.execute(
            f"SELECT 1 FROM entries WHERE kind IN ({placeholders}) AND seq > ? LIMIT 1",
            (*_SEND_EVIDENCE_KINDS, marker_seq),
        )
        return cur.fetchone() is not None

    def _handle_interrupted_event(
        self, *, seq: int, event_id: str, event: EngineEvent, marker_seq: int
    ) -> None:
        """Recover a crash between the write-ahead ``EVENT_HANDLING_STARTED`` marker and the
        ``EVENT_CONSUMED`` receipt (independent review finding #3, the WIDEST of the three crash
        windows: ``core.handle`` may have already run the real flow — including a real send —
        before the crash).

        Never re-handles the event (that would be a blind resubmit of a possibly-already-sent
        attempt). Splits into two durably-distinguished outcomes (re-review finding N1,
        2026-09-09 — before N1 both shared one ambiguous ``HANDLING_INTERRUPTED_POSSIBLY_LIVE``
        name):

        * **No send evidence found** (:meth:`_send_evidence_exists_after` is ``False`` — the
          marker was written but the flow never reached, or cannot be proven to have reached, the
          send boundary before the crash; this is also the ordinary "crashed before
          ``core.handle`` even ran" case): the receipt's ``halt_reason`` becomes
          ``HANDLING_INTERRUPTED_NO_SEND_EVIDENCE`` and an ADDITIONAL, non-halt
          ``DECISION_TICK_DROPPED_ON_RECOVERY`` evidence row is appended so the silent loss of
          this tick is durably visible by ``kind`` alone, without an operator having to scan
          ``EVENT_CONSUMED`` payloads for a halt-reason string.
        * **Send evidence found** (the flow provably reached the send boundary): the receipt's
          ``halt_reason`` becomes ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` and — unchanged from
          before N1 — an ADDITIONAL dual-path (sqlite + emergency-log)
          ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` HALT is durably recorded naming the
          possibly-live attempt for operator attention.

        ⚠ **Residual, disclosed (design #31 §2.1(iii) J3 crash-recovery — provisional, §9
        deferred).** This method does NOT rebuild the in-memory reservation ledger's state for
        the possibly-live attempt — the ledger a freshly-restarted process holds is empty
        regardless of this marking, exactly the same residual :mod:`tos_runtime.engine.replay`'s
        own module docstring already discloses for the send boundary. A conservative ledger
        rebuild from durable evidence (so a possibly-live attempt keeps occupying its scope's
        at-most-one exposure slot across a restart) is Phase 5 / J3 work, not this wave's.
        """
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
        )
        self._inbox.mark_consumed(seq, evidence_seq=evidence_seq, generation=generation)

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

    def _new_risk_halted_result(
        self, event: EngineEvent, halted: dict[str, object]
    ) -> EventResult:
        """Independent review finding #3: the synthetic ``EventResult`` returned for a
        ``DECISION_TICK`` refused by the durable new-risk halt latch — ``core.handle`` is never
        called for it. ``halt_reason`` stays ``None`` here (the kernel's ``HaltReason`` is a
        closed enum this runtime-level latch is not a member of); the reason lives in ``detail``
        and, durably, in the ``EVENT_CONSUMED`` receipt's own string ``halt_reason`` field
        (:meth:`_record_consumed` takes a plain ``str``, not the kernel enum).

        Re-review finding R3 (2026-09-09): the ``detail`` text used to say clearing this latch
        was deferred to "Phase 5" — no longer true. The re-arm path is
        :meth:`~tos_runtime.compose._types.ComposedRuntime.clear_new_risk_halt` (or, at the
        storage layer, :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`),
        available now; the ``detail`` text below names it.
        """
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

    # -- the drain loop --------------------------------------------------------

    def _process_next(self) -> tuple[int, EventResult] | None:
        """Drain crash-window rows, then process exactly one genuinely new event.

        Two crash windows are recovered here, mirroring exactly what a real process restart
        observes (the in-memory core/ledger reset to empty; the two sqlite files retain
        everything durably committed):

        1. **Evidence committed, inbox mark never happened** (``_find_consumed_receipt``) — the
           narrower window; ``core.handle`` genuinely completed and its ``EVENT_CONSUMED``
           receipt exists, so this just marks the row and moves on.
        2. **Handling started, no ``EVENT_CONSUMED`` receipt at all** (``handling_started_receipt``
           — independent review finding #3, the WIDEST window: ``core.handle`` may have already
           run the real flow, including a real send, before the crash. Re-handling would be a
           blind resubmit of a possibly-already-sent attempt — see ``_handle_interrupted_event``.

        Returns:
            ``(seq, EventResult)`` for the newly handled event, or ``None`` once the inbox has
            nothing left — every already-consumed / crash-window row was already skipped
            internally by this call, so ``None`` always means "genuinely idle".

        Raises:
            ArtifactIntegrityError: If this driver is called re-entrantly (re-review finding N3 —
                see :attr:`_draining` and ``_send_evidence_exists_after``'s own docstring for why
                single-threaded, non-overlapping drains are a soundness invariant, not merely a
                convention).
        """
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
                    continue  # crash-window recovery — keep draining, nothing new happened

                interrupted = self._inbox.handling_started_receipt(seq)
                if interrupted is not None:
                    marker_seq, _marker_generation = interrupted
                    self._handle_interrupted_event(
                        seq=seq, event_id=event_id, event=event, marker_seq=marker_seq
                    )
                    continue  # crash-window recovery — keep draining, nothing NEW happened

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
                        # Independent review finding #3 (2026-09-09): a durably-latched
                        # coupling/ownership violation blocks every NEW DECISION_TICK — never
                        # core.handle at all for it (the tick is refused, not evaluated; nothing
                        # is consumed, mirroring the kernel's own Coordinator-gate refusal
                        # contract). An EGRESS_RESULT is NEVER refused this way (see the branch
                        # below, unreached for that kind) — results still apply; knowledge may
                        # improve even while new risk stays blocked. Clearing this latch is an
                        # explicit operator action (re-review finding R3) — see
                        # ComposedRuntime.clear_new_risk_halt / SqliteEventInbox
                        # .clear_new_risk_halt; nothing here clears it automatically.
                        result = self._new_risk_halted_result(event, halted)
                        evidence_seq, generation = self._record_consumed(
                            event_id=event_id,
                            payload_digest=payload_digest,
                            outcome_digest=None,
                            halt_reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
                        )
                        self._inbox.mark_consumed(
                            seq, evidence_seq=evidence_seq, generation=generation
                        )
                        return seq, result

                result = self._core.handle(event)
                evidence_seq, generation = self._record_consumed(
                    event_id=event_id,
                    payload_digest=payload_digest,
                    outcome_digest=result.outcome_digest,
                    halt_reason=(
                        result.halt_reason.value
                        if result.halt_reason is not None
                        else None
                    ),
                )
                self._inbox.mark_consumed(
                    seq, evidence_seq=evidence_seq, generation=generation
                )

                self._track_timeouts(event, result)
                self._project_orthostate_and_finality(event, result)
                if event.kind is EventKind.DECISION_TICK:
                    self._drain_gateway_results()
                return seq, result
        finally:
            self._draining = False

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
        # An EGRESS_RESULT landed for this scope. The watch is cleared ONLY when the result was
        # genuinely APPLIED to the exact attempt being watched (independent review finding #7,
        # task disposition: "clears only when result.result_disposition is APPLIED AND
        # attempt_id equals the tracked one"). A late real APPLIED result for the SAME attempt is
        # exactly the "TIMEOUT then FILL" scenario the plan requires capacity to stay unchanged
        # for; a result for a DIFFERENT attempt, or one the kernel itself refused to apply
        # (MISMATCHED_ATTEMPT / ORPHAN_NO_RESERVATION / DUPLICATE / a rank- or quantity-regressing
        # disposition), must not silence the genuinely pending watch.
        if result.result_disposition is not ResultDisposition.APPLIED:
            return
        payload = event.egress_result
        assert (
            payload is not None
        )  # guaranteed by EngineEvent validation for EGRESS_RESULT
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

    # -- orthostate + post-trade finality projection (team-lead CR-4, plan §2.2) --

    def _project_orthostate_and_finality(
        self, event: EngineEvent, result: EventResult
    ) -> None:
        """Project one processed event onto orthostate and, for a genuinely-applied
        ``FULL_FILL``, a SYNTHETIC post-trade finality proof — the wiring the CR-3 modules
        (``tos_runtime.engine.orthostate_projection``, ``tos_runtime.posttrade.finality``,
        ``tos_runtime.rcl.finality_witness``) shipped isolated and tested but unreachable from
        this driver.

        Called unconditionally, right after every freshly-handled event's own
        ``EVENT_CONSUMED`` receipt is durable (never on a crash-window recovery path, which
        never calls ``core.handle`` at all and so has no fresh ``EventResult`` to project) —
        exactly the same placement as :meth:`_track_timeouts`, which this mirrors.

        :meth:`~tos_runtime.engine.orthostate_projection.OrthostateProjector.project` itself
        no-ops for a ``DECISION_TICK`` or a non-``APPLIED`` result, so this method calls it
        unconditionally; the ``FULL_FILL``-only finality-proof gate below is this method's own
        (mirroring :meth:`_track_timeouts`'s own APPLIED-only gate for the SAME reason: a
        non-``APPLIED`` result's ``EgressResultPayload`` still carries an attempt id and a
        ``FULL_FILL`` kind by construction, but was never actually accepted onto THIS
        attempt's reservation — producing a proof from it would assert finality for a fill the
        kernel itself refused).

        The durable ``attempt_finality_witness`` row is written for every genuinely-applied
        ``EGRESS_RESULT`` (not only a ``FULL_FILL``) so a later, non-proof-bearing result for
        the same attempt (e.g. a ``TIMEOUT``) does not leave a stale prior witness readable —
        :func:`~tos_runtime.rcl.finality_witness.finality_witness_for` itself always returns
        the correct value (``True`` only for THIS producer call's own proof, ``None``
        otherwise), so writing it unconditionally on every applied result can only ever
        record the CURRENT truth, never a stale one.

        No release-trigger call site exists yet anywhere in this runtime to CONSUME this durable
        witness (measured, ``tos_runtime.rcl.finality_witness``'s own module docstring survey) —
        that consumption is Phase 5's; this method's job ends at durably recording the proof and
        the witness so that future lane can read them.
        """
        self._orthostate_projector.project(event=event, result=result)
        if event.kind is not EventKind.EGRESS_RESULT:
            return
        if result.result_disposition is not ResultDisposition.APPLIED:
            return
        payload = event.egress_result
        assert (
            payload is not None
        )  # guaranteed by EngineEvent validation for EGRESS_RESULT

        produced = self._finality_producer.produce(payload)
        witness = finality_witness_for(None if produced is None else produced.proof)
        self._inbox.record_finality_witness(payload.attempt_id, witness)
        if produced is None:
            return
        self._evidence_store.append(
            produced.record.model_dump(mode="json"),
            kind=_ECONOMIC_OBLIGATION_KIND,
            record_class=_ECONOMIC_OBLIGATION_KIND,
        )
        self._evidence_store.append(
            produced.proof.model_dump(mode="json"),
            kind=_POSTTRADE_FINALITY_PROOF_KIND,
            record_class=_POSTTRADE_FINALITY_PROOF_KIND,
        )
