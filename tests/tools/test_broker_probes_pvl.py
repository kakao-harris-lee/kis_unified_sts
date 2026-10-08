"""Unit tests for P-VL — the GET-only venue-limits probe (``tools/broker_probes``).

Design: ``docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md``
§4 (legs) / §5 (verdicts) / §8 step 2 (this file is the "hermetic 테스트: 레그별
레드 증명" item).

Every red proof below is a CONCRETE failing input sitting beside the guard it
exercises, because a guard whose failing input nobody can write is a guard that
blocks nothing. The six the design asks for, and what each one is made of:

1. **band mismatch** — a stage-2 (15%) band against the stage-1 (8%) arithmetic.
   REPORTED, never raised: a 2단계 band outside the 08:45-09:00 no-escalation
   window is a legitimate market state, not a harness defect.
2. **non-integral ``ord_psbl_qty``** — ``"1.5"`` contracts. RAISES: quantities
   here are CONTRACTS and a fractional one cannot be rounded into a real order.
3. **``rt_cd != 0`` on L1** — RAISES: every later leg reads its prices from that
   response, so the refusal is the whole observation.
4. **tick mismatch** — ``futs_prpr="420.53"`` is not a multiple of the 0.02 tick
   ``config/execution.yaml`` registers for the mini contract. RAISES via
   ``_corroborate_tick``: the registry is contradicted by the venue's own quotes.
5. **real host refused** — the client handed ``REAL_BASE_URL``. RAISES before the
   session is touched, so a refused call opens no socket.
6. **``rt_cd != 0`` on L5** — RECORDED without raising: whether the GET surface
   validates a price above the band is exactly the open question, so a refusal
   there is an observation, not a failure.

No test here opens a socket: the transport is a scripted fake and the auth
manager is a stub.

The green fixture's numbers are chosen so the arithmetic is checkable by hand:
기준가격 420.00, so the stage-1 band is 420 × 1.08 = 453.6 (상한) and
420 × 0.92 = 386.4 (하한), both already exact multiples of 0.05 AND of the 0.02
tick the mini leaf registers — the only way one quote set can satisfy both the
제56조 arithmetic and the tick corroboration at once.
"""

from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tools.broker_probes import _tick_math
from tools.broker_probes import probes_venue_limits as pvl
from tools.broker_probes.common import (
    MOCK_BASE_URL,
    REAL_BASE_URL,
    ProbeError,
    ReadOnlyCall,
    SafetyViolation,
)
from tools.broker_probes.registry import coverage_report, get

KST = pvl.KST

_ACCOUNT = "1234567803"  # 8-digit CANO + product code 03 (futures)
_APP_KEY = "pvl-test-app-key"
_APP_SECRET = "pvl-test-app-secret"

#: A 미니코스피200 leaf — the product the resident paper session actually runs
#: (today's resident leaf). Its registered 호가가격단위 is 0.02, NOT the 0.05 of
#: the full-size contract that the deployed paper policy still carries.
_SYMBOL = "A05610"

#: The tick ``config/execution.yaml::futures_contract_spec.kospi200_mini``
#: registers for :data:`_SYMBOL`. Spelled out here so the hand-checkable band
#: arithmetic below is read against the right unit.
_MINI_TICK = Decimal("0.02")

#: 기준가격 for every fixture. See the module docstring for why 420.00.
_SDPR = "420.00"
_STAGE1_UPPER = "453.6"
_STAGE1_LOWER = "386.4"
_STAGE2_UPPER = "483.0"
_STAGE2_LOWER = "357.0"


# ---------------------------------------------------------------------------
# doubles
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal ``requests.Response`` stand-in — status, body and HEADERS."""

    def __init__(
        self,
        body: dict[str, Any],
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status
        self.headers = headers or {"Date": "Wed, 08 Oct 2026 00:50:00 GMT"}
        self._body = body
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeSession:
    """Serves the price TR from one body and the psbl TR from a queue."""

    def __init__(
        self, price: _FakeResponse, psbl: list[_FakeResponse] | None = None
    ) -> None:
        self._price = price
        self._psbl = list(psbl or [])
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
                "tr_id": headers.get("tr_id", ""),
                "params": dict(params),
            }
        )
        if "quotations/inquire-price" in url:
            return self._price
        if "trading/inquire-psbl-order" in url:
            if not self._psbl:
                raise AssertionError("more psbl calls than the script provides")
            return self._psbl.pop(0)
        raise AssertionError(f"unexpected probe URL: {url}")

    def close(self) -> None:
        self.closed = True


class _ExplodingSession:
    """Any contact at all is a test failure — used for refusal proofs."""

    def request(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a refused call must not reach the transport")

    def close(self) -> None:
        return None


class _FakeAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer test", "appkey": _APP_KEY}


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export exactly the env vars ``resolve_credentials('futures')`` reads.

    The legacy fallbacks are dropped so a host ``.env`` cannot leak in.
    """
    for name in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_TOKEN_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", _APP_KEY)
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", _APP_SECRET)
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replace auth + transport so the whole probe runs offline."""

    def _wire(session: Any) -> Any:
        monkeypatch.setattr("requests.Session", lambda: session)
        monkeypatch.setattr(
            "shared.kis.auth.KISAuthManager",
            lambda cfg, use_singleton=True: _FakeAuth(),
        )
        monkeypatch.setattr(pvl, "build_auth_config", lambda creds, cache: object())
        monkeypatch.setattr(pvl, "probe_token_cache_dir", lambda explicit: tmp_path)
        return session

    return _wire


@pytest.fixture
def escalation_window(monkeypatch: pytest.MonkeyPatch):
    """Force a sample INSIDE or OUTSIDE the 08:45-09:00 no-escalation window.

    L2's verdict is three-way and the third branch depends on which of the
    design's two samples is being taken. Leaving that to the wall clock would
    make every band test pass or fail by the hour, which is the time-fragile
    shape this repo bans. The real :func:`kst_sample_window` still runs, and
    still reads the session from the calendar — only the rule window moves.
    """

    def _set(*, determined: bool) -> None:
        monkeypatch.setattr(pvl, "_NO_ESCALATION_START", time(0, 0))
        # An empty window contains no instant; a whole-day one contains every.
        monkeypatch.setattr(
            pvl, "_NO_ESCALATION_END", time(23, 59, 59) if determined else time(0, 0)
        )

    return _set


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "probe_id": "P-VL",
        "symbol": _SYMBOL,
        "asset": "futures",
        "confirm": True,  # P-VL is requires_confirm=True (P-16 polarity)
        "pace_s": 0.0,  # these tests assert values, not intervals
        "token_cache_dir": None,
        "out_dir": None,
        "note": "",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _price_body(
    *,
    futs_prpr: str = "420.50",
    futs_prdy_clpr: str = "419.80",
    futs_sdpr: str = _SDPR,
    futs_mxpr: str = _STAGE1_UPPER,
    futs_llam: str = _STAGE1_LOWER,
    rt_cd: str = "0",
    drop: str = "",
) -> _FakeResponse:
    output = {
        "futs_prpr": futs_prpr,
        "futs_prdy_clpr": futs_prdy_clpr,
        "futs_sdpr": futs_sdpr,
        "futs_mxpr": futs_mxpr,
        "futs_llam": futs_llam,
    }
    if drop:
        output.pop(drop, None)
    return _FakeResponse(
        {
            "rt_cd": rt_cd,
            "msg_cd": "MCA00000" if rt_cd == "0" else "EGW00123",
            "msg1": (
                "정상처리 되었습니다." if rt_cd == "0" else "조회할 자료가 없습니다."
            ),
            "output1": output,
        }
    )


def _psbl_body(
    *,
    ord_psbl_qty: str = "5",
    tot_psbl_qty: str = "5",
    bass_idx: str = "420.50",
    rt_cd: str = "0",
    msg_cd: str = "MCA00000",
    msg1: str = "정상처리 되었습니다.",
) -> _FakeResponse:
    return _FakeResponse(
        {
            "rt_cd": rt_cd,
            "msg_cd": msg_cd,
            "msg1": msg1,
            "output": {
                "ord_psbl_qty": ord_psbl_qty,
                "tot_psbl_qty": tot_psbl_qty,
                "bass_idx": bass_idx,
            },
        }
    )


@pytest.fixture
def policy_tick(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Serve a chosen ``tick_size`` as the deployed paper policy.

    Below-bar (c): two tests asserted ``tick_registry_matches_policy`` against
    the LIVE policy file, so they would both go red the day the operator fixes
    ``tick_size`` to 2 — a test suite that breaks when the defect it describes
    is repaired. The comparison logic is what deserves pinning; the deployed
    value gets ONE dated test of its own
    (:func:`test_the_deployed_policy_still_says_five_as_of_2026_10_08`).
    """

    def _set(scaled_tick: int | None) -> Path:
        policy = tmp_path / "venue_constraint_policy.yaml"
        shape = "" if scaled_tick is None else f"    tick_size: {scaled_tick}\n"
        policy.write_text(
            "_model_view:\n  shape_constraints:\n" + (shape or "    lot_size: 1\n"),
            encoding="utf-8",
        )
        monkeypatch.setattr(pvl, "_PAPER_VENUE_POLICY", policy)
        return policy

    return _set


def _execution_yaml(product: str, *, tick: str, prefix: str) -> str:
    """A one-spec ``futures_contract_spec`` document for the tmp-registry tests.

    ``product`` is the spec NAME, which the probe cross-checks against its own
    별표 table, so these tests can exercise both the agreeing and the drifted
    pairing from one builder.
    """
    return (
        "futures_contract_spec:\n"
        f"  {product}:\n"
        "    multiplier_krw_per_point: 50000\n"
        f"    tick_size_points: {tick}\n"
        "    tick_value_krw: 1000\n"
        "    commission_rate: 0.00003\n"
        f'    symbol_prefix: "{prefix}"\n'
    )


def _green_psbl() -> list[_FakeResponse]:
    return [_psbl_body(), _psbl_body(), _psbl_body()]


def _client(session: Any, *, base_url: str = MOCK_BASE_URL) -> pvl.MockQueryClient:
    from tools.broker_probes.common import ProbeCredentials

    creds = ProbeCredentials(
        app_key=_APP_KEY,
        app_secret=_APP_SECRET,
        account_no=_ACCOUNT,
        is_real=False,
        asset="futures",
    )
    return pvl.MockQueryClient(
        creds, _FakeAuth(), session, base_url=base_url, pace_s=0.0
    )


# ---------------------------------------------------------------------------
# registry metadata
# ---------------------------------------------------------------------------


def test_registry_entry_is_a_get_only_mock_query() -> None:
    spec = get("P-VL")

    assert spec.kind == "QUERY"
    assert spec.environment == "MOCK_VTS"
    assert spec.emits_orders is False
    assert spec.risk == "LOW"
    assert spec.supported is True
    assert spec.entrypoint == "tools.broker_probes.probes_venue_limits:probe_pvl"


def test_registry_is_confirm_gated_like_every_other_networked_probe() -> None:
    """``--confirm`` gates broker contact even for a read-only probe.

    P-16 and P-13 are both read-only MOCK queries and both set this. A networked
    probe without it would be the only hole in runbook safety control #4, so the
    flag is asserted beside the register's own statement that the module is
    read-only and imports no order path.
    """
    spec = get("P-VL")

    assert spec.requires_confirm is True
    assert get("P-16").requires_confirm is True  # the polarity being followed
    prerequisites = " ".join(spec.prerequisites)
    assert "READ-ONLY" in prerequisites
    assert "GET 전용" in prerequisites
    assert "실주문 없음" in prerequisites
    assert "probes_order" in prerequisites


def test_registry_source_cites_the_design_document() -> None:
    assert (
        "docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md"
        in get("P-VL").source
    )


def test_registry_statistic_refuses_to_read_a_quantity_limit_from_the_probe() -> None:
    """The register must say, in words, that 2,000 is not a probe output."""
    statistic = get("P-VL").statistic

    assert "예수금 파생값" in statistic
    assert "GET 으로 관측 불가" in statistic


def test_instance_field_is_the_existing_p02_slot_not_an_invented_one() -> None:
    """Anti-phantom: the profile key the probe claims to feed must exist."""
    fields = get("P-VL").instance_fields
    assert fields == (
        "capabilities.market_and_instrument_constraints."
        "price_band_tick_lot_and_quantity_semantics",
    )

    repo_root = Path(pvl.__file__).resolve().parents[2]
    draft = (
        repo_root
        / "docs"
        / "broker-profiles"
        / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
    )
    assert "price_band_tick_lot_and_quantity_semantics:" in draft.read_text(
        encoding="utf-8"
    )


def test_followup_probe_does_not_inflate_the_ratified_counts() -> None:
    report = coverage_report()

    assert report["canonical_count"] == 12
    assert report["census_count"] == 4
    assert "P-VL" not in report["canonical_12"]
    assert "P-VL" not in report["census_4"]
    assert "P-VL" not in report["order_emitting"]


def test_run_py_knows_where_the_probe_s_cli_args_live() -> None:
    from tools.broker_probes import run as run_module

    assert (
        run_module._ARG_ADDERS["tools.broker_probes.probes_venue_limits"]
        == "add_venue_limits_args"
    )


def test_pace_default_is_p13s_measured_clean_rate() -> None:
    """1.1 s, and the constant is LOCAL on purpose.

    ``probes_order.DEFAULT_PACE_S`` holds the same number, but importing that
    module would put order-submitting code in this probe's graph — the hole
    ``test_module_does_not_import_order_capable_modules`` exists to close.
    ``probes_balance`` and ``probes_ca`` keep their own copies for the same
    reason, and the docstring on this one says so.
    """
    parser = argparse.ArgumentParser()
    pvl.add_venue_limits_args(parser)

    assert parser.get_default("pace_s") == pvl.DEFAULT_PACE_S == 1.1
    module_text = Path(pvl.__file__).read_text(encoding="utf-8")
    assert "probes_order.DEFAULT_PACE_S" in module_text  # the reason, in writing


# ---------------------------------------------------------------------------
# structural read-only property — this module's own AST, not its prose
# ---------------------------------------------------------------------------


def _module_ast() -> ast.Module:
    return ast.parse(Path(pvl.__file__).read_text(encoding="utf-8"))


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


def test_module_defines_no_order_submitting_helper() -> None:
    names = {
        node.name
        for node in ast.walk(_module_ast())
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    banned = ("submit", "cancel", "replace", "place", "rvsecncl")

    assert not [name for name in names if any(t in name.lower() for t in banned)]


def test_the_real_trading_tr_appears_nowhere_in_the_module() -> None:
    """``TTTO5105R`` is the REAL twin of ``VTTO5105R``. It must be absent."""
    assert "TTTO5105R" not in Path(pvl.__file__).read_text(encoding="utf-8")


def _imported_modules(module: Any) -> set[str]:
    imported: set[str] = set()
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    return imported


def test_module_does_not_import_order_capable_modules() -> None:
    """The canary ``test_broker_probes_ca.py`` carries, applied to this module.

    ``probes_real_order`` is the only order-emitting module in the harness and it
    imports ``probes_order`` at module level, so ONE import of either would put
    both order paths in this read-only module's graph. The two pure helpers this
    probe reuses live in ``_tick_math`` precisely so that import is unnecessary.
    """
    banned = ("probes_order", "probes_real_order")

    assert not [
        name for name in _imported_modules(pvl) if any(b in name for b in banned)
    ]


@pytest.mark.parametrize("raw", ["NaN", "nan", "Infinity", "-Infinity", "inf"])
def test_a_non_finite_broker_field_reads_as_unestablished(raw: str) -> None:
    """Below-bar (g): ``Decimal("NaN")`` PARSES, and then poisons the arithmetic.

    A NaN reaching ``corroborate_tick`` makes ``value % tick`` raise
    ``InvalidOperation`` far from the field that caused it. "The broker did not
    give us this number" is exactly the documented contract for these.
    """
    assert _tick_math.decimal_field({"futs_prpr": raw}, "futs_prpr") is None


def test_a_non_finite_quote_is_reported_as_an_unusable_field(
    futures_env: None, wire: Any
) -> None:
    """End to end: it lands in L1's unusable list, not in a traceback."""
    wire(_FakeSession(_price_body(futs_prpr="NaN"), []))

    run = pvl.probe_pvl(_args())

    assert run.measurements["l1_abort"]["code"] == "ABORT_L1_PRICE_FIELD_UNUSABLE"
    assert "futs_prpr='NaN'" in run.errors[0]


def test_the_tick_protocol_is_not_runtime_checkable() -> None:
    """Below-bar (g): a data-only Protocol cannot be used with isinstance.

    Keeping the decorator advertised a check that raises ``TypeError`` for
    anyone who tries it.
    """
    with pytest.raises(TypeError):
        isinstance(object(), _tick_math.TickLike)


def test_the_relocated_helper_module_is_stdlib_only() -> None:
    """``_tick_math`` is the shared dependency, so its own graph must stay empty.

    One ``tools.broker_probes`` or ``shared`` import here would be inherited by
    every GET-only module that reuses it and would silently reopen the hole the
    relocation closed.
    """
    imported = _imported_modules(_tick_math)

    assert not [
        name
        for name in imported
        if name.startswith(("tools", "shared", "services", "tos"))
    ]
    assert imported <= {"decimal", "typing", "__future__"}


def test_probes_real_order_still_exposes_the_relocated_helpers() -> None:
    """The relocation was an address change, not a rename for callers.

    ``probes_real_order._corroborate_tick`` is reached by name from
    ``tests/tools/test_broker_probes_real_order.py``, and every call site inside
    that module uses the private names. Re-export keeps both working.
    """
    from tools.broker_probes import probes_real_order as pro

    assert pro._corroborate_tick is _tick_math.corroborate_tick
    assert pro._decimal_field is _tick_math.decimal_field


def test_allowlist_is_two_read_only_inquiries_and_nothing_else() -> None:
    assert {entry.tr_id for entry in pvl.ALLOWLIST} == {
        "FHMIF10000000",
        "VTTO5105R",
    }
    for entry in pvl.ALLOWLIST:
        assert "/order" not in entry.path
        assert entry.path.endswith(("inquire-price", "inquire-psbl-order"))


# ---------------------------------------------------------------------------
# RED PROOF 5 — the real host is refused before any contact
# ---------------------------------------------------------------------------


def test_client_refuses_the_real_host_before_touching_the_session() -> None:
    client = _client(_ExplodingSession(), base_url=REAL_BASE_URL)

    with pytest.raises(SafetyViolation, match="not the mock host"):
        client.get(
            path=pvl._PRICE_PATH,
            tr_id=pvl._PRICE_TR,
            params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": _SYMBOL},
        )


def test_client_refuses_a_non_allowlisted_path() -> None:
    client = _client(_ExplodingSession())

    with pytest.raises(SafetyViolation, match="read-only allowlist"):
        client.get(
            path="/uapi/domestic-futureoption/v1/trading/order",
            tr_id=pvl._PSBL_TR,
            params={},
        )


def test_client_refuses_an_allowlisted_tr_on_the_wrong_path() -> None:
    client = _client(_ExplodingSession())

    with pytest.raises(SafetyViolation, match="read-only allowlist"):
        client.get(path=pvl._PSBL_PATH, tr_id=pvl._PRICE_TR, params={})


def test_a_real_trading_tr_added_to_the_allowlist_is_still_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second guard's concrete failing input: a widened allowlist.

    ``assert_mock_trading_tr`` cannot fire through the allowlist as it ships —
    the only ``/trading/`` pair is the demo TR. The input that does reach it is
    the edit most likely to happen: someone adds the real TR to
    :data:`~tools.broker_probes.probes_venue_limits.ALLOWLIST`. Without this
    layer that edit alone would send a real trading TR at the mock host; with
    it, the call is still refused.
    """
    monkeypatch.setattr(
        pvl,
        "ALLOWLIST",
        pvl.ALLOWLIST
        + (ReadOnlyCall("TTTO5105R", pvl._PSBL_PATH, "a real TR, wrongly admitted"),),
    )
    client = _client(_ExplodingSession())

    with pytest.raises(SafetyViolation, match="not a mock TR"):
        client.get(path=pvl._PSBL_PATH, tr_id="TTTO5105R", params={})


# ---------------------------------------------------------------------------
# pure arithmetic — Decimal, exact, no float anywhere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "tick", "expected"),
    [
        ("453.6", "0.05", "453.6"),
        ("453.64", "0.05", "453.60"),
        ("453.69", "0.05", "453.65"),
        ("420.53", "0.02", "420.52"),
        ("0.05", "0.05", "0.05"),
    ],
)
def test_floor_to_tick_is_exact(value: str, tick: str, expected: str) -> None:
    assert pvl.floor_to_tick(Decimal(value), Decimal(tick)) == Decimal(expected)


@pytest.mark.parametrize(
    ("value", "tick", "expected"),
    [
        ("386.4", "0.05", "386.4"),
        ("386.41", "0.05", "386.45"),
        ("386.46", "0.05", "386.50"),
        ("420.53", "0.02", "420.54"),
    ],
)
def test_ceil_to_tick_is_exact(value: str, tick: str, expected: str) -> None:
    assert pvl.ceil_to_tick(Decimal(value), Decimal(tick)) == Decimal(expected)


def test_tick_arithmetic_never_inherits_the_float_artifact() -> None:
    """``7443 * 0.05`` is ``372.15000000000003`` in binary floating point.

    The campaign already lost one order to that number (artifact
    ``P-5-20260730T000608Z``, 호가단위 오류). Nothing here may reproduce it.
    """
    assert str(7443 * 0.05) == "372.15000000000003"  # the hazard, made explicit

    assert pvl.floor_to_tick(Decimal("372.17"), Decimal("0.05")) == Decimal("372.15")
    assert pvl.ceil_to_tick(Decimal("372.11"), Decimal("0.05")) == Decimal("372.15")


@pytest.mark.parametrize("tick", ["0", "-0.05"])
def test_non_positive_tick_is_refused(tick: str) -> None:
    with pytest.raises(ProbeError, match="tick size must be positive"):
        pvl.floor_to_tick(Decimal("420"), Decimal(tick))


def test_negative_price_is_refused() -> None:
    with pytest.raises(ProbeError, match="negative"):
        pvl.ceil_to_tick(Decimal("-1"), Decimal("0.05"))


def test_band_expectation_reproduces_the_rule_arithmetic_by_hand() -> None:
    """420 × 1.08 = 453.6 내림 · 420 × 0.92 = 386.4 올림 (시행세칙 제56조)."""
    record = pvl.band_expectation(
        Decimal(_SDPR), ratio=Decimal("0.08"), tick=_MINI_TICK
    )

    assert Decimal(record["expected_upper"]) == Decimal(_STAGE1_UPPER)
    assert Decimal(record["expected_lower"]) == Decimal(_STAGE1_LOWER)
    assert "제56조" in record["rounding_rule"]
    assert "제55조제1항제2호" in record["basis_price_rule"]


def test_band_stage_matches_identifies_which_stage_reproduced_the_band() -> None:
    report = pvl.band_stage_matches(
        sdpr=Decimal(_SDPR),
        observed_upper=Decimal(_STAGE2_UPPER),
        observed_lower=Decimal(_STAGE2_LOWER),
        tick=_MINI_TICK,
    )

    assert report["any_match"] is True
    assert report["matching_stages"] == [2]
    assert len(report["candidates"]) == 3  # one per 별표 14 stage
    assert [c["ratio"] for c in report["candidates"]] == ["0.08", "0.15", "0.20"]


def test_band_stage_matches_reports_no_match_without_claiming_a_cause() -> None:
    """A band that no stage reproduces yields facts, not a diagnosis."""
    report = pvl.band_stage_matches(
        sdpr=Decimal(_SDPR),
        observed_upper=Decimal("500.00"),
        observed_lower=Decimal("300.00"),
        tick=_MINI_TICK,
    )

    assert report["any_match"] is False
    assert report["matching_stages"] == []
    assert "does not establish" in report["not_an_interpretation"]


def test_band_expectation_refuses_a_non_positive_basis_price() -> None:
    with pytest.raises(ProbeError, match="기준가격 must be positive"):
        pvl.band_expectation(Decimal("0"), ratio=Decimal("0.08"), tick=_MINI_TICK)


# ---------------------------------------------------------------------------
# the 08:45-09:00 no-escalation window (시행세칙 제56조의2제2항)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hour", "minute", "inside"),
    [
        (8, 44, False),
        (8, 45, True),
        (8, 59, True),
        (9, 0, False),
        (9, 20, False),
    ],
)
def test_no_escalation_window_boundaries(hour: int, minute: int, inside: bool) -> None:
    record = pvl.kst_sample_window(datetime(2026, 10, 8, hour, minute, tzinfo=KST))

    assert record["inside_no_escalation_window"] is inside
    assert record["expected_stage_is_determined"] is inside


def test_sample_window_records_the_kst_wall_clock_and_the_session() -> None:
    record = pvl.kst_sample_window(datetime(2026, 10, 8, 8, 50, tzinfo=KST))

    assert record["sampled_at_kst"].startswith("2026-10-08T08:50")
    assert record["inside_continuous_session"] is True
    assert "제56조의2제2항" in record["no_escalation_source"]
    # (f) both amendment dates, not one 절's date pinned on the other.
    assert "2025-05-29" in record["no_escalation_source"]
    assert "2026-06-11" in record["no_escalation_source"]
    # (b) the window is READ from the calendar, so the citation names the file
    # and the phase it came from rather than a line number beside a literal.
    assert "calendar.yaml::sessions.krx-index-futures" in (
        record["continuous_session_source"]
    )
    assert record["continuous_session_kst"] == "08:45-15:45"


def test_the_continuous_window_comes_from_the_calendar_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Below-bar (b): point the loader at another calendar; the window follows.

    This is the test a literal 08:45-15:45 could not pass. CLAUDE.md puts
    schedules in YAML and the artifact already cited the calendar, so the module
    may not keep its own copy of the times.
    """
    other = tmp_path / "calendar.yaml"
    other.write_text(
        "sessions:\n"
        "  krx-index-futures:\n"
        '    - {phase: CONTINUOUS, start: "10:00", end: "11:30"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(pvl, "_CALENDAR_CONFIG", other)

    record = pvl.kst_sample_window(datetime(2026, 10, 8, 10, 30, tzinfo=KST))

    assert record["continuous_session_kst"] == "10:00-11:30"
    assert record["inside_continuous_session"] is True


def test_a_calendar_without_the_phase_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fail-closed: a missing window must not read as "outside the session"."""
    empty = tmp_path / "calendar.yaml"
    empty.write_text("sessions: {}\n", encoding="utf-8")
    monkeypatch.setattr(pvl, "_CALENDAR_CONFIG", empty)

    with pytest.raises(ProbeError, match="declares no CONTINUOUS phase"):
        pvl.kst_sample_window(datetime(2026, 10, 8, 10, 30, tzinfo=KST))


def test_a_sample_outside_the_continuous_session_is_marked_as_such() -> None:
    record = pvl.kst_sample_window(datetime(2026, 10, 8, 16, 0, tzinfo=KST))

    assert record["inside_continuous_session"] is False


# ---------------------------------------------------------------------------
# GREEN — the whole probe, five legs, offline
# ---------------------------------------------------------------------------


def test_green_run_records_every_leg_and_passes_l1_l2_l3(
    futures_env: None, wire: Any
) -> None:
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    run = pvl.probe_pvl(_args())

    assert run.errors == []
    assert run.measurements["leg_verdicts"] == {
        "L1": "PASS",
        "L2": "PASS",
        "L3": "PASS",
        "L4": "OBSERVATION_ONLY_NO_VERDICT",
        "L5": "OBSERVATION_ONLY_NO_VERDICT",
    }
    # 1 quote + 3 주문가능 — exactly the five legs, no extra call.
    assert [call["tr_id"] for call in session.calls] == [
        "FHMIF10000000",
        "VTTO5105R",
        "VTTO5105R",
        "VTTO5105R",
    ]
    assert all(call["method"] == "GET" for call in session.calls)
    assert all(call["url"].startswith(MOCK_BASE_URL) for call in session.calls)
    assert session.closed is True


def test_green_run_records_the_five_l1_fields_and_the_tick_corroboration(
    futures_env: None, wire: Any
) -> None:
    wire(_FakeSession(_price_body(), _green_psbl()))

    measurements = pvl.probe_pvl(_args()).measurements

    assert set(measurements["l1_quote_fields"]["values"]) == {
        "futs_prpr",
        "futs_prdy_clpr",
        "futs_sdpr",
        "futs_mxpr",
        "futs_llam",
    }
    assert measurements["l1_quote_fields"]["unusable"] == []
    # Design §4.1 lists the Date header among L1's measurements.
    assert measurements["l1_quote_fields"]["broker_date_header"].startswith("Wed, 08")
    assert measurements["l1_tick_corroboration"]["corroborated"] is True
    assert measurements["l1_tick_corroboration"]["non_multiples"] == []
    # 420.00 (기준가) vs 419.80 (전일종가) differ, so this sample distinguishes
    # 제55조제1항제2호's settlement-price basis from the previous close.
    basis = measurements["l1_basis_price_distinguishable"]
    assert basis["differ"] is True
    # A05610 is an October leaf, so 제55조제1항 단서 does not apply and the
    # stronger reading is available.
    assert basis["quarterly_mini_leaf"] is False
    assert basis["distinguishes_settlement_from_close"] is True


@pytest.mark.parametrize(
    ("symbol", "quarterly"),
    [
        pytest.param("A05610", False, id="october-mini"),
        pytest.param("A05612", True, id="december-mini"),
        pytest.param("A05603", True, id="march-mini"),
        pytest.param("A05606", True, id="june-mini"),
        pytest.param("A05605", False, id="may-mini"),
    ],
)
def test_a_quarterly_mini_leaf_cannot_claim_the_settlement_reading(
    futures_env: None, wire: Any, symbol: str, quarterly: bool
) -> None:
    """Below-bar (e): 제55조제1항 단서 borrows the 코스피200선물's 기준가격.

    On a 분기월 mini leaf the two fields can differ because the basis came from
    ANOTHER product, so a difference does not distinguish 정산가 from 종가. The
    probe used to claim it did.
    """
    wire(_FakeSession(_price_body(), _green_psbl()))

    basis = pvl.probe_pvl(_args(symbol=symbol)).measurements[
        "l1_basis_price_distinguishable"
    ]

    assert basis["differ"] is True
    assert basis["quarterly_mini_leaf"] is quarterly
    assert basis["distinguishes_settlement_from_close"] is not quarterly
    assert "제55조제1항 단서" in basis["quarterly_caveat"]


def test_a_full_size_leaf_is_never_flagged_quarterly() -> None:
    """제55조제1항 단서 is a mini-only rule, so the flag must not spread."""
    assert pvl._is_quarterly_mini("A01612") is False
    assert pvl._is_quarterly_mini("A05612") is True


def test_green_run_sends_the_official_psbl_parameter_set(
    futures_env: None, wire: Any
) -> None:
    """Every ``VTTO5105R`` field from the official wrapper, nothing invented."""
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    pvl.probe_pvl(_args())

    psbl = [c for c in session.calls if c["tr_id"] == "VTTO5105R"]
    for call in psbl:
        assert set(call["params"]) == {
            "CANO",
            "ACNT_PRDT_CD",
            "PDNO",
            "SLL_BUY_DVSN_CD",
            "UNIT_PRICE",
            "ORD_DVSN_CD",
        }
        assert call["params"]["PDNO"] == _SYMBOL
        assert call["params"]["SLL_BUY_DVSN_CD"] == "02"
        assert call["params"]["ORD_DVSN_CD"] == "01"
        assert call["params"]["ACNT_PRDT_CD"] == "03"
    # L3 at the touch, L4 at the lower limit, L5 one tick above the upper limit.
    assert [c["params"]["UNIT_PRICE"] for c in psbl] == ["420.50", "386.4", "453.62"]


def test_green_run_states_what_it_cannot_establish(
    futures_env: None, wire: Any
) -> None:
    """Design §4.3 is written FIRST in the design and recorded in the artifact."""
    wire(_FakeSession(_price_body(), _green_psbl()))

    cannot = pvl.probe_pvl(_args()).measurements["cannot_establish"]

    assert "예수금" in cannot["kis_quantity_limit"]
    assert "별표 17의2" in cannot["kis_quantity_limit"]
    assert "제61조제3항" in cannot["kis_quantity_limit"]
    # No contract count is spelled here on purpose: WHICH number applies depends
    # on --symbol's product family, so the row lives in resolved_instrument and
    # this text points at it rather than hardcoding the full-size 2,000.
    assert "CONTEXT" in cannot["kis_quantity_limit"]
    assert "2,000" not in cannot["kis_quantity_limit"]
    # The leg's own parameters are the third cause design v2 §4.3 requires.
    assert (
        pvl._ORD_PSBL_QTY_PARAMETER_DEPENDENCE_CITATION in cannot["kis_quantity_limit"]
    )
    assert set(cannot) == {
        "kis_quantity_limit",
        "no_prior_ord_psbl_qty_observation",
        "stage_2_3_escalation",
        "runtime_band_supply",
    }


def test_the_parameter_dependence_citation_still_points_at_real_text() -> None:
    """The citation is checked against the cited file, not trusted.

    The first draft of this module cited ``probes_real_order.py:1651-1658`` and
    **this PR staled it**: relocating two helpers out of that file moved the
    block 34 lines up, so the range came to name a closing paren and the next
    ``def``. A line range cannot survive an edit above it, so the citation is
    symbol-anchored and this test locates the quoted sentence INSIDE the named
    function. If anyone moves it out, the anchor fails here instead of rotting.
    """
    import ast

    from tools.broker_probes import probes_real_order as pro

    source = Path(pro.__file__).read_text(encoding="utf-8")
    citation = pvl._ORD_PSBL_QTY_PARAMETER_DEPENDENCE_CITATION
    assert "_preflight_instrument_state" in citation
    assert "'interpretation'" in citation

    sentence = "about the parameters and not the account"
    assert source.count(sentence) == 1, (
        "the cited sentence is no longer unique in probes_real_order.py; the "
        "citation can no longer point at one place"
    )
    sentence_line = source[: source.index(sentence)].count("\n") + 1

    enclosing = [
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= sentence_line <= (node.end_lineno or node.lineno)
    ]
    assert "_preflight_instrument_state" in enclosing, (
        f"the cited sentence is now inside {enclosing}, not "
        "_preflight_instrument_state; update the citation in "
        "probes_venue_limits.py and the runbook"
    )
    # And it really is the ``interpretation`` value, not prose that happens to
    # contain the words.
    block = source[: source.index(sentence)]
    assert block.rindex('"interpretation": (') > block.rindex("run.measure(")


def test_the_byeolpyo_citations_point_at_the_rows_they_claim() -> None:
    """The 별표 line ranges are checked against the committed evidence texts.

    Same defect class as the verifier's blocker, one file over: a line-pinned
    citation that nobody resolves. These ranges became checkable when the
    evidence landed on main (#879), so they get checked rather than trusted —
    and the mini and full rows must resolve to DIFFERENT text, which is the
    specific confusion design v2 §2.1 records v1 making.
    """
    import re

    repo_root = Path(pvl.__file__).resolve().parents[2]
    seen: dict[str, str] = {}
    for prefix in ("A05", "101"):
        row = pvl.KRX_PREFIX_TABLE[prefix]
        match = re.search(r"([\w./-]+\.txt):(\d+)-(\d+)", row["evidence"])
        assert match, f"{prefix} evidence is not a resolvable range: {row['evidence']}"
        path, start, end = match.group(1), int(match.group(2)), int(match.group(3))
        lines = (repo_root / path).read_text(encoding="utf-8").splitlines()
        cited = "\n".join(lines[start - 1 : end])

        assert (
            row["product"] in cited
        ), f"{path}:{start}-{end} does not contain {row['product']!r}"
        assert f"{row['regular_session_contracts']:,}" in cited
        assert f"{row['night_session_contracts']:,}" in cited
        # The parenthesised 유동성관리상품 values live in the same row.
        assert f"({row['liquidity_managed_regular_contracts']:,})" in cited
        seen[prefix] = cited

    assert seen["A05"] != seen["101"], (
        "the mini and full rows resolve to the same text; the citation cannot "
        "distinguish the products it is there to distinguish"
    )


def test_the_price_limit_stage_citation_points_at_byeolpyo_14() -> None:
    """The ratios, likewise resolved rather than trusted."""
    repo_root = Path(pvl.__file__).resolve().parents[2]
    cited = (
        repo_root / pvl._EVIDENCE_DIR / "byeolpyo14_price_limit_ratios.txt"
    ).read_text(encoding="utf-8")
    lines = cited.splitlines()
    window = "\n".join(lines[18:25])  # the :19-25 the module cites

    assert "주가지수선물거래" in window
    for stage, ratio in pvl.KRX_PRICE_LIMIT_STAGES:
        assert f"{stage}단계" in window
        assert f"{int(ratio * 100)}%" in window


def test_no_live_line_pinned_citation_of_that_file_survives_in_the_probe() -> None:
    """A line-number citation of a file this PR edits will go stale again.

    ``probes_real_order.py::symbol`` is fine; ``probes_real_order.py:1651`` is
    not. Exactly one line-pinned mention is allowed — the comment recording why
    the anchor became symbolic — and it must be a comment, not live text a
    reader would follow.
    """
    import re

    module_text = Path(pvl.__file__).read_text(encoding="utf-8")
    pinned = [
        line.strip()
        for line in module_text.splitlines()
        if re.search(r"probes_real_order\.py:\d", line)
    ]

    assert len(pinned) == 1, f"expected only the history note, got: {pinned}"
    assert pinned[0].startswith("#"), (
        "the one permitted line-pinned mention must be a comment about the "
        f"staleness, not live text: {pinned[0]!r}"
    )
    assert "staled" in module_text


def test_the_artifact_does_not_claim_a_prior_ord_psbl_qty_observation(
    futures_env: None, wire: Any
) -> None:
    """Finding 2: the fabricated P-R5-PRE reading must be gone everywhere.

    The 2026-08-03 run aborted on the deposit leg before 주문가능 ran, so no
    artifact in this repo says what a zero 주문가능수량 means. The earlier text
    cited it for exactly that.
    """
    wire(_FakeSession(_price_body(), _green_psbl()))

    cannot = pvl.probe_pvl(_args()).measurements["cannot_establish"]
    module_text = Path(pvl.__file__).read_text(encoding="utf-8")

    assert "CTRP6550R" in cannot["no_prior_ord_psbl_qty_observation"]
    assert "NO ord_psbl_qty observation" in cannot["no_prior_ord_psbl_qty_observation"]
    assert "zero-deposit account reports 0" not in module_text
    assert "예수금 0 계좌에서 0" not in module_text


def test_green_run_proposes_the_compound_token_design_v2_asks_for(
    futures_env: None, wire: Any
) -> None:
    """Design v2 §5: a self-describing compound token, never a one-word status.

    ``PARTIAL`` is the word the design refuses by name, and it appears in the
    profile only as a key suffix.
    """
    wire(_FakeSession(_price_body(), _green_psbl()))

    disposition = pvl.probe_pvl(_args()).measurements["p02_disposition_proposal"]

    assert disposition["current"] == "UNKNOWN"
    assert disposition["proposed"] == (
        "BAND_SEMANTICS_OBSERVED_ON_MOCK"
        "__TICK_FROM_REGULATION_NOT_BROKER"
        "__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED"
    )
    assert disposition["proposed"] != "PARTIAL"
    assert disposition["derived_from"]["L1"] == "PASS"
    assert len(disposition["still_unestablished"]) >= 4


@pytest.mark.parametrize(
    ("verdicts", "band_segment"),
    [
        pytest.param(
            {"L1": "PASS", "L2": "PASS"},
            "BAND_SEMANTICS_OBSERVED_ON_MOCK",
            id="both-pass",
        ),
        pytest.param(
            {"L1": "PASS", "L2": "OBSERVATION_ONLY_NO_VERDICT"},
            "BAND_SEMANTICS_L2_STAGE_RECORDED_ONLY",
            id="l2-recorded",
        ),
        pytest.param(
            {"L1": "PASS", "L2": "FAIL"},
            "BAND_SEMANTICS_CONTRADICTED_ON_MOCK",
            id="l2-fail",
        ),
        pytest.param({"L1": "FAIL"}, "BAND_SEMANTICS_NOT_OBSERVED", id="l1-fail"),
        pytest.param({}, "BAND_SEMANTICS_NOT_OBSERVED", id="nothing-ran"),
    ],
)
def test_the_token_is_derived_so_a_failed_leg_cannot_claim_an_observed_axis(
    verdicts: dict[str, str], band_segment: str
) -> None:
    """The concrete failing input finding 3 asked for: an L2 that did not pass.

    If the token were a literal, an L2 FAIL would still ship
    ``BAND_SEMANTICS_OBSERVED_ON_MOCK``. It is derived, so it cannot.
    """
    token = pvl.disposition_token(verdicts)

    assert token.split("__")[0] == band_segment
    if band_segment != "BAND_SEMANTICS_OBSERVED_ON_MOCK":
        assert "BAND_SEMANTICS_OBSERVED_ON_MOCK" not in token
    # The quantity axis is never observable by this probe, in any outcome.
    assert token.endswith("__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED")


def test_the_tick_axis_claims_corroboration_only_when_l1_passed() -> None:
    assert "TICK_FROM_REGULATION_NOT_BROKER" in pvl.disposition_token(
        {"L1": "PASS", "L2": "PASS"}
    )
    assert "TICK_UNCORROBORATED" in pvl.disposition_token({"L1": "FAIL"})


def test_green_run_records_the_registry_policy_tick_disagreement(
    futures_env: None, wire: Any, policy_tick: Any
) -> None:
    """The mini leaf's 0.02 against the paper policy's 5 (= 0.05).

    The probe surfaces the drift and resolves nothing: the registry tick governs
    the arithmetic because it is keyed on this symbol's own product, and the
    policy value sits beside it so a reader sees they disagree.
    """
    policy_tick(5)
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args()).measurements["resolved_instrument"]

    assert record["resolved_product"] == "kospi200_mini"
    assert record["registry_tick_points"] == "0.02"
    assert record["paper_policy_tick"]["tick_size_scaled_int"] == 5
    assert record["paper_policy_tick"]["tick_points"] == "0.05"
    assert record["tick_registry_matches_policy"] is False
    assert "OBSERVATION, not a probe failure" in record["disagreement_note"]


def test_a_policy_fixed_to_the_mini_tick_reports_agreement(
    futures_env: None, wire: Any, policy_tick: Any
) -> None:
    """The other side of the comparison, so it is the LOGIC that is pinned.

    When the operator lands ``tick_size: 2`` the probe must report agreement, not
    keep asserting the drift. Without this test the suite would only know how to
    describe today's defect.
    """
    policy_tick(2)
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args()).measurements["resolved_instrument"]

    assert record["paper_policy_tick"]["tick_points"] == "0.02"
    assert record["tick_registry_matches_policy"] is True


def test_a_policy_without_a_tick_reports_no_comparison(
    futures_env: None, wire: Any, policy_tick: Any
) -> None:
    """An absent ``tick_size`` is not a match. Fail-closed on the boolean."""
    policy_tick(None)
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args()).measurements["resolved_instrument"]

    assert record["paper_policy_tick"]["tick_points"] is None
    assert record["tick_registry_matches_policy"] is False


def test_the_deployed_policy_still_says_five_as_of_2026_10_08() -> None:
    """The ONE test that reads the live file. Dated on purpose.

    If the operator lands the §6 wave's ``tick_size: 2``, this is the single
    test that should go red, and its failure is the reminder to re-date the
    claim — not a signal that the probe broke.
    """
    record = pvl._policy_tick_record()

    assert record["tick_size_scaled_int"] == 5, (
        "the deployed paper policy's tick_size changed; re-date this test and "
        "update the drift notes in the module and runbook §5.9"
    )
    assert record["tick_points"] == "0.05"


def test_artifact_leaks_no_secret_and_no_full_account_number(
    futures_env: None, wire: Any
) -> None:
    wire(_FakeSession(_price_body(), _green_psbl()))
    run = pvl.probe_pvl(_args())

    payload = json.dumps(run.to_dict(get("P-VL")), ensure_ascii=False, default=str)

    assert _APP_SECRET not in payload
    assert _APP_KEY not in payload
    assert _ACCOUNT not in payload
    assert run.credentials["account_masked"] == "12******03"
    assert run.measurements["account_product_code_is_futures_03"]["matches"] is True


def test_l2_does_its_arithmetic_at_the_registry_tick(
    futures_env: None, wire: Any
) -> None:
    """Not the paper policy's 0.05, and not a literal.

    420 × 1.08 = 453.6 and 420 × 0.92 = 386.4 are already exact multiples of
    both units, which is what makes the green fixture usable for either family —
    so the assertion is on the tick the report SAYS it used, not on the band.
    """
    wire(_FakeSession(_price_body(), _green_psbl()))

    report = pvl.probe_pvl(_args()).measurements["l2_band_rule_arithmetic"]

    assert report["tick_points"] == str(_MINI_TICK)
    assert "kospi200_mini" in report["tick_provenance"]
    assert all(c["tick_points"] == str(_MINI_TICK) for c in report["candidates"])


# ---------------------------------------------------------------------------
# --confirm gate (runbook safety control #4)
# ---------------------------------------------------------------------------


def test_without_confirm_nothing_is_sent(futures_env: None, wire: Any) -> None:
    """The dry run resolves the instrument offline and opens no socket."""
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    run = pvl.probe_pvl(_args(confirm=False))

    assert session.calls == []
    assert run.mode == "dry-run"
    assert "leg_verdicts" not in run.measurements
    assert run.measurements["resolved_instrument"]["registry_tick_points"] == str(
        _MINI_TICK
    )


def test_the_dry_run_says_what_it_would_send(futures_env: None, wire: Any) -> None:
    wire(_FakeSession(_price_body(), _green_psbl()))

    run = pvl.probe_pvl(_args(confirm=False))

    would = next(o for o in run.observations if "would_send" in o)
    # Finding 6: the count is DERIVED, so prose and call list cannot disagree.
    # L2 is offline, which is why it is 4 and not 5.
    assert pvl.GET_CALL_COUNT == 4
    assert f"{pvl.GET_CALL_COUNT} read-only GETs" in would["would_send"]
    assert would["get_call_count"] == pvl.GET_CALL_COUNT
    assert "FHMIF10000000" in would["would_send"]
    assert "VTTO5105R" in would["would_send"]
    assert would["resolved_tick_points"] == str(_MINI_TICK)


def test_the_get_count_matches_what_a_live_run_actually_sends(
    futures_env: None, wire: Any
) -> None:
    """The number in the prose is the number of calls. Finding 6's red proof."""
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    pvl.probe_pvl(_args())

    assert len(session.calls) == pvl.GET_CALL_COUNT


def test_the_registry_duration_states_the_same_get_count() -> None:
    """A literal in the register, guarded against the derived value."""
    assert f"GET {pvl.GET_CALL_COUNT} " in get("P-VL").duration


def test_the_dry_run_never_reads_the_account_number(
    futures_env: None, wire: Any
) -> None:
    """``require_account`` is past the gate, so a dry run works without one."""
    wire(_FakeSession(_price_body(), _green_psbl()))

    run = pvl.probe_pvl(_args(confirm=False))

    assert "account_product_code_is_futures_03" not in run.measurements


# ---------------------------------------------------------------------------
# RED PROOF 3 — rt_cd != 0 on L1 raises
# ---------------------------------------------------------------------------


def test_l1_rt_cd_not_zero_is_recorded_and_still_writes_an_artifact(
    futures_env: None, wire: Any
) -> None:
    """Finding 4's red proof. An L1 refusal is a RESULT, not a lost run.

    Before this, the three L1 guards raised a bare ``ProbeError``, which
    ``run.py`` turns into exit 4 with NO artifact — so a single ``rt_cd≠0`` in
    the 08:50±3분 window (what P-CA hit four times on 09-30) discarded the
    credentials, the sample window and every L1 measurement already collected.
    """
    session = wire(_FakeSession(_price_body(rt_cd="1"), []))

    run = pvl.probe_pvl(_args())

    # Returned, not raised — so run.py writes the artifact on the normal path.
    assert run.measurements["leg_verdicts"]["L1"] == "FAIL"
    assert run.measurements["l1_abort"]["code"] == "ABORT_L1_QUOTE_REFUSED"
    assert run.errors and "rt_cd='1'" in run.errors[0]
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"
    # The evidence collected before the guard fired survives.
    assert "l1_sample_window" in run.measurements
    assert run.credentials["account_fingerprint"]
    # And no later leg was attempted.
    assert [c["tr_id"] for c in session.calls] == ["FHMIF10000000"]


def test_the_abort_is_a_probe_error_subclass_so_run_py_still_knows_it() -> None:
    """``VenueLimitAbort`` must stay catchable as a ``ProbeError``.

    ``probe_pvl`` catches it, but anything that escapes the probe should still
    land on run.py's precondition path rather than its generic handler.
    """
    assert issubclass(pvl.VenueLimitAbort, ProbeError)
    abort = pvl.VenueLimitAbort(pvl.ABORT_L1_REFUSED, "because")
    assert abort.code == pvl.ABORT_L1_REFUSED
    assert "because" in str(abort)


def test_l1_off_tick_quote_is_recorded_via_corroborate_tick(
    futures_env: None, wire: Any
) -> None:
    """``420.53`` is not a multiple of the 0.02 tick the mini leaf registers.

    ``corroborate_tick`` is the imported pure function doing the check; the
    probe turns its ``corroborated: False`` into an abort, because no band
    arithmetic may be done against a tick the venue's own quotes deny.
    """
    session = wire(_FakeSession(_price_body(futs_prpr="420.53"), []))

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L1"] == "FAIL"
    assert (
        run.measurements["l1_abort"]["code"]
        == "ABORT_L1_TICK_CONTRADICTED_BY_BROKER_QUOTES"
    )
    assert "futs_prpr=420.53" in run.errors[0]
    assert run.measurements["l1_tick_corroboration"]["corroborated"] is False
    assert [c["tr_id"] for c in session.calls] == ["FHMIF10000000"]


@pytest.mark.parametrize(
    ("overrides", "expected_in_message"),
    [
        pytest.param({"drop": "futs_sdpr"}, "futs_sdpr=None", id="absent"),
        pytest.param({"futs_mxpr": "0"}, "futs_mxpr='0'", id="zero"),
        pytest.param({"futs_llam": "N/A"}, "futs_llam='N/A'", id="non-numeric"),
    ],
)
def test_l1_unusable_price_field_is_recorded(
    futures_env: None, wire: Any, overrides: dict[str, str], expected_in_message: str
) -> None:
    """Design §5: 「필드 누락·0」 is recorded and refused, never substituted."""
    wire(_FakeSession(_price_body(**overrides), []))

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L1"] == "FAIL"
    assert run.measurements["l1_abort"]["code"] == "ABORT_L1_PRICE_FIELD_UNUSABLE"
    assert expected_in_message in run.errors[0]
    assert run.measurements["l1_quote_fields"]["unusable"]


def test_an_l1_abort_still_derives_a_disposition_token(
    futures_env: None, wire: Any
) -> None:
    """The token must say the band was NOT observed, not stay absent."""
    wire(_FakeSession(_price_body(rt_cd="1"), []))

    disposition = pvl.probe_pvl(_args()).measurements["p02_disposition_proposal"]

    assert disposition["proposed"].startswith("BAND_SEMANTICS_NOT_OBSERVED__")
    assert "TICK_UNCORROBORATED" in disposition["proposed"]


# ---------------------------------------------------------------------------
# RED PROOF 1 — band mismatch is REPORTED, not raised
# ---------------------------------------------------------------------------


def test_stage2_band_inside_the_no_escalation_window_is_a_fail(
    futures_env: None, wire: Any, escalation_window: Any
) -> None:
    """420 × 1.15 = 483.0 / × 0.85 = 357.0 — a 2단계 band in sample ①.

    Inside 08:45-09:00 only stage 1 can be in force (시행세칙 제56조의2제2항), so
    a 2단계 band there contradicts the rule and IS a failure. Still recorded, not
    raised: the probe cannot choose the escalation it finds.
    """
    escalation_window(determined=True)
    wire(
        _FakeSession(
            _price_body(futs_mxpr=_STAGE2_UPPER, futs_llam=_STAGE2_LOWER),
            _green_psbl(),
        )
    )

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L2"] == "FAIL"
    assert run.measurements["leg_verdicts"]["L1"] == "PASS"
    assert run.measurements["leg_verdicts"]["L3"] == "PASS"
    report = run.measurements["l2_band_rule_arithmetic"]
    assert report["declared_expectation_matches"] is False
    assert report["matching_stages"] == [2]
    assert run.measurements["l2_mismatch_record"]["verdict"] == "FAIL"


def test_stage2_band_outside_the_window_carries_no_verdict(
    futures_env: None, wire: Any, escalation_window: Any
) -> None:
    """The same band in the design's sample ② is a legitimate market state.

    This is finding 5's concrete input: the 09:20+ sample the design itself
    prescribes. Scoring it FAIL called a lawful 2단계 band a defect, while
    ``_leg_l2``'s own docstring said the opposite. Design v2 §4.2 asks for
    「그날의 확대 사실을 기록만」, so the stage is recorded and no verdict is given.
    """
    escalation_window(determined=False)
    wire(
        _FakeSession(
            _price_body(futs_mxpr=_STAGE2_UPPER, futs_llam=_STAGE2_LOWER),
            _green_psbl(),
        )
    )

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L2"] == "OBSERVATION_ONLY_NO_VERDICT"
    report = run.measurements["l2_band_rule_arithmetic"]
    assert report["expected_stage_is_determined"] is False
    assert report["matching_stages"] == [2]
    record = run.measurements["l2_mismatch_record"]
    assert record["verdict"] == "OBSERVATION_ONLY_NO_VERDICT"
    assert "legitimate market state" in record["why_this_verdict"]
    # No verdict means no error, so the run stays MEASURED.
    assert run.errors == []
    assert run.to_dict()["provenance_class"] == "MEASURED"


def test_a_band_no_stage_reproduces_is_still_only_reported(
    futures_env: None, wire: Any, escalation_window: Any
) -> None:
    """500.00/300.00 against 기준가 420 matches no stage."""
    escalation_window(determined=True)
    wire(
        _FakeSession(_price_body(futs_mxpr="500.00", futs_llam="300.00"), _green_psbl())
    )

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L2"] == "FAIL"
    assert run.measurements["l2_band_rule_arithmetic"]["any_match"] is False
    assert run.measurements["l2_mismatch_record"]["matching_stages"] == []


def test_an_l2_fail_is_also_recorded_as_an_error(
    futures_env: None, wire: Any, escalation_window: Any
) -> None:
    """Below-bar (a): a FAIL verdict must not ship ``errors: []``.

    The runbook reads an empty errors list as a complete run, so a FAIL that
    left it empty made that reading false. P-CA records refusals the same way.
    """
    escalation_window(determined=True)
    wire(
        _FakeSession(
            _price_body(futs_mxpr=_STAGE2_UPPER, futs_llam=_STAGE2_LOWER),
            _green_psbl(),
        )
    )

    run = pvl.probe_pvl(_args())

    assert run.errors, "an L2 FAIL must be recorded in errors"
    assert "L2 FAIL" in run.errors[0]
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


# ---------------------------------------------------------------------------
# RED PROOF 2 — a non-integral ord_psbl_qty raises
# ---------------------------------------------------------------------------


def test_l3_non_integral_ord_psbl_qty_raises(futures_env: None, wire: Any) -> None:
    """``"1.5"`` contracts. Quantities here are CONTRACTS; 1.5 is not one."""
    wire(_FakeSession(_price_body(), [_psbl_body(ord_psbl_qty="1.5")]))

    with pytest.raises(ProbeError, match="ord_psbl_qty='1.5' is not an integer"):
        pvl.probe_pvl(_args())


def test_l3_unreadable_quantity_on_an_rt_cd_zero_answer_raises(
    futures_env: None, wire: Any
) -> None:
    """``rt_cd=0`` with no readable quantity means the field name is wrong."""
    wire(_FakeSession(_price_body(), [_psbl_body(ord_psbl_qty="")]))

    with pytest.raises(ProbeError, match="is not a readable number"):
        pvl.probe_pvl(_args())


def test_l4_and_l5_do_not_apply_the_integral_guard(
    futures_env: None, wire: Any
) -> None:
    """Observation-only legs transcribe whatever came back. Design §5."""
    wire(
        _FakeSession(
            _price_body(),
            [
                _psbl_body(),
                _psbl_body(ord_psbl_qty="1.5"),
                _psbl_body(ord_psbl_qty="not-a-number"),
            ],
        )
    )

    run = pvl.probe_pvl(_args())

    l4 = run.measurements["l4_psbl_at_lower_limit"]
    assert l4["ord_psbl_qty"] == "1.5"
    assert "ord_psbl_qty_int" not in l4
    assert (
        run.measurements["l5_psbl_above_upper_limit"]["ord_psbl_qty"] == "not-a-number"
    )
    assert run.measurements["leg_verdicts"]["L4"] == "OBSERVATION_ONLY_NO_VERDICT"


def test_a_non_integral_tot_psbl_qty_does_not_kill_l4_and_l5(
    futures_env: None, wire: Any
) -> None:
    """Below-bar (d): the field with no verdict must not abort the run.

    ``ord_psbl_qty`` is what L3's verdict reads, so it stays fatal. Design §5
    gives ``tot_psbl_qty`` no verdict at all, and raising on it traded the L4 and
    L5 observations for a field nothing judges.
    """
    wire(
        _FakeSession(
            _price_body(),
            [_psbl_body(tot_psbl_qty="2.5"), _psbl_body(), _psbl_body()],
        )
    )

    run = pvl.probe_pvl(_args())

    l3 = run.measurements["l3_psbl_at_touch"]
    assert l3["tot_psbl_qty"] == "2.5"  # transcribed
    assert "tot_psbl_qty_int" not in l3  # not parsed
    assert "not an integer" in l3["tot_psbl_qty_unreadable"]
    # L3's own verdict still stands on ord_psbl_qty, and L4/L5 still ran.
    assert run.measurements["leg_verdicts"]["L3"] == "PASS"
    assert run.measurements["leg_verdicts"]["L4"] == "OBSERVATION_ONLY_NO_VERDICT"
    assert run.measurements["leg_verdicts"]["L5"] == "OBSERVATION_ONLY_NO_VERDICT"


def test_an_l3_refusal_is_also_recorded_as_an_error(
    futures_env: None, wire: Any
) -> None:
    """Below-bar (a) for L3: the refusal code reaches ``errors`` verbatim."""
    wire(
        _FakeSession(
            _price_body(),
            [
                _psbl_body(rt_cd="1", msg_cd="EGW00215", msg1="처리 중 오류"),
                _psbl_body(),
                _psbl_body(),
            ],
        )
    )

    run = pvl.probe_pvl(_args())

    joined = " ".join(run.errors)
    assert "L3 FAIL" in joined
    assert "EGW00215" in joined
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"


def test_a_green_run_ships_no_errors_and_says_what_that_means(
    futures_env: None, wire: Any
) -> None:
    """The other half of (a): MEASURED must be earned, and documented."""
    wire(_FakeSession(_price_body(), _green_psbl()))

    run = pvl.probe_pvl(_args())

    assert run.errors == []
    assert run.to_dict()["provenance_class"] == "MEASURED"
    assert "errors == []" in run.measurements["verdict_and_error_relation"]


def test_the_artifact_names_the_common_args_it_ignores(
    futures_env: None, wire: Any
) -> None:
    """Below-bar (g): an inert ``--samples 30`` beside 4 calls looks discarded."""
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args()).measurements["inert_common_args"]

    assert "samples" in record["ignored"]
    assert "quantity" in record["ignored"]
    assert "unused flag" in record["why"]


def test_l3_refusal_is_recorded_and_never_read_as_zero_available(
    futures_env: None, wire: Any
) -> None:
    """P-CA's lesson: ``held=0`` on a refused query is not "flat"."""
    wire(
        _FakeSession(
            _price_body(),
            [
                _psbl_body(
                    rt_cd="1", msg_cd="EGW00215", msg1="처리 중 오류", ord_psbl_qty=""
                ),
                _psbl_body(),
                _psbl_body(),
            ],
        )
    )

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L3"] == "FAIL"
    record = run.measurements["l3_refusal_record"]
    assert record["rt_cd"] == "1"
    assert record["msg_cd"] == "EGW00215"
    assert "NOT 'zero available'" in record["recorded_not_interpreted"]
    assert "P-CA" in record["recorded_not_interpreted"]
    # The transcript keeps the broker's own empty string; the DERIVED
    # integer is absent, because nothing was parsed from a refused answer.
    assert run.measurements["l3_psbl_at_touch"]["ord_psbl_qty"] == ""
    assert "ord_psbl_qty_int" not in run.measurements["l3_psbl_at_touch"]


def test_l3_zero_quantity_is_a_fail_distinct_from_a_refusal(
    futures_env: None, wire: Any
) -> None:
    wire(
        _FakeSession(
            _price_body(),
            [
                _psbl_body(ord_psbl_qty="0", tot_psbl_qty="0"),
                _psbl_body(),
                _psbl_body(),
            ],
        )
    )

    run = pvl.probe_pvl(_args())

    assert run.measurements["leg_verdicts"]["L3"] == "FAIL"
    assert "l3_refusal_record" not in run.measurements
    assert run.measurements["l3_zero_quantity_record"]["ord_psbl_qty"] == 0


# ---------------------------------------------------------------------------
# RED PROOF 6 — rt_cd != 0 on L5 is recorded without raising
# ---------------------------------------------------------------------------


def test_l5_rt_cd_not_zero_is_recorded_verbatim_without_raising(
    futures_env: None, wire: Any
) -> None:
    """A price one tick above 상한가 refused at the GET surface.

    Whether the broker validates the band on this inquiry is precisely the open
    question, so the refusal is an observation. Raising would convert the
    probe's own subject matter into a failure.
    """
    wire(
        _FakeSession(
            _price_body(),
            [
                _psbl_body(),
                _psbl_body(),
                _psbl_body(
                    rt_cd="1",
                    msg_cd="40570000",
                    msg1="가격이 상한가를 초과하였습니다.",
                    ord_psbl_qty="0",
                ),
            ],
        )
    )

    run = pvl.probe_pvl(_args())

    assert run.errors == []
    record = run.measurements["l5_psbl_above_upper_limit"]
    assert record["rt_cd"] == "1"
    assert record["msg_cd"] == "40570000"
    assert record["msg1"] == "가격이 상한가를 초과하였습니다."
    assert record["answered"] is False
    assert record["verdict"] == "OBSERVATION_ONLY_NO_VERDICT"
    assert "never interpreted" in record["why_no_verdict"]
    assert run.measurements["leg_verdicts"]["L5"] == "OBSERVATION_ONLY_NO_VERDICT"


def test_l5_price_is_one_registry_tick_above_the_upper_limit(
    futures_env: None, wire: Any
) -> None:
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    run = pvl.probe_pvl(_args())

    derivation = run.measurements["l5_psbl_above_upper_limit"]["price_derivation"]
    assert derivation["futs_mxpr"] == "453.6"
    assert derivation["tick_added"] == "0.02"
    assert session.calls[-1]["params"]["UNIT_PRICE"] == "453.62"


# ---------------------------------------------------------------------------
# CLI preconditions
# ---------------------------------------------------------------------------


def test_symbol_is_required_and_has_no_literal_default(
    futures_env: None, wire: Any
) -> None:
    """A default month would silently probe a leaf nobody is observing."""
    wire(_FakeSession(_price_body(), _green_psbl()))

    with pytest.raises(ProbeError, match="--symbol is required"):
        pvl.probe_pvl(_args(symbol=""))


def test_asset_stock_is_refused_rather_than_silently_ignored(
    futures_env: None, wire: Any
) -> None:
    """``--asset`` is a COMMON flag, so ``--asset stock`` parses fine.

    Every TR in this probe is 선물옵션 and the credentials resolve as futures
    unconditionally. Honouring the futures account under a stock flag would put
    a wrong ``args.asset`` in the artifact beside futures measurements.
    """
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    with pytest.raises(ProbeError, match="not available for P-VL"):
        pvl.probe_pvl(_args(asset="stock"))

    assert session.calls == []


def test_a_negative_pace_is_refused(futures_env: None, wire: Any) -> None:
    wire(_FakeSession(_price_body(), _green_psbl()))

    with pytest.raises(ProbeError, match=r"--pace-s must be >= 0"):
        pvl.probe_pvl(_args(pace_s=-1.0))


@pytest.mark.parametrize("symbol", ["ZZ99999", "005930", "A06610", "10", ""])
def test_a_non_kospi200_symbol_is_refused_before_any_contact(
    futures_env: None, wire: Any, symbol: str
) -> None:
    """Fail-closed on an unknown family.

    ``005930`` is a stock code, ``A06610`` is a neighbouring futures prefix, and
    ``10`` is a truncated one. None of them belong to 주가지수선물거래, so
    measuring them against this probe's 별표 rows would be wrong with no sign
    that it happened. The empty string is caught earlier, by the --symbol check.
    """
    session = wire(_FakeSession(_price_body(), _green_psbl()))

    with pytest.raises(ProbeError):
        pvl.probe_pvl(_args(symbol=symbol))

    assert session.calls == []


def test_the_refusal_message_names_the_accepted_prefixes() -> None:
    with pytest.raises(ProbeError, match="not a KOSPI200 index-futures code"):
        pvl._symbol_prefix("ZZ99999")

    with pytest.raises(ProbeError) as excinfo:
        pvl._symbol_prefix("005930")
    message = str(excinfo.value)
    assert "A05" in message and "101" in message and "A01" in message


def test_the_tick_is_read_from_the_config_file_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Point the loader at a different spec; the resolved tick must follow it.

    This is the test a literal 0.02 or a read of the paper policy's 5 could not
    pass. It is also the reachable failing input for the "no contract spec"
    refusal: every accepted prefix is registered today, so the only way that
    branch fires is a ``config/execution.yaml`` that dropped one.
    """
    other = tmp_path / "execution.yaml"
    other.write_text(
        _execution_yaml("kospi200_mini", tick="0.25", prefix="A05"), encoding="utf-8"
    )
    monkeypatch.setattr(pvl, "_EXECUTION_CONFIG", other)

    tick, record = pvl.resolve_instrument(_SYMBOL)

    assert tick.size == Decimal("0.25")
    assert "kospi200_mini" in tick.source
    assert record["registry_tick_points"] == "0.25"


def test_a_non_positive_registered_tick_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A zero tick cannot be corroborated against, so it is refused loudly.

    Reachable input: a ``config/execution.yaml`` whose spec declares
    ``tick_size_points: 0``. Without this the zero would flow into
    ``corroborate_tick``, where ``value % 0`` raises an opaque
    ``DecimalException`` instead of naming the config as the cause.
    """
    broken = tmp_path / "execution.yaml"
    broken.write_text(
        _execution_yaml("kospi200_mini", tick="0", prefix="A05"), encoding="utf-8"
    )
    monkeypatch.setattr(pvl, "_EXECUTION_CONFIG", broken)

    with pytest.raises(ProbeError, match="non-positive tick"):
        pvl.resolve_instrument(_SYMBOL)


def test_a_prefix_bound_to_another_product_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Finding 8's red proof: move ``A05`` off ``kospi200_mini``.

    The 별표 row and the tick come from two different files. Before the
    cross-check, this input produced an artifact carrying the mini 10,000 row
    beside the full-size 0.05 tick, silently. Now it refuses, naming both.
    """
    drifted = tmp_path / "execution.yaml"
    drifted.write_text(
        _execution_yaml("kospi200_full", tick="0.05", prefix="A05"), encoding="utf-8"
    )
    monkeypatch.setattr(pvl, "_EXECUTION_CONFIG", drifted)

    with pytest.raises(ProbeError) as excinfo:
        pvl.resolve_instrument(_SYMBOL)

    message = str(excinfo.value)
    assert "kospi200_mini" in message  # what this module's 별표 table says
    assert "kospi200_full" in message  # what execution.yaml resolved
    assert "별표" in message


def test_a_prefix_absent_from_the_resolved_specs_prefix_list_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The other half of the pairing: the spec must claim THIS prefix.

    A registry whose ``kospi200_mini`` matches ``A05`` only through a broader
    rule would resolve the right product for the wrong reason.
    """
    loose = tmp_path / "execution.yaml"
    loose.write_text(
        _execution_yaml("kospi200_mini", tick="0.02", prefix="A"), encoding="utf-8"
    )
    monkeypatch.setattr(pvl, "_EXECUTION_CONFIG", loose)

    with pytest.raises(ProbeError, match="symbol_prefix"):
        pvl.resolve_instrument(_SYMBOL)


def test_an_accepted_prefix_with_no_registered_spec_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The reachable failing input for the registry-miss branch."""
    empty = tmp_path / "execution.yaml"
    empty.write_text("futures_contract_spec: {}\n", encoding="utf-8")
    monkeypatch.setattr(pvl, "_EXECUTION_CONFIG", empty)

    with pytest.raises(ProbeError, match="no contract spec for --symbol"):
        pvl.resolve_instrument(_SYMBOL)


def test_the_full_size_family_resolves_its_own_tick_and_rulebook_row(
    futures_env: None, wire: Any, policy_tick: Any
) -> None:
    """``A01609`` is 코스피200선물거래: tick 0.05, 별표 17의2 regular 2,000.

    Both families are accepted. The point of resolving per symbol is that the
    mini row (10,000) and the full row (2,000) are different numbers, and a
    probe that assumed one would mislabel the other.
    """
    policy_tick(5)
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args(symbol="A01609")).measurements["resolved_instrument"]

    assert record["matched_prefix"] == "A01"
    assert record["resolved_product"] == "kospi200_full"
    assert record["registry_tick_points"] == "0.05"
    # With a 5 policy it is the full-size leaf that agrees.
    assert record["tick_registry_matches_policy"] is True
    row = record["krx_quantity_limit_row"]
    assert row["product"] == "코스피200선물거래"
    assert row["regular_session_contracts"] == 2000
    assert row["night_session_contracts"] == 1000


def test_the_mini_family_gets_the_mini_rulebook_row(
    futures_env: None, wire: Any
) -> None:
    """``A05610`` is 미니코스피200선물거래: 별표 17의2 regular 10,000.

    This is the row that governs the resident paper leaf. Reading the full-size
    2,000 onto it was the specific misreading this record exists to prevent.
    """
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args()).measurements["resolved_instrument"]

    assert record["matched_prefix"] == "A05"
    row = record["krx_quantity_limit_row"]
    assert row["product"] == "미니코스피200선물거래"
    assert row["regular_session_contracts"] == 10000
    assert row["night_session_contracts"] == 5000
    assert "별표 17의2 제1호" in row["source"]
    assert "제61조제3항" in row["caveats"]
    assert "누적호가수량한도" in row["caveats"]
    assert "CONTEXT" in record["krx_quantity_limit_is_context_only"]


def test_one_table_keys_the_prefixes_the_probe_accepts() -> None:
    """Finding 8's structural fix: ONE table, so there is nothing to drift.

    The prefix gate, the 별표 row and the 호가가격단위's 호 all read the same
    dict, so a prefix cannot be accepted without a row or carry a row for
    another product's article.
    """
    assert set(pvl.ACCEPTED_PREFIXES) == {"A05", "101", "A01"}
    assert set(pvl.KRX_PREFIX_TABLE) == set(pvl.ACCEPTED_PREFIXES)
    for prefix in pvl.ACCEPTED_PREFIXES:
        row = pvl.KRX_PREFIX_TABLE[prefix]
        assert row["registry_product"] in {"kospi200_mini", "kospi200_full"}
        assert row["tick_article"]
        assert row["evidence"]
    # A01 is the live front-month code for the SAME product as 101.
    assert pvl.KRX_PREFIX_TABLE["A01"] is pvl.KRX_PREFIX_TABLE["101"]


def test_rulebook_rows_cite_the_committed_evidence_texts() -> None:
    """Each row points into the parsed 별표 text, at the line range for ITS row.

    Design v2 §2.1 is explicit that v1's 2,000 was the full-size row read onto a
    mini product. A citation that did not distinguish the two line ranges would
    leave that mistake just as easy to repeat.
    """
    mini = pvl.KRX_PREFIX_TABLE["A05"]
    full = pvl.KRX_PREFIX_TABLE["101"]
    evidence_dir = "docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/"

    for row in (mini, full):
        assert row["evidence"].startswith(evidence_dir)
        assert "byeolpyo17-2_order_quantity_limits.txt:" in row["evidence"]
        assert "업무규정 제71조" in row["source"]
        assert "별표 17의2 제1호" in row["source"]
    assert mini["evidence"] != full["evidence"]


def test_liquidity_managed_variants_are_recorded_not_folded_in() -> None:
    """별표 17의2's parenthesised numbers are a DIFFERENT condition.

    10,000 applies unless the product is designated 유동성관리상품, in which case
    the limit is 1,000. The probe does not observe that designation, so folding
    the two into one number would state more than it knows.
    """
    mini = pvl.KRX_PREFIX_TABLE["A05"]
    full = pvl.KRX_PREFIX_TABLE["101"]

    assert mini["liquidity_managed_regular_contracts"] == 1000
    assert mini["liquidity_managed_night_contracts"] == 500
    assert full["liquidity_managed_regular_contracts"] == 200
    assert full["liquidity_managed_night_contracts"] == 100


@pytest.mark.parametrize(
    ("prefix", "ho"),
    [("A05", "제4조의9제2호"), ("101", "제4조의9제1호"), ("A01", "제4조의9제1호")],
)
def test_the_tick_article_is_the_ho_that_governs_that_product(
    prefix: str, ho: str
) -> None:
    """시행세칙 제4조의9: 제1호 is the full contract's unit, 제2호 the mini's."""
    assert ho in pvl.KRX_PREFIX_TABLE[prefix]["tick_article"]


def test_the_instrument_record_names_the_tick_article_and_the_drift_consequence(
    futures_env: None, wire: Any
) -> None:
    """A False ``tick_registry_matches_policy`` must not read as cosmetic.

    Design v2 §2.0 names what it costs later: once a band arrives, a 0.05 policy
    tick would judge a mini leaf's normal 0.02-grid quotes INADMISSIBLE. The
    record says so, and still leaves the disposition to the operator.
    """
    wire(_FakeSession(_price_body(), _green_psbl()))

    record = pvl.probe_pvl(_args()).measurements["resolved_instrument"]

    assert "제4조의9제2호" in record["registry_tick_rule_article"]
    assert "INADMISSIBLE" in record["why_the_drift_matters_later"]
    assert "predicates.py" in record["why_the_drift_matters_later"]


def test_the_basis_price_rule_records_the_article_55_4_adjustment() -> None:
    """제55조제4항 snaps 기준가격 to the nearest 호가가격단위 before the band.

    L2 floors and ceils FROM that basis, so a reader checking the arithmetic by
    hand needs to know the basis is already on-grid.
    """
    record = pvl.band_expectation(
        Decimal(_SDPR), ratio=Decimal("0.08"), tick=_MINI_TICK
    )

    assert "제55조제1항제2호" in record["basis_price_rule"]
    assert "제55조제4항" in record["basis_price_rule"]


def test_price_limit_stages_are_the_byeolpyo_14_ratios() -> None:
    assert (
        (1, Decimal("0.08")),
        (2, Decimal("0.15")),
        (3, Decimal("0.20")),
    ) == pvl.KRX_PRICE_LIMIT_STAGES
