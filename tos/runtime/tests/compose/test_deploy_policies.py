"""Compose e2e tests for the REAL deployed policy INSTANCE files"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import EffectBasis, EffectDimensionSpec
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.venue import OrderAdmissibilityResult, OrderShapeFields
from tos.venue.predicates import order_shape_admissible
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.marketfeed.policy import (
    CriticalInputPolicyConfigError,
    load_critical_input_policy,
)
from tos_runtime.marketfeed.time_projection import _DELAY_BOUND_FIELDS
from tos_runtime.time.config import _BOUND_FIELD_BY_KEY
from tos_runtime.venue import (
    VenuePolicyConfigError,
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
)
from .test_compose_root import _compose, _reach_trusted
from .test_deploy_config import _install_real_calendar, _kst_unix_ms
from .test_venue_wiring import _kind_count, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEPLOY_DIR = _REPO_ROOT / "config" / "tos_runtime" / "paper"
_REAL_VENUE_POLICY = _DEPLOY_DIR / "venue_constraint_policy.yaml"
_REAL_OCP = _DEPLOY_DIR / "order_construction_policy.yaml"

_TENANT_DIR = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-long"

_TENANT_SHORT_DIR = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-short"
_TENANT_VENUE_POLICY = _TENANT_DIR / "venue_constraint_policy.yaml"

_ADOPTED_TENANT_MAX_QTY = 10000

_TENANT_VENUE_POLICY_ID = "vcp-paper-cp3-setup-d-long-krx-index-futures"

_DECISION_9_PROVENANCE = (
    "결정 9 (a) · 운영자 채택 2026-10-08 · "
    "별표 17의2 제1호 미니코스피200선물거래 행 · 등급 R"
)

_DECISION_9_CAVEATS = (
    "회원(증권사)은 이보다 낮게 정할 수 있다",
    "KIS 측 한도는 미확인",
    "거래소가 시장관리상 변경할 수 있다",
    "누적호가수량한도는 다른 한도다",
)

_TICK_PROVENANCE = (
    "운영자 승인 2026-10-08 · 시행세칙 제4조의9 제2호 · 등급 R · "
    "브로커 정황 = P-VL band 격자(PR #881)"
)

_TICK_RESIDENT_DEFERRAL = "상주 `paper` 트리의 tick 은 5 그대로다"

_B1A_PRICE: tuple[str, str, str, str] = ("index_point", "hundredths", "100", "unsigned")
_B1A_BOOL: tuple[str, str, str, str] = ("bool", "none", "1", "unsigned")
_B1A_FIELD_POLICY: dict[str, tuple[str, str, str, str]] = {
    "open_x100": _B1A_PRICE,
    "high_x100": _B1A_PRICE,
    "low_x100": _B1A_PRICE,
    "close_x100": _B1A_PRICE,
    "volume": ("contract", "unit", "1", "unsigned"),
    "session_token": ("opaque_token", "none", "1", "unsigned"),
    "vwap_x100": _B1A_PRICE,
    "atr14_x100": _B1A_PRICE,
    "z_x1000": ("atr", "thousandths", "1000", "signed"),
    "hi_vol": _B1A_BOOL,
    "stall_ok": _B1A_BOOL,
    "reversal_ok": _B1A_BOOL,
    "entry_window": _B1A_BOOL,
    "vwap_reverted": _B1A_BOOL,
    "eod": _B1A_BOOL,
}

_B1A_BAR_PERIOD_MS = 60_000

_TENANT_MAX_AGE_MS = 800

_TIME_DELAY_BOUND_KEYS: tuple[str, ...] = tuple(
    key
    for field in _DELAY_BOUND_FIELDS
    for key, mapped in _BOUND_FIELD_BY_KEY.items()
    if mapped == field
)

_MAX_AGE_PROVENANCE = (
    "운영자 결정 2026-10-09: 800 ms (= 커널 시간 예산 1000 − Σ지연 200)",
    "」 · 등급 A(운영자 결정 2026-10-09)",
    "── 등급 A(운영자 결정 2026-10-09) ──",
    "VERIFICATION-PROFILE-002.yaml:1078",
    "`MAX_time_source_sequence_gap_ms` :1077 — 전부 APPROVED 2026-07-29",
    "값이 같아 조용히 통과하는 이웃 둘을 섞지 말 것",
    "A(§11 결정 11)",
    "M 은 「운영자·서버에서만 산출 가능」이고",
    "The label, not label+60s",
    "now_ms - as_of_ms",
    "현행 B1a 의미론에서는 열다섯 전부 STALE 이다",
    "저널에 append 하는 시각을 `as_of_ms` 로 찍어야 한다",
    "180000 은 폐기됐다",
    "올바른 한도는 180,000 이 아니라 위 800 ms 예산 자리수다",
    "보수 방향 = 작게",
)

_B1A_PRICE_FIELDS = frozenset(
    {"open_x100", "high_x100", "low_x100", "close_x100", "vwap_x100", "atr14_x100"}
)

_PAPER_DEFERRAL_NOTE = (
    "source exists (10-08 결정 9); paper adoption deferred by operator"
)


def _tenant_kernel_time_budget_ms() -> int:
    """The conservative freshness budget THIS TREE's own ``time.yaml`` leaves, derived the way"""
    time_cfg = yaml.safe_load((_TENANT_DIR / "time.yaml").read_text(encoding="utf-8"))

    assert len(_TIME_DELAY_BOUND_KEYS) == len(_DELAY_BOUND_FIELDS)
    assert set(_TIME_DELAY_BOUND_KEYS) <= set(time_cfg)

    return int(time_cfg["MAX_time_conservative_freshness_age_ms"]) - sum(
        int(time_cfg[name]) for name in _TIME_DELAY_BOUND_KEYS
    )


def _comment_prose(path: Path) -> str:
    """Every comment line's text with ``#`` and indentation removed, joined by single spaces."""
    words: list[str] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            words.extend(stripped.lstrip("#").split())
    return " ".join(words)


_RESIDENT_TICK = 5
_TENANT_TICK = 2
_ADOPTED_LOT = 1
_ADOPTED_MIN_QTY = 1
_ADOPTED_ADMITTING_PHASE = "CONTINUOUS"
_ADOPTED_OCP_VERSION = "1.0.0"


_OCP_ADMITTED_QUANTITY_BASIS = "RISK"

_OCP_FLAT_QUANTITY_BASIS = "ZERO_POSITION"

_OCP_DIRECTION = "LONG"

_BAND_JOURNAL_PATH_STAND_IN = "/nonexistent/producer-session/band.jsonl"


def _filled(
    path: Path,
    *,
    environment: str,
    account: str,
    instrument: str,
    direction: str = _OCP_DIRECTION,
    admits_flat_exit: bool = False,
) -> dict:
    """The real document with ONLY the operator-fill coordinates filled -- exactly what"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"policy document loaded as {type(raw).__name__}"
    assert raw["scope"]["accounts"] == ["TBD"]
    assert raw["scope"]["instruments"] == ["TBD"]
    raw["scope"]["environments"] = [environment]
    raw["scope"]["accounts"] = [account]
    raw["scope"]["instruments"] = [instrument]
    band_source = raw.get("_runtime", {}).get("band_source")
    if band_source is not None:
        assert band_source["instrument"] == "TBD"
        assert band_source["band_journal_path"] == "TBD"
        assert band_source["approved_source_prefixes"] == ["TBD"]
        band_source["instrument"] = instrument
        band_source["band_journal_path"] = _BAND_JOURNAL_PATH_STAND_IN
        band_source["approved_source_prefixes"] = ["tos-cp3-live"]
    construction = raw.get("_runtime", {}).get("construction")
    if construction is not None:
        expected_bases = [_OCP_ADMITTED_QUANTITY_BASIS]
        if admits_flat_exit:
            expected_bases.append(_OCP_FLAT_QUANTITY_BASIS)
        assert construction["sizing"]["admitted_quantity_bases"] == expected_bases
        direction_entries = [
            entry for entry in construction["axes"] if entry["axis"] == "DIRECTION"
        ]
        assert len(direction_entries) == 1
        assert direction_entries[0]["value"] == direction
    return raw


def _install_real_policies(config_dir: Path) -> tuple[str, str]:
    """Install the filled real policies over the fixture ones. Returns both freshly"""
    for source, target in (
        (_REAL_VENUE_POLICY, "venue_constraint_policy.yaml"),
        (_REAL_OCP, "order_construction_policy.yaml"),
    ):
        raw = _filled(
            source,
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
        )
        (config_dir / target).write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    venue = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    ocp = load_order_construction_policy(
        config_dir / "order_construction_policy.yaml", scheme=_SCHEME
    )
    assert venue.policy.canonical_digest is not None
    assert ocp.policy.canonical_digest is not None
    return venue.policy.canonical_digest, ocp.policy.canonical_digest


def test_real_policy_files_carry_their_approval_provenance() -> None:
    for path in (_REAL_VENUE_POLICY, _REAL_OCP):
        text = path.read_text(encoding="utf-8")
        assert "§6 ②" in text
        assert "DR-0002" in text
        assert "2026-09-16" in text


@pytest.mark.parametrize(
    "path, loader",
    [
        (_REAL_VENUE_POLICY, load_venue_constraint_policy),
        (_REAL_OCP, load_order_construction_policy),
    ],
)
def test_real_policy_files_refuse_to_load_until_the_operator_fills_the_scope(
    path: Path, loader
) -> None:
    """As committed, accounts/instruments are ``"TBD"`` -- the loader's"""
    with pytest.raises(VenuePolicyConfigError):
        loader(path, scheme=_SCHEME)


def test_filled_real_policies_carry_exactly_the_adopted_values(tmp_path: Path) -> None:
    venue_raw = _filled(
        _REAL_VENUE_POLICY, environment="paper", account="acct-x", instrument="inst-x"
    )
    venue_path = tmp_path / "venue_constraint_policy.yaml"
    venue_path.write_text(
        yaml.safe_dump(venue_raw, sort_keys=False, allow_unicode=True)
    )
    venue = load_venue_constraint_policy(venue_path, scheme=_SCHEME)

    shape = venue.policy.shape_constraints
    assert shape.tick_size == _RESIDENT_TICK
    assert shape.lot_size == _ADOPTED_LOT
    assert shape.min_quantity == _ADOPTED_MIN_QTY
    assert shape.price_min is None and shape.price_max is None
    assert shape.max_quantity is None
    assert set(venue.null_shape_bounds) == {"price_min", "price_max", "max_quantity"}
    assert shape.allowed_order_types == frozenset({"LIMIT"})
    assert shape.allowed_tifs == frozenset({"DAY"})
    assert shape.allowed_sides == frozenset({"BUY", "SELL"})
    assert shape.allowed_position_effects == frozenset({"OPEN", "CLOSE"})
    for action in (
        fx.ActionClass.NEW_LONG,
        fx.ActionClass.NEW_SHORT,
        fx.ActionClass.CLOSE,
    ):
        assert venue.policy.admitting_phases_for(action) == frozenset(
            {_ADOPTED_ADMITTING_PHASE}
        )
    assert venue.scope.instrument_class == "krx-index-futures"

    ocp_raw = _filled(
        _REAL_OCP, environment="paper", account="acct-x", instrument="inst-x"
    )
    ocp_path = tmp_path / "order_construction_policy.yaml"
    ocp_path.write_text(yaml.safe_dump(ocp_raw, sort_keys=False, allow_unicode=True))
    ocp = load_order_construction_policy(ocp_path, scheme=_SCHEME)
    assert ocp.policy.policy_version == _ADOPTED_OCP_VERSION
    assert ocp.policy.policy_generation == 3
    assert ocp.construction_generation == 1
    assert ocp.wire_codec_kind is None
    assert ocp.construction_rules.effect_dimensions == (
        EffectDimensionSpec(
            dimension_id="INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL",
            basis=EffectBasis.QUANTITY,
            unit="CONTRACTS",
            scale="1",
        ),
    )
    assert ocp.construction_rules.sizing_bound.admitted_quantity_bases == frozenset(
        {_OCP_ADMITTED_QUANTITY_BASIS}
    )


def test_tenant_venue_policy_carries_the_decision_9_provenance_and_its_three_caveats() -> (
    None
):
    """Design §8 step 5: the adopted value lands WITH its citation and §2.2's three caveats."""
    prose = _comment_prose(_TENANT_VENUE_POLICY)
    assert _DECISION_9_PROVENANCE in prose
    for caveat in _DECISION_9_CAVEATS:
        assert caveat in prose, caveat
    assert _TICK_PROVENANCE in prose
    assert _TICK_RESIDENT_DEFERRAL in prose

    tenant_raw = yaml.safe_load(_TENANT_VENUE_POLICY.read_text(encoding="utf-8"))
    resident_raw = yaml.safe_load(_REAL_VENUE_POLICY.read_text(encoding="utf-8"))
    assert tenant_raw["policy_id"] == _TENANT_VENUE_POLICY_ID
    assert tenant_raw["policy_id"] != resident_raw["policy_id"]
    assert tenant_raw["policy_generation"] == resident_raw["policy_generation"] == 1


def test_resident_paper_tree_records_the_deferral_rather_than_the_value() -> None:
    """The other half of design §8 step 5: the resident tree says a source now EXISTS and that"""
    assert _PAPER_DEFERRAL_NOTE in _comment_prose(_REAL_VENUE_POLICY)
    assert "cp3-setup-d-long" in _comment_prose(_REAL_VENUE_POLICY)


def test_tenant_venue_policy_refuses_to_load_until_the_operator_fills_the_scope() -> (
    None
):
    """The tenant tree inherits the SAME operator-fill gate: accounts/instruments are"""
    with pytest.raises(VenuePolicyConfigError):
        load_venue_constraint_policy(_TENANT_VENUE_POLICY, scheme=_SCHEME)


def test_filled_tenant_venue_policy_carries_10000_with_the_band_still_null(
    tmp_path: Path,
) -> None:
    """Decision 9 (a) is a NECESSARY, not sufficient, condition (design §3): the quantity"""
    raw = _filled(
        _TENANT_VENUE_POLICY,
        environment="paper",
        account="acct-x",
        instrument="inst-x",
    )
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))
    venue = load_venue_constraint_policy(path, scheme=_SCHEME)

    shape = venue.policy.shape_constraints
    assert shape.max_quantity == _ADOPTED_TENANT_MAX_QTY
    assert shape.price_min is None and shape.price_max is None
    assert set(venue.null_shape_bounds) == {"price_min", "price_max"}
    assert shape.tick_size == _TENANT_TICK
    assert shape.tick_size != _RESIDENT_TICK
    assert shape.lot_size == _ADOPTED_LOT
    assert shape.min_quantity == _ADOPTED_MIN_QTY
    assert venue.scope.instrument_class == "krx-index-futures"

    on_grid = OrderShapeFields(
        price=5 * 100_000,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )
    assert order_shape_admissible(on_grid, shape) is OrderAdmissibilityResult.UNKNOWN


def test_tenant_critical_input_policy_declares_fifteen_fields_with_the_adopted_max_age_ms() -> (
    None
):
    """CP-3 kickoff §5 1 / §5 3 ②: the tenant tree declares B1a's fifteen upstream fields with"""
    path = _TENANT_DIR / "critical_input_policy.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert [entry["field_key"] for entry in raw["fields"]] == list(_B1A_FIELD_POLICY)

    multipliers = {entry["field_key"]: entry["multiplier"] for entry in raw["fields"]}
    signs = {entry["field_key"]: entry["sign"] for entry in raw["fields"]}
    assert {
        key for key, multiplier in multipliers.items() if multiplier == "100"
    } == _B1A_PRICE_FIELDS
    assert {key for key, sign in signs.items() if sign == "signed"} == {"z_x1000"}

    for entry in raw["fields"]:
        key = entry["field_key"]
        assert (
            entry["unit"],
            entry["scale"],
            entry["multiplier"],
            entry["sign"],
        ) == _B1A_FIELD_POLICY[key], key
        assert entry["max_age_ms"] == _TENANT_MAX_AGE_MS, key

    policy = load_critical_input_policy(path, scheme=_SCHEME)
    assert [field.field_key for field in policy.fields] == list(_B1A_FIELD_POLICY)
    assert {field.max_age_ms for field in policy.fields} == {_TENANT_MAX_AGE_MS}


@pytest.mark.parametrize(
    "tree_dir", [_TENANT_DIR, _TENANT_SHORT_DIR], ids=["long", "short"]
)
def test_both_tenant_headers_carry_the_max_age_provenance(tree_dir: Path) -> None:
    """The provenance the adopted value cannot be read without -- in **both** tenant headers."""
    prose = _comment_prose(tree_dir / "critical_input_policy.yaml")
    for sentence in _MAX_AGE_PROVENANCE:
        assert sentence in prose, (tree_dir.name, sentence)


def test_tenant_critical_input_policy_still_refuses_a_null_max_age_ms(
    tmp_path: Path,
) -> None:
    """Filling the fifteen did not retire the loader's refusal -- pinned BY KEY NAME against a"""
    raw = yaml.safe_load(
        (_TENANT_DIR / "critical_input_policy.yaml").read_text(encoding="utf-8")
    )
    assert raw["fields"][-1]["field_key"] == "eod"
    raw["fields"][-1]["max_age_ms"] = None
    path = tmp_path / "critical_input_policy.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(CriticalInputPolicyConfigError) as excinfo:
        load_critical_input_policy(path, scheme=_SCHEME)
    assert "max_age_ms" in str(excinfo.value)


def test_the_adopted_max_age_ms_is_the_kernel_budget_label_stamped_bars_cannot_meet() -> (
    None
):
    """The operator's 2026-10-09 decision, as arithmetic rather than a comment -- and its honest"""
    budget = _tenant_kernel_time_budget_ms()

    assert budget == _TENANT_MAX_AGE_MS

    assert _TENANT_MAX_AGE_MS < _B1A_BAR_PERIOD_MS


def test_tenant_construction_price_field_keys_are_declared_critical_inputs() -> None:
    """``construction.yaml``'s two price field keys must name fields the SAME tree's"""
    construction = yaml.safe_load(
        (_TENANT_DIR / "construction.yaml").read_text(encoding="utf-8")
    )
    critical_input = yaml.safe_load(
        (_TENANT_DIR / "critical_input_policy.yaml").read_text(encoding="utf-8")
    )
    declared = {entry["field_key"] for entry in critical_input["fields"]}

    for key_name in ("price_field_key", "shape_price_field_key"):
        key = construction[key_name]
        assert key in declared, (
            f"construction.yaml::{key_name} = {key!r} is not declared by this tree's "
            f"critical_input_policy.yaml (declared: {sorted(declared)})"
        )
        assert key in _B1A_PRICE_FIELDS, (key_name, key)


def test_real_policies_boot_the_compose_root_and_the_attempt_denies_fail_closed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Real calendar + filled real policies, Monday 2026-09-07 10:00 KST"""
    _install_real_calendar(config_dir)
    venue_digest, ocp_digest = _install_real_policies(config_dir)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 7, 10, 0)),
    )
    _reach_trusted(runtime)

    bound = _rows(runtime, "VENUE_POLICY_BOUND")
    assert len(bound) == 1
    assert bound[0]["canonical_digest"] == venue_digest
    assert set(bound[0]["null_shape_bounds"]) == {
        "price_min",
        "price_max",
        "max_quantity",
    }
    assert _kind_count(runtime, "ORDER_CONSTRUCTION_POLICY_BOUND") == 1
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == (
        _ADOPTED_ADMITTING_PHASE
    )

    results = runtime.run_once((fx.crossing_event(),))
    assert results[0].flow is not None
    verdicts = {v.step: v for v in results[0].flow.verdicts}
    step2 = verdicts[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    assert step2.outcome is StageOutcome.DENY
    assert "quantity constraint is incomplete" in (step2.reason or "")
    assert CommitmentStep.VENUE_ADMISSIBILITY_DECISION not in verdicts
    assert runtime.venue.last_decision is None
    assert _kind_count(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED") == 0
    assert runtime.venue.quantity_constraint.max_quantity is None

    on_grid = OrderShapeFields(
        price=5 * 100_000,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )
    assert (
        order_shape_admissible(on_grid, runtime.venue.shape_constraints)
        is OrderAdmissibilityResult.UNKNOWN
    )

    construction = runtime.construction_stage.construction
    assert construction is not None
    assert construction.command is None
    assert runtime.venue.policy.canonical_digest == venue_digest
    assert (
        construction.policy is None
        or construction.policy.canonical_digest == ocp_digest
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()
