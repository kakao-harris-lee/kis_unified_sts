"""The venue ledger through the REAL ``ReconciliationService`` (plan 2026-10-31 §5 ③)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tos.rcl import CapacityState
from tos.recon import FieldConfidenceClass, FreshnessMarker, SafetyRelevantField
from tos.recon.vocabulary import CAPACITY_RELEASING_FIELDS
from tos_runtime.recon.ports import EgressReceiptObservation, WitnessScope
from tos_runtime.recon.service import (
    WITNESS_NOT_INDEPENDENT_REASON,
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness
from tos_runtime.recon.witness_synthetic_venue import SyntheticVenueLedgerWitness
from tos_runtime.venue_ledger.synthetic import SyntheticVenueLedger, VenueLedgerReader

from .test_service import FakeEvidenceReader, FakeRclReader

TODAY = "20261031"
BUY = "BUY"
SELL = "SELL"
ACCOUNT = "acct-1"
INSTRUMENT = "101W12"
ATTEMPT = "a1"
EXECUTION_ID = f"syn-exec:{ATTEMPT}:FULL_FILL"


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "venue_ledger.sqlite3"


@pytest.fixture
def ledger(ledger_path: Path):
    instance = SyntheticVenueLedger(ledger_path)
    yield instance
    instance.close()


def _record_entry_fill(ledger: SyntheticVenueLedger, *, filled: str = "1") -> None:
    ledger.record(
        attempt_id=ATTEMPT,
        broker_execution_id=EXECUTION_ID,
        account=ACCOUNT,
        instrument=INSTRUMENT,
        side=BUY,
        quantity=Decimal(filled),
        filled_quantity=Decimal(filled),
        remaining_quantity=Decimal("0"),
        result_kind="FULL_FILL",
        trading_date=TODAY,
    )


def _receipt(filled: str = "1") -> EgressReceiptObservation:
    return EgressReceiptObservation(
        attempt_id=ATTEMPT,
        account=ACCOUNT,
        instrument=INSTRUMENT,
        egress_result_kind="FULL_FILL",
        broker_execution_id=EXECUTION_ID,
        filled_quantity=Decimal(filled),
        remaining_quantity=Decimal("0"),
        finality_proof_recorded=True,
        source_ref="evidence:1",
        trading_date=TODAY,
    )


def _venue_witness(path: Path) -> SyntheticVenueLedgerWitness:
    return SyntheticVenueLedgerWitness(
        VenueLedgerReader(path),
        buy_side_token=BUY,
        sell_side_token=SELL,
        trading_date_now=lambda: TODAY,
    )


def _service(
    path: Path,
    *,
    receipts: tuple[EgressReceiptObservation, ...],
    rcl: dict[str, CapacityState] | None = None,
) -> ReconciliationService:
    return ReconciliationService(
        FakeRclReader(rcl or {}), FakeEvidenceReader(receipts), _venue_witness(path)
    )


def _scope() -> WitnessScope:
    return WitnessScope(account=ACCOUNT, attempt_ids=(ATTEMPT,), as_of_generation=1)


def _confidence(
    report: ReconciliationReport, field: SafetyRelevantField
) -> FieldConfidenceClass:
    (confidence,) = [c for c in report.field_confidences if c.field is field]
    assert confidence.confidence_class is not None
    return confidence.confidence_class


def test_a_ledger_fill_matching_the_evidence_releases_capacity(
    ledger, ledger_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """This is the verdict #1011 reports as structurally unreachable today (§1 F3/F4): the"""
    _record_entry_fill(ledger)
    report = _service(
        ledger_path,
        receipts=(_receipt(),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
    ).reconcile(_scope(), freshness=fresh_marker)

    assert [c.classification for c in report.classifications] == [
        ReconciliationClass.MATCHED
    ]
    assert report.permits_capacity_release is True
    assert report.permits_rearm is True
    assert report.reason is None
    for field in CAPACITY_RELEASING_FIELDS:
        assert _confidence(report, field) is FieldConfidenceClass.CORROBORATED
    assert _confidence(report, SafetyRelevantField.ORDER_EXISTENCE) is (
        FieldConfidenceClass.CORROBORATED
    )
    assert report.observed_positions == (("101W12", Decimal("1")),)
    assert report.observed_positions_complete is True


def test_the_store_derived_witness_on_the_same_facts_still_cannot_release(
    ledger, ledger_path: Path, store, fresh_marker: FreshnessMarker
) -> None:
    """The control: identical RCL and receipt facts, the OLD witness over an evidence store with"""
    _record_entry_fill(ledger)
    report = ReconciliationService(
        FakeRclReader({ATTEMPT: CapacityState.POSITION_CONSUMED}),
        FakeEvidenceReader((_receipt(),)),
        SyntheticLedgerWitness(store),
    ).reconcile(_scope(), freshness=fresh_marker)

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False


def test_release_still_requires_the_final_quantity_proof(
    ledger, ledger_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """Independence is not a bypass: an independent witness with no recorded Final Quantity"""
    _record_entry_fill(ledger)
    report = _service(
        ledger_path,
        receipts=(
            EgressReceiptObservation(
                **{**_receipt().__dict__, "finality_proof_recorded": False}
            ),
        ),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
    ).reconcile(_scope(), freshness=fresh_marker)

    assert [c.classification for c in report.classifications] == [
        ReconciliationClass.MATCHED
    ]
    assert report.permits_capacity_release is False


def test_release_still_requires_freshness(ledger, ledger_path: Path) -> None:
    """The default all-``None`` marker fails closed — recon is clock-free by design."""
    _record_entry_fill(ledger)
    report = _service(
        ledger_path,
        receipts=(_receipt(),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
    ).reconcile(_scope())
    assert report.permits_capacity_release is False


def test_a_ledger_fill_with_no_evidence_is_an_orphan_and_releases_nothing(
    ledger, ledger_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """§3.4 case 1: the process died between the venue write and the evidence record. The"""
    _record_entry_fill(ledger)
    report = _service(ledger_path, receipts=()).reconcile(
        _scope(), freshness=fresh_marker
    )

    assert [c.classification for c in report.classifications] == [
        ReconciliationClass.ORPHAN_BROKER_ORDER
    ]
    assert report.permits_capacity_release is False
    assert report.permits_rearm is False
    assert report.reason != WITNESS_NOT_INDEPENDENT_REASON, (
        "the independent witness must not be reported as the reason — that is the §3.5 "
        "distinction P2 carries into the HELD reason"
    )


def test_an_empty_ledger_releases_nothing(
    ledger, ledger_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """§3.4 case 3: evidence says a fill happened, the venue has no record of it (the wrapper"""
    report = _service(
        ledger_path,
        receipts=(_receipt(),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
    ).reconcile(_scope(), freshness=fresh_marker)

    assert [c.classification for c in report.classifications] == [
        ReconciliationClass.STALE_RESERVATION
    ]
    assert report.permits_capacity_release is False


def test_a_quantity_disagreement_conflicts_and_releases_nothing(
    ledger, ledger_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """§3.4 case 2: the driver re-injected a result whose magnitude is not what the venue"""
    _record_entry_fill(ledger, filled="1")
    report = _service(
        ledger_path,
        receipts=(_receipt(filled="2"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
    ).reconcile(_scope(), freshness=fresh_marker)

    assert [c.classification for c in report.classifications] == [
        ReconciliationClass.MATCHED
    ]
    assert (
        _confidence(report, SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY)
        is FieldConfidenceClass.CONFLICTED
    )
    assert report.permits_capacity_release is False
    assert report.permits_rearm is False


def test_a_ledger_row_the_witness_cannot_read_holds_everything(
    ledger, ledger_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """``WitnessUnavailable`` takes the service's own fail-closed branch: no classifications,"""
    _record_entry_fill(ledger)
    ledger.close()
    ledger_path.write_bytes(b"corrupt")
    report = _service(
        ledger_path,
        receipts=(_receipt(),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
    ).reconcile(_scope(), freshness=fresh_marker)

    assert report.classifications == ()
    assert report.permits_capacity_release is False
    assert report.permits_rearm is False
    assert report.reason is not None
    assert "witness unavailable" in report.reason
