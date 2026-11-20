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
