"""Safety-envelope tests for the REAL-MONEY order probe (``P-R5`` / ``P-R5-PRE``).

This file is where the safety envelope is pinned. Every guard in
``tools/broker_probes/probes_real_order.py`` has a test here that fails if the
guard is deleted or weakened, because the probe it protects submits orders to a
real brokerage account with real capital at risk and there is no undo.

Three properties get special attention:

1. **The GET-only module stays GET-only.** ``probes_real.py``'s docstring makes a
   structural claim — "There is no POST helper in this module" — that the new
   order path could have quietly destroyed by living there.
   :func:`test_get_only_real_module_has_no_mutating_http_method_literal` and its
   neighbours assert the property against the module's own AST, not its prose.
2. **A refused order sends nothing.** Where a guard fires on the send path, the
   test asserts both that it raised AND that the recording transport saw no
   POST. A guard that raises after the wire would be decoration.
3. **Stage 1 cannot build an order body.** The preflight is run end to end with
   :func:`~tools.broker_probes.probes_real_order.build_real_futures_order_body`
   replaced by a bomb; it must still reach ``READY_FOR_STAGE_2``.

No test here opens a socket: ``probes_real_order.http_json`` is replaced by a
recorder, and ``KISAuthManager`` by a stub. Pacing is set to zero so the suite
does not pay the 1.1 s call interval.

Guards tested in isolation vs. at their call site
-------------------------------------------------
Time- and calendar-dependent guards (market session) are asserted directly with
injected clocks, because asserting them through the end-to-end path would make
the suite fail on weekends. The *call site* is pinned separately by replacing the
guard with one that raises and asserting the probe aborts — so deleting either
the guard or its invocation fails a test.
"""

from __future__ import annotations

import argparse
import ast
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.broker_probes import probes_order, probes_real
from tools.broker_probes import probes_real_order as pro
from tools.broker_probes.common import (
    ENV_REAL,
    ProbeCredentials,
    ProbeError,
    ProbeRun,
    SafetyViolation,
    account_fingerprint,
    assert_read_only_call,
)
from tools.broker_probes.registry import PROBES, coverage_report, get

_ACCOUNT = "1234567890"
_MINI_SYMBOL = "A05609"
_FULL_SYMBOL = "A01609"

#: A representative KOSPI200 level. Mini tick is 0.02, so 350.00 and the 5 %
#: resting price 332.50 are both exact tick multiples, and the ±8 % band below
#: brackets them. Notional = max(350, 332.5) x 50,000 x 1 = 17,500,000 KRW.
_TOUCH = 350.00
_BAND_LOW = "322.00"
_BAND_HIGH = "378.00"
_RESTING_WIRE = "332.5"
_MINI_MULTIPLIER = 50_000
_TRIAL_NOTIONAL = Decimal(17_500_000)


# ---------------------------------------------------------------------------
# fixtures / doubles
# ---------------------------------------------------------------------------


class _StubAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


class _Recorder:
    """Stand-in for :func:`common.http_json` that records and replays.

    ``responses`` maps a ``tr_id`` to either a response dict or a callable taking
    the zero-based call index for that TR, so a poll sequence can change answer
    between polls.
    """

    def __init__(
        self, responses: dict[str, Any] | None = None, *, status: int = 200
    ) -> None:
        self.responses = responses or {}
        self.status = status
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        session: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        tr_id = headers.get("tr_id", "")
        index = len([c for c in self.calls if c["tr_id"] == tr_id])
        self.calls.append(
            {
                "method": method.upper(),
                "url": url,
                "tr_id": tr_id,
                "params": params,
                "body": json_body,
            }
        )
        response = self.responses.get(tr_id, {"rt_cd": "0"})
        if callable(response):
            response = response(index)
        return self.status, response, 1.0, json.dumps(response, ensure_ascii=False)

    # -- assertions helpers ---------------------------------------------
    @property
    def posts(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["method"] == "POST"]

    def by_tr(self, tr_id: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["tr_id"] == tr_id]


@pytest.fixture
def creds() -> ProbeCredentials:
    return ProbeCredentials(
        app_key="k",
        app_secret="s",
        account_no=_ACCOUNT,
        is_real=True,
        asset="futures",
    )


@pytest.fixture
def fingerprint() -> str:
    return account_fingerprint(_ACCOUNT)


@pytest.fixture
def real_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "k")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "s")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


def _args(**overrides: Any) -> argparse.Namespace:
    """A namespace matching ``add_common_args`` + ``add_real_order_args``."""
    base: dict[str, Any] = {
        "probe_id": "P-R5",
        "confirm": True,
        "asset": "futures",
        "symbol": _MINI_SYMBOL,
        "quantity": 1,
        "price_offset_pct": pro.DEFAULT_REAL_RESTING_OFFSET_PCT,
        "samples": 1,
        "margin_pct": 50.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": "",
        pro._CONFIRM_DEST: True,
        "expect_account_fingerprint": account_fingerprint(_ACCOUNT),
        "max_notional_krw": 20_000_000.0,
        "max_cumulative_notional_krw": None,
        "stage1_artifact": "",
        "stage1_max_age_s": 1800.0,
        "min_touch_distance_pct": pro.DEFAULT_MIN_TOUCH_DISTANCE_PCT,
        "min_session_remaining_s": pro.DEFAULT_MIN_SESSION_REMAINING_S,
        "cancel_retry_attempts": 2,
        "order_class_ramp_attempts": 0,
        "order_class_ramp_step_s": 0.0,
        "order_class_ramp_floor_s": 0.0,
        "pace_s": 0.0,
        "poll_ms": 0.0,
        "visibility_timeout_s": 5.0,
        "inter_trial_s": 0.0,
        "max_pages": 1,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _tick() -> pro.Tick:
    return pro.Tick(size=Decimal("0.02"), source="test fixture")


def _plan(**overrides: Any) -> pro.RestingPlan:
    kwargs: dict[str, Any] = {
        "symbol": _MINI_SYMBOL,
        "touch": _TOUCH,
        "band_low": Decimal(_BAND_LOW),
        "band_high": Decimal(_BAND_HIGH),
        "tick": _tick(),
        "multiplier": _MINI_MULTIPLIER,
        "quantity": 1,
        "offset_pct": 5.0,
        "min_distance_pct": 3.0,
    }
    kwargs.update(overrides)
    return pro.plan_resting_order(**kwargs)


def _quote_response(
    *, touch: str = "350.00", low: str = _BAND_LOW, high: str = _BAND_HIGH
) -> dict[str, Any]:
    return {
        "rt_cd": "0",
        "output1": {
            "futs_prpr": touch,
            "futs_prdy_clpr": touch,
            "futs_sdpr": touch,
            "futs_mxpr": high,
            "futs_llam": low,
        },
    }


def _open_session_state() -> dict[str, Any]:
    return {
        "now_kst": "2026-07-31 10:00:00",
        "open": True,
        "reason": "inside the futures day session",
        "seconds_remaining": 20_700.0,
        "window_kst": "08:45-15:45",
    }


def _client(
    creds: ProbeCredentials, budget: pro.RunBudget | None = None
) -> pro.RealOrderClient:
    run = ProbeRun(probe_id="P-R5", title="t", mode="live", environment=ENV_REAL)
    return pro.RealOrderClient(
        creds,
        _StubAuth(),
        run,
        budget
        or pro.RunBudget(
            max_samples=5,
            max_notional_krw=Decimal(20_000_000),
            max_cumulative_notional_krw=Decimal(100_000_000),
        ),
        pace_s=0.0,
    )


# ===========================================================================
# 1. STRUCTURAL — the GET-only module must stay GET-only
# ===========================================================================


def _module_ast(module: Any) -> ast.Module:
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def test_get_only_real_module_has_no_mutating_http_method_literal() -> None:
    """``probes_real.py`` must keep its committed property: no POST path at all.

    Its docstring says "There is no POST helper in this module. ``_get`` is the
    only transport." The real-money order path was deliberately put in a separate
    module so that this stays true; this test is what makes "deliberately" hold
    for the next reader.
    """
    literals = {
        node.value.strip().upper()
        for node in ast.walk(_module_ast(probes_real))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "GET" in literals, "sanity: the GET literal should still be present"
    assert not literals & {"POST", "PUT", "PATCH", "DELETE"}


def test_get_only_real_module_defines_no_order_helper() -> None:
    names = {
        node.name
        for node in ast.walk(_module_ast(probes_real))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    banned = ("submit", "order", "cancel", "replace", "place", "rvsecncl")
    offenders = [n for n in names if any(t in n.lower() for t in banned)]
    assert not offenders, f"an order-shaped helper appeared in probes_real: {offenders}"


def test_get_only_real_module_allowlist_has_no_order_path_or_order_tr() -> None:
    for entry in probes_real.ALLOWLIST:
        assert "/trading/order" not in entry.path
        assert not entry.path.endswith("/order")
        # Mock/real order TRs end in U (VTTO1101U / TTTO1101U); inquiries end R.
        assert not entry.tr_id.endswith("U"), entry.tr_id


def test_get_only_real_module_allowlist_refuses_post_for_every_entry() -> None:
    for entry in probes_real.ALLOWLIST:
        url = f"https://openapi.koreainvestment.com:9443{entry.path}"
        with pytest.raises(SafetyViolation, match="read-only"):
            assert_read_only_call("POST", url, entry.tr_id, probes_real.ALLOWLIST)


def test_get_only_real_module_does_not_import_the_real_order_module() -> None:
    """A single import would put an order path in that module's graph."""
    imported: set[str] = set()
    for node in ast.walk(_module_ast(probes_real)):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not [name for name in imported if "probes_real_order" in name]


def test_real_order_module_does_not_import_the_mock_trading_client() -> None:
    """Reusing pure helpers from ``probes_order`` is fine; its client is not.

    ``MockTradingClient`` asserts the mock host, so importing it here would be
    both useless and confusing about which environment is in play.
    """
    source = Path(pro.__file__).read_text(encoding="utf-8")
    assert (
        "MockTradingClient" in source
    ), "sanity: the docstring should still mention it, to say it is NOT imported"
    imported_names: set[str] = set()
    for node in ast.walk(_module_ast(pro)):
        if isinstance(node, ast.ImportFrom):
            imported_names |= {a.name for a in node.names}
    assert "MockTradingClient" not in imported_names


# ===========================================================================
# 2. Stage-1 allowlist — the preflight cannot mutate anything
# ===========================================================================


def test_preflight_allowlist_has_no_order_path() -> None:
    for entry in pro.PREFLIGHT_ALLOWLIST:
        assert "/trading/order" not in entry.path
        assert not entry.tr_id.endswith("U"), entry.tr_id


def test_preflight_allowlist_refuses_post_for_every_entry() -> None:
    for entry in pro.PREFLIGHT_ALLOWLIST:
        url = f"https://openapi.koreainvestment.com:9443{entry.path}"
        with pytest.raises(SafetyViolation, match="read-only"):
            assert_read_only_call("POST", url, entry.tr_id, pro.PREFLIGHT_ALLOWLIST)


def test_preflight_allowlist_refuses_an_order_path_even_by_get() -> None:
    """The order endpoint is not on the list, so even a GET to it is refused."""
    url = f"https://openapi.koreainvestment.com:9443{pro._ORDER_PATH}"
    with pytest.raises(SafetyViolation, match="not on the"):
        assert_read_only_call("GET", url, "TTTO1101U", pro.PREFLIGHT_ALLOWLIST)


def test_inquire_tr_constant_is_cross_checked_against_the_audited_sot() -> None:
    assert pro.assert_inquire_tr_matches_sot() == pro._INQUIRE_TR_REAL


def test_inquire_tr_mismatch_with_the_sot_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A literal that drifts from ``tr_ids.yaml`` must fail loudly, not silently."""
    import shared.execution.tr_ids as tr_ids

    monkeypatch.setattr(
        tr_ids, "get_tr_ids", lambda: {"futures_inquire_day_real": "TTTO9999R"}
    )
    with pytest.raises(SafetyViolation, match="stale allowlist"):
        pro.assert_inquire_tr_matches_sot()


# ===========================================================================
# 3. Host / TR direction guards
# ===========================================================================


def test_mock_host_is_refused_on_the_real_probe() -> None:
    """A mock-host call would produce a MOCK number wearing a REAL_PROD label."""
    with pytest.raises(SafetyViolation, match="not the real host"):
        pro.assert_real_host("https://openapivts.koreainvestment.com:29443/uapi/x")


def test_real_host_is_admitted() -> None:
    pro.assert_real_host(f"{pro.REAL_BASE_URL}{pro._ORDER_PATH}")


def test_mock_trading_tr_is_refused_on_the_real_host() -> None:
    with pytest.raises(SafetyViolation, match="MOCK"):
        pro.assert_real_trading_tr("VTTO1101U")


def test_empty_trading_tr_is_refused() -> None:
    with pytest.raises(SafetyViolation, match="empty tr_id"):
        pro.assert_real_trading_tr("")


# ===========================================================================
# 4. The long-form authorisation flag
# ===========================================================================


def test_live_mode_without_the_long_form_flag_refuses() -> None:
    args = _args(**{pro._CONFIRM_DEST: False})
    with pytest.raises(SafetyViolation, match="i-understand-this-places-real-orders"):
        pro.assert_real_order_confirmation(args)


def test_live_mode_with_the_long_form_flag_is_admitted() -> None:
    pro.assert_real_order_confirmation(_args())


def test_dry_run_does_not_need_the_long_form_flag() -> None:
    """Without ``--confirm`` nothing is sent, so nothing needs authorising."""
    pro.assert_real_order_confirmation(
        _args(confirm=False, **{pro._CONFIRM_DEST: False})
    )


def test_a_truthy_non_true_confirm_value_is_refused() -> None:
    """``is True``, not truthiness: a stray string must not arm real orders."""
    with pytest.raises(SafetyViolation):
        pro.assert_real_order_confirmation(_args(**{pro._CONFIRM_DEST: "yes"}))


def test_the_long_form_flag_cannot_be_abbreviated() -> None:
    """argparse accepts unambiguous prefixes by default; this probe turns that off."""
    parser = argparse.ArgumentParser()
    from tools.broker_probes.common import add_common_args

    add_common_args(parser)
    pro.add_real_order_args(parser)

    assert parser.allow_abbrev is False
    with pytest.raises(SystemExit):
        parser.parse_args(["--i-understand"])
    parsed = parser.parse_args([pro.REAL_ORDER_CONFIRM_FLAG])
    assert getattr(parsed, pro._CONFIRM_DEST) is True


def test_every_shared_default_the_hard_caps_forbid_is_lowered() -> None:
    """A default invocation must be runnable, not an instant abort.

    ``add_common_args`` sets ``--samples`` to 30 for the mock probes, where a
    sample is free. Here 30 is above :data:`HARD_MAX_SAMPLES`, so leaving the
    shared default would make ``P-R5`` abort on its own default — fail-closed,
    but a confusing way to greet an operator. This test is the general form: no
    shared default may sit outside a hard cap.
    """
    parser = argparse.ArgumentParser()
    from tools.broker_probes.common import add_common_args

    add_common_args(parser)
    pro.add_real_order_args(parser)
    defaults = parser.parse_args([])

    assert defaults.samples <= pro.HARD_MAX_SAMPLES
    assert defaults.samples == pro.DEFAULT_REAL_SAMPLES
    assert defaults.quantity <= pro.HARD_MAX_QUANTITY
    assert defaults.order_class_ramp_attempts <= pro.HARD_MAX_RAMP_ATTEMPTS
    assert defaults.cancel_retry_attempts <= pro.HARD_MAX_CANCEL_RETRIES
    assert defaults.stage1_max_age_s <= pro.HARD_MAX_STAGE1_AGE_S
    assert defaults.max_pages <= pro.HARD_MAX_PAGES


def test_the_lowered_defaults_survive_budget_construction() -> None:
    """The complement of the test above, taken through the real code path."""
    parser = argparse.ArgumentParser()
    from tools.broker_probes.common import add_common_args

    add_common_args(parser)
    pro.add_real_order_args(parser)
    defaults = parser.parse_args(["--max-notional-krw", "20000000"])

    budget = pro._build_budget(defaults)

    assert (
        budget.max_samples
        == pro.DEFAULT_REAL_SAMPLES + defaults.order_class_ramp_attempts
    )


def test_the_parser_lowers_the_resting_offset_default_for_the_real_band() -> None:
    """10 % from the touch can fall outside the KOSPI200 daily band."""
    parser = argparse.ArgumentParser()
    from tools.broker_probes.common import add_common_args

    add_common_args(parser)
    pro.add_real_order_args(parser)

    assert parser.parse_args([]).price_offset_pct == pro.DEFAULT_REAL_RESTING_OFFSET_PCT
    assert pro.DEFAULT_REAL_RESTING_OFFSET_PCT < 10.0


def test_max_notional_has_no_default() -> None:
    """A defaulted cap is a cap nobody chose."""
    parser = argparse.ArgumentParser()
    from tools.broker_probes.common import add_common_args

    add_common_args(parser)
    pro.add_real_order_args(parser)

    assert parser.parse_args([]).max_notional_krw is None


# ===========================================================================
# 5. Account fingerprint
# ===========================================================================


def test_fingerprint_mismatch_refuses(fingerprint: str) -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_account_fingerprint(fingerprint, "deadbeefcafe")
    assert excinfo.value.verdict == pro.ABORT_FINGERPRINT_MISMATCH


def test_missing_expected_fingerprint_refuses(fingerprint: str) -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_account_fingerprint(fingerprint, "")
    assert excinfo.value.verdict == pro.ABORT_FINGERPRINT_MISMATCH


def test_matching_fingerprint_is_admitted_case_insensitively(fingerprint: str) -> None:
    pro.assert_account_fingerprint(fingerprint, fingerprint.upper())


def test_the_raw_account_number_never_appears_in_the_fingerprint(
    fingerprint: str,
) -> None:
    assert _ACCOUNT not in fingerprint
    assert len(fingerprint) == 12


# ===========================================================================
# 6. Market session
# ===========================================================================


def _schedule_file(tmp_path: Path, *, open_at: str, close_at: str, holidays: list[str]):
    path = tmp_path / "market_schedule.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "market_schedule": {
                    "futures": {"regular": {"open": open_at, "close": close_at}}
                },
                "holidays": holidays,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_market_closed_outside_the_window_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        pro,
        "_MARKET_SCHEDULE_CONFIG",
        _schedule_file(tmp_path, open_at="08:45", close_at="15:45", holidays=[]),
    )
    # A Wednesday, well after the close.
    when = datetime(2026, 7, 29, 17, 30, tzinfo=pro.KST)
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_market_open(when, min_remaining_s=0.0)
    assert excinfo.value.verdict == pro.ABORT_MARKET_CLOSED


def test_weekend_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        pro,
        "_MARKET_SCHEDULE_CONFIG",
        _schedule_file(tmp_path, open_at="00:00", close_at="23:59", holidays=[]),
    )
    saturday = datetime(2026, 8, 1, 10, 0, tzinfo=pro.KST)
    assert saturday.weekday() == 5
    with pytest.raises(pro.RealOrderAbort, match="weekend"):
        pro.assert_market_open(saturday, min_remaining_s=0.0)


def test_configured_holiday_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        pro,
        "_MARKET_SCHEDULE_CONFIG",
        _schedule_file(
            tmp_path, open_at="00:00", close_at="23:59", holidays=["2026-07-29"]
        ),
    )
    with pytest.raises(pro.RealOrderAbort, match="holidays"):
        pro.assert_market_open(
            datetime(2026, 7, 29, 10, 0, tzinfo=pro.KST), min_remaining_s=0.0
        )


def test_too_little_session_remaining_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A cancel is not accepted after the close, so a run that could be cut off
    by it is refused rather than started."""
    monkeypatch.setattr(
        pro,
        "_MARKET_SCHEDULE_CONFIG",
        _schedule_file(tmp_path, open_at="08:45", close_at="15:45", holidays=[]),
    )
    when = datetime(2026, 7, 29, 15, 40, tzinfo=pro.KST)  # 5 minutes left
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_market_open(when, min_remaining_s=1800.0)
    assert excinfo.value.verdict == pro.ABORT_SESSION_TOO_SHORT


def test_inside_the_session_with_room_is_admitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        pro,
        "_MARKET_SCHEDULE_CONFIG",
        _schedule_file(tmp_path, open_at="08:45", close_at="15:45", holidays=[]),
    )
    state = pro.assert_market_open(
        datetime(2026, 7, 29, 10, 0, tzinfo=pro.KST), min_remaining_s=1800.0
    )
    assert state["open"] is True
    assert state["seconds_remaining"] > 1800.0


def test_unreadable_schedule_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pro, "_MARKET_SCHEDULE_CONFIG", tmp_path / "absent.yaml")
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_market_open(
            datetime(2026, 7, 29, 10, 0, tzinfo=pro.KST), min_remaining_s=0.0
        )
    assert excinfo.value.verdict == pro.ABORT_MARKET_CLOSED


def test_there_is_no_flag_that_overrides_the_market_guard() -> None:
    """``probes_real.py`` has ``--ignore-session-window``; this probe must not.

    A read-only call outside a window yields a weaker observation. An order
    outside one yields exposure.
    """
    parser = argparse.ArgumentParser()
    pro.add_real_order_args(parser)
    options = {s for action in parser._actions for s in action.option_strings}
    assert not [o for o in options if "ignore" in o or "force" in o]


# ===========================================================================
# 7. Order-available amount
# ===========================================================================


def test_zero_order_available_refuses() -> None:
    parsed = {"rt_cd": "0", "output": {"ord_psbl_cash": "0", "ord_psbl_tota": "0"}}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_order_available(parsed["output"], parsed)
    assert excinfo.value.verdict == pro.ABORT_ORDER_AVAILABLE_ZERO


def test_unreadable_order_available_refuses() -> None:
    """Absent is not zero and is not 'probably fine' — both refuse."""
    parsed = {"rt_cd": "0", "output": {"dnca_tota": "5000000"}}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_order_available(parsed["output"], parsed)
    assert excinfo.value.verdict == pro.ABORT_ORDER_AVAILABLE_ZERO


def test_failed_deposit_query_refuses_rather_than_reading_zero() -> None:
    parsed = {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수를 초과"}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_order_available(parsed.get("output"), parsed)
    assert excinfo.value.verdict == pro.ABORT_ACCOUNT_STATE_UNREADABLE


def test_positive_order_available_is_admitted_and_recorded() -> None:
    parsed = {
        "rt_cd": "0",
        "output": {"ord_psbl_cash": "9,000,000", "ord_psbl_tota": "9500000"},
    }
    record = pro.assert_order_available(parsed["output"], parsed)
    assert record["order_available_krw"] == "9500000"
    assert record["ord_psbl_cash"] == "9000000"


# ===========================================================================
# 8. Positions and pre-existing orders
# ===========================================================================


def test_preexisting_position_refuses() -> None:
    parsed = {
        "rt_cd": "0",
        "output1": [{"shtn_pdno": _MINI_SYMBOL, "cblc_qty": "1", "lqd_psbl_qty": "1"}],
    }
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_flat_account(parsed)
    assert excinfo.value.verdict == pro.ABORT_POSITION_EXISTS


def test_unparseable_position_quantity_refuses() -> None:
    """A row whose quantity cannot be read is treated as held, not as flat."""
    parsed = {"rt_cd": "0", "output1": [{"shtn_pdno": _MINI_SYMBOL, "cblc_qty": ""}]}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_flat_account(parsed)
    assert excinfo.value.verdict == pro.ABORT_POSITION_EXISTS


def test_failed_balance_query_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_flat_account({"rt_cd": "7", "msg1": "no"})
    assert excinfo.value.verdict == pro.ABORT_ACCOUNT_STATE_UNREADABLE


def test_explicitly_empty_balance_is_flat_and_records_the_row_count() -> None:
    record = pro.assert_flat_account({"rt_cd": "0", "output1": []})
    assert record["row_count"] == 0
    assert record["held_rows"] == []


def test_zero_quantity_rows_do_not_count_as_held() -> None:
    parsed = {"rt_cd": "0", "output1": [{"shtn_pdno": _MINI_SYMBOL, "cblc_qty": "0"}]}
    assert pro.assert_flat_account(parsed)["held_rows"] == []


def test_preexisting_open_orders_refuse() -> None:
    parsed = {"rt_cd": "0", "output1": [{"odno": "0000000762", "qty": "0"}]}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_no_preexisting_open_orders(parsed, _MINI_SYMBOL)
    assert excinfo.value.verdict == pro.ABORT_OPEN_ORDERS_EXIST


def test_open_order_predicate_is_row_presence_not_remaining_quantity() -> None:
    """The campaign showed ``qty > 0`` is not a cancellability predicate."""
    parsed = {"rt_cd": "0", "output1": [{"odno": "0000000762", "qty": "0"}]}
    with pytest.raises(pro.RealOrderAbort):
        pro.assert_no_preexisting_open_orders(parsed, _MINI_SYMBOL)


def test_failed_open_order_query_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_no_preexisting_open_orders({"rt_cd": "1"}, _MINI_SYMBOL)
    assert excinfo.value.verdict == pro.ABORT_ACCOUNT_STATE_UNREADABLE


# ===========================================================================
# 9. Contract resolution — smallest only, multiplier read not assumed
# ===========================================================================


def test_non_smallest_contract_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.resolve_smallest_contract(_FULL_SYMBOL)
    assert excinfo.value.verdict == pro.ABORT_NOT_SMALLEST_CONTRACT


def test_smallest_contract_resolves_and_reports_the_ratio() -> None:
    spec, tick, record = pro.resolve_smallest_contract(_MINI_SYMBOL)
    declared = yaml.safe_load(
        probes_order._EXECUTION_CONFIG.read_text(encoding="utf-8")
    )["futures_contract_spec"]
    assert spec.multiplier_krw_per_point == (
        declared["kospi200_mini"]["multiplier_krw_per_point"]
    )
    assert tick.size == Decimal(str(declared["kospi200_mini"]["tick_size_points"]))
    # The campaign's 1/5 claim, recorded as an observation rather than asserted
    # as a constant: the ratio is derived from the registry, not hardcoded.
    assert record["multiplier_ratio_to_largest"] == "50000/250000"


def test_the_multiplier_is_read_from_config_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Point the registry at a different spec; the multiplier must follow it."""
    other = tmp_path / "execution.yaml"
    other.write_text(
        yaml.safe_dump(
            {
                "futures_contract_spec": {
                    "probe_fixture": {
                        "multiplier_krw_per_point": 7,
                        "tick_size_points": 0.5,
                        "tick_value_krw": 3,
                        "commission_rate": 0.0,
                        "symbol_prefix": "A05",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(probes_order, "_EXECUTION_CONFIG", other)

    spec, tick, record = pro.resolve_smallest_contract(_MINI_SYMBOL)

    assert spec.multiplier_krw_per_point == 7
    assert tick.size == Decimal("0.5")
    assert "probe_fixture" in record["source"]


def test_unregistered_symbol_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.resolve_smallest_contract("ZZZ999")
    assert excinfo.value.verdict == pro.ABORT_INSTRUMENT_UNRESOLVED


# ===========================================================================
# 10. Resting price — distance, tick, band
# ===========================================================================


def test_the_happy_plan_is_a_tick_multiple_clear_of_the_touch() -> None:
    plan = _plan()
    assert plan.price.wire == _RESTING_WIRE
    assert Decimal(plan.price.wire) % _tick().size == 0
    assert plan.notional_krw == _TRIAL_NOTIONAL
    assert plan.describe()["distance_pct_from_touch"] == 5.0


def test_price_too_close_to_the_touch_refuses() -> None:
    """The floor is checked against a number that is NOT the offset that produced
    the price, so lowering the offset does not silently lower the floor."""
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _plan(offset_pct=0.5, min_distance_pct=3.0)
    assert excinfo.value.verdict == pro.ABORT_PRICE_TOO_CLOSE


def test_non_tick_price_refuses() -> None:
    price = probes_order.TickPrice(
        value=332.51,
        wire="332.51",
        tick=_tick(),
        unrounded=332.51,
        rounding="floor",
    )
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_resting_plan_price(
            price=price,
            touch=_TOUCH,
            tick=_tick(),
            band_low=Decimal(_BAND_LOW),
            band_high=Decimal(_BAND_HIGH),
            min_distance_pct=3.0,
        )
    assert excinfo.value.verdict == pro.ABORT_PRICE_OFF_TICK


def test_price_outside_the_daily_band_refuses() -> None:
    """A limit outside the band is rejected outright — the order is spent on nothing."""
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _plan(offset_pct=20.0, min_distance_pct=3.0)
    assert excinfo.value.verdict == pro.ABORT_PRICE_OUTSIDE_BAND


def test_unreadable_band_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _plan(band_low=None)
    assert excinfo.value.verdict == pro.ABORT_PRICE_BAND_UNREADABLE


def test_unreadable_touch_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _plan(touch=0.0)
    assert excinfo.value.verdict == pro.ABORT_TOUCH_UNREADABLE


def test_the_snap_moves_away_from_the_touch_never_toward_it() -> None:
    """A snap toward the touch would narrow the gap that keeps the order resting."""
    plan = _plan(touch=350.01)
    assert plan.price.value <= 350.01 * (1 - 0.05)
    assert plan.price.rounding == "floor"


# ===========================================================================
# 11. Caps
# ===========================================================================


def _budget(**overrides: Any) -> pro.RunBudget:
    kwargs: dict[str, Any] = {
        "max_samples": 3,
        "max_notional_krw": Decimal(20_000_000),
        "max_cumulative_notional_krw": Decimal(40_000_000),
    }
    kwargs.update(overrides)
    return pro.RunBudget(**kwargs)


def test_notional_cap_exceeded_refuses() -> None:
    budget = _budget(max_notional_krw=Decimal(1_000_000))
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        budget.authorize(_plan())
    assert excinfo.value.verdict == pro.ABORT_NOTIONAL_CAP
    assert budget.orders_sent == 0


def test_cumulative_notional_cap_is_enforced_across_orders() -> None:
    budget = _budget(max_samples=10, max_cumulative_notional_krw=Decimal(30_000_000))
    plan = _plan()
    budget.authorize(plan)  # 17.5m
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        budget.authorize(plan)  # would reach 35m
    assert excinfo.value.verdict == pro.ABORT_CUMULATIVE_NOTIONAL_CAP
    assert budget.orders_sent == 1


def test_sample_cap_is_enforced() -> None:
    budget = _budget(max_samples=1, max_cumulative_notional_krw=Decimal(999_000_000))
    plan = _plan()
    budget.authorize(plan)
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        budget.authorize(plan)
    assert excinfo.value.verdict == pro.ABORT_SAMPLE_CAP


def test_quantity_above_the_hard_cap_refuses() -> None:
    budget = _budget()
    plan = _plan(quantity=pro.HARD_MAX_QUANTITY + 1)
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        budget.authorize(plan)
    assert excinfo.value.verdict == pro.ABORT_QUANTITY_CAP


def test_samples_above_the_hard_cap_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro._build_budget(_args(samples=pro.HARD_MAX_SAMPLES + 1))
    assert excinfo.value.verdict == pro.ABORT_SAMPLE_CAP


def test_ramp_attempts_above_the_hard_cap_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort):
        pro._build_budget(
            _args(order_class_ramp_attempts=pro.HARD_MAX_RAMP_ATTEMPTS + 1)
        )


def test_missing_max_notional_refuses() -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro._build_budget(_args(max_notional_krw=None))
    assert excinfo.value.verdict == pro.ABORT_NOTIONAL_CAP


def test_the_default_cumulative_cap_covers_trials_plus_ramp() -> None:
    budget = pro._build_budget(
        _args(samples=2, order_class_ramp_attempts=1, max_notional_krw=10.0)
    )
    assert budget.max_samples == 3
    assert budget.max_cumulative_notional_krw == Decimal(30)


def test_cumulative_notional_is_documented_as_turnover_not_exposure() -> None:
    text = _budget().describe()["cumulative_is_turnover_not_exposure"]
    assert "TURNOVER" in text and "one order is live at a time" in text


# ===========================================================================
# 12. The send path — a refused order sends NOTHING
# ===========================================================================


def test_over_cap_notional_sends_no_order(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds, _budget(max_notional_krw=Decimal(1)))

    with pytest.raises(pro.RealOrderAbort):
        client.submit_resting(_plan())

    assert recorder.posts == [], "a capped order must never reach the wire"


def test_a_price_that_fails_the_floor_sends_no_order(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    """The send path re-takes the price assertions, so a stale plan cannot slip
    through when the touch has moved."""
    recorder = _Recorder()
    monkeypatch.setattr(pro, "http_json", recorder)
    plan = _plan()
    # The touch rallied to just above the resting price: the gap is gone.
    moved = pro.RestingPlan(
        symbol=plan.symbol,
        side=plan.side,
        quantity=plan.quantity,
        price=plan.price,
        touch=333.0,
        band_low=plan.band_low,
        band_high=plan.band_high,
        min_distance_pct=plan.min_distance_pct,
        multiplier_krw_per_point=plan.multiplier_krw_per_point,
        notional_krw=plan.notional_krw,
    )
    client = _client(creds)

    with pytest.raises(pro.RealOrderAbort) as excinfo:
        client.submit_resting(moved)

    assert excinfo.value.verdict == pro.ABORT_PRICE_TOO_CLOSE
    assert recorder.posts == []


def test_an_accepted_order_carries_the_runtime_body_shape_and_the_real_tr(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {"TTTO1101U": {"rt_cd": "0", "output": {"ODNO": "0000000762"}}}
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    odno, parsed, status = client.submit_resting(_plan())

    assert (odno, status) == ("0000000762", 200)
    assert parsed["rt_cd"] == "0"
    sent = recorder.posts[0]
    assert sent["tr_id"] == "TTTO1101U"
    assert sent["url"].endswith(pro._ORDER_PATH)
    assert sent["body"]["ORD_DVSN_CD"] == "01"  # 지정가
    assert sent["body"]["SLL_BUY_DVSN_CD"] == "02"  # BUY
    assert sent["body"]["UNIT_PRICE"] == _RESTING_WIRE
    assert sent["body"]["ORD_QTY"] == "1"
    # The [필수] quote fields are explicit, never blank: P-NMPR's finding that a
    # blank behaves as 01 was a MOCK finding and does not transfer to 실전.
    assert sent["body"]["NMPR_TYPE_CD"] == "01"
    assert sent["body"]["KRX_NMPR_CNDT_CD"] == "0"


def test_a_rejected_order_yields_no_odno(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder({"TTTO1101U": {"rt_cd": "1", "msg1": "호가단위 오류"}})
    monkeypatch.setattr(pro, "http_json", recorder)

    odno, _parsed, _status = _client(creds).submit_resting(_plan())

    assert odno is None


def test_the_order_body_is_the_only_one_in_the_package() -> None:
    """Grep-level canary: no other module may build a real futures order body."""
    package = Path(pro.__file__).parent
    offenders = []
    for path in sorted(package.glob("*.py")):
        if path.name == "probes_real_order.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "futures_order_day_real" in source:
            offenders.append(path.name)
    assert offenders == [], f"a real futures order TR appeared elsewhere: {offenders}"


# ===========================================================================
# 13. Fill detection — a fill is a safety event, not a data point
# ===========================================================================


def test_a_full_fill_aborts_the_run() -> None:
    row = {"odno": "0000000762", "tot_ccld_qty": "1", "qty": "0", "ord_qty": "1"}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_no_fill(row, context="test")
    assert excinfo.value.verdict == pro.ABORT_FILL_DETECTED


def test_a_partial_fill_aborts_the_run() -> None:
    row = {"odno": "0000000762", "tot_ccld_qty": "1", "qty": "4", "ord_qty": "5"}
    state, _record = pro.classify_fill(row)
    assert state == pro.FILL_PARTIAL_OR_FULL
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_no_fill(row, context="test")
    assert excinfo.value.verdict == pro.ABORT_FILL_DETECTED


def test_an_unreadable_fill_quantity_aborts_rather_than_reading_no_fill() -> None:
    """'We could not tell' must not resolve to 'it did not fill' on real money."""
    row = {"odno": "0000000762", "qty": "1", "ord_qty": "1"}
    state, _record = pro.classify_fill(row)
    assert state == pro.FILL_UNKNOWN
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro.assert_no_fill(row, context="test")
    assert excinfo.value.verdict == pro.ABORT_FILL_STATE_UNKNOWN


def test_an_explicit_zero_fill_is_admitted() -> None:
    row = {"odno": "0000000762", "tot_ccld_qty": "0", "qty": "1", "ord_qty": "1"}
    assert pro.classify_fill(row)[0] == pro.FILL_NONE
    assert pro.assert_no_fill(row, context="test")["tot_ccld_qty"] == 0


def test_a_detected_fill_stops_the_trial_loop_before_another_order(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO1101U": {"rt_cd": "0", "output": {"ODNO": "0000000762"}},
            "TTTO5201R": {
                "rt_cd": "0",
                "output1": [{"odno": "        762", "tot_ccld_qty": "1", "qty": "0"}],
            },
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)
    args = _args(samples=3)
    unresolved: list[str] = []

    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro._one_trial(client.run, args, client, _plan(), 0, unresolved)

    assert excinfo.value.verdict == pro.ABORT_FILL_DETECTED
    assert len(recorder.by_tr("TTTO1101U")) == 1, "no second order after a fill"
    assert unresolved == ["0000000762"], "the order is left registered for the sweep"


# ===========================================================================
# 14. Cancel — bounded retry, verified, and abort on failure
# ===========================================================================


def test_a_cancel_failure_aborts_the_run_and_places_no_further_order(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO1101U": {"rt_cd": "0", "output": {"ODNO": "0000000762"}},
            "TTTO5201R": {
                "rt_cd": "0",
                "output1": [{"odno": "        762", "tot_ccld_qty": "0", "qty": "1"}],
            },
            "TTTO1103U": {"rt_cd": "1", "msg1": "초당 거래건수를 초과하였습니다"},
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)
    args = _args(samples=3, cancel_retry_attempts=2)
    unresolved: list[str] = []

    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro._one_trial(client.run, args, client, _plan(), 0, unresolved)

    assert excinfo.value.verdict == pro.ABORT_CANCEL_FAILED
    assert "0000000762" in str(excinfo.value)
    assert "MAY STILL BE RESTING" in str(excinfo.value)
    assert len(recorder.by_tr("TTTO1103U")) == 2, "retries are bounded by the flag"
    assert len(recorder.by_tr("TTTO1101U")) == 1, "no order after a failed cancel"
    assert unresolved == ["0000000762"]


def test_cancel_retries_are_capped_by_the_hard_ceiling(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder({"TTTO1103U": {"rt_cd": "1", "msg1": "no"}})
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)
    args = _args(cancel_retry_attempts=99)

    with pytest.raises(pro.RealOrderAbort):
        pro._cancel_and_verify(client.run, args, client, _plan(), "762", 0, [])

    assert len(recorder.by_tr("TTTO1103U")) == pro.HARD_MAX_CANCEL_RETRIES


def test_a_successful_cancel_is_verified_and_deregisters_the_order(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO1103U": {"rt_cd": "0", "msg1": "취소 완료"},
            "TTTO5201R": {
                "rt_cd": "0",
                "output1": [{"odno": "        762", "tot_ccld_qty": "0", "qty": "0"}],
            },
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)
    unresolved = ["0000000762"]

    pro._cancel_and_verify(
        client.run, _args(), client, _plan(), "0000000762", 0, unresolved
    )

    assert unresolved == []
    # Verbatim zero-padded ODNO on the wire — canonicalisation is for comparison
    # only and must never reach a body (harness defect #3).
    assert recorder.by_tr("TTTO1103U")[0]["body"]["ORGN_ODNO"] == "0000000762"
    assert any("cancel_verified" in o for o in client.run.observations)


def test_a_fill_found_during_cancel_verification_aborts(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO1103U": {"rt_cd": "0"},
            "TTTO5201R": {
                "rt_cd": "0",
                "output1": [{"odno": "        762", "tot_ccld_qty": "1", "qty": "0"}],
            },
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro._cancel_and_verify(
            client.run, _args(), client, _plan(), "0000000762", 0, ["0000000762"]
        )

    assert excinfo.value.verdict == pro.ABORT_FILL_DETECTED


# ===========================================================================
# 15. Latency measurement — same computation as mock P-5
# ===========================================================================


def test_the_visibility_measurement_matches_a_space_padded_query_row(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    """Harness defect #3: the accept zero-pads and the row space-pads.

    A raw strip-and-compare asks ``"762" == "0000000762"`` and censors every
    trial, so both sides go through ``odno_key``.
    """
    recorder = _Recorder(
        {
            "TTTO1101U": {"rt_cd": "0", "output": {"ODNO": "0000000762"}},
            "TTTO5201R": {
                "rt_cd": "0",
                "output1": [{"odno": "        762", "tot_ccld_qty": "0", "qty": "1"}],
            },
            "TTTO1103U": {"rt_cd": "0"},
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    outcome = pro._one_trial(client.run, _args(), client, _plan(), 0, [])

    assert outcome.censored is False
    assert outcome.latency_ms is not None and outcome.latency_ms >= 0.0
    assert outcome.polls == 1


def test_a_never_visible_order_is_censored_not_dropped(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO1101U": {"rt_cd": "0", "output": {"ODNO": "0000000762"}},
            "TTTO5201R": {"rt_cd": "0", "output1": []},
            "TTTO1103U": {"rt_cd": "0"},
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    outcome = pro._one_trial(
        client.run, _args(visibility_timeout_s=0.05), client, _plan(), 0, []
    )

    assert outcome.censored is True
    assert outcome.latency_ms is None
    assert any("CENSORED" in e for e in client.run.errors)


def test_a_rejected_submit_stops_the_run_rather_than_retrying(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder({"TTTO1101U": {"rt_cd": "1", "msg1": "호가단위 오류"}})
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    with pytest.raises(pro.RealOrderAbort) as excinfo:
        pro._one_trial(client.run, _args(), client, _plan(), 0, [])

    assert excinfo.value.verdict == pro.ABORT_SUBMIT_REJECTED
    assert len(recorder.by_tr("TTTO1101U")) == 1


# ===========================================================================
# 16. Stage-1 artifact — required, fresh, matching, and still re-validated
# ===========================================================================


def _stage1_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_id": "P-R5-PRE-20260731T010000Z",
        "probe_id": "P-R5-PRE",
        "mode": "live",
        "environment": ENV_REAL,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "credentials": {"account_fingerprint": account_fingerprint(_ACCOUNT)},
        "measurements": {
            "preflight_verdict": pro.VERDICT_PREFLIGHT_READY,
            "resting_plan": {"symbol": _MINI_SYMBOL},
        },
        "errors": [],
    }
    payload.update(overrides)
    return payload


def _write_stage1(tmp_path: Path, payload: dict[str, Any]) -> str:
    path = tmp_path / "stage1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _load(path: str, **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "max_age_s": 1800.0,
        "expect_fingerprint": account_fingerprint(_ACCOUNT),
        "symbol": _MINI_SYMBOL,
    }
    kwargs.update(overrides)
    return pro.load_stage1_artifact(path, **kwargs)


def test_a_fresh_ready_artifact_is_accepted(tmp_path: Path) -> None:
    record = _load(_write_stage1(tmp_path, _stage1_payload()))
    assert record["preflight_verdict"] == pro.VERDICT_PREFLIGHT_READY
    assert "re-taken live" in record["revalidation_note"]


def test_a_missing_stage1_path_refuses() -> None:
    """An empty path is refused BY NAME, not by falling into a read failure.

    Dropping the explicit-empty check still refuses — ``Path("")`` resolves to a
    directory and the read raises — so the message is what the test pins. The
    operator needs to be told which flag is missing, not handed
    ``could not read stage-1 artifact .``.
    """
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load("")
    assert excinfo.value.verdict == pro.ABORT_STAGE1_MISSING
    assert "--stage1-artifact is required" in str(excinfo.value)


def test_an_unreadable_stage1_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load(str(tmp_path / "absent.json"))
    assert excinfo.value.verdict == pro.ABORT_STAGE1_MISSING


def test_a_stale_stage1_artifact_refuses(tmp_path: Path) -> None:
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load(_write_stage1(tmp_path, _stage1_payload(finished_at_utc=old)))
    assert excinfo.value.verdict == pro.ABORT_STAGE1_STALE


def test_an_undatable_stage1_artifact_refuses(tmp_path: Path) -> None:
    payload = _stage1_payload()
    payload.pop("finished_at_utc")
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load(_write_stage1(tmp_path, payload))
    assert excinfo.value.verdict == pro.ABORT_STAGE1_STALE


def test_a_non_ready_verdict_refuses(tmp_path: Path) -> None:
    payload = _stage1_payload()
    payload["measurements"]["preflight_verdict"] = pro.ABORT_POSITION_EXISTS
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load(_write_stage1(tmp_path, payload))
    assert excinfo.value.verdict == pro.ABORT_STAGE1_UNUSABLE


def test_a_dry_run_artifact_refuses(tmp_path: Path) -> None:
    """A dry run observed nothing about the account."""
    with pytest.raises(pro.RealOrderAbort, match="dry run"):
        _load(_write_stage1(tmp_path, _stage1_payload(mode="dry-run")))


def test_an_artifact_with_errors_refuses(tmp_path: Path) -> None:
    with pytest.raises(pro.RealOrderAbort, match="recorded errors"):
        _load(_write_stage1(tmp_path, _stage1_payload(errors=["boom"])))


def test_an_artifact_from_another_account_refuses(tmp_path: Path) -> None:
    payload = _stage1_payload(credentials={"account_fingerprint": "deadbeefcafe"})
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load(_write_stage1(tmp_path, payload))
    assert excinfo.value.verdict == pro.ABORT_STAGE1_UNUSABLE


def test_an_artifact_for_another_symbol_refuses(tmp_path: Path) -> None:
    payload = _stage1_payload()
    payload["measurements"]["resting_plan"] = {"symbol": _FULL_SYMBOL}
    with pytest.raises(pro.RealOrderAbort) as excinfo:
        _load(_write_stage1(tmp_path, payload))
    assert excinfo.value.verdict == pro.ABORT_STAGE1_UNUSABLE


def test_an_artifact_from_the_wrong_probe_refuses(tmp_path: Path) -> None:
    with pytest.raises(pro.RealOrderAbort, match="probe_id"):
        _load(_write_stage1(tmp_path, _stage1_payload(probe_id="P-5")))


def test_the_stage1_age_flag_cannot_exceed_the_hard_cap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_env: None
) -> None:
    """``--stage1-max-age-s 99999`` must still refuse a 2-hour-old artifact."""
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    path = _write_stage1(tmp_path, _stage1_payload(finished_at_utc=old))
    monkeypatch.setattr(pro, "http_json", _Recorder())

    run = pro.probe_real_order(_args(stage1_artifact=path, stage1_max_age_s=99_999.0))

    assert run.measurements["verdict"] == pro.ABORT_STAGE1_STALE


# ===========================================================================
# 17. Stage 1 end to end — and it never constructs an order body
# ===========================================================================


def _preflight_responses() -> dict[str, Any]:
    return {
        "CTRP6550R": {
            "rt_cd": "0",
            "output": {"ord_psbl_cash": "9000000", "ord_psbl_tota": "9500000"},
        },
        "CTFO6118R": {"rt_cd": "0", "output1": [], "output2": {}},
        "FHMIF10000000": _quote_response(),
        "TTTO5105R": {"rt_cd": "0", "output": {"ord_psbl_qty": "2"}},
        "TTTO5201R": {"rt_cd": "0", "output1": []},
    }


@pytest.fixture
def preflight_env(monkeypatch: pytest.MonkeyPatch, real_env: None, tmp_path: Path):
    """Wire stage 1 to a recorder, a stub auth manager, and an open session.

    The session guard is stubbed here (and asserted directly in §6) so the suite
    does not fail on weekends. Its call site is pinned by
    :func:`test_stage1_aborts_when_the_market_guard_fires`.
    """
    recorder = _Recorder(_preflight_responses())
    monkeypatch.setattr(pro, "http_json", recorder)
    monkeypatch.setattr(pro, "market_session_state", lambda now: _open_session_state())
    import shared.kis.auth as kis_auth

    monkeypatch.setattr(
        kis_auth, "KISAuthManager", lambda cfg, use_singleton=False: _StubAuth()
    )
    return recorder


def _preflight_args(tmp_path: Path, **overrides: Any) -> argparse.Namespace:
    return _args(
        probe_id="P-R5-PRE", token_cache_dir=str(tmp_path / "tok"), **overrides
    )


def test_stage1_reaches_ready_and_issues_only_gets(
    preflight_env: _Recorder, tmp_path: Path
) -> None:
    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    assert run.measurements["preflight_verdict"] == pro.VERDICT_PREFLIGHT_READY
    assert run.errors == []
    assert preflight_env.posts == []
    assert {c["method"] for c in preflight_env.calls} == {"GET"}
    assert len(preflight_env.calls) == 5


def test_stage1_never_constructs_an_order_body(
    monkeypatch: pytest.MonkeyPatch, preflight_env: _Recorder, tmp_path: Path
) -> None:
    """Replace the order-body builder with a bomb; stage 1 must still complete."""

    def _bomb(**_kwargs: Any) -> dict[str, str]:
        raise AssertionError("stage 1 built an order body")

    monkeypatch.setattr(pro, "build_real_futures_order_body", _bomb)

    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    assert run.measurements["preflight_verdict"] == pro.VERDICT_PREFLIGHT_READY


def test_stage1_records_the_fingerprint_but_never_the_raw_account(
    preflight_env: _Recorder, tmp_path: Path
) -> None:
    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    blob = json.dumps(run.to_dict(get("P-R5-PRE")), ensure_ascii=False)
    assert account_fingerprint(_ACCOUNT) in blob
    assert _ACCOUNT not in blob


def test_stage1_aborts_and_still_writes_an_artifact(
    preflight_env: _Recorder, tmp_path: Path
) -> None:
    """An abort is a result: the artifact explains it instead of being empty."""
    run = pro.probe_real_preflight(
        _preflight_args(tmp_path, expect_account_fingerprint="deadbeefcafe")
    )

    payload = run.to_dict(get("P-R5-PRE"))
    assert payload["measurements"]["preflight_verdict"] == (
        pro.ABORT_FINGERPRINT_MISMATCH
    )
    assert payload["errors"], "the abort reason must be recorded"
    assert payload["provenance_class"] == "NOT_MEASURED"
    assert payload["approval_status"] == "UNAPPROVED_CANDIDATE"
    assert "abort_is_a_result" in payload["measurements"]


def test_stage1_aborts_when_the_market_guard_fires(
    monkeypatch: pytest.MonkeyPatch, preflight_env: _Recorder, tmp_path: Path
) -> None:
    """Pins the CALL SITE: deleting the guard's invocation fails here."""
    monkeypatch.setattr(
        pro, "market_session_state", lambda now: {"open": False, "reason": "closed"}
    )

    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    assert run.measurements["preflight_verdict"] == pro.ABORT_MARKET_CLOSED
    assert preflight_env.calls == [], "no call is made once the market guard fires"


def test_stage1_aborts_on_a_pre_existing_position(
    monkeypatch: pytest.MonkeyPatch, preflight_env: _Recorder, tmp_path: Path
) -> None:
    responses = _preflight_responses()
    responses["CTFO6118R"] = {
        "rt_cd": "0",
        "output1": [{"shtn_pdno": _MINI_SYMBOL, "cblc_qty": "1"}],
    }
    preflight_env.responses = responses

    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    assert run.measurements["preflight_verdict"] == pro.ABORT_POSITION_EXISTS


def test_stage1_aborts_on_zero_order_available(
    preflight_env: _Recorder, tmp_path: Path
) -> None:
    preflight_env.responses = dict(
        _preflight_responses(),
        CTRP6550R={"rt_cd": "0", "output": {"ord_psbl_tota": "0"}},
    )

    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    assert run.measurements["preflight_verdict"] == pro.ABORT_ORDER_AVAILABLE_ZERO


def test_stage1_records_the_tick_corroboration_and_why_it_is_needed(
    preflight_env: _Recorder, tmp_path: Path
) -> None:
    """The futures 시세 TR reports no 호가단위, so the tick is corroborated instead."""
    run = pro.probe_real_preflight(_preflight_args(tmp_path))

    corroboration = run.measurements["tick_corroboration"]
    assert corroboration["corroborated"] is True
    assert corroboration["non_multiples"] == []
    assert (
        "no 호가단위 field"
        in run.measurements["tick_provenance"]["why_not_broker_reported"]
    )


def test_a_broker_price_off_the_registered_tick_is_reported_as_a_contradiction() -> (
    None
):
    record = pro._corroborate_tick({"futs_prpr": "350.013"}, _tick(), ("futs_prpr",))
    assert record["corroborated"] is False
    assert record["non_multiples"] == ["futs_prpr=350.013"]


# ===========================================================================
# 18. Stage 2 — dry run, and aborts produce artifacts
# ===========================================================================


def test_stage2_dry_run_sends_nothing_and_lists_its_preconditions(
    monkeypatch: pytest.MonkeyPatch, real_env: None
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(pro, "http_json", recorder)

    run = pro.probe_real_order(_args(confirm=False, **{pro._CONFIRM_DEST: False}))

    assert recorder.calls == []
    assert run.mode == "dry-run"
    required = next(
        o["live_mode_requires"] for o in run.observations if "live_mode_requires" in o
    )
    assert pro.REAL_ORDER_CONFIRM_FLAG in required
    assert "--stage1-artifact <path to a fresh READY P-R5-PRE artifact>" in required


def test_stage2_refuses_live_without_the_long_form_flag_before_any_setup(
    monkeypatch: pytest.MonkeyPatch, real_env: None
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(pro, "http_json", recorder)

    with pytest.raises(SafetyViolation):
        pro.probe_real_order(_args(**{pro._CONFIRM_DEST: False}))

    assert recorder.calls == []


def test_stage2_abort_artifact_is_not_measured_and_explains_itself(
    monkeypatch: pytest.MonkeyPatch, real_env: None
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(pro, "http_json", recorder)

    run = pro.probe_real_order(_args(stage1_artifact=""))

    payload = run.to_dict(get("P-R5"))
    assert payload["measurements"]["verdict"] == pro.ABORT_STAGE1_MISSING
    assert payload["provenance_class"] == "NOT_MEASURED"
    assert payload["approval_status"] == "UNAPPROVED_CANDIDATE"
    assert recorder.calls == []


def test_stage2_records_the_environment_scope_note(
    monkeypatch: pytest.MonkeyPatch, real_env: None
) -> None:
    monkeypatch.setattr(pro, "http_json", _Recorder())

    run = pro.probe_real_order(_args(stage1_artifact=""))

    scope = run.measurements["scope_and_transfer"]
    assert scope["environment"] == ENV_REAL
    assert "both ways" in scope["does_not_transfer_to_mock"]


def test_every_exit_path_records_the_scope_note(
    monkeypatch: pytest.MonkeyPatch,
    preflight_env: _Recorder,
    real_env: None,
    tmp_path: Path,
) -> None:
    """Including the dry runs, which an early ``return`` used to skip.

    An artifact without the both-ways inheritance prohibition on it is an
    artifact a reader could cite into the wrong environment's declaration.
    """
    dry_stage2 = pro.probe_real_order(
        _args(confirm=False, **{pro._CONFIRM_DEST: False})
    )
    abort_stage2 = pro.probe_real_order(_args(stage1_artifact=""))
    dry_stage1 = pro.probe_real_preflight(_preflight_args(tmp_path, confirm=False))
    ready_stage1 = pro.probe_real_preflight(_preflight_args(tmp_path))

    for run in (dry_stage2, abort_stage2, dry_stage1, ready_stage1):
        assert "scope_and_transfer" in run.measurements, run.mode
        assert run.measurements["scope_and_transfer"]["environment"] == ENV_REAL


def test_a_symbol_is_required() -> None:
    with pytest.raises(ProbeError, match="--symbol is required"):
        pro.probe_real_order(_args(symbol=""))


# ===========================================================================
# 19. Page-size walk honesty
# ===========================================================================


def test_a_walk_our_cap_ended_leaves_the_total_unestablished(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO5201R": {
                "rt_cd": "0",
                "output1": [{"odno": f"{i}"} for i in range(15)],
                "ctx_area_fk200": "fk",
                "ctx_area_nk200": "nk",
            }
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    pro._page_size_walk(client.run, _args(max_pages=1), client)

    record = client.run.measurements["real_page_size"]
    assert record["walk_terminated_by_our_max_pages"] is True
    assert record["total_rows_established"] is False
    assert record["page_size_observed"] == 15


def test_a_walk_the_broker_ended_establishes_the_total(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {"TTTO5201R": {"rt_cd": "0", "output1": [{"odno": "1"}], "ctx_area_nk200": ""}}
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    pro._page_size_walk(client.run, _args(max_pages=3), client)

    record = client.run.measurements["real_page_size"]
    assert record["walk_terminated_by_our_max_pages"] is False
    assert record["total_rows_established"] is True


# ===========================================================================
# 20. Order-class ramp honesty
# ===========================================================================


def test_a_disabled_ramp_records_an_explicit_skip_not_a_silent_omission(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    monkeypatch.setattr(pro, "http_json", _Recorder())
    client = _client(creds)

    pro._order_class_ramp(
        client.run, _args(order_class_ramp_attempts=0), client, _tick(), 50_000, []
    )

    assert client.run.skips
    assert "UNESTABLISHED" in client.run.skips[0]["reason"]
    assert "P-13" in client.run.skips[0]["reason"]


def test_the_ramp_stops_at_the_first_throttle_and_reports_a_bracket(
    monkeypatch: pytest.MonkeyPatch, creds: ProbeCredentials
) -> None:
    recorder = _Recorder(
        {
            "TTTO1101U": {
                "rt_cd": "1",
                "msg_cd": "EGW00201",
                "msg1": "초당 거래건수를 초과하였습니다",
            },
            "FHMIF10000000": _quote_response(),
        }
    )
    monkeypatch.setattr(pro, "http_json", recorder)
    client = _client(creds)

    pro._order_class_ramp(
        client.run,
        _args(order_class_ramp_attempts=3),
        client,
        _tick(),
        50_000,
        [],
    )

    record = client.run.measurements["order_class_rate_observation"]
    assert len(record["steps"]) == 1, "the ramp stops at the first throttle"
    assert record["throttled_submit_interval_ms"] is not None
    assert record["candidate_only"] is True
    assert "CANCEL class NOT measured" in record["endpoint_class"]


# ===========================================================================
# 21. Registry metadata
# ===========================================================================


def test_the_order_stage_declares_that_it_emits_real_orders() -> None:
    spec = get("P-R5")
    assert spec.kind == "ORDER"
    assert spec.environment == ENV_REAL
    assert spec.emits_orders is True
    assert spec.requires_confirm is True
    assert spec.risk == "HIGH"
    assert spec.entrypoint == "tools.broker_probes.probes_real_order:probe_real_order"


def test_the_preflight_declares_that_it_does_not() -> None:
    spec = get("P-R5-PRE")
    assert spec.kind == "REAL_READ_ONLY"
    assert spec.emits_orders is False
    assert spec.instance_fields == ()
    assert spec.entrypoint == (
        "tools.broker_probes.probes_real_order:probe_real_preflight"
    )


def test_the_real_pair_does_not_inflate_the_ratified_counts() -> None:
    report = coverage_report()
    assert report["canonical_count"] == 12
    assert report["census_count"] == 4
    for probe_id in ("P-R5", "P-R5-PRE"):
        assert probe_id not in report["canonical_12"]
        assert probe_id not in report["census_4"]
    assert "P-R5" in report["order_emitting"]
    assert "P-R5-PRE" not in report["order_emitting"]


def test_p_r5_is_the_only_real_order_emitting_probe() -> None:
    """If a second one ever appears, this test forces a deliberate decision."""
    real_order_probes = sorted(
        spec.probe_id
        for spec in PROBES.values()
        if spec.emits_orders and spec.environment == ENV_REAL
    )
    assert real_order_probes == ["P-R5"]


def test_the_order_stage_prerequisites_name_the_live_gate_bypass() -> None:
    """The runtime's live-mode guard does not cover this probe; say so out loud."""
    joined = " ".join(get("P-R5").prerequisites)
    assert "futures_live.yaml" in joined
    assert "suspend" in joined
    assert "two order sources" in joined
