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
