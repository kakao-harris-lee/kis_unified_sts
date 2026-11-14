"""Compose e2e pins for the REAL deployed values under ``config/tos_runtime/paper/``"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.authority.epoch import AuthorityConfigError, load_authority_config
from tos_runtime.brokercap.scopes import BrokerScopeConfigError, load_broker_scopes
from tos_runtime.compose._construction_config import (
    CONSTRUCTION_CONFIG_NAME,
    ConstructionConfigError,
    load_construction_config,
)
from tos_runtime.compose._egress_coordinates import (
    EgressCoordinateConfigError,
    load_egress_coordinates,
)
from tos_runtime.compose._engine_config import EngineConfigError, load_engine_config
from tos_runtime.compose._engine_wiring import (
    EngineDriverConfigError,
    load_engine_driver_config,
)
from tos_runtime.compose._preconditions import (
    CoordinatorPreconditionsConfigError,
    load_coordinator_preconditions_config,
)
from tos_runtime.compose._risk_attestations import (
    RiskAttestationConfigError,
    load_risk_attestations,
)
from tos_runtime.currentness.config import (
    CurrentnessConfigError,
    load_currentness_config,
)
from tos_runtime.marketfeed.policy import (
    CRITICAL_INPUT_POLICY_CONFIG_NAME,
    load_critical_input_policy,
)
from tos_runtime.posttrade.config import FinalityConfigError, load_finality_config
from tos_runtime.release.config import (
    ReleaseAdmissionConfigError,
    load_release_config,
)
from tos_runtime.safety.monitoring import MonitoringConfigError, MonitoringService
from tos_runtime.time.config import TimeConfigError, load_time_config

from ._loader_probe import format_table, refusing_labels, run_probes
from .conftest import EXPECTED_CODE_DIGEST

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEPLOY_DIR = _REPO_ROOT / "config" / "tos_runtime" / "paper"

_ENVIRONMENT_LABEL = "non-live-test"

_PROVENANCE = "docs/plans/2026-09-18-tos-config-value-proposal.md"
_APPROVAL_DATES = ("2026-09-18", "2026-09-23")

_NOT_A_SAFETY_POSTURE = "첫 부팅 프로파일이지 운영 안전 태세가 아니다"

_ADOPTED_BY_THIS_WAVE: tuple[str, ...] = (
    "time.yaml",
    "authority.yaml",
    "release.yaml",
    "currentness.yaml",
    "risk_attestations.yaml",
    "egress_coordinates.yaml",
    "broker_scopes.yaml",
    "engine.yaml",
    "engine_driver.yaml",
    "coordinator_preconditions.yaml",
    "finality.yaml",
    "monitor_coverage.yaml",
)


_VALUE_PINS: dict[str, Any] = {
    "time.yaml::MAX_time_source_precision_ms": 50,
    "time.yaml::MAX_time_transport_and_queue_uncertainty_ms": 50,
    "time.yaml::MAX_time_source_disagreement_ms": 50,
    "time.yaml::MAX_clock_domain_conversion_uncertainty_ms": 50,
    "time.yaml::MAX_future_timestamp_tolerance_ms": 50,
    "time.yaml::MAX_time_source_sequence_gap_ms": 50,
    "time.yaml::MAX_process_suspension_ms": 2000,
    "time.yaml::MAX_critical_input_consumer_receipt_age_ms": 1000,
    "time.yaml::MAX_time_conservative_freshness_age_ms": 1000,
    "time.yaml::MIN_time_independent_reference_count": 1,
    "time.yaml::MAX_send_result_wait_ms": 2000,
    "time.yaml::time_health_snapshot_heartbeat_ms": 55000,
    "time.yaml::tz_db_version": "2026c",
    "time.yaml::trading_calendar_version": "krx-2026.11",
    "time.yaml::verification_profile_version": "VERIFICATION-PROFILE-002-v2.1",
    "time.yaml::safety_profile_version": "tos-paper-profile-g1",
    "authority.yaml::containment_bound_ms": 1000,
    "authority.yaml::trading_approval_policy_generation": 1,
    "release.yaml::expected_dependency_set_digest": "20559763a1132fc75f71f3d83e99512f4b0d9cdde9e0df61b54b9d2459f98d8b",
    "release.yaml::admission_result": "ADMIT",
    "release.yaml::restriction_state_resolved": True,
    "release.yaml::restriction_present": False,
    "release.yaml::restriction.restriction_id": None,
    "release.yaml::restriction.restriction_generation": None,
    "release.yaml::restriction.trigger_class": None,
    "currentness.yaml::B_capability_claim_to_send": 500,
    "currentness.yaml::required_dimensions": [
        "COMMIT_LOG",
        "CURRENTNESS_POLICY",
        "ENVIRONMENT_SCOPE",
        "MONITORING",
        "POST_TRADE",
        "RECOVERY",
        "RELEASE",
        "SAFETY_AUTHORITY",
        "TRUSTWORTHY_TIME",
    ],
    "risk_attestations.yaml::numerically_safe.attested": True,
    "risk_attestations.yaml::valuation_ok.attested": True,
    "risk_attestations.yaml::all_fields_attributed.attested": True,
    "risk_attestations.yaml::limit_source_is_injected_envelope.attested": True,
    "risk_attestations.yaml::economic_commitment_exclusive.attested": True,
    "risk_attestations.yaml::flow_commitment_exclusive.attested": True,
    "egress_coordinates.yaml::endpoint.value": "synthetic://paper/order",
    "egress_coordinates.yaml::action.value": "NEW_ORDER",
    "egress_coordinates.yaml::method.value": "SUBMIT",
    "egress_coordinates.yaml::route_identity.value": "synthetic-route",
    "egress_coordinates.yaml::credential_generation.value": 0,
    "egress_coordinates.yaml::broker_session_generation.value": 0,
    "egress_coordinates.yaml::egress_generation.value": 1,
    "egress_coordinates.yaml::active_principal.value": "egressgw-{environment_label}",
    "egress_coordinates.yaml::capsule_terminus_fields.value": ["account", "instrument"],
    "broker_scopes.yaml::active_scope": "SYNTHETIC_FUTURES_ORDER",
    "engine.yaml::dsl_evaluation_budget_steps": 64,
    "engine.yaml::max_unresolved_send_per_scope": 1,
    "engine_driver.yaml::replay_window_events": 1000000,
    "coordinator_preconditions.yaml::live_authorization_state": "NOT_AUTHORIZED",
    "coordinator_preconditions.yaml::nonlive_broker_consuming.admitted": False,
    "finality.yaml::currency": "KRW",
    "finality.yaml::release_proof_wait_ms": 60000,
    "finality.yaml::value_date": "T+1",
    "finality.yaml::source_revision": None,
    "finality.yaml::proof_recipe_id": "tos-paper-proof-recipe-bootproof-g1",
    "finality.yaml::witness": "synthetic_venue_ledger",
    "monitor_coverage.yaml::coverage.coverage_generation": 1,
    "monitor_coverage.yaml::coverage.bounds.max_evidence_tip_stall_ms": 60000,
    "monitor_coverage.yaml::coverage.bounds.max_inbox_unconsumed": 100,
}


_UNPINNED_BY_DESIGN: dict[str, str] = {
    "release.yaml::expected_code_digest": (
        "운영자 승인값이 아니라 **측정값**이다 — 값 핀 대신 "
        "test_release_code_digest_pin_equals_the_measured_source_tree 가 "
        "측정 자체와 대조한다(핀을 손으로 적는 자리를 하나 없앤다)"
    ),
    "broker_scopes.yaml::instance_path": (
        "example 축자 복사 — byte-identity 핀이 값 핀보다 강하게 덮는다"
    ),
    "broker_scopes.yaml::environment_binding.*": (
        "example 축자 복사(KIS INSTANCE 의 environment 대응표) — byte-identity 핀이 덮는다"
    ),
    "broker_scopes.yaml::asset_binding.*": (
        "example 축자 복사(INSTANCE 의 instrument_class 대응표) — byte-identity 핀이 덮는다"
    ),
    "broker_scopes.yaml::scopes": (
        "example 축자 복사한 4 스코프 테이블 전체 — byte-identity 핀이 줄 단위로 덮는다"
    ),
}


def _read(name: str) -> str:
    return (_DEPLOY_DIR / name).read_text(encoding="utf-8")


def _mapping(name: str) -> dict[str, Any]:
    raw = yaml.safe_load(_read(name))
    assert isinstance(raw, dict), f"{name} did not load as a mapping"
    return raw


def _leaves(node: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every non-mapping node, as ``(dotted.path, value)``. A list is ONE leaf."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaves(value, f"{prefix}.{key}" if prefix else str(key))
    else:
        yield prefix, node


def _all_leaf_refs(config_dir: Path) -> dict[str, Any]:
    """``{"<file>::<dotted>": value}`` across all 18 adopted files."""
    found: dict[str, Any] = {}
    for name in _ADOPTED_BY_THIS_WAVE:
        raw = yaml.safe_load((config_dir / name).read_text(encoding="utf-8"))
        for path, value in _leaves(raw):
            found[f"{name}::{path}"] = value
    return found


def _is_unpinned_by_design(ref: str) -> bool:
    for pattern in _UNPINNED_BY_DESIGN:
        if pattern.endswith("*"):
            if ref.startswith(pattern[:-1]):
                return True
        elif ref == pattern:
            return True
    return False


def _unaccounted_leaves(config_dir: Path) -> list[str]:
    """Leaves that are neither value-pinned nor exempted — the completeness gate's own"""
    return sorted(
        ref
        for ref in _all_leaf_refs(config_dir)
        if ref not in _VALUE_PINS and not _is_unpinned_by_design(ref)
    )


def _mismatched_pins(config_dir: Path) -> list[tuple[str, Any, Any]]:
    """``[(ref, approved, actual), …]`` — empty when every pinned leaf still holds its value."""
    actual = _all_leaf_refs(config_dir)
    return [
        (ref, approved, actual.get(ref))
        for ref, approved in _VALUE_PINS.items()
        if ref not in actual or actual[ref] != approved
    ]


def _deploy_copy(tmp_path: Path, *names: str) -> Path:
    """Copy REAL deploy files into ``tmp_path`` so a test may mutate them — the named ones,"""
    dest = tmp_path / "deploy"
    dest.mkdir(exist_ok=True)
    for name in names or _ADOPTED_BY_THIS_WAVE:
        (dest / name).write_text(_read(name), encoding="utf-8")
    return dest


def _resolve_dotted(mapping: dict[str, Any], dotted: str) -> Any:
    cursor: Any = mapping
    for key in dotted.split("."):
        cursor = cursor[key]
    return cursor


def _substitute_scalar_line(path: Path, dotted_key: str, new_value_text: str) -> None:
    """Rewrite the one YAML line holding ``dotted_key``'s scalar so it holds"""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    parts = dotted_key.split(".")
    start = 0
    for anchor in parts[:-1]:
        anchor_pattern = re.compile(rf"^\s*{re.escape(anchor)}:\s*$")
        anchor_hits = [
            i for i in range(start, len(lines)) if anchor_pattern.match(lines[i])
        ]
        assert (
            anchor_hits
        ), f"{path.name}: anchor {anchor!r} of {dotted_key!r} not found"
        start = anchor_hits[0] + 1
    key = parts[-1]
    pattern = re.compile(rf"^(\s*){re.escape(key)}:(?:\s|$)")
    hits = [i for i in range(start, len(lines)) if pattern.match(lines[i])]
    if len(parts) == 1:
        assert len(hits) == 1, (
            f"{path.name}: {key!r} matched {len(hits)} lines, expected exactly 1 "
            "(add a dotted anchor)"
        )
    assert hits, f"{path.name}: {dotted_key!r} matched no line"
    index = hits[0]
    match = pattern.match(lines[index])
    assert match is not None
    lines[index] = f"{match.group(1)}{key}: {new_value_text}\n"
    path.write_text("".join(lines), encoding="utf-8")


def _text_set_null(path: Path, dotted_key: str) -> None:
    """Flip one scalar leaf back to ``null`` (named-TBD), asserting it was filled first — a"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert (
        _resolve_dotted(raw, dotted_key) is not None
    ), f"{path.name}:{dotted_key} was already null"
    _substitute_scalar_line(path, dotted_key, "null")


def _no_op_observer() -> Any:
    raise AssertionError("observer must not be reached during config load")


def _monitoring_service(config_dir: Path) -> MonitoringService:
    """Construct the service purely to exercise its config load — every injected observer"""
    return MonitoringService(
        config_path=config_dir / "monitor_coverage.yaml",
        evidence_tip_observer=lambda: _no_op_observer(),
        inbox_unconsumed_observer=lambda: _no_op_observer(),
        monotonic_ns=lambda: _no_op_observer(),
        evidence_recorder=lambda *_args, **_kwargs: _no_op_observer(),
    )


def test_every_adopted_leaf_is_pinned_or_explicitly_unpinned() -> None:
    """review-794 HIGH-2, the class fix rather than the instance fix: it is not enough to add"""
    unaccounted = _unaccounted_leaves(_DEPLOY_DIR)
    assert not unaccounted, (
        "these adopted leaves are neither value-pinned nor listed in _UNPINNED_BY_DESIGN "
        f"with a reason: {unaccounted}"
    )


def test_the_completeness_gate_actually_fires(tmp_path: Path) -> None:
    """Dead-check guard: a gate that can never report anything is not a gate. Add a leaf to a"""
    config_dir = _deploy_copy(tmp_path)
    (config_dir / "engine.yaml").write_text(
        _read("engine.yaml") + "\nleaf_added_by_this_test: 7\n", encoding="utf-8"
    )
    assert "engine.yaml::leaf_added_by_this_test" in _unaccounted_leaves(config_dir)


def test_no_pin_names_a_leaf_that_no_longer_exists() -> None:
    """The reverse drift: a pin left behind after its leaf was renamed or removed silently"""
    present = _all_leaf_refs(_DEPLOY_DIR)
    stale_pins = sorted(ref for ref in _VALUE_PINS if ref not in present)
    stale_exemptions = sorted(
        pattern
        for pattern in _UNPINNED_BY_DESIGN
        if not any(
            _is_unpinned_by_design(ref) and ref.startswith(pattern.rstrip("*"))
            for ref in present
        )
    )
    assert (
        not stale_pins
    ), f"_VALUE_PINS names leaves that no longer exist: {stale_pins}"
    assert (
        not stale_exemptions
    ), f"_UNPINNED_BY_DESIGN names leaves that no longer exist: {stale_exemptions}"


@pytest.mark.parametrize("ref", sorted(_VALUE_PINS))
def test_approved_value_is_unchanged(ref: str) -> None:
    """The value itself — this is the path review-794 HIGH-2 found empty: an approved value"""
    name, _, dotted = ref.partition("::")
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert cursor == _VALUE_PINS[ref]


@pytest.mark.parametrize(
    ("name", "key", "unapproved_text"),
    [
        ("engine_driver.yaml", "replay_window_events", "1"),
        ("time.yaml", "MAX_time_source_precision_ms", "5000"),
        ("time.yaml", "MAX_process_suspension_ms", "999999"),
        ("time.yaml", "MIN_time_independent_reference_count", "99"),
        ("time.yaml", "tz_db_version", '"1999a"'),
        ("engine.yaml", "max_unresolved_send_per_scope", "50"),
        ("authority.yaml", "containment_bound_ms", "99999"),
        ("monitor_coverage.yaml", "coverage.bounds.max_inbox_unconsumed", "999999"),
    ],
)
def test_a_value_pin_actually_fires(
    name: str, key: str, unapproved_text: str, tmp_path: Path
) -> None:
    """Proves the pins are LIVE, not merely present: change a real approved value to another"""
    config_dir = _deploy_copy(tmp_path)
    _substitute_scalar_line(config_dir / name, key, unapproved_text)
    mismatches = _mismatched_pins(config_dir)
    assert any(ref == f"{name}::{key}" for ref, _, _ in mismatches), (
        f"changing {name}::{key} to {unapproved_text} did not trip any value pin "
        f"(mismatches: {mismatches})"
    )


@dataclass(frozen=True)
class _LoadablePin:
    """One adopted file that loads cleanly, plus the one leaf a mutation nulls."""

    label: str
    files: tuple[str, ...]
    load: Callable[[Path], object]
    error: type[Exception]
    mutate: tuple[str, str]


_LOADABLE: tuple[_LoadablePin, ...] = (
    _LoadablePin(
        label="time.yaml",
        files=("time.yaml",),
        load=lambda d: load_time_config(d / "time.yaml"),
        error=TimeConfigError,
        mutate=("time.yaml", "MAX_time_source_precision_ms"),
    ),
    _LoadablePin(
        label="authority.yaml",
        files=("authority.yaml",),
        load=lambda d: load_authority_config(d / "authority.yaml"),
        error=AuthorityConfigError,
        mutate=("authority.yaml", "containment_bound_ms"),
    ),
    _LoadablePin(
        label="release.yaml",
        files=("release.yaml",),
        load=lambda d: load_release_config(d / "release.yaml"),
        error=ReleaseAdmissionConfigError,
        mutate=("release.yaml", "admission_result"),
    ),
    _LoadablePin(
        label="currentness.yaml",
        files=("currentness.yaml",),
        load=lambda d: load_currentness_config(d / "currentness.yaml"),
        error=CurrentnessConfigError,
        mutate=("currentness.yaml", "B_capability_claim_to_send"),
    ),
    _LoadablePin(
        label="risk_attestations.yaml",
        files=("risk_attestations.yaml",),
        load=lambda d: load_risk_attestations(d / "risk_attestations.yaml"),
        error=RiskAttestationConfigError,
        mutate=("risk_attestations.yaml", "numerically_safe.attested"),
    ),
    _LoadablePin(
        label="egress_coordinates.yaml",
        files=("egress_coordinates.yaml",),
        load=lambda d: load_egress_coordinates(
            d / "egress_coordinates.yaml", environment_label=_ENVIRONMENT_LABEL
        ),
        error=EgressCoordinateConfigError,
        mutate=("egress_coordinates.yaml", "route_identity.value"),
    ),
    _LoadablePin(
        label="broker_scopes.yaml",
        files=("broker_scopes.yaml",),
        load=lambda d: load_broker_scopes(
            d / "broker_scopes.yaml", environment_label=_ENVIRONMENT_LABEL
        ),
        error=BrokerScopeConfigError,
        mutate=("broker_scopes.yaml", "active_scope"),
    ),
    _LoadablePin(
        label="engine.yaml",
        files=("engine.yaml",),
        load=lambda d: load_engine_config(d / "engine.yaml"),
        error=EngineConfigError,
        mutate=("engine.yaml", "max_unresolved_send_per_scope"),
    ),
    _LoadablePin(
        label="engine_driver.yaml",
        files=("engine_driver.yaml",),
        load=lambda d: load_engine_driver_config(d / "engine_driver.yaml"),
        error=EngineDriverConfigError,
        mutate=("engine_driver.yaml", "replay_window_events"),
    ),
    _LoadablePin(
        label="coordinator_preconditions.yaml",
        files=("coordinator_preconditions.yaml",),
        load=lambda d: load_coordinator_preconditions_config(
            d / "coordinator_preconditions.yaml"
        ),
        error=CoordinatorPreconditionsConfigError,
        mutate=("coordinator_preconditions.yaml", "live_authorization_state"),
    ),
    _LoadablePin(
        label="monitor_coverage.yaml",
        files=("monitor_coverage.yaml",),
        load=_monitoring_service,
        error=MonitoringConfigError,
        mutate=("monitor_coverage.yaml", "coverage.bounds.max_inbox_unconsumed"),
    ),
)


def _loadable_ids() -> list[str]:
    return [pin.label for pin in _LOADABLE]


@pytest.mark.parametrize("pin", _LOADABLE, ids=_loadable_ids())
def test_real_deploy_file_loads_through_its_real_loader(pin: _LoadablePin) -> None:
    """A-2: the file an operator actually deploys is read by the loader that reads it at"""
    pin.load(_DEPLOY_DIR)


@pytest.mark.parametrize("pin", _LOADABLE, ids=_loadable_ids())
def test_named_tbd_mutation_of_one_approved_value_refuses(
    pin: _LoadablePin, tmp_path: Path
) -> None:
    """Mutation lens: the SAME real values with exactly one approved leaf flipped back to"""
    config_dir = _deploy_copy(tmp_path, *pin.files)
    file_name, key = pin.mutate
    _text_set_null(config_dir / file_name, key)
    with pytest.raises(pin.error, match=re.escape(key.split(".")[-1])):
        pin.load(config_dir)


_EXPECTED_REFUSALS: dict[str, str] = {
    "finality.yaml": "source_revision 은 렌더 산출물(배포 SHA) — 커밋 파일은 자기 SHA 를 담을 수 없다",
    "venue_constraint_policy.yaml": "운영자 좌표 scope.accounts — 렌더가 저장소 밖에서 채운다",
    "order_construction_policy.yaml": "운영자 좌표 scope.accounts — 렌더가 저장소 밖에서 채운다",
    "aggregate_risk_policy.yaml": "운영자 좌표 instrument_scope — 렌더가 저장소 밖에서 채운다",
    "action_flow_policy.yaml": "운영자 좌표 account_scope — 렌더가 저장소 밖에서 채운다",
    "construction.yaml": "부팅 증명 픽스처 · 좌표 account/instrument 는 렌더가 채운다",
    "strategies/": "부팅 증명 픽스처 · 좌표 target.account/instrument 는 렌더가 채운다",
    "marketfeed.yaml": "부팅 증명 픽스처 · 좌표 instruments/account/journal_path 는 렌더가 채운다",
}


def test_loader_probe_partition_is_as_recorded() -> None:
    """review-794 MEDIUM-4: the landing record's "N PASS / M REFUSE" must be re-derivable."""
    outcomes = run_probes(_DEPLOY_DIR)
    assert refusing_labels(outcomes) == frozenset(_EXPECTED_REFUSALS), format_table(
        outcomes
    )
    passed = sum(1 for outcome in outcomes if outcome.passed)
    assert (passed, len(outcomes)) == (14, 22), format_table(outcomes)


@pytest.mark.parametrize("name", _ADOPTED_BY_THIS_WAVE)
def test_adopted_file_cites_its_approval_provenance(name: str) -> None:
    """``config/tos_runtime/README.md``: "never add a value here without that citation"."""
    text = _read(name)
    assert _PROVENANCE in text, f"{name} does not cite the value proposal"
    for date in _APPROVAL_DATES:
        assert date in text, f"{name} does not carry the {date} approval date"


@pytest.mark.parametrize("name", _ADOPTED_BY_THIS_WAVE)
def test_adopted_file_says_it_is_not_a_safety_posture(name: str) -> None:
    """Proposal §0, binding: "채택되는 각 파일에 이 문장을 주석으로 박는다" — a reader"""
    assert _NOT_A_SAFETY_POSTURE in _read(
        name
    ), f"{name} omits the proposal §0 sentence"


def test_live_authorization_state_is_the_only_supported_posture() -> None:
    """Proposal §1 [S] — the single value ``compose/_preconditions.py``'s"""
    assert (
        _mapping("coordinator_preconditions.yaml")["live_authorization_state"]
        == "NOT_AUTHORIZED"
    )


def test_nonlive_broker_consuming_is_not_admitted() -> None:
    """Proposal §4.1 ⚠ — the narrower posture. Turning this on is a separate operator"""
    admitted = _mapping("coordinator_preconditions.yaml")["nonlive_broker_consuming"][
        "admitted"
    ]
    assert admitted is False


def test_active_scope_is_the_only_non_broker_reaching_scope() -> None:
    """Proposal §4.1 ⚠ — ``SYNTHETIC_FUTURES_ORDER`` is the one scope in the table that"""
    assert _mapping("broker_scopes.yaml")["active_scope"] == "SYNTHETIC_FUTURES_ORDER"


def test_broker_scopes_body_is_the_shipped_example_plus_one_line() -> None:
    """The deploy file was COPIED from ``broker_scopes.example.yaml``, never hand-retyped:"""
    example_lines = (
        (_REPO_ROOT / "tos" / "runtime" / "config" / "broker_scopes.example.yaml")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    deploy_lines = _read("broker_scopes.yaml").splitlines()
    assert len(deploy_lines) > len(example_lines)
    body = deploy_lines[-len(example_lines) :]
    differing = [(a, b) for a, b in zip(example_lines, body, strict=True) if a != b]
    assert len(differing) == 1, f"expected exactly one changed line, got {differing}"
    example_line, deploy_line = differing[0]
    assert example_line == "active_scope: null"
    assert deploy_line.startswith("active_scope: SYNTHETIC_FUTURES_ORDER")


def test_release_code_digest_pin_equals_the_measured_source_tree() -> None:
    """The pin against the MEASUREMENT, not against a second copy of the hex."""
    assert _mapping("release.yaml")["expected_code_digest"] == EXPECTED_CODE_DIGEST, (
        "release.yaml's expected_code_digest is stale for this source tree — "
        "run `python tools/tos_redigest.py --write` and commit the three files"
    )


def test_release_admission_is_admit_paired_with_no_restriction() -> None:
    """Proposal §4.1 ⚠ — ``ADMIT`` (never the non-existent ``ADMITTED`` the proposal's own"""
    release = _mapping("release.yaml")
    assert release["admission_result"] == "ADMIT"
    assert release["restriction_present"] is False
    assert release["restriction_state_resolved"] is True


def test_all_six_risk_attestations_are_operator_asserted() -> None:
    """Proposal §4.1 ⚠ — six step 6/7 admission witnesses with NO Phase 2 producer. These"""
    attestations = _mapping("risk_attestations.yaml")
    assert sorted(attestations) == [
        "all_fields_attributed",
        "economic_commitment_exclusive",
        "flow_commitment_exclusive",
        "limit_source_is_injected_envelope",
        "numerically_safe",
        "valuation_ok",
    ]
    for field, block in attestations.items():
        assert block["attested"] is True, field


def test_replay_window_covers_the_whole_inbox() -> None:
    """Proposal §4.2 ⚠ (review-794 HIGH-1): the file's own header warns that a window smaller"""
    assert _mapping("engine_driver.yaml")["replay_window_events"] == 1_000_000


def test_time_trading_calendar_version_matches_the_deployed_calendar() -> None:
    """``calendar/owner.py:170-179`` refuses to boot (``SessionCalendarMismatch``) when the"""
    assert (
        _mapping("time.yaml")["trading_calendar_version"]
        == _mapping("calendar.yaml")["calendar_version"]
    )


def test_snapshot_heartbeat_is_shorter_than_the_closed_evaluate_interval() -> None:
    """The ``TIME_HEALTH_SNAPSHOT`` heartbeat must be STRICTLY shorter than the closed-session"""
    heartbeat_ms = _mapping("time.yaml")["time_health_snapshot_heartbeat_ms"]
    closed_interval_ms = _mapping("marketfeed.yaml")["time_evaluate_closed_interval_ms"]
    assert heartbeat_ms < closed_interval_ms, (
        f"time_health_snapshot_heartbeat_ms={heartbeat_ms} must be < "
        f"time_evaluate_closed_interval_ms={closed_interval_ms}"
    )


@pytest.mark.parametrize(
    ("name", "dotted"),
    [
        ("monitor_coverage.yaml", "coverage.coverage_generation"),
        ("authority.yaml", "trading_approval_policy_generation"),
    ],
)
def test_generation_identifiers_are_all_first_generation(
    name: str, dotted: str
) -> None:
    """Proposal §4.3: "``*_generation`` 계열은 전부 **1**(첫 세대)"."""
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert cursor == 1


@pytest.mark.parametrize(
    ("name", "dotted"),
    [
        ("critical_input_policy.yaml", "policy_id"),
        ("critical_input_policy.yaml", "issuer_principal_id"),
        ("finality.yaml", "proof_recipe_id"),
    ],
)
def test_identifiers_follow_the_proposal_naming_rule(name: str, dotted: str) -> None:
    """Proposal §4.3: identifiers are names, not measurements — ``tos-paper-<what>-g<gen>``,"""
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert isinstance(cursor, str)
    assert cursor.startswith("tos-paper-"), cursor
    assert cursor.endswith("-g1"), cursor


@pytest.mark.parametrize(
    ("name", "dotted"),
    [],
)
def test_empty_lists_are_explicitly_empty_never_null(name: str, dotted: str) -> None:
    """Proposal §4.3: "아직 지배할 차원도, 기록된 승인도, 발생한 이탈·사고도 없다."""
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert cursor == []


def test_required_dimensions_is_the_whole_mandated_floor() -> None:
    """Operator 2026-09-23 "그대로 사용" — proposal §6 item 6 had left this a design call;"""
    from tos.cur import MANDATED_DIMENSION_FLOOR

    declared = _mapping("currentness.yaml")["required_dimensions"]
    assert declared == sorted(key.value for key in MANDATED_DIMENSION_FLOOR)
    assert len(declared) == 9


def test_monitor_coverage_bounds_use_the_earlier_recommended_values() -> None:
    """Operator 2026-09-23 "추천 값이 있으면 활용". Proposal §6 item 5 called these "상위"""
    bounds = _mapping("monitor_coverage.yaml")["coverage"]["bounds"]
    assert bounds["max_evidence_tip_stall_ms"] == 60_000
    assert bounds["max_inbox_unconsumed"] == 100


@pytest.mark.parametrize("key", ["source_revision"])
def test_finality_undetermined_keys_are_still_null(key: str) -> None:
    """What is STILL unfilled after the 2026-09-23 operator answers."""
    assert _mapping("finality.yaml")[key] is None


def test_finality_refuses_while_those_keys_are_undetermined() -> None:
    """The refusal key moved from ``value_date`` to ``source_revision`` when the former was"""
    with pytest.raises(FinalityConfigError, match="source_revision"):
        load_finality_config(_DEPLOY_DIR / "finality.yaml")


def _critical_input_scheme() -> Any:
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

    return get_scheme(EV_L1_PROVISIONAL_VERSION)


def _critical_input_field_keys(config_dir: Path) -> frozenset[str]:
    loaded = load_critical_input_policy(
        config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME,
        scheme=_critical_input_scheme(),
    )
    return frozenset(loaded.fields_by_key)


def test_construction_price_field_keys_match_the_deployed_critical_input_policy() -> (
    None
):
    """A-4, both branches of proposal §5.4 — whichever one the deployment lands on:"""
    construction_path = _DEPLOY_DIR / CONSTRUCTION_CONFIG_NAME
    policy_path = _DEPLOY_DIR / CRITICAL_INPUT_POLICY_CONFIG_NAME
    if not construction_path.is_file():
        assert not policy_path.is_file(), (
            "critical_input_policy.yaml is adopted but construction.yaml is not — "
            "proposal §5.4 admits only 'both' or 'neither'"
        )
        return
    assert policy_path.is_file(), (
        "construction.yaml and critical_input_policy.yaml must be adopted TOGETHER — "
        "the construction loader cannot cross-check the policy file itself"
    )
    construction = _mapping(CONSTRUCTION_CONFIG_NAME)
    declared = _critical_input_field_keys(_DEPLOY_DIR)
    assert construction["price_field_key"] in declared
    assert construction["shape_price_field_key"] in declared


_FIXTURE_SENTENCE = "부팅 증명 픽스처 — 거래 전략 아님 · 대칭은 전략 제안 경로 착지 후 · 운영자 선택 (가) 2026-09-23"

_FIXTURE_PROVENANCE = "2026-09-23-tos-paper-coordinates-and-first-boot-design.md"

_BOOTPROOF_FIXTURE_FILES: tuple[str, ...] = (
    "construction.yaml",
    "marketfeed.yaml",
    "critical_input_policy.yaml",
    "strategies/bootproof_band.strategy.yaml",
)

_UNRENDERED_PLACEHOLDERS: dict[str, Any] = {
    "construction.yaml::account": "TBD",
    "construction.yaml::instrument": "TBD",
    "marketfeed.yaml::instruments": ["TBD"],
    "marketfeed.yaml::account": "TBD",
    "marketfeed.yaml::journal_path": "TBD",
}

_FIXTURE_VALUE_PINS: dict[str, Any] = {
    "construction.yaml::account": "TBD",
    "construction.yaml::instrument": "TBD",
    "construction.yaml::action_class": "NEW_LONG",
    "construction.yaml::outbound_side": "BUY",
    "construction.yaml::instrument_class": "krx-index-futures",
    "construction.yaml::price_field_key": "close",
    "construction.yaml::shape_price_field_key": "close",
    "marketfeed.yaml::instruments": ["TBD"],
    "marketfeed.yaml::account": "TBD",
    "marketfeed.yaml::journal_path": "TBD",
    "marketfeed.yaml::instrument_class": "krx-index-futures",
    "marketfeed.yaml::direction": "LONG",
    "marketfeed.yaml::quantity_basis": "RISK",
    "marketfeed.yaml::unit": "CONTRACTS",
    "marketfeed.yaml::intake_kind": "journal",
    "marketfeed.yaml::poll_interval_ms": 400,
    "marketfeed.yaml::journal_pass_allowance_ms": 100,
    "marketfeed.yaml::time_evaluate_closed_interval_ms": 60000,
    "marketfeed.yaml::snapshot_age_bound": 20,
    "marketfeed.yaml::interval_width": 10,
    "critical_input_policy.yaml::policy_id": "tos-paper-critical-input-bootproof-g1",
    "critical_input_policy.yaml::policy_version": "1.0.0",
    "critical_input_policy.yaml::policy_generation": 1,
    "critical_input_policy.yaml::issuer_principal_id": (
        "tos-paper-critical-input-issuer-bootproof-g1"
    ),
    "critical_input_policy.yaml::environment": "paper",
    "critical_input_policy.yaml::decision_class": "entry",
    "critical_input_policy.yaml::intended_use": "entry-decision",
    "critical_input_policy.yaml::fields": [
        {
            "field_key": field_key,
            "unit": "KRW",
            "scale": "minor",
            "multiplier": "1",
            "sign": "POSITIVE",
            "max_age_ms": 600000,
        }
        for field_key in ("close", "lower_band", "upper_band")
    ],
    "strategies/bootproof_band.strategy.yaml::dsl_version": "tos-paper-bootproof-dsl-g1",
    "strategies/bootproof_band.strategy.yaml::config_binding_version": (
        "tos-paper-bootproof-cfg-g1"
    ),
    "strategies/bootproof_band.strategy.yaml::policy.rules": [
        {
            "all_of": [
                {
                    "left": {"ref": ["capsule", "resolved_values", "close"]},
                    "op": "LT",
                    "right": {"ref": ["capsule", "resolved_values", "lower_band"]},
                }
            ],
            "decision": {
                "kind": "ACTION",
                "rationale": "부팅 증명 픽스처 — close 가 lower_band 아래. 거래 근거 아님.",
                "target": {
                    "kind": "ACTION",
                    "account": "TBD",
                    "instrument": "TBD",
                    "direction": "LONG",
                    "position_effect": "OPEN",
                    "quantity_basis": "RISK",
                    "edge_or_confidence": "bootproof-fixture",
                    "rationale": "부팅 증명 픽스처 — 거래 전략 아님.",
                },
            },
        }
    ],
    "strategies/bootproof_band.strategy.yaml::policy.default.kind": "NO_ACTION",
    "strategies/bootproof_band.strategy.yaml::policy.default.rationale": (
        "부팅 증명 픽스처 — 밴드 안. 제안 없음."
    ),
}


def _fixture_leaf_refs() -> dict[str, Any]:
    found: dict[str, Any] = {}
    for name in _BOOTPROOF_FIXTURE_FILES:
        raw = yaml.safe_load((_DEPLOY_DIR / name).read_text(encoding="utf-8"))
        for path, value in _leaves(raw):
            found[f"{name}::{path}"] = value
    return found


@pytest.mark.parametrize("name", _BOOTPROOF_FIXTURE_FILES)
def test_bootproof_fixture_says_what_it_is(name: str) -> None:
    """Each fixture file must say, in its own header, that it is a boot proof and not a"""
    text = (_DEPLOY_DIR / name).read_text(encoding="utf-8")
    assert _FIXTURE_SENTENCE in text, name
    assert _FIXTURE_PROVENANCE in text, name


def test_every_bootproof_fixture_leaf_is_pinned() -> None:
    """Completeness gate — the same one the 18 approved files get. A leaf added to a fixture"""
    unaccounted = sorted(
        ref for ref in _fixture_leaf_refs() if ref not in _FIXTURE_VALUE_PINS
    )
    assert not unaccounted, f"unpinned boot-proof fixture leaves: {unaccounted}"


def test_no_bootproof_pin_names_a_leaf_that_no_longer_exists() -> None:
    present = _fixture_leaf_refs()
    stale = sorted(ref for ref in _FIXTURE_VALUE_PINS if ref not in present)
    assert not stale, f"_FIXTURE_VALUE_PINS names leaves that no longer exist: {stale}"


@pytest.mark.parametrize("ref", sorted(_FIXTURE_VALUE_PINS))
def test_bootproof_fixture_value_is_unchanged(ref: str) -> None:
    name, dotted = ref.split("::", 1)
    raw = yaml.safe_load((_DEPLOY_DIR / name).read_text(encoding="utf-8"))
    assert _resolve_dotted(raw, dotted) == _FIXTURE_VALUE_PINS[ref]


@pytest.mark.parametrize("ref", sorted(_UNRENDERED_PLACEHOLDERS))
def test_unrendered_coordinate_slot_carries_the_placeholder_its_loader_refuses(
    ref: str,
) -> None:
    """Every coordinate slot carries the SAME named-TBD token, and its loader refuses it."""
    name, dotted = ref.split("::", 1)
    raw = yaml.safe_load((_DEPLOY_DIR / name).read_text(encoding="utf-8"))
    assert _resolve_dotted(raw, dotted) == _UNRENDERED_PLACEHOLDERS[ref]


def test_unrendered_fixtures_refuse_through_their_own_loaders_naming_the_key() -> None:
    """The committed (unrendered) fixtures must REFUSE, each naming its own coordinate key."""
    with pytest.raises(ConstructionConfigError, match="account"):
        load_construction_config(_DEPLOY_DIR / CONSTRUCTION_CONFIG_NAME)

    from tos_runtime.compose._marketfeed_wiring import (
        MarketFeedConfigError,
        load_marketfeed_config,
    )

    with pytest.raises(MarketFeedConfigError, match="instruments"):
        load_marketfeed_config(_DEPLOY_DIR / "marketfeed.yaml")

    from tos_runtime.strategy.loader import StrategyLoadError, load_strategies

    def _never(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the named-TBD walk precedes parse/admit")

    with pytest.raises(StrategyLoadError, match="target.account"):
        load_strategies(_DEPLOY_DIR / "strategies", parse=_never, admit=_never)


def _rendered_marketfeed_mapping(tmp_path: Path, **overrides: Any) -> Path:
    """The COMMITTED ``marketfeed.yaml`` with only its three coordinate slots filled — what"""
    raw = _mapping("marketfeed.yaml")
    raw["instruments"] = ["101W09"]
    raw["account"] = "00000000-01"
    raw["journal_path"] = str(tmp_path / "journal.jsonl")
    raw.update(overrides)
    path = tmp_path / "marketfeed.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_the_committed_pacing_fits_the_approved_freshness_budget(
    tmp_path: Path,
) -> None:
    """The two approved files are cross-checked against EACH OTHER, by the guard that runs at"""
    from tos_runtime.compose._marketfeed_wiring import (
        _load_config_within_freshness_budget,
    )

    time_config = load_time_config(_DEPLOY_DIR / "time.yaml")
    config = _load_config_within_freshness_budget(
        _rendered_marketfeed_mapping(tmp_path), time_config
    )
    assert config.poll_interval_ms == 400
    assert config.journal_pass_allowance_ms == 100


def test_the_superseded_poll_interval_would_be_refused_at_boot(tmp_path: Path) -> None:
    """The regression pin with a named input: restore ONLY the superseded"""
    from tos_runtime.compose._marketfeed_wiring import (
        MarketFeedConfigError,
        _load_config_within_freshness_budget,
    )

    time_config = load_time_config(_DEPLOY_DIR / "time.yaml")
    path = _rendered_marketfeed_mapping(tmp_path, poll_interval_ms=1000)

    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _load_config_within_freshness_budget(path, time_config)


def test_critical_input_policy_loads_as_committed() -> None:
    """The one fixture with no coordinate slot — it carries neither account nor instrument, so"""
    field_keys = _critical_input_field_keys(_DEPLOY_DIR)
    assert field_keys == frozenset({"close", "lower_band", "upper_band"})


def test_bootproof_strategy_quantity_basis_equals_the_ocp_admitted_set() -> None:
    """OCP sizing proposal §4 ②'s own condition, now checkable: the deployed strategy file's"""
    strategy = _mapping("strategies/bootproof_band.strategy.yaml")
    basis = strategy["policy"]["rules"][0]["decision"]["target"]["quantity_basis"]
    ocp = _mapping("order_construction_policy.yaml")
    admitted = ocp["_runtime"]["construction"]["sizing"]["admitted_quantity_bases"]
    assert admitted == [basis]


def test_bootproof_direction_is_consistent_across_every_file_that_carries_one() -> None:
    """The committed direction is LONG in every slot that carries one. The SHORT variant is a"""
    ocp = _mapping("order_construction_policy.yaml")
    axes = ocp["_runtime"]["construction"]["axes"]
    direction_axes = [entry for entry in axes if entry["axis"] == "DIRECTION"]
    assert len(direction_axes) == 1
    assert direction_axes[0]["value"] == "LONG"

    construction = _mapping(CONSTRUCTION_CONFIG_NAME)
    shape = ocp["_runtime"]["construction"]["action_class_shape"]
    action_class = construction["action_class"]
    assert action_class == "NEW_LONG"
    assert shape[action_class]["LONG"]["side"] == construction["outbound_side"]

    strategy = _mapping("strategies/bootproof_band.strategy.yaml")
    target = strategy["policy"]["rules"][0]["decision"]["target"]
    assert target["direction"] == "LONG"
    assert target["position_effect"] == shape[action_class]["LONG"]["position_effect"]
    assert _mapping("marketfeed.yaml")["direction"] == "LONG"


def test_ocp_scope_still_authorizes_both_directions() -> None:
    """⚠ The non-negotiable long/short symmetry rule, as a mechanical pin: committing ONE"""
    ocp = _mapping("order_construction_policy.yaml")
    assert set(ocp["scope"]["action_classes"]) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}
    shape = ocp["_runtime"]["construction"]["action_class_shape"]
    assert set(shape) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}
    assert set(shape["CLOSE"]) == {"LONG", "SHORT"}


def test_envelope_and_profile_govern_the_are_dimension() -> None:
    """The ARE policy's own ceiling map must cover every dimension it governs."""
    are = _mapping("aggregate_risk_policy.yaml")
    dimension_ids = set(are["_runtime"]["dimension_ids"])
    ceilinged = set(are["_runtime"]["envelope_max"])

    assert dimension_ids <= ceilinged, (
        "every ARE-governed dimension needs a real declared ceiling "
        f"(ARE {sorted(dimension_ids)} vs envelope_max {sorted(ceilinged)})"
    )
    assert ceilinged <= dimension_ids, "a ceiling for an ungoverned dimension is dead"


def test_envelope_maximum_admits_the_deployments_own_effective_limit() -> None:
    """``_runtime.envelope_max`` must actually admit what this deployment sizes to."""
    from decimal import Decimal

    are = _mapping("aggregate_risk_policy.yaml")
    dimension_id = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
    effective_limit = Decimal(str(are["_runtime"]["effective_limits"][dimension_id]))
    ceiling = Decimal(str(are["_runtime"]["envelope_max"][dimension_id]))

    assert ceiling >= effective_limit
    assert ceiling == Decimal(
        1
    ), "the value measured off safety_envelope.yaml before plan S2-a deleted it"


def test_the_requirement_that_asked_for_this_value_is_still_in_the_are_policy() -> None:
    """The envelope value is only justified while the ARE keeps asking for it."""
    requirements = _mapping("aggregate_risk_policy.yaml")["compatibility_requirements"]
    assert any(
        "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL" in line and "envelope_max" in line
        for line in requirements
    ), requirements
