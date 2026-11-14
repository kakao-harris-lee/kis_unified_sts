"""The single, synchronous, deterministic event core (design #31 §2 / D5)."""

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
    egress_result_outcome_digest,
    event_identity,
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
from tos.engine.state import ProvisionalReservationLedger, ResultApplication
from tos.engine.vocabulary import (
    ADMISSIBLE_EVENT_KINDS,
    DispatchResolution,
    EventKind,
    EvidenceKind,
    HaltReason,
    OrderingAdmission,
    ResultDisposition,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "CoordinatorPreconditions",
    "DecisionContextResolver",
    "EngineCore",
    "EventBatch",
    "EventResult",
    "EventSource",
    "TransportNatureLike",
    "UnknownEventKindError",
    "admit_kind",
    "ordering_admission",
]


@runtime_checkable
class DecisionContextResolver(Protocol):
    """The D-E2 plug that fills a ``DECISION_TICK`` payload (design #31 §12-1)."""

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Resolve one Decision Context into a tick payload."""
        ...


@runtime_checkable
class TransportNatureLike(Protocol):
    """Structural stand-in for ``tos.egressgw.records.TransportNature`` (Phase 3 KW2-B)."""

    @property
    def reaches_broker(self) -> bool | None:
        """Whether this transport is broker-reaching (``None`` ⇒ unestablished)."""


@runtime_checkable
class CoordinatorPreconditions(Protocol):
    """The RFC-002 §10.7 Execution Coordinator positive gates (design #31 §9-10; plan §2.1)."""

    def authority_epoch_current(self) -> bool | None:
        """Whether the current Safety Authority epoch is verifiably current right now."""
        ...

    def live_scope_authorized(
        self, transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Whether live-scope authorization covers a send over ``transport_nature``."""
        ...


@runtime_checkable
class EventSource(Protocol):
    """The plug that supplies events to the core (design #31 §12-4)."""

    def __iter__(self) -> Iterator[EngineEvent]:
        """Yield events in causal order."""
        ...


EventBatch = tuple[EngineEvent, ...]


class UnknownEventKindError(ArtifactIntegrityError):
    """An event kind outside the closed vocabulary reached the dispatcher (design #31 §2.2)."""


def admit_kind(kind: object) -> EventKind:
    """Resolve an event kind by **positive membership** in the closed vocabulary."""
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
    """Classify an incoming event's causal order against the last consumed one (§2.1(ii))."""
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
    """What one event produced (design #31 §2)."""

    kind: EventKind
    instrument_key: InstrumentKey
    ordering: OrderingAdmission
    halt_reason: HaltReason | None = None
    pipeline: PipelineResult | None = None
    flow: FlowResult | None = None
    reservation: ProvisionalReservation | None = None
    result_disposition: ResultDisposition | None = None
    result_outcome_digest: str | None = None
    detail: str | None = None

    @property
    def outcome_digest(self) -> str | None:
        """The outcome digest this event established, for ``EVENT_CONSUMED`` replay evidence."""
        if self.pipeline is not None:
            return self.pipeline.outcome_digest
        return self.result_outcome_digest


class EngineCore:
    """The synchronous, deterministic single event core (design #31 §2)."""

    def __init__(
        self,
        *,
        registry: StrategyRegistry,
        stages: Mapping[CommitmentStep, Stage],
        configuration: EngineConfiguration,
        preconditions: CoordinatorPreconditions,
        ledger: ProvisionalReservationLedger | None = None,
        transmit: Transmit | None = None,
        transport_nature: TransportNatureLike | None = None,
        sink: EvidenceSink | None = None,
        scheme: CanonicalizationScheme | None = None,
    ) -> None:
        """Wire the core."""
        validate_stage_map(stages)
        self._registry = registry
        self._stages = dict(stages)
        self._configuration = configuration
        self._preconditions = preconditions
        self._ledger = (
            ledger
            if ledger is not None
            else ProvisionalReservationLedger(
                max_unresolved_send_per_scope=configuration.max_unresolved_send_per_scope
            )
        )
        self._transmit = transmit
        self._transport_nature = transport_nature
        self._sink: EvidenceSink = sink or NullEvidenceSink()
        self._scheme = scheme or get_scheme(configuration.canonicalization_version)
        self._last_reference: OrderingEvent | None = None

    @property
    def ledger(self) -> ProvisionalReservationLedger:
        """The provisional, non-authoritative reservation projection."""
        return self._ledger

    def run(self, events: Iterable[EngineEvent]) -> tuple[EventResult, ...]:
        """Process events one at a time, each to completion, in the given order."""
        return tuple(self.handle(event) for event in events)

    def handle(self, event: EngineEvent) -> EventResult:
        """Process exactly one event to completion (design #31 §2.1)."""
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
        if (
            handler is None
        ):  # pragma: no cover - admit_kind + this map are the same closure
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

    def _handle_decision_tick(
        self, event: EngineEvent, admission: OrderingAdmission
    ) -> EventResult:
        """Run the decision pipeline and, for a Proposal, the 19-step commitment flow."""
        payload = event.decision_tick
        if payload is None:  # pragma: no cover - guaranteed by EngineEvent validation
            raise UnknownEventKindError(
                "DECISION_TICK event carries no payload (fail-closed)"
            )
        key = payload.instrument_key
        event_id = event_identity(event, scheme=self._scheme)

        refusal = self._coordinator_precondition_refusal(key, admission)
        if refusal is not None:
            return refusal

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

        return self._run_entries(
            payload, dispatch.entries, admission, event_id=event_id
        )

    def _coordinator_precondition_refusal(
        self, key: InstrumentKey, admission: OrderingAdmission
    ) -> EventResult | None:
        """Run the RFC-002 §10.7 Coordinator positive gates before step 1 (design #31 §9-10)."""
        if self._preconditions.authority_epoch_current() is True:
            if (
                self._preconditions.live_scope_authorized(self._transport_nature)
                is True
            ):
                return None
            return self._coordinator_precondition_refused(
                key,
                admission,
                halt_reason=HaltReason.LIVE_SCOPE_NOT_AUTHORIZED,
                detail=(
                    "live-scope authorization is not verifiably granted for this core's wired "
                    "transport (RFC-002 §10.7 'verify live authorization') — the tick is "
                    "refused before step 1: no registry dispatch, no pipeline, no step-1 "
                    "evidence, no ledger mutation; the causal-order coordinate is still "
                    "advanced (design #31 §9-10; Phase 3 wave 2 review finding #9)"
                ),
            )
        return self._coordinator_precondition_refused(
            key,
            admission,
            halt_reason=HaltReason.AUTHORITY_NOT_CURRENT,
            detail=(
                "the current Safety Authority epoch is not verifiably current (RFC-002 §10.7 "
                "'verify current Safety Authority') — the tick is refused before step 1: no "
                "registry dispatch, no pipeline, no step-1 evidence, no ledger mutation; the "
                "causal-order coordinate is still advanced (design #31 §9-10; Phase 3 wave 2 "
                "review finding #9)"
            ),
        )

    def _coordinator_precondition_refused(
        self,
        key: InstrumentKey,
        admission: OrderingAdmission,
        *,
        halt_reason: HaltReason,
        detail: str,
    ) -> EventResult:
        """Record and return one Coordinator-precondition refusal (shared by both gates)."""
        self._sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.COORDINATOR_PRECONDITION_REFUSED,
                instrument_key=key,
                halt_reason=halt_reason,
                detail=detail,
            )
        )
        return EventResult(
            kind=EventKind.DECISION_TICK,
            instrument_key=key,
            ordering=admission,
            halt_reason=halt_reason,
            detail=detail,
        )

    def _run_entries(
        self,
        payload: DecisionTickPayload,
        entries: tuple[RegisteredStrategy, ...],
        admission: OrderingAdmission,
        *,
        event_id: str,
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
                value_view=payload.value_view,
                event_id=event_id,
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

    def _handle_egress_result(
        self, event: EngineEvent, admission: OrderingAdmission
    ) -> EventResult:
        """Apply — or conservatively record — a re-injected send-boundary result (Phase 3 A-K-2)."""
        payload: EgressResultPayload | None = event.egress_result
        if payload is None:  # pragma: no cover - guaranteed by EngineEvent validation
            raise UnknownEventKindError(
                "EGRESS_RESULT event carries no payload (fail-closed)"
            )
        key = payload.instrument_key
        application: ResultApplication = self._ledger.apply_egress_result(payload)
        result_outcome_digest = egress_result_outcome_digest(
            application.disposition, application.projection, scheme=self._scheme
        )
        if not application.applied:
            detail = (
                f"egress result disposition={application.disposition} — not applied to the "
                "reservation projection; capacity and knowledge are left exactly where they were "
                "(design plan 2026-09-09 §1.1 '크래시는 이벤트가 아니다')"
            )
            self._sink.record(
                EngineEvidenceRecord(
                    kind=EvidenceKind.RESULT_UNMATCHED,
                    instrument_key=key,
                    halt_reason=HaltReason.RESULT_UNMATCHED,
                    egress_result_kind=payload.kind,
                    result_disposition=application.disposition,
                    attempt_id=payload.attempt_id,
                    filled_quantity=payload.filled_quantity,
                    remaining_quantity=payload.remaining_quantity,
                    broker_execution_id=payload.broker_execution_id,
                    trading_date=payload.trading_date,
                    detail=detail,
                )
            )
            return EventResult(
                kind=EventKind.EGRESS_RESULT,
                instrument_key=key,
                ordering=admission,
                halt_reason=HaltReason.RESULT_UNMATCHED,
                reservation=application.projection,
                result_disposition=application.disposition,
                result_outcome_digest=result_outcome_digest,
                detail=detail,
            )
        reservation = application.projection
        assert reservation is not None
        self._sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.EGRESS_RESULT_CONSUMED,
                instrument_key=key,
                egress_result_kind=payload.kind,
                result_disposition=application.disposition,
                capacity_state=reservation.capacity_state,
                knowledge=reservation.knowledge,
                attempt_id=payload.attempt_id,
                filled_quantity=reservation.filled_quantity,
                remaining_quantity=reservation.remaining_quantity,
                broker_execution_id=payload.broker_execution_id,
                trading_date=payload.trading_date,
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
            result_disposition=application.disposition,
            result_outcome_digest=result_outcome_digest,
        )
