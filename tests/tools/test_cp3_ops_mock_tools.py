"""tools/tos_cp3/ops — the mock-account flat check and flatten, as the restart script uses them."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.support.probe_auth import StubAuth
from tools.broker_probes.common import (
    MOCK_BASE_URL,
    ProbeCredentials,
    ProbeRun,
    SafetyViolation,
)
from tools.broker_probes.probes_order import MockTradingClient
from tools.tos_cp3.ops import mock_flat_check as flat
from tools.tos_cp3.ops import mock_flatten as flatten

_FP = "ee1bdb5f1ca2"
_SYMBOL = "005930"


class _Creds:
    cano = "50000000"
    acnt_prdt_cd = "01"
    account_no = "5000000001"


_END_OF_SET = "D"


class _Client:
    """Records what a tool asked of the broker. Sends nothing."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {"rt_cd": "0", "output1": []}
        self.calls: list[tuple[str, str, str]] = []
        self.params: dict[str, Any] = {}
        self.orders: list[dict[str, str]] = []
        self.closed = 0

    def trading_call(
        self,
        method: str,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        self.calls.append((method, path, tr_id))
        self.params = dict(params or {})
        return 200, self.payload, 1.0, tr_id

    def trading_get_with_headers(
        self,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        tr_cont: str = "",
    ) -> tuple[int, dict[str, Any], float, str, dict[str, str]]:
        self.calls.append(("GET", path, tr_id))
        self.params = dict(params or {})
        return 200, self.payload, 1.0, tr_id, {"tr_cont": _END_OF_SET}

    def stock_order_body(
        self, symbol: str, qty: int, *, order_type: str = "limit"
    ) -> dict[str, str]:
        return {"PDNO": symbol, "ORD_QTY": str(qty), "ORD_DVSN": order_type}

    def close(self) -> None:
        self.closed += 1


def _no_env_file(monkeypatch: pytest.MonkeyPatch, module: Any) -> None:
    monkeypatch.setattr(module, "load_env_file", lambda path: Path("/dev/null"))


def test_flat_check_refuses_without_fingerprint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(flat.EXPECT_FP_ENV, raising=False)
    monkeypatch.setattr(
        flat, "build_client", lambda **kw: pytest.fail("a client was built")
    )
    assert flat.main([_SYMBOL]) == flat.EXIT_REFUSED
    assert flat.EXPECT_FP_ENV in capsys.readouterr().err


def test_flatten_refuses_without_fingerprint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(flat.EXPECT_FP_ENV, raising=False)
    monkeypatch.setattr(
        flatten, "build_client", lambda **kw: pytest.fail("a client was built")
    )
    assert flatten.main([_SYMBOL]) == flatten.EXIT_REFUSED
    assert flat.EXPECT_FP_ENV in capsys.readouterr().err


def test_fingerprint_comes_from_env_or_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(flat.EXPECT_FP_ENV, "  EE1BDB5F1CA2 ")
    assert flat.resolve_expected_fingerprint(None) == _FP
    assert flat.resolve_expected_fingerprint("DEADBEEFCAFE") == "deadbeefcafe"
    with pytest.raises(flat.OpsRefusal):
        flat.resolve_expected_fingerprint("")


def test_credentials_come_through_the_bounded_loader_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A test process reads no credential file at all, and says so (#698)."""
    env_file = tmp_path / ".env.mock"
    env_file.write_text(
        "KIS_STOCK_APP_KEY=FAKEKEY\n"
        "KIS_STOCK_APP_SECRET=FAKESECRET\n"
        "KIS_STOCK_ACCOUNT_NO=50000000-01\n",
        encoding="utf-8",
    )
    for key in flat.CREDENTIAL_KEYS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(flat.OpsRefusal, match="does not carry"):
        flat.load_env_file(str(env_file))
    assert [key for key in flat.CREDENTIAL_KEYS if key in os.environ] == []


def test_missing_credential_file_is_a_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    missing = tmp_path / ".env.mock"
    assert flat.main([_SYMBOL, "--env-file", str(missing)]) == flat.EXIT_REFUSED
    assert str(missing) in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["5930", "0059300", "00593a", "", " "])
def test_symbol_must_be_six_digits(bad: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        flat.six_digit_symbol(bad)


def test_symbol_is_normalised_not_guessed() -> None:
    assert flat.six_digit_symbol(" 005930 ") == _SYMBOL


def test_both_tools_take_the_same_account_arguments() -> None:
    argv = [
        _SYMBOL,
        "--expect-account-fingerprint",
        _FP,
        "--env-file",
        "/tmp/.env.mock",
        "--token-cache-dir",
        "/tmp/tc",
        "--pace-s",
        "0.5",
    ]
    for parser in (
        flat.build_parser("flat", "d"),
        flatten.build_parser("flatten", "d"),
    ):
        args = parser.parse_args(argv)
        assert args.symbol == _SYMBOL
        assert args.expect_account_fingerprint == _FP
        assert args.env_file == "/tmp/.env.mock"
        assert args.token_cache_dir == "/tmp/tc"
        assert args.pace_s == 0.5


def test_holdings_sums_rows_per_symbol_and_queries_the_mock_tr() -> None:
    client = _Client(
        {
            "rt_cd": "0",
            "output1": [
                {"pdno": _SYMBOL, "hldg_qty": "1"},
                {"pdno": _SYMBOL, "hldg_qty": "2"},
                {"pdno": "000660", "hldg_qty": "0"},
                {"pdno": "", "hldg_qty": "9"},
            ],
        }
    )
    creds = _Creds()
    assert flat.holdings(client, creds) == {_SYMBOL: 3, "000660": 0}
    assert client.calls == [("GET", flat.BALANCE_PATH, flat.BALANCE_TR_ID)]
    assert client.params["CANO"] == creds.cano
    assert client.params["ACNT_PRDT_CD"] == creds.acnt_prdt_cd


def test_holdings_refuses_a_non_zero_rt_cd() -> None:
    with pytest.raises(flat.BalanceUnreadable):
        flat.holdings(_Client({"rt_cd": "1", "msg1": "조회가 불가합니다"}), _Creds())


@pytest.mark.parametrize(
    ("held", "expected"),
    [
        ({}, flat.EXIT_FLAT),
        ({_SYMBOL: 0}, flat.EXIT_FLAT),
        ({_SYMBOL: 1}, flat.EXIT_HELD),
    ],
)
def test_flat_check_exit_codes(
    monkeypatch: pytest.MonkeyPatch, held: dict[str, int], expected: int
) -> None:
    client = _Client()
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flat)
    monkeypatch.setattr(flat, "build_client", lambda **kw: (client, _Creds()))
    monkeypatch.setattr(flat, "holdings", lambda c, creds: held)
    assert flat.main([_SYMBOL]) == expected
    assert client.closed == 1


def test_flat_check_unreadable_balance_is_not_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flat)
    monkeypatch.setattr(flat, "build_client", lambda **kw: (client, _Creds()))

    def _unreadable(c: Any, creds: Any) -> dict[str, int]:
        raise flat.BalanceUnreadable("balance not readable: http 500")

    monkeypatch.setattr(flat, "holdings", _unreadable)
    assert flat.main([_SYMBOL]) == flat.EXIT_UNREADABLE
    assert client.closed == 1


def _wire_flatten(
    monkeypatch: pytest.MonkeyPatch, client: _Client, reads: list[dict[str, int]]
) -> list[tuple[dict[str, str], str]]:
    sent: list[tuple[dict[str, str], str]] = []
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flatten)
    monkeypatch.setattr(flatten, "build_client", lambda **kw: (client, _Creds()))
    monkeypatch.setattr(flatten, "holdings", lambda c, creds: reads.pop(0))

    def _submit(body: dict[str, str], *, side: str) -> tuple[Any, int, Any, str, float]:
        sent.append((body, side))
        return _Placed(), 200, {"rt_cd": "0", "msg1": "ok"}, "", 1.0

    monkeypatch.setattr(client, "submit_stock_verbose", _submit, raising=False)
    return sent


class _Placed:
    odno = "0000000001"


def test_flatten_sends_nothing_when_already_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    sent = _wire_flatten(monkeypatch, client, [{}])
    assert flatten.main([_SYMBOL]) == flatten.EXIT_FLAT
    assert sent == []
    assert client.closed == 1


def test_flatten_market_sells_the_whole_holding_and_polls_to_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    sent = _wire_flatten(monkeypatch, client, [{_SYMBOL: 3}, {_SYMBOL: 0}])
    assert (
        flatten.main([_SYMBOL, "--poll-interval-s", "0", "--poll-tries", "2"])
        == flatten.EXIT_FLAT
    )
    assert sent == [({"PDNO": _SYMBOL, "ORD_QTY": "3", "ORD_DVSN": "market"}, "SELL")]


def test_flatten_reports_a_rejected_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    _wire_flatten(monkeypatch, client, [{_SYMBOL: 1}])
    monkeypatch.setattr(
        client,
        "submit_stock_verbose",
        lambda body, *, side: (None, 200, {"rt_cd": "1", "msg1": "거부"}, "", 1.0),
        raising=False,
    )
    assert flatten.main([_SYMBOL, "--poll-interval-s", "0"]) == flatten.EXIT_REJECTED
    assert client.closed == 1


def test_flatten_says_still_held_when_the_poll_bound_runs_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    _wire_flatten(monkeypatch, client, [{_SYMBOL: 1}, {_SYMBOL: 1}])
    assert (
        flatten.main([_SYMBOL, "--poll-interval-s", "0", "--poll-tries", "1"])
        == flatten.EXIT_STILL_HELD
    )


class _PagedClient(_Client):
    """Answers a fixed sequence of ``(payload, headers)`` pages, recording each ask."""

    def __init__(
        self,
        pages: list[tuple[dict[str, Any], dict[str, str]]],
        *,
        status: int = 200,
    ) -> None:
        super().__init__()
        self.pages = list(pages)
        self.status = status
        self.sent: list[dict[str, Any]] = []
        self.tr_cont_sent: list[str] = []

    def trading_get_with_headers(
        self,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        tr_cont: str = "",
    ) -> tuple[int, dict[str, Any], float, str, dict[str, str]]:
        self.calls.append(("GET", path, tr_id))
        self.sent.append(dict(params or {}))
        self.params = dict(params or {})
        self.tr_cont_sent.append(tr_cont)
        payload, headers = (
            self.pages.pop(0)
            if self.pages
            else ({"rt_cd": "0", "output1": []}, {"tr_cont": _END_OF_SET})
        )
        return self.status, payload, 1.0, tr_id, headers


def _page(
    rows: list[dict[str, Any]],
    *,
    fk: str = "",
    nk: str = "",
    tr_cont: str = _END_OF_SET,
) -> tuple[dict[str, Any], dict[str, str]]:
    """One page: body (rows + cursor) and the header that says whether more follows."""
    body = {
        "rt_cd": "0",
        "output1": rows,
        "ctx_area_fk100": fk,
        "ctx_area_nk100": nk,
    }
    return body, ({"tr_cont": tr_cont} if tr_cont else {})


def _more(
    rows: list[dict[str, Any]], *, fk: str, nk: str
) -> tuple[dict[str, Any], dict[str, str]]:
    return _page(rows, fk=fk, nk=nk, tr_cont="M")


def _resting(odno: str = "0000000001", qty: str = "1") -> dict[str, Any]:
    return {"pdno": _SYMBOL, "odno": odno, "rmn_qty": qty, "cncl_yn": "N"}


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"pdno": _SYMBOL, "rmn_qty": "1", "cncl_yn": "N"}, True),
        ({"pdno": _SYMBOL, "rmn_qty": "0", "cncl_yn": "N"}, False),
        ({"pdno": _SYMBOL, "rmn_qty": "0", "cncl_yn": "Y"}, False),
        ({"pdno": "000660", "rmn_qty": "5", "cncl_yn": "N"}, False),
        ({"pdno": "", "rmn_qty": "1", "cncl_yn": "N"}, True),
    ],
)
def test_row_is_open(row: dict[str, Any], expected: bool) -> None:
    assert flat.row_is_open(row, _SYMBOL) is expected


@pytest.mark.parametrize(
    "rmn_qty",
    ["", "   ", None, "??", "1.5"],
    ids=["blank", "spaces", "none", "not-a-number", "not-an-int"],
)
def test_an_unreadable_remainder_is_open_not_zero(rmn_qty: Any) -> None:
    """Round-1 HIGH: `or "0"` read a blank remainder as a closed order."""
    row = {
        "pdno": _SYMBOL,
        "ord_qty": "1",
        "tot_ccld_qty": "0",
        "rmn_qty": rmn_qty,
        "cncl_yn": "N",
    }
    assert flat.row_is_open(row, _SYMBOL) is True


def test_a_missing_remainder_key_is_open() -> None:
    assert flat.row_is_open({"pdno": _SYMBOL, "cncl_yn": "N"}, _SYMBOL) is True


def test_the_remainder_is_derived_when_the_row_does_not_state_it() -> None:
    """`ord_qty - tot_ccld_qty` is readable, so the row CAN be proven closed."""
    filled = {"pdno": _SYMBOL, "ord_qty": "1", "tot_ccld_qty": "1", "rmn_qty": ""}
    assert flat.row_is_open(filled, _SYMBOL) is False
    working = {"pdno": _SYMBOL, "ord_qty": "2", "tot_ccld_qty": "1", "rmn_qty": ""}
    assert flat.row_is_open(working, _SYMBOL) is True


@pytest.mark.parametrize(
    "row",
    [
        {"pdno": _SYMBOL, "rmn_qty": "", "cncl_yn": "Y"},
        {"pdno": _SYMBOL, "ord_qty": "2", "tot_ccld_qty": "1", "rmn_qty": "5"},
        {"pdno": _SYMBOL, "rmn_qty": "-1"},
    ],
    ids=["cancelled-unquantified", "inconsistent", "negative"],
)
def test_quantities_that_do_not_add_up_are_open(row: dict[str, Any]) -> None:
    assert flat.row_is_open(row, _SYMBOL) is True


def _zero_remainder_row(**overrides: str) -> dict[str, Any]:
    """A row that states ``rmn_qty=0`` while 주문수량 − 총체결수량 is 1 — the #948 M1 input."""
    row: dict[str, Any] = {
        "pdno": _SYMBOL,
        "odno": "0000004470",
        "ord_qty": "1",
        "tot_ccld_qty": "0",
        "rmn_qty": "0",
        "cncl_yn": "N",
    }
    row.update(overrides)
    return row


def test_a_zero_remainder_with_an_unexplained_shortfall_stays_open() -> None:
    """#948 리뷰 MEDIUM 1: 1 ordered, 0 filled, 0 remaining and nothing saying where the

    other share went. Reading that as closed is reading a quantity nobody can account for
    as «flat», so it stays open until this read explains the shortfall.
    """
    assert flat.row_is_open(_zero_remainder_row(), _SYMBOL) is True


@pytest.mark.parametrize(
    "row,parents",
    [
        (_zero_remainder_row(cncl_yn="Y"), frozenset()),
        (_zero_remainder_row(rjct_qty="1"), frozenset()),
        (_zero_remainder_row(), frozenset({"4470"})),
        (_zero_remainder_row(orgn_odno="0000004470"), frozenset()),
        (_zero_remainder_row(ord_qty="1", tot_ccld_qty="1"), frozenset()),
    ],
    ids=[
        "cancel-flag",
        "rejected-covers-it",
        "a-child-row-names-this-one",
        "this-row-is-the-cancel",
        "filled",
    ],
)
def test_a_zero_remainder_closes_once_the_shortfall_is_accounted_for(
    row: dict[str, Any], parents: frozenset[str]
) -> None:
    """The three explanations, plus the shape with no shortfall at all. Under the separate-row

    cancel shape the withdrawal is not on this row, so the parent set of the SAME read is
    what tells that apart from an unaccounted quantity.
    """
    assert flat.row_is_open(row, _SYMBOL, cancel_parents=parents) is False


def test_the_parent_set_comes_from_the_rows_of_one_read() -> None:
    """``orgn_odno`` is matched to ``odno`` with leading zeros dropped on both sides."""
    child = {"odno": "0000004471", "orgn_odno": "0000004470"}
    assert flat.cancel_parent_odnos([_zero_remainder_row(), child]) == frozenset(
        {"4470"}
    )
    assert flat.cancel_parent_odnos([_zero_remainder_row()]) == frozenset()


def test_a_rejected_quantity_short_of_the_shortfall_leaves_it_open() -> None:
    row = _zero_remainder_row(ord_qty="3", tot_ccld_qty="0", rjct_qty="2")
    assert flat.row_is_open(row, _SYMBOL) is True


def test_the_working_quantity_rule_is_shared_without_the_symbol_filter() -> None:
    """The P-SC probe reads rows it already fetched per symbol, so it asks this half."""
    row = {"pdno": "000660", "ord_qty": "1", "tot_ccld_qty": "0", "rmn_qty": "1"}
    assert flat.row_is_open(row, _SYMBOL) is False
    assert flat.row_has_working_quantity(row) is True


def test_an_accepted_cancel_that_left_a_remainder_is_still_open() -> None:
    """#1135 item 1: ord 1 / filled 0 / rmn 1 / cncl_yn=Y can still fill."""
    row = {
        "pdno": _SYMBOL,
        "ord_qty": "1",
        "tot_ccld_qty": "0",
        "rmn_qty": "1",
        "cncl_yn": "Y",
    }
    assert flat.row_is_open(row, _SYMBOL) is True


@pytest.mark.parametrize("key", flat.CANCEL_CONFIRMED_QTY_KEYS)
def test_a_cancel_confirmed_over_the_whole_remainder_closes_the_row(key: str) -> None:
    row = {
        "pdno": _SYMBOL,
        "ord_qty": "1",
        "tot_ccld_qty": "0",
        "rmn_qty": "1",
        "cncl_yn": "Y",
        key: "1",
    }
    assert flat.row_is_open(row, _SYMBOL) is False


@pytest.mark.parametrize(
    "confirmed",
    ["1", "", "0", None, "??"],
    ids=["partial", "blank", "zero", "none", "not-a-number"],
)
def test_a_cancel_confirmed_short_of_the_remainder_leaves_it_open(
    confirmed: Any,
) -> None:
    """Only a confirmation that covers the whole remainder closes the row."""
    row = {
        "pdno": _SYMBOL,
        "ord_qty": "2",
        "tot_ccld_qty": "0",
        "rmn_qty": "2",
        "cncl_yn": "Y",
        "cnc_cfrm_qty": confirmed,
    }
    assert flat.row_is_open(row, _SYMBOL) is True


def test_the_cancel_confirmed_quantity_is_read_whichever_key_carries_it() -> None:
    assert flat.cancel_confirmed_qty({"cnc_cfrm_qty": " 2 "}) == 2
    assert flat.cancel_confirmed_qty({"cncl_cfrm_qty": "3"}) == 3
    assert flat.cancel_confirmed_qty({"cnc_cfrm_qty": ""}) is None
    assert flat.cancel_confirmed_qty({}) is None


def test_open_orders_queries_the_mock_tr_with_the_runtimes_parameters() -> None:
    client = _PagedClient([_page([_resting()])])
    assert flat.open_orders(client, _Creds(), _SYMBOL) == [_resting()]
    assert client.calls == [("GET", flat.ORDER_PATH, flat.ORDER_TR_ID)]
    sent = client.sent[0]
    assert sent["PDNO"] == _SYMBOL
    assert sent["CANO"] == _Creds.cano
    assert sent["CCLD_DVSN"] == "00"
    assert sent["INQR_STRT_DT"] == sent["INQR_END_DT"]
    assert sent["EXCG_ID_DVSN_CD"] == "KRX"
    assert (sent["CTX_AREA_FK100"], sent["CTX_AREA_NK100"]) == ("", "")


def test_the_last_page_is_the_one_the_tr_cont_header_calls_last() -> None:
    """Round-1 MEDIUM: the mock sets cursor keys on its LAST page too."""
    client = _PagedClient([_page([_resting()], fk="FK9", nk="NK9")])
    assert len(flat.open_orders(client, _Creds(), _SYMBOL)) == 1
    assert len(client.sent) == 1, "a page the broker called last was followed"


def test_open_orders_walks_while_the_header_says_more() -> None:
    client = _PagedClient(
        [
            _more([{"pdno": _SYMBOL, "rmn_qty": "0"}], fk="FK1", nk="NK1"),
            _page([_resting(odno="0000000002")], fk="FK2", nk="NK2"),
        ]
    )
    working = flat.open_orders(client, _Creds(), _SYMBOL)
    assert [row["odno"] for row in working] == ["0000000002"]
    assert len(client.sent) == 2
    assert (client.sent[1]["CTX_AREA_FK100"], client.sent[1]["CTX_AREA_NK100"]) == (
        "FK1",
        "NK1",
    )
    assert client.tr_cont_sent == ["", flat.TR_CONT_REQUEST_NEXT]


def test_a_page_without_a_tr_cont_header_is_refused() -> None:
    """Fail closed: with no header there is no end-of-set, only a guess."""
    client = _PagedClient([_page([], tr_cont="")])
    with pytest.raises(flat.BalanceUnreadable, match="tr_cont"):
        flat.open_orders(client, _Creds(), _SYMBOL)


def test_the_header_is_read_whatever_its_case() -> None:
    """The wire spells it; a plain-dict transport would not fold the case for us."""
    client = _PagedClient([({"rt_cd": "0", "output1": []}, {"TR_CONT": "D"})])
    assert flat.header_value({"TR_CONT": " D "}, "tr_cont") == "D"
    assert flat.header_value({}, "tr_cont") == ""
    assert flat.open_orders(client, _Creds(), _SYMBOL) == []


def test_open_orders_refuses_our_page_cap_rather_than_report_none() -> None:
    client = _PagedClient([_more([], fk=f"FK{i}", nk=f"NK{i}") for i in range(9)])
    with pytest.raises(flat.BalanceUnreadable, match="cap"):
        flat.open_orders(client, _Creds(), _SYMBOL)
    assert len(client.sent) == flat.MAX_PAGES


def test_open_orders_refuses_a_cursor_that_does_not_advance() -> None:
    client = _PagedClient([_more([], fk="FK1", nk="NK1") for _ in range(3)])
    with pytest.raises(flat.BalanceUnreadable, match="did not advance"):
        flat.open_orders(client, _Creds(), _SYMBOL)


def test_open_orders_refuses_more_without_a_cursor() -> None:
    client = _PagedClient([_page([], tr_cont="M")])
    with pytest.raises(flat.BalanceUnreadable, match="no continuation key"):
        flat.open_orders(client, _Creds(), _SYMBOL)


def test_open_orders_refuses_a_non_zero_rt_cd() -> None:
    client = _PagedClient(
        [({"rt_cd": "1", "msg1": "조회가 불가합니다"}, {"tr_cont": "D"})]
    )
    with pytest.raises(flat.BalanceUnreadable):
        flat.open_orders(client, _Creds(), _SYMBOL)


def test_open_orders_refuses_a_non_200() -> None:
    client = _PagedClient([_page([])], status=500)
    with pytest.raises(flat.BalanceUnreadable, match="http 500"):
        flat.open_orders(client, _Creds(), _SYMBOL)


def test_holdings_walks_past_the_first_page() -> None:
    """A symbol held only on page 2 must not read as "not held" — that is flat."""
    client = _PagedClient(
        [
            _more([{"pdno": "000660", "hldg_qty": "1"}], fk="FK1", nk="NK1"),
            _page([{"pdno": _SYMBOL, "hldg_qty": "1"}], fk="FK2", nk="NK2"),
        ]
    )
    assert flat.holdings(client, _Creds()) == {"000660": 1, _SYMBOL: 1}
    assert client.tr_cont_sent == ["", flat.TR_CONT_REQUEST_NEXT]
    assert client.calls[0] == ("GET", flat.BALANCE_PATH, flat.BALANCE_TR_ID)


@pytest.mark.parametrize(
    "hldg_qty",
    ["", "   ", None, "??", "1.5"],
    ids=["blank", "spaces", "none", "not-a-number", "not-an-int"],
)
def test_an_unreadable_holding_quantity_is_not_zero(hldg_qty: Any) -> None:
    """#1135 item 2: `or 0` would call a held symbol flat (H1's shape, balance side)."""
    row = (
        {"pdno": _SYMBOL}
        if hldg_qty is None
        else {"pdno": _SYMBOL, "hldg_qty": hldg_qty}
    )
    with pytest.raises(flat.BalanceUnreadable, match="hldg_qty"):
        flat.holdings(_PagedClient([_page([row])]), _Creds())


def test_an_unreadable_holding_does_not_name_the_account() -> None:
    client = _PagedClient([_page([{"pdno": _SYMBOL, "hldg_qty": ""}])])
    with pytest.raises(flat.BalanceUnreadable) as caught:
        flat.holdings(client, _Creds())
    assert _SYMBOL in str(caught.value)
    assert _Creds.cano not in str(caught.value)


def test_a_balance_walk_that_cannot_finish_is_unreadable() -> None:
    client = _PagedClient([_more([], fk=f"FK{i}", nk=f"NK{i}") for i in range(9)])
    with pytest.raises(flat.BalanceUnreadable, match="balance"):
        flat.holdings(client, _Creds())


def _wire_flat_check(
    monkeypatch: pytest.MonkeyPatch, client: Any, held: dict[str, int]
) -> None:
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flat)
    monkeypatch.setattr(flat, "build_client", lambda **kw: (client, _Creds()))
    monkeypatch.setattr(flat, "holdings", lambda c, creds: held)


def test_flat_check_calls_a_resting_order_not_flat(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The leaf must survive an ACKed, unfilled order (#948: no cancel exists)."""
    client = _PagedClient([_page([_resting()])])
    _wire_flat_check(monkeypatch, client, {})
    assert flat.main([_SYMBOL]) == flat.EXIT_HELD
    assert "open orders" in capsys.readouterr().out
    assert client.closed == 1


def test_flat_check_is_not_flat_while_a_cancel_is_only_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The leaf must not boot onto an order the broker may still fill (#1135)."""
    cancelling = {
        "pdno": _SYMBOL,
        "odno": "0000000003",
        "ord_qty": "1",
        "tot_ccld_qty": "0",
        "rmn_qty": "1",
        "cncl_yn": "Y",
    }
    client = _PagedClient([_page([cancelling])])
    _wire_flat_check(monkeypatch, client, {})
    assert flat.main([_SYMBOL]) == flat.EXIT_HELD


def test_flat_check_calls_an_unreadable_holding_quantity_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _PagedClient([_page([{"pdno": _SYMBOL, "hldg_qty": ""}])])
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flat)
    monkeypatch.setattr(flat, "build_client", lambda **kw: (client, _Creds()))
    assert flat.main([_SYMBOL]) == flat.EXIT_UNREADABLE
    assert client.closed == 1


def test_flat_check_is_flat_only_with_no_holding_and_no_working_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _PagedClient([_page([{"pdno": _SYMBOL, "rmn_qty": "0", "cncl_yn": "N"}])])
    _wire_flat_check(monkeypatch, client, {})
    assert flat.main([_SYMBOL]) == flat.EXIT_FLAT


def test_flat_check_reports_an_incomplete_order_read_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _PagedClient([_more([], fk=f"FK{i}", nk=f"NK{i}") for i in range(9)])
    _wire_flat_check(monkeypatch, client, {})
    assert flat.main([_SYMBOL]) == flat.EXIT_UNREADABLE
    assert client.closed == 1


def test_flat_check_spends_no_order_call_when_the_balance_already_says_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _PagedClient([])
    _wire_flat_check(monkeypatch, client, {_SYMBOL: 1})
    assert flat.main([_SYMBOL]) == flat.EXIT_HELD
    assert client.sent == []


_URL_IN_EXC = (
    "HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): "
    "Max retries exceeded with url: /uapi/domestic-stock/v1/trading/"
    "inquire-balance?CANO=50000000&ACNT_PRDT_CD=01"
)


def _raise_transport(*_args: Any, **_kwargs: Any) -> dict[str, int]:
    import requests

    raise requests.ConnectionError(_URL_IN_EXC)


def test_flat_check_maps_a_transport_failure_to_unknown_without_the_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = _Client()
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flat)
    monkeypatch.setattr(flat, "build_client", lambda **kw: (client, _Creds()))
    monkeypatch.setattr(flat, "holdings", _raise_transport)
    assert flat.main([_SYMBOL]) == flat.EXIT_UNREADABLE
    printed = capsys.readouterr()
    assert "ConnectionError" in printed.err
    for leak in ("CANO", "50000000", "openapivts"):
        assert leak not in printed.out + printed.err
    assert client.closed == 1


def test_flatten_maps_a_transport_failure_to_rejected_without_the_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = _Client()
    monkeypatch.setenv(flat.EXPECT_FP_ENV, _FP)
    _no_env_file(monkeypatch, flatten)
    monkeypatch.setattr(flatten, "build_client", lambda **kw: (client, _Creds()))
    monkeypatch.setattr(flatten, "holdings", _raise_transport)
    assert flatten.main([_SYMBOL]) == flatten.EXIT_REJECTED
    printed = capsys.readouterr()
    assert "ConnectionError" in printed.err
    for leak in ("CANO", "50000000", "openapivts"):
        assert leak not in printed.out + printed.err
    assert client.closed == 1


def test_a_probe_error_is_caught_the_same_way() -> None:
    """ProbeError is in the caught set, so it cannot print a call's detail either."""
    from tools.broker_probes.common import ProbeError

    assert issubclass(ProbeError, tuple(flat.broker_transport_errors()))


class _FakeResponse:
    """``requests.Response`` stand-in — status, body, and the RESPONSE headers."""

    def __init__(
        self,
        body: dict[str, Any],
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self) -> dict[str, Any]:
        return self._body


class _RecordingSession:
    """Records every request and answers from a script. Opens no socket."""

    def __init__(self, responses: list[_FakeResponse] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> _FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "params": dict(params or {}),
                "json": json,
            }
        )
        if self._responses:
            return self._responses.pop(0)
        return _FakeResponse({"rt_cd": "0", "output1": []}, headers={"tr_cont": "D"})

    def close(self) -> None:
        self.closed = True


class _RecordingPacer:
    """Counts the pacer slots the client spends, without sleeping."""

    def __init__(self) -> None:
        self.waits = 0

    def wait(self) -> float:
        self.waits += 1
        return 100.0 + self.waits


def _transport_client(session: _RecordingSession) -> MockTradingClient:
    """A real :class:`MockTradingClient` whose socket and pacer are stand-ins."""
    creds = ProbeCredentials(
        app_key="FAKEKEY",
        app_secret="FAKESECRET",
        account_no=_Creds.account_no,
        is_real=False,
        asset="stock",
    )
    run = ProbeRun(
        probe_id="cp3-ops-flat-check", title="t", mode="live", environment="mock"
    )
    client = MockTradingClient(creds, StubAuth(), run, pace_s=0.0)
    client.session.close()
    client.session = session
    client.pacer = _RecordingPacer()
    return client


def test_the_paged_get_asks_the_mock_host_with_a_get() -> None:
    """#1135 item 3: the transport the walk calls, under direct test."""
    session = _RecordingSession(
        [_FakeResponse({"rt_cd": "0", "output1": []}, headers={"tr_cont": "D"})]
    )
    client = _transport_client(session)
    status, parsed, _ms, _text, headers = client.trading_get_with_headers(
        flat.ORDER_PATH, flat.ORDER_TR_ID, params={"PDNO": _SYMBOL}
    )
    assert (status, parsed["rt_cd"], headers["tr_cont"]) == (200, "0", "D")
    sent = session.calls[0]
    assert sent["method"] == "GET"
    assert sent["url"] == f"{MOCK_BASE_URL}{flat.ORDER_PATH}"
    assert sent["json"] is None
    assert sent["params"] == {"PDNO": _SYMBOL}
    assert sent["headers"]["tr_id"] == flat.ORDER_TR_ID


def test_the_paged_get_sends_tr_cont_only_on_a_continuation() -> None:
    session = _RecordingSession()
    client = _transport_client(session)
    client.trading_get_with_headers(flat.ORDER_PATH, flat.ORDER_TR_ID, tr_cont="")
    client.trading_get_with_headers(
        flat.ORDER_PATH, flat.ORDER_TR_ID, tr_cont=flat.TR_CONT_REQUEST_NEXT
    )
    assert "tr_cont" not in session.calls[0]["headers"]
    assert session.calls[1]["headers"]["tr_cont"] == "N"


def test_the_paged_get_refuses_a_real_trading_tr() -> None:
    """The TR gate is what keeps this GET on the 모의투자 account."""
    session = _RecordingSession()
    client = _transport_client(session)
    with pytest.raises(SafetyViolation, match="not a mock TR"):
        client.trading_get_with_headers("/uapi/x", "TTTC0081R")
    assert session.calls == []
    assert client.pacer.waits == 0


def test_the_paged_get_spends_one_pacer_slot_per_call() -> None:
    session = _RecordingSession()
    client = _transport_client(session)
    client.trading_get_with_headers(flat.BALANCE_PATH, flat.BALANCE_TR_ID)
    client.trading_get_with_headers(flat.BALANCE_PATH, flat.BALANCE_TR_ID)
    assert client.pacer.waits == len(session.calls) == 2
    assert client.last_send_instant() == 102.0
