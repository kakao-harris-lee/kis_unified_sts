"""Unit tests for the P-BAL balance-pagination probe (``tools/broker_probes``).

P-BAL exists because a runtime trace found that ``shared/kis/client.py`` reads one
page of every balance query and cannot notice it, while
``services/trading/broker_verification.py`` turns a "missing" position into
``remove_position(reason="broker_absent")`` (:187-190). The probe measures the page
size so that consequence stops being inference.

The properties these tests guard are the ones a code read at review time cannot
confirm:

1. **The verdict is derived, not self-reported.** On a small account the honest
   answer is "page size UNESTABLISHED, here is a lower bound" — never "page size =
   8" and never "no truncation risk". All three verdict branches are exercised,
   including the fail-open trap where our own page cap ended the walk.
2. **A total row count is never reported when OUR cap stopped the walk.** The
   prior pagination probe (P-5b) hit exactly that wall.
3. **Both continuation keys are recorded per page.** The prior campaign saw a case
   where only one of the two moved; a single boolean would have erased it.
4. **The module is structurally read-only.** Asserted against the module's own
   AST, because a comment promising "no order path" is not a guarantee.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import pytest

from tools.broker_probes import probes_balance as pb
from tools.broker_probes.common import ProbeError, SafetyViolation
from tools.broker_probes.registry import coverage_report, get

_ACCOUNT = "1234567890"


# ---------------------------------------------------------------------------
# fixtures / doubles
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal ``requests.Response`` stand-in — status, body, HEADERS."""

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


class _ScriptedSession:
    """Returns a scripted response per call and records what was sent."""

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
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "params": dict(params),
            }
        )
        if not self._responses:
            raise AssertionError("probe issued more calls than the script provides")
        return self._responses.pop(0)

    def close(self) -> None:
        self.closed = True


class _ExplodingSession:
    """Any contact is a test failure."""

    def request(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("probe contacted the broker when it must not")

    def close(self) -> None:
        return None


class _FakeAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer test", "appkey": "k", "appsecret": "s"}


def _clear_ambient_kis_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the legacy fallback vars so a host ``.env`` cannot leak into a test."""
    for name in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_TOKEN_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def stock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export exactly the env vars ``resolve_credentials('stock')`` reads."""
    _clear_ambient_kis_env(monkeypatch)
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_STOCK_ACCOUNT_NO", _ACCOUNT)


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export exactly the env vars ``resolve_credentials('futures')`` reads."""
    _clear_ambient_kis_env(monkeypatch)
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replace auth + transport so a walk runs offline."""

    def _wire(session: Any) -> Any:
        monkeypatch.setattr("requests.Session", lambda: session)
        monkeypatch.setattr(
            "shared.kis.auth.KISAuthManager",
            lambda cfg, use_singleton=True: _FakeAuth(),
        )
        monkeypatch.setattr(pb, "build_auth_config", lambda creds, cache: object())
        monkeypatch.setattr(pb, "probe_token_cache_dir", lambda explicit: tmp_path)
        return session

    return _wire


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "asset": "stock",
        "env": "real",
        "confirm": True,
        "max_pages": 10,
        "inter_page_s": 0.0,
        "known_page_size": 0,
        "known_page_size_source": "",
        "record_raw_continuation_keys": False,
        "token_cache_dir": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _stock_page(
    rows: int,
    *,
    fk: str = "",
    nk: str = "",
    rt_cd: str = "0",
    tr_cont: str = "",
) -> _FakeResponse:
    body: dict[str, Any] = {
        "rt_cd": rt_cd,
        "msg_cd": "MCA00000" if rt_cd == "0" else "APBK0919",
        "msg1": "정상처리 되었습니다." if rt_cd == "0" else "조회할 자료가 없습니다.",
        "output1": [
            {"pdno": f"00593{index % 10}", "hldg_qty": "1"} for index in range(rows)
        ],
        "output2": [{"tot_evlu_amt": "0"}],
        "ctx_area_fk100": fk,
        "ctx_area_nk100": nk,
    }
    return _FakeResponse(body, headers={"tr_cont": tr_cont} if tr_cont else {})


# ---------------------------------------------------------------------------
# registry metadata
# ---------------------------------------------------------------------------


def test_registry_entry_is_read_only_and_confirm_gated() -> None:
    spec = get("P-BAL")
    assert spec.kind == "REAL_READ_ONLY"
    assert spec.emits_orders is False
    assert spec.requires_confirm is True
    assert spec.supported is True
    assert spec.entrypoint == "tools.broker_probes.probes_balance:probe_pbal"


def test_registry_lookup_is_case_and_separator_insensitive() -> None:
    assert get("p-bal") is get("P-BAL") is get("P_BAL")


def test_probe_claims_no_verification_profile_bound() -> None:
    """Page size is a count and the verdict is categorical — no latency bound."""
    assert get("P-BAL").bounds_keys == ()


def test_instance_fields_use_existing_slots_only() -> None:
    """``position_balance_margin`` has no ``.pagination`` key; do not invent one."""
    assert get("P-BAL").instance_fields == (
        "capabilities.position_balance_margin.evidence_refs",
        "capabilities.position_balance_margin.status",
    )


def test_followup_probe_does_not_inflate_the_ratified_counts() -> None:
    report = coverage_report()
    assert report["canonical_count"] == 12
    assert report["census_count"] == 4
    assert "P-BAL" not in report["canonical_12"]
    assert "P-BAL" not in report["census_4"]
    assert "P-BAL" not in report["order_emitting"]


# ---------------------------------------------------------------------------
# structural read-only property (module AST — not prose)
# ---------------------------------------------------------------------------


def _module_ast() -> ast.Module:
    return ast.parse(Path(pb.__file__).read_text(encoding="utf-8"))


def test_module_has_no_mutating_http_method_literal() -> None:
    """No ``"POST"``/``"PUT"``/``"PATCH"``/``"DELETE"`` string exists to pass anywhere."""
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


def test_module_defines_no_order_submitting_helper() -> None:
    names = {
        node.name
        for node in ast.walk(_module_ast())
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    banned = ("submit", "order", "cancel", "replace", "place", "rvsecncl")
    assert not [name for name in names if any(t in name.lower() for t in banned)]


def test_module_does_not_import_the_order_probe_module() -> None:
    """Importing ``probes_order`` would put order paths in this module's graph."""
    imported: set[str] = set()
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not [name for name in imported if "probes_order" in name]


def test_allowlist_is_three_balance_inquiries_and_nothing_else() -> None:
    assert {entry.tr_id for entry in pb.ALLOWLIST} == {
        "TTTC8434R",
        "VTTC8434R",
        "CTFO6118R",
    }
    for entry in pb.ALLOWLIST:
        assert entry.path.endswith("inquire-balance")
        assert "/order" not in entry.path


def test_allowlist_carries_no_mock_futures_entry() -> None:
    """Mock futures balance is broker-unsupported; admitting it would be a lie."""
    futures = [e for e in pb.ALLOWLIST if "futureoption" in e.path]
    assert [e.tr_id for e in futures] == ["CTFO6118R"]
    assert not [e for e in futures if e.tr_id.startswith("V")]


# ---------------------------------------------------------------------------
# read-only enforcement
# ---------------------------------------------------------------------------


def test_get_refuses_a_non_allowlisted_path_before_any_contact() -> None:
    session = _ExplodingSession()
    with pytest.raises(SafetyViolation, match="read-only allowlist"):
        pb._get(
            session,
            _FakeAuth(),
            base_url=pb.REAL_BASE_URL,
            path="/uapi/domestic-stock/v1/trading/order-cash",
            tr_id="TTTC0012U",
            params={},
        )


def test_get_refuses_an_allowlisted_tr_on_the_wrong_path() -> None:
    with pytest.raises(SafetyViolation, match="read-only allowlist"):
        pb._get(
            _ExplodingSession(),
            _FakeAuth(),
            base_url=pb.REAL_BASE_URL,
            path="/uapi/domestic-futureoption/v1/trading/order",
            tr_id="TTTC8434R",
            params={},
        )


# ---------------------------------------------------------------------------
# truncation verdict — three branches, computed from the data
# ---------------------------------------------------------------------------


def test_single_page_records_a_lower_bound_and_never_a_page_size() -> None:
    """The critical honesty requirement: 8 rows on one page is NOT page size 8."""
    result = pb.truncation_verdict(page_row_counts=[8], termination=pb._TERM_BROKER_END)
    assert result["verdict"] == pb._RISK_UNESTABLISHED
    assert result["page_size"] is None
    assert result["page_size_source"] == pb._PAGE_SIZE_UNESTABLISHED
    assert result["page_size_lower_bound"] == 8
    assert result["holdings_total"] == 8
    assert "LOWER BOUND" in result["rationale"]


def test_multi_page_walk_demonstrates_the_truncation_risk() -> None:
    result = pb.truncation_verdict(
        page_row_counts=[15, 15], termination=pb._TERM_BROKER_END
    )
    assert result["verdict"] == pb._RISK_DEMONSTRATED
    assert result["page_size"] == 15
    assert result["page_size_source"] == pb._PAGE_SIZE_MEASURED
    assert result["page_size_lower_bound"] is None
    assert result["holdings_total"] == 30


def test_known_page_size_with_broker_end_below_it_is_not_demonstrated() -> None:
    result = pb.truncation_verdict(
        page_row_counts=[8],
        termination=pb._TERM_BROKER_END,
        known_page_size=15,
        known_page_size_source="P-5b-20260731T014917Z",
    )
    assert result["verdict"] == pb._RISK_NOT_DEMONSTRATED
    assert result["page_size"] == 15
    assert result["page_size_source"] == pb._PAGE_SIZE_OPERATOR
    assert result["holdings_total"] == 8
    assert "not a property of the code" in result["rationale"]


def test_cap_terminated_walk_cannot_claim_not_demonstrated() -> None:
    """The fail-open trap: rows-so-far below a known page size proves nothing."""
    result = pb.truncation_verdict(
        page_row_counts=[8],
        termination=pb._TERM_CAP,
        known_page_size=15,
        known_page_size_source="prior run",
    )
    assert result["verdict"] == pb._RISK_UNESTABLISHED
    assert result["page_size"] == 15
    assert result["holdings_total"] is None
    assert result["holdings_total_lower_bound"] == 8
    assert "fail-open" in result["rationale"]


def test_cap_terminated_walk_reports_no_total_row_count() -> None:
    result = pb.truncation_verdict(page_row_counts=[15, 15], termination=pb._TERM_CAP)
    assert result["verdict"] == pb._RISK_DEMONSTRATED
    assert result["holdings_total"] is None
    assert result["holdings_total_lower_bound"] == 30
    assert result["holdings_total_established"] is False


def test_measured_page_size_wins_over_operator_value_and_disagreement_is_reported() -> (
    None
):
    result = pb.truncation_verdict(
        page_row_counts=[15, 4],
        termination=pb._TERM_BROKER_END,
        known_page_size=100,
        known_page_size_source="official spec claim",
    )
    assert result["page_size"] == 15
    assert result["page_size_source"] == pb._PAGE_SIZE_MEASURED
    assert "page_size_disagreement" in result


def test_a_larger_later_page_leaves_the_page_size_unestablished() -> None:
    """If page 1 was not the largest page it was not a full page."""
    result = pb.truncation_verdict(
        page_row_counts=[4, 15], termination=pb._TERM_BROKER_END
    )
    assert result["page_size"] is None
    assert result["verdict"] == pb._RISK_UNESTABLISHED
    assert "page_size_shape_note" in result


def test_verdict_vocabulary_is_exactly_three_valued() -> None:
    assert len(set(pb._VERDICTS)) == 3
    assert len(set(pb._TERMINATION_CAUSES)) == 3


def test_unknown_termination_cause_is_refused() -> None:
    with pytest.raises(ProbeError, match="unknown termination cause"):
        pb.truncation_verdict(page_row_counts=[1], termination="MAYBE")


# ---------------------------------------------------------------------------
# walk behaviour — termination classification and per-key recording
# ---------------------------------------------------------------------------


def test_broker_end_of_set_is_classified_as_such(stock_env: None, wire: Any) -> None:
    session = wire(_ScriptedSession([_stock_page(8)]))
    run = pb.probe_pbal(_args())

    assert run.environment == "REAL_PROD"
    assert run.errors == []
    assert run.measurements["termination_cause"] == pb._TERM_BROKER_END
    assert run.measurements["truncation_risk"]["verdict"] == pb._RISK_UNESTABLISHED
    assert run.measurements["truncation_risk"]["page_size_lower_bound"] == 8
    assert len(session.calls) == 1
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["params"]["CTX_AREA_FK100"] == ""


def test_our_cap_is_classified_as_our_cap_not_broker_end(
    stock_env: None, wire: Any
) -> None:
    session = wire(
        _ScriptedSession(
            [
                _stock_page(15, fk="F1", nk="N1", tr_cont="M"),
                _stock_page(15, fk="F2", nk="N2", tr_cont="M"),
            ]
        )
    )
    run = pb.probe_pbal(_args(max_pages=2))

    assert run.measurements["termination_cause"] == pb._TERM_CAP
    assert "--max-pages" in run.measurements["termination_detail"]
    risk = run.measurements["truncation_risk"]
    assert risk["verdict"] == pb._RISK_DEMONSTRATED
    assert risk["page_size"] == 15
    assert risk["holdings_total"] is None
    assert risk["holdings_total_lower_bound"] == 30
    # The second call must carry the keys the first response returned.
    assert session.calls[1]["params"]["CTX_AREA_FK100"] == "F1"
    assert session.calls[1]["params"]["CTX_AREA_NK100"] == "N1"
    assert session.calls[1]["headers"]["tr_cont"] == pb._TR_CONT_REQUEST_NEXT


def test_only_one_key_advancing_is_recorded_per_key(stock_env: None, wire: Any) -> None:
    """The prior campaign's shape: FK frozen, NK moving. A boolean would hide it."""
    wire(
        _ScriptedSession(
            [
                _stock_page(15, fk="SAME", nk="N1"),
                _stock_page(15, fk="SAME", nk="N2"),
                _stock_page(2),
            ]
        )
    )
    run = pb.probe_pbal(_args())

    assert run.measurements["termination_cause"] == pb._TERM_BROKER_END
    assert run.measurements["continuation_key_asymmetry"] == [
        {"page": 1, "fk_advanced": False, "nk_advanced": True}
    ]
    page1 = run.observations[2]  # [0] = attestation, [1] = page 0
    assert page1["page"] == 1
    assert page1["continuation_keys"]["fk"]["advanced"] is False
    assert page1["continuation_keys"]["nk"]["advanced"] is True
    assert (
        page1["continuation_keys"]["fk"]["fingerprint"]
        != page1["continuation_keys"]["nk"]["fingerprint"]
    )
    # Page 0 has no predecessor, so "advanced" must not claim anything.
    assert run.observations[1]["continuation_keys"]["fk"]["advanced"] is None


def test_raw_continuation_keys_are_withheld_unless_requested(
    stock_env: None, wire: Any
) -> None:
    wire(
        _ScriptedSession([_stock_page(3, fk="SECRETFK", nk="SECRETNK"), _stock_page(1)])
    )
    run = pb.probe_pbal(_args())
    blob = json.dumps(run.to_dict(), ensure_ascii=False)
    assert "SECRETFK" not in blob
    assert "raw" not in run.observations[1]["continuation_keys"]["fk"]


def test_raw_continuation_keys_are_included_when_requested(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_stock_page(3, fk="RAWFK", nk="RAWNK"), _stock_page(1)]))
    run = pb.probe_pbal(_args(record_raw_continuation_keys=True))
    assert run.observations[1]["continuation_keys"]["fk"]["raw"] == "RAWFK"


def test_non_advancing_keys_stop_the_walk_as_an_error(
    stock_env: None, wire: Any
) -> None:
    wire(
        _ScriptedSession(
            [
                _stock_page(15, fk="F1", nk="N1"),
                _stock_page(15, fk="F1", nk="N1"),
            ]
        )
    )
    run = pb.probe_pbal(_args())
    assert run.measurements["termination_cause"] == pb._TERM_ERROR
    assert any("did not advance" in message for message in run.errors)
    assert run.measurements["truncation_risk"]["holdings_total"] is None


def test_tr_cont_end_code_stops_the_walk_as_broker_end(
    stock_env: None, wire: Any
) -> None:
    """The real stock endpoint's shape (P-BAL-20260731T083102Z): tr_cont='D'
    with a static padded cursor still present in the body. The broker's end
    signal must win — one request, no error, no re-fetch of the same page."""
    session = wire(_ScriptedSession([_stock_page(8, fk="PADDED-CURSOR", tr_cont="D")]))
    run = pb.probe_pbal(_args())

    assert run.errors == []
    assert run.measurements["termination_cause"] == pb._TERM_BROKER_END
    assert "tr_cont='D'" in run.measurements["termination_detail"]
    assert len(session.calls) == 1
    assert run.measurements["truncation_risk"]["holdings_total"] == 8


def test_tr_cont_f_is_more_follows_and_the_walk_continues(
    stock_env: None, wire: Any
) -> None:
    """KIS's official inquire_balance example recurses on tr_cont in ('M', 'F');
    'F' must not be misread as end-of-set."""
    session = wire(
        _ScriptedSession(
            [
                _stock_page(15, fk="F1", nk="N1", tr_cont="F"),
                _stock_page(3, fk="F2", nk="N2", tr_cont="D"),
            ]
        )
    )
    run = pb.probe_pbal(_args())

    assert run.measurements["termination_cause"] == pb._TERM_BROKER_END
    assert len(session.calls) == 2
    assert run.measurements["truncation_risk"]["holdings_total"] == 18


def test_duplicate_refetch_before_end_code_is_not_double_counted(
    stock_env: None, wire: Any
) -> None:
    """Page 0 without a tr_cont header forces a key-driven re-request; the
    repeat page then carries tr_cont='D'. End-of-set is honoured, but the
    repeated page's rows are the same rows again and must not enter a total."""
    wire(
        _ScriptedSession(
            [
                _stock_page(8, fk="SAME", nk="SAME2"),
                _stock_page(8, fk="SAME", nk="SAME2", tr_cont="D"),
            ]
        )
    )
    run = pb.probe_pbal(_args())

    assert run.errors == []
    assert run.measurements["termination_cause"] == pb._TERM_BROKER_END
    assert run.measurements["duplicate_final_page_excluded_from_totals"] is True
    assert run.measurements["pages_walked"] == 2
    assert run.measurements["truncation_risk"]["holdings_total"] == 8
    assert run.measurements["rows_with_positive_qty_total"] == 8


def test_more_code_with_no_cursor_is_an_error_not_end_of_set(
    stock_env: None, wire: Any
) -> None:
    """tr_cont says more follows but no continuation key came back: there is no
    cursor to continue with, so the total is a lower bound, not a total."""
    wire(_ScriptedSession([_stock_page(15, tr_cont="M")]))
    run = pb.probe_pbal(_args())

    assert run.measurements["termination_cause"] == pb._TERM_ERROR
    assert any("no cursor" in message for message in run.errors)
    assert run.measurements["truncation_risk"]["holdings_total"] is None


def test_static_keys_without_end_code_stay_an_error(
    stock_env: None, wire: Any
) -> None:
    """A frozen cursor while tr_cont still claims more follows is a genuine
    anomaly — the loop-risk classification must survive the tr_cont fix."""
    wire(
        _ScriptedSession(
            [
                _stock_page(15, fk="F1", nk="N1", tr_cont="M"),
                _stock_page(15, fk="F1", nk="N1", tr_cont="M"),
            ]
        )
    )
    run = pb.probe_pbal(_args())

    assert run.measurements["termination_cause"] == pb._TERM_ERROR
    assert any("did not advance" in message for message in run.errors)
    assert run.measurements["truncation_risk"]["holdings_total"] is None


def test_broker_rejection_is_an_error_termination(stock_env: None, wire: Any) -> None:
    wire(_ScriptedSession([_stock_page(0, rt_cd="1")]))
    run = pb.probe_pbal(_args())
    assert run.measurements["termination_cause"] == pb._TERM_ERROR
    assert run.measurements["truncation_risk"]["verdict"] == pb._RISK_UNESTABLISHED
    assert any("rejected page 0" in message for message in run.errors)


def test_kiok0560_empty_set_is_an_answer_not_a_rejection(
    stock_env: None, wire: Any
) -> None:
    """The real futures balance pairs the empty-result msg_cd KIOK0560 with
    rt_cd='7' (P-BAL-20260731T114054Z) where the stock sibling uses rt_cd='0'.
    An empty set is an answer: no error, broker end-of-set, explicit skip."""
    wire(
        _ScriptedSession(
            [
                _FakeResponse(
                    {
                        "rt_cd": "7",
                        "msg_cd": "KIOK0560",
                        "msg1": "조회할 내용이 없습니다",
                        "output1": [],
                    }
                )
            ]
        )
    )
    run = pb.probe_pbal(_args())

    assert run.errors == []
    assert run.measurements["termination_cause"] == pb._TERM_BROKER_END
    assert run.measurements["truncation_risk"]["verdict"] == pb._RISK_UNESTABLISHED
    assert any(entry["what"] == "page-size determination" for entry in run.skips)


def test_kiok0560_is_the_only_nonzero_rt_cd_read_as_empty(
    stock_env: None, wire: Any
) -> None:
    """Any other msg_cd with a non-zero rt_cd must stay a rejection."""
    wire(
        _ScriptedSession(
            [
                _FakeResponse(
                    {
                        "rt_cd": "7",
                        "msg_cd": "APMP0001",
                        "msg1": "증거금구분코드은(는) 필수입력 항목입니다.",
                        "output1": [],
                    }
                )
            ]
        )
    )
    run = pb.probe_pbal(_args())

    assert run.measurements["termination_cause"] == pb._TERM_ERROR
    assert any("rejected page 0" in message for message in run.errors)


def test_empty_balance_is_an_explicit_skip_not_a_negative(
    stock_env: None, wire: Any
) -> None:
    wire(_ScriptedSession([_stock_page(0)]))
    run = pb.probe_pbal(_args())
    assert any(entry["what"] == "page-size determination" for entry in run.skips)
    assert run.measurements["truncation_risk"]["verdict"] == pb._RISK_UNESTABLISHED


def test_tr_cont_header_is_read_and_recorded(stock_env: None, wire: Any) -> None:
    wire(_ScriptedSession([_stock_page(5, tr_cont="D")]))
    run = pb.probe_pbal(_args())
    assert run.measurements["tr_cont_header_observed"] is True
    assert run.observations[1]["tr_cont_response"] == "D"
    # Only "M" is code-evidenced as "more follows" (client.py:354).
    assert run.observations[1]["tr_cont_more_code_evidenced"] is False


def test_runtime_visible_row_count_is_recorded_separately(
    stock_env: None, wire: Any
) -> None:
    """The runtime drops ``hldg_qty <= 0`` rows, but they still occupy a page."""
    page = _stock_page(3)
    page._body["output1"][0]["hldg_qty"] = "0"
    wire(_ScriptedSession([page]))
    run = pb.probe_pbal(_args())
    assert run.observations[1]["rows"] == 3
    assert run.observations[1]["rows_with_positive_qty"] == 2
    assert run.measurements["rows_with_positive_qty_total"] == 2


# ---------------------------------------------------------------------------
# targets: mock-futures skip, environment labelling, dry-run
# ---------------------------------------------------------------------------


def test_mock_futures_skips_with_the_unsupported_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Broker-unsupported must be a SKIP, and must not need credentials at all."""
    for name in (
        "KIS_FUTURES_APP_KEY",
        "KIS_FUTURES_APP_SECRET",
        "KIS_FUTURES_ACCOUNT_NO",
        "KIS_APP_KEY",
        "KIS_APP_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("requests.Session", lambda: _ExplodingSession())

    run = pb.probe_pbal(_args(asset="futures", env="mock"))

    assert run.environment == "MOCK_VTS"
    assert run.errors == []
    assert len(run.skips) == 1
    assert "선물 잔고조회 미지원" in run.skips[0]["reason"]
    assert "1031-1033" in run.skips[0]["reason"]
    assert run.measurements["target_supported"] is False
    assert run.measurements["truncation_risk"] is None


def test_real_futures_target_is_supported(futures_env: None, wire: Any) -> None:
    """--asset futures --env real uses CTFO6118R and the FK200/NK200 pair."""
    session = wire(
        _ScriptedSession(
            [
                _FakeResponse(
                    {
                        "rt_cd": "0",
                        "output1": [{"pdno": "101S6000", "cblc_qty": "1"}],
                        "ctx_area_fk200": "",
                        "ctx_area_nk200": "",
                    }
                )
            ]
        )
    )
    run = pb.probe_pbal(_args(asset="futures", env="real"))
    assert run.measurements["target"]["tr_id"] == "CTFO6118R"
    assert run.measurements["target"]["continuation_key_pair"] == [
        "CTX_AREA_FK200",
        "CTX_AREA_NK200",
    ]
    assert "CTX_AREA_FK200" in session.calls[0]["params"]
    # REAL_PROD rejects the runtime's param set without these two (rt_cd=7
    # APMP0001, P-BAL-20260731T084304Z); KIS's official example marks both 필수.
    assert session.calls[0]["params"]["MGNA_DVSN"] == "01"
    assert session.calls[0]["params"]["EXCC_STAT_CD"] == "1"


def test_mock_stock_target_uses_the_mock_tr_and_host(
    stock_env: None, wire: Any
) -> None:
    session = wire(_ScriptedSession([_stock_page(2)]))
    run = pb.probe_pbal(_args(env="mock"))
    assert run.environment == "MOCK_VTS"
    assert run.measurements["target"]["tr_id"] == "VTTC8434R"
    assert session.calls[0]["url"].startswith(pb.MOCK_BASE_URL)


def test_real_stock_target_uses_the_real_tr_and_host(
    stock_env: None, wire: Any
) -> None:
    session = wire(_ScriptedSession([_stock_page(2)]))
    run = pb.probe_pbal(_args(env="real"))
    assert run.measurements["target"]["tr_id"] == "TTTC8434R"
    assert session.calls[0]["url"].startswith(pb.REAL_BASE_URL)


def test_dry_run_contacts_no_broker(
    monkeypatch: pytest.MonkeyPatch, stock_env: None
) -> None:
    monkeypatch.setattr("requests.Session", lambda: _ExplodingSession())
    run = pb.probe_pbal(_args(confirm=False))
    assert run.mode == "dry-run"
    assert run.errors == []
    assert "termination_cause" not in run.measurements
    assert any("would_send" in obs for obs in run.observations)


# ---------------------------------------------------------------------------
# preconditions
# ---------------------------------------------------------------------------


def test_known_page_size_without_a_source_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="known-page-size-source"):
        pb.probe_pbal(_args(known_page_size=15))


def test_zero_max_pages_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="max-pages"):
        pb.probe_pbal(_args(max_pages=0))


def test_unknown_env_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--env"):
        pb.probe_pbal(_args(env="paper"))


def test_unknown_asset_is_refused(stock_env: None) -> None:
    with pytest.raises(ProbeError, match="--asset"):
        pb.probe_pbal(_args(asset="bond"))


def test_arg_adder_defaults_to_the_target_that_matters() -> None:
    from tools.broker_probes.common import add_common_args

    parser = argparse.ArgumentParser()
    add_common_args(parser)
    pb.add_balance_args(parser)
    parsed = parser.parse_args([])
    assert parsed.asset == "stock"
    assert parsed.env == "real"
    assert parsed.max_pages == 10
