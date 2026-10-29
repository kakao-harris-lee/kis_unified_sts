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
    """The witness splits the account with the order codec's own parser
    (``transport/kis_mock/account.py``, #932) — a shape the order path refuses is refused here
    too, so a fill read can never target a different account than the order did."""
    witness = _witness(server)
    with pytest.raises(WitnessUnavailable, match="8-2"):
        witness.observe(WitnessScope(account=account))
    assert server.all_requests == []  # refused before any GET


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


def test_non_ascii_credential_is_refused_without_keeping_its_bytes(
    server: FakeKisGetServer,
) -> None:
    """Review finding (PR #806): a ``UnicodeDecodeError`` carries the whole plaintext in
    ``.object``; chained onto ``WitnessUnavailable`` it would outlive the zeroed handle. The
    refusal must keep no link to it (neither ``__cause__`` nor ``__context__``)."""
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


@pytest.mark.parametrize("pdno", [None, "000660"])
def test_an_order_row_not_naming_the_queried_instrument_makes_the_read_unavailable(
    server: FakeKisGetServer, pdno: str | None
) -> None:
    """PR-3b review HIGH 2: ODNO-only joining would let a row for another symbol (or naming
    none) corroborate this instrument's fill. The witness keeps the conflict — the whole read is
    unavailable — instead of filtering the row out."""
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


# ---------------------------------------------------------------------------
# Issue #981 — an order row the witness cannot read is never dropped (the #973 fail-open
# class on the orders axis: a dropped row could be an orphan order, and an orphan is what
# must BLOCK a capacity release).
# ---------------------------------------------------------------------------


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
    """HTTP 200, ``rt_cd: "0"``, no more pages — but ``output1`` is absent, ``null``, or a
    dict. The walk recorded that page as zero rows and the order read returned "no orders",
    indistinguishable from a page that genuinely listed none; a row the page hid (the dict
    case literally carries one) therefore stopped existing, and an orphan order that must
    block a release stopped blocking it. All four shapes review-973 round 2 named for the
    BALANCE container are covered here for the ORDER one; ``output1: []`` is the valid empty
    control in :func:`test_an_empty_order_list_is_a_well_formed_read_with_no_rows`.

    Mutation: iterate a ``None`` page as no rows again (the pre-#981 ``for row in rows if
    rows is not None else ()``) -> no raise -> red.
    """
    server.queue_response(ORDER_PATH, status=200, body=body)
    with pytest.raises(WitnessUnavailable, match="carried no output1 list"):
        _witness(server).order_rows(
            WitnessScope(account=ACCOUNT), inquiry_date="20261023"
        )


def test_an_empty_order_list_is_a_well_formed_read_with_no_rows(
    server: FakeKisGetServer,
) -> None:
    """The positive control for the two tests around it: an empty LIST is a complete read of
    an empty order book — it must stay a successful, empty answer, never a refusal."""
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
    """One readable row beside one that is not an object at all. The unreadable row used to be
    skipped, leaving a read that looked complete and carried only what happened to parse —
    while the row it dropped could be the unattributed broker order the release must hold for.
    The whole read is unavailable instead, the same answer a row naming the wrong instrument
    already gets.

    Mutation: ``continue`` on the non-dict row instead of raising -> the good row comes back
    as the whole list -> red.
    """
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
    """Issue #981, the holdings axis: only a STRING ``pdno`` names a symbol.

    ``str(row.get("pdno") or "")`` fabricated a plausible-looking one out of anything (a
    broker that renders the code as a JSON number answers ``pdno: 5930`` for ``005930``), so
    the row read as some OTHER instrument — dropped by the scope filter, or kept under a
    symbol the flatness check never compares against. Either way ``positions`` held no row for
    the instrument being closed while the observation still claimed to be COMPLETE, which
    :func:`~tos_runtime.posttrade.entry_discharge.broker_position_flat` reads as proven flat.
    An unreadable ``pdno`` now makes the observation incomplete, exactly as an unreadable
    ``hldg_qty`` already did (#966 review round 1).

    Mutation: coerce with ``str(...)`` again -> ``positions_complete`` is ``True`` -> red.
    """
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
    """The positive control for the test above: the measured wire shape (all strings) is read,
    attributed, and reported as a COMPLETE holdings observation — the #981 type check must not
    turn an ordinary balance answer into an incomplete one."""
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


# ---------------------------------------------------------------------------
# The caller's deadline (#949 review HIGH): it stops the WALK, and what was read so far is
# never returned. The fill observer owns the clock — this class has none.
# ---------------------------------------------------------------------------


def test_a_callers_deadline_stops_the_walk_and_returns_no_partial_list(
    server: FakeKisGetServer,
) -> None:
    """Page 0 arrives with rows and ``tr_cont=M`` (more follows); the deadline then expires, so
    page 1 is never requested and the read is unavailable — exactly the answer our own
    ``max_pages`` cap gives, for the same reason (``_walk_continuation``'s own contract).

    Mutations: return ``_WalkOutcome(pages=tuple(pages), ...)`` on the deadline instead of
    raising -> the row from page 0 comes back as if it were the whole list -> the
    ``WitnessUnavailable`` assertion goes red; drop the check entirely -> page 1 IS requested
    -> the request-count assertion goes red.
    """
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
        # Fresh for the first page, past for every page after it.
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
    """The predicate is asked BEFORE the first page too, so the observer's date loop needs no
    deadline logic of its own: handing the predicate down is enough to make a read that starts
    too late cost nothing.

    Mutation: ask it only from the second page on -> one GET is sent -> red.
    """
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
    """Issue #970: the witness reads through the app key's REAL credential session, so its GET
    takes a slot from the key's one pacer. The token POST just took the key's slot, and the
    GET's slot is beyond the wait budget: the read fails closed as ``WitnessUnavailable`` and
    nothing reaches the broker — the HOLD path, never a late send.

    Mutation: catch nothing (let the pacer refusal escape as itself) -> not WitnessUnavailable
    -> red; skip the pacer in ``app_credentials`` -> one GET is sent -> red.
    """
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
