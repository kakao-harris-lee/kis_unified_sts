"""``FinalityReleaseConsumer`` — the ONE production call site reaching a ``RELEASED``/
``POSITION_CONSUMED`` RCL destination (TOS Phase 5 W2-R; plan §10 row ①).

**Kernel diff 0.** This module never touches ``tos.engine.state.PROJECTION_ORDER`` (the engine's
own in-memory reservation ledger, which still carries no ``RELEASED`` member — that stays a
kernel-round #2 / W2-K concern, plan §10's own W2-K row) — it writes ONLY to the separate,
durable :class:`~tos_runtime.rcl.log.SqliteCommitLog`, the authoritative capacity ledger design
#40 D2.1 establishes. The engine's in-process projection therefore stays occupied for the life
of the process regardless of what this consumer does — a disclosed, accepted limit (plan §10's
own "정직 상태" note), not a bug this module works around.

**Called by, never calling, the driver.** :mod:`tos_runtime.engine.finality_projection`'s
``project_finality`` invokes :meth:`FinalityReleaseConsumer.consume` once per genuinely-
``APPLIED`` ``EGRESS_RESULT``, AFTER the durable ``attempt_finality_witness`` row and (for a
``FULL_FILL``) the ``POSTTRADE_FINALITY_PROOF``/``ECONOMIC_OBLIGATION`` evidence rows are
already committed — this consumer never produces those two rows itself for a ``FULL_FILL``; it
only RE-LOADS them from the evidence store (never the in-memory
:class:`~tos.posttrade.records.PostTradeFinalityProof` object the driver just built) as its own
independent read of durable truth.

**Every gate is a conjunction; any non-positive gate holds, never releases (plan §3 "주문 응답으로
finality 판정" is a rejected alternative).** Per attempt:

1. The durable witness row (:func:`tos_runtime.rcl.finality_witness.finality_witness_for`'s own
   output, read back via :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.finality_witness`)
   must be ``True`` — checked only on the ``FULL_FILL`` path, where the driver already derived it
   from the SAME proof this consumer re-loads.
2. The :class:`~tos.posttrade.records.PostTradeFinalityProof` (or, for a non-execution
   destination, the :class:`~tos.posttrade.records.EconomicObligationRecord` this consumer
   itself produces AFTER step 3 below) must be durably re-loadable from the evidence store by
   this exact attempt id.
3. :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` must report
   ``permits_capacity_release is True`` AND this attempt's own classification must be
   :attr:`~tos_runtime.recon.service.ReconciliationClass.MATCHED` — the SAME conjunction
   :mod:`tos_runtime.recovery.reconciliation` already requires for a possibly-live attempt to
   clear (W1); this consumer never relaxes it.
4. The kernel :func:`~tos.posttrade.predicates.finality_proof_non_transferable` (against this
   attempt's OWN expected leg scope + the re-loaded obligation's own identity/version — never
   the proof's own claimed scope compared to itself, which would be vacuous) and
   :func:`~tos.posttrade.predicates.finality_proof_current` (against the re-loaded obligation's
   own ``obligation_generation`` — this runtime implements no correction/generation-advance
   mechanism yet, so this is always the SAME generation the proof was issued under; the check is
   still real, not vacuous, because a future correction lane would advance it) must both hold.

Any non-positive gate records ``CAPACITY_RELEASE_HELD`` (with the reason) and performs NO RCL
transition. Every positive path records ``CAPACITY_RELEASE_INTENT`` BEFORE calling
:func:`~tos_runtime.rcl.finality_witness.release_reservation` — evidence always precedes the RCL
mutation it intends, mirroring this runtime's own halt-then-append convention everywhere else
(:func:`~tos_runtime.evidence.emergency.record_halt`'s own discipline, inverted for a positive
outcome instead of a halt).

**Destinations.** A ``FULL_FILL`` targets :attr:`~tos.rcl.CapacityState.POSITION_CONSUMED`; a
``CANCEL_ACK``/``EXPIRED``/``REJECT`` targets :attr:`~tos.rcl.CapacityState.RELEASED`, gated on a
FRESHLY-PRODUCED non-execution proof (:meth:`~tos_runtime.posttrade.finality
.SyntheticFinalityProducer.produce_non_execution`, filled zero / remaining zero) that this
consumer itself appends to evidence and then re-loads — never produced from the payload alone,
only after step 3's reconciliation corroborates non-execution. Every other result kind (``ACK``,
``PARTIAL_FILL``, ``UNKNOWN``, ``TIMEOUT``) has no release destination at all and this consumer
does nothing for it — not even a ``CAPACITY_RELEASE_HELD`` row, since no release was ever
attempted.

**Obligation expiry (plan §10 row ④, record-only).** On every call, regardless of the current
attempt's own kind, :meth:`consume` also checks the SCOPE reservation's current projected state:
once it has sat in ``RELEASE_PENDING_PROOF``/``QUARANTINED_UNKNOWN`` longer than
``release_proof_wait_ms`` (as measured from this consumer's own first observation of that state
— the RCL log's ``reservations`` table carries no per-transition timestamp to measure from,
disclosed rather than fabricated), a ``RELEASE_PROOF_OVERDUE`` evidence row is appended ONCE.
This is a record, never a state change or an incident response — an operator or a future lane
reads it.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``json``, ``dataclasses``,
``decimal``, ``enum``) + ``tos.canonical``/``tos.engine.records``/``tos.engine.vocabulary``/
``tos.posttrade``/``tos.rcl`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

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

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.rcl.finality_witness import release_reservation
from tos_runtime.rcl.log import ReservationTransitionRefusal, SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.service import (
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)

# TOS Phase 5 W1 factory reuse (team-lead directive, plan §10 row ①③): the EXACT same
# reservation-id bridge and freshness derivation W1's recovery-barrier reconciliation already
# uses, never a second, possibly-diverging construction. Both are module-private in their own
# package because this consumer is their only cross-lane reuse site so far.
from tos_runtime.recovery.reconciliation import (  # noqa: SLF001
    _build_freshness_marker,
)
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "CAPACITY_RELEASE_HELD_KIND",
    "CAPACITY_RELEASE_INTENT_KIND",
    "RELEASE_PROOF_OVERDUE_KIND",
    "FinalityReleaseConsumer",
    "ReleaseHoldReason",
]

#: The obligation-record evidence kind this consumer appends for a freshly-produced
#: non-execution proof — the SAME literal :mod:`tos_runtime.engine.finality_projection` uses for
#: the driver's own ``FULL_FILL`` path (single source of truth for the kind string).
_ECONOMIC_OBLIGATION_KIND = "ECONOMIC_OBLIGATION"
#: The finality-proof evidence kind — same literal, both call sites.
_POSTTRADE_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
#: The literal prefix :mod:`tos_runtime.posttrade.finality`'s own ``idempotency_key`` uses for a
#: proof (cited, not re-derived — mirrors :mod:`tos_runtime.recon.evidence_reader`'s own
#: "disclosed coupling" section for the identical literal).
_FINALITY_PROOF_IDEMPOTENCY_PREFIX = "synthetic-fqp-proof:"
_OBLIGATION_IDEMPOTENCY_PREFIX = "synthetic-fqp-obligation:"

#: Evidence kind appended BEFORE every RCL release attempt (module docstring).
CAPACITY_RELEASE_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
#: Evidence kind appended for every non-positive gate — no RCL transition follows it.
CAPACITY_RELEASE_HELD_KIND = "CAPACITY_RELEASE_HELD"
#: Evidence kind for the record-only obligation-expiry observation (plan §10 row ④).
RELEASE_PROOF_OVERDUE_KIND = "RELEASE_PROOF_OVERDUE"
#: The FIRST-observed marker this consumer records for an overdue-candidate reservation state —
#: read back on a later call to measure elapsed time (module docstring's "disclosed, not
#: fabricated").
_RELEASE_PROOF_WAIT_START_KIND = "RELEASE_PROOF_WAIT_START"

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
            — freshness for every :meth:`~tos_runtime.recon.service.ReconciliationService
            .reconcile` call is derived FRESH from this on every :meth:`consume` call (never a
            marker captured once at wiring time, since :meth:`consume` runs on every applied
            result for the life of the process — the W1 recovery-barrier factory this consumer
            reuses instead captures it once because THAT call happens once, at boot).
        finality_producer: A :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer`
            used ONLY for :meth:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer
            .produce_non_execution` here (the driver's own instance already produced any
            ``FULL_FILL`` proof before this consumer runs) — a second, functionally-identical
            instance of a stateless, pure-function dataclass; never shared mutable state.
        scheme: The canonicalization scheme for command digests.
        monotonic_source: The injected monotonic clock for the obligation-expiry check (never a
            direct ``time.monotonic()`` read — design #40 D1.1).
        account: The single scope account this compose root is bound to.
        instrument: The single scope instrument this compose root is bound to.
        release_proof_wait_ms: The obligation-expiry bound (module docstring's row ④).
    """

    rcl_log: SqliteCommitLog
    projection: SqliteReservationProjectionReader
    evidence_store: SqliteEvidenceStore
    inbox: SqliteEventInbox
    recon_service: ReconciliationService
    time_service: TrustworthyTimeService
    finality_producer: SyntheticFinalityProducer
    scheme: CanonicalizationScheme
    monotonic_source: MonotonicSource
    account: str
    instrument: str
    release_proof_wait_ms: int

    # -- entry point -----------------------------------------------------------------

    def consume(self, payload: EgressResultPayload) -> None:
        """Attempt a release for one genuinely-``APPLIED`` ``EGRESS_RESULT`` payload.

        Args:
            payload: The re-injected ``EGRESS_RESULT`` payload the driver just applied — the
                SAME payload :mod:`tos_runtime.engine.finality_projection` passed its own
                finality producer.
        """
        reservation_id = self._reservation_id()
        self._check_obligation_expiry(reservation_id=reservation_id)

        if payload.kind is EgressResultKind.FULL_FILL:
            self._consume_full_fill(payload, reservation_id=reservation_id)
        elif payload.kind in _NON_EXECUTION_KINDS:
            self._consume_non_execution(payload, reservation_id=reservation_id)
        # else: ACK / PARTIAL_FILL / UNKNOWN / TIMEOUT -- no release destination at all
        # (module docstring); nothing recorded, since no release was ever attempted.

    def _reservation_id(self) -> str:
        """Mirrors :class:`~tos_runtime.rcl.obligation.CapacityObligationRecorder`'s own
        formula — the SAME per-``(account, instrument)`` scope identity every wiring site in
        this compose root already uses (module docstring)."""
        return f"resv-{self.account}-{self.instrument}"

    # -- FULL_FILL -> POSITION_CONSUMED -----------------------------------------------

    def _consume_full_fill(
        self, payload: EgressResultPayload, *, reservation_id: str
    ) -> None:
        witness = self.inbox.finality_witness(payload.attempt_id)
        if witness is not True:
            self._hold(payload, reservation_id, ReleaseHoldReason.NO_WITNESS)
            return
        proof = self._reload_proof(payload.attempt_id)
        obligation = self._reload_obligation(payload.attempt_id)
        if proof is None or obligation is None:
            self._hold(payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED)
            return
        self._corroborate_and_release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            obligation=obligation,
            to_state=CapacityState.POSITION_CONSUMED,
        )

    # -- CANCEL_ACK / EXPIRED / REJECT -> RELEASED ------------------------------------

    def _consume_non_execution(
        self, payload: EgressResultPayload, *, reservation_id: str
    ) -> None:
        report, corroborated = self._reconcile(payload.attempt_id)
        if report is None:
            self._hold(
                payload, reservation_id, ReleaseHoldReason.RECONCILIATION_UNAVAILABLE
            )
            return
        if not corroborated:
            self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NOT_CORROBORATED,
                detail=report.reason,
            )
            return
        produced = self.finality_producer.produce_non_execution(payload)
        if produced is None:
            self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NON_EXECUTION_PROOF_UNPRODUCIBLE,
            )
            return
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
        proof = self._reload_proof(payload.attempt_id)
        obligation = self._reload_obligation(payload.attempt_id)
        if proof is None or obligation is None:
            self._hold(payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED)
            return
        self._release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            report_reason=report.reason,
            to_state=CapacityState.RELEASED,
        )

    # -- shared gate 3 (reconciliation) + gate 4 (non-transferable/current) ----------

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

    def _corroborate_and_release(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        proof: PostTradeFinalityProof,
        obligation: EconomicObligationRecord,
        to_state: CapacityState,
    ) -> None:
        report, corroborated = self._reconcile(payload.attempt_id)
        if report is None:
            self._hold(
                payload, reservation_id, ReleaseHoldReason.RECONCILIATION_UNAVAILABLE
            )
            return
        if not corroborated:
            self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NOT_CORROBORATED,
                detail=report.reason,
            )
            return
        target_scope = ObligationLegScope(
            leg=ObligationLegDirection.RECEIPT,
            account=self.account,
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
            self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_TRANSFERABLE
            )
            return
        if not finality_proof_current(proof, obligation.obligation_generation):
            self._hold(payload, reservation_id, ReleaseHoldReason.PROOF_NOT_CURRENT)
            return
        self._release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            report_reason=report.reason,
            to_state=to_state,
        )

    # -- the RCL mutation itself -------------------------------------------------------

    def _release(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        proof: PostTradeFinalityProof,
        report_reason: str | None,
        to_state: CapacityState,
    ) -> None:
        current_state = self.projection.reservation_state(reservation_id)
        if current_state is None:
            self._hold(payload, reservation_id, ReleaseHoldReason.NO_RESERVATION)
            return
        current_seq = self.projection.reservation_last_seq(reservation_id)
        expected_seq = -1 if current_seq is None else current_seq
        self.evidence_store.append(
            {
                "attempt_id": payload.attempt_id,
                "reservation_id": reservation_id,
                "proof_id": proof.proof_id,
                "destination": to_state.value,
                "report_reason": report_reason,
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
            self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.RCL_TRANSITION_REFUSED,
                detail=str(exc),
            )

    # -- HELD ---------------------------------------------------------------------------

    def _hold(
        self,
        payload: EgressResultPayload,
        reservation_id: str,
        reason: ReleaseHoldReason,
        *,
        detail: str | None = None,
    ) -> None:
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

    # -- durable re-loads (module docstring's "never an in-memory proof object") -------

    def _reload_proof(self, attempt_id: str) -> PostTradeFinalityProof | None:
        idempotency_key = f"{_FINALITY_PROOF_IDEMPOTENCY_PREFIX}{attempt_id}"
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
            (_POSTTRADE_FINALITY_PROOF_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("idempotency_key") == idempotency_key:
                return PostTradeFinalityProof.model_validate(decoded)
        return None

    def _reload_obligation(self, attempt_id: str) -> EconomicObligationRecord | None:
        idempotency_key = f"{_OBLIGATION_IDEMPOTENCY_PREFIX}{attempt_id}"
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
        state = self.projection.reservation_state(reservation_id)
        if state not in _OVERDUE_ELIGIBLE_STATES:
            return
        now_ms = self.monotonic_source.now_ms()
        first_observed_ms = self._read_wait_start(reservation_id)
        if first_observed_ms is None:
            self.evidence_store.append(
                {
                    "reservation_id": reservation_id,
                    "state": state.value,
                    "first_observed_ms": now_ms,
                },
                kind=_RELEASE_PROOF_WAIT_START_KIND,
                record_class=_RELEASE_PROOF_WAIT_START_KIND,
            )
            return
        if now_ms - first_observed_ms < self.release_proof_wait_ms:
            return
        if self._overdue_already_recorded(reservation_id):
            return
        self.evidence_store.append(
            {
                "reservation_id": reservation_id,
                "state": state.value,
                "waited_ms": now_ms - first_observed_ms,
            },
            kind=RELEASE_PROOF_OVERDUE_KIND,
            record_class=RELEASE_PROOF_OVERDUE_KIND,
        )

    def _read_wait_start(self, reservation_id: str) -> int | None:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (_RELEASE_PROOF_WAIT_START_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("reservation_id") == reservation_id:
                value = decoded.get("first_observed_ms")
                return value if isinstance(value, int) else None
        return None

    def _overdue_already_recorded(self, reservation_id: str) -> bool:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (RELEASE_PROOF_OVERDUE_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("reservation_id") == reservation_id:
                return True
        return False
