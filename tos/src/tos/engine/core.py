"""The single, synchronous, deterministic event core (design #31 §2 / D5).

**One event is processed to completion before the next.** Slice #1's core is synchronous and
single-threaded, and asynchronous I/O is isolated at the D-E4 send boundary with its result
re-injected as an ``EGRESS_RESULT`` event (design #31 §2.1). Three reasons, all from the design:

* **determinism** — RFC-003 §10:345-348 requires an independent re-execution over the exact
  recorded Decision Context, policy version, and configuration version to reconstruct the same
  outcome. A synchronous core makes that trivially true and removes the whole race-induced wiring
  fail-open class;
* **backtest / live parity** — a backtest replaying historical bars and a paper run share **this
  same core and this same sequencer**; only the event source and the egress sink differ
  (design #31 §2.1/§12);
* **envelope** — the workload is bar-scale and single-venue; a nanosecond async loop buys nothing.

**No wall clock.** The core never calls ``time`` / ``datetime``: its time is the reference
coordinate the event carries (design #31 §2.3). :mod:`tos.time` is itself clock-free, so freshness
is a pure function of injected coordinates.

**Closed vocabulary.** Dispatch is positive membership over :class:`~tos.engine.vocabulary.EventKind`
handlers; an unknown kind is a fail-closed error, never a silent drop (design #31 §2.2/§7.2-7).

**Causal order.** The core consumes monotonically: an event whose ordering coordinates positively
establish that it *precedes* the last consumed one is refused
(:func:`~tos.ordering.compare_order`). An *ambiguous* pair is recorded and admitted rather than
refused — an "cannot order" is not a proven reversal, and refusing it would be the #26 WDR MAJOR-1
over-rejection defect; the exposure risk it might carry is separately sealed by the at-most-one
retention and by the positive attempt-identity match on result consumption (design #31 §2.1(ii)).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tos.capsule import DecisionContextCapsule
from tos.engine._base import ArtifactIntegrityError, CanonicalizationScheme, get_scheme
from tos.engine.pipeline import PipelineResult, run_decision_pipeline
from tos.engine.records import (
    DecisionTickPayload,
    EgressResultPayload,
    EngineConfiguration,
    EngineEvent,
    EngineEvidenceRecord,
    InstrumentKey,
    ProvisionalReservation,
    RegisteredStrategy,
)
from tos.engine.registry import StrategyRegistry
from tos.engine.sequencer import (
    CommitmentStep,
    FlowResult,
    Stage,
    Transmit,
    run_commitment_flow,
    validate_stage_map,
)
from tos.engine.sink import EvidenceSink, NullEvidenceSink
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    ADMISSIBLE_EVENT_KINDS,
    DispatchResolution,
    EventKind,
    EvidenceKind,
    HaltReason,
    OrderingAdmission,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "DecisionContextResolver",
    "EngineCore",
    "EventBatch",
    "EventResult",
    "EventSource",
    "UnknownEventKindError",
    "admit_kind",
    "ordering_admission",
]


@runtime_checkable
class DecisionContextResolver(Protocol):
    """The D-E2 plug that fills a ``DECISION_TICK`` payload (design #31 §12-1).

    ``(capsule, instrument_key) -> DecisionTickPayload``: resolve the Capsule's ``SnapshotRef``
    into the value-carrying Critical Input observations (with source identity, continuity, and
    provenance) and attach the reference time coordinates.

    ⚠ **The slot only.** The value surface itself — a ``CriticalInputSnapshot`` body carrying
    admitted observations — does **not** exist yet and is D-E2's to add (design #31 §3.2 (4)).
    Inventing it here would be over-realization, and inventing a third ``"market"`` context source
    was explicitly rejected (§3.2 alternative C). What D-E1 fixes is the **contract**: market-derived
    values reach a policy only through the ``"capsule"`` source, never relabelled as configuration
    (RFC-004 §9:242-244; RFC-008 §10:327-331).
    """

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Resolve one Decision Context into a tick payload."""
        ...


@runtime_checkable
class EventSource(Protocol):
    """The plug that supplies events to the core (design #31 §12-4).

    A backtest (D-E3) iterates historical bars; a paper run (D-E4) iterates a live feed. The core
    cannot tell them apart — that indistinguishability *is* the backtest/live parity claim
    (design #31 §2.1/§12). Any iterable of :class:`~tos.engine.records.EngineEvent` satisfies it,
    which is why :meth:`EngineCore.run` takes a plain ``Iterable``.
    """

    def __iter__(self) -> Iterator[EngineEvent]:
        """Yield events in causal order."""
        ...


#: A ready-made in-memory :class:`EventSource` (a bar replay, a fixture stream, a test double).
EventBatch = tuple[EngineEvent, ...]


class UnknownEventKindError(ArtifactIntegrityError):
    """An event kind outside the closed vocabulary reached the dispatcher (design #31 §2.2).

    Raised — never swallowed. Silently dropping an unrecognised event is the classic wiring
    fail-open: the system would keep running while an entire class of event vanished.
    """


def admit_kind(kind: object) -> EventKind:
    """Resolve an event kind by **positive membership** in the closed vocabulary.

    Args:
        kind: The candidate kind (an :class:`~tos.engine.vocabulary.EventKind`, its string value,
            or anything else).

    Returns:
        The admitted :class:`~tos.engine.vocabulary.EventKind`.

    Raises:
        UnknownEventKindError: For anything not positively in
            :data:`~tos.engine.vocabulary.ADMISSIBLE_EVENT_KINDS` **or** for an admissible member
            with no registered handler — a vocabulary member the core cannot actually process is
            an unhandled event, not a no-op.
    """
    if isinstance(kind, EventKind) and kind in ADMISSIBLE_EVENT_KINDS:
        return kind
    raise UnknownEventKindError(
        f"event kind {kind!r} is not in the closed engine vocabulary "
        f"{sorted(member.value for member in ADMISSIBLE_EVENT_KINDS)} — an unknown kind is a "
        "fail-closed error, never a silent drop (design #31 §2.2)"
    )


def ordering_admission(
    last: OrderingEvent | None, incoming: OrderingEvent
) -> OrderingAdmission:
    """Classify an incoming event's causal order against the last consumed one (§2.1(ii)).

    Args:
        last: The last consumed event's ordering coordinates (``None`` for the first event).
        incoming: The incoming event's ordering coordinates.

    Returns:
        ``MONOTONE`` when the incoming event positively follows the last one (or is the first),
        ``REVERSED`` when it positively precedes it, ``AMBIGUOUS`` when the §11 ordering bases do
        not establish an order at all.
    """
    if last is None:
        return OrderingAdmission.MONOTONE
    order = compare_order(incoming, last)
    if order is Ordering.BEFORE:
        return OrderingAdmission.REVERSED
    if order is Ordering.AFTER:
        return OrderingAdmission.MONOTONE
    return OrderingAdmission.AMBIGUOUS


@dataclass(frozen=True)
class EventResult:
    """What one event produced (design #31 §2).

    Every terminal shape is named: ``halt_reason`` records why nothing further happened, and
    ``pipeline`` / ``flow`` / ``reservation`` carry whichever stage the event actually reached.
    """

    kind: EventKind
    instrument_key: InstrumentKey
    ordering: OrderingAdmission
    halt_reason: HaltReason | None = None
    pipeline: PipelineResult | None = None
    flow: FlowResult | None = None
    reservation: ProvisionalReservation | None = None
    detail: str | None = None


class EngineCore:
    """The synchronous, deterministic single event core (design #31 §2).

    Backtest (D-E3) and paper (D-E4) run **this** core with **this** sequencer; only the event
    source, the injected stages, and the transmit sink differ (design #31 §12).
    """

    def __init__(
        self,
        *,
        registry: StrategyRegistry,
        stages: Mapping[CommitmentStep, Stage],
        configuration: EngineConfiguration,
        ledger: ProvisionalReservationLedger | None = None,
        transmit: Transmit | None = None,
        sink: EvidenceSink | None = None,
        scheme: CanonicalizationScheme | None = None,
    ) -> None:
        """Wire the core.

        Args:
            registry: The instrument-keyed strategy registry.
            stages: The injected step → stage mapping for steps 2-11, 13, 14.
            configuration: The injected engine configuration (every bound arrives here).
            ledger: The provisional reservation projection; built from the configured
                ``max_unresolved_send_per_scope`` when omitted.
            transmit: The injected send-boundary hand-off; ``None`` stops every flow after step 14.
            sink: The provisional evidence sink (a discarding sink when omitted).
            scheme: The canonicalization scheme; resolved from the configured version when omitted.

        Raises:
            ArtifactIntegrityError: If the stage map breaches a Coordinator structural seal, or if
                the configured canonicalization version is not registered.
        """
        validate_stage_map(stages)
        self._registry = registry
        self._stages = dict(stages)
        self._configuration = configuration
        self._ledger = ledger or ProvisionalReservationLedger(
            max_unresolved_send_per_scope=configuration.max_unresolved_send_per_scope
        )
        self._transmit = transmit
        self._sink: EvidenceSink = sink or NullEvidenceSink()
        self._scheme = scheme or get_scheme(configuration.canonicalization_version)
        self._last_reference: OrderingEvent | None = None

    @property
    def ledger(self) -> ProvisionalReservationLedger:
        """The provisional, non-authoritative reservation projection."""
        return self._ledger

    def run(self, events: Iterable[EngineEvent]) -> tuple[EventResult, ...]:
        """Process events one at a time, each to completion, in the given order.

        Args:
            events: The event stream (a backtest bar replay or a live feed — the core cannot tell).

        Returns:
            One :class:`EventResult` per event, in order.
        """
        return tuple(self.handle(event) for event in events)

    def handle(self, event: EngineEvent) -> EventResult:
        """Process exactly one event to completion (design #31 §2.1).

        Args:
            event: The event.

        Returns:
            The :class:`EventResult`.

        Raises:
            UnknownEventKindError: If the event's kind is outside the closed vocabulary.
        """
        kind = admit_kind(event.kind)
        key = event.instrument_key()
        reference = event.reference()

        admission = ordering_admission(self._last_reference, reference)
        if admission is OrderingAdmission.REVERSED:
            detail = (
                "the incoming event positively precedes the last consumed one — the core consumes "
                "monotonically (design #31 §2.1(ii))"
            )
            self._sink.record(
                EngineEvidenceRecord(
                    kind=EvidenceKind.EVENT_REFUSED,
                    instrument_key=key,
                    halt_reason=HaltReason.EVENT_ORDER_REVERSED,
                    detail=detail,
                )
            )
            return EventResult(
                kind=kind,
                instrument_key=key,
                ordering=admission,
                halt_reason=HaltReason.EVENT_ORDER_REVERSED,
                detail=detail,
            )
        self._last_reference = reference

        handler = self._handlers().get(kind)
        if handler is None:  # pragma: no cover - admit_kind + this map are the same closure
            raise UnknownEventKindError(
                f"no handler is registered for admissible event kind {kind!r} — an unhandled "
                "vocabulary member is a fail-closed error (design #31 §2.2)"
            )
        return handler(event, admission)

    def _handlers(
        self,
    ) -> dict[EventKind, Callable[[EngineEvent, OrderingAdmission], EventResult]]:
        """The positive-membership handler map — the closed-vocabulary dispatcher."""
        return {
            EventKind.DECISION_TICK: self._handle_decision_tick,
            EventKind.EGRESS_RESULT: self._handle_egress_result,
        }

    # -- DECISION_TICK -------------------------------------------------------

    def _handle_decision_tick(
        self, event: EngineEvent, admission: OrderingAdmission
    ) -> EventResult:
        """Run the decision pipeline and, for a Proposal, the 19-step commitment flow."""
        payload = event.decision_tick
        if payload is None:  # pragma: no cover - guaranteed by EngineEvent validation
            raise UnknownEventKindError("DECISION_TICK event carries no payload (fail-closed)")
        key = payload.instrument_key

        dispatch = self._registry.resolve(key)
        if dispatch.resolution is not DispatchResolution.DISPATCHED:
            halt = (
                HaltReason.REGISTRY_MISSING
                if dispatch.resolution is DispatchResolution.MISSING
                else HaltReason.REGISTRY_EXPLICIT_EMPTY
            )
            detail = (
                "no registry entry is declared for this instrument key — nothing is evaluated "
                "(fail-closed)"
                if halt is HaltReason.REGISTRY_MISSING
                else "the key is declared with zero strategies — a defined no-action, materially "
                "different from a missing key (design #31 §6 ∅ 양방향)"
            )
            self._sink.record(
                EngineEvidenceRecord(
                    kind=EvidenceKind.DECISION_WITHHELD,
                    instrument_key=key,
                    halt_reason=halt,
                    detail=detail,
                )
            )
            return EventResult(
                kind=EventKind.DECISION_TICK,
                instrument_key=key,
                ordering=admission,
                halt_reason=halt,
                detail=detail,
            )

        return self._run_entries(payload, dispatch.entries, admission)

    def _run_entries(
        self,
        payload: DecisionTickPayload,
        entries: tuple[RegisteredStrategy, ...],
        admission: OrderingAdmission,
    ) -> EventResult:
        """Run each registered strategy for the key; the first Proposal starts the flow."""
        key = payload.instrument_key
        last_pipeline: PipelineResult | None = None
        for entry in entries:
            pipeline = run_decision_pipeline(
                entry=entry,
                payload=payload,
                configuration=self._configuration,
                scheme=self._scheme,
                sink=self._sink,
            )
            last_pipeline = pipeline
            if pipeline.proposal is None:
                continue
            flow = run_commitment_flow(
                proposal_id=pipeline.proposal.proposal_id,
                proposal=pipeline.proposal,
                instrument_key=key,
                reference=payload.reference,
                stages=self._stages,
                transmit=self._transmit,
                ledger=self._ledger,
                sink=self._sink,
                scheme=self._scheme,
            )
            return EventResult(
                kind=EventKind.DECISION_TICK,
                instrument_key=key,
                ordering=admission,
                halt_reason=flow.halt_reason,
                pipeline=pipeline,
                flow=flow,
                reservation=self._ledger.outstanding(key),
                detail=flow.detail,
            )
        return EventResult(
            kind=EventKind.DECISION_TICK,
            instrument_key=key,
            ordering=admission,
            halt_reason=None if last_pipeline is None else last_pipeline.halt_reason,
            pipeline=last_pipeline,
            reservation=self._ledger.outstanding(key),
            detail=None if last_pipeline is None else last_pipeline.detail,
        )

    # -- EGRESS_RESULT -------------------------------------------------------

    def _handle_egress_result(
        self, event: EngineEvent, admission: OrderingAdmission
    ) -> EventResult:
        """Transition the provisional projection on a re-injected send-boundary result."""
        payload: EgressResultPayload | None = event.egress_result
        if payload is None:  # pragma: no cover - guaranteed by EngineEvent validation
            raise UnknownEventKindError("EGRESS_RESULT event carries no payload (fail-closed)")
        key = payload.instrument_key
        try:
            reservation = self._ledger.apply_egress_result(payload)
        except ArtifactIntegrityError as exc:
            outstanding = self._ledger.outstanding(key)
            halt = (
                HaltReason.RESERVATION_ABSENT_FOR_RESULT
                if outstanding is None
                else HaltReason.ATTEMPT_IDENTITY_MISMATCH
            )
            self._sink.record(
                EngineEvidenceRecord(
                    kind=EvidenceKind.EVENT_REFUSED,
                    instrument_key=key,
                    halt_reason=halt,
                    egress_result_kind=payload.kind,
                    attempt_id=payload.attempt_id,
                    detail=str(exc),
                )
            )
            return EventResult(
                kind=EventKind.EGRESS_RESULT,
                instrument_key=key,
                ordering=admission,
                halt_reason=halt,
                reservation=outstanding,
                detail=str(exc),
            )
        self._sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.EGRESS_RESULT_CONSUMED,
                instrument_key=key,
                egress_result_kind=payload.kind,
                capacity_state=reservation.capacity_state,
                knowledge=reservation.knowledge,
                attempt_id=payload.attempt_id,
                detail=(
                    "the projection advanced; capacity is never released here — release is the "
                    "RCL's (RFC-002 §9.1:557; ADR-002-002 INV-005:168)"
                ),
            )
        )
        return EventResult(
            kind=EventKind.EGRESS_RESULT,
            instrument_key=key,
            ordering=admission,
            reservation=reservation,
        )
