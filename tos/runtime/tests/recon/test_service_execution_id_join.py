"""``broker_execution_id`` cross-reference in ``ReconciliationService`` (carryover plan W-C C-1).

A real broker witness returns orders with ``attempt_id=None``. These tests pin that such an order
joins its attempt only through an unambiguous one-to-one broker-id match against same-trading-date
evidence receipts, and that every ambiguous, cross-day, undated or unmatched case stays an orphan
(fail-closed).
"""

from __future__ import annotations

import dataclasses
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
)
from .test_service import _matched_receipt as _undated_receipt
from .test_service import _matched_witness_order as _undated_order

TODAY = "20260925"
YESTERDAY = "20260924"


_KEEP = object()


def _matched_receipt(
    trading_date: str | None = TODAY,
    *,
    attempt_id: str | None | object = _KEEP,
    broker_execution_id: str | None | object = _KEEP,
) -> EgressReceiptObservation:
    """``test_service``'s matched receipt, dated ``TODAY`` unless told otherwise."""
    receipt = dataclasses.replace(_undated_receipt(), trading_date=trading_date)
    if attempt_id is not _KEEP:
        assert attempt_id is None or isinstance(attempt_id, str)
        receipt = dataclasses.replace(receipt, attempt_id=attempt_id)
    if broker_execution_id is not _KEEP:
        assert broker_execution_id is None or isinstance(broker_execution_id, str)
        receipt = dataclasses.replace(receipt, broker_execution_id=broker_execution_id)
    return receipt


def _matched_witness_order(
    order_date: str | None = TODAY,
    *,
    attempt_id: str | None | object = _KEEP,
    broker_execution_id: str | None | object = _KEEP,
    quantity: Decimal | None | object = _KEEP,
) -> WitnessOrder:
    """``test_service``'s matched witness order, carrying the broker's own order date
    (``ord_dt``) — ``TODAY`` unless told otherwise."""
    order = dataclasses.replace(_undated_order(), order_date=order_date)
    if attempt_id is not _KEEP:
        assert attempt_id is None or isinstance(attempt_id, str)
        order = dataclasses.replace(order, attempt_id=attempt_id)
    if broker_execution_id is not _KEEP:
        assert broker_execution_id is None or isinstance(broker_execution_id, str)
        order = dataclasses.replace(order, broker_execution_id=broker_execution_id)
    if quantity is not _KEEP:
        assert quantity is None or isinstance(quantity, Decimal)
        order = dataclasses.replace(order, quantity=quantity)
    return order


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


def _assert_orphaned(report: ReconciliationReport) -> None:
    assert _classes(report) == [
        ("a1", ReconciliationClass.STALE_RESERVATION),
        (None, ReconciliationClass.ORPHAN_BROKER_ORDER),
    ]
    assert report.permits_rearm is False
    assert report.permits_capacity_release is False


def test_receipt_from_another_trading_day_does_not_join(
    fresh: FreshnessMarker,
) -> None:
    """Review S2: a KIS ODNO is a per-day sequence. Today's order with no receipt of its own must
    not join yesterday's attempt that happened to record the same ODNO — before this guard both
    permits went True here."""
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(trading_date=YESTERDAY),),
        orders=(_matched_witness_order(attempt_id=None),),
    )
    _assert_orphaned(report)


@pytest.mark.parametrize(
    ("receipt_date", "order_date"),
    [(None, TODAY), (TODAY, None), (None, None)],
    ids=["undated-receipt", "undated-order", "both-undated"],
)
def test_missing_date_on_either_side_does_not_join(
    fresh: FreshnessMarker, receipt_date: str | None, order_date: str | None
) -> None:
    """An undated receipt is every receipt recorded before the trading date existed — it must
    never join. An undated order is a witness row without ``ord_dt``."""
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(trading_date=receipt_date),),
        orders=(_matched_witness_order(order_date, attempt_id=None),),
    )
    _assert_orphaned(report)


def test_order_dated_another_day_does_not_join(fresh: FreshnessMarker) -> None:
    """The mirror of review S2: the receipt is today's, the broker dates the order yesterday."""
    report = _reconcile(
        fresh,
        receipts=(_matched_receipt(),),
        orders=(_matched_witness_order(YESTERDAY, attempt_id=None),),
    )
    _assert_orphaned(report)


def test_attempt_whose_receipts_name_two_ids_does_not_join(
    fresh: FreshnessMarker,
) -> None:
    """Review S1: receipts X then Y for one attempt; the broker shows only X. The service judges
    against the last receipt (Y), so joining on X would merge a real disagreement into MATCHED —
    before this guard both permits went True here."""
    report = _reconcile(
        fresh,
        receipts=(
            _matched_receipt(broker_execution_id="X"),
            _matched_receipt(broker_execution_id="Y"),
        ),
        orders=(_matched_witness_order(attempt_id=None, broker_execution_id="X"),),
    )
    _assert_orphaned(report)


def test_joined_id_must_be_on_the_receipt_used_as_evidence(
    fresh: FreshnessMarker,
) -> None:
    """Same attempt, an id-less receipt last: the evidence receipt names no id at all."""
    report = _reconcile(
        fresh,
        receipts=(
            _matched_receipt(),
            _matched_receipt(broker_execution_id=None),
        ),
        orders=(_matched_witness_order(attempt_id=None),),
    )
    _assert_orphaned(report)


def test_earlier_receipt_with_another_id_blocks_the_join(
    fresh: FreshnessMarker,
) -> None:
    """The evidence receipt (the last one) does carry the order's id, but an earlier receipt of the
    same attempt names another — the attempt's broker identity is not one id."""
    report = _reconcile(
        fresh,
        receipts=(
            _matched_receipt(broker_execution_id="Y"),
            _matched_receipt(broker_execution_id="X"),
        ),
        orders=(_matched_witness_order(attempt_id=None, broker_execution_id="X"),),
    )
    _assert_orphaned(report)


def test_evidence_receipt_from_another_day_blocks_the_join(
    fresh: FreshnessMarker,
) -> None:
    """Today's receipts all carry X, but the receipt the service judges quantities against is a
    later one dated another day with Y — matching on X would compare against Y."""
    report = _reconcile(
        fresh,
        receipts=(
            _matched_receipt(broker_execution_id="X"),
            _matched_receipt(trading_date=YESTERDAY, broker_execution_id="Y"),
        ),
        orders=(_matched_witness_order(attempt_id=None, broker_execution_id="X"),),
    )
    _assert_orphaned(report)
