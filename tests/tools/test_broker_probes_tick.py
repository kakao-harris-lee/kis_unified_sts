"""Unit tests for limit-price tick discipline (``tools/broker_probes``).

Tick rounding exists because of a lost measurement, not a hypothesis. P-5 went
out with ``UNIT_PRICE`` computed as ``round(last * 0.9, 2)`` — two decimal places,
which is not a multiple of the KOSPI200 full contract's 0.05 index-point tick —
and the broker refused the order outright: artifact
``P-5-20260730T000608Z.json``, ``rt_cd=1``,
``모의투자 주문처리가 안되었습니다(호가단위 오류)``, ``n=0``, ``NOT_MEASURED``. An
off-tick price does not degrade a trial, it deletes it.

Three properties are tested here because each one fails silently:

1. **Exactness.** A price that is off-tick by a float artifact
   (``7443 * 0.05 == 372.15000000000003``) looks right in a log and is rejected on
   the wire. The snapped value is asserted to be an exact tick multiple and the
   wire string is asserted to parse back to it.
2. **Direction.** This is the safety-relevant one. The resting probes (P-2, P-5,
   P-8, P-FQP, P-NMPR) depend on the order NOT filling, so a snap toward the touch
   narrows the ``--price-offset-pct`` gap that keeps it resting; P-11 is the mirror
   case and must stay marketable. The rule is derived inside
   :func:`~tools.broker_probes.probes_order.snap_to_tick` from ``side``/
   ``marketable`` rather than passed in, and the full truth table is asserted.
3. **Provenance.** A tick that came from a literal in the probe would keep working
   right up until the contract changed. The futures tick is therefore asserted to
   follow ``config/execution.yaml`` when that file says something else, and the
   stock tick to come from the broker's own response — with a hard refusal, not a
   guess, when the broker does not report one.

No test here opens a socket: ``probes_order.http_json`` is replaced by a recorder.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any

import pytest
import yaml

from tools.broker_probes import probes_order
from tools.broker_probes.common import ProbeCredentials, ProbeError, ProbeRun
from tools.broker_probes.probes_order import (
    MockTradingClient,
    Tick,
    _futures_tick,
    _resting_price,
    _stock_tick,
    probe_p11,
    snap_to_tick,
)

_ACCOUNT = "1234567890"

#: A symbol per registered ``symbol_prefix``, so prefix mapping is observable.
_FULL_SYMBOL = "A01609"
_MINI_SYMBOL = "A05603"


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
    """A client with pacing disabled — these tests assert prices, not intervals."""
    run = ProbeRun(probe_id="P-11", title="t", mode="live", environment="MOCK_VTS")
    return MockTradingClient(creds, _StubAuth(), run, pace_s=0.0)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "probe_id": "P-11",
        "symbol": "005930",
        "asset": "stock",
        "confirm": True,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "samples": 1,
        "margin_pct": 50.0,
        "poll_ms": 200.0,
        "gap_ms": 200.0,
        "inter_trial_s": 0.0,
        "settle_seconds": 0.0,
        "visibility_timeout_s": 30.0,
        "late_window_s": 120.0,
        "max_pages": 10,
        "allow_fill": True,
        # Mirrors the real CLI defaults (add_order_args): P-11 sends a 시장가
        # order unless a caller opts out. Every tick assertion in this file is
        # about the 지정가 path, so those tests pass stock_order_type="limit".
        "stock_order_type": "market",
        "balance_timeout_s": 120.0,
        "pace_s": 0.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _yaml_tick(spec_name: str) -> Decimal:
    """The tick this repo's config actually declares, read independently."""
    data = yaml.safe_load(probes_order._EXECUTION_CONFIG.read_text(encoding="utf-8"))
    return Decimal(str(data["futures_contract_spec"][spec_name]["tick_size_points"]))


# ---------------------------------------------------------------------------
# futures tick provenance — config/execution.yaml, never a literal
# ---------------------------------------------------------------------------


def test_futures_tick_matches_the_declared_contract_spec() -> None:
    """The resolved tick equals what the YAML says, for both products."""
    assert _futures_tick(_FULL_SYMBOL).size == _yaml_tick("kospi200_full")
    assert _futures_tick(_MINI_SYMBOL).size == _yaml_tick("kospi200_mini")


def test_futures_tick_follows_the_symbol_prefix() -> None:
    """``resolve_contract_spec`` maps by prefix, so full and mini must differ."""
    full = _futures_tick(_FULL_SYMBOL)
    mini = _futures_tick(_MINI_SYMBOL)

    assert full.size != mini.size
    # The continuous backtest code and the live front-month code are both
    # registered on the full contract (symbol_prefix "101,A01").
    assert _futures_tick("101S6000").size == full.size
    assert "kospi200_full" in full.source
    assert "kospi200_mini" in mini.source


def test_futures_tick_is_read_from_the_config_file_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Point the loader at a different contract spec; the tick must follow it.

    This is the test a literal ``0.05`` in the probe could not pass. It is also
    the regression guard for the annotation on the YAML block itself — "모든 계약
    상수는 여기서 로드 — 코드에 하드코딩 금지".
    """
    other = tmp_path / "execution.yaml"
    other.write_text(
        yaml.safe_dump(
            {
                "futures_contract_spec": {
                    "probe_fixture": {
                        "multiplier_krw_per_point": 250000,
                        "tick_size_points": 0.25,
                        "tick_value_krw": 62500,
                        "commission_rate": 0.00003,
                        "symbol_prefix": "A01",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(probes_order, "_EXECUTION_CONFIG", other)

    tick = _futures_tick(_FULL_SYMBOL)

    assert tick.size == Decimal("0.25")
    assert "probe_fixture" in tick.source


def test_unregistered_futures_symbol_is_refused() -> None:
    """Fail-closed: no fallback tick for a symbol the registry does not know."""
    with pytest.raises(ProbeError, match="no contract spec for --symbol"):
        _futures_tick("ZZ99999")


def test_futures_tick_source_names_the_config_path() -> None:
    """A reviewer must be able to re-derive the number from the artifact alone."""
    source = _futures_tick(_FULL_SYMBOL).source

    assert "config/execution.yaml::futures_contract_spec" in source
    assert "tick_size_points" in source


# ---------------------------------------------------------------------------
# stock tick provenance — the broker's own 호가단위, or a hard refusal
# ---------------------------------------------------------------------------


def test_stock_tick_uses_the_broker_reported_quote_unit() -> None:
    """``output.aspr_unit`` of TR FHKST01010100 is the only accepted source."""
    tick = _stock_tick({"aspr_unit": "50", "stck_prpr": "12345"}, "005930")

    assert tick.size == Decimal("50")
    assert "FHKST01010100" in tick.source
    assert "aspr_unit" in tick.source


@pytest.mark.parametrize(
    "output",
    [
        pytest.param({}, id="field-absent"),
        pytest.param({"aspr_unit": ""}, id="empty"),
        pytest.param({"aspr_unit": None}, id="null"),
        pytest.param({"aspr_unit": "0"}, id="zero"),
        pytest.param({"aspr_unit": "-100"}, id="negative"),
        pytest.param({"aspr_unit": "N/A"}, id="non-numeric"),
        # ORD_UNPR is int-truncated on the wire (Q-WIRE-1), so a sub-won unit
        # could not survive the encoding — refuse rather than truncate it.
        pytest.param({"aspr_unit": "0.5"}, id="fractional"),
    ],
)
def test_stock_tick_without_a_usable_quote_unit_is_blocked(
    output: dict[str, Any],
) -> None:
    """No KRX price-band table exists in this repo and none may be invented.

    The required outcome is a loud ``ProbeError`` so P-11 reports a blocked
    precondition, never an order at a guessed granularity.
    """
    with pytest.raises(ProbeError, match="호가단위"):
        _stock_tick(output, "005930")


def test_stock_tick_block_message_forbids_a_hand_tweaked_retry() -> None:
    """The error has to say what an operator must NOT do next."""
    with pytest.raises(ProbeError) as excinfo:
        _stock_tick({}, "005930")

    message = str(excinfo.value)
    assert "BLOCKED" in message
    assert "hand-picked" in message


def test_stock_quote_reads_price_and_tick_from_one_call(
    monkeypatch: pytest.MonkeyPatch, stock_creds: ProbeCredentials
) -> None:
    """One inquire-price call must yield both; a second would cost a rate slot."""
    calls = _install_stock_recorder(monkeypatch, aspr_unit="100")
    client = _client(stock_creds)

    price, tick = client.stock_quote("005930")

    assert price == pytest.approx(70200.0)
    assert tick.size == Decimal("100")
    assert len(calls) == 1


def test_stock_quote_blocks_when_the_broker_reports_no_quote_unit(
    monkeypatch: pytest.MonkeyPatch, stock_creds: ProbeCredentials
) -> None:
    """A price without a tick is not enough to place an order."""
    _install_stock_recorder(monkeypatch, aspr_unit=None)

    with pytest.raises(ProbeError, match="호가단위"):
        _client(stock_creds).stock_quote("005930")


# ---------------------------------------------------------------------------
# exactness — the wire value is a clean multiple, artifacts never escape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marketable", [False, True], ids=["resting", "marketable"])
@pytest.mark.parametrize(
    "unrounded",
    [372.13, 372.132, 306.0, 413.481, 0.07, 1234.5678],
)
def test_snapped_futures_price_is_an_exact_tick_multiple(
    unrounded: float, marketable: bool
) -> None:
    tick = _futures_tick(_FULL_SYMBOL)

    snapped = snap_to_tick(unrounded, tick, side="BUY", marketable=marketable)

    assert Decimal(snapped.wire) % tick.size == 0
    assert Decimal(snapped.wire) == Decimal(str(snapped.value))
    assert snapped.value > 0


@pytest.mark.parametrize("unrounded", [70123.0, 63180.0, 77220.4, 1050.0])
def test_snapped_stock_price_is_an_exact_whole_won_multiple(unrounded: float) -> None:
    tick = _stock_tick({"aspr_unit": "100"}, "005930")

    snapped = snap_to_tick(unrounded, tick, side="BUY", marketable=False)

    assert Decimal(snapped.wire) % tick.size == 0
    # Stock ORD_UNPR is an integer string; a "63100.0" would not mirror the
    # runtime's ``str(int(price))`` at executor.py:393.
    assert "." not in snapped.wire


def test_float_artifact_never_reaches_the_wire() -> None:
    """The concrete artifact the Decimal arithmetic exists to prevent.

    ``7443 * 0.05`` is ``372.15000000000003`` in binary floating point. Snapping
    372.13 up to a 0.05 tick lands on multiple 7443, so a float implementation
    would put that string in ``UNIT_PRICE``.
    """
    assert str(7443 * 0.05) == "372.15000000000003"  # the hazard, made explicit

    snapped = snap_to_tick(
        372.13, _futures_tick(_FULL_SYMBOL), side="BUY", marketable=True
    )

    assert snapped.wire == "372.15"
    assert Decimal(snapped.wire) == Decimal("372.15")


def test_trailing_zero_snap_keeps_the_runtime_wire_shape() -> None:
    """``372.10`` goes out as ``372.1`` — the shape ``str(price)`` produces."""
    snapped = snap_to_tick(
        372.13, _futures_tick(_FULL_SYMBOL), side="BUY", marketable=False
    )

    assert snapped.wire == "372.1"


def test_non_positive_tick_is_refused() -> None:
    with pytest.raises(ProbeError, match="tick size must be positive"):
        snap_to_tick(
            300.0, Tick(size=Decimal("0"), source="test"), side="BUY", marketable=False
        )


def test_unknown_side_is_refused() -> None:
    """Fail-closed: an unrecognised side must not default to a rounding direction."""
    with pytest.raises(ProbeError, match="unknown order side"):
        snap_to_tick(300.0, _futures_tick(_FULL_SYMBOL), side="LONG", marketable=False)


# ---------------------------------------------------------------------------
# direction — away from the touch, in every combination
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("side", "marketable", "rounding"),
    [
        ("BUY", False, "floor"),
        ("BUY", True, "ceiling"),
        ("SELL", False, "ceiling"),
        ("SELL", True, "floor"),
    ],
)
def test_rounding_direction_is_always_away_from_the_touch(
    side: str, marketable: bool, rounding: str
) -> None:
    """A resting order must move further out; a marketable one further in.

    Getting a single cell of this table backwards is the failure with a trading
    consequence: it narrows the gap a resting probe relies on to stay unfilled.
    """
    tick = _futures_tick(_FULL_SYMBOL)

    snapped = snap_to_tick(372.13, tick, side=side, marketable=marketable)

    assert snapped.rounding == rounding
    if rounding == "floor":
        assert snapped.value < 372.13
    else:
        assert snapped.value > 372.13


def test_resting_snap_only_widens_the_offset() -> None:
    """The snap cannot eat into ``--price-offset-pct``."""
    touch = 413.48
    tick = _futures_tick(_FULL_SYMBOL)
    unrounded = touch * 0.9

    snapped = snap_to_tick(unrounded, tick, side="BUY", marketable=False)

    assert snapped.value <= unrounded
    assert touch - snapped.value >= touch - unrounded


def test_marketable_snap_only_deepens_the_cross() -> None:
    """P-11's order must stay across the touch after snapping."""
    touch = 70200.0
    tick = _stock_tick({"aspr_unit": "100"}, "005930")
    unrounded = touch * 1.1

    snapped = snap_to_tick(unrounded, tick, side="BUY", marketable=True)

    assert snapped.value >= unrounded > touch


def test_resting_price_snaps_the_futures_touch_down(
    monkeypatch: pytest.MonkeyPatch, stock_creds: ProbeCredentials
) -> None:
    """``_resting_price`` end to end: quote -> tick -> snapped below the touch."""
    _install_futures_recorder(monkeypatch, futs_prpr="413.48")
    client = _client(stock_creds)

    price, side = _resting_price(client, _args(asset="futures", symbol=_FULL_SYMBOL))

    assert side == "BUY"
    assert price.rounding == "floor"
    assert price.value == pytest.approx(372.1)
    assert price.wire == "372.1"
    assert price.tick.size == _yaml_tick("kospi200_full")


def test_resting_price_snaps_the_stock_touch_down(
    monkeypatch: pytest.MonkeyPatch, stock_creds: ProbeCredentials
) -> None:
    _install_stock_recorder(monkeypatch, aspr_unit="100")
    client = _client(stock_creds)

    price, _side = _resting_price(client, _args(asset="stock", symbol="005930"))

    assert price.rounding == "floor"
    assert price.wire == "63100"


# ---------------------------------------------------------------------------
# the wire — request bodies carry the snapped string
# ---------------------------------------------------------------------------


def test_futures_order_body_carries_the_snapped_wire_string(
    stock_creds: ProbeCredentials,
) -> None:
    price = snap_to_tick(
        372.13, _futures_tick(_FULL_SYMBOL), side="BUY", marketable=False
    )

    body = _client(stock_creds).futures_order_body(_FULL_SYMBOL, 1, price, "BUY")

    assert body["UNIT_PRICE"] == price.wire == "372.1"


def test_futures_amend_body_carries_the_snapped_wire_string(
    monkeypatch: pytest.MonkeyPatch, stock_creds: ProbeCredentials
) -> None:
    """P-8's amend price needs the same discipline as the submit price."""
    calls = _install_futures_recorder(monkeypatch, futs_prpr="413.48")
    price = snap_to_tick(
        368.42, _futures_tick(_FULL_SYMBOL), side="BUY", marketable=False
    )

    _client(stock_creds).replace_futures("ODNO0001", 1, price)

    assert calls[-1]["body"]["UNIT_PRICE"] == price.wire == "368.4"


def test_cancel_body_still_sends_a_zero_price(
    monkeypatch: pytest.MonkeyPatch, stock_creds: ProbeCredentials
) -> None:
    """A cancel carries no price; the tick change must not have altered that."""
    calls = _install_futures_recorder(monkeypatch, futs_prpr="413.48")

    _client(stock_creds).cancel_futures("ODNO0001", 1)

    assert calls[-1]["body"]["UNIT_PRICE"] == "0"


def test_amend_without_a_price_is_refused(stock_creds: ProbeCredentials) -> None:
    """Fail-closed rather than sending ``UNIT_PRICE="0"`` as an amend target."""
    with pytest.raises(ProbeError, match="needs a tick-snapped price"):
        _client(stock_creds)._rvsecncl("ODNO0001", 1, dvsn="01", price=None)


# ---------------------------------------------------------------------------
# P-11 — the marketable LIMIT path (--stock-order-type limit)
#
# This is the opt-out path, not the default: P-11 defaults to 시장가 because a
# marketable limit was accepted and never filled on 모의투자
# (P-11-20260730T002715Z). The limit path is kept reachable for comparison, so its
# tick discipline still has to hold — hence stock_order_type="limit" below.
# ---------------------------------------------------------------------------


def test_p11_submits_a_tick_valid_marketable_price(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The limit order P-11 sends is above the touch AND on a valid tick."""
    calls = _install_stock_recorder(monkeypatch, aspr_unit="100", with_trading=True)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )

    run = probe_p11(_args(stock_order_type="limit"))

    order = next(c for c in calls if "trading/order-cash" in c["url"])
    assert Decimal(order["body"]["ORD_UNPR"]) % 100 == 0
    assert float(order["body"]["ORD_UNPR"]) > 70200.0
    assert run.errors == []


def test_p11_records_the_tick_and_its_source_in_the_artifact(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """A reviewer must see the price was tick-valid by construction."""
    _install_stock_recorder(monkeypatch, aspr_unit="100", with_trading=True)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )

    record = probe_p11(_args(stock_order_type="limit")).measurements["limit_price_tick"]

    assert record["tick_size"] == "100"
    assert "FHKST01010100" in record["tick_source"]
    assert record["rounding"] == "ceiling"
    assert record["wire_value"] == "77300"


def test_p11_reports_a_blocked_precondition_without_a_quote_unit(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """No 호가단위 => no order. The probe must not fall back to 1원 granularity.

    This precondition belongs to the limit path alone. The 시장가 default sends no
    price and so never asks for a tick — see
    ``test_market_path_needs_no_broker_quote_unit`` in
    ``test_broker_probes_p11_fill.py``, which is the payoff of that default.
    """
    calls = _install_stock_recorder(monkeypatch, aspr_unit=None, with_trading=True)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )

    with pytest.raises(ProbeError, match="호가단위"):
        probe_p11(_args(stock_order_type="limit"))

    assert not [c for c in calls if "trading/order-cash" in c["url"]]


# ---------------------------------------------------------------------------
# transport recorders
# ---------------------------------------------------------------------------


def _install_futures_recorder(
    monkeypatch: pytest.MonkeyPatch, *, futs_prpr: str
) -> list[dict[str, Any]]:
    """Serve a futures quote and accept order/amend/cancel; record every body."""
    calls: list[dict[str, Any]] = []

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
            payload: dict[str, Any] = {
                "rt_cd": "0",
                "output1": {"futs_prpr": futs_prpr},
            }
        else:
            payload = {"rt_cd": "0", "output": {"ODNO": f"ODNO{len(calls):04d}"}}
        return 200, payload, 1.0, "{}"

    monkeypatch.setattr(probes_order, "http_json", _recorder)
    return calls


def _install_stock_recorder(
    monkeypatch: pytest.MonkeyPatch,
    *,
    aspr_unit: str | None,
    with_trading: bool = False,
) -> list[dict[str, Any]]:
    """Serve a stock quote at 70,200원, plus the order/balance/ccld set for P-11.

    The first balance read is the baseline (flat) and every later one reports the
    holding, so P-11's reflection loop terminates on its first poll and the test
    needs no wall-clock wait. P-11 also confirms the fill through one read-only
    주식일별주문체결조회 (``VTTC0081R``), so that path is served with a filled row for
    the ODNO the order accept returns — otherwise these tick tests would fail on a
    fill the harness could not confirm rather than on anything about ticks.
    """
    calls: list[dict[str, Any]] = []
    quote: dict[str, Any] = {"stck_prpr": "70200"}
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
        elif "trading/inquire-daily-ccld" in url:
            payload = {
                "rt_cd": "0",
                "output1": [
                    {
                        "odno": "0000000001",
                        "pdno": "005930",
                        "ord_qty": "1",
                        "ord_tmd": "105710",
                        "tot_ccld_qty": "1",
                        "rmn_qty": "0",
                        "cncl_yn": "N",
                    }
                ],
            }
        elif "trading/inquire-balance" in url:
            balances = [c for c in calls if "trading/inquire-balance" in c["url"]]
            held = "0" if len(balances) == 1 else "1"
            payload = {
                "rt_cd": "0",
                "output1": [{"pdno": "005930", "hldg_qty": held}],
            }
        elif with_trading and "trading/order-cash" in url:
            payload = {"rt_cd": "0", "output": {"ODNO": "0000000001"}}
        else:  # pragma: no cover - an unexpected path is a test bug, not a pass
            raise AssertionError(f"unexpected probe URL: {url}")
        return 200, payload, 1.0, "{}"

    monkeypatch.setattr(probes_order, "http_json", _recorder)
    return calls
