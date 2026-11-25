"""``KisStockBrokerWitness`` tests — multi-page continuation walk (mirrors the measured"""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable, Iterator
from decimal import Decimal, InvalidOperation

import pytest
from tos_runtime.posttrade.broker_clock_skew import (
    BrokerClockSkew,
    parse_http_date_ms,
)
from tos_runtime.recon import witness_kis
from tos_runtime.recon.ports import WitnessOrderState, WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_kis import (
    KisOrderRow,
    KisStockBrokerWitness,
    KisWitnessCredentialSession,
    KstDateSource,
)
from tos_runtime.recon.witness_kis_client import KisWitnessHttpClient
from tos_runtime.recon.witness_kis_config import FuturesAssetRefused, KisWitnessConfig

from ._fake_kis_get_server import FakeKisGetServer
from ._measured_cancel import (
    MEASURED_DATE,
    MEASURED_ORIGINAL_ODNO,
    measured_rows,
)
from ._witness_kis_fakes import (
    FakeCredentialSession,
    FakeKstDateSource,
    RaisingCredentialSession,
)

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
ACCOUNT = "1234567801"


@pytest.fixture
def server() -> Iterator[FakeKisGetServer]:
    srv = FakeKisGetServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _config(server: FakeKisGetServer, *, max_pages: int = 10) -> KisWitnessConfig:
    return KisWitnessConfig(
        endpoint_rest_base=server.rest_base,
        balance_path=BALANCE_PATH,
        balance_tr_id="VTTC8434R",
        order_inquiry_path=ORDER_PATH,
        order_inquiry_tr_id="VTTC0081R",
        request_timeout_s=2.0,
        max_pages=max_pages,
        allow_plaintext_for_tests=True,
    )


def _witness(
    server: FakeKisGetServer,
    *,
    max_pages: int = 10,
    credential_session: KisWitnessCredentialSession | None = None,
    date_source: KstDateSource | None = None,
    date_header_sink: Callable[[str | None], None] | None = None,
) -> KisStockBrokerWitness:
    config = _config(server, max_pages=max_pages)
    client = KisWitnessHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=True,
    )
    return KisStockBrokerWitness(
        config=config,
        client=client,
        credential_session=credential_session or FakeCredentialSession(),
        date_source=date_source or FakeKstDateSource(),
        date_header_sink=date_header_sink,
    )


def _balance_row(symbol: str, qty: str = "10") -> dict[str, str]:
    return {"pdno": symbol, "hldg_qty": qty}


def _queue_two_page_balance(server: FakeKisGetServer) -> None:
    """The measured P-BAL shape: 20 rows (tr_cont='M') then 5 rows (tr_cont='D')."""
    page0_rows = [_balance_row(f"A{i:04d}") for i in range(20)]
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": page0_rows,
            "output2": [{"dnca_tot_amt": "10000000"}],
            "ctx_area_fk100": "cursor-fk-1",
            "ctx_area_nk100": "cursor-nk-1",
        },
        headers={"tr_cont": "M"},
    )
    page1_rows = [_balance_row(f"A{i:04d}") for i in range(20, 25)]
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": page1_rows,
            "ctx_area_fk100": "",
            "ctx_area_nk100": "",
        },
        headers={"tr_cont": "D"},
    )


def _empty_order_response() -> dict[str, object]:
    return {"rt_cd": "0", "output1": []}


def test_multi_page_balance_walk_assembles_all_25_positions(
    server: FakeKisGetServer,
) -> None:
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())

    witness = _witness(server)
    snapshot = witness.observe(WitnessScope(account=ACCOUNT))

    assert len(snapshot.positions) == 25
    assert {symbol for symbol, _qty in snapshot.positions} == {
        f"A{i:04d}" for i in range(25)
    }
    assert snapshot.cash == Decimal("10000000")

    balance_requests = server.requests_for(BALANCE_PATH)
    assert len(balance_requests) == 2
    assert "tr_cont" not in balance_requests[0].headers
    assert balance_requests[1].headers["tr_cont"] == "N"
    assert balance_requests[1].query["CTX_AREA_FK100"] == "cursor-fk-1"
    assert balance_requests[1].query["CTX_AREA_NK100"] == "cursor-nk-1"


def test_independent_of_evidence_store_is_true(server: FakeKisGetServer) -> None:
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    witness = _witness(server)
    snapshot = witness.observe(WitnessScope(account=ACCOUNT))
    assert snapshot.independent_of_evidence_store is True
    assert snapshot.provenance == "kis-mock-stock"


def test_snapshot_reports_the_one_date_its_order_inquiry_covered(
    server: FakeKisGetServer,
) -> None:
    """C-1 review: the order join needs the inquiry date (a KIS ODNO is a per-day sequence). The"""
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    snapshot = _witness(server).observe(WitnessScope(account=ACCOUNT))
    assert snapshot.order_inquiry_date == "20260917"
    [order_request] = server.requests_for(ORDER_PATH)
    assert order_request.query["INQR_STRT_DT"] == snapshot.order_inquiry_date
    assert order_request.query["INQR_END_DT"] == snapshot.order_inquiry_date


def test_zero_and_negative_quantity_rows_are_excluded(server: FakeKisGetServer) -> None:
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [_balance_row("HELD", "3"), _balance_row("FLAT", "0")],
            "output2": [{"dnca_tot_amt": "500"}],
        },
        headers={"tr_cont": "D"},
    )
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    witness = _witness(server)
    snapshot = witness.observe(WitnessScope(account=ACCOUNT))
    assert snapshot.positions == (("HELD", Decimal("3")),)


def test_more_follows_with_no_continuation_key_raises_witness_unavailable(
    server: FakeKisGetServer,
) -> None:
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={"rt_cd": "0", "output1": [_balance_row("A")]},
        headers={"tr_cont": "M"},
    )
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="no continuation key"):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_non_advancing_continuation_key_raises_witness_unavailable(
    server: FakeKisGetServer,
) -> None:
    body = {
        "rt_cd": "0",
        "output1": [_balance_row("A")],
        "ctx_area_fk100": "same-cursor",
        "ctx_area_nk100": "same-cursor",
    }
    server.queue_response(BALANCE_PATH, status=200, body=body, headers={"tr_cont": "M"})
    server.queue_response(BALANCE_PATH, status=200, body=body, headers={"tr_cont": "M"})
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="did not advance"):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_broker_rejection_raises_witness_unavailable(server: FakeKisGetServer) -> None:
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={"rt_cd": "1", "msg_cd": "SOME_ERROR"},
    )
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="rejected"):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_non_200_http_status_raises_even_when_the_body_looks_successful(
    server: FakeKisGetServer,
) -> None:
    """Review MEDIUM-1 (2026-09-17): a non-200 response (a proxy, a WAF, an"""
    server.queue_response(
        BALANCE_PATH,
        status=500,
        body={"rt_cd": "0", "output1": [_balance_row("A")]},
    )
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="HTTP 500"):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_a_non_200_says_what_kis_called_it(server: FakeKisGetServer) -> None:
    """#1125: on 2026-11-20 every witness read failed with `returned HTTP 500` and nothing"""
    server.queue_response(
        BALANCE_PATH,
        status=500,
        body={"msg_cd": "EGW00201", "msg1": "초당 거래건수를 초과하였습니다."},
    )
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable) as excinfo:
        witness.observe(WitnessScope(account=ACCOUNT))

    message = str(excinfo.value)
    assert "EGW00201" in message and "초당 거래건수" in message


def test_a_non_200_with_nothing_to_say_names_its_keys(
    server: FakeKisGetServer,
) -> None:
    server.queue_response(BALANCE_PATH, status=500, body={"unexpected": "shape"})
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="keys="):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_our_own_max_pages_cap_raises_rather_than_returning_a_partial_snapshot(
    server: FakeKisGetServer,
) -> None:
    """This is the pin the task brief calls for: exceeding OUR cap while the broker still"""
    for index in range(3):
        server.queue_response(
            BALANCE_PATH,
            status=200,
            body={
                "rt_cd": "0",
                "output1": [_balance_row(f"A{index}")],
                "ctx_area_fk100": f"cursor-{index}",
                "ctx_area_nk100": f"cursor-{index}",
            },
            headers={"tr_cont": "M"},
        )
    witness = _witness(server, max_pages=2)
    with pytest.raises(WitnessUnavailable, match="max_pages"):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_orders_are_parsed_with_attempt_id_always_none_for_orphan_detection(
    server: FakeKisGetServer,
) -> None:
    server.queue_response(BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []})
    server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "005930",
                    "odno": "0000004470",
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                },
                {
                    "pdno": "005930",
                    "odno": "0000004471",
                    "tot_ccld_qty": "0",
                    "rmn_qty": "5",
                    "cncl_yn": "N",
                },
                {
                    "pdno": "005930",
                    "odno": "0000004472",
                    "tot_ccld_qty": "2",
                    "rmn_qty": "3",
                    "cncl_yn": "N",
                },
                {
                    "pdno": "005930",
                    "odno": "0000004473",
                    "tot_ccld_qty": "0",
                    "rmn_qty": "0",
                    "cncl_yn": "Y",
                },
            ],
        },
    )
    witness = _witness(server)
    snapshot = witness.observe(
        WitnessScope(account=ACCOUNT, attempt_ids=("some-other-attempt",))
    )
    assert len(snapshot.orders) == 4
    assert all(order.attempt_id is None for order in snapshot.orders)
    by_odno = {order.broker_execution_id: order for order in snapshot.orders}
    assert by_odno["0000004470"].state is WitnessOrderState.FILLED
    assert by_odno["0000004471"].state is WitnessOrderState.ACKED
    assert by_odno["0000004472"].state is WitnessOrderState.PARTIAL
    assert by_odno["0000004473"].state is WitnessOrderState.CANCELLED


def test_each_order_carries_the_brokers_own_order_date(
    server: FakeKisGetServer,
) -> None:
    """Plan 2026-09-26 egress trading date T-4: ``ord_dt`` (KIS 주문일자) becomes the order's"""
    server.queue_response(BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []})
    rows = [
        ("0000004470", "20260917"),
        ("0000004471", " 20260917 "),
        ("0000004472", "2026-09-17"),
        ("0000004473", ""),
        ("0000004474", None),
    ]
    server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "005930",
                    "odno": odno,
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                    **({} if ord_dt is None else {"ord_dt": ord_dt}),
                }
                for odno, ord_dt in rows
            ],
        },
    )
    snapshot = _witness(server).observe(WitnessScope(account=ACCOUNT))
    by_odno = {o.broker_execution_id: o.order_date for o in snapshot.orders}
    assert by_odno == {
        "0000004470": "20260917",
        "0000004471": "20260917",
        "0000004472": None,
        "0000004473": None,
        "0000004474": None,
    }


def test_trusted_date_source_reads_the_injected_wall_clock_in_kst() -> None:
    from tos_runtime.calendar.ports import FixedWallClockReference
    from tos_runtime.recon.witness_kis import TrustedKstDateSource

    source = TrustedKstDateSource(FixedWallClockReference(1789601400000))
    assert source.today() == "20260917"


def test_trusted_date_source_refuses_without_a_reading() -> None:
    """No trusted time, no inquiry — ``WitnessUnavailable``, the port's own "could not answer"."""
    from tos_runtime.calendar.ports import AbsentWallClockReference
    from tos_runtime.recon.witness_kis import TrustedKstDateSource

    with pytest.raises(WitnessUnavailable):
        TrustedKstDateSource(AbsentWallClockReference()).today()


def test_futures_asset_is_refused_at_construction(server: FakeKisGetServer) -> None:
    config = _config(server)
    client = KisWitnessHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=True,
    )
    with pytest.raises(FuturesAssetRefused, match="never funded"):
        KisStockBrokerWitness(
            config=config,
            client=client,
            credential_session=FakeCredentialSession(),
            date_source=FakeKstDateSource(),
            asset="futures",
        )


@pytest.mark.parametrize(
    "account",
    [
        "not-an-account",
        "123456789",
        "1234-567801",
        "12345678-0-1",
        "１２３４５６７８０１",
    ],
)
def test_a_non_8_2_account_raises_witness_unavailable(
    server: FakeKisGetServer, account: str
) -> None:
    """The witness splits the account with the order codec's own parser"""
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="8-2"):
        witness.observe(WitnessScope(account=account))
    assert server.all_requests == []


def test_secrets_appear_only_in_headers_never_in_query_params(
    server: FakeKisGetServer,
) -> None:
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    credential_session = FakeCredentialSession(
        access_token="TOP-SECRET-TOKEN",
        app_key="TOP-SECRET-KEY",
        app_secret="TOP-SECRET-SECRET",
    )
    witness = _witness(server, credential_session=credential_session)
    witness.observe(WitnessScope(account=ACCOUNT))

    for request in server.all_requests:
        for value in request.query.values():
            assert "TOP-SECRET" not in value
        assert request.headers.get("appkey") == "TOP-SECRET-KEY"


def test_one_credential_block_per_request_and_none_left_open(
    server: FakeKisGetServer,
) -> None:
    """C-2 decision (C): the key/secret are readable only inside a block wrapped around ONE"""
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    credential_session = FakeCredentialSession()
    witness = _witness(server, credential_session=credential_session)
    witness.observe(WitnessScope(account=ACCOUNT))
    assert credential_session.request_credentials_calls == len(server.all_requests)
    assert credential_session.open_blocks == 0


def test_credential_session_failure_is_wrapped_without_leaking_the_secret(
    server: FakeKisGetServer,
) -> None:
    witness = _witness(server, credential_session=RaisingCredentialSession())
    with pytest.raises(WitnessUnavailable) as excinfo:
        witness.observe(WitnessScope(account=ACCOUNT))
    assert "TOP-SECRET" not in str(excinfo.value)
    assert "fake-app-key" not in str(excinfo.value)


def test_non_ascii_credential_is_refused_without_keeping_its_bytes(
    server: FakeKisGetServer,
) -> None:
    """Review finding (PR #806): a ``UnicodeDecodeError`` carries the whole plaintext in"""
    witness = _witness(
        server, credential_session=FakeCredentialSession(app_secret="SECRÉT-KEY")
    )
    with pytest.raises(WitnessUnavailable) as excinfo:
        witness.observe(WitnessScope(account=ACCOUNT))
    chain: list[BaseException] = []
    exc: BaseException | None = excinfo.value
    while exc is not None and len(chain) < 10:
        chain.append(exc)
        exc = exc.__cause__ or exc.__context__
    assert not any(isinstance(link, UnicodeDecodeError) for link in chain)
    assert all("SECR" not in str(link) for link in chain)
    assert server.all_requests == []


def test_http_rejection_message_never_contains_appkey_or_appsecret(
    server: FakeKisGetServer,
) -> None:
    server.queue_response(BALANCE_PATH, status=200, body={"rt_cd": "9", "msg_cd": "X"})
    credential_session = FakeCredentialSession(
        access_token="TOP-SECRET-TOKEN",
        app_key="TOP-SECRET-KEY",
        app_secret="TOP-SECRET-SECRET",
    )
    witness = _witness(server, credential_session=credential_session)
    with pytest.raises(WitnessUnavailable) as excinfo:
        witness.observe(WitnessScope(account=ACCOUNT))
    message = str(excinfo.value)
    assert "TOP-SECRET" not in message


def test_module_never_touches_the_evidence_store() -> None:
    source = inspect.getsource(witness_kis)
    for needle in (
        "SqliteEvidenceStore",
        "evidence_reader",
        "store.append",
        "EvidenceReceiptReader",
    ):
        assert needle not in source


def test_module_reads_no_ambient_environment() -> None:
    source = inspect.getsource(witness_kis)
    assert "import os" not in source
    assert "os.environ" not in source.replace("``os.environ``", "")
    assert "os.getenv" not in source.replace("``os.getenv``", "")


@pytest.mark.parametrize("pdno", [None, "000660"])
def test_an_order_row_not_naming_the_queried_instrument_makes_the_read_unavailable(
    server: FakeKisGetServer, pdno: str | None
) -> None:
    """PR-3b review HIGH 2: ODNO-only joining would let a row for another symbol (or naming"""
    from tos.engine.records import InstrumentKey

    row = {"odno": "0000004470", "tot_ccld_qty": "1", "rmn_qty": "0", "cncl_yn": "N"}
    if pdno is not None:
        row["pdno"] = pdno
    server.queue_response(BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []})
    server.queue_response(ORDER_PATH, status=200, body={"rt_cd": "0", "output1": [row]})
    with pytest.raises(WitnessUnavailable, match="names instrument"):
        _witness(server).observe(
            WitnessScope(
                account=ACCOUNT,
                instrument_keys=(InstrumentKey(account=ACCOUNT, instrument="005930"),),
            )
        )


@pytest.mark.parametrize(
    "body",
    [
        {"rt_cd": "0"},
        {"rt_cd": "0", "output1": None},
        {"rt_cd": "0", "output1": {}},
        {"rt_cd": "0", "output1": {"odno": "0000009999", "pdno": "005930"}},
    ],
    ids=["missing", "null", "empty-dict", "dict"],
)
def test_a_malformed_order_container_makes_the_whole_read_unavailable(
    server: FakeKisGetServer, body: dict[str, object]
) -> None:
    """HTTP 200, ``rt_cd: "0"``, no more pages — but ``output1`` is absent, ``null``, or a"""
    server.queue_response(ORDER_PATH, status=200, body=body)
    with pytest.raises(WitnessUnavailable, match="carried no output1 list"):
        _witness(server).order_rows(
            WitnessScope(account=ACCOUNT), inquiry_date="20261023"
        )


def test_an_empty_order_list_is_a_well_formed_read_with_no_rows(
    server: FakeKisGetServer,
) -> None:
    """The positive control for the two tests around it: an empty LIST is a complete read of"""
    server.queue_response(ORDER_PATH, status=200, body={"rt_cd": "0", "output1": []})
    date, rows = _witness(server).order_rows(
        WitnessScope(account=ACCOUNT), inquiry_date="20261023"
    )
    assert (date, rows) == ("20261023", ())


@pytest.mark.parametrize(
    "bad_row",
    [None, "0000009999", 7, ["0000009999"]],
    ids=["null", "str", "int", "list"],
)
def test_an_unreadable_order_row_makes_the_whole_read_unavailable(
    server: FakeKisGetServer, bad_row: object
) -> None:
    """One readable row beside one that is not an object at all. The unreadable row used to be"""
    good = {
        "pdno": "005930",
        "odno": "0000004470",
        "ord_dt": "20261023",
        "tot_ccld_qty": "1",
        "rmn_qty": "0",
        "cncl_yn": "N",
    }
    server.queue_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output1": [good, bad_row]}
    )
    with pytest.raises(WitnessUnavailable, match="not an object"):
        _witness(server).order_rows(
            WitnessScope(account=ACCOUNT), inquiry_date="20261023"
        )


@pytest.mark.parametrize(
    "pdno",
    [5930, ["005930"], {"code": "005930"}, True],
    ids=["number", "array", "object", "bool"],
)
def test_a_holdings_row_whose_pdno_is_not_a_string_is_not_a_complete_observation(
    server: FakeKisGetServer, pdno: object
) -> None:
    """Issue #981, the holdings axis: only a STRING ``pdno`` names a symbol."""
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={"rt_cd": "0", "output1": [{"pdno": pdno, "hldg_qty": "10"}]},
        headers={"tr_cont": "D"},
    )
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    snapshot = _witness(server).observe(WitnessScope(account=ACCOUNT))
    assert snapshot.positions == ()
    assert snapshot.positions_complete is False


def test_a_string_pdno_row_is_a_complete_observation(
    server: FakeKisGetServer,
) -> None:
    """The positive control for the test above: the measured wire shape (all strings) is read,"""
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={"rt_cd": "0", "output1": [{"pdno": "005930", "hldg_qty": "10"}]},
        headers={"tr_cont": "D"},
    )
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    snapshot = _witness(server).observe(WitnessScope(account=ACCOUNT))
    assert snapshot.positions == (("005930", Decimal("10")),)
    assert snapshot.positions_complete is True


@pytest.mark.parametrize("field", ["odno", "orgn_odno", "pdno"])
@pytest.mark.parametrize(
    "value",
    [5930, ["005930"], {"code": "005930"}, True],
    ids=["number", "array", "object", "bool"],
)
def test_an_order_identifier_that_is_not_a_string_is_unreadable(
    field: str, value: object
) -> None:
    row = {
        "odno": "0000004470",
        "orgn_odno": "0000000000",
        "pdno": "005930",
        field: value,
    }

    parsed = witness_kis.KisOrderRow.from_wire(row)

    assert getattr(parsed, field) is None


def test_order_identifiers_keep_their_measured_string_form() -> None:
    parsed = witness_kis.KisOrderRow.from_wire(
        {"odno": " 0000004470 ", "orgn_odno": "0000000000", "pdno": " 005930 "}
    )

    assert (parsed.odno, parsed.orgn_odno, parsed.pdno) == (
        "0000004470",
        "0000000000",
        "005930",
    )


def _priced_wire_row(**overrides: object) -> dict[str, object]:
    """One ``VTTC0081R`` ``output1`` row in the measured wire shape (all strings)."""
    row: dict[str, object] = {
        "ord_dt": "20261117",
        "odno": "0000004470",
        "orgn_odno": "0000000000",
        "pdno": "005930",
        "ord_qty": "1",
        "tot_ccld_qty": "1",
        "rmn_qty": "0",
        "rjct_qty": "0",
        "cncl_yn": "N",
        "avg_prvs": "193300",
        "tot_ccld_amt": "193300",
    }
    row.update(overrides)
    return row


def test_the_execution_price_fields_are_read_as_exact_decimals() -> None:
    """``avg_prvs``/``tot_ccld_amt`` are whole KRW as the broker printed them — the tree's"""
    parsed = witness_kis.KisOrderRow.from_wire(_priced_wire_row())

    assert (parsed.avg_prvs, parsed.tot_ccld_amt) == (
        Decimal("193300"),
        Decimal("193300"),
    )
    assert (parsed.ord_qty, parsed.tot_ccld_qty, parsed.rmn_qty) == (
        Decimal("1"),
        Decimal("1"),
        Decimal("0"),
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "-",
        None,
        ["193300"],
        {"price": "193300"},
        True,
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
    ],
    ids=[
        "blank",
        "whitespace",
        "dash",
        "null",
        "array",
        "object",
        "bool",
        "nan",
        "snan",
        "infinity",
        "negative-infinity",
    ],
)
def test_an_unusable_execution_price_leaves_the_rest_of_the_row_readable(
    value: object,
) -> None:
    """A blank/absent/unparseable price is ``None`` — never a refused row and never a changed"""
    parsed = witness_kis.KisOrderRow.from_wire(
        _priced_wire_row(avg_prvs=value, tot_ccld_amt=value)
    )

    assert (parsed.avg_prvs, parsed.tot_ccld_amt) == (None, None)
    assert (parsed.odno, parsed.ord_dt, parsed.cancelled) == (
        "0000004470",
        "20261117",
        False,
    )
    assert (parsed.ord_qty, parsed.tot_ccld_qty, parsed.rmn_qty) == (
        Decimal("1"),
        Decimal("1"),
        Decimal("0"),
    )


def test_a_non_finite_price_never_reaches_a_comparison() -> None:
    """``Decimal("NaN") > 0`` RAISES ``InvalidOperation`` — it is not ``False``."""
    parsed = witness_kis.KisOrderRow.from_wire(
        _priced_wire_row(avg_prvs="NaN", tot_ccld_amt="Infinity")
    )

    assert (parsed.avg_prvs, parsed.tot_ccld_amt) == (None, None)
    with pytest.raises(InvalidOperation):
        _ = Decimal("NaN") > 0


def test_a_row_without_the_price_fields_parses_as_it_always_did() -> None:
    """Every ``output1`` row the observer met before these fields existed had neither key."""
    row = _priced_wire_row()
    row.pop("avg_prvs")
    row.pop("tot_ccld_amt")

    parsed = witness_kis.KisOrderRow.from_wire(row)

    assert (parsed.avg_prvs, parsed.tot_ccld_amt) == (None, None)
    assert parsed.tot_ccld_qty == Decimal("1")


def test_a_callers_deadline_stops_the_walk_and_returns_no_partial_list(
    server: FakeKisGetServer,
) -> None:
    """Page 0 arrives with rows and ``tr_cont=M`` (more follows); the deadline then expires, so"""
    server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "005930",
                    "odno": "0000004470",
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                }
            ],
            "ctx_area_fk100": "cursor-0",
            "ctx_area_nk100": "cursor-0",
        },
        headers={"tr_cont": "M"},
    )
    pages_seen = {"count": 0}

    def deadline_expired() -> bool:
        expired = pages_seen["count"] > 0
        pages_seen["count"] += 1
        return expired

    with pytest.raises(WitnessUnavailable, match="deadline"):
        _witness(server).order_rows(
            WitnessScope(account=ACCOUNT),
            inquiry_date="20261023",
            deadline_expired=deadline_expired,
        )
    assert len(server.requests_for(ORDER_PATH)) == 1


def test_a_deadline_already_past_sends_no_request_at_all(
    server: FakeKisGetServer,
) -> None:
    """The predicate is asked BEFORE the first page too, so the observer's date loop needs no"""
    with pytest.raises(WitnessUnavailable, match="deadline"):
        _witness(server).order_rows(
            WitnessScope(account=ACCOUNT),
            inquiry_date="20261023",
            deadline_expired=lambda: True,
        )
    assert server.all_requests == []


def test_a_pacer_refused_slot_is_witness_unavailable_with_no_request(
    server: FakeKisGetServer,
) -> None:
    """Issue #970: the witness reads through the app key's REAL credential session, so its GET"""
    from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
    from tos_runtime.transport.kis_mock.pacer import KisPacing

    from ..transport.kis_mock._fakes import (
        FakeMonotonicSource,
        InMemoryCredentialCustody,
        RecordingEvidenceSink,
    )

    class _TokenClient:
        def issue_token(
            self,
            _app_key: bytes,
            _app_secret: bytes,
            *,
            path: str,  # noqa: ARG002
        ) -> dict[str, object]:
            return {"access_token": "tok-1", "expires_in": 86_400}

    session = KisCredentialSessions(
        custody=InMemoryCredentialCustody(
            {"kis_mock.app_key": b"key", "kis_mock.app_secret": b"secret"}
        ),
        monotonic=FakeMonotonicSource(start_ms=5_000),
        evidence_sink=RecordingEvidenceSink(),
    ).session_for(
        client=_TokenClient(),
        app_key_scope="kis_mock.app_key",
        app_secret_scope="kis_mock.app_secret",
        token_endpoint_base=server.rest_base,
        token_path="/oauth2/tokenP",
        token_reissue_min_interval_s=60,
        pacing=KisPacing(min_interval_ms=2_000, wait_budget_ms=1_000),
    )

    with pytest.raises(WitnessUnavailable):
        _witness(server, credential_session=session).order_rows(
            WitnessScope(account=ACCOUNT), inquiry_date="20261023"
        )
    assert server.all_requests == []


def test_every_read_hands_its_date_header_to_the_skew_meter(
    server: FakeKisGetServer,
) -> None:
    """Issue #1138: the host↔broker offset is measured on the very reads the judgment uses."""
    seen: list[str | None] = []
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    witness = _witness(server, date_header_sink=seen.append)

    witness.observe(WitnessScope(account=ACCOUNT))

    assert len(seen) == 3, seen
    assert all(parse_http_date_ms(value) is not None for value in seen), seen
    meter = BrokerClockSkew(
        tolerance_s=30, host_unix_ms=lambda: int(time.time() * 1000)
    )
    meter.observe(seen[-1])
    assert meter.corroborated() is True


def test_a_sink_that_raises_does_not_break_the_read(server: FakeKisGetServer) -> None:
    """The meter is a judgment input, not the witness's answer."""

    def _boom(value: str | None) -> None:
        raise RuntimeError(f"meter exploded on {value!r}")

    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    witness = _witness(server, date_header_sink=_boom)

    snapshot = witness.observe(WitnessScope(account=ACCOUNT))

    assert len(snapshot.positions) == 25


def _wire_row(**overrides: str) -> dict[str, str]:
    """One ``VTTC0081R`` ``output1`` row in the measured field names (2026-11-23, #948)."""
    row = {
        "ord_dt": "20261123",
        "odno": "0000004470",
        "orgn_odno": "0000000000",
        "pdno": "005930",
        "ord_qty": "3",
        "tot_ccld_qty": "0",
        "rmn_qty": "3",
        "rjct_qty": "0",
        "cncl_yn": "N",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("spelling", ["cncl_cfrm_qty", "cnc_cfrm_qty"])
def test_the_cancel_confirmed_quantity_is_read_under_either_wire_spelling(
    spelling: str,
) -> None:
    parsed = KisOrderRow.from_wire(_wire_row(cncl_yn="Y", **{spelling: "3"}))
    assert parsed.cancel_confirmed_qty == Decimal("3")
    assert parsed.cancel_withdrew_remainder is True


@pytest.mark.parametrize(
    "row,withdrew",
    [
        (_wire_row(cncl_yn="Y", cncl_cfrm_qty="3"), True),
        (_wire_row(cncl_yn="Y", cncl_cfrm_qty="4"), True),
        (_wire_row(cncl_yn="Y", rmn_qty="0", cncl_cfrm_qty="3"), True),
        (_wire_row(cncl_yn="Y", tot_ccld_qty="3", rmn_qty="0"), True),
        (_wire_row(cncl_yn="Y"), False),
        (_wire_row(cncl_yn="Y", cncl_cfrm_qty="2"), False),
        (_wire_row(cncl_yn="Y", cncl_cfrm_qty=""), False),
        (_wire_row(cncl_yn="Y", rmn_qty="x"), False),
        (_wire_row(rmn_qty="0"), False),
    ],
    ids=[
        "confirmed-covers-the-remainder",
        "confirmed-over-the-remainder",
        "zero-remainder-and-confirmed",
        "nothing-was-outstanding",
        "accepted-only",
        "confirmed-short",
        "confirmed-blank",
        "unreadable-remainder",
        "not-cancelled",
    ],
)
def test_cncl_yn_alone_never_closes_a_row_that_still_has_a_remainder(
    row: dict[str, str], withdrew: bool
) -> None:
    """``mock_flat_check.row_has_working_quantity``'s rule, read off the typed row."""
    assert KisOrderRow.from_wire(row).cancel_withdrew_remainder is withdrew


@pytest.mark.parametrize(
    "row",
    [
        _wire_row(cncl_yn="Y", rmn_qty="0"),
        _wire_row(cncl_yn="Y", rmn_qty="0", cncl_cfrm_qty="2"),
        _wire_row(cncl_yn="Y", rmn_qty="0", ord_qty="x"),
        _wire_row(cncl_yn="Y", rmn_qty="0", tot_ccld_qty="x"),
    ],
    ids=["unconfirmed", "confirmed-short", "ordered-unreadable", "filled-unreadable"],
)
def test_a_zeroed_remainder_is_not_a_withdrawal_without_the_confirmed_quantity(
    row: dict[str, str],
) -> None:
    """#948 리뷰 MEDIUM 2: ``rmn_qty=0`` with 주문수량 > 총체결수량 may be KIS ACCEPTING the

    cancel rather than the exchange confirming it — unmeasured as of 2026-11-23. Until the
    broker states a 취소확인수량 that covers the shortfall, the quantity is not proven
    withdrawn and nothing may be released on it.
    """
    assert KisOrderRow.from_wire(row).cancel_withdrew_remainder is False


@pytest.mark.parametrize(
    "row,remaining",
    [
        (_wire_row(cncl_yn="Y", rmn_qty="0"), Decimal("0")),
        (_wire_row(cncl_yn="Y", cncl_cfrm_qty="3"), Decimal("0")),
        (_wire_row(cncl_yn="Y", cncl_cfrm_qty="1"), Decimal("3")),
        (_wire_row(cncl_yn="Y"), Decimal("3")),
    ],
    ids=["already-zero", "withdrawn", "confirmed-short", "accepted-only"],
)
def test_a_withdrawn_remainder_is_reported_as_zero_executable_quantity(
    row: dict[str, str], remaining: Decimal
) -> None:
    order = KisStockBrokerWitness._order_from_row(  # noqa: SLF001
        KisOrderRow.from_wire(row)
    )
    assert order.state is WitnessOrderState.CANCELLED
    assert order.remaining == remaining


def _measured() -> tuple[KisOrderRow, KisOrderRow]:
    """``(cancel row, original row)`` as parsed from the 2026-11-24 measurement."""
    cancel_wire, original_wire = measured_rows()
    return KisOrderRow.from_wire(cancel_wire), KisOrderRow.from_wire(original_wire)


def test_the_measured_cancel_puts_cncl_yn_y_on_the_cancel_row_not_the_original() -> (
    None
):
    """#1169: the premise #1167's release rule got wrong. The original NEVER says cncl_yn=Y."""
    cancel, original = _measured()

    assert original.cancelled is False
    assert (original.tot_ccld_qty, original.rmn_qty) == (Decimal("0"), Decimal("0"))
    assert original.cancel_confirmed_qty == Decimal("1")
    assert (
        original.cancel_withdrew_remainder is False
    ), "#1167's rule can never fire here"

    assert cancel.cancelled is True
    assert cancel.orgn_odno == MEASURED_ORIGINAL_ODNO
    assert cancel.sll_buy_dvsn_cd == original.sll_buy_dvsn_cd == "02"


def test_the_measured_shape_needs_the_confirmed_quantity_and_the_cancel_row() -> None:
    """Both halves, or nothing — either alone is a cancel KIS may only have ACCEPTED."""
    cancel, original = _measured()
    parents = witness_kis.confirmed_cancel_parents((cancel, original))

    assert original.unfilled_cancel_settled(parents) is True
    assert (
        original.unfilled_cancel_settled(frozenset()) is False
    ), "no corroborating row"


@pytest.mark.parametrize(
    "override,why",
    [
        ({"cncl_cfrm_qty": "0"}, "nothing confirmed"),
        ({"cncl_cfrm_qty": ""}, "confirmed quantity unreadable"),
        ({"rmn_qty": "1"}, "quantity still stated as working"),
        ({"tot_ccld_qty": "1", "ord_qty": "2"}, "something executed"),
        ({"ord_qty": "x"}, "ordered quantity unreadable"),
    ],
)
def test_a_measured_shape_one_field_off_is_not_a_settled_cancel(
    override: dict[str, str], why: str
) -> None:
    cancel_wire, original_wire = measured_rows()
    parents = witness_kis.confirmed_cancel_parents(
        (KisOrderRow.from_wire(cancel_wire),)
    )
    row = KisOrderRow.from_wire({**original_wire, **override})
    assert row.unfilled_cancel_settled(parents) is False, why


def test_a_cancel_row_for_another_order_does_not_settle_this_one() -> None:
    """The join is ODNO + 주문일 + 종목 — a cancel naming anything else corroborates nothing.

    ``observe()`` concatenates one walk per symbol, so a cancel row of ANOTHER symbol is in
    the same row list; without 종목 in the key it would settle this row by ODNO alone
    (#1172 리뷰 LOW). ``tot_ccld_qty`` on the cancel row must be 0 for the same reason the
    orphan gate demands it — a cancel that executed withdrew nothing.
    """
    cancel_wire, original_wire = measured_rows()
    elsewhere = KisOrderRow.from_wire({**cancel_wire, "orgn_odno": "0000011559"})
    other_day = KisOrderRow.from_wire({**cancel_wire, "ord_dt": "20261123"})
    other_symbol = KisOrderRow.from_wire({**cancel_wire, "pdno": "005930"})
    executed = KisOrderRow.from_wire({**cancel_wire, "tot_ccld_qty": "1"})
    original = KisOrderRow.from_wire(original_wire)

    assert (
        original.unfilled_cancel_settled(
            witness_kis.confirmed_cancel_parents(
                (elsewhere, other_day, other_symbol, executed)
            )
        )
        is False
    )
    assert witness_kis.confirmed_cancel_parents((other_symbol,)) == frozenset(
        {("11558", MEASURED_DATE, "005930")}
    ), "the row is read, it just does not name THIS instrument's order"


def test_the_measured_original_is_reported_with_no_executable_quantity_left() -> None:
    """Read as merely ACKED it is an order that can never fill again, reported as live."""
    cancel, original = _measured()
    parents = witness_kis.confirmed_cancel_parents((cancel, original))

    order = KisStockBrokerWitness._order_from_row(  # noqa: SLF001
        original, cancel_parents=parents
    )
    assert order.state is WitnessOrderState.CANCELLED
    assert order.remaining == Decimal("0") and order.quantity == Decimal("0")
    # `orgn_odno=0000000000` is KIS's "no 원주문", not order zero.
    assert order.origin_execution_id is None

    cancel_order = KisStockBrokerWitness._order_from_row(  # noqa: SLF001
        cancel, cancel_parents=parents
    )
    assert cancel_order.origin_execution_id == MEASURED_ORIGINAL_ODNO
    assert cancel_order.state is WitnessOrderState.CANCELLED


def test_the_measured_rows_come_back_as_one_cancelled_order_and_its_cancel(
    server: FakeKisGetServer,
) -> None:
    """End to end through ``observe()``: the walk, the parse and the corroboration together."""
    cancel_wire, original_wire = measured_rows()
    _queue_two_page_balance(server)
    server.queue_response(
        ORDER_PATH,
        status=200,
        body={"rt_cd": "0", "output1": [cancel_wire, original_wire]},
    )
    witness = _witness(server, date_source=FakeKstDateSource(MEASURED_DATE))

    snapshot = witness.observe(WitnessScope(account=ACCOUNT))

    by_id = {order.broker_execution_id: order for order in snapshot.orders}
    assert set(by_id) == {MEASURED_ORIGINAL_ODNO, "0000011561"}
    assert by_id[MEASURED_ORIGINAL_ODNO].state is WitnessOrderState.CANCELLED
    assert by_id[MEASURED_ORIGINAL_ODNO].remaining == Decimal("0")
    assert by_id["0000011561"].origin_execution_id == MEASURED_ORIGINAL_ODNO


def test_egw00215_reads_like_egw00201_on_a_tenant_read(
    server: FakeKisGetServer,
) -> None:
    """#1169: EGW00215 is the mock ACCOUNT ledger's per-second limit, a bucket of its own —

    it refused the P-SC probe's flat-start read at 2026-11-24 09:49 KST while the app-key
    bucket (EGW00201, paced by #1170) was fine. On a tenant read it must be what EGW00201
    is: KIS's own code carried into the refusal, retried next cycle, never a verdict.
    """
    server.queue_response(
        BALANCE_PATH,
        status=500,
        body={
            "msg_cd": "EGW00215",
            "msg1": "원장에서 허용 가능한 초당 거래건수를 초과하였습니다.",
        },
    )
    witness = _witness(server)

    with pytest.raises(WitnessUnavailable) as excinfo:
        witness.observe(WitnessScope(account=ACCOUNT))

    message = str(excinfo.value)
    assert "EGW00215" in message and "원장에서" in message
