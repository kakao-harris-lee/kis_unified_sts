"""``broker_execution_id`` cross-reference in ``ReconciliationService`` (carryover plan W-C C-1).

A real broker witness returns orders with ``attempt_id=None``. These tests pin that such an order
joins its attempt only through an unambiguous one-to-one broker-id match against the evidence
receipts, and that every ambiguous or unmatched case stays an orphan (fail-closed).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.rcl import CapacityState
from tos.recon import FreshnessMarker
from tos_runtime.recon.ports import (
    EgressReceiptObservation,
    WitnessOrder,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.recon.service import (
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)

from .test_service import (
    FakeEvidenceReader,
    FakeRclReader,
    FakeWitness,
    _matched_receipt,
    _matched_witness_order,
)


@pytest.fixture
def fresh() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def _reconcile(
    fresh: FreshnessMarker,
    *,
    receipts: tuple[EgressReceiptObservation, ...],
    orders: tuple[WitnessOrder, ...],
    rcl: dict[str, CapacityState] | None = None,
    attempt_ids: tuple[str, ...] = ("a1",),
) -> ReconciliationReport:
    service = ReconciliationService(
        FakeRclReader(
            rcl if rcl is not None else {"a1": CapacityState.POSITION_CONSUMED}
        ),
        FakeEvidenceReader(receipts),
        FakeWitness(
            WitnessSnapshot(
                observed_at_generation=1,
                orders=orders,
                provenance="independent-broker-double",
                independent_of_evidence_store=True,
            )
        ),
    )
    return service.reconcile(
        WitnessScope(account="acct-1", attempt_ids=attempt_ids), freshness=fresh
    )


def _classes(
    report: ReconciliationReport,
) -> list[tuple[str | None, ReconciliationClass]]:
    return [(c.attempt_id, c.classification) for c in report.classifications]


def test_attemptless_order_joins_through_its_broker_id(fresh: FreshnessMarker) -> None:
    """The KIS shape: the witness knows only the ODNO. It now joins the attempt whose receipt
    recorded that ODNO — MATCHED, no duplicate orphan, and the permits follow the kernel.
    """
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(),),
        orders=(_matched_witness_order(attempt_id=None),),
    )
    assert _classes(report) == [("a1", ReconciliationClass.MATCHED)]
    assert report.classifications[0].broker_execution_id == "exec-1"
    assert report.permits_rearm is True
    assert report.permits_capacity_release is True


def test_joined_order_with_conflicting_quantity_still_does_not_permit(
    fresh: FreshnessMarker,
) -> None:
    """Joining grants nothing by itself — a quantity disagreement between the receipt and the
    joined order is still the kernel's conflict."""
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(),),
        orders=(_matched_witness_order(attempt_id=None, quantity=Decimal("7")),),
    )
    assert _classes(report) == [("a1", ReconciliationClass.MATCHED)]
    assert report.permits_rearm is False
    assert report.permits_capacity_release is False


@pytest.mark.parametrize(
    "order_id",
    [None, "", "exec-other", "0exec-1"],
    ids=["no-id", "empty-id", "unknown-id", "different-spelling"],
)
def test_unmatched_broker_id_stays_an_orphan(
    fresh: FreshnessMarker, order_id: str | None
) -> None:
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(),),
        orders=(_matched_witness_order(attempt_id=None, broker_execution_id=order_id),),
    )
    assert _classes(report) == [
        ("a1", ReconciliationClass.STALE_RESERVATION),
        (None, ReconciliationClass.ORPHAN_BROKER_ORDER),
    ]
    assert report.permits_rearm is False
    assert report.permits_capacity_release is False


def test_surrounding_whitespace_is_not_an_identity_difference(
    fresh: FreshnessMarker,
) -> None:
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(broker_execution_id=" exec-1 "),),
        orders=(_matched_witness_order(attempt_id=None),),
    )
    assert _classes(report) == [("a1", ReconciliationClass.MATCHED)]


def test_broker_id_recorded_under_two_attempts_is_ambiguous(
    fresh: FreshnessMarker,
) -> None:
    """E.g. an ODNO reused on another trading day: the id cannot say which attempt it is."""
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(), _matched_receipt(attempt_id="a2")),
        orders=(_matched_witness_order(attempt_id=None),),
        rcl={
            "a1": CapacityState.POSITION_CONSUMED,
            "a2": CapacityState.POSITION_CONSUMED,
        },
        attempt_ids=("a1", "a2"),
    )
    assert (None, ReconciliationClass.ORPHAN_BROKER_ORDER) in _classes(report)
    assert all(
        cls is not ReconciliationClass.MATCHED for _attempt, cls in _classes(report)
    )
    assert report.permits_rearm is False


def test_two_orders_resolving_to_one_attempt_both_stay_orphans(
    fresh: FreshnessMarker,
) -> None:
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(),),
        orders=(
            _matched_witness_order(attempt_id=None),
            _matched_witness_order(attempt_id=None),
        ),
    )
    assert _classes(report) == [
        ("a1", ReconciliationClass.STALE_RESERVATION),
        (None, ReconciliationClass.ORPHAN_BROKER_ORDER),
        (None, ReconciliationClass.ORPHAN_BROKER_ORDER),
    ]
    assert report.permits_rearm is False


def test_direct_attempt_match_is_not_displaced_by_a_cross_referenced_one(
    fresh: FreshnessMarker,
) -> None:
    """An attempt that already has its own order keeps it; a second, id-matched order for the
    same attempt is a disagreement and stays an orphan — never silently merged."""
    direct = _matched_witness_order()
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(),),
        orders=(direct, _matched_witness_order(attempt_id=None)),
    )
    assert _classes(report) == [
        ("a1", ReconciliationClass.MATCHED),
        (None, ReconciliationClass.ORPHAN_BROKER_ORDER),
    ]
    assert report.permits_rearm is False


def test_receipt_without_attempt_contributes_no_join_key(
    fresh: FreshnessMarker,
) -> None:
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(attempt_id=None),),
        orders=(_matched_witness_order(attempt_id=None),),
    )
    assert (None, ReconciliationClass.ORPHAN_BROKER_ORDER) in _classes(report)
    assert report.permits_rearm is False
