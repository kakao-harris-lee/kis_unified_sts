"""`witness_independence_collapsed` against the REAL ``ReconciliationService`` (review-1018 M1).

**What M1 found.** :meth:`~tos_runtime.recon.service.ReconciliationService._reason_for` stamps
``WITNESS_NOT_INDEPENDENT`` on any uncleared report whose witness declared itself store-derived,
and it decides that BEFORE looking at orphans or conflicted fields. So the reason alone means
"store-derived and not cleared". Mapping it straight onto the softer hold reason recorded a
GENUINE disagreement as an independence hold, which the POST_TRADE currentness dimension then
reads as conflict-free — the opposite of plan §5 ④'s "진짜 충돌 → False 유지". Measured at the
service level: a store-derived witness reporting qty 5 / rem 5 against a receipt of 10 / 0.

**Why these tests drive the service.** ``test_witness_not_independent_reason.py`` pins the
mapping and the dimension from hold rows written directly, so nothing there ever reaches the
predicate with a report the service actually built. Every case below runs a real
:class:`~tos_runtime.recon.service.ReconciliationService` and asks
:func:`~tos_runtime.posttrade.release_hold.uncorroborated_hold_reason` what the release path
would record.

(b) and (c) use a witness DOUBLE declaring ``independent_of_evidence_store=False`` with rows
that diverge from the receipts. That is deliberate, and it is the finding: the only shipped
store-derived witness
(:class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`) reads the same evidence
rows as the receipt path and so CANNOT diverge from it. The guarantee has to live in the code
rather than in how that one class happens to be built.

Hermetic: ``tmp_path`` sqlite only, no network, no ambient env (D1.4).
"""

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
    """A witness declaring itself store-derived, with rows the caller chooses.

    ``independent_of_evidence_store=False`` is the ONE field
    :meth:`ReconciliationService._reason_for` keys the independence collapse on, so this
    double reaches exactly the branch under test.
    """
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


# ===========================================================================
# (a) store-derived, clean — the independence collapse IS the only failure
# ===========================================================================


def test_a_clean_store_derived_report_is_an_independence_hold(
    store: SqliteEvidenceStore, fresh_marker: FreshnessMarker
) -> None:
    """The REAL ``SyntheticLedgerWitness`` on facts that agree: hold ``WITNESS_NOT_INDEPENDENT``.

    Concrete input: one ``EGRESS_RESULT_CONSUMED`` row of 10/0, the matching receipt, and an
    open RCL reservation. Concrete result: MATCHED, no conflicted field, the report names the
    independence collapse, no capacity released — and the release path records the softer
    reason, so the POST_TRADE dimension does not report a conflict this scope never had.
    """
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


# ===========================================================================
# (b) store-derived + a quantity conflict — a conflict, not an independence hold
# ===========================================================================


def test_a_store_derived_report_with_a_quantity_conflict_is_a_conflict(
    fresh_marker: FreshnessMarker,
) -> None:
    """M1's own failing input, at the service level.

    Concrete input: a store-derived witness order of 5 filled / 5 remaining against a receipt
    of 10 / 0. Concrete result BEFORE the fix: ``report.reason == WITNESS_NOT_INDEPENDENT``,
    hold ``WITNESS_NOT_INDEPENDENT``, POST_TRADE ``True`` — a real disagreement reported as
    conflict-free. Now the report carries NO reason at all, which every caller already maps to
    "not corroborated".

    Note which check catches it, because it is not the obvious one: with a store-derived
    witness BOTH paths carry the same independence class, so ``classify_field`` degrades the
    disagreement to ``SINGLE_SOURCE`` and the fields are NOT ``CONFLICTED`` (asserted below —
    that is the measurement that made the field scan alone insufficient). What catches it is
    ``_reason_for``'s new ``any_path_disagreed``, fed from the observations'
    ``agrees_within_tolerance``.
    """
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
    # The measurement behind the fix: a store-derived disagreement is NOT conflicted.
    assert not any(
        confidence.confidence_class is FieldConfidenceClass.CONFLICTED
        for confidence in report.field_confidences
    )
    assert report.permits_capacity_release is False

    assert witness_independence_collapsed(report) is False
    assert uncorroborated_hold_reason(report) is ReleaseHoldReason.NOT_CORROBORATED


# ===========================================================================
# (c) store-derived + an orphan order — also a conflict
# ===========================================================================


def test_a_store_derived_report_with_an_orphan_order_is_a_conflict(
    fresh_marker: FreshnessMarker,
) -> None:
    """An order nothing accounts for is the §3.4 crash-before-evidence catch — never "softer".

    Concrete input: the matched attempt PLUS a second witness order for an attempt with no RCL
    reservation and no receipt. Nothing DISAGREES here — no magnitude contradicts another — so
    the report still names the independence collapse; what catches the orphan is the
    predicate's own "every classification MATCHED" condition. The two conditions cover
    different shapes, which is why both exist.
    """
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


# ===========================================================================
# (d) the independent venue witness + a conflict — unchanged, still a conflict
# ===========================================================================


def test_the_venue_witness_with_a_conflict_is_a_conflict(
    tmp_path: Path, fresh_marker: FreshnessMarker
) -> None:
    """The key-ON control: an independent witness never reaches the independence reason at all.

    Concrete input: a REAL venue ledger holding a 5-contract fill against a receipt of 10.
    Concrete result: ``reason`` is ``None`` (nothing collapsed — the witness IS independent),
    the field conflicts, and the release path records ``NOT_CORROBORATED``. That is the
    behaviour plan §5 ④ asks to keep, and it is unchanged by M1.
    """
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


# ===========================================================================
# the narrowing itself, stated as a table
# ===========================================================================


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
    """The boundary in one table: an attempt the witness does not report at all is
    ``STALE_RESERVATION``, not MATCHED, so it is a conflict too — the one-sided shapes are
    narrowed away alongside the orphan, because "the witness is merely not independent" is a
    claim about a report where everything else lined up.
    """
    report = _report(
        _store_derived_double(orders),
        receipts=(_receipt("10"),),
        rcl={ATTEMPT: CapacityState.POSITION_CONSUMED},
        fresh_marker=fresh_marker,
    )
    assert uncorroborated_hold_reason(report) is expected
