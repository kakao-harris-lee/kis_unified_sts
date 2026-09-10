"""``ReconciliationService`` — Phase 5 W1 three-way reconciliation (plan §2 decision 3).

Assembles three independently-sourced observations — RCL reservation state
(:class:`~tos_runtime.rcl.projection.ReservationProjectionReader`), durably recorded
egress-result receipts (:class:`~tos_runtime.recon.ports.EvidenceReceiptReader`), and a
broker witness (:class:`~tos_runtime.recon.ports.BrokerWitness`) — into the kernel
``tos.recon`` predicate inputs and calls those predicates for every judgement (**판정은
커널 술어만 한다** — the ``tos_runtime.currentness.vector.CurrentnessAssembler`` precedent:
this service authors no boolean a kernel predicate could produce instead).

**Independence-class assignment (design #9 §0.2/§4.2 — injected, never computed).** Each
observation path gets its own label:

* ``RCL_RESERVATION_LOG`` — a reservation existing in the RCL commit log (a separate
  sqlite file from the evidence store, design #40 D3.1);
* ``EVIDENCE_RECEIPT`` — a durably recorded ``EGRESS_RESULT`` receipt;
* ``BROKER_WITNESS`` — the injected :class:`~tos_runtime.recon.ports.BrokerWitness`.

See :mod:`tos_runtime.recon.witness_synthetic`'s module docstring for the disclosed Phase 5
caveat: today's one ``BrokerWitness`` implementation (``SyntheticLedgerWitness``) reads the
same durable store as the ``EVIDENCE_RECEIPT`` path, so a CORROBORATED verdict resting only
on those two paths (without RCL) is not yet genuine broker-independent corroboration. This
service does not special-case that today — it assigns the labels above unconditionally by
structural path, as ``tos.recon``'s own state.py docstring says independence must be an
injected caller judgment — and relies on the disclosure in the witness module plus a future
real (KIS) ``BrokerWitness`` to make it substantively true.

**Runtime-only classification vocabulary.** The kernel ``tos.recon`` package classifies
per-FIELD confidence only (``FieldConfidenceClass``) — it has no per-attempt three-way
classification concept. :class:`ReconciliationClass` is added here, purely for reporting;
it feeds nothing back into any kernel predicate.

**Fail-closed throughout (plan §2 decision 3).** A :class:`~tos_runtime.recon.ports
.WitnessUnavailable` witness, an empty scope, or any per-field conflict all yield
``permits_capacity_release=False`` / ``permits_rearm=False`` — never a vacuous ``True``
from "nothing to disagree with" (mirrors ``tos.recon.predicates.classify_field``'s own
"0 usable paths => UNKNOWN, never a vacuous CORROBORATED").

**Pure judgement — mutates nothing.** This module holds no RCL commit-log writer, no
evidence-store append call, and reads no clock (freshness is an injected
:class:`~tos.recon.FreshnessMarker` parameter — ``tos.recon`` itself is clock-free, design
#9 §3.5). See ``tos/runtime/tests/recon/test_service.py``'s negative-grep test.

**``attempt_id`` vs ``reservation_id`` (Phase 5 W1 close-out).** This module never assumed the
two share one identity space, but shipped no bridge between them until a real caller measured
the gap directly: a compose root whose RCL commit log keys reservations at SCOPE granularity
(one reservation per ``(account, instrument)``, shared by every attempt in that scope — e.g.
:class:`~tos_runtime.rcl.obligation.CapacityObligationRecorder`'s own
``reservation_id_resolver``) would otherwise see :meth:`ReconciliationService.reconcile` call
``rcl_reader.reservation_state`` with the wrong key for every attempt, so ``rcl_present`` is
always ``False`` and :class:`ReconciliationClass.MATCHED` — and therefore any capacity
release/re-arm — is structurally unreachable. The constructor's optional
``reservation_id_for_attempt`` callable closes this: an injected caller-side mapping from
attempt id to whatever identity the caller's own ``rcl_reader`` actually uses, defaulting to the
identity mapping (unchanged behaviour for a caller whose RCL projection genuinely is
per-attempt).

Firewall: stdlib + ``tos.recon`` + ``tos.rcl`` (``CapacityState`` only, for the type
signature this service reads through) + ``tos_runtime.recon.ports`` only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tos.recon import (
    ConservativeBound,
    EvidencePathObservation,
    FieldConfidence,
    FreshnessMarker,
    ReleaseProofInputs,
    SafetyRelevantField,
    any_field_conflicted,
    classify_field,
    conservative_bound_of,
    field_specific_release_proof_ok,
    is_corroborated,
)

from tos_runtime.recon.ports import (
    BrokerWitness,
    EgressReceiptObservation,
    EvidenceReceiptReader,
    ReservationProjectionReader,
    WitnessOrder,
    WitnessScope,
    WitnessUnavailable,
)

__all__ = [
    "AttemptClassification",
    "ReconciliationClass",
    "ReconciliationReport",
    "ReconciliationService",
]

#: See module docstring "Independence-class assignment".
_RCL_INDEPENDENCE_CLASS = "RCL_RESERVATION_LOG"
_EVIDENCE_INDEPENDENCE_CLASS = "EVIDENCE_RECEIPT"
_WITNESS_INDEPENDENCE_CLASS = "BROKER_WITNESS"

#: The two capacity-releasing fields this service actually has quantity data for
#: (``tos.recon.CAPACITY_RELEASING_FIELDS`` names both; RCL carries no per-dimension
#: usage magnitude today — same landed-projection gap ``tos_runtime.risk.aggregate``'s own
#: module docstring already reports — so only the evidence-receipt and witness paths ever
#: contribute an observation for these two fields).
_QUANTITY_FIELDS: tuple[SafetyRelevantField, SafetyRelevantField] = (
    SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
    SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY,
)


class ReconciliationClass(StrEnum):
    """Runtime-only per-attempt three-way classification (module docstring)."""

    #: All three paths (RCL, evidence receipt, broker witness) report the same attempt.
    MATCHED = "MATCHED"
    #: RCL-only — a reservation with no corroborating downstream receipt or witness order.
    STALE_RESERVATION = "STALE_RESERVATION"
    #: Witness-only — a broker order with no RCL reservation and no evidence receipt.
    ORPHAN_BROKER_ORDER = "ORPHAN_BROKER_ORDER"
    #: Evidence-only — a recorded egress-result receipt with no live reservation or
    #: witness order.
    RECEIPT_ONLY = "RECEIPT_ONLY"


@dataclass(frozen=True)
class AttemptClassification:
    """One attempt's (or orphan order's) :class:`ReconciliationClass` verdict."""

    attempt_id: str | None
    classification: ReconciliationClass
    broker_execution_id: str | None = None


@dataclass(frozen=True)
class ReconciliationReport:
    """The result of one :meth:`ReconciliationService.reconcile` call.

    ``permits_capacity_release`` / ``permits_rearm`` are both ``True`` only when every
    attempt (and orphan order) in scope independently passes its own gate — a conjunction,
    never an average or a majority (mirrors ``tos.recon``'s own no-blended-release
    discipline at the report level).
    """

    field_confidences: tuple[FieldConfidence, ...]
    classifications: tuple[AttemptClassification, ...]
    permits_capacity_release: bool
    permits_rearm: bool
    reason: str | None = None


def _order_existence_observations(
    *,
    rcl_present: bool,
    evidence: EgressReceiptObservation | None,
    witness_order: WitnessOrder | None,
    freshness: FreshnessMarker,
) -> tuple[EvidencePathObservation, ...]:
    """Build the ``ORDER_EXISTENCE`` observations for one attempt/order.

    Each present path asserts existence with no magnitude (``ConservativeBound()``) and
    ``agrees_within_tolerance=True`` — existence has no partial-agreement notion; a path
    either reports the attempt or it does not (an absent path is simply fewer usable
    observations, never a recorded disagreement, matching ``classify_field``'s own "fewer
    paths -> SINGLE_SOURCE/UNKNOWN" degradation rather than an invented conflict).
    """
    observations: list[EvidencePathObservation] = []
    if rcl_present:
        observations.append(
            EvidencePathObservation(
                field=SafetyRelevantField.ORDER_EXISTENCE,
                source_ref="rcl",
                independence_class=_RCL_INDEPENDENCE_CLASS,
                asserted_bound=ConservativeBound(),
                agrees_within_tolerance=True,
                freshness_marker=freshness,
            )
        )
    if evidence is not None:
        observations.append(
            EvidencePathObservation(
                field=SafetyRelevantField.ORDER_EXISTENCE,
                source_ref=evidence.source_ref,
                independence_class=_EVIDENCE_INDEPENDENCE_CLASS,
                asserted_bound=ConservativeBound(),
                agrees_within_tolerance=True,
                freshness_marker=freshness,
            )
        )
    if witness_order is not None:
        observations.append(
            EvidencePathObservation(
                field=SafetyRelevantField.ORDER_EXISTENCE,
                source_ref="witness",
                independence_class=_WITNESS_INDEPENDENCE_CLASS,
                asserted_bound=ConservativeBound(),
                agrees_within_tolerance=True,
                freshness_marker=freshness,
            )
        )
    return tuple(observations)


def _quantity_observations(
    *,
    field: SafetyRelevantField,
    evidence_value: Decimal | None,
    witness_value: Decimal | None,
    freshness: FreshnessMarker,
    evidence_source_ref: str,
) -> tuple[EvidencePathObservation, ...]:
    """Build the observations for one quantity field from the two paths that carry a
    magnitude at all (module docstring — RCL carries none). Agreement is exact equality:
    Phase 5 injects no Verification Profile tolerance value, so this is the conservative
    (strictest) default until a caller-injected tolerance replaces it.
    """
    observations: list[EvidencePathObservation] = []
    if evidence_value is not None:
        agrees = witness_value is not None and evidence_value == witness_value
        observations.append(
            EvidencePathObservation(
                field=field,
                source_ref=evidence_source_ref,
                independence_class=_EVIDENCE_INDEPENDENCE_CLASS,
                asserted_bound=ConservativeBound(
                    lower=evidence_value, upper=evidence_value
                ),
                agrees_within_tolerance=(agrees if witness_value is not None else None),
                freshness_marker=freshness,
            )
        )
    if witness_value is not None:
        agrees = evidence_value is not None and evidence_value == witness_value
        observations.append(
            EvidencePathObservation(
                field=field,
                source_ref="witness",
                independence_class=_WITNESS_INDEPENDENCE_CLASS,
                asserted_bound=ConservativeBound(
                    lower=witness_value, upper=witness_value
                ),
                agrees_within_tolerance=(
                    agrees if evidence_value is not None else None
                ),
                freshness_marker=freshness,
            )
        )
    return tuple(observations)


def _classify_attempt(
    *,
    rcl_present: bool,
    evidence: EgressReceiptObservation | None,
    witness_order: WitnessOrder | None,
) -> ReconciliationClass:
    """The runtime-only three-way classification (module docstring)."""
    has_evidence = evidence is not None
    has_witness = witness_order is not None
    if rcl_present and has_evidence and has_witness:
        return ReconciliationClass.MATCHED
    if rcl_present and not has_witness:
        # RCL-only, or RCL + a receipt but no broker confirmation — still not confirmed
        # live by any downstream path; conservatively "stale reservation" either way.
        return ReconciliationClass.STALE_RESERVATION
    if has_witness and not rcl_present:
        return ReconciliationClass.ORPHAN_BROKER_ORDER
    return ReconciliationClass.RECEIPT_ONLY


class ReconciliationService:
    """Assembles the three observation paths and calls the kernel ``tos.recon``
    predicates for every judgement (module docstring)."""

    def __init__(
        self,
        rcl_reader: ReservationProjectionReader,
        evidence_reader: EvidenceReceiptReader,
        witness: BrokerWitness,
        *,
        reservation_id_for_attempt: Callable[[str], str | None] | None = None,
    ) -> None:
        """Bind this service to its three injected observation ports.

        Args:
            rcl_reader: Read-only RCL reservation-projection port.
            evidence_reader: Read-only evidence-receipt port.
            witness: The broker-witness port. See module docstring's independence-class
                caveat for what a ``SyntheticLedgerWitness`` injection here does and does
                not establish.
            reservation_id_for_attempt: Maps an ``attempt_id`` (as reported by the
                evidence-receipt / witness observations) onto the identity
                :attr:`rcl_reader` actually keys its reservation projection by. This
                package's own predicates (design #9) never assume ``attempt_id`` and
                ``reservation_id`` share one identity space — a caller whose RCL commit log
                keys reservations differently from its attempt ids (e.g. a scope-level
                reservation id shared by every attempt in that scope — the SAME identity
                :class:`~tos_runtime.rcl.obligation.CapacityObligationRecorder`'s own
                ``reservation_id_resolver`` already produces for exactly that reason)
                supplies this to bridge the gap. Defaults to ``None``, which means "``rcl_reader``
                is keyed by attempt id directly" (the identity mapping — unchanged pre-existing
                behaviour for a caller whose RCL projection genuinely is per-attempt). Called
                once per attempt per :meth:`reconcile`; returning ``None`` for a given attempt id
                is treated exactly like "no mapping known", i.e. :meth:`reconcile` looks up
                ``rcl_reader.reservation_state`` with the ORIGINAL ``attempt_id`` unchanged (never
                silently skips the RCL path) — this function narrows, it does not gate.
        """
        self._rcl_reader = rcl_reader
        self._evidence_reader = evidence_reader
        self._witness = witness
        self._reservation_id_for_attempt = reservation_id_for_attempt

    def _reservation_id_for(self, attempt_id: str) -> str:
        """Resolve ``attempt_id`` onto the identity :attr:`_rcl_reader` is actually keyed by
        (constructor's own ``reservation_id_for_attempt`` docstring) — the identity mapping when
        no resolver was injected, or the resolver's own mapping otherwise (falling back to the
        identity mapping if the resolver itself returns ``None`` for this attempt — narrows,
        never gates)."""
        if self._reservation_id_for_attempt is None:
            return attempt_id
        resolved = self._reservation_id_for_attempt(attempt_id)
        return attempt_id if resolved is None else resolved

    def _attempt_field_confidences_and_gates(
        self,
        *,
        rcl_present: bool,
        evidence: EgressReceiptObservation | None,
        witness_order: WitnessOrder | None,
        freshness: FreshnessMarker,
    ) -> tuple[ReconciliationClass, tuple[FieldConfidence, ...], bool, bool]:
        """One attempt's classification, field confidences, rearm-ok, capacity-ok.

        Split out of :meth:`reconcile` to stay under the module's function size budget.
        """
        classification = _classify_attempt(
            rcl_present=rcl_present, evidence=evidence, witness_order=witness_order
        )

        existence_obs = _order_existence_observations(
            rcl_present=rcl_present,
            evidence=evidence,
            witness_order=witness_order,
            freshness=freshness,
        )
        existence_confidence = FieldConfidence(
            field=SafetyRelevantField.ORDER_EXISTENCE,
            confidence_class=classify_field(existence_obs, freshness),
            bound=ConservativeBound(),
            freshness_marker=freshness,
        )

        field_confidences = [existence_confidence]
        proof_ok_by_field: dict[SafetyRelevantField, bool] = {}
        fqp_token = evidence.finality_proof_recorded if evidence is not None else False
        proof_inputs = ReleaseProofInputs(
            final_quantity_proof_token=fqp_token, freshness=freshness
        )

        evidence_values = {
            SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY: (
                None if evidence is None else evidence.filled_quantity
            ),
            SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY: (
                None if evidence is None else evidence.remaining_quantity
            ),
        }
        witness_values = {
            SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY: (
                None if witness_order is None else witness_order.quantity
            ),
            SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY: (
                None if witness_order is None else witness_order.remaining
            ),
        }
        evidence_source_ref = "" if evidence is None else evidence.source_ref

        for field in _QUANTITY_FIELDS:
            obs = _quantity_observations(
                field=field,
                evidence_value=evidence_values[field],
                witness_value=witness_values[field],
                freshness=freshness,
                evidence_source_ref=evidence_source_ref,
            )
            confidence = FieldConfidence(
                field=field,
                confidence_class=classify_field(obs, freshness),
                bound=conservative_bound_of(obs),
                freshness_marker=freshness,
            )
            field_confidences.append(confidence)
            proof_ok_by_field[field] = field_specific_release_proof_ok(
                field, confidence, proof_inputs
            )

        conflicted = any_field_conflicted(tuple(field_confidences))
        rearm_ok = (
            classification is ReconciliationClass.MATCHED
            and not conflicted
            and is_corroborated(existence_obs, freshness)
        )
        capacity_ok = (
            classification is ReconciliationClass.MATCHED
            and not conflicted
            and all(proof_ok_by_field.values())
        )
        return classification, tuple(field_confidences), rearm_ok, capacity_ok

    def _reconcile_attempt(
        self,
        attempt_id: str,
        *,
        receipts_by_attempt: dict[str, EgressReceiptObservation],
        witness_by_attempt: dict[str, WitnessOrder],
        freshness: FreshnessMarker,
    ) -> tuple[AttemptClassification, tuple[FieldConfidence, ...], bool, bool]:
        """One known attempt id's full verdict — split out of :meth:`reconcile` to stay
        under the module's function size budget."""
        rcl_state = self._rcl_reader.reservation_state(
            self._reservation_id_for(attempt_id)
        )
        evidence = receipts_by_attempt.get(attempt_id)
        witness_order = witness_by_attempt.get(attempt_id)
        classification, confidences, rearm_ok, capacity_ok = (
            self._attempt_field_confidences_and_gates(
                rcl_present=rcl_state is not None,
                evidence=evidence,
                witness_order=witness_order,
                freshness=freshness,
            )
        )
        record = AttemptClassification(
            attempt_id=attempt_id,
            classification=classification,
            broker_execution_id=(
                None if witness_order is None else witness_order.broker_execution_id
            ),
        )
        return record, confidences, rearm_ok, capacity_ok

    @staticmethod
    def _classify_orphan_order(
        order: WitnessOrder, *, freshness: FreshnessMarker
    ) -> tuple[AttemptClassification, FieldConfidence]:
        """One orphan broker order's verdict — split out of :meth:`reconcile`."""
        existence_obs = _order_existence_observations(
            rcl_present=False, evidence=None, witness_order=order, freshness=freshness
        )
        confidence = FieldConfidence(
            field=SafetyRelevantField.ORDER_EXISTENCE,
            confidence_class=classify_field(existence_obs, freshness),
            bound=ConservativeBound(),
            freshness_marker=freshness,
        )
        record = AttemptClassification(
            attempt_id=None,
            classification=ReconciliationClass.ORPHAN_BROKER_ORDER,
            broker_execution_id=order.broker_execution_id,
        )
        return record, confidence

    def reconcile(
        self, scope: WitnessScope, *, freshness: FreshnessMarker = FreshnessMarker()
    ) -> ReconciliationReport:
        """Reconcile ``scope`` across RCL, evidence receipts, and the broker witness.

        Args:
            scope: The (account, instrument, attempt) window to reconcile.
            freshness: The injected freshness/time-confidence marker applied uniformly to
                every field this call assesses (``tos.recon`` is clock-free — see module
                docstring). Defaults to the all-``None`` marker, which fails closed
                (``tos.recon.predicates.freshness_ok`` is ``False`` on any ``None``).

        Returns:
            The assembled :class:`ReconciliationReport`. ``permits_capacity_release`` /
            ``permits_rearm`` are conjunctions over every attempt and orphan order found —
            an empty scope (nothing observed anywhere) yields ``False`` for both, never a
            vacuous ``True`` (module docstring "fail-closed throughout").
        """
        try:
            snapshot = self._witness.observe(scope)
        except WitnessUnavailable as exc:
            return ReconciliationReport(
                field_confidences=(),
                classifications=(),
                permits_capacity_release=False,
                permits_rearm=False,
                reason=f"broker witness unavailable: {exc}",
            )

        receipts = self._evidence_reader.receipts(scope)
        receipts_by_attempt = {
            r.attempt_id: r for r in receipts if r.attempt_id is not None
        }
        witness_by_attempt = {
            o.attempt_id: o for o in snapshot.orders if o.attempt_id is not None
        }
        orphan_orders = tuple(o for o in snapshot.orders if o.attempt_id is None)
        attempt_ids = (
            set(scope.attempt_ids) | set(receipts_by_attempt) | set(witness_by_attempt)
        )

        classifications: list[AttemptClassification] = []
        field_confidences: list[FieldConfidence] = []
        rearm_flags: list[bool] = []
        capacity_flags: list[bool] = []

        for attempt_id in sorted(attempt_ids):
            record, confidences, rearm_ok, capacity_ok = self._reconcile_attempt(
                attempt_id,
                receipts_by_attempt=receipts_by_attempt,
                witness_by_attempt=witness_by_attempt,
                freshness=freshness,
            )
            classifications.append(record)
            field_confidences.extend(confidences)
            rearm_flags.append(rearm_ok)
            capacity_flags.append(capacity_ok)

        for order in orphan_orders:
            record, confidence = self._classify_orphan_order(order, freshness=freshness)
            classifications.append(record)
            field_confidences.append(confidence)
            rearm_flags.append(False)
            capacity_flags.append(False)

        reason = None if rearm_flags else "no observations in scope"
        return ReconciliationReport(
            field_confidences=tuple(field_confidences),
            classifications=tuple(classifications),
            permits_capacity_release=bool(capacity_flags) and all(capacity_flags),
            permits_rearm=bool(rearm_flags) and all(rearm_flags),
            reason=reason,
        )
