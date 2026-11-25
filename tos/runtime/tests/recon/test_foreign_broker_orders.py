"""An orphan broker order this runtime could not have placed must not withhold its release."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState
from tos.recon import FreshnessMarker
from tos_runtime.rcl.projection import ScopeReservation
from tos_runtime.recon.ports import (
    EgressReceiptObservation,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService

ACCOUNT = "acct-1"
INSTRUMENT = "000660"
KEY = InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)
OURS = "a1"
OUR_RESERVATION = "resv-a1"
OUR_ODNO = "0000021560"
FOREIGN_ODNOS = ("0000008456", "0000008560", "0000019398")
DATE = "20261120"
FOREIGN_TIME = "093015"
OUR_TIME = "125012"


class _Rcl:
    """A reservation projection over a fixed row set; ``raises`` makes the scope unreadable."""

    def __init__(
        self,
        rows: tuple[ScopeReservation, ...] = (),
        *,
        raises: bool = False,
    ) -> None:
        self._rows = rows
        self._raises = raises

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        for row in self._rows:
            if row.reservation_id == reservation_id:
                return row.state
        return None

    def reservation_last_seq(self, _reservation_id: str) -> int | None:
        return None

    def all_reservations(self) -> dict[str, CapacityState]:
        return {row.reservation_id: row.state for row in self._rows}

    def scope_reservations(self, _key: InstrumentKey) -> tuple[ScopeReservation, ...]:
        if self._raises:
            raise RuntimeError("rcl.sqlite3 is unreadable")
        return self._rows

    def reservation_committed_vector(self, _reservation_id: str) -> None:
        return None


class _Evidence:
    def __init__(self, receipts: tuple[EgressReceiptObservation, ...]) -> None:
        self._receipts = receipts

    def receipts(self, _scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        return self._receipts


class _Witness:
    def __init__(self, orders: tuple[WitnessOrder, ...]) -> None:
        self._orders = orders

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=1,
            orders=self._orders,
            positions=((INSTRUMENT, Decimal("1")),),
            positions_complete=True,
            provenance="kis-mock-stock",
            independent_of_evidence_store=True,
            order_inquiry_date=DATE,
        )


@pytest.fixture
def fresh() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def _our_receipt() -> EgressReceiptObservation:
    return EgressReceiptObservation(
        attempt_id=OURS,
        account=ACCOUNT,
        instrument=INSTRUMENT,
        egress_result_kind="FULL_FILL",
        broker_execution_id=OUR_ODNO,
        filled_quantity=Decimal("1"),
        remaining_quantity=Decimal("0"),
        finality_proof_recorded=True,
        source_ref="evidence-egress-result",
        trading_date=DATE,
    )


def _order(
    odno: str,
    *,
    attempt_id: str | None = None,
    order_time: str | None = FOREIGN_TIME,
    state: WitnessOrderState = WitnessOrderState.FILLED,
    remaining: Decimal | None = Decimal("0"),
) -> WitnessOrder:
    return WitnessOrder(
        attempt_id=attempt_id,
        broker_execution_id=odno,
        quantity=Decimal("1"),
        remaining=remaining,
        state=state,
        order_date=DATE,
        order_time=order_time,
    )


def _ours(odno: str = OUR_ODNO) -> WitnessOrder:
    """This runtime's own order, placed after the 12:48 reboot."""
    return _order(odno, order_time=OUR_TIME)


def _reconcile(
    fresh: FreshnessMarker,
    *,
    rows: tuple[ScopeReservation, ...] = (
        ScopeReservation(OUR_RESERVATION, CapacityState.COMMITTED_UNBOUND, 2),
    ),
    orders: tuple[WitnessOrder, ...] = (),
    receipts: tuple[EgressReceiptObservation, ...] | None = None,
    instrument_keys: tuple[InstrumentKey, ...] = (KEY,),
    raises: bool = False,
):
    service = ReconciliationService(
        _Rcl(rows, raises=raises),
        _Evidence(receipts if receipts is not None else (_our_receipt(),)),
        _Witness((_ours(),) + orders),
        reservation_id_for_attempt=lambda attempt_id: (
            OUR_RESERVATION if attempt_id == OURS else None
        ),
    )
    return service.reconcile(
        WitnessScope(
            account=ACCOUNT,
            instrument_keys=instrument_keys,
            attempt_ids=(OURS,),
            order_dates=(DATE,),
        ),
        freshness=fresh,
    )


def _classes(report) -> list[ReconciliationClass]:
    return [record.classification for record in report.classifications]


def test_orders_the_leaf_never_placed_do_not_withhold_its_release(fresh) -> None:
    """The 2026-11-20 incident itself: six foreign orders, one MATCHED attempt, release."""
    report = _reconcile(fresh, orders=tuple(_order(o) for o in FOREIGN_ODNOS))

    assert report.permits_capacity_release is True
    assert report.permits_rearm is True
    assert report.reason is None
    assert _classes(report) == [ReconciliationClass.MATCHED] + [
        ReconciliationClass.ORPHAN_BROKER_ORDER
    ] * len(FOREIGN_ODNOS)
    assert [
        record.broker_execution_id
        for record in report.classifications
        if record.classification is ReconciliationClass.ORPHAN_BROKER_ORDER
    ] == list(FOREIGN_ODNOS)


def _cancel_of(
    parent: str | None,
    *,
    odno: str = "0000021563",
    remaining: Decimal | None = Decimal("0"),
    filled: Decimal | None = Decimal("0"),
) -> WitnessOrder:
    """The 모의 cancel row measured on 2026-11-24: its own ODNO, our order as 원주문 (#1169)."""
    return WitnessOrder(
        attempt_id=None,
        broker_execution_id=odno,
        quantity=filled,
        remaining=remaining,
        state=WitnessOrderState.CANCELLED,
        order_date=DATE,
        order_time="125016",
        origin_execution_id=parent,
    )


def test_the_cancel_row_of_our_own_order_does_not_withhold_its_release(fresh) -> None:
    """#1169: KIS writes a cancel as a row of its own, four seconds AFTER the order it

    cancels. Counted as an unexplained orphan it fails `_placed_before_our_first_order`
    and withholds the very release the cancel earned — the reservation of every cancelled
    order would be held for ever, which is #1167's "safe but useless" one layer down.
    """
    report = _reconcile(fresh, orders=(_cancel_of(OUR_ODNO),))

    assert report.permits_capacity_release is True
    assert report.permits_rearm is True
    assert ReconciliationClass.ORPHAN_BROKER_ORDER in _classes(
        report
    ), "the row is still reported — it is explained, not hidden"


@pytest.mark.parametrize(
    "order,why",
    [
        (_cancel_of(None), "names no 원주문 at all"),
        (_cancel_of("0000008456"), "cancels an order that is not ours"),
        (_cancel_of(OUR_ODNO, remaining=Decimal("1")), "still has quantity on it"),
        (_cancel_of(OUR_ODNO, remaining=None), "states no remainder"),
        (_cancel_of(OUR_ODNO, filled=Decimal("1")), "something executed on it"),
        (_cancel_of(OUR_ODNO, filled=None), "states no executed quantity"),
    ],
    ids=[
        "no-origin",
        "someone-elses-order",
        "remainder-left",
        "remainder-unreadable",
        "filled-quantity",
        "filled-unreadable",
    ],
)
def test_a_cancel_row_that_does_not_settle_one_of_ours_still_withholds(
    fresh, order: WitnessOrder, why: str
) -> None:
    """#1172 리뷰 MEDIUM: the witness demands 체결 0 of a cancel row before it will let that

    row corroborate anything (``confirmed_cancel_parents``); the orphan gate must demand the
    same 0, or a cancel row that DID execute would quietly stop withholding a release here.
    """
    report = _reconcile(fresh, orders=(order,))
    assert report.permits_capacity_release is False, why


def test_an_orphan_carrying_our_own_execution_id_still_withholds(fresh) -> None:
    """The duplicate-order shape: two broker orders answer to one attempt of ours."""
    report = _reconcile(fresh, orders=(_order(OUR_ODNO, order_time=OUR_TIME),))

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False
    assert ReconciliationClass.ORPHAN_BROKER_ORDER in _classes(report)


def test_an_outstanding_reservation_no_matched_attempt_accounts_for_withholds(
    fresh,
) -> None:
    """A send whose receipt was lost still leaves its reservation behind — the orphan may be it."""
    report = _reconcile(
        fresh,
        rows=(
            ScopeReservation(OUR_RESERVATION, CapacityState.COMMITTED_UNBOUND, 2),
            ScopeReservation("resv-lost", CapacityState.COMMITTED_UNBOUND, 3),
        ),
        orders=tuple(_order(o) for o in FOREIGN_ODNOS),
    )

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False


def test_a_released_sibling_reservation_does_not_withhold(fresh) -> None:
    """A RELEASED row consumes no capacity, so it is not an unaccounted reservation."""
    report = _reconcile(
        fresh,
        rows=(
            ScopeReservation(OUR_RESERVATION, CapacityState.COMMITTED_UNBOUND, 2),
            ScopeReservation("resv-done", CapacityState.RELEASED, 5),
        ),
        orders=tuple(_order(o) for o in FOREIGN_ODNOS),
    )

    assert report.permits_capacity_release is True


def test_a_scope_with_no_instrument_key_withholds(fresh) -> None:
    """Without an instrument key the scope's reservations cannot be enumerated at all."""
    report = _reconcile(
        fresh,
        orders=tuple(_order(o) for o in FOREIGN_ODNOS),
        instrument_keys=(),
    )

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False


def test_an_unreadable_rcl_withholds(fresh) -> None:
    """An unreadable RCL explains no orphan, so every orphan keeps its veto."""
    report = _reconcile(
        fresh, orders=tuple(_order(o) for o in FOREIGN_ODNOS), raises=True
    )

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False


def test_an_attempt_without_its_own_witness_order_withholds(fresh) -> None:
    """Our own attempt is unmatched, so a foreign-looking order might be its order after all."""
    report = _reconcile(
        fresh,
        orders=tuple(_order(o) for o in FOREIGN_ODNOS),
        receipts=(
            _our_receipt(),
            EgressReceiptObservation(
                attempt_id="a2",
                account=ACCOUNT,
                instrument=INSTRUMENT,
                egress_result_kind="ACK",
                broker_execution_id=None,
                filled_quantity=None,
                remaining_quantity=None,
                finality_proof_recorded=False,
                source_ref="evidence-egress-result",
                trading_date=DATE,
            ),
        ),
    )

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False
    assert ReconciliationClass.RECEIPT_ONLY in _classes(report)


def test_orders_alone_with_none_of_our_own_permit_nothing(fresh) -> None:
    """With no order of our own in the observation there is nothing to be earlier THAN."""
    service = ReconciliationService(
        _Rcl(),
        _Evidence(()),
        _Witness(tuple(_order(o) for o in FOREIGN_ODNOS)),
    )

    report = service.reconcile(
        WitnessScope(
            account=ACCOUNT, instrument_keys=(KEY,), attempt_ids=(), order_dates=(DATE,)
        ),
        freshness=fresh,
    )

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False
    assert _classes(report) == [ReconciliationClass.ORPHAN_BROKER_ORDER] * len(
        FOREIGN_ODNOS
    )


@pytest.mark.parametrize(
    ("time_", "label"),
    [
        (None, "no broker stamp at all"),
        (OUR_TIME, "the same second as our own order"),
        ("130000", "after our own order"),
    ],
)
def test_an_orphan_not_stamped_before_our_first_order_withholds(
    fresh, time_: str | None, label: str
) -> None:
    """Only a STRICTLY earlier broker stamp proves an order is not ours."""
    report = _reconcile(fresh, orders=(_order("0000099999", order_time=time_),))

    assert report.permits_capacity_release is False, label
    assert report.permits_rearm is False, label


@pytest.mark.parametrize(
    ("state", "remaining", "label"),
    [
        (
            WitnessOrderState.ACKED,
            Decimal("1"),
            "ACKED with its whole quantity outstanding",
        ),
        (WitnessOrderState.PARTIAL, Decimal("1"), "PARTIAL, half of it still working"),
        (
            WitnessOrderState.UNKNOWN,
            Decimal("0"),
            "a state the broker row did not settle",
        ),
        (WitnessOrderState.FILLED, None, "terminal but with no rmn_qty printed"),
    ],
)
def test_an_earlier_orphan_that_is_not_finished_withholds(
    fresh, state: WitnessOrderState, remaining: Decimal | None, label: str
) -> None:
    """An earlier stamp proves the order is not ours; it does not prove the order is over (#1128)."""
    report = _reconcile(
        fresh,
        orders=(_order("0000099999", state=state, remaining=remaining),),
    )

    assert report.permits_capacity_release is False, label
    assert report.permits_rearm is False, label
    assert ReconciliationClass.ORPHAN_BROKER_ORDER in _classes(report), label


def test_an_earlier_cancelled_orphan_with_nothing_left_does_not_withhold(fresh) -> None:
    """A cancelled order with no residual is as over as a filled one, so it still exempts."""
    report = _reconcile(
        fresh,
        orders=(
            _order(
                "0000099999", state=WitnessOrderState.CANCELLED, remaining=Decimal("0")
            ),
        ),
    )

    assert report.permits_capacity_release is True
    assert report.permits_rearm is True


@pytest.mark.parametrize("other_date", ["20261119", "20261121"])
def test_an_orphan_from_another_trading_date_withholds(fresh, other_date: str) -> None:
    """A stamp from a different date is not compared with ours at all, so it proves nothing."""
    other_day = WitnessOrder(
        attempt_id=None,
        broker_execution_id="0000099999",
        quantity=Decimal("1"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
        order_date=other_date,
        order_time="093015",
    )

    report = _reconcile(fresh, orders=(other_day,))

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False


def test_our_own_order_without_a_stamp_withholds(fresh) -> None:
    """If OUR order carries no time, nothing can be shown to precede it."""
    service = ReconciliationService(
        _Rcl((ScopeReservation(OUR_RESERVATION, CapacityState.COMMITTED_UNBOUND, 2),)),
        _Evidence((_our_receipt(),)),
        _Witness(
            (_order(OUR_ODNO, attempt_id=OURS, order_time=None),)
            + tuple(_order(o) for o in FOREIGN_ODNOS)
        ),
        reservation_id_for_attempt=lambda attempt_id: (
            OUR_RESERVATION if attempt_id == OURS else None
        ),
    )

    report = service.reconcile(
        WitnessScope(
            account=ACCOUNT,
            instrument_keys=(KEY,),
            attempt_ids=(OURS,),
            order_dates=(DATE,),
        ),
        freshness=fresh,
    )

    assert report.permits_capacity_release is False
    assert report.permits_rearm is False
