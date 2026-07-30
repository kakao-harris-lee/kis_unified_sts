"""Unit tests for P-11's fill path (``tools/broker_probes``).

P-11 measures a *fill*-to-balance-reflection lag, so a run that does not fill
produces nothing. It did not fill. Artifact ``P-11-20260730T002715Z.json`` was
ACCEPTED — ``rt_cd=0``, ``모의투자 매수주문이 완료 되었습니다``, ODNO ``0000008686`` —
carrying ``ORD_DVSN="00"`` (지정가) at ``ORD_UNPR="232500"``, a correctly
tick-snapped limit 10% above the 211,000 touch. The holding never moved inside the
30 s window, and an out-of-band balance read ~18 minutes later still showed the
unchanged baseline. So the censoring recorded a NON-FILL, and the probe spent a
real 모의 order on no measurement at all.

Four properties are tested here, one per way that failure could recur:

1. **The wire code.** Stock ``ORD_DVSN`` "01" is 시장가 while futures
   ``ORD_DVSN_CD`` "01" is 지정가 — the same literal with opposite meanings across
   the two asset classes. A market order that shipped the futures reading would be
   a limit order again, silently, and would reproduce the original defect exactly.
   The inversion is asserted directly, on both bodies at once.
2. **No price with a market order.** ``ORD_UNPR`` must carry the spec value and no
   snapping may be attempted; both mismatched combinations are refused rather than
   defaulted, because an omitted price must never become a market order and a
   market order must never carry a limit price.
3. **The window.** P-11 polls the balance and the pacer floors that polling at
   ``--pace-s``, so the shared 30 s ``--visibility-timeout-s`` bought only ~27
   polls. The loop is asserted to run on P-11's own ``--balance-timeout-s``.
4. **Fill versus lag.** The original artifact could not distinguish "never filled"
   from "filled, balance lagged" without a manual re-check. ``fill_case`` is
   asserted to state which case a run represents — and, when it cannot tell, to
   say so and name what would resolve it instead of yielding a bound.

No test here opens a socket: ``probes_order.http_json`` is replaced by a recorder.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any

import pytest

from tools.broker_probes import probes_order
from tools.broker_probes.common import (
    ProbeCredentials,
    ProbeError,
    ProbeRun,
    add_common_args,
)
from tools.broker_probes.probes_order import (
    _FILL_OBSERVED,
    _FILL_UNDETERMINED,
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

#: The touch the recorder quotes, so a limit-path expectation is derivable.
_LAST_PRICE = "70200"


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


class _StubAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


def _client(creds: ProbeCredentials) -> MockTradingClient:
    """A client with pacing disabled — these tests assert bodies, not intervals."""
    run = ProbeRun(probe_id="P-11", title="t", mode="live", environment="MOCK_VTS")
    return MockTradingClient(creds, _StubAuth(), run, pace_s=0.0)


def _args(**overrides: object) -> argparse.Namespace:
    """P-11 arguments at their CLI defaults, with the clocks wound down.

    ``poll_ms``/``balance_timeout_s`` are small so an undetermined run finishes in
    a fraction of a second; the assertions are on the recorded case, never on a
    wall-clock value, so no test here is timing-fragile.
    """
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


def _install_recorder(
    monkeypatch: pytest.MonkeyPatch,
    *,
    aspr_unit: str | None = "100",
    reflects: bool = True,
) -> list[dict[str, Any]]:
    """Serve a quote, an order accept, and a balance; record every call.

    Args:
        aspr_unit: The broker-reported 호가단위, or ``None`` to withhold it. The
            market path must not care either way.
        reflects: When true the second and later balance reads report the holding,
            so the reflection loop terminates on its first poll and no test waits
            on a clock. When false the holding never moves — the censored case.
    """
    calls: list[dict[str, Any]] = []
    quote: dict[str, Any] = {"stck_prpr": _LAST_PRICE}
    if aspr_unit is not None:
        quote["aspr_unit"] = aspr_unit

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
        calls.append({"url": url, "method": method, "body": json_body or {}})
        if "quotations/inquire-price" in url:
            payload: dict[str, Any] = {"rt_cd": "0", "output": quote}
        elif "trading/inquire-balance" in url:
            reads = len([c for c in calls if "trading/inquire-balance" in c["url"]])
            held = "1" if reflects and reads > 1 else "0"
            payload = {
                "rt_cd": "0",
                "output1": [{"pdno": _SYMBOL, "hldg_qty": held}],
            }
        elif "trading/order-cash" in url:
            payload = {"rt_cd": "0", "output": {"ODNO": "0000008686"}}
        else:  # pragma: no cover - an unexpected path is a test bug, not a pass
            raise AssertionError(f"unexpected probe URL: {url}")
        return 200, payload, 1.0, "{}"

    monkeypatch.setattr(probes_order, "http_json", _recorder)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )
    return calls


def _orders(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if "trading/order-cash" in c["url"]]


def _quotes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if "quotations/inquire-price" in c["url"]]


# ---------------------------------------------------------------------------
# the wire codes — official spec, and the cross-asset inversion
# ---------------------------------------------------------------------------


def test_market_body_carries_the_spec_ord_dvsn_and_no_limit_price() -> None:
    """시장가 = ORD_DVSN "01" with ORD_UNPR "0".

    Source: ``examples_llm/domestic_stock/inquire_psbl_order`` (TR
    ``v1_국내주식-007``), docstring — ``ord_dvsn (str): [필수] 주문구분
    (ex. 01 : 시장가)``. The values are read from the module's own table so this
    test pins the wire bytes, not a copy of them.
    """
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
    """The inversion, asserted on both bodies at once.

    Stock ``ORD_DVSN="01"`` is 시장가; futures ``ORD_DVSN_CD="01"`` is 지정가. Reading
    one as the other turns P-11's market order back into the resting limit that
    produced the censored artifact, and nothing on the wire would look wrong.
    """
    price = snap_to_tick(
        372.13, _futures_tick(_FUTURES_SYMBOL), side="BUY", marketable=False
    )
    client = _client(stock_creds)

    market = client.stock_order_body(_SYMBOL, 1, order_type="market")
    limit = client.futures_order_body(_FUTURES_SYMBOL, 1, price, "BUY")

    assert market["ORD_DVSN"] == limit["ORD_DVSN_CD"] == "01"
    # Same literal, opposite meaning: the futures one still carries a price.
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


# ---------------------------------------------------------------------------
# the CLI defaults
# ---------------------------------------------------------------------------


def test_cli_defaults_to_a_market_order_and_a_120s_balance_window() -> None:
    """The default is the fix; an operator gets it without passing a flag."""
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    add_order_args(parser)

    args = parser.parse_args([])

    assert args.stock_order_type == "market"
    assert args.balance_timeout_s == 120.0
    # The shared window is untouched — other probes still rely on 30s.
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


# ---------------------------------------------------------------------------
# P-11 end to end — the market default
# ---------------------------------------------------------------------------


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
    """The payoff of the default: no 호가단위 dependency, so no 호가단위 blocker.

    The limit path stops with ``ProbeError`` when the broker withholds
    ``aspr_unit`` (``test_p11_reports_a_blocked_precondition_without_a_quote_unit``
    in ``test_broker_probes_tick.py``). The market path cannot be blocked that way.
    """
    calls = _install_recorder(monkeypatch, aspr_unit=None)

    run = probe_p11(_args())

    assert len(_orders(calls)) == 1
    assert run.errors == []


def test_market_run_records_the_tick_bypass_rather_than_omitting_it(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """``limit_price_tick`` stays present, and says why it is empty.

    An absent key would have to be interpreted by a reviewer diffing artifacts
    against a limit-path run; a bypass record states the reason in place.
    """
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


# ---------------------------------------------------------------------------
# fill_case — which of the two cases a run represents
# ---------------------------------------------------------------------------


def test_fill_case_reports_a_fill_when_the_balance_reflects_it(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    _install_recorder(monkeypatch, reflects=True)

    run = probe_p11(_args())

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_OBSERVED
    assert case["baseline_holding_qty"] == 0
    assert case["final_holding_qty"] == 1
    assert "resolves_with" not in case
    assert "submit_to_balance_reflection" in run.measurements
    assert run.errors == []


def test_fill_case_is_undetermined_when_the_balance_never_moves(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The exact ambiguity that cost the 2026-07-30 run, now stated in the artifact.

    A flat balance is consistent with both a non-fill and a reflection lag beyond
    the window, so the record must claim neither.
    """
    _install_recorder(monkeypatch, reflects=False)

    run = probe_p11(_args(balance_timeout_s=0.1))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_UNDETERMINED
    assert "CANNOT tell" in case["interpretation"]
    assert case["baseline_holding_qty"] == case["final_holding_qty"] == 0
    # Names what would resolve it, without having added that path.
    assert "inquire-daily-ccld" in case["resolves_with"]
    assert "P-11-20260730T002715Z" in case["resolves_with"]


def test_an_unobserved_reflection_is_never_converted_into_a_measurement(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The censoring behaviour and its wording are unchanged."""
    _install_recorder(monkeypatch, reflects=False)

    run = probe_p11(_args(balance_timeout_s=0.1))

    assert "submit_to_balance_reflection" not in run.measurements
    assert run.errors == [
        "balance never reflected the order within the timeout — CENSORED. "
        "Do not record a bound from a censored trial."
    ]
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


def test_fill_case_records_the_effective_poll_granularity(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A requested poll interval below --pace-s did not happen; record what did."""
    _install_recorder(monkeypatch, reflects=False)

    run = probe_p11(_args(balance_timeout_s=0.1, poll_ms=5.0, pace_s=1.1))

    assert run.measurements["fill_case"]["poll_interval_ms_effective"] == 1100.0


# ---------------------------------------------------------------------------
# the balance window is P-11's own
# ---------------------------------------------------------------------------


def test_the_reflection_loop_runs_on_balance_timeout_not_visibility_timeout(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """With the shared window at zero, P-11 must still poll.

    Wired the other way round the loop body would never execute and a real fill
    would be reported as undetermined.
    """
    _install_recorder(monkeypatch, reflects=True)

    run = probe_p11(_args(visibility_timeout_s=0.0, balance_timeout_s=2.0))

    case = run.measurements["fill_case"]
    assert case["case"] == _FILL_OBSERVED
    assert case["window_s"] == 2.0
    assert case["polls"] >= 1


def test_a_zero_balance_window_polls_nothing_and_stays_undetermined(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The converse: the loop is bounded by --balance-timeout-s alone."""
    _install_recorder(monkeypatch, reflects=True)

    run = probe_p11(_args(visibility_timeout_s=999.0, balance_timeout_s=0.0))

    case = run.measurements["fill_case"]
    assert case["polls"] == 0
    assert case["case"] == _FILL_UNDETERMINED


# ---------------------------------------------------------------------------
# safety gates — unchanged
# ---------------------------------------------------------------------------


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
    """A 시장가 body needs no quote, so a dry-run can show it byte for byte.

    That is the point: the defect was an unnoticed ORD_DVSN/ORD_UNPR pair, and
    ``--confirm``'s own help text promises the dry-run prints what it would send.
    """
    calls = _install_recorder(monkeypatch)

    run = probe_p11(_args(confirm=False))

    assert calls == []
    body = next(o for o in run.observations if o.get("order_body"))["order_body"]
    assert body["ORD_DVSN"] == "01"
    assert body["ORD_UNPR"] == "0"
    assert '"ORD_DVSN": "01"' in capsys.readouterr().out


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
