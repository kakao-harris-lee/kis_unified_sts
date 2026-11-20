"""tools/tos_cp3/ops — the mock-account flat check and flatten, as the restart script uses them.

What this pins is the contract ``restart_stock_tenant.sh`` depends on and cannot
see: the exit codes (0 flat · 1 unreadable/rejected · 2 refused · 3 held) and the
fail-closed order — a missing account fingerprint refuses BEFORE anything is
built, so a restart that forgot it stops nothing and archives nothing.

Hermetic: no broker call, no network, no credential file. The client and the
balance read are monkeypatched; the real ones are exercised only against the
mock account by hand (runbook §7.2-f).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3.ops import mock_flat_check as flat
from tools.tos_cp3.ops import mock_flatten as flatten

_FP = "ee1bdb5f1ca2"
_SYMBOL = "005930"


class _Creds:
    cano = "50000000"
    acnt_prdt_cd = "01"
    account_no = "5000000001"


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

    def stock_order_body(
        self, symbol: str, qty: int, *, order_type: str = "limit"
    ) -> dict[str, str]:
        return {"PDNO": symbol, "ORD_QTY": str(qty), "ORD_DVSN": order_type}

    def close(self) -> None:
        self.closed += 1


def _no_env_file(monkeypatch: pytest.MonkeyPatch, module: Any) -> None:
    monkeypatch.setattr(module, "load_env_file", lambda path: Path("/dev/null"))


# --- fail closed on the account fingerprint ---------------------------------


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
    # The flag wins, and an empty flag is still a refusal (no silent env fallback
    # to an account the operator did not name on this call).
    assert flat.resolve_expected_fingerprint("DEADBEEFCAFE") == "deadbeefcafe"
    with pytest.raises(flat.OpsRefusal):
        flat.resolve_expected_fingerprint("")


def test_credentials_come_through_the_bounded_loader_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A test process reads no credential file at all, and says so (#698).

    The hermetic switch is on for the whole pytest session, so
    ``read_explicit_dotenv`` returns nothing and the tool refuses instead of
    running with a half-filled environment. That is also the proof the file is
    read through that loader rather than python-dotenv directly, which the
    repo-wide gate (``tests/unit/config/test_dotenv_call_gate.py``) forbids.
    """
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


# --- argument handling ------------------------------------------------------


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


# --- the balance read -------------------------------------------------------


def test_holdings_sums_rows_per_symbol_and_queries_the_mock_tr() -> None:
    client = _Client(
        {
            "rt_cd": "0",
            "output1": [
                {"pdno": _SYMBOL, "hldg_qty": "1"},
                {"pdno": _SYMBOL, "hldg_qty": "2"},
                {"pdno": "000660", "hldg_qty": ""},
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


# --- exit codes the restart script branches on ------------------------------


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


# --- flatten -----------------------------------------------------------------


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


# --- the open-order read (#1130 review: a resting order is not flat) --------


class _PagedClient(_Client):
    """Answers a fixed sequence of pages and records what was asked for each."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        super().__init__()
        self.pages = list(pages)
        self.sent: list[dict[str, Any]] = []

    def trading_call(
        self,
        method: str,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        self.calls.append((method, path, tr_id))
        self.sent.append(dict(params or {}))
        self.params = dict(params or {})
        payload = self.pages.pop(0) if self.pages else {"rt_cd": "0", "output1": []}
        return 200, payload, 1.0, tr_id


def _page(rows: list[dict[str, Any]], *, fk: str = "", nk: str = "") -> dict[str, Any]:
    return {"rt_cd": "0", "output1": rows, "ctx_area_fk100": fk, "ctx_area_nk100": nk}


def _resting(odno: str = "0000000001", qty: str = "1") -> dict[str, Any]:
    return {"pdno": _SYMBOL, "odno": odno, "rmn_qty": qty, "cncl_yn": "N"}


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"pdno": _SYMBOL, "rmn_qty": "1", "cncl_yn": "N"}, True),
        ({"pdno": _SYMBOL, "rmn_qty": "0", "cncl_yn": "N"}, False),
        ({"pdno": _SYMBOL, "rmn_qty": "1", "cncl_yn": "Y"}, False),
        ({"pdno": "000660", "rmn_qty": "5", "cncl_yn": "N"}, False),
        # Unattributable or unreadable working quantity is never read as flat.
        ({"pdno": "", "rmn_qty": "1", "cncl_yn": "N"}, True),
        ({"pdno": _SYMBOL, "rmn_qty": "??", "cncl_yn": "N"}, True),
    ],
)
def test_row_is_open(row: dict[str, Any], expected: bool) -> None:
    assert flat.row_is_open(row, _SYMBOL) is expected


def test_open_orders_queries_the_mock_tr_with_the_runtimes_parameters() -> None:
    client = _PagedClient([_page([_resting()])])
    assert flat.open_orders(client, _Creds(), _SYMBOL) == [_resting()]
    assert client.calls == [("GET", flat.ORDER_PATH, flat.ORDER_TR_ID)]
    sent = client.sent[0]
    assert sent["PDNO"] == _SYMBOL
    assert sent["CANO"] == _Creds.cano
    # 전체, not 미체결-only: a narrowing filter that returned nothing would read
    # as "no open order" — the one error this check may not make.
    assert sent["CCLD_DVSN"] == "00"
    assert sent["INQR_STRT_DT"] == sent["INQR_END_DT"]
    assert sent["EXCG_ID_DVSN_CD"] == "KRX"
    assert (sent["CTX_AREA_FK100"], sent["CTX_AREA_NK100"]) == ("", "")


def test_open_orders_walks_the_continuation_to_the_brokers_end() -> None:
    client = _PagedClient(
        [
            _page([{"pdno": _SYMBOL, "rmn_qty": "0"}], fk="FK1", nk="NK1"),
            _page([_resting(odno="0000000002")]),
        ]
    )
    working = flat.open_orders(client, _Creds(), _SYMBOL)
    assert [row["odno"] for row in working] == ["0000000002"]
    assert len(client.sent) == 2
    assert (client.sent[1]["CTX_AREA_FK100"], client.sent[1]["CTX_AREA_NK100"]) == (
        "FK1",
        "NK1",
    )


def test_open_orders_refuses_our_page_cap_rather_than_report_none() -> None:
    client = _PagedClient([_page([], fk=f"FK{i}", nk=f"NK{i}") for i in range(9)])
    with pytest.raises(flat.BalanceUnreadable, match="cap"):
        flat.open_orders(client, _Creds(), _SYMBOL, max_pages=3)
    assert len(client.sent) == 3


def test_open_orders_refuses_a_cursor_that_does_not_advance() -> None:
    client = _PagedClient([_page([], fk="FK1", nk="NK1") for _ in range(3)])
    with pytest.raises(flat.BalanceUnreadable, match="did not advance"):
        flat.open_orders(client, _Creds(), _SYMBOL)


def test_open_orders_refuses_a_non_zero_rt_cd() -> None:
    client = _PagedClient([{"rt_cd": "1", "msg1": "조회가 불가합니다"}])
    with pytest.raises(flat.BalanceUnreadable):
        flat.open_orders(client, _Creds(), _SYMBOL)


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


def test_flat_check_is_flat_only_with_no_holding_and_no_working_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _PagedClient([_page([{"pdno": _SYMBOL, "rmn_qty": "0", "cncl_yn": "N"}])])
    _wire_flat_check(monkeypatch, client, {})
    assert flat.main([_SYMBOL]) == flat.EXIT_FLAT


def test_flat_check_reports_an_incomplete_order_read_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _PagedClient([_page([], fk=f"FK{i}", nk=f"NK{i}") for i in range(9)])
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


# --- transport failures: rc 1, and no URL (the URL carries CANO) ------------


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
