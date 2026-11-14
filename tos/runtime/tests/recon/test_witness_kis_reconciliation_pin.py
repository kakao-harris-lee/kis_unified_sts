"""Lane C pin (W3 plan §4 W3 row C: "``ReconciliationService`` 경로 실증 — 실 증인일 때"""

from __future__ import annotations

import pytest
from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState, CapacityVector
from tos.recon import FieldConfidenceClass, FreshnessMarker, SafetyRelevantField
from tos_runtime.rcl.projection import ScopeReservation
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import ReservationProjectionReader, WitnessScope
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService
from tos_runtime.recon.witness_kis import KisStockBrokerWitness
from tos_runtime.recon.witness_kis_client import KisWitnessHttpClient
from tos_runtime.recon.witness_kis_config import KisWitnessConfig
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness

from ._fake_kis_get_server import FakeKisGetServer
from ._witness_kis_fakes import FakeCredentialSession, FakeKstDateSource

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
ACCOUNT = "1234567801"
TODAY = "20260917"


class _MinimalRclReader:
    """A tiny :class:`~tos_runtime.recon.ports.ReservationProjectionReader` double — local to"""

    def __init__(self, states: dict[str, CapacityState]) -> None:
        self._states = dict(states)

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        return self._states.get(reservation_id)

    def reservation_last_seq(self, _reservation_id: str) -> int | None:
        return None

    def all_reservations(self) -> dict[str, CapacityState]:
        return dict(self._states)

    def scope_reservations(self, _key: InstrumentKey) -> tuple[ScopeReservation, ...]:
        return ()

    def reservation_committed_vector(
        self, _reservation_id: str
    ) -> CapacityVector | None:
        return None


@pytest.fixture
def fresh() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def test_rcl_double_satisfies_protocol() -> None:
    assert isinstance(_MinimalRclReader({}), ReservationProjectionReader)


def _append_egress_result(store, **overrides: object) -> None:
    fields: dict[str, object] = {
        "attempt_id": "a1",
        "instrument_key": {"account": ACCOUNT, "instrument": "005930"},
        "egress_result_kind": "FULL_FILL",
        "broker_execution_id": "0000004470",
        "filled_quantity": "1",
        "remaining_quantity": "0",
    }
    fields.update(overrides)
    store.append(fields, kind="EGRESS_RESULT_CONSUMED", record_class="RESULT_UNMATCHED")


def test_synthetic_witness_never_reaches_corroborated_even_when_matched(
    store, fresh
) -> None:
    _append_egress_result(store)
    rcl = _MinimalRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = SqliteEvidenceReceiptReader(store)
    witness = SyntheticLedgerWitness(store)
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )

    [record] = report.classifications
    assert record.attempt_id == "a1"
    assert record.classification == ReconciliationClass.MATCHED
    assert not any(
        fc.confidence_class is FieldConfidenceClass.CORROBORATED
        and fc.field
        in (
            SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
            SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY,
        )
        for fc in report.field_confidences
    )
    assert report.permits_capacity_release is False


@pytest.fixture
def kis_server():
    srv = FakeKisGetServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _kis_witness(server: FakeKisGetServer) -> KisStockBrokerWitness:
    config = KisWitnessConfig(
        endpoint_rest_base=server.rest_base,
        balance_path=BALANCE_PATH,
        balance_tr_id="VTTC8434R",
        order_inquiry_path=ORDER_PATH,
        order_inquiry_tr_id="VTTC0081R",
        request_timeout_s=2.0,
        max_pages=10,
        allow_plaintext_for_tests=True,
    )
    client = KisWitnessHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=True,
    )
    return KisStockBrokerWitness(
        config=config,
        client=client,
        credential_session=FakeCredentialSession(),
        date_source=FakeKstDateSource(),
    )


def _reconcile_same_order(
    store, fresh, kis_server: FakeKisGetServer, **receipt_overrides: object
):
    """Receipt for attempt ``a1`` with ODNO ``0000004470`` (plus ``receipt_overrides``) and the REAL"""
    _append_egress_result(store, **receipt_overrides)
    kis_server.queue_response(
        BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []}
    )
    kis_server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "005930",
                    "odno": "0000004470",
                    "ord_dt": TODAY,
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                }
            ],
        },
    )
    rcl = _MinimalRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = SqliteEvidenceReceiptReader(store)
    witness = _kis_witness(kis_server)
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )

    return report


def test_real_kis_witness_joins_the_same_order_to_its_known_attempt(
    store, fresh, kis_server: FakeKisGetServer
) -> None:
    """The receipt carries today's trading date, the broker row carries today's ``ord_dt``: the"""
    report = _reconcile_same_order(store, fresh, kis_server, trading_date=TODAY)
    [record] = report.classifications
    assert record.attempt_id == "a1"
    assert record.classification == ReconciliationClass.MATCHED
    assert record.broker_execution_id == "0000004470"
    assert report.permits_rearm is True
    assert report.permits_capacity_release is False


@pytest.mark.parametrize(
    "receipt_date", [None, "20260916"], ids=["recorded-before-dates", "other-day"]
)
def test_real_kis_witness_does_not_join_an_undated_or_other_day_receipt(
    store, fresh, kis_server: FakeKisGetServer, receipt_date: str | None
) -> None:
    """A receipt recorded before the trading date existed (no key), or on another day: the ODNO"""
    overrides: dict[str, object] = (
        {} if receipt_date is None else {"trading_date": receipt_date}
    )
    report = _reconcile_same_order(store, fresh, kis_server, **overrides)
    by_attempt = {c.attempt_id: c for c in report.classifications}
    assert by_attempt["a1"].classification == ReconciliationClass.STALE_RESERVATION
    orphans = [c for c in report.classifications if c.attempt_id is None]
    assert [o.broker_execution_id for o in orphans] == ["0000004470"]
    assert report.permits_rearm is False
    assert report.permits_capacity_release is False


@pytest.mark.parametrize(
    "rcl_present,evidence_present",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_kis_witness_permits_stay_false_across_every_rcl_and_evidence_combination(
    store,
    fresh,
    kis_server: FakeKisGetServer,
    rcl_present: bool,
    evidence_present: bool,
) -> None:
    """All four combinations of RCL-reservation-present x evidence-receipt-present with the real"""
    if evidence_present:
        _append_egress_result(store, trading_date=TODAY)
    kis_server.queue_response(
        BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []}
    )
    kis_server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "005930",
                    "odno": "0000004470",
                    "ord_dt": TODAY,
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                }
            ],
        },
    )
    rcl_states = {"a1": CapacityState.POSITION_CONSUMED} if rcl_present else {}
    rcl = _MinimalRclReader(rcl_states)
    evidence = SqliteEvidenceReceiptReader(store)
    witness = _kis_witness(kis_server)
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )

    by_attempt = {c.attempt_id: c for c in report.classifications}
    joined = rcl_present and evidence_present
    assert (by_attempt["a1"].classification is ReconciliationClass.MATCHED) is joined
    assert report.permits_rearm is joined
    assert report.permits_capacity_release is False


_ORPHAN_ODNO = "0000009999"


def _orphan_row() -> dict[str, str]:
    """A broker order this runtime holds no receipt for — today, this instrument."""
    return {
        "pdno": "005930",
        "odno": _ORPHAN_ODNO,
        "ord_dt": TODAY,
        "tot_ccld_qty": "0",
        "rmn_qty": "7",
        "cncl_yn": "N",
    }


def _reconcile_two_page_order_walk(
    store, fresh, kis_server: FakeKisGetServer, second_page: dict[str, object]
):
    """Attempt ``a1``'s receipt and its order row on page 0 (``tr_cont='M'``, a cursor), then"""
    _append_egress_result(store, trading_date=TODAY)
    kis_server.queue_response(
        BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []}
    )
    kis_server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "005930",
                    "odno": "0000004470",
                    "ord_dt": TODAY,
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                }
            ],
            "ctx_area_fk100": "cursor-fk-1",
            "ctx_area_nk100": "cursor-nk-1",
        },
        headers={"tr_cont": "M"},
    )
    kis_server.queue_response(
        ORDER_PATH, status=200, body=second_page, headers={"tr_cont": "D"}
    )
    service = ReconciliationService(
        _MinimalRclReader({"a1": CapacityState.POSITION_CONSUMED}),
        SqliteEvidenceReceiptReader(store),
        _kis_witness(kis_server),
    )
    return service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )


@pytest.mark.parametrize(
    "second_page",
    [
        {"rt_cd": "0"},
        {"rt_cd": "0", "output1": None},
        {"rt_cd": "0", "output1": {}},
        {"rt_cd": "0", "output1": _orphan_row()},
    ],
    ids=["missing", "null", "empty-dict", "dict-carrying-the-orphan"],
)
def test_an_order_page_that_is_not_a_list_makes_the_whole_reconciliation_unavailable(
    store, fresh, kis_server: FakeKisGetServer, second_page: dict[str, object]
) -> None:
    """Page 0 is the attempt's own fill; page 1 is not a list (the last case literally carries"""
    report = _reconcile_two_page_order_walk(store, fresh, kis_server, second_page)
    assert report.classifications == ()
    assert (report.reason or "").startswith("broker witness unavailable")
    assert report.permits_rearm is False
    assert report.permits_capacity_release is False


def test_an_orphan_on_a_well_formed_second_order_page_blocks_the_release(
    store, fresh, kis_server: FakeKisGetServer
) -> None:
    """What the hidden orphan would have done, had the page been readable: ``a1`` joins and is"""
    report = _reconcile_two_page_order_walk(
        store, fresh, kis_server, {"rt_cd": "0", "output1": [_orphan_row()]}
    )
    by_attempt = {c.attempt_id: c for c in report.classifications}
    assert by_attempt["a1"].classification is ReconciliationClass.MATCHED
    orphans = [c for c in report.classifications if c.attempt_id is None]
    assert [o.broker_execution_id for o in orphans] == [_ORPHAN_ODNO]
    assert report.permits_rearm is False
    assert report.permits_capacity_release is False


def test_an_empty_second_order_page_still_matches_the_attempt(
    store, fresh, kis_server: FakeKisGetServer
) -> None:
    """The positive control: a two-page order walk whose second page is an empty LIST is a"""
    report = _reconcile_two_page_order_walk(
        store, fresh, kis_server, {"rt_cd": "0", "output1": []}
    )
    [record] = report.classifications
    assert (record.attempt_id, record.classification) == (
        "a1",
        ReconciliationClass.MATCHED,
    )
    assert report.permits_rearm is True
    assert report.permits_capacity_release is False
