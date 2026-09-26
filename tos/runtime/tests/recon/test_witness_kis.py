"""``KisStockBrokerWitness`` tests — multi-page continuation walk (mirrors the measured
P-BAL truncation-risk shape), futures refusal, independence, and secret hygiene.

Fixture shape mirrors ``docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign/
P-BAL-20260911T002427Z.json``: 25 holdings across 2 pages (20 then 5), broker ``tr_cont``
``'M'`` on page 0 and a non-more code (measured ``'D'``) on page 1.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from decimal import Decimal

import pytest
from tos_runtime.recon import witness_kis
from tos_runtime.recon.ports import WitnessOrderState, WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_kis import (
    KisStockBrokerWitness,
    KisWitnessCredentialSession,
    KstDateSource,
)
from tos_runtime.recon.witness_kis_client import KisWitnessHttpClient
from tos_runtime.recon.witness_kis_config import FuturesAssetRefused, KisWitnessConfig

from ._fake_kis_get_server import FakeKisGetServer
from ._witness_kis_fakes import (
    FakeCredentialSession,
    FakeKstDateSource,
    RaisingCredentialSession,
)

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
ACCOUNT = "1234567801"  # CANO=12345678, ACNT_PRDT_CD=01


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


# ---------------------------------------------------------------------------
# Continuation walk — positions/cash
# ---------------------------------------------------------------------------


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
    # Page 0 carries no tr_cont request header; page 1 carries 'N' and the cursor the
    # broker returned on page 0 (probes_balance.py's own request-side convention).
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
    """C-1 review: the order join needs the inquiry date (a KIS ODNO is a per-day sequence). The
    snapshot must report the same date the inquiry sent as INQR_STRT_DT/INQR_END_DT."""
    _queue_two_page_balance(server)
    server.queue_response(ORDER_PATH, status=200, body=_empty_order_response())
    snapshot = _witness(server).observe(WitnessScope(account=ACCOUNT))
    assert snapshot.order_inquiry_date == "20260917"  # FakeKstDateSource's default
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


# ---------------------------------------------------------------------------
# Continuation walk — cannot-complete cases (never a partial result)
# ---------------------------------------------------------------------------


def test_more_follows_with_no_continuation_key_raises_witness_unavailable(
    server: FakeKisGetServer,
) -> None:
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={"rt_cd": "0", "output1": [_balance_row("A")]},
        headers={"tr_cont": "M"},  # more follows, but body carries no cursor at all
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
    """Review MEDIUM-1 (2026-09-17): a non-200 response (a proxy, a WAF, an
    intermediary's own error page) whose body happens to parse as JSON shaped like a
    successful KIS answer (``rt_cd="0"``) must never be read as a genuine broker success
    just because the body parses and ``rt_cd`` looks right."""
    server.queue_response(
        BALANCE_PATH,
        status=500,
        body={"rt_cd": "0", "output1": [_balance_row("A")]},
    )
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="HTTP 500"):
        witness.observe(WitnessScope(account=ACCOUNT))


def test_our_own_max_pages_cap_raises_rather_than_returning_a_partial_snapshot(
    server: FakeKisGetServer,
) -> None:
    """This is the pin the task brief calls for: exceeding OUR cap while the broker still
    signals more must raise — never silently return a lower bound (contrast
    ``tools/broker_probes/probes_balance.py``, which IS allowed to report a lower bound;
    a ``WitnessSnapshot`` may not, per ``ports.py``'s own two-outcome contract)."""
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
            headers={"tr_cont": "M"},  # always "more" — never terminates
        )
    witness = _witness(server, max_pages=2)
    with pytest.raises(WitnessUnavailable, match="max_pages"):
        witness.observe(WitnessScope(account=ACCOUNT))


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


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
                    "odno": "0000004470",
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                },
                {
                    "odno": "0000004471",
                    "tot_ccld_qty": "0",
                    "rmn_qty": "5",
                    "cncl_yn": "N",
                },
                {
                    "odno": "0000004472",
                    "tot_ccld_qty": "2",
                    "rmn_qty": "3",
                    "cncl_yn": "N",
                },
                {
                    "odno": "0000004473",
                    "tot_ccld_qty": "0",
                    "rmn_qty": "0",
                    "cncl_yn": "Y",
                },
            ],
        },
    )
    witness = _witness(server)
    # attempt_ids names attempts already known — the witness must return the order
    # regardless (ports.py: never filter by attempt_ids).
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
    """Plan 2026-09-26 egress trading date T-4: ``ord_dt`` (KIS 주문일자) becomes the order's
    date — the broker's, not this process's clock. Anything but YYYYMMDD digits is no date.
    """
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

    # 2026-09-16 23:30 UTC == 2026-09-17 08:30 KST
    source = TrustedKstDateSource(FixedWallClockReference(1789601400000))
    assert source.today() == "20260917"


def test_trusted_date_source_refuses_without_a_reading() -> None:
    """No trusted time, no inquiry — ``WitnessUnavailable``, the port's own "could not answer"."""
    from tos_runtime.calendar.ports import AbsentWallClockReference
    from tos_runtime.recon.witness_kis import TrustedKstDateSource

    with pytest.raises(WitnessUnavailable):
        TrustedKstDateSource(AbsentWallClockReference()).today()


# ---------------------------------------------------------------------------
# Futures refusal
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Account shape
# ---------------------------------------------------------------------------


def test_non_10_digit_account_raises_witness_unavailable(
    server: FakeKisGetServer,
) -> None:
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="10-digit"):
        witness.observe(WitnessScope(account="not-an-account"))


# ---------------------------------------------------------------------------
# Secret hygiene
# ---------------------------------------------------------------------------


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
        # The secrets DO appear as headers on every call (KIS's own wire convention —
        # module docstring) — this assertion documents that as an accepted fact, not an
        # oversight.
        assert request.headers.get("appkey") == "TOP-SECRET-KEY"


def test_one_credential_block_per_request_and_none_left_open(
    server: FakeKisGetServer,
) -> None:
    """C-2 decision (C): the key/secret are readable only inside a block wrapped around ONE
    GET, and every block is closed when ``observe`` returns."""
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


# ---------------------------------------------------------------------------
# Negative greps — this module never touches the evidence store, never reads
# os.environ, never builds its own token lifecycle
# ---------------------------------------------------------------------------


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
