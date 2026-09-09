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
class TransportNatureLike(Protocol):
    """Structural stand-in for ``tos.egressgw.records.TransportNature`` (Phase 3 KW2-B).

    ``tos.engine`` cannot import the concrete type: ``tos.egressgw`` imports **from**
    ``tos.engine`` at module level (``construction.py`` / ``gateway.py`` / ``seal.py`` /
    ``records.py`` all do ``from tos.engine import ...``), so a module-level
    ``from tos.egressgw.records import TransportNature`` here would be a genuine circular
    import (``ImportError: cannot import name ... from partially initialized module``), not
    merely a firewall-discipline choice. ``tos.backtest``'s own import-closure test
    (``tos/tests/backtest/test_backtest_import_closure.py``) independently forbids
    ``tos.egressgw`` / ``tos.authority`` / ``tos.liveauth`` as siblings, so the concrete type
    is unreachable from the backtest side too.

    This ``Protocol`` names only the single field the Coordinator gate reads
    (``reaches_broker``), so any object with that attribute — including the real
    ``tos.egressgw.records.TransportNature`` — satisfies it structurally, with no import edge
    at all (design #31 §0.3 closure discipline extended to a typing-only seam).
    """

    reaches_broker: bool | None


@runtime_checkable
class CoordinatorPreconditions(Protocol):
    """The RFC-002 §10.7 Execution Coordinator positive gates (design #31 §9-10; plan §2.1).

    RFC-002 §10.7 lists, among the Coordinator's responsibilities, "verify current Safety
    Authority" and "verify live authorization" — both **before** anything from the 19-step
    Normal Commitment Flow runs. Slice #1 had no hosting point for either (D-E1 is
    authority-free by design, module docstring). This Protocol is that hosting point: two
    positive-admit predicates, read fresh on every ``DECISION_TICK`` rather than cached, so a
    later-revoked authority or a later-suspended live scope is caught on the very next tick.

    Both members return ``bool | None`` and the gate is **positive-admit**
    (design #31 §4.2 rule 1): only a literal ``True`` passes; ``False`` *and* ``None``
    (unestablished) both refuse. There is deliberately no default implementation and no
    optional member — :class:`EngineCore` requires a concrete ``preconditions`` object at
    construction (no default), so an authority-free core cannot be wired to run ticks that
    quietly assume both gates hold. A backtest supplies an explicit non-live stand-in (never
    a hardcoded ``True`` — see ``tos.backtest.driver.SyntheticNonLivePreconditions``); a real
    runtime supplies ``tos.authority.authority_epoch_current`` / a ``tos.liveauth`` predicate
    composed against its own current state, over the injection seam this Protocol is.
    """

    def authority_epoch_current(self) -> bool | None:
        """Whether the current Safety Authority epoch is verifiably current right now.

        Returns:
            ``True`` iff verifiably current; ``False`` or ``None`` (unestablished) refuse the
            gate — never treated as a pass.
        """
        ...

    def live_scope_authorized(
        self, transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Whether live-scope authorization covers a send over ``transport_nature``.

        Args:
            transport_nature: The wired core's declared transport nature (``None`` when the
                core was never given one — e.g. a unit test that never reaches a send
                boundary). ``None`` is conservatively **not** a pass; a concrete
                implementation decides its own fail-closed treatment of it.

        Returns:
            ``True`` iff verifiably authorized for this transport; ``False`` or ``None``
            refuse the gate.
        """
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
    #: The disposition of a re-injected ``EGRESS_RESULT`` (Phase 3 A-K-2); ``None`` for a
    #: ``DECISION_TICK`` event, which never carries one.
    result_disposition: ResultDisposition | None = None
    #: The content-addressed digest of an ``EGRESS_RESULT``'s *applied outcome* (Phase 3 wave 3
    #: KW3-RD; :func:`~tos.engine.records.egress_result_outcome_digest`) — ``None`` for a
    #: ``DECISION_TICK``, which reports through :attr:`pipeline` instead (see
    #: :attr:`outcome_digest`'s own docstring for why the two never both apply and how the public
    #: property picks between them). Set by :meth:`EngineCore._handle_egress_result` for **every**
    #: terminal disposition, including the non-``APPLIED`` ones — a ``DUPLICATE`` of a byte-
    #: identical ``EGRESS_RESULT`` reproduces the same digest as the first ``APPLIED`` application
    #: would have (RFC-003 §10:345-348 reproducibility), while a *different* disposition for the
    #: same payload (e.g. ``APPLIED`` the first time, ``DUPLICATE`` the second, or a
    #: ``NON_MONOTONIC_PROJECTION`` refusal) changes it, because the disposition is itself part of
    #: what :class:`~tos.engine.records.EgressResultOutcome` covers.
    result_outcome_digest: str | None = None
    detail: str | None = None

    @property
    def outcome_digest(self) -> str | None:
        """The outcome digest this event established, for ``EVENT_CONSUMED`` replay evidence.

        (Phase 3 A-K-3 / wave 3 KW3-RD; design #31 §7.1.) Derived from whichever stage the event
        actually reached — **never a new hash of mutable state**: a ``DECISION_TICK`` that emitted
        an outcome exposes its already-computed
        :attr:`~tos.engine.pipeline.PipelineResult.outcome_digest` (the emitted Decision/Proposal's
        own canonical digest); an ``EGRESS_RESULT`` exposes :attr:`result_outcome_digest` — the
        digest of its *applied outcome* (disposition + resulting capacity/knowledge/quantities),
        never a hash of the live, still-mutable :mod:`tos.engine.state` projection itself. The two
        are mutually exclusive by construction (:attr:`pipeline` is only ever set for a
        ``DECISION_TICK``, :attr:`result_outcome_digest` only ever for an ``EGRESS_RESULT``), so
        checking ``pipeline`` first and falling back is unambiguous rather than a priority choice.

        Before Phase 3 wave 3 KW3-RD this was unconditionally ``None`` for every ``EGRESS_RESULT``
        (wave 3 lane F-R survey finding), which made both the backtest=paper parity comparison and
        the runtime replay comparison vacuous for result events — ``None == None`` reads as
        "uncompared" (:data:`~tos.evidence.ReplayResultState.INCONCLUSIVE`), not "verified
        identical". A Coordinator-gate refusal (before step 1, before any handler runs) still sets
        neither field and correctly stays ``None`` — the core genuinely produced no outcome there.

        Returns:
            The recorded outcome digest, or ``None`` when the event produced none at all.
        """
        if self.pipeline is not None:
            return self.pipeline.outcome_digest
        return self.result_outcome_digest


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
        preconditions: CoordinatorPreconditions,
        ledger: ProvisionalReservationLedger | None = None,
        transmit: Transmit | None = None,
        transport_nature: TransportNatureLike | None = None,
        sink: EvidenceSink | None = None,
        scheme: CanonicalizationScheme | None = None,
    ) -> None:
        """Wire the core.

        Args:
            registry: The instrument-keyed strategy registry.
            stages: The injected step → stage mapping for steps 2-11, 13, 14.
            configuration: The injected engine configuration (every bound arrives here).
            preconditions: The RFC-002 §10.7 Coordinator positive gates (design #31 §9-10;
                plan §2.1) — **required, no default**, so a core cannot be wired without an
                explicit authority/live-scope stance. Checked fresh at the top of every
                ``DECISION_TICK``, before step 1.
            ledger: The provisional reservation projection; built from the configured
                ``max_unresolved_send_per_scope`` when omitted.
            transmit: The injected send-boundary hand-off; ``None`` stops every flow after step 14.
            transport_nature: This core's wired transport's declared nature (survey finding,
                Phase 3 KW2-B: the core cannot import the concrete
                ``tos.egressgw.records.TransportNature`` type — see
                :class:`TransportNatureLike` — so it holds this **structurally typed**,
                fixed-at-construction value and passes it, unchanged, to
                :meth:`CoordinatorPreconditions.live_scope_authorized` on every tick. ``None``
                when this core is never wired to a transport with a declared nature (e.g. a
                unit test that never reaches the send boundary).
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
        self._preconditions = preconditions
        self._ledger = ledger or ProvisionalReservationLedger(
            max_unresolved_send_per_scope=configuration.max_unresolved_send_per_scope
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

    # -- DECISION_TICK -------------------------------------------------------

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
        # ★ [KW3-EV] Computed once per tick and threaded into every per-step FLOW_STEP_ADMITTED /
        # FLOW_HALTED / ATTEMPT_REQUEST_CREATED / SEND_HANDED_OFF evidence record the commitment
        # flow emits, so a replay can correlate a flow instance's whole evidence trail by the
        # exact event that produced it (Phase 3 wave 3 lane C-R finding — encounter-order
        # correlation is fragile under a truncated replay window).
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
        """Run the RFC-002 §10.7 Coordinator positive gates before step 1 (design #31 §9-10).

        Both :meth:`CoordinatorPreconditions.authority_epoch_current` and
        :meth:`CoordinatorPreconditions.live_scope_authorized` are checked fresh — never
        cached — and the gate is positive-admit (design #31 §4.2 rule 1): only a literal
        ``True`` passes, so a ``False`` *or* an unestablished ``None`` both refuse. On refusal
        nothing further runs for this tick: no registry dispatch, no decision pipeline, no
        ``DECISION_PROPOSAL`` (step 1) evidence, and no ledger mutation. The one exception,
        precisely: the causal-order coordinate (``handle``'s ``self._last_reference``) *is*
        still advanced — it is stamped before this gate ever runs, not by it — so a refused
        tick still moves the core's ordering watermark forward (Phase 3 wave 2 review finding
        #9). Benign on the nominal path because the driver stamps monotone coordinates itself,
        but it means "nothing is consumed" understates this one coordinate; see
        :meth:`_coordinator_precondition_refused`'s detail strings for the exact wording.

        Args:
            key: The tick's dispatch scope (for the recorded evidence and result).
            admission: This tick's already-computed causal-order admission.

        Returns:
            An :class:`EventResult` naming the halt when either precondition does not read
            exactly ``True``; ``None`` when both hold, in which case the caller proceeds
            exactly as before.
        """
        # ★ Positive-identity gate only (design #31 §4.2 rule 1 / §6; test_engine_polarity.py
        # forbids ``is not True`` outright, series-wide — the #18/#22/#23/#25 MAJOR-2 lesson).
        # Each check reads "does this equal True", never "does this differ from True", so the
        # branch structure — not a negated comparison — is what makes ``False`` *and* ``None``
        # both refuse.
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

    # -- EGRESS_RESULT -------------------------------------------------------

    def _handle_egress_result(
        self, event: EngineEvent, admission: OrderingAdmission
    ) -> EventResult:
        """Apply — or conservatively record — a re-injected send-boundary result (Phase 3 A-K-2).

        A late, orphaned, duplicated, or attempt-mismatched result is **not** a crash: the ledger
        (:meth:`~tos.engine.state.ProvisionalReservationLedger.apply_egress_result`) now returns a
        :class:`~tos.engine.state.ResultApplication` naming the disposition instead of raising, and
        this handler records every non-``APPLIED`` disposition as ``EvidenceKind.RESULT_UNMATCHED`` /
        ``HaltReason.RESULT_UNMATCHED`` — never relaxing capacity or knowledge on it. Every terminal
        disposition also gets a real :attr:`EventResult.result_outcome_digest` (Phase 3 wave 3
        KW3-RD) so a replay comparison over this event is a genuine equality check.
        """
        payload: EgressResultPayload | None = event.egress_result
        if payload is None:  # pragma: no cover - guaranteed by EngineEvent validation
            raise UnknownEventKindError(
                "EGRESS_RESULT event carries no payload (fail-closed)"
            )
        key = payload.instrument_key
        application: ResultApplication = self._ledger.apply_egress_result(payload)
        # ★ [KW3-RD] Every terminal disposition gets a real outcome digest — including the five
        # non-APPLIED ones — so a replay comparison over an EGRESS_RESULT is a genuine equality
        # check, not a vacuous None == None (design #31 §7.1; Phase 3 wave 3 lane F-R survey
        # finding). See EgressResultOutcome's own docstring for exactly what is covered.
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
                    # ★ [KW2b-#13] The refused result's own reported magnitude, not the
                    # (unchanged) reservation's — a cancel-crossing fill's quantity must reach
                    # the hash-chained evidence store, not only the transport-local inbox row.
                    filled_quantity=payload.filled_quantity,
                    remaining_quantity=payload.remaining_quantity,
                    broker_execution_id=payload.broker_execution_id,
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
        assert reservation is not None  # APPLIED always stores a projection
        self._sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.EGRESS_RESULT_CONSUMED,
                instrument_key=key,
                egress_result_kind=payload.kind,
                result_disposition=application.disposition,
                capacity_state=reservation.capacity_state,
                knowledge=reservation.knowledge,
                attempt_id=payload.attempt_id,
                # ★ [KW2b-#13] The now-stored magnitude, for the same reason RESULT_UNMATCHED
                # carries the refused one — the hash-chained evidence store, not only the
                # in-process EventResult, is what reconciliation actually reads.
                filled_quantity=reservation.filled_quantity,
                remaining_quantity=reservation.remaining_quantity,
                broker_execution_id=payload.broker_execution_id,
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
