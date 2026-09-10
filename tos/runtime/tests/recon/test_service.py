"""``ReconciliationService`` tests (Phase 5 W1 — plan §2 decision 3).

Uses plain in-memory Protocol doubles for the RCL / evidence-receipt / broker-witness
ports — this service never touches a real sqlite file itself (pure judgement; see the
negative-grep test at the bottom).
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from tos.rcl import CapacityState
from tos.recon import FieldConfidenceClass, FreshnessMarker, SafetyRelevantField
from tos_runtime.recon import service as service_module
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
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService


class FakeRclReader:
    """A :class:`ReservationProjectionReader` test double."""

    def __init__(self, states: dict[str, CapacityState] | None = None) -> None:
        self._states = dict(states or {})

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        return self._states.get(reservation_id)

    def reservation_last_seq(self, _reservation_id: str) -> int | None:
        return None

    def all_reservations(self) -> dict[str, CapacityState]:
        return dict(self._states)

    def instrument_state(self, _key) -> CapacityState | None:
        return None

    def instrument_last_seq(self, _key) -> int | None:
        return None


class FakeEvidenceReader:
    """An :class:`EvidenceReceiptReader` test double."""

    def __init__(self, receipts: tuple[EgressReceiptObservation, ...] = ()) -> None:
        self._receipts = receipts

    def receipts(self, _scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        return self._receipts


class FakeWitness:
    """A :class:`BrokerWitness` test double — either a fixed snapshot or unavailable."""

    def __init__(
        self, snapshot: WitnessSnapshot | None = None, *, unavailable: bool = False
    ) -> None:
        self._snapshot = snapshot or WitnessSnapshot(
            observed_at_generation=1, orders=(), provenance="fake"
        )
        self._unavailable = unavailable

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        if self._unavailable:
            raise WitnessUnavailable("test double: witness unavailable")
        return self._snapshot


@pytest.fixture
def fresh() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def _matched_receipt(**overrides) -> EgressReceiptObservation:
    fields = {
        "attempt_id": "a1",
        "account": "acct-1",
        "instrument": "005930",
        "egress_result_kind": "FULL_FILL",
        "broker_execution_id": "exec-1",
        "filled_quantity": Decimal("10"),
        "remaining_quantity": Decimal("0"),
        "finality_proof_recorded": True,
        "source_ref": "evidence:1",
    }
    fields.update(overrides)
    return EgressReceiptObservation(**fields)


def _matched_witness_order(**overrides) -> WitnessOrder:
    fields = {
        "attempt_id": "a1",
        "broker_execution_id": "exec-1",
        "quantity": Decimal("10"),
        "remaining": Decimal("0"),
        "state": WitnessOrderState.FILLED,
    }
    fields.update(overrides)
    return WitnessOrder(**fields)


# ============================================================================
# Protocol conformance
# ============================================================================


def test_fake_rcl_reader_satisfies_protocol() -> None:
    assert isinstance(FakeRclReader(), ReservationProjectionReader)


def test_fake_evidence_reader_satisfies_protocol() -> None:
    assert isinstance(FakeEvidenceReader(), EvidenceReceiptReader)


def test_fake_witness_satisfies_protocol() -> None:
    assert isinstance(FakeWitness(), BrokerWitness)


# ============================================================================
# Matched set — the happy path
# ============================================================================


def test_matched_set_yields_positive_confidence_and_both_permits_true(fresh) -> None:
    """Independent-review finding F2: full corroboration requires a witness that is genuinely
    independent of the evidence-receipt path — ``independent_of_evidence_store=True`` here
    stands in for a real (non-store-derived) broker witness; see
    ``test_synthetic_witness_never_permits_capacity_release`` below for the OTHER half (a
    store-derived witness, ``SyntheticLedgerWitness``'s own shape, can never fully clear).
    """
    rcl = FakeRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = FakeEvidenceReader((_matched_receipt(),))
    witness = FakeWitness(
        WitnessSnapshot(
            observed_at_generation=1,
            orders=(_matched_witness_order(),),
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=("a1",)), freshness=fresh
    )

    assert report.permits_rearm is True
    assert report.permits_capacity_release is True
    assert report.classifications == (
        service_module.AttemptClassification(
            attempt_id="a1",
            classification=ReconciliationClass.MATCHED,
            broker_execution_id="exec-1",
        ),
    )
    assert any(
        fc.confidence_class is FieldConfidenceClass.CORROBORATED
        for fc in report.field_confidences
    )
    assert report.reason is None


def test_synthetic_witness_never_permits_capacity_release(fresh) -> None:
    """Independent-review finding F2 (HIGH): the SAME MATCHED setup as the test above, but the
    witness declares itself store-derived (``independent_of_evidence_store=False``, the
    ``SyntheticLedgerWitness`` shape) — the quantity fields' witness observation is stamped
    with the SAME independence class as the evidence-receipt path, so they can never reach
    ``CORROBORATED`` (only two byte-identical-source observations, never sufficiently
    independent), and ``permits_capacity_release`` is permanently ``False``. A mutation that
    unconditionally stamped the witness path with ``BROKER_WITNESS`` regardless of
    ``independent_of_evidence_store`` would turn this red."""
    rcl = FakeRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = FakeEvidenceReader((_matched_receipt(),))
    witness = FakeWitness(
        WitnessSnapshot(
            observed_at_generation=1,
            orders=(_matched_witness_order(),),
            provenance="synthetic-ledger",
            independent_of_evidence_store=False,
        )
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=("a1",)), freshness=fresh
    )

    assert report.permits_capacity_release is False
    assert report.reason == service_module.WITNESS_NOT_INDEPENDENT_REASON
    assert not any(
        fc.confidence_class is FieldConfidenceClass.CORROBORATED
        and fc.field
        in (
            SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
            SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY,
        )
        for fc in report.field_confidences
    )


# ============================================================================
# One stale reservation (RCL-only)
# ============================================================================


def test_stale_reservation_yields_both_permits_false_and_is_classified(fresh) -> None:
    rcl = FakeRclReader({"a1": CapacityState.COMMITTED_UNBOUND})
    evidence = FakeEvidenceReader(())
    witness = FakeWitness(
        WitnessSnapshot(observed_at_generation=1, orders=(), provenance="x")
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=("a1",)), freshness=fresh
    )

    assert report.permits_rearm is False
    assert report.permits_capacity_release is False
    assert len(report.classifications) == 1
    assert (
        report.classifications[0].classification
        is ReconciliationClass.STALE_RESERVATION
    )


# ============================================================================
# One orphan broker order (witness-only)
# ============================================================================


def test_orphan_broker_order_yields_both_permits_false_and_is_classified(fresh) -> None:
    rcl = FakeRclReader({})
    evidence = FakeEvidenceReader(())
    orphan = WitnessOrder(
        attempt_id=None,
        broker_execution_id="exec-orphan",
        quantity=Decimal("3"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
    )
    witness = FakeWitness(
        WitnessSnapshot(observed_at_generation=1, orders=(orphan,), provenance="x")
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(WitnessScope(account="acct-1"), freshness=fresh)

    assert report.permits_rearm is False
    assert report.permits_capacity_release is False
    assert len(report.classifications) == 1
    classification = report.classifications[0]
    assert classification.classification is ReconciliationClass.ORPHAN_BROKER_ORDER
    assert classification.broker_execution_id == "exec-orphan"
    assert classification.attempt_id is None


# ============================================================================
# Receipt-only (evidence-only)
# ============================================================================


def test_receipt_only_is_classified_and_does_not_permit(fresh) -> None:
    rcl = FakeRclReader({})
    evidence = FakeEvidenceReader((_matched_receipt(),))
    witness = FakeWitness(
        WitnessSnapshot(observed_at_generation=1, orders=(), provenance="x")
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=("a1",)), freshness=fresh
    )

    assert report.permits_rearm is False
    assert report.permits_capacity_release is False
    assert report.classifications[0].classification is ReconciliationClass.RECEIPT_ONLY


# ============================================================================
# Witness unavailable
# ============================================================================


def test_witness_unavailable_yields_both_permits_false_with_reason(fresh) -> None:
    rcl = FakeRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = FakeEvidenceReader((_matched_receipt(),))
    witness = FakeWitness(unavailable=True)
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=("a1",)), freshness=fresh
    )

    assert report.permits_rearm is False
    assert report.permits_capacity_release is False
    assert report.classifications == ()
    assert report.field_confidences == ()
    assert report.reason is not None
    assert "unavailable" in report.reason


# ============================================================================
# Empty everything — vacuous truth forbidden
# ============================================================================


def test_empty_scope_is_not_positive(fresh) -> None:
    rcl = FakeRclReader({})
    evidence = FakeEvidenceReader(())
    witness = FakeWitness(
        WitnessSnapshot(observed_at_generation=1, orders=(), provenance="x")
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(WitnessScope(account="acct-1"), freshness=fresh)

    assert report.permits_rearm is False
    assert report.permits_capacity_release is False
    assert report.field_confidences == ()
    assert report.classifications == ()
    assert report.reason == "no observations in scope"


# ============================================================================
# Conflicting quantities (even when all three paths report the attempt)
# ============================================================================


def test_matched_attempt_with_conflicting_quantities_does_not_permit(fresh) -> None:
    rcl = FakeRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = FakeEvidenceReader(
        (
            _matched_receipt(
                filled_quantity=Decimal("10"), remaining_quantity=Decimal("0")
            ),
        )
    )
    witness = FakeWitness(
        WitnessSnapshot(
            observed_at_generation=1,
            orders=(
                _matched_witness_order(quantity=Decimal("5"), remaining=Decimal("5")),
            ),
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )
    )
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=("a1",)), freshness=fresh
    )

    assert report.permits_rearm is False
    assert report.permits_capacity_release is False
    assert any(
        fc.confidence_class is FieldConfidenceClass.CONFLICTED
        for fc in report.field_confidences
    )


# ============================================================================
# Negative greps — pure judgement, mutates nothing
# ============================================================================


def test_service_module_imports_no_writer_apis_or_ambient_state() -> None:
    """Negative-grep: pure judgement, mutates nothing.

    ``list.append`` (building an in-memory report) is fine; only durable-writer calls
    and ambient env/clock reads are forbidden.
    """
    source = inspect.getsource(service_module)
    for forbidden in (
        "import os",
        "time.time(",
        "append_cas(",
        "apply_reservation_transition(",
        "store.append(",
        "SqliteEvidenceStore",
        "SqliteCommitLog",
    ):
        assert forbidden not in source, f"service.py must not reference {forbidden!r}"
