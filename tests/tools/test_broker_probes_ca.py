"""Unit tests for the P-CA corporate-action reflection probe (``tools/broker_probes``).

P-CA exists because N-19 (``docs/plans/2026-09-10-tos-p02-n19-ca-spec-collation.md``)
found that none of KIS's 12 ksdinfo reference TRs, nor the balance TR
(``TTTC8434R``/``VTTC8434R``), documents WHEN a corporate action is reflected in
balance/position. ``hldg_qty`` (quantity) and ``dnca_tot_amt`` (cash/deposit total)
are the only indirect observation surface; this probe polls them and pairs each
leg with the one of the seven ADR §8 times (design doc
``docs/plans/2026-08-07-tos-p02-nontrade-probe-definition.md`` §5.2) that leg's
rationale calls for — never a single collapsed scalar.

The properties tested here mirror ``test_broker_probes_balance.py``'s discipline:

1. **Futures are refused outright**, before any credential resolution.
2. **No holding ⇒ explicit skip**, never a spurious "no truncation risk"-style claim.
3. **A leg is CENSORED, never zero**, when the polling window expires unobserved.
4. **The module is structurally read-only** — GET-only, no order-capable import,
   asserted against the module's own AST.
5. **A rate limit stops the run outright** — no retry, no further broker call.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.broker_probes import probes_ca as pc
from tools.broker_probes.common import ProbeError, SafetyViolation
from tools.broker_probes.registry import coverage_report, get

_ACCOUNT = "1234567890"
#: What a request actually carries — ``ProbeCredentials.cano`` is
#: ``account_no[:8]`` (``common.py:266-267``), never the full 10 digits.
_CANO = _ACCOUNT[:8]


# ---------------------------------------------------------------------------
# fixtures / doubles
# ---------------------------------------------------------------------------


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
    """Replace auth + transport so a walk runs offline, and neutralise the
    operator prompt + real sleeping so the test is instant and deterministic."""

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
        "token_cache_dir": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _balance_body(
    qty: int, cash: float = 1_000_000.0, *, rt_cd: str = "0"
) -> _FakeResponse:
    return _FakeResponse(
        {
            "rt_cd": rt_cd,
            "msg_cd": "MCA00000" if rt_cd == "0" else "APBK0919",
            "msg1": "정상처리 되었습니다." if rt_cd == "0" else "오류",
            "output1": [{"pdno": "005930", "hldg_qty": str(qty)}],
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


# ---------------------------------------------------------------------------
# registry metadata
# ---------------------------------------------------------------------------


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
    # P-CA is no longer unsupported now that it has a real entrypoint.
    assert "P-CA" not in report["unsupported"]


def test_ca_entrypoint_module_and_function_are_importable() -> None:
    spec = get("P-CA")
    module_name, func_name = spec.entrypoint.split(":")
    import importlib

    module = importlib.import_module(module_name)
    assert callable(getattr(module, func_name))


# ---------------------------------------------------------------------------
# structural read-only property (module AST — not prose)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# preconditions
# ---------------------------------------------------------------------------


def test_futures_asset_is_refused_before_any_credential_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ambient_kis_env(monkeypatch)
    with pytest.raises(ProbeError, match="선물 제외"):
        pc.probe_pca(_args(asset="futures"))


def test_missing_symbol_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--symbol"):
        pc.probe_pca(_args(symbol=""))


def test_unknown_event_class_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--event-class"):
        pc.probe_pca(_args(event_class="rights_offering"))


def test_unknown_env_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--env"):
        pc.probe_pca(_args(env="paper"))


def test_zero_window_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--window-s"):
        pc.probe_pca(_args(window_s=0))


def test_bad_iso_time_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--effective-time"):
        pc.probe_pca(_args(effective_time="not-a-date"))


def test_naive_iso_time_without_utc_offset_is_refused_before_any_call(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    """F1: a naive timestamp parses fine via fromisoformat, then crashes later
    (aware - naive TypeError) at the moment the first leg would be observed —
    after the CA window has already been consumed. It must be refused at parse
    time, before any network call."""
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
    # Must not raise — t0 == now is the boundary, not "future".
    pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=1e-9)
    )


def test_non_kst_offset_is_recorded_and_warned_not_silently_normalized(
    stock_env: None, wire: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """F8: the CLI help promises KST; a different (still valid) offset must not
    be silently accepted as if it were +09:00 — it is recorded verbatim and the
    operator is warned."""
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


# ---------------------------------------------------------------------------
# dry-run: zero network, no credentials required
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# baseline / no-holding
# ---------------------------------------------------------------------------


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
    """F6: a single-page balance read cannot tell 'not held' from 'held on a
    later page' — it must walk continuation keys before concluding no holding."""
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
    """F6: the broker never signals end-of-set within the page cap and the
    symbol is never found — this must surface as an error, not a silent
    'no holding' conclusion (which would be fail-open)."""
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


# ---------------------------------------------------------------------------
# leg detection
# ---------------------------------------------------------------------------


def test_quantity_leg_detection_on_second_poll_latency_is_one_effective_interval(
    stock_env: None,
    wire: Any,
) -> None:
    from datetime import UTC, datetime, timedelta

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    interval = timedelta(seconds=1)
    # clock is consumed once per poll iteration; poll #1 sees no change, poll #2
    # (t0 + 1 interval) sees the quantity change => latency == 1 effective interval.
    wire(
        _ScriptedSession(
            [
                _balance_body(10),  # baseline
                _balance_body(10),  # poll #1 — unchanged
                _balance_body(11),  # poll #2 — quantity changed
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
    # F3: a detected balance change is not verified to be caused by THIS CA —
    # any account-level activity in the window looks identical.
    assert record["attribution"] == "UNVERIFIED_ACCOUNT_LEVEL_CHANGE"
    table = run.measurements["class_leg_table"]
    assert [row for row in table if row["leg"] == "quantity"][0]["status"] == "OBSERVED"
    assert run.measurements["leg_provenance_class"] == "MEASURED"
    # M2: on a run that ends naturally the two counts agree — both polls
    # completed, so nothing is hidden behind the ambiguous name.
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
    """F4: 배당 기준가-조정(ex) leg is a PRICE adjustment — hldg_qty cannot see
    it (N-19 §2.3: no price field in the balance TR response). P-CA must not
    silently CENSOR an unobservable leg; it must say so explicitly and never
    poll for it."""
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
    # No CENSORED (or any) row for the ex/quantity leg — it was never tracked.
    table = run.measurements.get("class_leg_table", [])
    assert not [row for row in table if row["leg"] in ("quantity", "ex")]


def test_legs_to_track_direct_cash_dividend_has_no_quantity_or_ex_entry() -> None:
    """M12 pin: even when ex_time/effective_time/payable_time are ALL supplied,
    cash_dividend must resolve to EXACTLY the cash leg. Asserted directly
    against :func:`pc._legs_to_track`'s return value — independent of the
    runtime ``NOT_OBSERVABLE_ON_BALANCE_SURFACE`` skip (which fires regardless
    of what the leg list actually contains, so a mutant that restores a
    quantity/ex leg for cash_dividend would otherwise survive)."""
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
    # M12: --ex-time AND --effective-time were both supplied — a mutant that
    # revives a quantity/ex leg for cash_dividend must still be caught here.
    table = run.measurements["class_leg_table"]
    assert not [row for row in table if row["leg"] in ("quantity", "ex")]


def test_cash_leg_detection(stock_env: None, wire: Any) -> None:
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(
        _ScriptedSession(
            [
                _balance_body(10, cash=1_000_000.0),  # baseline
                _balance_body(10, cash=1_050_000.0),  # poll #1 — cash changed
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
    # window_s small; monotonic clock advances only via real time, which we do
    # not fast-forward, so the loop condition `time.monotonic() < deadline`
    # with window_s=0 boundary would never enter — use a scripted session with
    # exactly one poll returning no change and a window that has already
    # elapsed by the time the loop re-checks (achieved via a 0 window plus a
    # baseline holding, guaranteeing the poll loop body never runs and every
    # leg is CENSORED).
    wire(_ScriptedSession([_balance_body(10)]), clock=[t0])
    run = pc.probe_pca(
        _args(effective_time=t0.isoformat(), poll_ms=0.0, pace_s=0.0, window_s=1e-9)
    )
    assert "legs.bonus_issue.quantity" not in run.measurements
    table = run.measurements["class_leg_table"]
    row = [r for r in table if r["leg"] == "quantity"][0]
    assert row["status"] == "CENSORED"
    # F5 (kills mutation M7 — a CENSORED row given a fabricated latency_ms):
    # a CENSORED row must carry NEITHER a timestamp NOR a value. It must also
    # not be tagged candidate_only — there is no candidate value to flag.
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
    """F5: this probe must never write a B_non_trade_* value as a scalar —
    only measurements.class_leg_table (per (event_class x leg) candidates)."""
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


# ---------------------------------------------------------------------------
# --reference-check
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ABORTED vs CENSORED + verbatim stop evidence (2026-09-17 P-CA trial 1 defects)
# ---------------------------------------------------------------------------


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
    """2026-09-17: a rate limit on poll #1 stopped the run after ~1s, yet the
    cash leg was labelled CENSORED "within --window-s=28800.0s" — asserting an
    8-hour absence that was never observed. The window did not elapse: that is
    ABORTED. And the artifact recorded only the string "rate-limited", though
    ``is_rate_limited`` fires on EITHER HTTP 429 OR EGW00201 in the body, so
    nobody could tell afterwards which one had fired."""
    wire(
        _ScriptedSession(
            [
                _balance_body(10),  # baseline
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
    # M2: polls_used counts ATTEMPTS, so the one it counts here is the attempt
    # that was rate-limited — zero polls came back with a usable balance. The
    # 2026-09-17 row said "polls_used=1" for exactly this run and read as "one
    # poll observed nothing".
    assert row["polls_completed"] == 0
    # M3: the row is the ONLY aggregate this probe emits, so it must carry how
    # long polling actually ran, not just the 8 hours that were requested.
    assert row["window_s"] == 28800.0
    assert row["polled_elapsed_s"] < 60.0

    skip = [
        entry for entry in run.skips if entry["what"] == "legs.bonus_issue.quantity"
    ][0]
    assert "ABORTED" in skip["reason"]
    assert "NOT elapse" in skip["reason"]
    assert "CENSORED" not in skip["reason"]
    # The prose must name which count is which, not leave "polls_used" to be
    # read as "polls that completed" — and it must spell the quantity the same
    # way the row key does, so prose and row are not two names for one number.
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
    """The other half of ``is_rate_limited``: EGW00201 in a 200 body. The
    evidence must show http_status=200, so the two signals are told apart."""
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
    """A rejection that is NOT a rate limit gets its own stop reason, and the
    evidence carries the broker's rt_cd/msg_cd/msg1 verbatim."""
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
    # Asserted against the ROW the run produced, not against the two constants:
    # a plain rejection must not be filed under the rate-limit reason.
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
    # H1: the page-cap stop is the leak that hid in plain sight — its last page
    # is a SUCCESSFUL balance page, so an ungated excerpt recorded a full
    # holdings body under the banner of "stop evidence".
    assert evidence["rt_cd"] == "0"
    assert evidence["body_excerpt"] == ""


def test_polls_completed_counts_polls_that_returned_a_balance(
    stock_env: None, wire: Any
) -> None:
    """M2: ``polls_used`` is incremented BEFORE the read, so the attempt that
    ends the run is counted. With one good poll and then a rate limit the two
    counters must differ — attempted 2, completed 1."""
    from datetime import UTC, datetime

    t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    wire(
        _ScriptedSession(
            [
                _balance_body(10),  # baseline
                _balance_body(10),  # poll #1 — completes, no change
                _FakeResponse(  # poll #2 — rate-limited, no observation
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
    """M3's whole point is that the row carries how long polling ACTUALLY ran.
    Every other assertion on it is ``< 60.0``, which a hardcoded ``0.0`` — or a
    silent substitution of the requested ``--window-s`` — satisfies just as
    well. Pin it to a simulated clock instead.

    The clock advances ONLY on a broker round-trip, so the expected value is
    fixed by the SCRIPT (2 polls x 7.5s) rather than by how many times the code
    happens to read ``time.monotonic()``.
    """
    clock = [1000.0]

    class _TickingSession(_ScriptedSession):
        def request(self, *args: Any, **kwargs: Any) -> _FakeResponse:
            response = super().request(*args, **kwargs)
            clock[0] += 7.5
            return response

    wire(
        _TickingSession(
            [
                _balance_body(10),  # baseline — before the polling clock starts
                _balance_body(10),  # poll #1 — completes, no change
                _FakeResponse(  # poll #2 — rate-limited, the run aborts
                    {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수 초과"},
                    status=429,
                ),
            ]
        )
    )
    # AFTER wire(), which installs its own no-op sleep — patching monotonic
    # first would be undone by nothing, but the sleep must already be inert or
    # the pacer would block on a clock that only this test advances.
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
    # Two polled round-trips at 7.5 simulated seconds each. Not 0.0, and not
    # the 28800.0s that were merely REQUESTED.
    assert row["polled_elapsed_s"] == pytest.approx(15.0)
    assert run.measurements["polled_elapsed_s"] == pytest.approx(15.0)
    assert row["window_s"] == 28800.0
    # The ABORTED prose quotes the same measured number, not the window.
    skip = [
        entry for entry in run.skips if entry["what"] == "legs.bonus_issue.quantity"
    ][0]
    assert "polling ran 15.0s" in skip["reason"]


def test_aborted_row_carries_no_value_fields(stock_env: None, wire: Any) -> None:
    """Like a CENSORED row, an ABORTED row must carry NEITHER a timestamp NOR a
    value, and must not be tagged candidate_only — there is no candidate."""
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
    """Regression guard for the untouched path: when nothing goes wrong, an
    unobserved leg stays CENSORED with no stop_reason and no stop evidence."""
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
    # M3: a CENSORED row states an absence over the window, so it too says how
    # long polling ran — here the window was 1e-9s and nothing polled.
    assert row["window_s"] == pytest.approx(1e-9)
    assert row["polled_elapsed_s"] < 60.0
    assert not [obs for obs in run.observations if "poll_stop_evidence" in obs]
    assert run.errors == []


def test_baseline_call_observation_carries_the_verbatim_broker_envelope(
    stock_env: None, wire: Any
) -> None:
    """``baseline_call`` recorded only status_kind + rt_cd; a baseline rejection
    was therefore as undiagnosable as the poll one."""
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
    """The excerpt is a broker ERROR body recorded unparsed, so it is capped;
    and neither a request param (which carry the account number) nor a request
    header (which carries the bearer token) may ever reach the artifact
    through it.

    The account assertion is on ``creds.cano`` — ``account_no[:8]``
    (``common.py:266-267``), the value the balance params ACTUALLY carry — not
    on the full 10-digit ``_ACCOUNT``, which no request ever transmits: dumping
    ``params`` verbatim would leak the CANO and a ``_ACCOUNT``-only assertion
    would still pass.

    The header half is asserted too, and stays asserted even though no current
    code path copies headers: ``_FakeAuth`` really does transmit
    ``authorization: Bearer test`` and ``_get`` (``probes_ca.py:416``) really
    does build the outgoing header dict from it, so this is the standing guard
    against a future ``_call_evidence`` that records the request the way it
    already records the response. ``_BODY_EXCERPT_MAX_CHARS`` promises "request
    params AND headers are never recorded here"; a test of only the params half
    leaves half the promise unenforced.
    """
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


#: Values that must never appear in a serialised artifact: another holder's
#: ``pdno``, purchase price, valuation, the verbatim account cash total, and the
#: raw continuation cursors ``probes_balance.py:529-540`` fingerprints rather
#: than stores.
_LEAK_SENTINELS = (
    "000660",  # another holder's pdno
    "81234.5678",  # pchs_avg_pric
    "98765432",  # evlu_amt
    "88888888.00",  # dnca_tot_amt, verbatim (the parsed float is fine)
    "CURSOR-FK-SENTINEL-9f3a",
    "CURSOR-NK-SENTINEL-c71b",
)

#: ``rt_cd`` key absent altogether — distinct from present-and-``null``.
_NO_RT_CD = object()


def _sentinel_balance_body(rt_cd: Any = "0") -> dict[str, Any]:
    """A success-SHAPED balance page carrying every :data:`_LEAK_SENTINELS`
    value, spelling ``rt_cd`` however the caller asks: the ``'0'`` the broker
    really sends, ``None`` (key present, JSON ``null``), the JSON number ``0``,
    or :data:`_NO_RT_CD` (key absent). The payload is identical in every case —
    which is the point: whether the excerpt is written must not hinge on how
    the success marker happens to be spelled."""
    body: dict[str, Any] = {
        "msg_cd": "MCA00000",
        "msg1": "정상처리 되었습니다.",
        "output1": [
            # A holding the probe never reports on — present only to prove the
            # raw page did not reach the artifact.
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
    """Assert against the SERIALISED artifact, not the in-memory record: what
    gets committed under ``docs/broker-profiles/evidence/`` is the dump."""
    blob = json.dumps(run.to_dict(), ensure_ascii=False)
    for leaked in _LEAK_SENTINELS:
        assert (
            leaked not in blob
        ), f"raw balance body leaked into the artifact: {leaked}"


def test_successful_balance_body_is_never_excerpted_into_the_artifact(
    stock_env: None, wire: Any
) -> None:
    """H1: ``_call_evidence`` runs on EVERY baseline status, including
    ``_BAL_OK`` — i.e. on 100% of runs that get past the baseline. An
    ungated ``text[:N]`` therefore embedded a live balance response (holdings,
    ``pchs_avg_pric``, ``evlu_amt``, ``dnca_tot_amt``, and the raw
    ``ctx_area_*`` continuation cursors) in every artifact, and these artifacts
    are committed under ``docs/broker-profiles/evidence/``.

    ``redact()`` keys on field NAMES and cannot reach inside a raw string leaf,
    so the cap was never a filter — only the gate is. The envelope fields that
    make a stop diagnosable must survive the gate.
    """
    wire(_ScriptedSession([_FakeResponse(_sentinel_balance_body())]))
    run = pc.probe_pca(
        _args(effective_time="2020-01-01T09:00:00+09:00", window_s=1e-9, pace_s=0.0)
    )

    baseline = [
        obs["baseline_call"] for obs in run.observations if "baseline_call" in obs
    ][0]
    # The diagnostic envelope still survives — the gate suppresses the body, not
    # the fields that tell a 429 from a body EGW00201.
    assert baseline["status_kind"] == pc._BAL_OK
    assert baseline["http_status"] == 200
    assert baseline["rt_cd"] == "0"
    assert baseline["body_excerpt"] == ""

    # The probe still did its job off that body.
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
    """The gate must fail CLOSED, not merely ask "did the broker say success?".

    An ``rt_cd``-only gate answers "no" to every body it cannot READ as ``'0'``
    and then records it — so a body the probe MISCLASSIFIES leaks exactly the
    payload the gate exists to suppress. Two shapes do that:

    * ``rt_cd`` absent, or explicitly ``null`` — ``parsed.get('rt_cd')`` is
      ``None``;
    * ``rt_cd`` as the JSON **number** ``0`` — ``str(0 or '').strip()`` is
      ``''``, not ``'0'``, because ``0`` is falsy and the ``or ''`` idiom drops
      it.

    Keying on the payload instead settles all three: the page carries holdings,
    so it is not diagnostic of anything and is never recorded, whatever
    ``rt_cd`` says. The diagnostic envelope (``status_kind``, ``http_status``)
    still is — suppressing the body must not blind the artifact.
    """
    wire(_ScriptedSession([_FakeResponse(_sentinel_balance_body(rt_cd))]))
    run = pc.probe_pca(
        _args(effective_time="2020-01-01T09:00:00+09:00", window_s=1e-9, pace_s=0.0)
    )

    baseline = [
        obs["baseline_call"] for obs in run.observations if "baseline_call" in obs
    ][0]
    assert baseline["body_excerpt"] == "", f"{label} leaked the body"
    # Still diagnosable: the probe reads this page as a rejection (it cannot
    # find rt_cd='0'), and the record says so, with the transport status.
    assert baseline["status_kind"] == pc._BAL_REJECTED
    assert baseline["http_status"] == 200

    _assert_no_sentinel_leaked(run)


def test_read_balance_reports_the_transport_status_alongside_the_kind(
    stock_env: None, wire: Any
) -> None:
    """The HTTP status must survive :func:`pc._read_balance`, which previously
    discarded it in favour of the ``_BAL_*`` kind."""
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


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_arg_adder_defaults(stock_env: None) -> None:
    from tools.broker_probes.common import add_common_args

    parser = argparse.ArgumentParser()
    add_common_args(parser)
    pc.add_ca_args(parser)
    parsed = parser.parse_args([])
    assert parsed.asset == "stock"
    assert parsed.env == "mock"
    assert parsed.event_class == ""


def test_list_shows_ca_as_confirm_gated(capsys: pytest.CaptureFixture[str]) -> None:
    from tools.broker_probes import run as run_module

    run_module._print_table()
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.startswith("P-CA")]
    assert lines, "P-CA should appear in --list output"
    assert "yes" in lines[0]  # requires_confirm column


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


# ---------------------------------------------------------------------------
# pacing across phases (2026-09-17 P-CA trial 1 defect)
# ---------------------------------------------------------------------------


def test_first_poll_is_paced_against_the_preceding_setup_call(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The polling loop paces on ``--poll-ms``, but its pacer must still owe the
    gap left by the last call of the setup phase (the baseline walk, then the
    ``--reference-check`` GET). A fresh pacer carries no outstanding gap, so
    poll #1 went out back-to-back with the reference GET and the broker answered
    with a rate limit — the cash leg of the 2026-09-17 SK텔레콤 trial came back
    CENSORED off a single poll.
    """
    wire(
        _ScriptedSession(
            [
                _balance_body(10),  # baseline walk
                _ksdinfo_body(rows=[{"sht_cd": "005930"}]),  # --reference-check
                _balance_body(11),  # poll #1 — quantity changed, loop ends
            ]
        )
    )
    # After wire(), which installs its own no-op sleep.
    sleeps: list[float] = []
    monkeypatch.setattr("time.monotonic", lambda: 1000.0)  # frozen: only gaps show
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
    # One gap before the reference GET, one before poll #1. Without the carried
    # gap the second sleep never happens.
    assert len(sleeps) == 2, f"expected a gap before every broker call, got {sleeps}"
    assert all(gap == pytest.approx(1.1) for gap in sleeps)


def test_derived_pacer_inherits_the_outstanding_gap() -> None:
    pacer = pc._Pacer(1.1)
    pacer.wait()  # first call is free; arms the gap for the next one
    derived = pacer.derive(5.0)
    assert derived.interval_s == pytest.approx(5.0)
    assert derived._next_allowed_at == pacer._next_allowed_at


# ---------------------------------------------------------------------------
# transient errors: ONE retry, one poll interval apart (2026-09-30 P-CA trial 2)
# ---------------------------------------------------------------------------
#
# 2026-09-30: four attempts to observe SK하이닉스 000660's cash dividend, four
# stops, zero cash-leg observations. The broker said only two things — a
# transport read timeout (twice) and EGW00215, the LEDGER throttle — and the
# harness treated both as "stop at once, never retry". That rule was written
# for 2026-09-17, whose cause was OUR pacing (EGW00201); none of the 09-30
# stops was ours. These tests pin the new policy AND pin that EGW00201 / HTTP
# 429 did not move with it.


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
    """A scripted session whose script may also contain exceptions to RAISE.

    A transport failure is not a response, so it cannot be scripted as one:
    the probe has to meet the same ``requests`` exception the broker handed it
    on 09-30, raised out of ``session.request`` where ``_get`` will see it.
    """

    def request(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        if self._responses and isinstance(self._responses[0], BaseException):
            self.calls.append({"method": "GET", "url": "", "params": {}})
            raise self._responses.pop(0)
        return super().request(*args, **kwargs)


def _retry_records(run: Any) -> list[dict[str, Any]]:
    """Every transient recorded, retried or not. The key is ``retry_evidence``
    and not ``poll_retry_evidence`` (review F8): three of the four phases that
    can write one are not the poll loop, and a harvester filtering on the old
    key counted baseline and reference-check retries as poll retries."""
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
    """Trial 3's shape: poll #8 raised ``ReadTimeout`` and the exception left
    the probe entirely (``run.py`` rc 5, no class_leg_table). One retry carries
    it — the leg is OBSERVED, and the artifact says a retry was spent."""
    session = wire(
        _TransientSession(
            [
                _balance_body(10),  # baseline
                _read_timeout(),  # poll #1 attempt 1 — transport
                _balance_body(11),  # poll #1 attempt 2 — quantity changed
            ]
        )
    )
    run = pc.probe_pca(_poll_args())

    assert run.errors == []
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    # Both ATTEMPTS counted; one poll actually came back with a balance.
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
    """One retry, not a retry loop: a second consecutive transport failure
    stops the run, and the leg is ABORTED (never CENSORED — the window did not
    elapse)."""
    session = wire(
        _TransientSession([_balance_body(10), _read_timeout(), _read_timeout()])
    )
    run = pc.probe_pca(_poll_args())

    row = _leg_row(run, "quantity")
    assert row["status"] == "ABORTED"
    assert row["stop_reason"] == pc._STOP_TRANSIENT
    assert (row["polls_used"], row["polls_completed"]) == (2, 0)
    # One retry SPENT, two transients SEEN: the counter answers "how much
    # extra waiting did this run buy", the records answer "what happened".
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert [r["retried"] for r in _retry_records(run)] == [True, False]
    assert any("twice in a row" in message for message in run.errors)
    assert _stop_evidence(run)["status_kind"] == pc._BAL_TRANSIENT_TRANSPORT
    assert len(session.calls) == 3


def test_one_ledger_throttle_is_retried_once_and_the_run_continues(
    stock_env: None, wire: Any
) -> None:
    """Trial 2's shape: poll #14 answered EGW00215 (HTTP 500, rt_cd='1'), which
    ``is_rate_limited`` does not see, so it fell through to _BAL_REJECTED and
    stopped the run on the spot."""
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
    """A doubled LEDGER throttle IS a rate limit, so the row says
    ``rate_limited`` — a reader must not need to know which broker code fired
    to know the run was throttled."""
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
    """REGRESSION PIN (plan §3). EGW00201 / HTTP 429 mean WE called too fast —
    2026-09-17's cause — and that rule is an account protection, not a
    transport hiccup. The retry policy must not have widened to cover it: one
    attempt, no retry record, ``retries`` untouched.
    """
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
    """The other direction of the EGW00215 rule: a rejection that merely
    MENTIONS the code in ``msg1`` is not the ledger throttle and buys no retry.
    ``_is_ledger_throttled`` keys on ``msg_cd`` exactly, unlike
    ``is_rate_limited``'s substring sweep for EGW00201."""
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
    """The retry waits a WHOLE poll interval, which ``_Pacer.wait()`` alone
    does not give: the failed attempt armed the gap before it went out, so
    after a 20s read timeout the ordinary pacer owes only the remaining 10s of
    a 30s interval. ``_Pacer.defer`` re-arms it from NOW; this pins the 30s.
    """
    clock = [1000.0]

    class _TickingTransientSession(_TransientSession):
        def request(self, *args: Any, **kwargs: Any) -> _FakeResponse:
            try:
                return super().request(*args, **kwargs)
            finally:
                clock[0] += 20.0  # a read timeout burns 20s of wall clock

    wire(
        _TickingTransientSession(
            [_balance_body(10), _read_timeout(), _balance_body(11)]
        )
    )
    sleeps: list[float] = []
    # After wire(), which installs its own no-op sleep.
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
    """Trial 4 died on the FIRST GET of the run and left an artifact with no
    baseline at all. The retry covers the baseline walk, and its record carries
    no ``poll_index`` because no poll had started."""
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
    # The count is published even on a path that never reaches _finalize.
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert [r["phase"] for r in _retry_records(run)] == ["baseline", "baseline"]
    assert len(session.calls) == 2


def test_a_transient_on_the_reference_check_is_retried_then_the_run_continues(
    stock_env: None, wire: Any
) -> None:
    """The reference check is the one call that does not go through
    ``_read_balance`` — and the one a transport exception used to escape from,
    taking the whole run with it."""
    wire(
        _TransientSession(
            [
                _balance_body(10),  # baseline
                _read_timeout(),  # --reference-check attempt 1
                _ksdinfo_body(rows=[{"sht_cd": "005930"}]),  # attempt 2
                _balance_body(11),  # poll #1
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
    """Two consecutive failures say the path to the broker is unhealthy, and
    the polling loop is a far longer walk down it. The run STOPS — but through
    the probe's own signal, so the artifact is written with what it has rather
    than rebuilt by ``run.py``'s catch-all."""
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
    """``requests``' ConnectionError renders the URL it failed on IN FULL, and
    that URL carries CANO — the account number — as a query parameter. These
    artifacts are committed under docs/broker-profiles/evidence/, and
    ``redact()`` keys on field names, so it cannot reach inside this one raw
    string leaf. The query string is stripped before the excerpt is recorded.
    """
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
    """A run that retried nothing has to SAY so, rather than leave a reader to
    infer it from a missing key: someone comparing artifacts across the policy
    change must be able to tell a clean run from one the old code wrote."""
    wire(_ScriptedSession([_balance_body(10), _balance_body(11)]))
    run = pc.probe_pca(_poll_args())

    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    assert _retry_records(run) == []


def test_the_transient_set_is_no_intact_answer_not_any_exception() -> None:
    """``_get`` raises from TWO places and both belong in the set: the request
    itself (timeouts, connection errors) and the BODY READ, where a cut
    chunked transfer or an undecodable gzip surfaces as
    ``ChunkedEncodingError`` / ``ContentDecodingError`` (independent review
    F3 — these were excluded and documented as misconfigurations, so a
    truncated body still escaped the probe as ``run.py`` rc 5).

    A malformed URL or a redirect loop stays out: it is a defect in this probe,
    and retrying it just produces the identical failure twice.
    """
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
    """The scenario behind the set above: the broker answers 200 with a
    chunked body and the connection dies before the terminating chunk.
    ``requests`` raises only when ``_get`` reads ``response.text``."""
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
    """Independent review F4: the ksdinfo path classified the ledger throttle
    BEFORE ``is_rate_limited``, so a 429 body carrying ``EGW00215`` bought a
    retry there and stopped the run at once on the balance walk. One
    classifier, one precedence — HTTP 429 / ``EGW00201`` win."""
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
    pacer.wait()  # arms next_allowed_at = 130.0
    clock[0] = 120.0  # a 20s read timeout burned part of the interval
    pacer.defer(30.0)
    assert pacer._next_allowed_at == pytest.approx(150.0)
    # A shorter deferral must not pull an outstanding longer gap forward.
    pacer.defer(1.0)
    assert pacer._next_allowed_at == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# the tracked runner template (plan §2.2)
# ---------------------------------------------------------------------------


_RUNNER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "broker_probes"
    / "runners"
    / "run_p_ca.sh"
)

#: Sourcing this would print the sentinel. A guard that fires "before any
#: credential sourcing" is only worth the words if its absence is observable.
_CREDENTIAL_SENTINEL = "CREDENTIAL_FILE_WAS_SOURCED"


def test_runner_template_is_tracked_and_executable() -> None:
    """It is in the repository at all — the 09-30 runner was not, and deleted
    itself, so the review could not say which script had run."""
    import os

    assert _RUNNER.is_file(), _RUNNER
    assert os.access(_RUNNER, os.X_OK), f"{_RUNNER} is not executable"


def test_runner_template_parses() -> None:
    import subprocess

    result = subprocess.run(
        ["bash", "-n", str(_RUNNER)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_runner_template_passes_shellcheck_when_it_is_available() -> None:
    import shutil
    import subprocess

    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        pytest.skip("shellcheck is not installed")
    result = subprocess.run(
        [shellcheck, "--severity=warning", str(_RUNNER)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runner_template_carries_no_instance_defaults() -> None:
    """Every ``PCA_*`` instance value must be read WITHOUT a ``:-`` default.
    A default is how one trial's symbol, window or fingerprint silently
    becomes the next trial's."""
    text = _RUNNER.read_text(encoding="utf-8")
    defaulted = set(re.findall(r"\$\{(PCA_[A-Z_]+):-[^}]*\}", text))
    # The only PCA_* variables allowed a default are the three switches, whose
    # default is "off" rather than an instance value.
    assert defaulted <= {
        "PCA_ALLOW_SHARED_CHECKOUT",
        "PCA_REFERENCE_CHECK",
        "PCA_CRON_MARK",
        "PCA_EFFECTIVE",
        "PCA_LOG",
    }, defaulted


def test_runner_template_never_removes_itself() -> None:
    """2026-09-30: the runner self-deleted after its first run, so attempts 3
    and 4 went out through a hand-made copy."""
    text = _RUNNER.read_text(encoding="utf-8")
    assert re.search(r"(?<![\w-])rm(?![\w-])", text) is None, "the runner runs rm"
    # ``$0`` is legitimate exactly once — deriving the checkout from the
    # script's own location. Anywhere else it is the script talking about
    # itself, which is how the 09-30 runner deleted itself.
    self_references = [line for line in text.splitlines() if "$0" in line]
    assert len(self_references) == 1, self_references
    assert "SCRIPT_DIR=" in self_references[0], self_references


def _runner_repo(tmp_path: Path, *, detached: bool, dirty: bool) -> Path:
    """A throwaway git checkout holding a copy of the template, so the guards
    can be exercised against a real ``git`` rather than a stubbed one."""
    import shutil
    import subprocess

    repo = tmp_path / "repo"
    (repo / "tools" / "broker_probes" / "runners").mkdir(parents=True)
    shutil.copy2(_RUNNER, repo / "tools/broker_probes/runners/run_p_ca.sh")
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
        "PCA_ENV_FILE": str(env_file),
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
    """#793: a shared checkout lets a parallel lane move the branch under a
    running probe, and ``repo_commit`` is then stamped with a non-main commit.
    The guard must fire BEFORE the credential file is sourced."""
    repo = _runner_repo(tmp_path, detached=False, dirty=False)
    result = _run_runner(repo, tmp_path)

    assert result.returncode != 0
    assert "ABORT:" in result.stdout
    assert "not a detached worktree" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_aborts_on_a_dirty_checkout(tmp_path: Path) -> None:
    """The 00:20 cron attempt on 2026-09-30 died here — correctly — on an
    untracked backup file in the shared checkout. Same guard, still before any
    credential sourcing."""
    repo = _runner_repo(tmp_path, detached=True, dirty=True)
    result = _run_runner(repo, tmp_path)

    assert result.returncode != 0
    assert "ABORT:" in result.stdout
    assert "is dirty" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_override_skips_the_checkout_guards_and_says_so(
    tmp_path: Path,
) -> None:
    """The escape hatch exists (plan §5) but is never silent: with it the run
    gets past the dirty/branch guards and is logged as an override."""
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
    # It still stops: the next guard is the required-env check, which has no
    # instance defaults to fall back on.
    assert result.returncode != 0
    assert "required env PCA_LOG is unset" in result.stdout


def test_runner_aborts_when_head_is_not_an_ancestor_of_origin_main(
    tmp_path: Path,
) -> None:
    """The third checkout guard, with the input that actually trips it: a
    detached, clean worktree carrying a commit that never reached
    ``origin/main``. Evidence has to be produced by merged code (#793)."""
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
    """The other direction: the guards must not be a blanket refusal. A clean,
    detached checkout that IS an ancestor of origin/main gets past all three
    and stops at the next gate instead — which here is the missing python."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path)
    assert "checkout ok:" in result.stdout
    assert "required probes_ca.py fixes present" in result.stdout
    assert "ABORT: required env PCA_PYTHON is unset" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_aborts_when_the_checkout_lacks_the_transient_retry_fix(
    tmp_path: Path,
) -> None:
    """A checkout without the fix this trial depends on must not be used to
    produce evidence — the 2026-09-30 runner already guarded ``pacer.derive(``
    for the same reason, and the retry policy joins it."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    (repo / "tools/broker_probes/probes_ca.py").write_text(
        "pacer.derive(\n", encoding="utf-8"
    )
    import subprocess

    for argv in (["add", "-A"], ["commit", "-q", "-m", "drop the retry fix"]):
        subprocess.run(["git", "-C", str(repo), *argv], check=True, capture_output=True)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path)
    assert result.returncode == 4
    assert "missing '_BAL_TRANSIENT'" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


# ---------------------------------------------------------------------------
# the pre-flight holding check (independent review F1/F2)
# ---------------------------------------------------------------------------
#
# The runner used to ask shared/kis/client.py::get_stock_balance whether the
# symbol was held. That function returns [] on EVERY failure (non-200,
# non-JSON, rt_cd != '0', and a catch-all `except Exception`) and sends empty
# continuation cursors, so it reads page 1 only. Both defects turn a failure
# or a page-2 holding into "held qty=0" — the 2026-09-30 10:58 misdiagnosis,
# reproduced by the tool the fix was built on.


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
    """The other direction: a completed walk that found nothing IS HELD=0, and
    the runner is entitled to stop on it. The failure form must not be used to
    paper over a genuine absence."""
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
    # Both transients are announced, and only the first claims a retry: the
    # callback now fires for every transient, so the wording has to follow.
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
    """F6, one step earlier than the probe: the mock stock account holds 25
    rows across 2 pages and ``get_stock_balance`` returns 20, so a target on
    page 2 read as "not held" and the runner aborted before the probe ever
    started."""
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
    """Review F4: the capped walk's ``parsed`` is the last SUCCESSFUL page, so
    keying the detail on "is there a body" printed a success code as the
    reason a run was abandoned — ``CAPPED:MCA00000``, which a reader looks up
    and finds 정상처리."""
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
    """A stand-in interpreter answering the four calls the runner makes.

    It lives OUTSIDE the checkout, like the real one: a freshly added detached
    worktree has no ``.venv``, and installing one into it is forbidden, so the
    runner takes ``PCA_PYTHON`` and proves separately that the code it loads is
    this checkout's (review F1). The earlier version of this helper planted a
    fake ``.venv`` INSIDE the temp repo, which is exactly what hid the defect:
    the README recipe could never have worked.
    """
    body = [
        "#!/bin/sh",
        'case "$1" in',
        "  -c)",
        '    case "$2" in',
        '      *__file__*) printf "%s\\n" "$FAKE_MODULE_PATH" ;;',
        '      *) printf "%s\\n" "$PCA_EXPECT_ACCOUNT_FP" ;;',
        "    esac",
        "    ;;",
        "  -m)",
        '    case "$2" in',
        f'      tools.broker_probes.probes_ca) printf "%s\\n" {holding_line!r};'
        f" exit {holding_rc} ;;",
        '      tools.broker_probes.run) for a in "$@"; do '
        f'printf "%s\\n" "$a" >> {str(dump)!r}; done ;;',
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
        "PCA_ENV_FILE": str(env_file),
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


def test_runner_passes_a_space_separated_iso_time_as_one_argv_word(
    tmp_path: Path,
) -> None:
    """Independent review F6: ``--effective-time $PCA_EFFECTIVE`` unquoted
    splits ``2026-10-01 09:00:00+09:00`` — a value the probe's own
    ``datetime.fromisoformat`` accepts — into two argv words, and argparse
    rejects the run before it starts."""
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


def test_runner_adds_the_reference_check_flag_only_when_asked(
    tmp_path: Path,
) -> None:
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env={"PCA_REFERENCE_CHECK": "1"}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--reference-check" in argv


def test_runner_aborts_when_the_holding_check_reports_a_failure(
    tmp_path: Path,
) -> None:
    """Independent review F1: the gate must distinguish "the query failed"
    from "nothing is held", and never start the probe on the former."""
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
    """The other direction: HELD=0 from a COMPLETED walk is a real absence and
    gets its own line, so the two verdicts stay distinguishable in the log."""
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


# ---------------------------------------------------------------------------
# the retry must not outlive the window (independent review F5)
# ---------------------------------------------------------------------------


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
    """Baseline, then one poll that fails transiently after ``burn_on_transient``
    seconds. ``--window-s`` is 60 and the poll interval 30s."""
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
    """The review's scenario: window 60s, the poll fails 80s in. Retrying would
    defer another 30s and poll at ~110s, then a CENSORED verdict would rest on
    a reading taken outside the window it claims to cover. The window has
    elapsed, so the loop simply ends — and the transient is still recorded."""
    run, session = _run_windowed_poll(wire, monkeypatch, burn_on_transient=80.0)

    row = _leg_row(run, "quantity")
    assert row["status"] == "CENSORED"
    assert "stop_reason" not in row
    assert len(session.calls) == 2, "the retry fired outside the window"
    assert run.measurements["polls_used"] == 1
    assert run.measurements["polls_completed"] == 0
    # No retry was spent, but the transient is not swallowed either.
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    record = _retry_records(run)
    assert len(record) == 1
    assert record[0]["retried"] is False
    assert record[0]["phase"] == "poll"
    assert run.measurements["polled_elapsed_s"] == pytest.approx(80.0)


def test_a_transient_inside_the_window_still_buys_its_retry(
    stock_env: None, wire: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other direction of the same guard: the deadline refuses the retry
    only when the window is actually over."""
    run, session = _run_windowed_poll(wire, monkeypatch, burn_on_transient=10.0)

    assert run.errors == []
    assert len(session.calls) == 3
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    assert _retry_records(run)[0]["retried"] is True
    assert _leg_row(run, "quantity")["status"] == "OBSERVED"


# ---------------------------------------------------------------------------
# runner: interpreter provenance, inter-process pacing, early config refusal
# ---------------------------------------------------------------------------


def test_runner_refuses_an_interpreter_that_loads_another_checkout(
    tmp_path: Path,
) -> None:
    """Review F1's consequence. The interpreter is the MAIN checkout's venv, so
    the code it resolves is not automatically this worktree's — and
    ``repo_commit`` and the results directory both follow the loaded module,
    not the runner's ``$REPO``. Without this check the clean/detached/ancestor
    guards would vouch for a tree that never ran."""
    result, argv = _run_runner_end_to_end(
        tmp_path,
        extra_env={"FAKE_MODULE_PATH": "/some/other/checkout/probes_ca.py"},
    )
    assert result.returncode != 0
    assert "resolves OUTSIDE the checkout" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert argv == []


def test_runner_paces_the_probe_against_the_holding_check(tmp_path: Path) -> None:
    """Review F2: the holding check and the probe are two processes with
    independent pacers, so the probe's baseline GET would follow the check's
    last GET with no gap — the back-to-back pair that produced the 2026-09-17
    EGW00201 stop, which this harness keeps as "stop, never retry"."""
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
    """Review F3: a pure configuration error must not cost broker calls. The
    check moved into the env step, ahead of the credential source and the
    holding walk."""
    result, argv = _run_runner_end_to_end(
        tmp_path, extra_env={"PCA_EVENT_CLASS": "split"}
    )
    assert result.returncode != 0
    assert "set PCA_EFFECTIVE" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr
    assert "held qty" not in result.stdout
    assert argv == []
