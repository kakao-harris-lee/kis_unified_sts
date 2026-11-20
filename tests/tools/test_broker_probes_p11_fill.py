"""Unit tests for P-11's fill path (``tools/broker_probes``)."""

from __future__ import annotations

import argparse
import time
from decimal import Decimal
from typing import Any

import pytest

from tests.support.probe_auth import StubAuth, install_stub_auth
from tools.broker_probes import probes_order
from tools.broker_probes.common import (
    ProbeCredentials,
    ProbeError,
    ProbeRun,
    add_common_args,
    assert_mock_trading_tr,
)
from tools.broker_probes.probes_order import (
    _FILL_NOT_FILLED,
    _FILL_NOT_REFLECTED,
    _FILL_OBSERVED,
    _FILL_UNDETERMINED,
    _STOCK_DAILY_CCLD_TR_MOCK,
    _STOCK_ORD_DVSN,
    _STOCK_ORD_UNPR_MARKET,
    MockTradingClient,
    Tick,
    _futures_tick,
    add_order_args,
    build_stock_order_body,
    probe_p11,
    snap_to_tick,
)

_ACCOUNT = "1234567890"
_CANO = "12345678"
_ACNT_PRDT_CD = "90"
_SYMBOL = "005930"
_FUTURES_SYMBOL = "A01609"

_LAST_PRICE = "70200"

_ACCEPT_ODNO = "0000008686"


@pytest.fixture
def stock_creds() -> ProbeCredentials:
    return ProbeCredentials(
        app_key="test-key",
        app_secret="test-secret",
        account_no=_ACCOUNT,
        is_real=False,
        asset="stock",
    )


@pytest.fixture
def stock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export exactly the env vars ``resolve_credentials`` reads for stock."""
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_STOCK_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


@pytest.fixture
def unpaced_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise ``time.sleep`` so a nonzero ``--pace-s`` costs no wall clock."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _client(creds: ProbeCredentials) -> MockTradingClient:
    """A client with pacing disabled — these tests assert bodies, not intervals."""
    run = ProbeRun(probe_id="P-11", title="t", mode="live", environment="MOCK_VTS")
    return MockTradingClient(creds, StubAuth(), run, pace_s=0.0)


def _args(**overrides: object) -> argparse.Namespace:
    """P-11 arguments at their CLI defaults, with the clocks wound down."""
    base: dict[str, object] = {
        "probe_id": "P-11",
        "symbol": _SYMBOL,
        "asset": "stock",
        "confirm": True,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "samples": 1,
        "margin_pct": 50.0,
        "poll_ms": 5.0,
        "gap_ms": 200.0,
        "inter_trial_s": 0.0,
        "settle_seconds": 0.0,
        "visibility_timeout_s": 30.0,
        "balance_timeout_s": 2.0,
        "late_window_s": 120.0,
        "max_pages": 10,
        "allow_fill": True,
        "stock_order_type": "market",
        "pace_s": 0.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _ccld_row(odno: str, *, filled: str, remaining: str) -> dict[str, Any]:
    """One 주식일별주문체결조회 row, field names per the official COLUMN_MAPPING."""
    return {
        "ord_dt": "20260731",
        "odno": odno,
        "orgn_odno": "",
        "ord_dvsn_name": "시장가",
        "sll_buy_dvsn_cd": "02",
        "pdno": _SYMBOL,
        "prdt_name": "삼성전자",
        "ord_qty": "1",
        "ord_unpr": "0",
        "ord_tmd": "105710",
        "tot_ccld_qty": filled,
        "tot_ccld_amt": "248500",
        "avg_prvs": "248500",
        "rmn_qty": remaining,
        "cncl_yn": "N",
        "rjct_qty": "0",
    }


def _install_recorder(
    monkeypatch: pytest.MonkeyPatch,
    *,
    aspr_unit: str | None = "100",
    balance: str = "reflects",
    fill: str = "filled",
    row_odno: str = _ACCEPT_ODNO,
) -> list[dict[str, Any]]:
    """Serve a quote, an order accept, a balance and an execution inquiry."""
    calls: list[dict[str, Any]] = []
    quote: dict[str, Any] = {"stck_prpr": _LAST_PRICE}
    if aspr_unit is not None:
        quote["aspr_unit"] = aspr_unit

    def _balance_payload() -> dict[str, Any]:
        reads = len([c for c in calls if "trading/inquire-balance" in c["url"]])
        if balance == "pre_filled":
            held = "1"
        elif balance == "flat":
            held = "0"
        else:
            held = "1" if reads > 1 else "0"
        return {"rt_cd": "0", "output1": [{"pdno": _SYMBOL, "hldg_qty": held}]}

    def _ccld_payload() -> dict[str, Any]:
        if fill == "refused":
            return {"rt_cd": "1", "msg1": "모의투자 조회가 안되었습니다", "output1": []}
        if fill == "no_row":
            return {"rt_cd": "0", "msg1": "정상처리", "output1": []}
        if fill == "unfilled":
            row = _ccld_row(row_odno, filled="0", remaining="1")
        elif fill == "unparseable":
            row = _ccld_row(row_odno, filled="", remaining="")
        else:
            row = _ccld_row(row_odno, filled="1", remaining="0")
        return {"rt_cd": "0", "msg1": "정상처리", "output1": [row], "output2": {}}

    def _recorder(
        _session: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        calls.append(
            {
                "url": url,
                "method": method,
                "body": json_body or {},
                "params": params or {},
                "headers": dict(headers),
            }
        )
        if "quotations/inquire-price" in url:
            payload: dict[str, Any] = {"rt_cd": "0", "output": quote}
        elif "trading/inquire-daily-ccld" in url:
            payload = _ccld_payload()
        elif "trading/inquire-balance" in url:
            payload = _balance_payload()
        elif "trading/order-cash" in url:
            payload = {"rt_cd": "0", "output": {"ODNO": _ACCEPT_ODNO}}
        else:  # pragma: no cover - an unexpected path is a test bug, not a pass
            raise AssertionError(f"unexpected probe URL: {url}")
        return 200, payload, 1.0, "{}"

    monkeypatch.setattr(probes_order, "http_json", _recorder)
    install_stub_auth(monkeypatch)
    return calls


def _orders(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if "trading/order-cash" in c["url"]]


def _quotes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if "quotations/inquire-price" in c["url"]]


def _ccld_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if "trading/inquire-daily-ccld" in c["url"]]


def _kinds(calls: list[dict[str, Any]]) -> list[str]:
    """The call sequence as short kind names, for ordering assertions."""
    kinds = []
    for call in calls:
        url = call["url"]
        if "quotations/inquire-price" in url:
            kinds.append("quote")
        elif "trading/inquire-daily-ccld" in url:
            kinds.append("ccld")
        elif "trading/inquire-balance" in url:
            kinds.append("balance")
        elif "trading/order-cash" in url:
            kinds.append("submit")
        else:  # pragma: no cover - see the recorder
            kinds.append("other")
    return kinds


def test_market_body_carries_the_spec_ord_dvsn_and_no_limit_price() -> None:
    """시장가 = ORD_DVSN "01" with ORD_UNPR "0"."""
    body = build_stock_order_body(_CANO, _ACNT_PRDT_CD, _SYMBOL, 1, order_type="market")

    assert body["ORD_DVSN"] == "01"
    assert body["ORD_UNPR"] == "0"
    assert body["ORD_DVSN"] == _STOCK_ORD_DVSN["market"]
    assert body["ORD_UNPR"] == _STOCK_ORD_UNPR_MARKET
    assert body["PDNO"] == _SYMBOL
    assert body["ORD_QTY"] == "1"


def test_stock_market_and_futures_limit_share_the_literal_01(
    stock_creds: ProbeCredentials,
) -> None:
    """The inversion, asserted on both bodies at once."""
    price = snap_to_tick(
        372.13, _futures_tick(_FUTURES_SYMBOL), side="BUY", marketable=False
    )
    client = _client(stock_creds)

    market = client.stock_order_body(_SYMBOL, 1, order_type="market")
    limit = client.futures_order_body(_FUTURES_SYMBOL, 1, price, "BUY")

    assert market["ORD_DVSN"] == limit["ORD_DVSN_CD"] == "01"
    assert market["ORD_UNPR"] == _STOCK_ORD_UNPR_MARKET
    assert limit["UNIT_PRICE"] == price.wire


def test_limit_body_is_unchanged_and_still_carries_the_snapped_price() -> None:
    """The opt-out path must be byte-identical to what it was before."""
    price = snap_to_tick(
        77_220.0,
        Tick(size=Decimal("100"), source="broker-reported 호가단위 (test)"),
        side="BUY",
        marketable=True,
    )

    body = build_stock_order_body(_CANO, _ACNT_PRDT_CD, _SYMBOL, 1, price)

    assert body["ORD_DVSN"] == "00"
    assert body["ORD_UNPR"] == price.wire == "77300"


def test_market_body_refuses_a_limit_price() -> None:
    """A 시장가 order carrying a price would report a fill it never took."""
    price = snap_to_tick(
        372.13, _futures_tick(_FUTURES_SYMBOL), side="BUY", marketable=False
    )

    with pytest.raises(ProbeError, match="must not carry a limit price"):
        build_stock_order_body(
            _CANO, _ACNT_PRDT_CD, _SYMBOL, 1, price, order_type="market"
        )


def test_limit_body_refuses_a_missing_price() -> None:
    """Fail-closed: an omitted price must never become a market order."""
    with pytest.raises(ProbeError, match="needs a tick-snapped price"):
        build_stock_order_body(_CANO, _ACNT_PRDT_CD, _SYMBOL, 1, order_type="limit")


def test_unknown_order_type_is_refused() -> None:
    """No default entry, for the same reason the runtime's table has none."""
    with pytest.raises(ProbeError, match="unknown stock order type"):
        build_stock_order_body(
            _CANO, _ACNT_PRDT_CD, _SYMBOL, 1, order_type="marketable"
        )


def test_cli_defaults_to_a_market_order_and_a_120s_balance_window() -> None:
    """The default is the fix; an operator gets it without passing a flag."""
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    add_order_args(parser)

    args = parser.parse_args([])

    assert args.stock_order_type == "market"
    assert args.balance_timeout_s == 120.0
    assert args.visibility_timeout_s == 30.0


def test_cli_still_offers_the_limit_path() -> None:
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    add_order_args(parser)

    assert (
        parser.parse_args(["--stock-order-type", "limit"]).stock_order_type == "limit"
    )


def test_probe_refuses_an_unknown_order_type_before_contacting_the_broker(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    calls = _install_recorder(monkeypatch)

    with pytest.raises(ProbeError, match="unknown --stock-order-type"):
        probe_p11(_args(stock_order_type="ioc"))

    assert calls == []


def test_the_holdings_baseline_is_read_before_the_submit(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The whole call sequence, pinned in order."""
    calls = _install_recorder(monkeypatch)

    probe_p11(_args())

    assert _kinds(calls)[:2] == ["balance", "submit"]
    assert _kinds(calls)[-1] == "ccld"


def test_the_limit_path_also_reads_the_baseline_before_the_submit(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The opt-out path shares the ordering; only the quote precedes the baseline."""
    calls = _install_recorder(monkeypatch, aspr_unit="100")

    probe_p11(_args(stock_order_type="limit"))

    assert _kinds(calls)[:3] == ["quote", "balance", "submit"]


def test_the_baseline_is_recorded_as_a_pre_submit_read(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The artifact says where the baseline was taken, so a reader need not infer it."""
    _install_recorder(monkeypatch)

    run = probe_p11(_args())

    baseline = next(o for o in run.observations if "baseline_read" in o)
    assert baseline["baseline_read"] == "before submit"
    assert baseline["baseline_holding_qty"] == 0


def test_a_fill_already_in_the_baseline_is_still_detected(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The exact shape of ``P-11-20260731T015709Z``, now resolved."""
    _install_recorder(monkeypatch, balance="pre_filled", fill="filled")

    run = probe_p11(_args(balance_timeout_s=0.1))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_NOT_REFLECTED
    assert case["baseline_holding_qty"] == case["final_holding_qty"] == 1
    assert case["execution_inquiry"]["filled"] is True
    assert case["execution_inquiry"]["filled_qty"] == 1
    assert "submit_to_balance_reflection" not in run.measurements


def test_execution_inquiry_uses_the_mock_tr_and_is_read_only(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """TR ``VTTC0081R``, GET, and gated like every other ``/trading/`` call."""
    calls = _install_recorder(monkeypatch)

    probe_p11(_args())

    inquiry = _ccld_calls(calls)[0]
    assert inquiry["method"] == "GET"
    assert inquiry["body"] == {}
    assert inquiry["headers"]["tr_id"] == _STOCK_DAILY_CCLD_TR_MOCK == "VTTC0081R"
    assert_mock_trading_tr(inquiry["headers"]["tr_id"])


def test_execution_inquiry_asks_for_all_orders_not_only_filled_ones(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """``CCLD_DVSN="00"`` (전체) is load-bearing."""
    calls = _install_recorder(monkeypatch)

    probe_p11(_args())

    params = _ccld_calls(calls)[0]["params"]
    assert params["CCLD_DVSN"] == "00"
    assert params["INQR_DVSN"] == "00"
    assert params["INQR_DVSN_3"] == "00"
    assert params["SLL_BUY_DVSN_CD"] == "00"
    assert params["PDNO"] == _SYMBOL
    assert params["INQR_STRT_DT"] == params["INQR_END_DT"]
    assert len(params["INQR_STRT_DT"]) == 8
    assert params["ODNO"] == ""


def test_execution_inquiry_records_the_row_verbatim(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The fill facts go into the artifact as the broker wrote them."""
    _install_recorder(monkeypatch)

    inquiry = probe_p11(_args()).measurements["fill_case"]["execution_inquiry"]

    assert inquiry["row"]["tot_ccld_qty"] == "1"
    assert inquiry["row"]["rmn_qty"] == "0"
    assert inquiry["row"]["cncl_yn"] == "N"
    assert inquiry["row"]["ord_tmd"] == "105710"
    assert inquiry["row"]["ord_dvsn_name"] == "시장가"
    assert "VTTC0081R" in inquiry["source"]
    assert "주문시각" in inquiry["source"]
    assert "NOT a fill timestamp" in inquiry["source"]


@pytest.mark.parametrize(
    "row_odno",
    [
        pytest.param("0000008686", id="zero_padded"),
        pytest.param("      8686", id="space_padded"),
        pytest.param("8686", id="bare"),
    ],
)
def test_odno_match_survives_either_padding(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, row_odno: str
) -> None:
    """Both encodings must match the zero-padded accept response."""
    _install_recorder(monkeypatch, row_odno=row_odno)

    case = probe_p11(_args()).measurements["fill_case"]

    assert case["execution_inquiry"]["matched_rows"] == 1
    assert case["execution_inquiry"]["filled"] is True
    assert case["case"] == _FILL_OBSERVED
    assert case["execution_inquiry"]["row_odno_encoding"]["verbatim"] == row_odno


def test_a_row_for_a_different_order_is_not_matched(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A page without our ODNO is an unanswered question, never a non-fill."""
    _install_recorder(monkeypatch, row_odno="0000009999")

    case = probe_p11(_args()).measurements["fill_case"]

    assert case["execution_inquiry"]["matched_rows"] == 0
    assert case["case"] == _FILL_UNDETERMINED
    assert "NOT evidence of a non-fill" in case["missing"]


def test_fill_case_filled_and_reflected_is_the_only_measuring_state(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    _install_recorder(monkeypatch, balance="reflects", fill="filled")

    run = probe_p11(_args())

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_OBSERVED
    assert case["baseline_holding_qty"] == 0
    assert case["final_holding_qty"] == 1
    assert case["balance_reflected"] is True
    assert case["execution_inquiry"]["filled"] is True
    assert "submit_to_balance_reflection" in run.measurements
    assert run.errors == []


def test_fill_case_filled_but_unreflected_is_an_honest_negative(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A confirmed fill the balance never showed inside the window."""
    _install_recorder(monkeypatch, balance="flat", fill="filled")

    run = probe_p11(_args(balance_timeout_s=0.1))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_NOT_REFLECTED
    assert case["balance_reflected"] is False
    assert case["execution_inquiry"]["filled"] is True
    assert "honest negative" in case["interpretation"]
    assert "submit_to_balance_reflection" not in run.measurements


def test_fill_case_not_filled_says_there_is_nothing_to_measure(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A non-fill is an ABSENT measurement, not a censored one."""
    _install_recorder(monkeypatch, balance="flat", fill="unfilled")

    run = probe_p11(_args(balance_timeout_s=0.1))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_NOT_FILLED
    assert case["execution_inquiry"]["filled"] is False
    assert case["execution_inquiry"]["filled_qty"] == 0
    assert "ABSENT" in case["interpretation"]
    assert "Widening --balance-timeout-s would change nothing" in case["interpretation"]
    assert "submit_to_balance_reflection" not in run.measurements
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


@pytest.mark.parametrize(
    ("fill", "expected_in_missing"),
    [
        pytest.param("refused", "was refused", id="rt_cd_not_zero"),
        pytest.param("no_row", "no row for ODNO", id="row_absent"),
        pytest.param("unparseable", "not a quantity", id="qty_unparseable"),
    ],
)
def test_fill_case_undetermined_names_what_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    stock_env: None,
    fill: str,
    expected_in_missing: str,
) -> None:
    """Without a fill answer the run is undetermined and says what it lacks."""
    _install_recorder(monkeypatch, balance="flat", fill=fill)

    run = probe_p11(_args(balance_timeout_s=0.1))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_UNDETERMINED
    assert case["execution_inquiry"]["filled"] is None
    assert expected_in_missing in case["missing"]
    assert "CANNOT tell" in case["interpretation"]
    assert "submit_to_balance_reflection" not in run.measurements
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


def test_an_unconfirmed_balance_rise_is_recorded_but_not_measured(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A rise with no fill confirmation cannot be attributed to our own order."""
    _install_recorder(monkeypatch, balance="reflects", fill="refused")

    run = probe_p11(_args())

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_UNDETERMINED
    assert case["balance_reflected"] is True
    assert case["balance_rise_unattributed_ms"] >= 0.0
    assert "cannot be attributed" in case["balance_rise_note"]
    assert "submit_to_balance_reflection" not in run.measurements


def test_the_censoring_wording_is_unchanged_for_the_unobserved_case(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The error text an operator greps for must survive the new verdicts."""
    _install_recorder(monkeypatch, balance="flat", fill="filled")

    run = probe_p11(_args(balance_timeout_s=0.1))

    assert run.errors == [
        "balance never reflected the order within the timeout — CENSORED. "
        "Do not record a bound from a censored trial."
    ]
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


def test_a_first_poll_reflection_is_reported_as_a_floor_not_a_measurement(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, unpaced_clock: None
) -> None:
    """The value that feeds a ``hard_maximum`` must not be the poll interval itself."""
    _install_recorder(monkeypatch, balance="reflects", fill="filled")

    run = probe_p11(_args(pace_s=1.1, poll_ms=5.0))

    floor = run.measurements["resolution_floor"]
    assert floor["poll_interval_ms_effective"] == 1100.0
    assert floor["smallest_resolvable_lag_ms"] == 1100.0
    assert floor["reflected_on_poll"] == 1
    assert floor["first_poll_reflection"] is True
    assert floor["sample_is_upper_bound"] is True
    assert "DETECTION FLOOR" in floor["do_not_report_as_measured"]
    assert "[0, 1100.0] ms" in floor["do_not_report_as_measured"]
    sample = run.measurements["submit_to_balance_reflection"]
    assert "UPPER BOUND" in sample["value_semantics"]
    assert "VTTC0081R" in sample["fill_confirmed_by"]


def test_the_resolution_floor_is_recorded_even_when_nothing_was_measured(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, unpaced_clock: None
) -> None:
    """The ceiling on what P-11 can ever say must not be visible only on success."""
    _install_recorder(monkeypatch, balance="flat", fill="unfilled")

    run = probe_p11(_args(pace_s=1.1, poll_ms=5.0, balance_timeout_s=0.0))

    floor = run.measurements["resolution_floor"]
    assert floor["poll_interval_ms_effective"] == 1100.0
    assert floor["reflected_on_poll"] is None
    assert "first_poll_reflection" not in floor
    assert "--pace-s" in floor["floor_source"]
    assert run.measurements["fill_case"]["case"] == _FILL_NOT_FILLED


def test_fill_case_records_the_effective_poll_granularity(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, unpaced_clock: None
) -> None:
    """A requested poll interval below --pace-s did not happen; record what did."""
    _install_recorder(monkeypatch, balance="flat", fill="filled")

    run = probe_p11(_args(balance_timeout_s=0.0, poll_ms=5.0, pace_s=1.1))

    assert run.measurements["fill_case"]["poll_interval_ms_effective"] == 1100.0


def test_a_later_poll_reflection_is_bracketed_rather_than_pointed(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """Reflection on poll k bounds the lag to one interval, not to a value."""
    record = probes_order._resolution_floor_record(
        poll_interval_ms=1100.0, reflected_on_poll=3, lag_ms=3300.0
    )

    assert record["bracket_ms"] == [2200.0, 3300.0]
    assert record["sample_is_upper_bound"] is True
    assert "first_poll_reflection" not in record


def test_p11_sends_a_market_order_by_default(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    calls = _install_recorder(monkeypatch)

    run = probe_p11(_args())

    body = _orders(calls)[0]["body"]
    assert body["ORD_DVSN"] == _STOCK_ORD_DVSN["market"] == "01"
    assert body["ORD_UNPR"] == _STOCK_ORD_UNPR_MARKET == "0"
    assert run.errors == []


def test_market_path_makes_no_quote_call(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """There is nothing to price, so the quote is not spent from the rate budget."""
    calls = _install_recorder(monkeypatch)

    probe_p11(_args())

    assert _quotes(calls) == []


def test_market_path_needs_no_broker_quote_unit(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The payoff of the default: no 호가단위 dependency, so no 호가단위 blocker."""
    calls = _install_recorder(monkeypatch, aspr_unit=None)

    run = probe_p11(_args())

    assert len(_orders(calls)) == 1
    assert run.errors == []


def test_market_run_records_the_tick_bypass_rather_than_omitting_it(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """``limit_price_tick`` stays present, and says why it is empty."""
    _install_recorder(monkeypatch)

    record = probe_p11(_args()).measurements["limit_price_tick"]

    assert record["applicable"] is False
    assert record["wire_value"] == _STOCK_ORD_UNPR_MARKET
    assert record["tick_size"] is None
    assert record["rounding"] is None
    assert "시장가" in record["tick_source"]
    assert "aspr_unit" in record["rounding_rationale"]


def test_limit_run_still_records_real_tick_provenance(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The opt-out path keeps the provenance the market path declares absent."""
    _install_recorder(monkeypatch, aspr_unit="100")

    record = probe_p11(_args(stock_order_type="limit")).measurements["limit_price_tick"]

    assert record.get("applicable") is not False
    assert record["tick_size"] == "100"
    assert "FHKST01010100" in record["tick_source"]


def test_the_reflection_loop_runs_on_balance_timeout_not_visibility_timeout(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """With the shared window at zero, P-11 must still poll."""
    _install_recorder(monkeypatch, balance="reflects")

    run = probe_p11(_args(visibility_timeout_s=0.0, balance_timeout_s=2.0))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_OBSERVED
    assert case["window_s"] == 2.0
    assert case["polls"] >= 1


def test_a_zero_balance_window_polls_nothing(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The converse: the loop is bounded by --balance-timeout-s alone."""
    _install_recorder(monkeypatch, balance="reflects")

    run = probe_p11(_args(visibility_timeout_s=999.0, balance_timeout_s=0.0))

    case = run.measurements["fill_case"]
    assert case["polls"] == 0
    assert case["case"] == _FILL_NOT_REFLECTED


def test_allow_fill_is_still_required(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A market order is MORE certain to fill, so the gate matters more, not less."""
    calls = _install_recorder(monkeypatch)

    run = probe_p11(_args(allow_fill=False))

    assert _orders(calls) == []
    assert run.skips[0]["what"] == "fill leg"


def test_dry_run_shows_the_market_body_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 시장가 body needs no quote, so a dry-run can show it byte for byte."""
    calls = _install_recorder(monkeypatch)

    run = probe_p11(_args(confirm=False))

    assert calls == []
    body = next(o for o in run.observations if o.get("order_body"))["order_body"]
    assert body["ORD_DVSN"] == "01"
    assert body["ORD_UNPR"] == "0"
    assert '"ORD_DVSN": "01"' in capsys.readouterr().out


def test_dry_run_states_the_baseline_ordering_and_the_fill_check(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """An operator reading the plan should see both, without running anything."""
    _install_recorder(monkeypatch)

    run = probe_p11(_args(confirm=False))

    plan = next(o for o in run.observations if o.get("would_send"))["would_send"]
    assert "baseline FIRST" in plan
    assert _STOCK_DAILY_CCLD_TR_MOCK in plan


def test_dry_run_masks_the_account_in_the_printed_body(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dry-run must not put the account number on an operator's terminal."""
    _install_recorder(monkeypatch)

    probe_p11(_args(confirm=False))

    assert _CANO not in capsys.readouterr().out


def test_futures_leg_is_still_skipped_with_its_citation(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    calls = _install_recorder(monkeypatch)

    run = probe_p11(_args(asset="futures", symbol="101S6000"))

    assert calls == []
    assert "client.py:1030-1032" in run.skips[0]["reason"]
