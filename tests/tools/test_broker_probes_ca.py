"""Unit tests for the P-CA corporate-action reflection probe (``tools/broker_probes``)."""

from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tools.broker_probes import probes_ca as pc
from tools.broker_probes.common import ProbeError, SafetyViolation
from tools.broker_probes.registry import coverage_report, get

_ACCOUNT = "1234567890"
_CANO = _ACCOUNT[:8]


class _FakeResponse:
    def __init__(self, body: dict[str, Any], *, status: int = 200) -> None:
        self.status_code = status
        self._body = body
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self) -> dict[str, Any]:
        return self._body


class _ScriptedSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any],
        timeout: float,
    ) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, "params": dict(params)})
        if not self._responses:
            raise AssertionError("probe issued more calls than the script provides")
        return self._responses.pop(0)

    def close(self) -> None:
        self.closed = True


class _ExplodingSession:
    def request(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("probe contacted the broker when it must not")

    def close(self) -> None:
        return None


class _FakeAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer test", "appkey": "k", "appsecret": "s"}


def _FrozenDatetime(instant: datetime) -> type[datetime]:  # noqa: N802
    """A ``datetime`` whose ``now()`` is ``instant``, for ``pc.datetime``."""

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return instant if tz is None else instant.astimezone(tz)

    return _Frozen


def _clear_ambient_kis_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_TOKEN_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def stock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ambient_kis_env(monkeypatch)
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_STOCK_ACCOUNT_NO", _ACCOUNT)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replace auth + transport so a walk runs offline, and neutralise the"""

    def _wire(session: Any, *, clock: list[Any] | None = None) -> Any:
        monkeypatch.setattr("requests.Session", lambda: session)
        monkeypatch.setattr(
            "shared.kis.auth.KISAuthManager",
            lambda cfg, use_singleton=True: _FakeAuth(),
        )
        monkeypatch.setattr(pc, "build_auth_config", lambda creds, cache: object())
        monkeypatch.setattr(pc, "probe_token_cache_dir", lambda explicit: tmp_path)
        monkeypatch.setattr("builtins.input", lambda *_a, **_k: "")
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
        if clock is not None:
            it = iter(clock)
            monkeypatch.setattr(pc, "_now", lambda: next(it))
        return session

    return _wire


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "asset": "stock",
        "symbol": "005930",
        "confirm": True,
        "env": "mock",
        "event_class": "bonus_issue",
        "ex_time": "",
        "effective_time": "",
        "payable_time": "",
        "settlement_time": "",
        "poll_ms": 0.0,
        "window_s": 60.0,
        "pace_s": 0.0,
        "reference_check": False,
        "reference_only": False,
        "reference_from": "",
        "reference_to": "",
        "reference_rows_from": "",
        "token_cache_dir": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _balance_body(
    qty: int, cash: float = 1_000_000.0, *, rt_cd: str = "0", symbol: str = "005930"
) -> _FakeResponse:
    return _FakeResponse(
        {
            "rt_cd": rt_cd,
            "msg_cd": "MCA00000" if rt_cd == "0" else "APBK0919",
            "msg1": "정상처리 되었습니다." if rt_cd == "0" else "오류",
            "output1": [{"pdno": symbol, "hldg_qty": str(qty)}],
            "output2": [{"dnca_tot_amt": str(cash)}],
        }
    )


def _ksdinfo_body(
    *, rt_cd: str = "0", rows: list[dict[str, Any]] | None = None
) -> _FakeResponse:
    return _FakeResponse(
        {
            "rt_cd": rt_cd,
            "msg_cd": "MCA00000" if rt_cd == "0" else "APBK0919",
            "msg1": "정상처리 되었습니다." if rt_cd == "0" else "모의투자 미지원",
            "output1": rows if rows is not None else [],
        }
    )


def test_registry_entry_is_supported_with_entrypoint() -> None:
    spec = get("P-CA")
    assert spec.supported is True
    assert spec.entrypoint == "tools.broker_probes.probes_ca:probe_pca"
    assert spec.skip_reason == ""
    assert spec.emits_orders is False
    assert spec.requires_confirm is True


def test_registry_lookup_is_case_and_separator_insensitive() -> None:
    assert get("p-ca") is get("P-CA") is get("P_CA")


def test_followup_probe_does_not_inflate_the_ratified_counts() -> None:
    report = coverage_report()
    assert report["canonical_count"] == 12
    assert report["census_count"] == 4
    assert "P-CA" not in report["canonical_12"]
    assert "P-CA" not in report["census_4"]
    assert "P-CA" not in report["order_emitting"]
    assert "P-CA" not in report["unsupported"]


def test_ca_entrypoint_module_and_function_are_importable() -> None:
    spec = get("P-CA")
    module_name, func_name = spec.entrypoint.split(":")
    import importlib

    module = importlib.import_module(module_name)
    assert callable(getattr(module, func_name))


def _module_ast() -> ast.Module:
    return ast.parse(Path(pc.__file__).read_text(encoding="utf-8"))


def test_module_has_no_mutating_http_method_literal() -> None:
    literals = {
        node.value.strip().upper()
        for node in ast.walk(_module_ast())
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert literals & {"GET"}, "sanity: the GET literal should be present"
    assert not literals & {"POST", "PUT", "PATCH", "DELETE"}


def test_module_calls_no_mutating_transport_method() -> None:
    attrs = {
        node.attr for node in ast.walk(_module_ast()) if isinstance(node, ast.Attribute)
    }
    assert not attrs & {"post", "put", "patch", "delete"}


def test_module_does_not_import_order_capable_modules() -> None:
    imported: set[str] = set()
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    banned = ("probes_order", "probes_real_order")
    assert not [name for name in imported if any(b in name for b in banned)]


def test_allowlist_is_balance_pair_plus_twelve_ksdinfo_and_nothing_else() -> None:
    assert len(pc.ALLOWLIST) == 14
    tr_ids = {entry.tr_id for entry in pc.ALLOWLIST}
    assert {"TTTC8434R", "VTTC8434R"} <= tr_ids
    for entry in pc.ALLOWLIST:
        assert "/order" not in entry.path


def test_futures_asset_is_refused_before_any_credential_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ambient_kis_env(monkeypatch)
    with pytest.raises(ProbeError, match="선물 제외"):
        pc.probe_pca(_args(asset="futures"))


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"symbol": ""}, "--symbol"),
        ({"event_class": "rights_offering"}, "--event-class"),
        ({"env": "paper"}, "--env"),
        ({"window_s": 0}, "--window-s"),
        ({"effective_time": "not-a-date"}, "--effective-time"),
    ],
)
def test_a_bad_argument_is_refused(
    stock_env: None, override: dict[str, Any], match: str
) -> None:
    with pytest.raises(ProbeError, match=match):
        pc.probe_pca(_args(**override))


def test_naive_iso_time_without_utc_offset_is_refused_before_any_call(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """F1: a naive timestamp parses fine via fromisoformat, then crashes later"""
    monkeypatch.setattr("requests.Session", lambda: _ExplodingSession())
    with pytest.raises(ProbeError, match="--effective-time.*(offset|\\+09:00)"):
        pc.probe_pca(_args(effective_time="2020-01-01T09:00:00"))


def test_future_operator_time_is_refused(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """F2: a t0 later than 'now' would record a negative latency."""
    from datetime import UTC, datetime

    monkeypatch.setattr(pc, "_reference_now", lambda: datetime(2020, 1, 1, tzinfo=UTC))
    monkeypatch.setattr("requests.Session", lambda: _ExplodingSession())
    with pytest.raises(ProbeError, match="--payable-time"):
        pc.probe_pca(_args(payable_time="2020-06-01T09:00:00+09:00"))


def test_operator_time_equal_to_now_is_accepted(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(pc, "_reference_now", lambda: t0)
    wire(_ScriptedSession([_balance_body(10)]))
    pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=1e-9)
    )


def test_non_kst_offset_is_recorded_and_warned_not_silently_normalized(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """F8: the CLI help promises KST; a different (still valid) offset must not"""
    wire(_ScriptedSession([_balance_body(10)]))
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T00:00:00+00:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=1e-9,
        )
    )
    assert any(
        obs.get("t0_offsets", {}).get("effective_time") == "+00:00"
        for obs in run.observations
    )
    out = capsys.readouterr().out
    assert "+00:00" in out and "KST" in out


def test_kst_offset_is_recorded_without_a_warning(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    wire(_ScriptedSession([_balance_body(10)]))
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=1e-9,
        )
    )
    assert any(
        obs.get("t0_offsets", {}).get("effective_time") == "+09:00"
        for obs in run.observations
    )
    out = capsys.readouterr().out
    assert "not KST" not in out


def test_dry_run_contacts_no_broker_and_needs_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ambient_kis_env(monkeypatch)
    for name in ("KIS_STOCK_APP_KEY", "KIS_STOCK_APP_SECRET", "KIS_STOCK_ACCOUNT_NO"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("requests.Session", lambda: _ExplodingSession())

    run = pc.probe_pca(_args(confirm=False))

    assert run.mode == "dry-run"
    assert run.errors == []
    assert any("would_send" in obs for obs in run.observations)
    assert "class_leg_table" not in run.measurements


def test_no_holding_is_an_explicit_skip_not_a_negative(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_balance_body(0)]))
    run = pc.probe_pca(_args(effective_time="2020-01-01T09:00:00+09:00"))
    assert any(entry["what"] == "no holding — cannot establish" for entry in run.skips)
    assert "class_leg_table" not in run.measurements


def test_baseline_rejection_is_an_error_and_stops(stock_env: None, wire: Any) -> None:
    wire(_ScriptedSession([_balance_body(10, rt_cd="1")]))
    run = pc.probe_pca(_args(effective_time="2020-01-01T09:00:00+09:00"))
    assert any("rejected" in message for message in run.errors)
    assert "class_leg_table" not in run.measurements


def _paged_balance(
    *,
    qty_row: dict[str, Any] | None = None,
    cash: float = 0.0,
    fk: str = "",
    nk: str = "",
) -> _FakeResponse:
    body: dict[str, Any] = {
        "rt_cd": "0",
        "msg_cd": "MCA00000",
        "msg1": "정상처리 되었습니다.",
        "output1": [qty_row] if qty_row else [],
        "output2": [{"dnca_tot_amt": str(cash)}],
        "ctx_area_fk100": fk,
        "ctx_area_nk100": nk,
    }
    return _FakeResponse(body)


def test_symbol_on_second_page_is_found_not_reported_as_no_holding(
    stock_env: None, wire: Any
) -> None:
    """F6: a single-page balance read cannot tell 'not held' from 'held on a"""
    page1 = _paged_balance(
        qty_row={"pdno": "000660", "hldg_qty": "3"}, fk="F1", nk="N1"
    )
    page2 = _paged_balance(qty_row={"pdno": "005930", "hldg_qty": "7"}, cash=500.0)
    session = wire(_ScriptedSession([page1, page2]))
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=1e-9,
        )
    )
    assert not any(
        entry["what"] == "no holding — cannot establish" for entry in run.skips
    )
    assert run.measurements["baseline"]["hldg_qty"] == 7
    assert len(session.calls) == 2


def test_pagination_cap_hit_is_an_error_not_no_holding(
    stock_env: None, wire: Any
) -> None:
    """F6: the broker never signals end-of-set within the page cap and the"""
    pages = [
        _paged_balance(
            qty_row={"pdno": "999999", "hldg_qty": "1"}, fk=f"F{i}", nk=f"N{i}"
        )
        for i in range(pc._MAX_BALANCE_PAGES)
    ]
    wire(_ScriptedSession(pages))
    run = pc.probe_pca(_args(effective_time="2020-01-01T09:00:00+09:00"))
    assert not any(
        entry["what"] == "no holding — cannot establish" for entry in run.skips
    )
    assert any(
        "page" in message.lower() and "cap" in message.lower() for message in run.errors
    )


def test_quantity_leg_detection_on_second_poll_latency_is_one_effective_interval(
    stock_env: None,
    wire: Any,
) -> None:
    from datetime import UTC, datetime, timedelta

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    interval = timedelta(seconds=1)
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _balance_body(10),
                _balance_body(11),
            ]
        ),
        clock=[t0, t0 + interval],
    )
    run = pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=1000.0, pace_s=0.0, window_s=60.0)
    )

    assert run.errors == []
    key = "legs.bonus_issue.quantity"
    assert key in run.measurements
    record = run.measurements[key]
    assert record["candidate_only"] is True
    assert record["t0_field"] == "effective_time"
    assert record["latency_ms"] == pytest.approx(1000.0)
    assert record["poll_interval_ms_effective"] == pytest.approx(1000.0)
    assert record["attribution"] == "UNVERIFIED_ACCOUNT_LEVEL_CHANGE"
    table = run.measurements["class_leg_table"]
    assert [row for row in table if row["leg"] == "quantity"][0]["status"] == "OBSERVED"
    assert run.measurements["leg_provenance_class"] == "MEASURED"
    assert run.measurements["polls_used"] == 2
    assert run.measurements["polls_completed"] == 2


def test_attribution_caveat_is_recorded_once_when_legs_are_polled(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_balance_body(10)]), clock=None)
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=1e-9,
        )
    )
    assert any("attribution_caveat" in obs for obs in run.observations)


def test_cash_dividend_never_tracks_a_quantity_or_ex_leg(
    stock_env: None, wire: Any
) -> None:
    """F4: 배당 기준가-조정(ex) leg is a PRICE adjustment — hldg_qty cannot see"""
    wire(_ScriptedSession([_balance_body(10)]))
    run = pc.probe_pca(
        _args(
            event_class="cash_dividend",
            ex_time="2020-01-01T09:00:00+09:00",
        )
    )
    assert any(
        entry["what"] == "legs.cash_dividend.ex"
        and "NOT_OBSERVABLE_ON_BALANCE_SURFACE" in entry["reason"]
        for entry in run.skips
    )
    table = run.measurements.get("class_leg_table", [])
    assert not [row for row in table if row["leg"] in ("quantity", "ex")]


def test_legs_to_track_direct_cash_dividend_has_no_quantity_or_ex_entry() -> None:
    """M12 pin: even when ex_time/effective_time/payable_time are ALL supplied,"""
    from datetime import UTC, datetime

    t_ex = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    t_eff = datetime(2020, 1, 2, 9, 0, 0, tzinfo=UTC)
    t_pay = datetime(2020, 1, 3, 9, 0, 0, tzinfo=UTC)
    trial = pc._Trial(
        symbol="005930",
        event_class="cash_dividend",
        is_real=False,
        window_s=60.0,
        poll_ms=0.0,
        pace_s=0.0,
        effective_poll_ms=0.0,
        ex_time=t_ex,
        effective_time=t_eff,
        payable_time=t_pay,
        settlement_time_raw="",
        reference_check=False,
        reference_only=False,
        reference_from="",
        reference_to="",
        reference_rows_from="",
        t0_offsets={},
    )
    legs = pc._legs_to_track(trial)
    assert legs == [("cash", "payable_time", t_pay)]
    assert not [leg for leg in legs if leg[0] in ("quantity", "ex")]


def test_cash_dividend_cash_leg_still_tracked_via_payable_time(
    stock_env: None, wire: Any
) -> None:
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(
        _ScriptedSession(
            [
                _balance_body(10, cash=1_000_000.0),
                _balance_body(10, cash=1_100_000.0),
            ]
        ),
        clock=[t0],
    )
    run = pc.probe_pca(
        _args(
            event_class="cash_dividend",
            ex_time="2020-01-01T09:00:00+09:00",
            effective_time="2020-01-01T09:00:00+09:00",
            payable_time=t0.isoformat(),
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )
    assert any(entry["what"] == "legs.cash_dividend.ex" for entry in run.skips)
    record = run.measurements["legs.cash_dividend.cash"]
    assert record["t0_field"] == "payable_time"
    table = run.measurements["class_leg_table"]
    assert not [row for row in table if row["leg"] in ("quantity", "ex")]


def test_cash_leg_detection(stock_env: None, wire: Any) -> None:
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(
        _ScriptedSession(
            [
                _balance_body(10, cash=1_000_000.0),
                _balance_body(10, cash=1_050_000.0),
            ]
        ),
        clock=[t0],
    )
    run = pc.probe_pca(
        _args(payable_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=60.0)
    )
    assert run.errors == []
    record = run.measurements["legs.bonus_issue.cash"]
    assert record["t0_field"] == "payable_time"
    assert record["candidate_only"] is True


def test_window_expiry_is_censored_and_reports_no_value(
    stock_env: None, wire: Any
) -> None:
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(_ScriptedSession([_balance_body(10)]), clock=[t0])
    run = pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=1e-9)
    )
    assert "legs.bonus_issue.quantity" not in run.measurements
    table = run.measurements["class_leg_table"]
    row = [r for r in table if r["leg"] == "quantity"][0]
    assert row["status"] == "CENSORED"
    assert "t1" not in row
    assert "latency_ms" not in row
    assert "candidate_only" not in row
    assert any(
        "CENSORED" in entry["reason"]
        for entry in run.skips
        if entry["what"] == "legs.bonus_issue.quantity"
    )
    assert run.measurements["leg_provenance_class"] == "NOT_MEASURED"


def test_no_bare_b_non_trade_scalar_ever_appears_in_measurements(
    stock_env: None, wire: Any
) -> None:
    """F5: this probe must never write a B_non_trade_* value as a scalar —"""
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(_ScriptedSession([_balance_body(10), _balance_body(11)]), clock=[t0])
    run = pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=60.0)
    )
    assert not [k for k in run.measurements if k.startswith("B_non_trade")]
    blob = json.dumps(run.to_dict(), ensure_ascii=False)
    assert '"B_non_trade_event_detect":' not in blob.replace(" ", "")
    assert '"B_non_trade_reconcile":' not in blob.replace(" ", "")


def test_no_operator_time_supplied_skips_leg_polling_entirely(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_balance_body(10)]))
    run = pc.probe_pca(_args())
    assert any(entry["what"] == "leg polling" for entry in run.skips)
    assert "class_leg_table" not in run.measurements


def test_settlement_time_is_recorded_but_never_measured(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_balance_body(10)]))
    run = pc.probe_pca(_args(settlement_time="2026-12-11T15:20:00+09:00"))
    assert any(
        obs.get("settlement_time_recorded") == "2026-12-11T15:20:00+09:00"
        for obs in run.observations
    )
    assert "settlement" not in run.measurements.get("class_leg_table", [])


def test_reference_check_success_records_dates(stock_env: None, wire: Any) -> None:
    rows = [{"record_date": "20261001", "right_dt": "20260930"}]
    wire(_ScriptedSession([_balance_body(10), _ksdinfo_body(rows=rows)]))
    run = pc.probe_pca(_args(reference_check=True))
    assert any(obs.get("reference_dates") == rows for obs in run.observations)
    assert any(
        obs.get("mock_reference_support") == "SUPPORTED" for obs in run.observations
    )


def test_reference_check_vts_error_records_unsupported_or_error(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_balance_body(10), _ksdinfo_body(rt_cd="1")]))
    run = pc.probe_pca(_args(reference_check=True))
    blob = [
        obs.get("mock_reference_support")
        for obs in run.observations
        if "mock_reference_support" in obs
    ]
    assert blob and blob[0].startswith("UNSUPPORTED_OR_ERROR:")


def test_reference_check_real_env_error_uses_a_different_key(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_balance_body(10), _ksdinfo_body(rt_cd="1")]))
    run = pc.probe_pca(_args(reference_check=True, env="real"))
    assert not any("mock_reference_support" in obs for obs in run.observations)
    assert any(
        str(obs.get("reference_check_error", "")).startswith("UNSUPPORTED_OR_ERROR:")
        for obs in run.observations
    )


_SKH_ROW = {
    "record_date": "20260831",
    "sht_cd": "000660",
    "divi_pay_dt": "2026/09/30",
    "per_sto_divi_amt": "375",
}


def _ksdinfo_calls(session: Any) -> list[dict[str, Any]]:
    return [call for call in session.calls if "/ksdinfo/" in call["url"]]


def _observation(run: Any, key: str) -> Any:
    for obs in run.observations:
        if key in obs:
            return obs[key]
    raise AssertionError(f"no observation carries {key!r}: {run.observations}")


def _reference_args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "event_class": "cash_dividend",
        "reference_only": True,
        "symbol": "000660",
    }
    base.update(overrides)
    return _args(**base)


def test_reference_only_makes_the_ksdinfo_call_and_nothing_else(
    stock_env: None, wire: Any
) -> None:
    """The whole point: one GET, to the reference TR, with no balance call —"""
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(_reference_args())

    assert len(session.calls) == 1, session.calls
    assert session.calls[0]["method"] == "GET"
    assert "/ksdinfo/dividend" in session.calls[0]["url"]
    assert "CANO" not in session.calls[0]["params"]
    assert _observation(run, "reference_dates") == [_SKH_ROW]
    assert _observation(run, "mock_reference_support") == "SUPPORTED"
    assert _observation(run, "reference_only") is True


def test_reference_only_skips_the_legs_with_an_explicit_reason(
    stock_env: None, wire: Any
) -> None:
    """Never CENSORED and never ABORTED: both of those assert something about"""
    wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(_reference_args())

    reasons = [skip["reason"] for skip in run.skips]
    assert any(reason.startswith("REFERENCE_ONLY —") for reason in reasons), reasons
    assert not any(reason.startswith(("CENSORED", "ABORTED")) for reason in reasons)
    assert "class_leg_table" not in run.measurements
    assert "baseline" not in run.measurements
    assert run.measurements["leg_provenance_class"] == "NOT_MEASURED"


def test_reference_only_needs_no_payable_time_at_all(
    stock_env: None, wire: Any
) -> None:
    """The 058610 pre-check's other half: an operator who does not yet know the"""
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(_reference_args(payable_time="", window_s=0.0, poll_ms=0.0))

    assert len(session.calls) == 1
    assert _observation(run, "reference_dates") == [_SKH_ROW]
    assert _observation(run, "reference_window")["anchor_source"] == "run_time"


def test_a_future_payable_time_no_longer_blocks_a_reference_only_run(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    """The verbatim 2026-10-01 refusal: ``--payable-time is in the future"""
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 4, 53, tzinfo=UTC)
    )
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(
        _reference_args(symbol="058610", payable_time="2026-10-22T00:00:00+09:00")
    )

    assert len(session.calls) == 1
    assert _observation(run, "reference_dates") == [_SKH_ROW]


def test_a_future_payable_time_is_still_refused_for_a_polling_run(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """The regression pin on the other side. The refusal exists because a poll"""
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 4, 53, tzinfo=UTC)
    )
    monkeypatch.setattr("requests.Session", lambda: _ExplodingSession())
    with pytest.raises(ProbeError, match="--payable-time is in the future"):
        pc.probe_pca(
            _args(event_class="cash_dividend", payable_time="2026-10-22T00:00:00+09:00")
        )


def test_the_ksdinfo_window_is_anchored_on_t0_not_the_run_clock(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    """The 2026-10-01 reproduction. Same event, same t0, run a day later: the"""
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )
    monkeypatch.setattr(
        pc, "datetime", _FrozenDatetime(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    )
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(
        _reference_args(payable_time="2026-09-30T00:00:00+09:00"),
    )

    params = _ksdinfo_calls(session)[0]["params"]
    assert params["F_DT"] <= _SKH_ROW["record_date"] <= params["T_DT"], params
    assert params["F_DT"] == "20260602"
    window = _observation(run, "reference_window")
    assert window["anchor_source"] == "payable_time"
    assert window["f_dt"] == "20260602"


def test_the_anchored_window_still_reaches_forward_from_the_run_clock(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    """Both directions, so anchoring cannot narrow the window instead of moving"""
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )
    monkeypatch.setattr(
        pc, "datetime", _FrozenDatetime(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    )
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    pc.probe_pca(_reference_args(payable_time="2026-09-30T00:00:00+09:00"))

    params = _ksdinfo_calls(session)[0]["params"]
    assert params["T_DT"] == "20270330"


def test_a_future_anchor_reaches_back_from_the_run_clock(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    """The 058610 shape: t0 three weeks out. The window must still cover the"""
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )
    monkeypatch.setattr(
        pc, "datetime", _FrozenDatetime(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    )
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[])]))
    pc.probe_pca(
        _reference_args(symbol="058610", payable_time="2026-10-22T00:00:00+09:00")
    )

    params = _ksdinfo_calls(session)[0]["params"]
    assert params["F_DT"] == "20260603"
    assert params["T_DT"] == "20270420"


def test_the_window_is_unchanged_when_no_operator_time_is_supplied(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    """Pin on the no-t0 window: run clock − 120 d … + 180 d, with no anchor to"""
    monkeypatch.setattr(
        pc, "datetime", _FrozenDatetime(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    )
    session = wire(_ScriptedSession([_balance_body(10), _ksdinfo_body(rows=[])]))
    pc.probe_pca(_args(reference_check=True, event_class="cash_dividend"))

    params = _ksdinfo_calls(session)[0]["params"]
    assert (params["F_DT"], params["T_DT"]) == ("20260603", "20270330")


def test_operator_window_overrides_are_sent_verbatim(
    stock_env: None, wire: Any
) -> None:
    """The escape hatch the margins need: the 기준일-to-지급일 gap is"""
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(
        _reference_args(reference_from="20260101", reference_to="20270101")
    )

    params = _ksdinfo_calls(session)[0]["params"]
    assert (params["F_DT"], params["T_DT"]) == ("20260101", "20270101")
    assert _observation(run, "reference_window")["operator_overrides"] == [
        "F_DT",
        "T_DT",
    ]


@pytest.mark.parametrize("bad", ["2026-01-01", "20260132", "abcdefgh", "202601"])
def test_a_malformed_window_override_is_refused_before_any_call(
    stock_env: None, wire: Any, bad: str
) -> None:
    wire(_ExplodingSession())
    with pytest.raises(ProbeError, match="--reference-from"):
        pc.probe_pca(_reference_args(reference_from=bad))


def test_reference_only_accepts_a_zero_window_but_a_polling_run_does_not(
    stock_env: None, wire: Any
) -> None:
    """``--window-s`` bounds a CENSORED row's assertion. A reference-only run"""
    wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    pc.probe_pca(_reference_args(window_s=0.0))
    with pytest.raises(ProbeError, match="--window-s"):
        pc.probe_pca(_args(window_s=0.0))


def test_the_anchored_reference_lines_are_printed_for_the_runner(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The runner's whole input for the pay-date comparison (#830). One record"""
    rows = [_SKH_ROW, {"record_date": "20261130", "divi_pay_dt": "2026/12/30"}]
    wire(_ScriptedSession([_ksdinfo_body(rows=rows)]))
    pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert f"{pc._REFERENCE_STATUS_PREFIX}OK" in printed
    assert f"{pc._REFERENCE_ROWS_PREFIX}2" in printed
    assert f"{pc._REFERENCE_ROW_PREFIX}20260831|20260930" in printed
    assert f"{pc._REFERENCE_ROW_PREFIX}20261130|20261230" in printed
    assert any(line.startswith(pc._REFERENCE_WINDOW_PREFIX) for line in printed)


def test_a_reference_error_says_so_on_its_own_anchored_line(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broker that refuses the TR must not read as "zero rows": the runner"""
    wire(_ScriptedSession([_ksdinfo_body(rt_cd="1")]))
    pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(f"{pc._REFERENCE_STATUS_PREFIX}UNSUPPORTED:")
        for line in printed
    ), printed
    assert not any(line.startswith(pc._REFERENCE_ROW_PREFIX) for line in printed)


def test_a_broker_row_cannot_forge_an_anchored_line(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The row is broker-controlled text going onto a line the runner parses."""
    hostile = {
        "record_date": "2026 08 31",
        "divi_pay_dt": "2026/09/30\nREFERENCE_ROW=99999999|2099/12/31",
    }
    wire(_ScriptedSession([_ksdinfo_body(rows=[hostile])]))
    pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    rows = [line for line in printed if line.startswith(pc._REFERENCE_ROW_PREFIX)]
    assert len(rows) == 1, rows
    assert f"{pc._REFERENCE_ROW_PREFIX}99999999|2099/12/31" not in printed
    assert rows[0].count("|") == 1
    assert rows[0].startswith(f"{pc._REFERENCE_ROW_PREFIX}20260831|")
    assert "REFERENCE_ROW" not in rows[0].split("|", 1)[1]


def test_reference_only_is_still_a_dry_run_without_confirm(
    stock_env: None, wire: Any
) -> None:
    wire(_ExplodingSession())
    run = pc.probe_pca(_reference_args(confirm=False))
    assert "--reference-only" in _observation(run, "would_send")


def _wrapper_says_done(artifact: dict[str, Any], symbol: str = "058610") -> bool:
    """`run-p-ca-20261022.sh::done_already`, transcribed verbatim in Python."""
    if artifact.get("args", {}).get("symbol") != symbol:
        return False
    if artifact.get("args", {}).get("reference_only"):
        return False
    if artifact.get("errors") != []:
        return False
    measurements = artifact.get("measurements") or {}
    if isinstance(measurements, dict) and "legs.cash_dividend.cash" in measurements:
        return True
    for skip in artifact.get("skips", []):
        if skip.get("what") == "legs.cash_dividend.cash" and str(
            skip.get("reason", "")
        ).startswith("CENSORED"):
            return True
    return False


def _cash_trial_args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "symbol": "058610",
        "event_class": "cash_dividend",
        "payable_time": "2020-01-01T09:00:00+09:00",
        "window_s": 1e-9,
    }
    base.update(overrides)
    return _args(**base)


def test_a_reference_only_artifact_is_not_a_completed_observation(
    stock_env: None, wire: Any
) -> None:
    """The finding itself: a lookup must not disarm the slots that would have"""
    wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(_reference_args(symbol="058610"))
    assert _wrapper_says_done(run.to_dict()) is False


def test_a_reference_only_artifact_answers_per_leg_and_never_as_censored(
    stock_env: None, wire: Any
) -> None:
    """It answers under the SAME key a trial uses, so the question is answered"""
    wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(_reference_args(symbol="058610"))

    cash = [s for s in run.skips if s["what"] == "legs.cash_dividend.cash"]
    assert len(cash) == 1, run.skips
    assert cash[0]["reason"].startswith("REFERENCE_ONLY —")
    assert "legs.cash_dividend.cash" not in run.measurements


def test_a_censored_trial_is_a_completed_observation(
    stock_env: None, wire: Any
) -> None:
    """The other direction, and the shape the 10-22 slots are expected to"""
    body = _balance_body(10, symbol="058610")
    wire(_ScriptedSession([body, body]))
    run = pc.probe_pca(_cash_trial_args())
    assert _wrapper_says_done(run.to_dict()) is True


def test_an_observed_trial_is_a_completed_observation(
    stock_env: None, wire: Any
) -> None:
    """The cash leg actually moving is the other completion, and it is"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10, cash=1_000_000.0, symbol="058610"),
                _balance_body(10, cash=1_000_375.0, symbol="058610"),
            ]
        )
    )
    run = pc.probe_pca(_cash_trial_args(window_s=60.0))
    artifact = run.to_dict()
    assert "legs.cash_dividend.cash" in artifact["measurements"]
    assert _wrapper_says_done(artifact) is True


def test_an_aborted_trial_is_not_a_completed_observation(
    stock_env: None, wire: Any
) -> None:
    """And the shape that must leave the next slot armed: polling stopped"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10, symbol="058610"),
                _FakeResponse({"rt_cd": "0"}, status=429),
            ]
        )
    )
    run = pc.probe_pca(_cash_trial_args(window_s=60.0))
    assert run.errors, "this run is supposed to stop early"
    assert _wrapper_says_done(run.to_dict()) is False


def test_every_leg_a_trial_can_track_is_one_reference_only_reports_on() -> None:
    """``_observable_leg_names`` and ``_legs_to_track`` are two spellings of"""
    for event_class in pc._EVENT_CLASSES:
        trial = pc._parse_trial(
            _args(
                event_class=event_class,
                ex_time="2020-01-01T09:00:00+09:00",
                effective_time="2020-01-01T09:00:00+09:00",
                payable_time="2020-01-01T09:00:00+09:00",
            )
        )
        tracked = {name for name, _field, _t0 in pc._legs_to_track(trial)}
        assert tracked == set(pc._observable_leg_names(event_class)), event_class


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026/09/30", "20260930"),
        ("20260831", "20260831"),
        ("2026-09-30", "20260930"),
        ("", ""),
        (None, ""),
        (" 2026 / 09 / 30 ", "20260930"),
    ],
)
def test_a_reference_field_is_digits_and_nothing_else(
    raw: object, expected: str
) -> None:
    """Review #831 F7. The broker spells its two date columns differently —"""
    assert pc._reference_field(raw) == expected


def test_the_status_tokens_the_runner_branches_on_are_the_ones_the_probe_prints() -> (
    None
):
    """The runner's ``case`` arms and these tests' parameters are literals —"""
    assert pc.REFERENCE_STATUSES == (
        "OK",
        "NO_ROWS",
        "UNSUPPORTED",
        "ERROR",
        "TRANSIENT_STOP",
        "RATE_LIMITED",
    )
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "    OK | NO_ROWS | UNSUPPORTED) ;;" in runner


def test_a_stopped_reference_check_says_so_on_the_status_line(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review #831 F5. Two transients stop the run because, in this module's"""
    wire(_TransientSession([_read_timeout(), _read_timeout()]))
    run = pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_TRANSIENT_STOP}")
        for line in printed
    ), printed
    assert run.errors


def test_a_rate_limited_reference_check_says_so_on_the_status_line(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other stop, with its own token: a rate limit is an account-safety"""
    wire(_ScriptedSession([_FakeResponse({"rt_cd": "0"}, status=429)]))
    run = pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_RATE_LIMITED}")
        for line in printed
    ), printed
    assert run.errors


def test_an_empty_reference_table_is_no_rows_not_ok(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """``OK`` with zero rows told the runner nothing it could act on. The two"""
    wire(_ScriptedSession([_ksdinfo_body(rows=[])]))
    pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_NO_ROWS}" in printed
    assert f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_OK}" not in printed


def test_every_reference_check_path_prints_exactly_one_status_line(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The property behind F5, stated once: a runner that branches on this"""
    cases: list[tuple[Any, str]] = [
        (_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]), pc._REF_OK),
        (_ScriptedSession([_ksdinfo_body(rows=[])]), pc._REF_NO_ROWS),
        (_ScriptedSession([_ksdinfo_body(rt_cd="1")]), pc._REF_UNSUPPORTED),
        (_TransientSession([_read_timeout(), _read_timeout()]), pc._REF_TRANSIENT_STOP),
        (
            _ScriptedSession([_FakeResponse({"rt_cd": "0"}, status=429)]),
            pc._REF_RATE_LIMITED,
        ),
    ]
    for session, expected in cases:
        wire(session)
        pc.probe_pca(_reference_args())
        lines = [
            line
            for line in capsys.readouterr().out.splitlines()
            if line.startswith(pc._REFERENCE_STATUS_PREFIX)
        ]
        assert len(lines) == 1, (expected, lines)
        token = lines[0][len(pc._REFERENCE_STATUS_PREFIX) :].split(":", 1)[0]
        assert token == expected
        assert token in pc.REFERENCE_STATUSES


def test_an_inverted_window_override_is_refused_before_any_call(
    stock_env: None, wire: Any
) -> None:
    """Review #831 F9. The broker answers an inverted window with zero rows or"""
    wire(_ExplodingSession())
    with pytest.raises(ProbeError, match="the ksdinfo window is empty"):
        pc.probe_pca(
            _reference_args(reference_from="20261001", reference_to="20260901")
        )


def test_an_equal_window_override_pair_is_accepted(stock_env: None, wire: Any) -> None:
    """The boundary is a single day, not an error: an operator who knows the"""
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    pc.probe_pca(_reference_args(reference_from="20260831", reference_to="20260831"))
    params = _ksdinfo_calls(session)[0]["params"]
    assert (params["F_DT"], params["T_DT"]) == ("20260831", "20260831")


def test_a_broker_refusal_with_a_clean_envelope_is_unsupported(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """HTTP 200 with a real envelope saying ``rt_cd != 0`` is the broker"""
    wire(_ScriptedSession([_ksdinfo_body(rt_cd="1")]))
    run = pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_UNSUPPORTED}:")
        for line in printed
    ), printed
    assert run.errors == []
    assert _observation(run, "mock_reference_support").startswith(
        "UNSUPPORTED_OR_ERROR:"
    )


@pytest.mark.parametrize(
    ("response", "why"),
    [
        (_FakeResponse({"rt_cd": "1"}, status=500), "a non-200 is not an answer"),
        (_FakeResponse({}, status=200), "a body with no rt_cd is not an envelope"),
    ],
)
def test_a_failed_reference_path_is_error_not_unsupported(
    stock_env: None,
    wire: Any,
    capsys: pytest.CaptureFixture[str],
    response: Any,
    why: str,
) -> None:
    """Round 2, F1: one token for both put an HTTP 500 carrying a gateway page"""
    wire(_ScriptedSession([response]))
    run = pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_ERROR}:")
        for line in printed
    ), (why, printed)
    assert not any(
        line.startswith(f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_UNSUPPORTED}")
        for line in printed
    )
    assert run.errors, why


def test_the_refusal_split_is_answered_versus_failed() -> None:
    """The predicate itself, stated once. Not a msg_cd allowlist: no code for"""
    assert pc._reference_refusal_status(200, {"rt_cd": "1"}) == pc._REF_UNSUPPORTED
    assert pc._reference_refusal_status(200, {"rt_cd": "7", "msg_cd": "?"}) == (
        pc._REF_UNSUPPORTED
    )
    assert pc._reference_refusal_status(500, {"rt_cd": "1"}) == pc._REF_ERROR
    assert pc._reference_refusal_status(200, {}) == pc._REF_ERROR
    assert pc._reference_refusal_status(None, {}) == pc._REF_ERROR


def test_a_stopped_lookup_still_answers_per_leg(stock_env: None, wire: Any) -> None:
    """Round 2, F8. ``_do_reference_only`` swallowed ``_StopRun`` and returned"""
    wire(_TransientSession([_read_timeout(), _read_timeout()]))
    run = pc.probe_pca(_reference_args())

    assert run.errors
    cash = [s for s in run.skips if s["what"] == "legs.cash_dividend.cash"]
    assert len(cash) == 1, run.skips
    assert cash[0]["reason"].startswith("REFERENCE_ONLY —")
    assert run.measurements["leg_provenance_class"] == "NOT_MEASURED"
    assert _wrapper_says_done(run.to_dict(), symbol="005930") is False


def test_the_row_count_matches_the_rows_actually_emitted(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Round 2, F10. ``REFERENCE_ROWS`` counted every element of ``output1``"""
    wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW, "", None])]))
    pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    rows = [line for line in printed if line.startswith(pc._REFERENCE_ROW_PREFIX)]
    assert f"{pc._REFERENCE_ROWS_PREFIX}{len(rows)}" in printed
    assert len(rows) == 1


def test_a_body_of_only_unusable_rows_is_no_rows(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """And the status follows the same count: rows that cannot be emitted are"""
    wire(_ScriptedSession([_ksdinfo_body(rows=["", None])]))
    pc.probe_pca(_reference_args())

    printed = capsys.readouterr().out.splitlines()
    assert f"{pc._REFERENCE_STATUS_PREFIX}{pc._REF_NO_ROWS}" in printed
    assert f"{pc._REFERENCE_ROWS_PREFIX}0" in printed


@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"reference_to": "20260501"}, "a lone --reference-to before the derived F_DT"),
        (
            {"reference_from": "20280101"},
            "a lone --reference-from after the derived T_DT",
        ),
        (
            {"reference_from": "20261001", "reference_to": "20260901"},
            "the inverted pair the first check caught",
        ),
    ],
)
def test_an_empty_window_is_refused_however_it_was_asked_for(
    monkeypatch: pytest.MonkeyPatch,
    stock_env: None,
    wire: Any,
    kwargs: dict[str, str],
    why: str,
) -> None:
    """Round 2, F4. Comparing the two overrides only with EACH OTHER missed"""
    monkeypatch.setattr(
        pc, "datetime", _FrozenDatetime(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    )
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )
    wire(_ExplodingSession())
    with pytest.raises(ProbeError, match="the ksdinfo window is empty"):
        pc.probe_pca(
            _reference_args(payable_time="2026-09-30T00:00:00+09:00", **kwargs)
        )


def test_a_single_override_inside_the_derived_window_is_accepted(
    monkeypatch: pytest.MonkeyPatch, stock_env: None, wire: Any
) -> None:
    """The other direction, so the check cannot become "no single override is"""
    monkeypatch.setattr(
        pc, "datetime", _FrozenDatetime(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    )
    monkeypatch.setattr(
        pc, "_reference_now", lambda: datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )
    session = wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    pc.probe_pca(
        _reference_args(
            payable_time="2026-09-30T00:00:00+09:00", reference_from="20260801"
        )
    )
    params = _ksdinfo_calls(session)[0]["params"]
    assert (params["F_DT"], params["T_DT"]) == ("20260801", "20270330")


def _reference_only_artifact(tmp_path: Path, stock_env: None, wire: Any) -> Path:
    """Run a real ``--reference-only`` probe and write its artifact to disk."""
    wire(_ScriptedSession([_ksdinfo_body(rows=[_SKH_ROW])]))
    run = pc.probe_pca(
        _reference_args(symbol="058610", payable_time="2020-01-01T09:00:00+09:00")
    )
    path = tmp_path / "P-CA-reference-only.json"
    path.write_text(json.dumps(run.to_dict()), encoding="utf-8")
    return path


def test_a_trial_adopts_the_precheck_rows_without_a_second_get(
    tmp_path: Path, stock_env: None, wire: Any
) -> None:
    """Round 2, F5. Dropping ``--reference-check`` from the trial to avoid the"""
    source = _reference_only_artifact(tmp_path, stock_env, wire)

    body = _balance_body(10, symbol="058610")
    session = wire(_ScriptedSession([body, body]))
    run = pc.probe_pca(
        _cash_trial_args(reference_rows_from=str(source), reference_check=True)
    )

    assert _ksdinfo_calls(session) == [], "the trial re-sent the reference GET"
    assert _observation(run, "reference_dates") == [_SKH_ROW]
    assert _observation(run, "mock_reference_support") == "SUPPORTED"
    assert _observation(run, "reference_window")["anchor_source"] == "payable_time"
    assert "ADOPTED VERBATIM" in _observation(run, "reference_rows_provenance")


def test_an_adopted_trial_is_still_a_completed_observation(
    tmp_path: Path, stock_env: None, wire: Any
) -> None:
    """Adopting must not disturb the shape the 10-22 re-arm guard reads."""
    source = _reference_only_artifact(tmp_path, stock_env, wire)
    body = _balance_body(10, symbol="058610")
    wire(_ScriptedSession([body, body]))
    run = pc.probe_pca(_cash_trial_args(reference_rows_from=str(source)))
    assert _wrapper_says_done(run.to_dict()) is True


@pytest.mark.parametrize(
    "contents",
    ["not json at all", '{"observations": []}', '["a list, not an artifact"]'],
)
def test_an_unusable_rows_source_is_refused_before_any_broker_call(
    tmp_path: Path, stock_env: None, wire: Any, contents: str
) -> None:
    """A trial that cannot read the artifact it was told to adopt would poll a"""
    source = tmp_path / "bad.json"
    source.write_text(contents, encoding="utf-8")
    wire(_ExplodingSession())
    with pytest.raises(ProbeError, match="--reference-rows-from"):
        pc.probe_pca(_cash_trial_args(reference_rows_from=str(source)))


def test_a_missing_rows_source_is_refused_before_any_broker_call(
    tmp_path: Path, stock_env: None, wire: Any
) -> None:
    wire(_ExplodingSession())
    with pytest.raises(ProbeError, match="could not be read"):
        pc.probe_pca(_cash_trial_args(reference_rows_from=str(tmp_path / "nope.json")))


def test_adopting_and_fetching_write_the_same_observation_keys(
    tmp_path: Path, stock_env: None, wire: Any
) -> None:
    """The property that keeps the two paths from drifting: whatever a"""
    source = _reference_only_artifact(tmp_path, stock_env, wire)

    body = _balance_body(10, symbol="058610")
    wire(_ScriptedSession([body, _ksdinfo_body(rows=[_SKH_ROW]), body]))
    fetched = pc.probe_pca(_cash_trial_args(reference_check=True))

    wire(_ScriptedSession([body, body]))
    adopted = pc.probe_pca(_cash_trial_args(reference_rows_from=str(source)))

    def keys(run: Any) -> set[str]:
        return {
            key
            for obs in run.observations
            for key in obs
            if key in pc._REFERENCE_OBSERVATION_KEYS
        }

    assert keys(fetched) <= keys(adopted), (keys(fetched), keys(adopted))
    assert "reference_dates" in keys(adopted)


def test_rate_limit_on_baseline_stops_with_no_further_call(
    stock_env: None, wire: Any
) -> None:
    session = wire(
        _ScriptedSession(
            [
                _FakeResponse(
                    {"rt_cd": "1", "msg_cd": "", "msg1": "EGW00201"}, status=429
                )
            ]
        )
    )
    run = pc.probe_pca(_args(effective_time="2020-01-01T09:00:00+09:00"))
    assert any("rate-limited" in message for message in run.errors)
    assert len(session.calls) == 1


def test_rate_limit_during_poll_stops_with_no_further_call(
    stock_env: None, wire: Any
) -> None:
    session = wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {"rt_cd": "1", "msg_cd": "", "msg1": "EGW00201"}, status=429
                ),
            ]
        )
    )
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )
    assert any("rate-limited" in message for message in run.errors)
    assert len(session.calls) == 2


def _stop_evidence(run: Any) -> dict[str, Any]:
    """The single ``poll_stop_evidence`` observation, or fail loudly."""
    records = [
        obs["poll_stop_evidence"]
        for obs in run.observations
        if "poll_stop_evidence" in obs
    ]
    assert (
        len(records) == 1
    ), f"expected exactly one stop evidence record, got {records}"
    return records[0]


def _leg_row(run: Any, leg: str) -> dict[str, Any]:
    table = run.measurements["class_leg_table"]
    rows = [row for row in table if row["leg"] == leg]
    assert rows, f"no {leg} row in class_leg_table: {table}"
    return rows[0]


def test_rate_limited_poll_aborts_the_leg_and_records_verbatim_evidence(
    stock_env: None, wire: Any
) -> None:
    """2026-09-17: a rate limit on poll #1 stopped the run after ~1s, yet the"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {
                        "rt_cd": "1",
                        "msg_cd": "EGW00201",
                        "msg1": "초당 거래건수를 초과하였습니다.",
                    },
                    status=429,
                ),
            ]
        )
    )
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=28800.0,
        )
    )

    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["stop_reason"] == pc._STOP_RATE_LIMITED
    assert row["polls_used"] == 1
    assert row["polls_completed"] == 0
    assert row["window_s"] == 28800.0
    assert row["polled_elapsed_s"] < 60.0

    skip = [
        entry for entry in run.skips if entry["what"] == "legs.bonus_issue.quantity"
    ][0]
    assert "ABORTED" in skip["reason"]
    assert "NOT elapse" in skip["reason"]
    assert "CENSORED" not in skip["reason"]
    assert "polls_used=1 (attempts)" in skip["reason"]
    assert "polls_attempted" not in skip["reason"]
    assert "polls_completed=0" in skip["reason"]

    evidence = _stop_evidence(run)
    assert evidence["poll_index"] == 1
    assert evidence["status_kind"] == pc._BAL_RATE_LIMITED
    assert evidence["http_status"] == 429
    assert evidence["msg_cd"] == "EGW00201"
    assert "EGW00201" in evidence["body_excerpt"]


def test_rate_limited_poll_evidence_distinguishes_429_from_body_egw00201(
    stock_env: None, wire: Any
) -> None:
    """The other half of ``is_rate_limited``: EGW00201 in a 200 body. The"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {
                        "rt_cd": "1",
                        "msg_cd": "EGW00201",
                        "msg1": "초당 거래건수를 초과하였습니다.",
                    },
                    status=200,
                ),
            ]
        )
    )
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )
    evidence = _stop_evidence(run)
    assert evidence["http_status"] == 200
    assert evidence["status_kind"] == pc._BAL_RATE_LIMITED
    assert _leg_row(run, "quantity")["status"] == "ABORTED"


def test_rejected_poll_aborts_with_its_own_reason_and_carries_the_envelope(
    stock_env: None, wire: Any
) -> None:
    """A rejection that is NOT a rate limit gets its own stop reason, and the"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {
                        "rt_cd": "1",
                        "msg_cd": "APBK0919",
                        "msg1": "계좌번호가 유효하지 않습니다.",
                        "output1": [],
                        "output2": [],
                    },
                    status=200,
                ),
            ]
        )
    )
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )

    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["stop_reason"] == pc._STOP_REJECTED
    assert row["stop_reason"] != pc._STOP_RATE_LIMITED

    evidence = _stop_evidence(run)
    assert evidence["status_kind"] == pc._BAL_REJECTED
    assert evidence["http_status"] == 200
    assert evidence["rt_cd"] == "1"
    assert evidence["msg_cd"] == "APBK0919"
    assert evidence["msg1"] == "계좌번호가 유효하지 않습니다."


def test_page_capped_poll_aborts_with_the_page_cap_reason(
    stock_env: None, wire: Any
) -> None:
    pages = [_balance_body(10)] + [
        _paged_balance(
            qty_row={"pdno": "999999", "hldg_qty": "1"}, fk=f"F{i}", nk=f"N{i}"
        )
        for i in range(pc._MAX_BALANCE_PAGES)
    ]
    wire(_ScriptedSession(pages))
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )
    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["stop_reason"] == pc._STOP_PAGE_CAP
    evidence = _stop_evidence(run)
    assert evidence["status_kind"] == pc._BAL_CAPPED
    assert evidence["rt_cd"] == "0"
    assert evidence["body_excerpt"] == ""


def test_polls_completed_counts_polls_that_returned_a_balance(
    stock_env: None, wire: Any
) -> None:
    """M2: ``polls_used`` is incremented BEFORE the read, so the attempt that"""
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _balance_body(10),
                _FakeResponse(
                    {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수 초과"},
                    status=429,
                ),
            ]
        ),
        clock=[t0],
    )
    run = pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=60.0)
    )
    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert (row["polls_used"], row["polls_completed"]) == (2, 1)
    assert run.measurements["polls_used"] == 2
    assert run.measurements["polls_completed"] == 1


def test_polled_elapsed_s_is_measured_off_the_clock_not_a_constant(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M3's whole point is that the row carries how long polling ACTUALLY ran."""
    clock = [1000.0]

    class _TickingSession(_ScriptedSession):
        def request(self, *args: Any, **kwargs: Any) -> _FakeResponse:
            response = super().request(*args, **kwargs)
            clock[0] += 7.5
            return response

    wire(
        _TickingSession(
            [
                _balance_body(10),
                _balance_body(10),
                _FakeResponse(
                    {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수 초과"},
                    status=429,
                ),
            ]
        )
    )
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=28800.0,
        )
    )

    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["polls_used"] == 2
    assert row["polled_elapsed_s"] == pytest.approx(15.0)
    assert run.measurements["polled_elapsed_s"] == pytest.approx(15.0)
    assert row["window_s"] == 28800.0
    skip = [
        entry for entry in run.skips if entry["what"] == "legs.bonus_issue.quantity"
    ][0]
    assert "polling ran 15.0s" in skip["reason"]


def test_aborted_row_carries_no_value_fields(stock_env: None, wire: Any) -> None:
    """Like a CENSORED row, an ABORTED row must carry NEITHER a timestamp NOR a"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {"rt_cd": "1", "msg_cd": "", "msg1": "EGW00201"}, status=429
                ),
            ]
        )
    )
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )
    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert "t1" not in row
    assert "latency_ms" not in row
    assert "candidate_only" not in row
    assert "legs.bonus_issue.quantity" not in run.measurements


def test_window_expiry_carries_no_stop_reason_and_no_stop_evidence(
    stock_env: None, wire: Any
) -> None:
    """Regression guard for the untouched path: when nothing goes wrong, an"""
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(_ScriptedSession([_balance_body(10)]), clock=[t0])
    run = pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=1e-9)
    )
    row = _leg_row(run, "quantity")
    assert row["status"] == "CENSORED"
    assert "stop_reason" not in row
    assert "polls_completed" not in row
    assert row["window_s"] == pytest.approx(1e-9)
    assert row["polled_elapsed_s"] < 60.0
    assert not [obs for obs in run.observations if "poll_stop_evidence" in obs]
    assert run.errors == []


def test_baseline_call_observation_carries_the_verbatim_broker_envelope(
    stock_env: None, wire: Any
) -> None:
    """``baseline_call`` recorded only status_kind + rt_cd; a baseline rejection"""
    wire(
        _ScriptedSession(
            [
                _FakeResponse(
                    {
                        "rt_cd": "1",
                        "msg_cd": "APBK0919",
                        "msg1": "계좌번호가 유효하지 않습니다.",
                    },
                    status=200,
                )
            ]
        )
    )
    run = pc.probe_pca(_args(effective_time="2020-01-01T09:00:00+09:00"))
    baseline = [
        obs["baseline_call"] for obs in run.observations if "baseline_call" in obs
    ][0]
    assert baseline["status_kind"] == pc._BAL_REJECTED
    assert baseline["http_status"] == 200
    assert baseline["rt_cd"] == "1"
    assert baseline["msg_cd"] == "APBK0919"
    assert baseline["msg1"] == "계좌번호가 유효하지 않습니다."
    assert "APBK0919" in baseline["body_excerpt"]


def test_body_excerpt_is_truncated_and_never_carries_request_params_or_headers(
    stock_env: None, wire: Any
) -> None:
    """The excerpt is a broker ERROR body recorded unparsed, so it is capped;"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {
                        "rt_cd": "1",
                        "msg_cd": "EGW00201",
                        "msg1": "x" * 4000,
                    },
                    status=429,
                ),
            ]
        )
    )
    run = pc.probe_pca(
        _args(
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=0.0,
            pace_s=0.0,
            window_s=60.0,
        )
    )
    evidence = _stop_evidence(run)
    assert len(evidence["body_excerpt"]) == pc._BODY_EXCERPT_MAX_CHARS
    blob = json.dumps(run.to_dict(), ensure_ascii=False)
    assert _ACCOUNT not in blob
    assert _CANO not in blob
    assert "Bearer test" not in blob


_LEAK_SENTINELS = (
    "000660",
    "81234.5678",
    "98765432",
    "88888888.00",
    "CURSOR-FK-SENTINEL-9f3a",
    "CURSOR-NK-SENTINEL-c71b",
)

_NO_RT_CD = object()


def _sentinel_balance_body(rt_cd: Any = "0") -> dict[str, Any]:
    """A success-SHAPED balance page carrying every :data:`_LEAK_SENTINELS`"""
    body: dict[str, Any] = {
        "msg_cd": "MCA00000",
        "msg1": "정상처리 되었습니다.",
        "output1": [
            {"pdno": "000660", "hldg_qty": "4", "pchs_avg_pric": "81234.5678"},
            {"pdno": "005930", "hldg_qty": "13", "evlu_amt": "98765432"},
        ],
        "output2": [{"dnca_tot_amt": "88888888.00"}],
        "ctx_area_fk100": "CURSOR-FK-SENTINEL-9f3a",
        "ctx_area_nk100": "CURSOR-NK-SENTINEL-c71b",
    }
    if rt_cd is not _NO_RT_CD:
        body["rt_cd"] = rt_cd
    return body


def _assert_no_sentinel_leaked(run: Any) -> None:
    """Assert against the SERIALISED artifact, not the in-memory record: what"""
    blob = json.dumps(run.to_dict(), ensure_ascii=False)
    for leaked in _LEAK_SENTINELS:
        assert (
            leaked not in blob
        ), f"raw balance body leaked into the artifact: {leaked}"


def test_successful_balance_body_is_never_excerpted_into_the_artifact(
    stock_env: None, wire: Any
) -> None:
    """H1: ``_call_evidence`` runs on EVERY baseline status, including"""
    wire(_ScriptedSession([_FakeResponse(_sentinel_balance_body())]))
    run = pc.probe_pca(
        _args(effective_time="2020-01-01T09:00:00+09:00", window_s=1e-9, pace_s=0.0)
    )

    baseline = [
        obs["baseline_call"] for obs in run.observations if "baseline_call" in obs
    ][0]
    assert baseline["status_kind"] == pc._BAL_OK
    assert baseline["http_status"] == 200
    assert baseline["rt_cd"] == "0"
    assert baseline["body_excerpt"] == ""

    assert run.measurements["baseline"]["hldg_qty"] == 13

    _assert_no_sentinel_leaked(run)


@pytest.mark.parametrize(
    ("rt_cd", "label"),
    [
        (_NO_RT_CD, "rt_cd key absent"),
        (None, "rt_cd present but JSON null"),
        (0, "rt_cd as a JSON number, not a string"),
    ],
    ids=["absent", "null", "number_zero"],
)
def test_misclassified_success_body_is_still_never_excerpted(
    stock_env: None, wire: Any, rt_cd: Any, label: str
) -> None:
    """The gate must fail CLOSED, not merely ask "did the broker say success?"."""
    wire(_ScriptedSession([_FakeResponse(_sentinel_balance_body(rt_cd))]))
    run = pc.probe_pca(
        _args(effective_time="2020-01-01T09:00:00+09:00", window_s=1e-9, pace_s=0.0)
    )

    baseline = [
        obs["baseline_call"] for obs in run.observations if "baseline_call" in obs
    ][0]
    assert baseline["body_excerpt"] == "", f"{label} leaked the body"
    assert baseline["status_kind"] == pc._BAL_REJECTED
    assert baseline["http_status"] == 200

    _assert_no_sentinel_leaked(run)


def test_read_balance_reports_the_transport_status_alongside_the_kind(
    stock_env: None, wire: Any
) -> None:
    """The HTTP status must survive :func:`pc._read_balance`, which previously"""
    session = _ScriptedSession(
        [_FakeResponse({"rt_cd": "1", "msg_cd": "", "msg1": "EGW00201"}, status=429)]
    )

    class _Creds:
        cano = _ACCOUNT[:8]
        acnt_prdt_cd = "01"

    kind, qty, cash, _parsed, _text, http_status = pc._read_balance(
        session,
        _FakeAuth(),
        pc.MOCK_BASE_URL,
        pc._STOCK_TR_MOCK,
        _Creds(),
        "005930",
        pc._Pacer(0.0),
    )
    assert kind == pc._BAL_RATE_LIMITED
    assert http_status == 429
    assert (qty, cash) == (0, 0.0)


def test_arg_adder_defaults(stock_env: None) -> None:
    from tools.broker_probes.common import add_common_args

    parser = argparse.ArgumentParser()
    add_common_args(parser)
    pc.add_ca_args(parser)
    parsed = parser.parse_args([])
    assert parsed.asset == "stock"
    assert parsed.env == "mock"
    assert parsed.event_class == ""
    assert parsed.reference_only is False
    assert parsed.reference_from == ""
    assert parsed.reference_to == ""


def test_list_shows_ca_as_confirm_gated(capsys: pytest.CaptureFixture[str]) -> None:
    from tools.broker_probes import run as run_module

    run_module._print_table()
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.startswith("P-CA")]
    assert lines, "P-CA should appear in --list output"
    assert "yes" in lines[0]


def test_get_refuses_a_non_allowlisted_path_before_any_contact() -> None:
    with pytest.raises(SafetyViolation, match="read-only allowlist"):
        pc._get(
            _ExplodingSession(),
            _FakeAuth(),
            base_url=pc.REAL_BASE_URL,
            path="/uapi/domestic-stock/v1/trading/order-cash",
            tr_id="TTTC0012U",
            params={},
        )


def test_first_poll_is_paced_against_the_preceding_setup_call(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The polling loop paces on ``--poll-ms``, but its pacer must still owe the"""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),
                _ksdinfo_body(rows=[{"sht_cd": "005930"}]),
                _balance_body(11),
            ]
        )
    )
    sleeps: list[float] = []
    monkeypatch.setattr("time.monotonic", lambda: 1000.0)
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    run = pc.probe_pca(
        _args(
            event_class="bonus_issue",
            effective_time="2020-01-01T09:00:00+09:00",
            poll_ms=5000.0,
            pace_s=1.1,
            window_s=60.0,
            reference_check=True,
        )
    )

    assert run.errors == []
    assert len(sleeps) == 2, f"expected a gap before every broker call, got {sleeps}"
    assert all(gap == pytest.approx(1.1) for gap in sleeps)


def test_derived_pacer_inherits_the_outstanding_gap() -> None:
    pacer = pc._Pacer(1.1)
    pacer.wait()
    derived = pacer.derive(5.0)
    assert derived.interval_s == pytest.approx(5.0)
    assert derived._next_allowed_at == pacer._next_allowed_at


def _read_timeout() -> BaseException:
    """The exact exception the 09-30 trials died on (artifact ``errors[0]``)."""
    import requests

    return requests.exceptions.ReadTimeout(
        "HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): "
        "Read timed out. (read timeout=20.0)"
    )


def _throttle_body() -> _FakeResponse:
    """EGW00215 verbatim from ``P-CA-20260930T015946Z.json`` poll #14."""
    return _FakeResponse(
        {
            "rt_cd": "1",
            "msg_cd": "EGW00215",
            "msg1": "원장에서 허용 가능한 초당 거래건수를 초과하였습니다.",
        },
        status=500,
    )


class _TransientSession(_ScriptedSession):
    """A scripted session whose script may also contain exceptions to RAISE."""

    def request(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        if self._responses and isinstance(self._responses[0], BaseException):
            self.calls.append({"method": "GET", "url": "", "params": {}})
            raise self._responses.pop(0)
        return super().request(*args, **kwargs)


def _retry_records(run: Any) -> list[dict[str, Any]]:
    """Every transient recorded, retried or not. The key is ``retry_evidence``"""
    return [
        obs["retry_evidence"] for obs in run.observations if "retry_evidence" in obs
    ]


def _poll_args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "effective_time": "2020-01-01T09:00:00+09:00",
        "poll_ms": 0.0,
        "pace_s": 0.0,
        "window_s": 60.0,
    }
    base.update(overrides)
    return _args(**base)


def test_one_transport_timeout_is_retried_once_and_the_run_continues(
    stock_env: None, wire: Any
) -> None:
    """Trial 3's shape: poll #8 raised ``ReadTimeout`` and the exception left"""
    session = wire(
        _TransientSession(
            [
                _balance_body(10),
                _read_timeout(),
                _balance_body(11),
            ]
        )
    )
    run = pc.probe_pca(_poll_args())

    assert run.errors == []
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert run.measurements["polls_used"] == 2
    assert run.measurements["polls_completed"] == 1
    assert _leg_row(run, "quantity")["status"] == "OBSERVED"
    assert len(session.calls) == 3

    record = _retry_records(run)
    assert len(record) == 1
    assert record[0]["phase"] == "poll"
    assert record[0]["poll_index"] == 1
    assert record[0]["retried"] is True
    assert record[0]["transient_kind"] == "transport"
    assert record[0]["status_kind"] == pc._BAL_TRANSIENT_TRANSPORT
    assert record[0]["http_status"] == 0
    assert "ReadTimeout" in record[0]["body_excerpt"]


def test_two_consecutive_transport_timeouts_abort_with_the_transient_reason(
    stock_env: None, wire: Any
) -> None:
    """One retry, not a retry loop: a second consecutive transport failure"""
    session = wire(
        _TransientSession([_balance_body(10), _read_timeout(), _read_timeout()])
    )
    run = pc.probe_pca(_poll_args())

    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["stop_reason"] == pc._STOP_TRANSIENT
    assert (row["polls_used"], row["polls_completed"]) == (2, 0)
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert [r["retried"] for r in _retry_records(run)] == [True, False]
    assert any("twice in a row" in message for message in run.errors)
    assert _stop_evidence(run)["status_kind"] == pc._BAL_TRANSIENT_TRANSPORT
    assert len(session.calls) == 3


def test_one_ledger_throttle_is_retried_once_and_the_run_continues(
    stock_env: None, wire: Any
) -> None:
    """Trial 2's shape: poll #14 answered EGW00215 (HTTP 500, rt_cd='1'), which"""
    session = wire(
        _TransientSession([_balance_body(10), _throttle_body(), _balance_body(11)])
    )
    run = pc.probe_pca(_poll_args())

    assert run.errors == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 1}
    assert run.measurements["polls_completed"] == 1
    assert _leg_row(run, "quantity")["status"] == "OBSERVED"
    record = _retry_records(run)
    assert len(record) == 1
    assert record[0]["retried"] is True
    assert record[0]["transient_kind"] == "ledger_throttle"
    assert record[0]["msg_cd"] == "EGW00215"
    assert record[0]["http_status"] == 500
    assert len(session.calls) == 3


def test_two_consecutive_ledger_throttles_abort_as_rate_limited(
    stock_env: None, wire: Any
) -> None:
    """A doubled LEDGER throttle IS a rate limit, so the row says"""
    wire(_TransientSession([_balance_body(10), _throttle_body(), _throttle_body()]))
    run = pc.probe_pca(_poll_args())

    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["stop_reason"] == pc._STOP_RATE_LIMITED
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 1}
    assert [r["retried"] for r in _retry_records(run)] == [True, False]
    assert _stop_evidence(run)["status_kind"] == pc._BAL_TRANSIENT_LEDGER_THROTTLE


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"rt_cd": "1", "msg_cd": "", "msg1": "EGW00201"}, 429),
        ({"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수 초과"}, 200),
    ],
    ids=["http-429", "body-egw00201"],
)
def test_our_own_rate_limit_is_still_never_retried(
    stock_env: None, wire: Any, body: dict[str, Any], status: int
) -> None:
    """REGRESSION PIN (plan §3). EGW00201 / HTTP 429 mean WE called too fast —"""
    session = wire(
        _TransientSession([_balance_body(10), _FakeResponse(body, status=status)])
    )
    run = pc.probe_pca(_poll_args())

    assert len(session.calls) == 2, "a rate limit bought a retry"
    assert _retry_records(run) == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    row = _leg_row(run, "quantity")
    assert row["stop_reason"] == pc._STOP_RATE_LIMITED
    assert (row["polls_used"], row["polls_completed"]) == (1, 0)
    assert any("no retry" in message for message in run.errors)


def test_a_plain_rejection_is_still_never_retried(stock_env: None, wire: Any) -> None:
    """The other direction of the EGW00215 rule: a rejection that merely"""
    session = wire(
        _TransientSession(
            [
                _balance_body(10),
                _FakeResponse(
                    {"rt_cd": "1", "msg_cd": "APBK0919", "msg1": "not EGW00215 really"},
                    status=200,
                ),
            ]
        )
    )
    run = pc.probe_pca(_poll_args())

    assert len(session.calls) == 2
    assert _retry_records(run) == []
    assert _leg_row(run, "quantity")["stop_reason"] == pc._STOP_REJECTED


def test_the_wait_between_a_poll_and_its_retry_is_one_whole_poll_interval(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry waits a WHOLE poll interval, which ``_Pacer.wait()`` alone"""
    clock = [1000.0]

    class _TickingTransientSession(_TransientSession):
        def request(self, *args: Any, **kwargs: Any) -> _FakeResponse:
            try:
                return super().request(*args, **kwargs)
            finally:
                clock[0] += 20.0

    wire(
        _TickingTransientSession(
            [_balance_body(10), _read_timeout(), _balance_body(11)]
        )
    )
    sleeps: list[float] = []
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    run = pc.probe_pca(
        _poll_args(poll_ms=30000.0, pace_s=0.0, window_s=28800.0),
    )

    assert run.errors == []
    assert sleeps == [pytest.approx(30.0)], (
        "the retry must wait a whole poll interval (30s), not the 10s the "
        f"pacer still owed: {sleeps}"
    )
    assert run.measurements["poll_interval_ms_effective"] == 30000.0


def test_a_transport_timeout_on_the_baseline_is_retried_too(
    stock_env: None, wire: Any
) -> None:
    """Trial 4 died on the FIRST GET of the run and left an artifact with no"""
    session = wire(
        _TransientSession([_read_timeout(), _balance_body(10), _balance_body(11)])
    )
    run = pc.probe_pca(_poll_args())

    assert run.errors == []
    assert run.measurements["baseline"] == {"hldg_qty": 10, "dnca_tot_amt": 1_000_000.0}
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert _leg_row(run, "quantity")["status"] == "OBSERVED"
    record = _retry_records(run)
    assert len(record) == 1
    assert record[0]["phase"] == "baseline"
    assert record[0]["retried"] is True
    assert "poll_index" not in record[0]
    assert len(session.calls) == 3


def test_two_transport_timeouts_on_the_baseline_stop_before_any_poll(
    stock_env: None, wire: Any
) -> None:
    session = wire(_TransientSession([_read_timeout(), _read_timeout()]))
    run = pc.probe_pca(_poll_args())

    assert any(
        "baseline balance call failed twice in a row" in message
        for message in run.errors
    )
    assert "baseline" not in run.measurements
    assert "class_leg_table" not in run.measurements
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert [r["phase"] for r in _retry_records(run)] == ["baseline", "baseline"]
    assert len(session.calls) == 2


def test_a_transient_on_the_reference_check_is_retried_then_the_run_continues(
    stock_env: None, wire: Any
) -> None:
    """The reference check is the one call that does not go through"""
    wire(
        _TransientSession(
            [
                _balance_body(10),
                _read_timeout(),
                _ksdinfo_body(rows=[{"sht_cd": "005930"}]),
                _balance_body(11),
            ]
        )
    )
    run = pc.probe_pca(_poll_args(reference_check=True))

    assert run.errors == []
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert _retry_records(run)[0]["phase"] == "reference_check"
    assert _retry_records(run)[0]["retried"] is True
    assert any("reference_dates" in obs for obs in run.observations)
    assert _leg_row(run, "quantity")["status"] == "OBSERVED"


def test_two_transients_on_the_reference_check_stop_the_run_politely(
    stock_env: None, wire: Any
) -> None:
    """Two consecutive failures say the path to the broker is unhealthy, and"""
    session = wire(
        _TransientSession([_balance_body(10), _read_timeout(), _read_timeout()])
    )
    run = pc.probe_pca(_poll_args(reference_check=True))

    assert any(
        "reference-check call failed twice in a row" in message
        for message in run.errors
    )
    assert "class_leg_table" not in run.measurements
    assert len(session.calls) == 3


def test_a_transport_excerpt_never_carries_the_request_query_string(
    stock_env: None, wire: Any
) -> None:
    """``requests``' ConnectionError renders the URL it failed on IN FULL, and"""
    import requests

    leaky = requests.exceptions.ConnectionError(
        "HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): "
        "Max retries exceeded with url: /uapi/domestic-stock/v1/trading/"
        f"inquire-balance?CANO={_CANO}&ACNT_PRDT_CD=01&INQR_DVSN=02 "
        "(Caused by NewConnectionError('failed to establish a new connection'))"
    )
    wire(_TransientSession([_balance_body(10), leaky, _balance_body(11)]))
    run = pc.probe_pca(_poll_args())

    excerpt = _retry_records(run)[0]["body_excerpt"]
    assert "ConnectionError" in excerpt
    assert "?<redacted>" in excerpt
    assert "CANO" not in excerpt
    assert _CANO not in json.dumps(run.to_dict(get("P-CA")), ensure_ascii=False)


def test_a_run_with_no_transient_still_states_that_it_retried_nothing(
    stock_env: None, wire: Any
) -> None:
    """A run that retried nothing has to SAY so, rather than leave a reader to"""
    wire(_ScriptedSession([_balance_body(10), _balance_body(11)]))
    run = pc.probe_pca(_poll_args())

    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    assert _retry_records(run) == []


def test_the_transient_set_is_no_intact_answer_not_any_exception() -> None:
    """``_get`` raises from TWO places and both belong in the set: the request"""
    import requests

    transient = pc._transport_transient_types()
    for exc_type in (
        requests.exceptions.ReadTimeout,
        requests.exceptions.ConnectTimeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.SSLError,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ContentDecodingError,
    ):
        assert issubclass(exc_type, transient), exc_type
    for exc_type in (
        requests.exceptions.TooManyRedirects,
        requests.exceptions.InvalidURL,
        requests.exceptions.MissingSchema,
        requests.exceptions.URLRequired,
        ValueError,
    ):
        assert not issubclass(exc_type, transient), exc_type


def test_a_body_cut_mid_read_is_retried_like_a_timeout(
    stock_env: None, wire: Any
) -> None:
    """The scenario behind the set above: the broker answers 200 with a"""
    import requests

    class _TruncatedResponse:
        status_code = 200

        @property
        def text(self) -> str:
            raise requests.exceptions.ChunkedEncodingError(
                "Connection broken: IncompleteRead(512 bytes read)"
            )

        def json(self) -> dict[str, Any]:  # pragma: no cover - never reached
            raise AssertionError("text is read first")

    session = wire(
        _TransientSession([_balance_body(10), _TruncatedResponse(), _balance_body(11)])
    )
    run = pc.probe_pca(_poll_args())

    assert run.errors == []
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert "ChunkedEncodingError" in _retry_records(run)[0]["body_excerpt"]
    assert len(session.calls) == 3


def test_a_rate_limited_body_is_never_retried_on_the_reference_check_either(
    stock_env: None, wire: Any
) -> None:
    """Independent review F4: the ksdinfo path classified the ledger throttle"""
    both_signals = _FakeResponse(
        {"rt_cd": "1", "msg_cd": "EGW00215", "msg1": "초당 거래건수 초과"}, status=429
    )
    session = wire(_TransientSession([_balance_body(10), both_signals]))
    run = pc.probe_pca(_poll_args(reference_check=True))

    assert len(session.calls) == 2, "the reference check retried a rate limit"
    assert _retry_records(run) == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    assert any("rate-limited on reference-check" in msg for msg in run.errors)


def test_the_same_body_is_classified_the_same_way_on_both_paths() -> None:
    """The point of a single classifier, stated directly."""
    rate_limited = {"rt_cd": "1", "msg_cd": "EGW00215", "msg1": "x"}
    assert pc._get_classified.__doc__ is not None
    session = _ScriptedSession(
        [
            _FakeResponse(rate_limited, status=429),
            _FakeResponse(rate_limited, status=429),
        ]
    )
    balance_kind, _s, _p, _t = pc._get_classified(
        session,
        _FakeAuth(),
        base_url=pc.MOCK_BASE_URL,
        path=pc._STOCK_BALANCE_PATH,
        tr_id=pc._STOCK_TR_MOCK,
        params={},
    )
    ksd_tr, ksd_path = pc._KSDINFO_TRS["dividend"]
    ksd_kind, _s2, _p2, _t2 = pc._get_classified(
        session,
        _FakeAuth(),
        base_url=pc.MOCK_BASE_URL,
        path=ksd_path,
        tr_id=ksd_tr,
        params={},
    )
    assert balance_kind == ksd_kind == pc._BAL_RATE_LIMITED


def test_defer_re_arms_the_gap_from_now_and_never_shortens_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    pacer = pc._Pacer(30.0)
    pacer.wait()
    clock[0] = 120.0
    pacer.defer(30.0)
    assert pacer._next_allowed_at == pytest.approx(150.0)
    pacer.defer(1.0)
    assert pacer._next_allowed_at == pytest.approx(150.0)


_REPO_ROOT = Path(__file__).resolve().parents[2]

_RUNNERS_DIR = (
    Path(__file__).resolve().parents[2] / "tools" / "broker_probes" / "runners"
)
_RUNNER = _RUNNERS_DIR / "run_p_ca.sh"

_RUNNER_COMMON = _RUNNERS_DIR / "_common.sh"

_CREDENTIAL_SENTINEL = "CREDENTIAL_FILE_WAS_SOURCED"


def test_runner_template_is_tracked_and_executable() -> None:
    """It is in the repository at all — the 09-30 runner was not, and deleted"""
    import os

    assert _RUNNER.is_file(), _RUNNER
    assert os.access(_RUNNER, os.X_OK), f"{_RUNNER} is not executable"


def test_runner_template_parses() -> None:
    import subprocess

    for script in (_RUNNER, _RUNNER_COMMON):
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{script}: {result.stderr}"


def test_runner_template_passes_shellcheck() -> None:
    """On CI a missing shellcheck is a FAILURE, not a skip — and each file is"""
    import os
    import shutil
    import subprocess

    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        if os.environ.get("CI"):
            pytest.fail(
                "shellcheck is missing on CI, where this gate is meant to run; "
                "add it to the workflow rather than letting the check vanish"
            )
        pytest.skip("shellcheck is not installed locally — CI runs this gate")
    for argv in ([_RUNNER], [_RUNNER_COMMON], [_RUNNER, _RUNNER_COMMON]):
        result = subprocess.run(
            [shellcheck, "--severity=warning", *(str(f) for f in argv)],
            capture_output=True,
            text=True,
        )
        assert (
            result.returncode == 0
        ), f"{[f.name for f in argv]}: {result.stdout}{result.stderr}"


def test_runner_template_carries_no_instance_defaults() -> None:
    """Every ``PCA_*`` instance value must be read WITHOUT a ``:-`` default."""
    text = _RUNNER.read_text(encoding="utf-8")
    pairs = set(re.findall(r"\$\{(PCA_[A-Z_]+):-([^}]*)\}", text))
    assert not re.findall(
        r"\b(?:PCA|P8)_[A-Z_]+", _RUNNER_COMMON.read_text(encoding="utf-8")
    )
    assert {name for name, default in pairs if default not in ("", "0")} == set(), pairs
    assert {name for name, _default in pairs} <= {
        "PCA_ALLOW_SHARED_CHECKOUT",
        "PCA_REFERENCE_CHECK",
        "PCA_CRON_MARK",
        "PCA_EFFECTIVE",
        "PCA_LOG",
        "PCA_RECORD_DATE",
        "PCA_ALLOW_PAYDATE_MISMATCH",
        "PCA_REQUIRE_REFERENCE_ROW",
    }, pairs


def _assert_no_self_deletion(text: str) -> None:
    """Two checks, applied to a runner's source."""
    destructive = re.search(
        r"(?<![\w-])(rm|unlink|mv|shred|truncate)(?![\w-])|:\s*>[^>]", text
    )
    assert destructive is None, f"the runner runs a destructive command: {destructive}"
    self_references = [
        line for line in text.splitlines() if "$0" in line and "awk" not in line
    ]
    assert len(self_references) == 1, self_references
    assert "SCRIPT_DIR=" in self_references[0], self_references


@pytest.mark.parametrize(
    "mutation",
    [
        'rm -f "$0"',
        "unlink $0",
        "mv $0 /tmp/",
        "shred -u $0",
        "truncate -s 0 $0",
        ': > "$0"',
        'rm -f "$SCRIPT_DIR/run_p_ca.sh"',
    ],
)
def test_the_self_deletion_guard_catches_what_it_names(mutation: str) -> None:
    """Every form the 09-30 runner could have used to delete itself. The guard"""
    mutated = _RUNNER.read_text(encoding="utf-8") + f"\n{mutation}\n"
    with pytest.raises(AssertionError):
        _assert_no_self_deletion(mutated)


def test_runner_template_never_removes_itself() -> None:
    """2026-09-30: the runner self-deleted after its first run, so attempts 3"""
    _assert_no_self_deletion(_RUNNER.read_text(encoding="utf-8"))


def test_the_shared_helpers_delete_nothing_either() -> None:
    """The guard applies to the file the runner SOURCES too: a destructive"""
    text = _RUNNER_COMMON.read_text(encoding="utf-8")
    destructive = re.search(
        r"(?<![\w-])(rm|unlink|mv|shred|truncate)(?![\w-])|:\s*>[^>]", text
    )
    assert (
        destructive is None
    ), f"the shared helpers run a destructive command: {destructive}"
    assert [
        line for line in text.splitlines() if "$0" in line and "awk" not in line
    ] == []


def _runner_repo(tmp_path: Path, *, detached: bool, dirty: bool) -> Path:
    """A throwaway git checkout holding a copy of the template, so the guards"""
    import shutil
    import subprocess

    repo = tmp_path / "repo"
    (repo / "tools" / "broker_probes" / "runners").mkdir(parents=True)
    shutil.copy2(_RUNNER, repo / "tools/broker_probes/runners/run_p_ca.sh")
    shutil.copy2(_RUNNER_COMMON, repo / "tools/broker_probes/runners/_common.sh")
    (repo / "tools/broker_probes/probes_ca.py").write_text(
        "pacer.derive(  _BAL_TRANSIENT\n", encoding="utf-8"
    )
    (repo / ".gitignore").write_text("results/\n", encoding="utf-8")

    def git(*argv: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *argv],
            check=True,
            capture_output=True,
            text=True,
        )

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True
    )
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("add", "-A")
    git("commit", "-q", "-m", "runner")
    if detached:
        git("checkout", "-q", "--detach", "HEAD")
    if dirty:
        (repo / "untracked.txt").write_text("x", encoding="utf-8")
    return repo


def _publish_origin_main(repo: Path, ref: str = "HEAD") -> None:
    """Point ``refs/remotes/origin/main`` at ``ref`` without a real remote."""
    import subprocess

    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", sha],
        check=True,
        capture_output=True,
    )


def _run_runner(repo: Path, tmp_path: Path) -> Any:
    import subprocess

    env_file = tmp_path / "creds.env"
    env_file.write_text(f"echo {_CREDENTIAL_SENTINEL}\n", encoding="utf-8")
    env = {
        "PATH": __import__("os").environ["PATH"],
        "HOME": str(tmp_path),
        "PCA_LOG": str(tmp_path / "run.log"),
        "PCA_CREDENTIAL_FILE": str(env_file),
        "PCA_KIS_ENV": "mock",
        "PCA_SYMBOL": "000660",
        "PCA_EVENT_CLASS": "cash_dividend",
        "PCA_PAYABLE": "2020-01-01T00:00:00+09:00",
        "PCA_WINDOW_S": "60",
        "PCA_POLL_MS": "30000",
        "PCA_PACE_S": "1.5",
        "PCA_EXPECT_KEY_FP": "deadbeefcafe",
        "PCA_EXPECT_ACCOUNT_FP": "0123456789ab",
        "PCA_TOKEN_CACHE": str(tmp_path / "token-cache"),
        "PCA_EVIDENCE_DIR": str(tmp_path),
        "PCA_NOTE": "runner guard test",
    }
    return subprocess.run(
        ["bash", str(repo / "tools/broker_probes/runners/run_p_ca.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )


def test_runner_aborts_on_a_checkout_that_is_not_detached(tmp_path: Path) -> None:
    """#793: a shared checkout lets a parallel lane move the branch under a"""
    repo = _runner_repo(tmp_path, detached=False, dirty=False)
    result = _run_runner(repo, tmp_path)

    assert result.returncode != 0
    assert "ABORT:" in result.stdout
    assert "not a detached worktree" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_aborts_on_a_dirty_checkout(tmp_path: Path) -> None:
    """The 00:20 cron attempt on 2026-09-30 died here — correctly — on an"""
    repo = _runner_repo(tmp_path, detached=True, dirty=True)
    result = _run_runner(repo, tmp_path)

    assert result.returncode != 0
    assert "ABORT:" in result.stdout
    assert "is dirty" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_override_skips_the_checkout_guards_and_says_so(
    tmp_path: Path,
) -> None:
    """The escape hatch exists (plan §5) but is never silent: with it the run"""
    import subprocess

    repo = _runner_repo(tmp_path, detached=False, dirty=True)
    env_file = tmp_path / "creds.env"
    env_file.write_text("true\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", str(repo / "tools/broker_probes/runners/run_p_ca.sh")],
        capture_output=True,
        text=True,
        env={
            "PATH": __import__("os").environ["PATH"],
            "HOME": str(tmp_path),
            "PCA_ALLOW_SHARED_CHECKOUT": "1",
        },
        cwd=str(tmp_path),
    )
    assert "PCA_ALLOW_SHARED_CHECKOUT=1" in result.stdout
    assert "SKIPPED" in result.stdout
    assert result.returncode != 0
    assert "required env PCA_LOG is unset" in result.stdout


def test_runner_aborts_when_head_is_not_an_ancestor_of_origin_main(
    tmp_path: Path,
) -> None:
    """The third checkout guard, with the input that actually trips it: a"""
    import subprocess

    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)
    (repo / "local-only.txt").write_text("x", encoding="utf-8")
    for argv in (
        ["add", "-A"],
        ["commit", "-q", "-m", "not on origin/main"],
    ):
        subprocess.run(["git", "-C", str(repo), *argv], check=True, capture_output=True)

    result = _run_runner(repo, tmp_path)
    assert result.returncode != 0
    assert "is not an ancestor of origin/main" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_accepts_a_clean_detached_ancestor_checkout(tmp_path: Path) -> None:
    """The other direction: the guards must not be a blanket refusal. A clean,"""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path)
    assert "checkout ok:" in result.stdout
    assert "ABORT: required env PCA_PYTHON is unset" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_aborts_when_the_probe_reports_a_different_policy_version(
    tmp_path: Path,
) -> None:
    """Review F7: the gate used to grep probes_ca.py for ``pacer.derive(`` and"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env={"FAKE_POLICY_VERSION": "p-ca-retry-policy/0"}
    )
    assert result.returncode == 4
    assert "policy version mismatch" in result.stdout
    assert pc.POLICY_VERSION in result.stdout
    assert "p-ca-retry-policy/0" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert argv == []


def test_runner_accepts_the_policy_version_the_probe_reports(tmp_path: Path) -> None:
    """The other direction: the matching version is logged and the run goes on."""
    result, argv = _run_runner_end_to_end(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"probe policy version {pc.POLICY_VERSION} matches this runner" in (
        result.stdout
    )
    assert argv


def _holding_argv(**overrides: str) -> list[str]:
    argv = {
        "--env": "mock",
        "--symbol": "005930",
        "--pace-s": "0",
    }
    argv.update(overrides)
    flat = ["--check-holding"]
    for key, value in argv.items():
        flat += [key, value]
    return flat


def test_holding_check_reports_a_completed_walk_as_held(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    wire(_ScriptedSession([_balance_body(4)]))
    rc = pc.check_holding(_holding_argv())
    assert rc == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "HELD=4"


def test_holding_check_reports_a_real_absence_as_zero(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction: a completed walk that found nothing IS HELD=0, and"""
    wire(
        _ScriptedSession([_paged_balance(qty_row={"pdno": "000660", "hldg_qty": "1"})])
    )
    rc = pc.check_holding(_holding_argv())
    assert rc == 0
    assert "HELD=0" in capsys.readouterr().out


def test_holding_check_never_reports_a_rejection_as_zero(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The 10:58 shape. A rejected balance query is NOT a holding verdict."""
    wire(_ScriptedSession([_balance_body(0, rt_cd="1")]))
    rc = pc.check_holding(_holding_argv())
    out = capsys.readouterr().out
    assert rc != 0
    assert "HELD=" not in out.replace("HOLDING_QUERY_FAILED=", "")
    assert "HOLDING_QUERY_FAILED=REJECTED:APBK0919" in out


def test_holding_check_never_reports_a_timeout_as_zero(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    wire(_TransientSession([_read_timeout(), _read_timeout()]))
    rc = pc.check_holding(_holding_argv())
    captured = capsys.readouterr()
    assert rc != 0
    assert "HOLDING_QUERY_FAILED=TRANSIENT:transport:ReadTimeout" in captured.out
    assert captured.err.count("transient transport") == 2
    assert captured.err.count("retrying once") == 1
    assert "no retry left" in captured.err


def test_holding_check_never_reports_a_rate_limit_as_zero(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    session = wire(
        _TransientSession(
            [_FakeResponse({"rt_cd": "1", "msg_cd": "EGW00201"}, status=429)]
        )
    )
    rc = pc.check_holding(_holding_argv())
    assert rc != 0
    assert "HOLDING_QUERY_FAILED=RATE_LIMITED:EGW00201" in capsys.readouterr().out
    assert len(session.calls) == 1, "the pre-flight retried a rate limit"


def test_holding_check_retries_one_transient_and_then_answers(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """One read timeout must not cost a whole trial window before it starts."""
    session = wire(_TransientSession([_read_timeout(), _balance_body(2)]))
    rc = pc.check_holding(_holding_argv())
    assert rc == 0
    captured = capsys.readouterr()
    assert "HELD=2" in captured.out
    assert "transient transport" in captured.err
    assert "retrying once in 0.0s" in captured.err
    assert len(session.calls) == 2


def test_holding_check_walks_to_page_two_before_saying_not_held(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """F6, one step earlier than the probe: the mock stock account holds 25"""
    page1 = _paged_balance(
        qty_row={"pdno": "000660", "hldg_qty": "3"}, fk="F1", nk="N1"
    )
    page2 = _paged_balance(qty_row={"pdno": "005930", "hldg_qty": "7"})
    session = wire(_ScriptedSession([page1, page2]))
    rc = pc.check_holding(_holding_argv())
    assert rc == 0
    assert "HELD=7" in capsys.readouterr().out
    assert len(session.calls) == 2


def test_holding_check_reports_the_page_cap_without_a_success_code(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review F4: the capped walk's ``parsed`` is the last SUCCESSFUL page, so"""
    pages = [
        _paged_balance(qty_row={"pdno": "000660", "hldg_qty": "1"}, fk="F", nk="N")
        for _ in range(pc._MAX_BALANCE_PAGES)
    ]
    wire(_ScriptedSession(pages))
    rc = pc.check_holding(_holding_argv())
    out = capsys.readouterr().out
    assert rc != 0
    assert f"HOLDING_QUERY_FAILED=CAPPED:page_cap:{pc._MAX_BALANCE_PAGES}" in out
    assert "MCA00000" not in out


def _fake_python(
    tmp_path: Path, *, holding_line: str, holding_rc: int, dump: Path
) -> Path:
    """A stand-in interpreter answering the four calls the runner makes."""
    body = [
        "#!/bin/sh",
        'case "$1" in',
        "  -c)",
        '    case "$2" in',
        '      *__file__*) printf "%s\\n%s\\n" "$FAKE_MODULE_PATH" '
        '"$FAKE_POLICY_VERSION" ;;',
        '      *) printf "%s\\n" "$PCA_EXPECT_ACCOUNT_FP" ;;',
        "    esac",
        "    ;;",
        "  -m)",
        '    case "$2" in',
        f'      tools.broker_probes.probes_ca) printf "%s\\n" {holding_line!r};'
        f" exit {holding_rc} ;;",
        "      tools.broker_probes.run)",
        "        _ref=0",
        '        for a in "$@"; do [ "$a" = "--reference-only" ] && _ref=1; done',
        '        if [ "$_ref" = "1" ]; then',
        '          for a in "$@"; do printf "%s\\n" "$a" >> '
        f"{str(dump) + '.reference'!r}; done",
        '          [ -n "$FAKE_REFERENCE_ARTIFACT" ] && { mkdir -p '
        '"$FAKE_RESULTS_DIR" && printf "{}" '
        '> "$FAKE_RESULTS_DIR/$FAKE_REFERENCE_ARTIFACT"; }',
        '          printf "%s\\n" "$FAKE_REFERENCE_OUTPUT"',
        '          exit "$FAKE_REFERENCE_RC"',
        "        fi",
        f'        for a in "$@"; do printf "%s\\n" "$a" >> {str(dump)!r}; done',
        "        ;;",
        "    esac",
        "    ;;",
        "esac",
        "exit 0",
        "",
    ]
    script = tmp_path / "fake-python"
    script.write_text("\n".join(body), encoding="utf-8")
    script.chmod(0o755)
    return script


def _run_runner_end_to_end(
    tmp_path: Path,
    *,
    holding_line: str = "HELD=1",
    holding_rc: int = 0,
    extra_env: dict[str, str] | None = None,
) -> tuple[Any, list[str]]:
    """Drive the whole template against a fake python; return (result, probe argv)."""
    import hashlib
    import subprocess

    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)
    dump = tmp_path / "probe-argv.txt"
    python = _fake_python(
        tmp_path, holding_line=holding_line, holding_rc=holding_rc, dump=dump
    )

    env_file = tmp_path / "creds.env"
    env_file.write_text(
        f"KIS_STOCK_APP_KEY=test-key\nKIS_STOCK_ACCOUNT_NO=1234567890\n"
        f"echo {_CREDENTIAL_SENTINEL}\n",
        encoding="utf-8",
    )
    key_fp = hashlib.sha256(b"test-key").hexdigest()[:12]
    env = {
        "PATH": __import__("os").environ["PATH"],
        "HOME": str(tmp_path),
        "PCA_LOG": str(tmp_path / "run.log"),
        "PCA_PYTHON": str(python),
        "FAKE_MODULE_PATH": str(repo / "tools/broker_probes/probes_ca.py"),
        "FAKE_POLICY_VERSION": pc.POLICY_VERSION,
        "PCA_CREDENTIAL_FILE": str(env_file),
        "PCA_KIS_ENV": "mock",
        "PCA_SYMBOL": "000660",
        "PCA_EVENT_CLASS": "cash_dividend",
        "PCA_PAYABLE": "2020-01-01T00:00:00+09:00",
        "PCA_WINDOW_S": "60",
        "PCA_POLL_MS": "30000",
        "PCA_PACE_S": "0",
        "PCA_EXPECT_KEY_FP": key_fp,
        "PCA_EXPECT_ACCOUNT_FP": "0123456789ab",
        "PCA_TOKEN_CACHE": str(tmp_path / "token-cache"),
        "PCA_EVIDENCE_DIR": str(tmp_path),
        "PCA_NOTE": "runner end-to-end test",
        "FAKE_REFERENCE_OUTPUT": _reference_output(["20191231|20200101"]),
        "FAKE_REFERENCE_RC": "0",
        "FAKE_REFERENCE_ARTIFACT": "",
        "FAKE_RESULTS_DIR": str(repo / "tools/broker_probes/results"),
    }
    env.update(extra_env or {})
    result = subprocess.run(
        ["bash", str(repo / "tools/broker_probes/runners/run_p_ca.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    argv = dump.read_text(encoding="utf-8").splitlines() if dump.exists() else []
    return result, argv


def _reference_output(rows: list[str], *, status: str = "OK") -> str:
    """The anchored stdout block the probe prints for a reference check."""
    lines = [
        f"{pc._REFERENCE_WINDOW_PREFIX}20190101-20210101",
        f"{pc._REFERENCE_STATUS_PREFIX}{status}",
        f"{pc._REFERENCE_ROWS_PREFIX}{len(rows)}",
    ]
    lines += [f"{pc._REFERENCE_ROW_PREFIX}{row}" for row in rows]
    return "\n".join(lines)


def _reference_argv(tmp_path: Path) -> list[str]:
    """The argv of the reference-only pre-check, or ``[]`` if it never ran."""
    dump = tmp_path / "probe-argv.txt.reference"
    return dump.read_text(encoding="utf-8").splitlines() if dump.exists() else []


def test_runner_passes_a_space_separated_iso_time_as_one_argv_word(
    tmp_path: Path,
) -> None:
    """Independent review F6: ``--effective-time $PCA_EFFECTIVE`` unquoted"""
    spaced = "2020-10-01 09:00:00+09:00"
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env={"PCA_EVENT_CLASS": "bonus_issue", "PCA_EFFECTIVE": spaced},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--effective-time" in argv
    assert argv[argv.index("--effective-time") + 1] == spaced


def test_runner_passes_the_note_as_one_argv_word(tmp_path: Path) -> None:
    """The same quoting property on the field most likely to contain spaces."""
    result, argv = _run_runner_end_to_end(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert argv[argv.index("--note") + 1] == "runner end-to-end test"
    assert "--reference-check" not in argv


def test_the_trial_does_not_repeat_the_reference_get_the_precheck_made(
    tmp_path: Path,
) -> None:
    """Review #831 F6: with the pre-check on, `--reference-check` on the trial"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261022"],
            FAKE_REFERENCE_ARTIFACT="P-CA-20261022T000000Z.json",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--reference-check" not in argv
    assert "--reference-only" in _reference_argv(tmp_path)
    assert "--reference-rows-from" in argv
    assert argv[argv.index("--reference-rows-from") + 1].endswith(
        "P-CA-20261022T000000Z.json"
    )
    assert argv[argv.index("--note") + 1] == "runner end-to-end test"


def test_the_trial_still_asks_for_the_reference_rows_when_no_precheck_ran(
    tmp_path: Path,
) -> None:
    """The other direction. A quantity-leg class gets no pay-date pre-check,"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env={
            "PCA_REFERENCE_CHECK": "1",
            "PCA_EVENT_CLASS": "bonus_issue",
            "PCA_EFFECTIVE": "2020-02-01T09:00:00+09:00",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--reference-check" in argv
    assert _reference_argv(tmp_path) == []


def test_runner_aborts_when_the_holding_check_reports_a_failure(
    tmp_path: Path,
) -> None:
    'Independent review F1: the gate must distinguish "the query failed"'
    result, argv = _run_runner_end_to_end(
        tmp_path,
        holding_line="HOLDING_QUERY_FAILED=TRANSIENT:transport:ReadTimeout",
        holding_rc=1,
    )
    assert result.returncode != 0
    assert "holding check FAILED (this is not a holding verdict)" in result.stdout
    assert "TRANSIENT:transport:ReadTimeout" in result.stdout
    assert "not held" not in result.stdout
    assert argv == [], "the probe ran despite an unknown holding"


def test_runner_aborts_on_a_real_zero_holding_with_a_different_message(
    tmp_path: Path,
) -> None:
    """The other direction: HELD=0 from a COMPLETED walk is a real absence and"""
    result, argv = _run_runner_end_to_end(tmp_path, holding_line="HELD=0")
    assert result.returncode != 0
    assert "the walk completed; this is a real absence" in result.stdout
    assert "not held — nothing to observe" in result.stdout
    assert "holding check FAILED" not in result.stdout
    assert argv == []


def test_runner_refuses_a_holding_number_from_a_failed_exit(tmp_path: Path) -> None:
    """A number printed by a process that then failed is not a verdict."""
    result, argv = _run_runner_end_to_end(tmp_path, holding_line="HELD=3", holding_rc=7)
    assert result.returncode != 0
    assert "exited 7 while reporting HELD=3" in result.stdout
    assert argv == []


def test_runner_aborts_when_the_holding_check_says_nothing_parseable(
    tmp_path: Path,
) -> None:
    result, argv = _run_runner_end_to_end(
        tmp_path, holding_line="Traceback (most recent call last):", holding_rc=1
    )
    assert result.returncode != 0
    assert "printed neither HELD= nor HOLDING_QUERY_FAILED=" in result.stdout
    assert argv == []


def _pay_date_env(rows: list[str], **extra: str) -> dict[str, str]:
    env = {
        "PCA_REFERENCE_CHECK": "1",
        "PCA_PAYABLE": "2026-10-22T00:00:00+09:00",
        "FAKE_REFERENCE_OUTPUT": _reference_output(rows),
    }
    env.update(extra)
    return env


def test_runner_aborts_before_polling_when_the_broker_pay_date_differs(
    tmp_path: Path,
) -> None:
    """The defect, head on: the broker says the 23rd, the trial was planned for"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261023"])
    )
    assert result.returncode != 0
    assert "ABORT: pay-date mismatch" in result.stdout
    assert "{20261023}" in result.stdout
    assert "PCA_PAYABLE=20261022" in result.stdout
    assert argv == [], "the probe polled a window against an unconfirmed t0"
    assert "--reference-only" in _reference_argv(tmp_path)


def test_runner_proceeds_when_the_broker_pay_date_matches(tmp_path: Path) -> None:
    """The other direction: agreement is logged and the trial goes ahead, with"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261022"])
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pay date confirmed by the broker" in result.stdout
    assert argv, "the main probe never ran"
    assert "--reference-only" not in argv
    ref_argv = _reference_argv(tmp_path)
    assert "--reference-only" in ref_argv
    assert ref_argv[ref_argv.index("--symbol") + 1] == "000660"


def test_a_pay_date_mismatch_can_be_overridden_and_is_logged(tmp_path: Path) -> None:
    """The escape hatch is never silent — the same shape as"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(["20260930|20261023"], PCA_ALLOW_PAYDATE_MISMATCH="1"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN" in result.stdout
    assert "PCA_ALLOW_PAYDATE_MISMATCH=1" in result.stdout
    assert "{20261023}" in result.stdout
    assert argv


def test_runner_continues_when_the_reference_table_returns_no_row(
    tmp_path: Path,
) -> None:
    """Record-only, as before this change: an empty reference table is not"""
    result, argv = _run_runner_end_to_end(tmp_path, extra_env=_pay_date_env([]))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN" in result.stdout
    assert "no row matched" in result.stdout
    assert "is NOT confirmed by the broker" in result.stdout
    assert argv


def test_runner_can_be_told_to_require_a_reference_row(tmp_path: Path) -> None:
    """For an unattended slot that would rather skip than measure against an"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env([], PCA_REQUIRE_REFERENCE_ROW="1")
    )
    assert result.returncode != 0
    assert "ABORT: reference check: no row matched" in result.stdout
    assert "PCA_REQUIRE_REFERENCE_ROW=1" in result.stdout
    assert argv == []


def test_a_matched_row_without_a_pay_date_is_not_a_confirmation(
    tmp_path: Path,
) -> None:
    """``divi_pay_dt`` is empty on a stock-dividend row. An empty field must"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|"])
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no candidate row carries a divi_pay_dt" in result.stdout
    assert "no row matched" not in result.stdout
    assert argv


def test_a_row_line_without_a_separator_is_not_read_as_a_match(
    tmp_path: Path,
) -> None:
    """``${SELECTED#*|}`` returns the WHOLE string when there is no ``|``, so a"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20261022"])
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no candidate row carries a divi_pay_dt" in result.stdout
    assert "pay date confirmed" not in result.stdout
    assert argv


def test_runner_selects_the_row_named_by_the_record_date(tmp_path: Path) -> None:
    """Several quarters of one issuer come back in a single answer. With"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261022", "20261231|20270410"],
            PCA_RECORD_DATE="20260930",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pay date confirmed by the broker" in result.stdout
    assert "record_date=20260930" in result.stdout
    assert argv


def test_a_later_quarters_row_does_not_fake_a_mismatch(tmp_path: Path) -> None:
    """Review #831 F2. The window reaches 180 days PAST the pay date, so a"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(["20261231|20270410", "20260930|20261022"]),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pay date confirmed by the broker" in result.stdout
    assert "any returned row (PCA_RECORD_DATE unset)" in result.stdout
    assert argv


def test_a_mismatch_needs_every_candidate_row_to_disagree(tmp_path: Path) -> None:
    """The other direction, so "any row confirms" cannot become "nothing ever"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(["20261231|20270410", "20260930|20261023"]),
    )
    assert result.returncode != 0
    assert "ABORT: pay-date mismatch" in result.stdout
    assert "20261023" in result.stdout
    assert "20270410" in result.stdout
    assert argv == []


def test_a_sibling_row_with_no_pay_date_does_not_mask_the_one_that_has_it(
    tmp_path: Path,
) -> None:
    """Review #831 F8. The dividend TR serves cash AND stock dividends under"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261022", "20260930|"], PCA_RECORD_DATE="20260930"
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pay date confirmed by the broker" in result.stdout
    assert "record_date=20260930" in result.stdout
    assert argv


def test_a_non_kst_payable_time_is_compared_in_kst(tmp_path: Path) -> None:
    """Review #831 F3, and CLAUDE.md's non-negotiable: convert to KST BEFORE"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261022"], PCA_PAYABLE="2026-10-21T15:00:00Z"
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pay date confirmed by the broker" in result.stdout
    assert "20261022" in result.stdout
    assert argv


def test_an_unparseable_payable_time_aborts_before_any_broker_call(
    tmp_path: Path,
) -> None:
    """``date -d`` also answers the question the old prefix match could not:"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env([], PCA_PAYABLE="whenever")
    )
    assert result.returncode != 0
    assert "is not a date this shell can parse" in result.stdout
    assert argv == []
    assert _reference_argv(tmp_path) == []


def test_runner_refuses_a_malformed_record_date_before_any_broker_call(
    tmp_path: Path,
) -> None:
    """It is interpolated into a ``sed`` pattern, so its shape is checked with"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env([], PCA_RECORD_DATE="2026-09-30")
    )
    assert result.returncode != 0
    assert "ABORT: PCA_RECORD_DATE must be YYYYMMDD" in result.stdout
    assert argv == []
    assert _reference_argv(tmp_path) == []
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_the_pay_date_check_is_skipped_for_a_quantity_leg_class(
    tmp_path: Path,
) -> None:
    """``divi_pay_dt`` is the CASH leg's field. A bonus issue pairs with"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261023"],
            PCA_EVENT_CLASS="bonus_issue",
            PCA_EFFECTIVE="2020-02-01T09:00:00+09:00",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pay-date mismatch" not in result.stdout
    assert _reference_argv(tmp_path) == []
    assert argv


def test_no_pay_date_check_runs_when_the_reference_check_is_not_asked(
    tmp_path: Path,
) -> None:
    """The pre-check costs a broker call, so it is opt-in on the same switch"""
    result, argv = _run_runner_end_to_end(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _reference_argv(tmp_path) == []
    assert "reference-only" not in result.stdout
    assert argv


def test_the_reference_only_artifact_lands_beside_the_trials_not_among_them(
    tmp_path: Path,
) -> None:
    """Acceptance criterion: a future pay date now LEAVES an artifact — and"""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    result, _argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261023"],
            PCA_EVIDENCE_DIR=str(evidence),
            FAKE_REFERENCE_ARTIFACT="P-CA-20261022T000000Z.json",
        ),
    )
    assert result.returncode != 0, "this run aborts on the mismatch"
    assert "(reference-only)" in result.stdout
    assert list(evidence.glob("P-CA-*.json")) == []
    assert [path.name for path in (evidence / "reference-only").iterdir()] == [
        "P-CA-20261022T000000Z.json"
    ]


def test_a_copy_that_fails_says_so_and_does_not_claim_the_artifact(
    tmp_path: Path,
) -> None:
    """Review #831 F10: only the success branch was chained, so a copy into an"""
    import os

    evidence = tmp_path / "readonly-evidence"
    evidence.mkdir()
    os.chmod(evidence, 0o500)
    try:
        result, _argv = _run_runner_end_to_end(
            tmp_path,
            extra_env=_pay_date_env(
                ["20260930|20261022"],
                PCA_EVIDENCE_DIR=str(evidence),
                FAKE_REFERENCE_ARTIFACT="P-CA-20261022T000000Z.json",
            ),
        )
    finally:
        os.chmod(evidence, 0o700)
    failed = [line for line in result.stdout.splitlines() if "could NOT copy" in line]
    assert len(failed) == 1, result.stdout
    assert "(reference-only)" in failed[0]
    assert "is this run's reference-only lookup, not a trial" in result.stdout
    assert list(evidence.iterdir()) == []


@pytest.mark.parametrize(
    "status", ["TRANSIENT_STOP:transport", "RATE_LIMITED:http_429"]
)
def test_a_stopped_reference_check_aborts_instead_of_starting_the_trial(
    tmp_path: Path, status: str
) -> None:
    """``_do_reference_check`` stops on two transients precisely because "the"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            [], FAKE_REFERENCE_OUTPUT=_reference_output([], status=status)
        ),
    )
    assert result.returncode != 0
    assert "ABORT: reference check did not complete" in result.stdout
    assert status in result.stdout
    assert argv == [], "a 16-hour window started down an unhealthy path"


def test_a_reference_check_that_printed_nothing_aborts_too(tmp_path: Path) -> None:
    """What a crash out of the probe looks like from the runner: no status"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            [], FAKE_REFERENCE_OUTPUT="Traceback (most recent call last):"
        ),
    )
    assert result.returncode != 0
    assert "ABORT: reference check did not complete" in result.stdout
    assert "<none>" in result.stdout
    assert argv == []


@pytest.mark.parametrize("status", ["OK", "NO_ROWS", "UNSUPPORTED"])
def test_a_clean_reference_answer_lets_the_trial_start(
    tmp_path: Path, status: str
) -> None:
    """The other direction, for all three statuses that are answers rather"""
    rows = ["20260930|20261022"] if status == "OK" else []
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            rows, FAKE_REFERENCE_OUTPUT=_reference_output(rows, status=status)
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert argv


def test_the_runner_anchors_the_window_on_a_known_record_date(
    tmp_path: Path,
) -> None:
    """Review #831 F4. The window filters on 기준일, which precedes the pay"""
    result, _argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(["20260922|20261022"], PCA_RECORD_DATE="20260922"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    ref_argv = _reference_argv(tmp_path)
    assert "--reference-from" in ref_argv
    assert ref_argv[ref_argv.index("--reference-from") + 1] == "20260921"


def test_no_window_override_is_sent_when_no_record_date_is_known(
    tmp_path: Path,
) -> None:
    """The other direction: without PCA_RECORD_DATE the probe's own anchored"""
    result, _argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261022"])
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--reference-from" not in _reference_argv(tmp_path)


def test_the_reference_only_call_is_paced_like_every_other_process(
    tmp_path: Path,
) -> None:
    """Three processes now, three independent pacers. The 2026-09-17"""
    import os

    bindir = tmp_path / "bin"
    bindir.mkdir()
    slept = tmp_path / "slept.txt"
    fake_sleep = bindir / "sleep"
    fake_sleep.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$1" >> {str(slept)!r}\nexit 0\n',
        encoding="utf-8",
    )
    fake_sleep.chmod(0o755)

    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261022"],
            PATH=f"{bindir}:{os.environ['PATH']}",
            PCA_PACE_S="1.5",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert argv, "the probe never ran"
    assert slept.read_text(encoding="utf-8").split() == ["1.5", "1.5"], (
        "expected one PCA_PACE_S wait before the reference-only call and one "
        f"before the probe, got {slept.read_text(encoding='utf-8')!r}"
    )


def test_an_error_status_aborts_while_unsupported_proceeds(tmp_path: Path) -> None:
    'Round 2, F1. One token covered both "the mock does not serve this TR"'
    bad, _argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            [], FAKE_REFERENCE_OUTPUT=_reference_output([], status="ERROR:http_500/")
        ),
    )
    assert bad.returncode != 0
    assert "ABORT: reference check did not complete" in bad.stdout


def test_the_precheck_retry_waits_the_trials_polling_interval(
    tmp_path: Path,
) -> None:
    """Round 2, F2. Without --poll-ms the single retry after a ledger throttle"""
    _result, _argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261022"])
    )
    ref_argv = _reference_argv(tmp_path)
    assert "--poll-ms" in ref_argv
    assert ref_argv[ref_argv.index("--poll-ms") + 1] == "30000"


def test_a_precheck_that_failed_after_printing_is_not_trusted(
    tmp_path: Path,
) -> None:
    """Round 2, F3. The probe can print its rows and still die writing the"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(["20260930|20261022"], FAKE_REFERENCE_RC="5"),
    )
    assert result.returncode != 0
    assert "reference check exited 5 while reporting" in result.stdout
    assert argv == [], "the trial started on a pre-check that had failed"


def test_the_pay_date_is_checked_before_the_holding_walk(tmp_path: Path) -> None:
    """Round 2, F7. The pre-check needs no holding — the ksdinfo TRs are"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261023"])
    )
    assert result.returncode != 0
    assert "ABORT: pay-date mismatch" in result.stdout
    assert "held qty" not in result.stdout, "the holding walk was spent anyway"
    assert argv == []


def test_the_holding_walk_still_runs_when_the_pay_date_agrees(
    tmp_path: Path,
) -> None:
    """The other direction, so moving the pre-check first cannot quietly drop"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261022"])
    )
    assert result.returncode == 0, result.stdout + result.stderr
    order = result.stdout.index("reference-only") < result.stdout.index("held qty")
    assert order, "the holding walk ran before the pre-check"
    assert argv


def test_a_reference_only_artifact_is_never_copied_into_the_evidence_root(
    tmp_path: Path,
) -> None:
    """Round 2, F6. The subdirectory keeps a lookup out of the re-arm guard's"""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    result, _argv = _run_runner_end_to_end(
        tmp_path,
        extra_env=_pay_date_env(
            ["20260930|20261022"],
            PCA_EVIDENCE_DIR=str(evidence),
            FAKE_REFERENCE_ARTIFACT="P-CA-20261022T000000Z.json",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "is this run's reference-only lookup, not a trial" in result.stdout
    assert list(evidence.glob("P-CA-*.json")) == []
    assert [p.name for p in (evidence / "reference-only").iterdir()] == [
        "P-CA-20261022T000000Z.json"
    ]


def test_the_runner_says_so_when_the_precheck_left_no_artifact_to_adopt(
    tmp_path: Path,
) -> None:
    """The trial then carries no reference_dates, and silence about that is"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env=_pay_date_env(["20260930|20261022"])
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "left no artifact, so this trial carries no reference_dates" in (
        result.stdout
    )
    assert "--reference-rows-from" not in argv
    assert "--reference-check" not in argv


class _ClockedTransientSession(_TransientSession):
    """A scripted session that burns a scripted number of seconds per call."""

    def __init__(self, responses: list[Any], clock: list[float], burns: list[float]):
        super().__init__(responses)
        self._clock = clock
        self._burns = list(burns)

    def request(self, *args: Any, **kwargs: Any) -> Any:
        burn = self._burns.pop(0) if self._burns else 0.0
        try:
            return super().request(*args, **kwargs)
        finally:
            self._clock[0] += burn


def _run_windowed_poll(
    wire: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    burn_on_transient: float,
) -> tuple[Any, Any]:
    """Baseline, then one poll that fails transiently after ``burn_on_transient``"""
    clock = [1000.0]
    session = wire(
        _ClockedTransientSession(
            [_balance_body(10), _read_timeout(), _balance_body(11)],
            clock,
            [0.0, burn_on_transient, 0.0],
        )
    )
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    run = pc.probe_pca(
        _poll_args(poll_ms=30000.0, pace_s=0.0, window_s=60.0),
    )
    return run, session


def test_a_transient_after_the_window_buys_no_retry(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's scenario: window 60s, the poll fails 80s in. Retrying would"""
    run, session = _run_windowed_poll(wire, monkeypatch, burn_on_transient=80.0)

    row = _leg_row(run, "quantity")
    assert row["status"] == "CENSORED"
    assert "stop_reason" not in row
    assert len(session.calls) == 2, "the retry fired outside the window"
    assert run.measurements["polls_used"] == 1
    assert run.measurements["polls_completed"] == 0
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    record = _retry_records(run)
    assert len(record) == 1
    assert record[0]["retried"] is False
    assert record[0]["phase"] == "poll"
    assert run.measurements["polled_elapsed_s"] == pytest.approx(80.0)


def test_a_transient_inside_the_window_still_buys_its_retry(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other direction of the same guard: the deadline refuses the retry"""
    run, session = _run_windowed_poll(wire, monkeypatch, burn_on_transient=10.0)

    assert run.errors == []
    assert len(session.calls) == 3
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert _retry_records(run)[0]["retried"] is True
    assert _leg_row(run, "quantity")["status"] == "OBSERVED"


def test_runner_refuses_an_interpreter_that_loads_another_checkout(
    tmp_path: Path,
) -> None:
    """Review F1's consequence. The interpreter is the MAIN checkout's venv, so"""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env={"FAKE_MODULE_PATH": "/some/other/checkout/probes_ca.py"},
    )
    assert result.returncode != 0
    assert "resolves OUTSIDE the checkout" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert argv == []


def test_runner_paces_the_probe_against_the_holding_check(tmp_path: Path) -> None:
    """Review F2: the holding check and the probe are two processes with"""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    slept = tmp_path / "slept.txt"
    fake_sleep = bindir / "sleep"
    fake_sleep.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$1" >> {str(slept)!r}\nexit 0\n',
        encoding="utf-8",
    )
    fake_sleep.chmod(0o755)
    import os

    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env={
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "PCA_PACE_S": "1.5",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert argv, "the probe never ran"
    assert slept.read_text(encoding="utf-8").split() == ["1.5"], (
        "expected exactly one PCA_PACE_S wait between the holding check and "
        f"the probe, got {slept.read_text(encoding='utf-8')!r}"
    )


def test_runner_refuses_a_quantity_leg_class_without_an_effective_time(
    tmp_path: Path,
) -> None:
    """Review F3: a pure configuration error must not cost broker calls. The"""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env={"PCA_EVENT_CLASS": "split"}
    )
    assert result.returncode != 0
    assert "set PCA_EFFECTIVE" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert "held qty" not in result.stdout
    assert argv == []


def _worktree_pair(
    tmp_path: Path,
    *,
    primary_has_credentials: bool,
    credential_name: str = ".env.mock",
) -> tuple[Path, Path]:
    """A primary checkout plus a detached linked worktree of it — the real"""
    import shutil
    import subprocess

    primary = tmp_path / "primary"
    (primary / "tools" / "broker_probes" / "runners").mkdir(parents=True)
    shutil.copy2(_RUNNER, primary / "tools/broker_probes/runners/run_p_ca.sh")
    shutil.copy2(_RUNNER_COMMON, primary / "tools/broker_probes/runners/_common.sh")
    (primary / "tools/broker_probes/probes_ca.py").write_text(
        "pacer.derive(  _BAL_TRANSIENT\n", encoding="utf-8"
    )
    shutil.copy2(_REPO_ROOT / ".gitignore", primary / ".gitignore")

    def git(*argv: str) -> None:
        subprocess.run(
            ["git", "-C", str(primary), *argv],
            check=True,
            capture_output=True,
            text=True,
        )

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(primary)],
        check=True,
        capture_output=True,
    )
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("add", "-A")
    git("commit", "-q", "-m", "runner")
    _publish_origin_main(primary)

    if primary_has_credentials:
        cred = primary / credential_name
        cred.write_text(
            "KIS_STOCK_APP_KEY=test-key\nKIS_STOCK_ACCOUNT_NO=1234567890\n"
            f"echo {_CREDENTIAL_SENTINEL}\n",
            encoding="utf-8",
        )
        cred.chmod(0o644)

    worktree = tmp_path / "wt"
    git("worktree", "add", "--detach", "-q", str(worktree), "HEAD")
    return primary, worktree


def _run_from_worktree(
    tmp_path: Path,
    worktree: Path,
    *,
    credential_file: str,
    holding_line: str = "HELD=1",
) -> tuple[Any, list[str]]:
    import hashlib
    import os
    import subprocess

    dump = tmp_path / "probe-argv.txt"
    python = _fake_python(tmp_path, holding_line=holding_line, holding_rc=0, dump=dump)
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "PCA_LOG": str(tmp_path / "run.log"),
        "PCA_PYTHON": str(python),
        "FAKE_MODULE_PATH": str(worktree / "tools/broker_probes/probes_ca.py"),
        "FAKE_POLICY_VERSION": pc.POLICY_VERSION,
        "PCA_CREDENTIAL_FILE": credential_file,
        "PCA_KIS_ENV": "mock",
        "PCA_SYMBOL": "000660",
        "PCA_EVENT_CLASS": "cash_dividend",
        "PCA_PAYABLE": "2020-01-01T00:00:00+09:00",
        "PCA_WINDOW_S": "60",
        "PCA_POLL_MS": "30000",
        "PCA_PACE_S": "0",
        "PCA_EXPECT_KEY_FP": hashlib.sha256(b"test-key").hexdigest()[:12],
        "PCA_EXPECT_ACCOUNT_FP": "0123456789ab",
        "PCA_TOKEN_CACHE": str(tmp_path / "token-cache"),
        "PCA_EVIDENCE_DIR": str(tmp_path),
        "PCA_NOTE": "worktree credential test",
    }
    result = subprocess.run(
        ["bash", str(worktree / "tools/broker_probes/runners/run_p_ca.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    argv = dump.read_text(encoding="utf-8").splitlines() if dump.exists() else []
    return result, argv


def test_runner_copies_the_credential_file_into_a_bare_worktree(
    tmp_path: Path,
) -> None:
    """A freshly added worktree carries none of the ignored env files, so the"""
    import stat

    primary, worktree = _worktree_pair(tmp_path, primary_has_credentials=True)
    assert not (worktree / ".env.mock").exists(), "precondition: worktree is bare"

    result, argv = _run_from_worktree(tmp_path, worktree, credential_file=".env.mock")

    assert result.returncode == 0, result.stdout + result.stderr
    copied = worktree / ".env.mock"
    assert copied.is_file()
    assert stat.S_IMODE(copied.stat().st_mode) == 0o600
    assert "credential file copied from the primary checkout" in result.stdout
    assert str(primary / ".env.mock") in result.stdout
    assert str(copied) in result.stdout
    assert "test-key" not in result.stdout
    assert "1234567890" not in result.stdout
    assert _CREDENTIAL_SENTINEL in result.stdout
    assert argv, "the probe never ran"


def test_a_copied_credential_file_does_not_dirty_the_worktree(
    tmp_path: Path,
) -> None:
    """The copy persists, so it must land on an ignored path — otherwise the"""
    import subprocess

    _primary, worktree = _worktree_pair(tmp_path, primary_has_credentials=True)
    result, _argv = _run_from_worktree(tmp_path, worktree, credential_file=".env.mock")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (worktree / ".env.mock").is_file()

    status = subprocess.run(
        ["git", "-C", str(worktree), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout == "", f"the copy dirtied the worktree: {status.stdout!r}"


def test_runner_aborts_naming_both_paths_when_neither_checkout_has_it(
    tmp_path: Path,
) -> None:
    primary, worktree = _worktree_pair(tmp_path, primary_has_credentials=False)
    result, argv = _run_from_worktree(tmp_path, worktree, credential_file=".env.mock")

    assert result.returncode != 0
    assert "is in neither checkout" in result.stdout
    assert str(worktree / ".env.mock") in result.stdout
    assert str(primary / ".env.mock") in result.stdout
    assert not (worktree / ".env.mock").exists()
    assert argv == []


def test_an_absolute_credential_path_is_used_as_given_and_never_copied(
    tmp_path: Path,
) -> None:
    """The 09-15 credential backup lives under ~/.config and is named"""
    _primary, worktree = _worktree_pair(tmp_path, primary_has_credentials=False)
    absolute = tmp_path / "backup-creds.env"
    absolute.write_text(
        "KIS_STOCK_APP_KEY=test-key\nKIS_STOCK_ACCOUNT_NO=1234567890\n"
        f"echo {_CREDENTIAL_SENTINEL}\n",
        encoding="utf-8",
    )

    result, argv = _run_from_worktree(tmp_path, worktree, credential_file=str(absolute))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "copied from the primary checkout" not in result.stdout
    assert not (worktree / ".env.mock").exists()
    assert _CREDENTIAL_SENTINEL in result.stdout
    assert argv


def test_an_unreadable_absolute_credential_path_says_so_without_copying(
    tmp_path: Path,
) -> None:
    _primary, worktree = _worktree_pair(tmp_path, primary_has_credentials=True)
    result, argv = _run_from_worktree(
        tmp_path, worktree, credential_file=str(tmp_path / "nope.env")
    )

    assert result.returncode != 0
    assert "absolute path, used as given" in result.stdout
    assert "copied from the primary checkout" not in result.stdout
    assert argv == []


def test_the_repo_ignores_exact_env_names_not_a_glob() -> None:
    """The premise the credential copy rests on, measured rather than assumed"""
    import subprocess

    def ignored(name: str) -> bool:
        return (
            subprocess.run(
                ["git", "-C", str(_REPO_ROOT), "check-ignore", "-q", "--", name],
                capture_output=True,
            ).returncode
            == 0
        )

    assert ignored(".env.mock")
    assert ignored(".env.real")
    assert not ignored(".env.mock.bak-20260915")
    assert not ignored(".env.probe")


def test_runner_refuses_a_relative_credential_name_that_is_not_ignored(
    tmp_path: Path,
) -> None:
    """Review F2, the secrets rule. `.env.mock.bak-20260915` is a name the"""
    primary, worktree = _worktree_pair(
        tmp_path, primary_has_credentials=True, credential_name=".env.mock.bak-x"
    )
    result, argv = _run_from_worktree(
        tmp_path, worktree, credential_file=".env.mock.bak-x"
    )

    assert result.returncode != 0
    assert "is NOT gitignored" in result.stdout
    assert not (worktree / ".env.mock.bak-x").exists()
    assert (primary / ".env.mock.bak-x").is_file()
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert argv == []


def test_runner_creates_a_missing_log_directory_instead_of_losing_the_trial(
    tmp_path: Path,
) -> None:
    """Review F1: with the log directory absent, step 6's `>>"$PCA_LOG"`"""
    fresh = tmp_path / "logs-that-do-not-exist-yet" / "p-ca.log"
    result, argv = _run_runner_end_to_end(tmp_path, extra_env={"PCA_LOG": str(fresh)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert fresh.is_file()
    assert argv, "the probe never ran"


def test_runner_aborts_when_the_log_path_cannot_be_created(tmp_path: Path) -> None:
    """The other direction: an unusable PCA_LOG stops the run loudly, before"""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env={"PCA_LOG": str(blocker / "sub" / "p-ca.log")}
    )
    assert result.returncode != 0
    assert "PCA_LOG" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert argv == []


def _fake_crontab(tmp_path: Path, *, existing_line: str) -> tuple[Path, Path]:
    """A `crontab` stand-in on PATH that records whether a write happened."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    written = tmp_path / "crontab-written.txt"
    table = tmp_path / "crontab-table.txt"
    table.write_text(existing_line + "\n", encoding="utf-8")
    script = bindir / "crontab"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-l" ]; then cat ' + repr(str(table))[1:-1] + "; exit 0; fi\n"
        "cat > " + repr(str(written))[1:-1] + "\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bindir, written


def test_runner_retires_the_cron_entry_once_the_probe_has_run(
    tmp_path: Path,
) -> None:
    import os

    bindir, written = _fake_crontab(tmp_path, existing_line="30 0 * * * run_p_ca_mark")
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env={
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "PCA_CRON_MARK": "run_p_ca_mark",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert argv, "the probe never ran"
    assert written.is_file(), "the crontab was never rewritten"
    assert "run_p_ca_mark" not in written.read_text(encoding="utf-8")


def test_runner_leaves_the_cron_entry_when_it_aborts_before_the_probe(
    tmp_path: Path,
) -> None:
    """Review F1: a run that never started the probe must not retire its own"""
    import os

    bindir, written = _fake_crontab(tmp_path, existing_line="30 0 * * * run_p_ca_mark")
    result, argv = _run_runner_end_to_end(
        tmp_path,
        holding_line="HOLDING_QUERY_FAILED=TRANSIENT:transport:ReadTimeout",
        holding_rc=1,
        extra_env={
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "PCA_CRON_MARK": "run_p_ca_mark",
        },
    )
    assert result.returncode != 0
    assert argv == []
    assert not written.exists(), "an aborted run retired its own cron entry"


def test_the_holding_failure_detail_is_capped_and_single_line(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review F5: a gateway can answer with a colon-free HTML page, and the"""
    html = "<html>\nHELD=99\n" + ("A" * 900) + "\n</html>"

    class _HtmlResponse:
        status_code = 502
        text = html

        def json(self) -> dict[str, Any]:
            raise ValueError("not json")

    wire(_TransientSession([_HtmlResponse()]))
    rc = pc.check_holding(_holding_argv())
    out = capsys.readouterr().out

    assert rc != 0
    failed = [ln for ln in out.splitlines() if ln.startswith("HOLDING_QUERY_FAILED=")]
    assert len(failed) == 1
    detail = failed[0].split(":", 1)[1]
    assert len(detail) <= pc._BODY_EXCERPT_MAX_CHARS
    assert "HELD=99" in detail
    assert not any(ln.startswith("HELD=") for ln in out.splitlines())


def test_the_preflight_retry_waits_the_trial_polling_interval(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F6: the pre-flight retried a ledger throttle after --pace-s, the"""
    wire(_TransientSession([_throttle_body(), _balance_body(3)]))
    sleeps: list[float] = []
    monkeypatch.setattr("time.monotonic", lambda: 1000.0)
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    rc = pc.check_holding(_holding_argv(**{"--retry-wait-ms": "30000"}))

    assert rc == 0
    assert sleeps == [pytest.approx(30.0)], sleeps


def test_the_preflight_falls_back_to_pace_when_no_interval_is_given(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    wire(_TransientSession([_throttle_body(), _balance_body(3)]))
    sleeps: list[float] = []
    monkeypatch.setattr("time.monotonic", lambda: 1000.0)
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    rc = pc.check_holding(_holding_argv(**{"--pace-s": "1.5"}))

    assert rc == 0
    assert sleeps == [pytest.approx(1.5)], sleeps


def test_the_holding_check_announces_the_policy_version(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """So the log of any run records which policy actually answered, not just"""
    wire(_ScriptedSession([_balance_body(4)]))
    pc.check_holding(_holding_argv())
    assert f"POLICY_VERSION={pc.POLICY_VERSION}" in capsys.readouterr().out


def test_credentials_are_recorded_before_the_session_is_opened(
    stock_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Review F4: anything after the credential resolution can raise something"""
    seen: dict[str, Any] = {}

    def _boom(cfg: Any, use_singleton: bool = True) -> Any:
        raise OSError("token cache unreadable")

    monkeypatch.setattr("shared.kis.auth.KISAuthManager", _boom)
    monkeypatch.setattr(pc, "build_auth_config", lambda creds, cache: object())
    monkeypatch.setattr(pc, "probe_token_cache_dir", lambda explicit: tmp_path)

    def _record(resolved: Any) -> None:
        seen["credentials"] = resolved.describe()

    with pytest.raises(OSError):
        pc._open_broker_session(
            is_real=False, token_cache_dir=None, on_credentials=_record
        )
    assert seen["credentials"], "credentials were not recorded before the failure"
