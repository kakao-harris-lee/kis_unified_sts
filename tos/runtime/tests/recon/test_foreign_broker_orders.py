"""An orphan broker order this runtime could not have placed must not withhold its release.

2026-11-20: 주식일별주문체결조회 is keyed by (account, symbol, trading date), not by leaf, so a
leaf booted mid-day sees every order the account placed on its symbol that day — an archived
leaf's morning round trips, an operator's manual flatten. Each arrived as an
``ORPHAN_BROKER_ORDER`` whose unconditional veto over ``permits_capacity_release`` wedged every
release for the rest of the day. These tests pin both halves of
:func:`~tos_runtime.recon.service._orphans_may_be_ours`: the foreign order does not withhold,
and each shape of "it could be ours" still does.
"""

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
#: The attempt under release, and the reservation it committed against.
OURS = "a1"
OUR_RESERVATION = "resv-a1"
OUR_ODNO = "0000021560"
#: Three of the six orders 000660's fresh leaf inherited on 2026-11-20 — two from the
#: archived morning leaf, one the operator's manual market SELL that flattened the account.
FOREIGN_ODNOS = ("0000008456", "0000008560", "0000019398")
DATE = "20261120"
#: 주문시각 as the broker stamps it. The foreign orders are the morning leaf's and the manual
#: flatten's; this runtime's own order went in after the 12:48 reboot.
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
    """This runtime's own order, placed after the 12:48 reboot.

    ``attempt_id`` is ``None`` because that is the real KIS shape — 주식일별주문체결조회 knows
    only the ODNO, and the join to our attempt happens through the receipt that carries it.
    """
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


def test_an_orphan_carrying_our_own_execution_id_still_withholds(fresh) -> None:
    """The duplicate-order shape: two broker orders answer to one attempt of ours.

    Its broker stamp is our own order's, so the placement-time test is not what withholds here
    — the shared execution id is.
    """
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
    """With no order of our own in the observation there is nothing to be earlier THAN.

    So no orphan is provably foreign, every one keeps its veto, and a report made only of
    orphans permits nothing. This is also why the relaxation can never produce a vacuously
    positive report: being foreign requires one of our own orders in the same observation, and
    that order is an attempt whose own flags are in the tally.
    """
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
    """Only a STRICTLY earlier broker stamp proves an order is not ours.

    This is what keeps an order that merely appeared mid-session — between the balance read and
    the order read, or after a release snapshot expired — withholding the release.
    """
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
    """An earlier stamp proves the order is not ours; it does not prove the order is over (#1128).

    The 10:00 limit BUY an archived leaf left hanging — or an operator's resting order — is
    stamped before this leaf's first order and can still fill after the release, buying a lot no
    reservation covers. Only a terminal state with an exhausted ``rmn_qty`` earns the exemption.
    """
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
    """A stamp from a different date is not compared with ours at all, so it proves nothing.

    An earlier date looks earlier, but a leaf that has run for more than one session could own
    it, and ``ord_tmd`` alone cannot say. Only a same-date, strictly-earlier stamp counts.
    """
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
