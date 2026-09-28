"""Consume durable finality evidence and release the RCL reservation.

This is the runtime's production path to ``RELEASED`` or
``POSITION_CONSUMED``. It runs after the driver has written finality evidence,
then independently reloads the proof, economic obligation, reservation scope,
and reconciliation result. Every release gate is conjunctive; a non-positive
gate records ``CAPACITY_RELEASE_HELD`` and performs no RCL transition.

``FULL_FILL`` targets ``POSITION_CONSUMED``. A confirmed non-execution result
(``CANCEL_ACK``, ``EXPIRED``, or ``REJECT``) requires a fresh non-execution
proof and targets ``RELEASED``. Positive intent is evidenced before the RCL
mutation, and the returned :class:`ReleaseOutcome` lets the caller update its
in-memory projection only after the durable transition commits.

Obligation-expiry observations are record-only and deduplicated per
reservation occupancy. Their wait clock is process-local monotonic time; it
is never persisted or compared across restarts. The consumer does not import
or mutate the engine's reservation projection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from tos.canonical import CanonicalizationScheme
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind
from tos.posttrade import (
    EconomicObligationRecord,
    FinalityDimensionKind,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeFinalityProof,
    finality_proof_current,
    finality_proof_non_transferable,
)
from tos.rcl import (
    CapacityReservationTransition,
    CapacityState,
    ReservationScope,
)
from tos.time.domains import HealthState

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import (
    FULL_FILL_OBLIGATION_ID_PREFIX,
    FULL_FILL_PROOF_ID_PREFIX,
    NON_EXECUTION_OBLIGATION_ID_PREFIX,
    NON_EXECUTION_PROOF_ID_PREFIX,
    SyntheticFinalityProducer,
)
from tos_runtime.rcl.finality_witness import release_reservation
from tos_runtime.rcl.log import ReservationTransitionRefusal, SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import scope_reservation_id
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.service import (
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)

# TOS Phase 5 W1 factory reuse (team-lead directive, plan §10 row ①③): the EXACT same
# freshness derivation W1's recovery-barrier reconciliation already uses, never a second,
# possibly-diverging construction. Module-private because this consumer is its only cross-lane
# reuse site so far.
from tos_runtime.recovery.reconciliation import (  # noqa: SLF001
    FreshnessTimeReader,
    _build_freshness_marker,
)
from tos_runtime.time.service import TimeHealthReader
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "CAPACITY_RELEASE_HELD_KIND",
    "CAPACITY_RELEASE_INTENT_KIND",
    "RELEASE_PROOF_OVERDUE_KIND",
    "FinalityConsumerPort",
    "FinalityConsumerTimeReader",
    "FinalityReleaseConsumer",
    "ReleaseConflictReader",
    "ReleaseHoldReason",
    "ReleaseOutcome",
    "ReleaseOutcomeLike",
]

#: The obligation-record evidence kind this consumer appends for a freshly-produced
#: non-execution proof — the SAME literal value :mod:`tos_runtime.engine.finality_projection`
#: uses for the driver's own ``FULL_FILL`` path, redeclared here (not imported) to avoid a
#: circular import (:mod:`tos_runtime.engine.finality_projection` imports
#: :class:`FinalityReleaseConsumer` FROM this module) — the two literal strings are kept in
#: lockstep by ``tests/posttrade/test_release_consumer.py`` and the compose e2e suite, which
#: both query these exact kind strings against a real, shared evidence store.
_ECONOMIC_OBLIGATION_KIND = "ECONOMIC_OBLIGATION"
#: The finality-proof evidence kind — same literal-value convention as above.
_POSTTRADE_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"

#: Evidence kind appended BEFORE every RCL release attempt (module docstring).
CAPACITY_RELEASE_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
#: Evidence kind appended for every non-positive gate — no RCL transition follows it.
CAPACITY_RELEASE_HELD_KIND = "CAPACITY_RELEASE_HELD"
#: Evidence kind for the record-only obligation-expiry observation (plan §10 row ④).
RELEASE_PROOF_OVERDUE_KIND = "RELEASE_PROOF_OVERDUE"

#: The two :class:`~tos.rcl.CapacityState` members :meth:`FinalityReleaseConsumer
#: ._check_obligation_expiry` ever considers overdue-eligible (plan §10 row ④).
_OVERDUE_ELIGIBLE_STATES: frozenset[CapacityState] = frozenset(
    {CapacityState.RELEASE_PENDING_PROOF, CapacityState.QUARANTINED_UNKNOWN}
)

#: Result kinds :meth:`FinalityReleaseConsumer.consume` ever attempts a release for — mirrors
#: :mod:`tos_runtime.posttrade.finality`'s own ``_NON_EXECUTION_KINDS``, imported nowhere here to
#: avoid a private cross-module import; the two are kept in lockstep by
#: ``tests/posttrade/test_release_consumer.py``.
_NON_EXECUTION_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


class ReleaseHoldReason(StrEnum):
    """Why :meth:`FinalityReleaseConsumer.consume` recorded ``CAPACITY_RELEASE_HELD`` instead of
    releasing (module docstring's numbered gate list)."""

    #: Gate 1 (``FULL_FILL`` only): the durable witness row is not ``True``.
    NO_WITNESS = "NO_WITNESS"
    #: Gate 2: the expected durable proof/obligation row could not be re-loaded.
    PROOF_NOT_RELOADED = "PROOF_NOT_RELOADED"
    #: The non-execution proof itself could not be built (kernel gate refusal).
    NON_EXECUTION_PROOF_UNPRODUCIBLE = "NON_EXECUTION_PROOF_UNPRODUCIBLE"
    #: Gate 3: :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` itself raised.
    RECONCILIATION_UNAVAILABLE = "RECONCILIATION_UNAVAILABLE"
    #: Gate 3: the report did not positively corroborate this exact attempt.
    NOT_CORROBORATED = "NOT_CORROBORATED"
    #: Gate 4: :func:`~tos.posttrade.predicates.finality_proof_non_transferable` is ``False``.
    PROOF_NOT_TRANSFERABLE = "PROOF_NOT_TRANSFERABLE"
    #: Gate 4: :func:`~tos.posttrade.predicates.finality_proof_current` is ``False``.
    PROOF_NOT_CURRENT = "PROOF_NOT_CURRENT"
    #: The reservation's own current state could not be read (no reservation for this scope).
    NO_RESERVATION = "NO_RESERVATION"
    #: Every prior gate passed but the RCL log itself refused the transition (e.g. a concurrent
    #: writer moved the tip — a genuine CAS race, not a gate this consumer can pre-empt).
    RCL_TRANSITION_REFUSED = "RCL_TRANSITION_REFUSED"


class ReleaseOutcomeLike(Protocol):
    """The read surface :func:`~tos_runtime.engine.finality_projection._project_release` needs
    off whatever :meth:`FinalityReleaseConsumer.consume` (or a test double standing in for it)
    returns (mypy stage 3 §1.3 rule 3 port introduction) — exactly the fields that caller reads
    off the outcome, never the outcome TYPE itself, so a hand-built stand-in with the same
    fields (no inheritance) satisfies it structurally. Declared as read-only properties (not
    plain mutable attributes) because both real implementations
    (:class:`ReleaseOutcome`/the test double) are frozen — a plain Protocol attribute demands a
    SETTABLE variable and a frozen dataclass's field is read-only, so the mutable form would
    reject exactly the frozen values this Protocol exists to accept."""

    @property
    def released(self) -> bool: ...
    @property
    def attempt_id(self) -> str: ...
    @property
    def proof_digest(self) -> str | None: ...
    @property
    def evidence_seq(self) -> int | None: ...
    @property
    def resolution_generation(self) -> int | None: ...


@dataclass(frozen=True)
class ReleaseOutcome:
    """What :meth:`FinalityReleaseConsumer.consume` actually did for one attempt (kernel round #3
    §2 decision 5 W2-K wiring).

    Deliberately DATA ONLY — never a ``tos.engine.state`` import here (this module's own firewall
    scope, module docstring, never grew to include it). The caller
    (:func:`~tos_runtime.engine.finality_projection.project_finality`) is the one that turns this
    into a kernel :class:`~tos.engine.state.FinalityProofRef` and calls
    :meth:`~tos.engine.state.ProvisionalReservationLedger.release`.

    Attributes:
        released: ``True`` iff the RCL transition actually committed (``_release`` reached
            :func:`~tos_runtime.rcl.finality_witness.release_reservation` without a
            :class:`~tos_runtime.rcl.log.ReservationTransitionRefusal`). ``False`` for every hold
            reason, every non-release-eligible result kind, and a refused RCL transition.
        attempt_id: The attempt this outcome is for — always present, even on ``released=False``.
        proof_digest: The committed :class:`~tos.posttrade.PostTradeFinalityProof`'s own
            ``proof_id`` — ``None`` unless ``released`` is ``True``.
        evidence_seq: The durable ``seq`` the ``CAPACITY_RELEASE_INTENT`` evidence row this
            consumer appends BEFORE the RCL call itself received — ``None`` unless ``released``.
        resolution_generation: The ``active_generation`` gate 4 validated the proof against (the
            SAME value :meth:`_apply_gate4_and_release` fed
            :func:`~tos.posttrade.finality_proof_current`) — ``None`` unless ``released``.
    """

    released: bool
    attempt_id: str
    proof_digest: str | None = None
    evidence_seq: int | None = None
    resolution_generation: int | None = None


class FinalityConsumerPort(Protocol):
    """The narrow read surface :func:`~tos_runtime.engine.finality_projection._project_release`
    needs off a :class:`FinalityReleaseConsumer` (mypy stage 3 §1.3 rule 3 port introduction) —
    only :meth:`consume`, never the class's own construction-time gates/state."""

    def consume(self, payload: EgressResultPayload) -> ReleaseOutcomeLike:
        """Consume one genuinely-applied ``EGRESS_RESULT`` payload; see
        :meth:`FinalityReleaseConsumer.consume`'s own docstring for the gate sequence.
        """
        ...


class ReleaseConflictReader(Protocol):
    """The narrow read surface :mod:`tos_runtime.compose._dimension_readers`'s POST_TRADE
    dimension reader needs off a :class:`FinalityReleaseConsumer` (mypy stage 3 §1.3 rule 3 port
    introduction) — only :meth:`latest_release_is_conflict_free`, never :meth:`consume` or any
    construction-time state."""

    def latest_release_is_conflict_free(self) -> bool:
        """See :meth:`FinalityReleaseConsumer.latest_release_is_conflict_free`'s own docstring."""
        ...


class FinalityConsumerTimeReader(TimeHealthReader, FreshnessTimeReader, Protocol):
    """The combined read surface :class:`FinalityReleaseConsumer` needs off the runtime's time
    service (mypy stage 3 §1.3 rule 3 port introduction) — :attr:`~TimeHealthReader.health_state`
    (``_check_obligation_expiry``'s own gate) AND :meth:`~FreshnessTimeReader.current_snapshot`
    (forwarded to :func:`~tos_runtime.recovery.reconciliation._build_freshness_marker` inside
    :meth:`FinalityReleaseConsumer._reconcile`) — never the wider
    :class:`~tos_runtime.time.service.TrustworthyTimeService`'s ``start``/``evaluate``/
    ``wall_clock_now``."""


@dataclass(frozen=True)
class FinalityReleaseConsumer:
    """Bind this consumer to every collaborator :meth:`consume` needs (module docstring).

    Attributes:
        rcl_log: The durable RCL commit log — the ONE writable handle this consumer holds.
        projection: A read-only reservation-projection reader over the SAME ``rcl_log`` (never a
            second, independently-opened log — the caller wires both from one instance).
        evidence_store: The durable evidence store this consumer both reads (re-loading proofs)
            and appends to (every evidence kind this module defines).
        inbox: The durable event inbox — read for the ``attempt_finality_witness`` row.
        recon_service: The already-composed :class:`~tos_runtime.recon.service
            .ReconciliationService` (module docstring: built via the SAME factory
            :mod:`tos_runtime.recovery.reconciliation` uses for W1).
        time_service: This runtime's own :class:`~tos_runtime.time.service.TrustworthyTimeService`
            (typed as the narrower :class:`FinalityConsumerTimeReader` — mypy stage 3 §1.3 rule 3
            — since this consumer only ever reads two of its members) — freshness for every
            :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` call is derived
            FRESH from this on every :meth:`consume` call (never a marker captured once at wiring
            time, since :meth:`consume` runs on every applied result for the life of the
            process). Also gates :meth:`_check_obligation_expiry` (module docstring's H2 fix):
            the health check runs ONLY while ``time_service.health_state is
            HealthState.TRUSTED``.
        finality_producer: A :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer`
            used ONLY for :meth:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer
            .produce_non_execution` here (the driver's own instance already produced any
            ``FULL_FILL`` proof before this consumer runs) — a second, functionally-identical
            instance of a stateless, pure-function dataclass; never shared mutable state.
        scheme: The canonicalization scheme for command digests.
        monotonic_source: The injected monotonic clock for the obligation-expiry check (never a
            direct ``time.monotonic()`` read — design #40 D1.1). Its readings are held only in
            :attr:`_wait_start_ms`, an in-memory mapping never durably persisted (module
            docstring's H2 fix).
        account: The single scope account this compose root is bound to.
        instrument: The single scope instrument this compose root is bound to.
        release_proof_wait_ms: The obligation-expiry bound (module docstring's row ④).
    """

    rcl_log: SqliteCommitLog
    projection: SqliteReservationProjectionReader
    evidence_store: SqliteEvidenceStore
    inbox: SqliteEventInbox
    recon_service: ReconciliationService
    time_service: FinalityConsumerTimeReader
    finality_producer: SyntheticFinalityProducer
    scheme: CanonicalizationScheme
    monotonic_source: MonotonicSource
    account: str
    instrument: str
    release_proof_wait_ms: int
    #: In-memory-only occupancy -> first-observed-``now_ms`` map (module docstring's H2 fix).
    #: Keyed by ``(reservation_id, occupancy_seq)`` (module docstring's M1 fix). Never read from
    #: or written to durable evidence — a fresh process starts this empty, which is the whole
    #: point (a monotonic reading is never meaningful across a restart).
    _wait_start_ms: dict[tuple[str, int | None], int] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    # -- entry point -----------------------------------------------------------------

    def consume(self, payload: EgressResultPayload) -> ReleaseOutcome:
        """Attempt a release for one genuinely-``APPLIED`` ``EGRESS_RESULT`` payload.

        Args:
            payload: The re-injected ``EGRESS_RESULT`` payload the driver just applied — the
                SAME payload :mod:`tos_runtime.engine.finality_projection` passed its own
                finality producer.

        Returns:
            The :class:`ReleaseOutcome` (kernel round #3 §2 decision 5 W2-K wiring) — the
            caller's own signal for whether the kernel's in-memory projection may now be
            released too.
        """
        reservation_id = self._reservation_id()
        self._check_obligation_expiry(reservation_id=reservation_id)

        if payload.kind is EgressResultKind.FULL_FILL:
            return self._consume_full_fill(payload, reservation_id=reservation_id)
        if payload.kind in _NON_EXECUTION_KINDS:
            return self._consume_non_execution(payload, reservation_id=reservation_id)
        # ACK / PARTIAL_FILL / UNKNOWN / TIMEOUT -- no release destination at all (module
        # docstring); nothing recorded, since no release was ever attempted.
        return ReleaseOutcome(released=False, attempt_id=payload.attempt_id)

    def _reservation_id(self) -> str:
        """The scope-level RCL reservation id (module docstring's M6 fix —
        :func:`~tos_runtime.rcl.reservation_identity.scope_reservation_id`, the ONE shared
        helper every production site in this compose root now imports instead of re-deriving).
        """
        return scope_reservation_id(self.account, self.instrument)

    # -- currentness (Phase 5 W3.2 POST_TRADE dimension reader) -----------------------

    def latest_release_is_conflict_free(self) -> bool:
        """Whether this consumer's own scope's MOST RECENT recorded post-trade release
        evidence is free of a reconciliation conflict — the read
        :mod:`tos_runtime.compose._currentness_wiring`'s POST_TRADE dimension reader
        (:func:`~tos_runtime.compose._currentness_wiring._post_trade_dimension_reader_for`)
        uses, never a second judgement authored there.

        Scans this scope's own :data:`CAPACITY_RELEASE_INTENT_KIND` /
        :data:`CAPACITY_RELEASE_HELD_KIND` evidence rows (newest ``seq`` first, mirroring
        :meth:`_active_generation`'s own scan style) for the first one matching this
        consumer's own :meth:`_reservation_id`:

        - No matching row at all (no post-trade fact yet for this scope) ⇒ ``True`` — a
          scope that has never sent an attempt has no post-trade fact YET, which is the
          normal state before any send, never treated as a conflict.
        - The latest matching row is a :data:`CAPACITY_RELEASE_INTENT_KIND` (a release
          actually proceeded) ⇒ ``True``.
        - The latest matching row is a :data:`CAPACITY_RELEASE_HELD_KIND` whose recorded
          ``reason`` is :attr:`ReleaseHoldReason.NOT_CORROBORATED` ⇒ ``False`` — the ONE
          hold reason that structurally means gate 3's reconciliation found a genuine
          conflict (an orphan broker order, or a non-``MATCHED`` classification) between
          what this scope expected and what actually happened downstream.
        - Any OTHER :data:`CAPACITY_RELEASE_HELD_KIND` reason (no witness yet, proof not
          yet reloaded, reconciliation itself unavailable, the RCL transition itself
          refused, ...) ⇒ ``True`` — a normal, transient "not yet complete" gate, never a
          conflict; folding every hold into ``False`` would permanently block new risk on
          ordinary pipeline timing, which this dimension does not do.

        Returns:
            ``True`` unless the most recent recorded outcome for this scope is a
            genuine reconciliation conflict.
        """
        reservation_id = self._reservation_id()
        rows = self.evidence_store.connection.execute(
            "SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq DESC",
            (CAPACITY_RELEASE_INTENT_KIND, CAPACITY_RELEASE_HELD_KIND),
        ).fetchall()
        for kind, payload_json in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("reservation_id") != reservation_id:
                continue
            if kind == CAPACITY_RELEASE_INTENT_KIND:
                return True
            return bool(
                decoded.get("reason") != ReleaseHoldReason.NOT_CORROBORATED.value
            )
        return True

    # -- FULL_FILL -> POSITION_CONSUMED -----------------------------------------------

    def _consume_full_fill(
        self, payload: EgressResultPayload, *, reservation_id: str
    ) -> ReleaseOutcome:
        witness = self.inbox.finality_witness(payload.attempt_id)
        if witness is not True:
            return self._hold(payload, reservation_id, ReleaseHoldReason.NO_WITNESS)
        proof = self._reload_proof(
            payload.attempt_id, id_prefix=FULL_FILL_PROOF_ID_PREFIX
        )
        obligation = self._reload_obligation(
            payload.attempt_id, id_prefix=FULL_FILL_OBLIGATION_ID_PREFIX
        )
        if proof is None or obligation is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED
            )
        report, corroborated = self._reconcile(payload.attempt_id)
        if report is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.RECONCILIATION_UNAVAILABLE
            )
        if not corroborated:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NOT_CORROBORATED,
                detail=report.reason,
            )
        return self._apply_gate4_and_release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            obligation=obligation,
            report_reason=report.reason,
            to_state=CapacityState.POSITION_CONSUMED,
        )

    # -- CANCEL_ACK / EXPIRED / REJECT -> RELEASED ------------------------------------

    def _consume_non_execution(
        self, payload: EgressResultPayload, *, reservation_id: str
    ) -> ReleaseOutcome:
        report, corroborated = self._reconcile(payload.attempt_id)
        if report is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.RECONCILIATION_UNAVAILABLE
            )
        if not corroborated:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NOT_CORROBORATED,
                detail=report.reason,
            )
        produced = self.finality_producer.produce_non_execution(payload)
        if produced is None:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NON_EXECUTION_PROOF_UNPRODUCIBLE,
            )
        self.evidence_store.append(
            produced.record.model_dump(mode="json"),
            kind=_ECONOMIC_OBLIGATION_KIND,
            record_class=_ECONOMIC_OBLIGATION_KIND,
        )
        self.evidence_store.append(
            produced.proof.model_dump(mode="json"),
            kind=_POSTTRADE_FINALITY_PROOF_KIND,
            record_class=_POSTTRADE_FINALITY_PROOF_KIND,
        )
        # Re-load rather than trust `produced` directly (module docstring's "never an
        # in-memory proof object" discipline, applied uniformly to both release paths).
        proof = self._reload_proof(
            payload.attempt_id, id_prefix=NON_EXECUTION_PROOF_ID_PREFIX
        )
        obligation = self._reload_obligation(
            payload.attempt_id, id_prefix=NON_EXECUTION_OBLIGATION_ID_PREFIX
        )
        if proof is None or obligation is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED
            )
        return self._apply_gate4_and_release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            obligation=obligation,
            report_reason=report.reason,
            to_state=CapacityState.RELEASED,
        )

    # -- gate 3 (reconciliation) --------------------------------------------------------

    def _reconcile(self, attempt_id: str) -> tuple[ReconciliationReport | None, bool]:
        """Gate 3 (module docstring): a fresh :class:`~tos_runtime.recon.service
        .ReconciliationReport` plus whether it positively corroborates ``attempt_id``.

        Returns:
            ``(report, corroborated)`` — ``report`` is ``None`` only when ``.reconcile()``
            itself raised (fail-closed, never propagated out of this consumer).
        """
        instrument_key = InstrumentKey(account=self.account, instrument=self.instrument)
        scope = WitnessScope(
            account=self.account,
            instrument_keys=(instrument_key,),
            attempt_ids=(attempt_id,),
        )
        freshness = _build_freshness_marker(self.time_service)
        try:
            report = self.recon_service.reconcile(scope, freshness=freshness)
        except (
            Exception
        ):  # noqa: BLE001 -- fail-closed, mirrors recovery/reconciliation.py
            return None, False
        matched = any(
            classification.attempt_id == attempt_id
            and classification.classification is ReconciliationClass.MATCHED
            for classification in report.classifications
        )
        return report, bool(report.permits_capacity_release and matched)

    # -- gate 4 (non-transferable/current, from independent inputs — H1 fix) + release --

    def _apply_gate4_and_release(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        proof: PostTradeFinalityProof,
        obligation: EconomicObligationRecord,
        report_reason: str | None,
        to_state: CapacityState,
    ) -> ReleaseOutcome:
        reservation_scope = self._reservation_scope(reservation_id)
        if reservation_scope is None:
            return self._hold(payload, reservation_id, ReleaseHoldReason.NO_RESERVATION)
        target_scope = ObligationLegScope(
            leg=ObligationLegDirection.RECEIPT,
            account=reservation_scope.account,
            currency=self.finality_producer.config.currency,
            value_date=self.finality_producer.config.value_date,
            source_revision=self.finality_producer.config.source_revision,
            finality_class=FinalityDimensionKind.ORDER_FQP,
        )
        if not finality_proof_non_transferable(
            proof,
            target_scope,
            target_obligation_ref=obligation.obligation_id,
            target_obligation_version=obligation.obligation_version,
        ):
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_TRANSFERABLE
            )
        active_generation = self._active_generation(
            account=reservation_scope.account, instrument=reservation_scope.instrument
        )
        if not finality_proof_current(proof, active_generation):
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_CURRENT
            )
        return self._release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            report_reason=report_reason,
            to_state=to_state,
            resolution_generation=active_generation,
        )

    def _reservation_scope(self, reservation_id: str) -> ReservationScope | None:
        """The RCL log's OWN persisted :class:`~tos.rcl.ReservationScope` for ``reservation_id``
        (module docstring's H1 fix) — a fresh scan of :meth:`~tos_runtime.rcl.log.SqliteCommitLog
        .reservation_rows`, independent of whatever scope the proof under test claims.
        """
        for (
            row_reservation_id,
            _state,
            _last_seq,
            scope,
        ) in self.rcl_log.reservation_rows():
            if row_reservation_id == reservation_id:
                return scope
        return None

    def _active_generation(self, *, account: str, instrument: str) -> int | None:
        """The newest ``obligation_generation`` durably recorded across every
        ``ECONOMIC_OBLIGATION`` evidence row sharing ``(account, instrument)`` (module
        docstring's H1 fix) — an independent evidence-store scan, never
        ``proof.bound_generation`` read off the artifact under test."""
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (_ECONOMIC_OBLIGATION_KIND,),
        ).fetchall()
        newest: int | None = None
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if (
                decoded.get("account_scope") != account
                or decoded.get("instrument_identity") != instrument
            ):
                continue
            generation = decoded.get("obligation_generation")
            if isinstance(generation, int) and (newest is None or generation > newest):
                newest = generation
        return newest

    # -- the RCL mutation itself -------------------------------------------------------

    def _release(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        proof: PostTradeFinalityProof,
        report_reason: str | None,
        to_state: CapacityState,
        resolution_generation: int | None,
    ) -> ReleaseOutcome:
        current_state = self.projection.reservation_state(reservation_id)
        if current_state is None:
            return self._hold(payload, reservation_id, ReleaseHoldReason.NO_RESERVATION)
        current_seq = self.projection.reservation_last_seq(reservation_id)
        expected_seq = -1 if current_seq is None else current_seq
        # ★ kernel round #3 §2 decision 5 (ⓖ): SyntheticFinalityProducer hardcodes
        # obligation_generation=0 for every proof it mints (module docstring's own note); the
        # honest floor for the kernel's own resolution_generation axis is therefore 0, never a
        # fabricated None, once gate 4 has already validated currentness against it.
        generation = 0 if resolution_generation is None else resolution_generation
        intent_receipt = self.evidence_store.append(
            {
                "attempt_id": payload.attempt_id,
                "reservation_id": reservation_id,
                "proof_id": proof.proof_id,
                "destination": to_state.value,
                "report_reason": report_reason,
                "resolution_generation": generation,
            },
            kind=CAPACITY_RELEASE_INTENT_KIND,
            record_class=CAPACITY_RELEASE_INTENT_KIND,
        )
        transition = CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=self.rcl_log.current_epoch(),
            from_state=current_state,
            to_state=to_state,
            scope=ReservationScope(account=self.account, instrument=self.instrument),
        )
        command_digest = self.scheme.compute_digest(
            {"attempt_id": payload.attempt_id, "to_state": to_state.value}
        )
        try:
            release_reservation(
                self.rcl_log,
                transition,
                command_id=f"release-{payload.attempt_id}",
                command_digest=command_digest,
                expected_seq=expected_seq,
                proof=proof,
            )
        except ReservationTransitionRefusal as exc:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.RCL_TRANSITION_REFUSED,
                detail=str(exc),
            )
        return ReleaseOutcome(
            released=True,
            attempt_id=payload.attempt_id,
            proof_digest=proof.proof_id,
            evidence_seq=intent_receipt.seq,
            resolution_generation=generation,
        )

    # -- HELD ---------------------------------------------------------------------------

    def _hold(
        self,
        payload: EgressResultPayload,
        reservation_id: str,
        reason: ReleaseHoldReason,
        *,
        detail: str | None = None,
    ) -> ReleaseOutcome:
        self.evidence_store.append(
            {
                "attempt_id": payload.attempt_id,
                "reservation_id": reservation_id,
                "reason": reason.value,
                "detail": detail,
            },
            kind=CAPACITY_RELEASE_HELD_KIND,
            record_class=CAPACITY_RELEASE_HELD_KIND,
        )
        return ReleaseOutcome(released=False, attempt_id=payload.attempt_id)

    # -- durable re-loads (module docstring's "never an in-memory proof object") -------

    def _reload_proof(
        self, attempt_id: str, *, id_prefix: str
    ) -> PostTradeFinalityProof | None:
        idempotency_key = f"{id_prefix}:{attempt_id}"
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
            (_POSTTRADE_FINALITY_PROOF_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("idempotency_key") == idempotency_key:
                return PostTradeFinalityProof.model_validate(decoded)
        return None

    def _reload_obligation(
        self, attempt_id: str, *, id_prefix: str
    ) -> EconomicObligationRecord | None:
        idempotency_key = f"{id_prefix}:{attempt_id}"
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
            (_ECONOMIC_OBLIGATION_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("idempotency_key") == idempotency_key:
                return EconomicObligationRecord.model_validate(decoded)
        return None

    # -- obligation expiry (plan §10 row ④, record-only) --------------------------------

    def _check_obligation_expiry(self, *, reservation_id: str) -> None:
        if self.time_service.health_state is not HealthState.TRUSTED:
            # H2 fix: evaluate and record nothing without a TRUSTED time reading.
            return
        state = self.projection.reservation_state(reservation_id)
        if state not in _OVERDUE_ELIGIBLE_STATES:
            return
        occupancy_seq = self.projection.reservation_last_seq(reservation_id)
        marker_key = (reservation_id, occupancy_seq)
        now_ms = self.monotonic_source.now_ms()
        first_observed_ms = self._wait_start_ms.get(marker_key)
        if first_observed_ms is None:
            self._wait_start_ms[marker_key] = now_ms
            return
        if now_ms - first_observed_ms < self.release_proof_wait_ms:
            return
        if self._overdue_already_recorded(reservation_id, occupancy_seq=occupancy_seq):
            return
        self.evidence_store.append(
            {
                "reservation_id": reservation_id,
                "occupancy_seq": occupancy_seq,
                "state": state.value,
                "waited_ms": now_ms - first_observed_ms,
            },
            kind=RELEASE_PROOF_OVERDUE_KIND,
            record_class=RELEASE_PROOF_OVERDUE_KIND,
        )

    def _overdue_already_recorded(
        self, reservation_id: str, *, occupancy_seq: int | None
    ) -> bool:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (RELEASE_PROOF_OVERDUE_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if (
                decoded.get("reservation_id") == reservation_id
                and decoded.get("occupancy_seq") == occupancy_seq
            ):
                return True
        return False
