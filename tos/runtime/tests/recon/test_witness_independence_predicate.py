"""`witness_independence_collapsed` against the REAL ``ReconciliationService`` (review-1018 M1)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tos.rcl import CapacityState
from tos.recon import FieldConfidenceClass, FreshnessMarker
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.release_hold import (
    ReleaseHoldReason,
    uncorroborated_hold_reason,
)
from tos_runtime.recon.ports import (
    EgressReceiptObservation,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.recon.service import (
    WITNESS_NOT_INDEPENDENT_REASON,
    ReconciliationClass,
    ReconciliationService,
    witness_independence_collapsed,
)
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness
from tos_runtime.recon.witness_synthetic_venue import SyntheticVenueLedgerWitness
from tos_runtime.venue_ledger.synthetic import SyntheticVenueLedger, VenueLedgerReader

from .test_service import FakeEvidenceReader, FakeRclReader, FakeWitness

ACCOUNT = "acct-1"
INSTRUMENT = "101W12"
ATTEMPT = "a1"
ORPHAN_ATTEMPT = "a-orphan"
EXECUTION_ID = f"syn-exec:{ATTEMPT}:FULL_FILL"
TODAY = "20261031"
BUY = "BUY"
SELL = "SELL"


def _receipt(filled: str = "10") -> EgressReceiptObservation:
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


def _store_derived_double(orders: tuple[WitnessOrder, ...]) -> FakeWitness:
    """A witness declaring itself store-derived, with rows the caller chooses."""
    return FakeWitness(
        WitnessSnapshot(
            observed_at_generation=1,
            orders=orders,
            positions=(),
            positions_complete=False,
            provenance="test-store-derived",
            independent_of_evidence_store=False,
            order_inquiry_date=TODAY,
        )
    )


def _report(witness, *, receipts, rcl, fresh_marker: FreshnessMarker):
    return ReconciliationService(
        FakeRclReader(rcl), FakeEvidenceReader(receipts), witness
    ).reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=(ATTEMPT,), as_of_generation=1),
        freshness=fresh_marker,
    )


def _append_consumed_result(
    store: SqliteEvidenceStore, *, filled: str, remaining: str
) -> None:
    """The durable row the REAL store-derived witness reconstructs its order from."""
    store.append(
        {
            "attempt_id": ATTEMPT,
            "instrument_key": {"account": ACCOUNT, "instrument": INSTRUMENT},
            "egress_result_kind": "FULL_FILL",
            "broker_execution_id": EXECUTION_ID,
            "filled_quantity": filled,
            "remaining_quantity": remaining,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )


def test_a_clean_store_derived_report_is_an_independence_hold(
    store: SqliteEvidenceStore, fresh_marker: FreshnessMarker
) -> None:
    """The REAL ``SyntheticLedgerWitness`` on facts that agree: hold ``WITNESS_NOT_INDEPENDENT``."""
    _append_consumed_result(store, filled="10", remaining="0")

    report = _report(
        SyntheticLedgerWitness(store),
        receipts=(_receipt("10"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
        fresh_marker=fresh_marker,
    )

    assert [item.classification for item in report.classifications] == [
        ReconciliationClass.MATCHED
    ]
    assert not any(
        confidence.confidence_class is FieldConfidenceClass.CONFLICTED
        for confidence in report.field_confidences
    )
    assert report.reason == WITNESS_NOT_INDEPENDENT_REASON
    assert report.permits_capacity_release is False

    assert witness_independence_collapsed(report) is True
    assert uncorroborated_hold_reason(report) is (
        ReleaseHoldReason.WITNESS_NOT_INDEPENDENT
    )


def test_a_store_derived_report_with_a_quantity_conflict_is_a_conflict(
    fresh_marker: FreshnessMarker,
) -> None:
    """M1's own failing input, at the service level."""
    conflicting = WitnessOrder(
        attempt_id=ATTEMPT,
        broker_execution_id=EXECUTION_ID,
        quantity=Decimal("5"),
        remaining=Decimal("5"),
        state=WitnessOrderState.PARTIAL,
        order_date=TODAY,
    )

    report = _report(
        _store_derived_double((conflicting,)),
        receipts=(_receipt("10"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
        fresh_marker=fresh_marker,
    )

    assert report.reason is None
    assert not any(
        confidence.confidence_class is FieldConfidenceClass.CONFLICTED
        for confidence in report.field_confidences
    )
    assert report.permits_capacity_release is False

    assert witness_independence_collapsed(report) is False
    assert uncorroborated_hold_reason(report) is ReleaseHoldReason.NOT_CORROBORATED


def test_a_store_derived_report_with_an_orphan_order_is_a_conflict(
    fresh_marker: FreshnessMarker,
) -> None:
    """An order nothing accounts for is the §3.4 crash-before-evidence catch — never "softer"."""
    matched = WitnessOrder(
        attempt_id=ATTEMPT,
        broker_execution_id=EXECUTION_ID,
        quantity=Decimal("10"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
        order_date=TODAY,
    )
    orphan = WitnessOrder(
        attempt_id=ORPHAN_ATTEMPT,
        broker_execution_id=f"syn-exec:{ORPHAN_ATTEMPT}:FULL_FILL",
        quantity=Decimal("10"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
        order_date=TODAY,
    )

    report = _report(
        _store_derived_double((matched, orphan)),
        receipts=(_receipt("10"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
        fresh_marker=fresh_marker,
    )

    assert report.reason == WITNESS_NOT_INDEPENDENT_REASON
    assert ReconciliationClass.ORPHAN_BROKER_ORDER in [
        item.classification for item in report.classifications
    ]

    assert witness_independence_collapsed(report) is False
    assert uncorroborated_hold_reason(report) is ReleaseHoldReason.NOT_CORROBORATED


def test_the_venue_witness_with_a_conflict_is_a_conflict(
    tmp_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """The key-ON control: an independent witness never reaches the independence reason at all."""
    path = tmp_path / "venue_ledger.sqlite3"
    ledger = SyntheticVenueLedger(path)
    try:
        ledger.record(
            attempt_id=ATTEMPT,
            broker_execution_id=EXECUTION_ID,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            side=BUY,
            quantity=Decimal("5"),
            filled_quantity=Decimal("5"),
            remaining_quantity=Decimal("5"),
            result_kind="PARTIAL_FILL",
            trading_date=TODAY,
        )
    finally:
        ledger.close()

    report = _report(
        SyntheticVenueLedgerWitness(
            VenueLedgerReader(path),
            buy_side_token=BUY,
            sell_side_token=SELL,
            trading_date_now=lambda: TODAY,
        ),
        receipts=(_receipt("10"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
        fresh_marker=fresh_marker,
    )

    assert report.reason is None
    assert any(
        confidence.confidence_class is FieldConfidenceClass.CONFLICTED
        for confidence in report.field_confidences
    )

    assert witness_independence_collapsed(report) is False
    assert uncorroborated_hold_reason(report) is ReleaseHoldReason.NOT_CORROBORATED


@pytest.mark.parametrize(
    ("orders", "expected"),
    [
        pytest.param((), ReleaseHoldReason.NOT_CORROBORATED, id="no-witness-order"),
        pytest.param(
            (
                WitnessOrder(
                    attempt_id=ATTEMPT,
                    broker_execution_id=EXECUTION_ID,
                    quantity=Decimal("10"),
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                    order_date=TODAY,
                ),
            ),
            ReleaseHoldReason.WITNESS_NOT_INDEPENDENT,
            id="agreeing-order",
        ),
    ],
)
def test_only_an_all_matched_conflict_free_report_earns_the_softer_reason(
    orders: tuple[WitnessOrder, ...],
    expected: ReleaseHoldReason,
    fresh_marker: FreshnessMarker,
) -> None:
    """The boundary in one table: an attempt the witness does not report at all is"""
    report = _report(
        _store_derived_double(orders),
        receipts=(_receipt("10"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
        fresh_marker=fresh_marker,
    )
    assert uncorroborated_hold_reason(report) is expected
