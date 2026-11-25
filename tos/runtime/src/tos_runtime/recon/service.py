"""``ReconciliationService`` — Phase 5 W1 three-way reconciliation (plan §2 decision 3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tos.engine.vocabulary import EgressResultKind
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

from tos_runtime.rcl.projection import outstanding_reservations
from tos_runtime.recon.ports import (
    BrokerWitness,
    EgressReceiptObservation,
    EvidenceReceiptReader,
    ReservationProjectionReader,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)

__all__ = [
    "WITNESS_NOT_INDEPENDENT_REASON",
    "witness_independence_collapsed",
    "AttemptClassification",
    "ReconciliationClass",
    "ReconciliationReport",
    "ReconciliationService",
]

_RCL_INDEPENDENCE_CLASS = "RCL_RESERVATION_LOG"
_EVIDENCE_INDEPENDENCE_CLASS = "EVIDENCE_RECEIPT"
_WITNESS_INDEPENDENCE_CLASS = "BROKER_WITNESS"

WITNESS_NOT_INDEPENDENT_REASON = "WITNESS_NOT_INDEPENDENT"


def witness_independence_collapsed(report: ReconciliationReport | None) -> bool:
    """Whether the witness's lost independence is the ONLY reason ``report`` did not clear."""
    if report is None or report.reason != WITNESS_NOT_INDEPENDENT_REASON:
        return False
    if any_field_conflicted(report.field_confidences):
        return False
    return all(
        item.classification is ReconciliationClass.MATCHED
        for item in report.classifications
    )


_QUANTITY_FIELDS: tuple[SafetyRelevantField, SafetyRelevantField] = (
    SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
    SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY,
)

_ZERO = Decimal("0")

_NON_EXECUTION_RECEIPT_KINDS: frozenset[str] = frozenset(
    kind.value
    for kind in (
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    )
)


def _asserts_zero_execution(
    evidence: EgressReceiptObservation | None, *, any_filled: bool
) -> bool:
    """Whether this receipt states «nothing executed, nothing outstanding» by its KIND alone."""
    # SAFETY: the kernel FORBIDS a fill magnitude on a non-execution payload
    # (EgressResultPayload._fill_shape_consistent), so reading those two quantities as
    # «not stated» leaves both capacity-releasing fields SINGLE_SOURCE and holds every
    # cancelled order's reservation for ever (#939 r2 HIGH 1 · #948).
    #
    # SAFETY: `any_filled` is the attempt's OWN receipt history — a non-execution that
    # followed a fill does not mean «nothing executed», and reading it as zero would
    # release the capacity of a quantity the broker still reports (#980 path).
    return (
        not any_filled
        and evidence is not None
        and evidence.egress_result_kind in _NON_EXECUTION_RECEIPT_KINDS
        and evidence.filled_quantity is None
        and evidence.remaining_quantity is None
    )


def _attempts_with_a_filled_receipt(
    receipts: tuple[EgressReceiptObservation, ...],
) -> frozenset[str]:
    """Every attempt whose own receipts record a positive filled quantity."""
    return frozenset(
        receipt.attempt_id
        for receipt in receipts
        if receipt.attempt_id is not None
        and receipt.filled_quantity is not None
        and receipt.filled_quantity > _ZERO
    )


class ReconciliationClass(StrEnum):
    """Runtime-only per-attempt three-way classification (module docstring)."""

    MATCHED = "MATCHED"
    STALE_RESERVATION = "STALE_RESERVATION"
    ORPHAN_BROKER_ORDER = "ORPHAN_BROKER_ORDER"
    RECEIPT_ONLY = "RECEIPT_ONLY"


@dataclass(frozen=True)
class AttemptClassification:
    """One attempt's (or orphan order's) :class:`ReconciliationClass` verdict."""

    attempt_id: str | None
    classification: ReconciliationClass
    broker_execution_id: str | None = None


@dataclass(frozen=True)
class ReconciliationReport:
    """The result of one :meth:`ReconciliationService.reconcile` call."""

    field_confidences: tuple[FieldConfidence, ...]
    classifications: tuple[AttemptClassification, ...]
    permits_capacity_release: bool
    permits_rearm: bool
    reason: str | None = None
    observed_positions: tuple[tuple[str, Decimal], ...] = ()
    observed_positions_complete: bool = False


def _order_existence_observations(
    *,
    rcl_present: bool,
    evidence: EgressReceiptObservation | None,
    witness_order: WitnessOrder | None,
    freshness: FreshnessMarker,
    witness_independence_class: str,
) -> tuple[EvidencePathObservation, ...]:
    """Build the ``ORDER_EXISTENCE`` observations for one attempt/order."""
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
                independence_class=witness_independence_class,
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
    witness_independence_class: str,
) -> tuple[EvidencePathObservation, ...]:
    """Build the observations for one quantity field from the two paths that carry a"""
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
                independence_class=witness_independence_class,
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


def _quantity_field_verdicts(
    *,
    evidence: EgressReceiptObservation | None,
    witness_order: WitnessOrder | None,
    freshness: FreshnessMarker,
    witness_independence_class: str,
    proof_inputs: ReleaseProofInputs,
    asserts_zero_execution: bool = False,
) -> tuple[tuple[FieldConfidence, ...], dict[SafetyRelevantField, bool], bool]:
    """Both quantity fields' confidences, release-proof gates, and the disagreement flag."""
    evidence_values = {
        SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY: (
            _ZERO
            if asserts_zero_execution
            else (None if evidence is None else evidence.filled_quantity)
        ),
        SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY: (
            _ZERO
            if asserts_zero_execution
            else (None if evidence is None else evidence.remaining_quantity)
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

    confidences: list[FieldConfidence] = []
    proof_ok_by_field: dict[SafetyRelevantField, bool] = {}
    disagreed = False
    for field in _QUANTITY_FIELDS:
        obs = _quantity_observations(
            field=field,
            evidence_value=evidence_values[field],
            witness_value=witness_values[field],
            freshness=freshness,
            evidence_source_ref=evidence_source_ref,
            witness_independence_class=witness_independence_class,
        )
        confidence = FieldConfidence(
            field=field,
            confidence_class=classify_field(obs, freshness),
            bound=conservative_bound_of(obs),
            freshness_marker=freshness,
        )
        confidences.append(confidence)
        disagreed = disagreed or any(
            observation.agrees_within_tolerance is False for observation in obs
        )
        proof_ok_by_field[field] = field_specific_release_proof_ok(
            field, confidence, proof_inputs
        )
    return tuple(confidences), proof_ok_by_field, disagreed


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
        return ReconciliationClass.STALE_RESERVATION
    if has_witness and not rcl_present:
        return ReconciliationClass.ORPHAN_BROKER_ORDER
    return ReconciliationClass.RECEIPT_ONLY


def _execution_id(value: str | None) -> str | None:
    """A broker execution id as a join key: surrounding whitespace dropped (the KIS witness"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _join_orders_by_execution_id(
    snapshot: WitnessSnapshot,
    receipts: tuple[EgressReceiptObservation, ...],
    receipts_by_attempt: dict[str, EgressReceiptObservation],
) -> tuple[dict[str, WitnessOrder], tuple[WitnessOrder, ...]]:
    """Split witness orders into ``{attempt_id: order}`` and the remaining orphans (module"""
    orders = snapshot.orders
    by_attempt = {o.attempt_id: o for o in orders if o.attempt_id is not None}
    attempts_for_key: dict[tuple[str, str], set[str]] = {}
    keys_for_attempt: dict[str, set[tuple[str | None, str]]] = {}
    for receipt in receipts:
        if receipt.attempt_id is None or receipt.trading_date is None:
            continue
        receipt_id = _execution_id(receipt.broker_execution_id)
        keys_for_attempt.setdefault(receipt.attempt_id, set()).add(
            (receipt_id, receipt.trading_date)
        )
        if receipt_id is not None:
            attempts_for_key.setdefault((receipt_id, receipt.trading_date), set()).add(
                receipt.attempt_id
            )

    candidates: dict[str, list[WitnessOrder]] = {}
    orphans: list[WitnessOrder] = []
    for order in orders:
        if order.attempt_id is not None:
            continue
        order_id = _execution_id(order.broker_execution_id)
        key = (
            (order_id, order.order_date)
            if order_id is not None and order.order_date is not None
            else None
        )
        attempts = attempts_for_key.get(key, set()) if key is not None else set()
        attempt_id = next(iter(attempts)) if len(attempts) == 1 else None
        evidence = receipts_by_attempt.get(attempt_id) if attempt_id else None
        if (
            key is not None
            and attempt_id is not None
            and keys_for_attempt.get(attempt_id) == {key}
            and evidence is not None
            and (_execution_id(evidence.broker_execution_id), evidence.trading_date)
            == key
        ):
            candidates.setdefault(attempt_id, []).append(order)
        else:
            orphans.append(order)

    joined = dict(by_attempt)
    for attempt_id, matched in candidates.items():
        if len(matched) == 1 and attempt_id not in by_attempt:
            joined[attempt_id] = matched[0]
        else:
            orphans.extend(matched)
    return joined, tuple(orphans)


def _placed_before_our_first_order(
    order: WitnessOrder, ours: tuple[WitnessOrder, ...]
) -> bool:
    """Whether the broker's OWN clock puts ``order`` before every order in ``ours`` (2026-11-20)."""
    order_date, order_time = order.order_date, order.order_time
    if order_date is None or order_time is None or not ours:
        return False
    earliest: tuple[str, str] | None = None
    for own in ours:
        if own.order_date is None or own.order_time is None:
            return False
        stamp = (own.order_date, own.order_time)
        earliest = stamp if earliest is None else min(earliest, stamp)
    assert earliest is not None
    earliest_date, earliest_time = earliest
    if order_date != earliest_date:
        return False
    return order_time < earliest_time


_FINISHED_WITNESS_STATES = frozenset(
    (WitnessOrderState.FILLED, WitnessOrderState.CANCELLED)
)


def _is_finished(order: WitnessOrder) -> bool:
    """Whether the broker's OWN row says ``order`` can never fill again (2026-11-20)."""
    return (
        order.state in _FINISHED_WITNESS_STATES
        and order.remaining is not None
        and order.remaining <= 0
    )


def _settles_one_of_ours(order: WitnessOrder, ours: tuple[WitnessOrder, ...]) -> bool:
    """Whether ``order`` is the broker's own settled cancel row for one of OUR orders (#1169)."""
    # SAFETY: 모의 KIS 는 취소를 자기 ODNO 를 가진 «별도 행» 으로 적고 원주문을 orgn_odno 로
    # 가리킨다 (측정 2026-11-24). 그 행을 설명되지 않은 고아로 세면 취소가 벌어 온 바로 그
    # 해제를 스스로 막아, 취소된 주문의 예약이 영원히 풀리지 않는다.
    if order.state is not WitnessOrderState.CANCELLED or not _is_finished(order):
        return False
    # SAFETY: 체결 수량이 적힌 취소 행(또는 수량을 말하지 않는 행)은 «아무것도 체결하지 않고 거둬 갔다» 가 아니다 — 증인이 코퍼로보레이션에 요구하는 0 과 같은 0 을 여기서도 요구한다 (#1172 리뷰 MEDIUM)
    if order.quantity != _ZERO:
        return False
    origin = _execution_id(order.origin_execution_id)
    if origin is None:
        return False
    return origin in {
        own_id
        for own in ours
        if (own_id := _execution_id(own.broker_execution_id)) is not None
    }


def _orphans_may_be_ours(
    *,
    orphan_orders: tuple[WitnessOrder, ...],
    receipts: tuple[EgressReceiptObservation, ...],
    attempt_records: tuple[AttemptClassification, ...],
    outstanding_reservation_ids: frozenset[str] | None,
    matched_reservation_ids: frozenset[str],
    our_orders: tuple[WitnessOrder, ...] = (),
) -> bool:
    """Whether an orphan broker order could be an order THIS runtime emitted (2026-11-20)."""
    # SAFETY: 우리가 냈을 수 있거나 아직 살아 있는 고아 주문이면 거부를 유지한다 — 풀면 두 번째 물량을 산다 (#1128)
    if any(
        record.classification is not ReconciliationClass.MATCHED
        for record in attempt_records
    ):
        return True
    if outstanding_reservation_ids is None:
        return True
    if outstanding_reservation_ids - matched_reservation_ids:
        return True
    own_execution_ids = {
        execution_id
        for receipt in receipts
        if (execution_id := _execution_id(receipt.broker_execution_id)) is not None
    }
    return any(
        _execution_id(order.broker_execution_id) in own_execution_ids
        or not _placed_before_our_first_order(order, our_orders)
        or not _is_finished(order)
        for order in orphan_orders
        if not _settles_one_of_ours(order, our_orders)
    )


class ReconciliationService:
    """Assembles the three observation paths and calls the kernel ``tos.recon``"""

    def __init__(
        self,
        rcl_reader: ReservationProjectionReader,
        evidence_reader: EvidenceReceiptReader,
        witness: BrokerWitness,
        *,
        reservation_id_for_attempt: Callable[[str], str | None] | None = None,
    ) -> None:
        """Bind this service to its three injected observation ports."""
        self._rcl_reader = rcl_reader
        self._evidence_reader = evidence_reader
        self._witness = witness
        self._reservation_id_for_attempt = reservation_id_for_attempt

    def _reservation_id_for(self, attempt_id: str) -> str:
        """Resolve ``attempt_id`` onto the identity :attr:`_rcl_reader` is actually keyed by"""
        if self._reservation_id_for_attempt is None:
            return attempt_id
        resolved = self._reservation_id_for_attempt(attempt_id)
        return attempt_id if resolved is None else resolved

    def _outstanding_reservation_ids(
        self, scope: WitnessScope
    ) -> frozenset[str] | None:
        """Every non-``RELEASED`` reservation id ``scope`` holds, or ``None`` when unknowable."""
        if not scope.instrument_keys:
            return None
        reservation_ids: set[str] = set()
        for key in scope.instrument_keys:
            try:
                rows = self._rcl_reader.scope_reservations(key)
            except Exception:  # noqa: BLE001 - an unreadable RCL explains no orphan
                return None
            reservation_ids.update(
                row.reservation_id for row in outstanding_reservations(rows)
            )
        return frozenset(reservation_ids)

    def _orphans_withhold_release(
        self,
        scope: WitnessScope,
        *,
        orphan_orders: tuple[WitnessOrder, ...],
        receipts: tuple[EgressReceiptObservation, ...],
        attempt_records: tuple[AttemptClassification, ...],
        our_orders: tuple[WitnessOrder, ...],
    ) -> bool:
        """Whether ``orphan_orders`` withhold this scope's release (:func:`_orphans_may_be_ours`)."""
        matched_reservation_ids = frozenset(
            self._reservation_id_for(record.attempt_id)
            for record in attempt_records
            if record.attempt_id is not None
            and record.classification is ReconciliationClass.MATCHED
        )
        return _orphans_may_be_ours(
            orphan_orders=orphan_orders,
            receipts=receipts,
            attempt_records=attempt_records,
            outstanding_reservation_ids=self._outstanding_reservation_ids(scope),
            matched_reservation_ids=matched_reservation_ids,
            our_orders=our_orders,
        )

    def _attempt_field_confidences_and_gates(
        self,
        *,
        rcl_present: bool,
        evidence: EgressReceiptObservation | None,
        witness_order: WitnessOrder | None,
        freshness: FreshnessMarker,
        witness_independence_class: str,
        any_filled: bool = False,
    ) -> tuple[ReconciliationClass, tuple[FieldConfidence, ...], bool, bool, bool]:
        """One attempt's classification, field confidences, rearm-ok, capacity-ok, disagreed."""
        classification = _classify_attempt(
            rcl_present=rcl_present, evidence=evidence, witness_order=witness_order
        )

        existence_obs = _order_existence_observations(
            rcl_present=rcl_present,
            evidence=evidence,
            witness_order=witness_order,
            freshness=freshness,
            witness_independence_class=witness_independence_class,
        )
        existence_confidence = FieldConfidence(
            field=SafetyRelevantField.ORDER_EXISTENCE,
            confidence_class=classify_field(existence_obs, freshness),
            bound=ConservativeBound(),
            freshness_marker=freshness,
        )

        field_confidences = [existence_confidence]
        proof_ok_by_field: dict[SafetyRelevantField, bool] = {}
        asserts_zero = _asserts_zero_execution(evidence, any_filled=any_filled)
        # SAFETY: a non-execution has no separate final-quantity proof artifact and never
        # will — the producer only runs AFTER this gate — so its own zero is the proof.
        # The witness still has to agree at zero: a disagreeing path is CONFLICTED and
        # `capacity_ok` below stays False (#948).
        fqp_token = evidence is not None and (
            evidence.finality_proof_recorded or asserts_zero
        )
        proof_inputs = ReleaseProofInputs(
            final_quantity_proof_token=fqp_token, freshness=freshness
        )

        quantity_confidences, quantity_proof_ok, disagreed = _quantity_field_verdicts(
            evidence=evidence,
            witness_order=witness_order,
            freshness=freshness,
            witness_independence_class=witness_independence_class,
            proof_inputs=proof_inputs,
            asserts_zero_execution=asserts_zero,
        )
        field_confidences.extend(quantity_confidences)
        proof_ok_by_field.update(quantity_proof_ok)

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
        return (
            classification,
            tuple(field_confidences),
            rearm_ok,
            capacity_ok,
            disagreed,
        )

    def _reconcile_attempt(
        self,
        attempt_id: str,
        *,
        receipts_by_attempt: dict[str, EgressReceiptObservation],
        witness_by_attempt: dict[str, WitnessOrder],
        freshness: FreshnessMarker,
        witness_independence_class: str,
        filled_attempts: frozenset[str] = frozenset(),
    ) -> tuple[AttemptClassification, tuple[FieldConfidence, ...], bool, bool, bool]:
        """One known attempt id's full verdict — split out of :meth:`reconcile` to stay"""
        rcl_state = self._rcl_reader.reservation_state(
            self._reservation_id_for(attempt_id)
        )
        evidence = receipts_by_attempt.get(attempt_id)
        witness_order = witness_by_attempt.get(attempt_id)
        classification, confidences, rearm_ok, capacity_ok, disagreed = (
            self._attempt_field_confidences_and_gates(
                rcl_present=rcl_state is not None,
                evidence=evidence,
                witness_order=witness_order,
                any_filled=attempt_id in filled_attempts,
                freshness=freshness,
                witness_independence_class=witness_independence_class,
            )
        )
        record = AttemptClassification(
            attempt_id=attempt_id,
            classification=classification,
            broker_execution_id=(
                None if witness_order is None else witness_order.broker_execution_id
            ),
        )
        return record, confidences, rearm_ok, capacity_ok, disagreed

    @staticmethod
    def _classify_orphan_order(
        order: WitnessOrder,
        *,
        freshness: FreshnessMarker,
        witness_independence_class: str,
    ) -> tuple[AttemptClassification, FieldConfidence]:
        """One orphan broker order's verdict — split out of :meth:`reconcile`."""
        existence_obs = _order_existence_observations(
            rcl_present=False,
            evidence=None,
            witness_order=order,
            freshness=freshness,
            witness_independence_class=witness_independence_class,
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
        """Reconcile ``scope`` across RCL, evidence receipts, and the broker witness."""
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
        witness_by_attempt, orphan_orders = _join_orders_by_execution_id(
            snapshot, receipts, receipts_by_attempt
        )
        attempt_ids = (
            set(scope.attempt_ids) | set(receipts_by_attempt) | set(witness_by_attempt)
        )
        witness_independence_class = (
            _WITNESS_INDEPENDENCE_CLASS
            if snapshot.independent_of_evidence_store
            else _EVIDENCE_INDEPENDENCE_CLASS
        )

        classifications: list[AttemptClassification] = []
        field_confidences: list[FieldConfidence] = []
        rearm_flags: list[bool] = []
        capacity_flags: list[bool] = []
        disagreed = False
        filled_attempts = _attempts_with_a_filled_receipt(receipts)

        for attempt_id in sorted(attempt_ids):
            record, confidences, rearm_ok, capacity_ok, attempt_disagreed = (
                self._reconcile_attempt(
                    attempt_id,
                    receipts_by_attempt=receipts_by_attempt,
                    witness_by_attempt=witness_by_attempt,
                    freshness=freshness,
                    witness_independence_class=witness_independence_class,
                    filled_attempts=filled_attempts,
                )
            )
            classifications.append(record)
            field_confidences.extend(confidences)
            rearm_flags.append(rearm_ok)
            capacity_flags.append(capacity_ok)
            disagreed = disagreed or attempt_disagreed

        orphans_withhold = bool(orphan_orders) and self._orphans_withhold_release(
            scope,
            orphan_orders=orphan_orders,
            receipts=receipts,
            attempt_records=tuple(classifications),
            our_orders=tuple(witness_by_attempt.values()),
        )
        for order in orphan_orders:
            record, confidence = self._classify_orphan_order(
                order,
                freshness=freshness,
                witness_independence_class=witness_independence_class,
            )
            classifications.append(record)
            field_confidences.append(confidence)
            if orphans_withhold:
                rearm_flags.append(False)
                capacity_flags.append(False)

        reason = self._reason_for(
            capacity_flags=capacity_flags,
            rearm_flags=rearm_flags,
            witness_involved=bool(witness_by_attempt) or bool(orphan_orders),
            snapshot=snapshot,
            any_path_disagreed=disagreed,
        )
        return ReconciliationReport(
            field_confidences=tuple(field_confidences),
            classifications=tuple(classifications),
            permits_capacity_release=bool(capacity_flags) and all(capacity_flags),
            permits_rearm=bool(rearm_flags) and all(rearm_flags),
            reason=reason,
            observed_positions=snapshot.positions,
            observed_positions_complete=snapshot.positions_complete,
        )

    @staticmethod
    def _reason_for(
        *,
        capacity_flags: list[bool],
        rearm_flags: list[bool],
        witness_involved: bool,
        snapshot: WitnessSnapshot,
        any_path_disagreed: bool = False,
    ) -> str | None:
        """The report's own ``reason`` — split out of :meth:`reconcile` to stay under the"""
        if not rearm_flags:
            return "no observations in scope"
        fully_cleared = (bool(capacity_flags) and all(capacity_flags)) and (
            bool(rearm_flags) and all(rearm_flags)
        )
        if (
            not fully_cleared
            and witness_involved
            and not snapshot.independent_of_evidence_store
            and not any_path_disagreed
        ):
            return WITNESS_NOT_INDEPENDENT_REASON
        return None
