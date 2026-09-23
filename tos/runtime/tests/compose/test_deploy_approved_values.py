"""Compose e2e pins for the REAL deployed values under ``config/tos_runtime/paper/``
adopted by W-A / A-2..A-5 (``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md``
§4 W-A; value table ``docs/plans/2026-09-18-tos-config-value-proposal.md``, adopted by the
operator 2026-09-18 and confirmed as-proposed 2026-09-23).

Sibling of :mod:`.test_deploy_config` (which pins the deployed ``calendar.yaml``),
:mod:`.test_deploy_policies` and :mod:`.test_deploy_risk_policies` — same discipline, wider
surface: **every newly approved file is loaded by the loader that actually reads it at boot**,
not by a stand-in shaped like it, and every adopted value a reader would call load-bearing is
pinned so a silent edit cannot pass as "still the approved value".

Three kinds of pin live here, and the difference matters:

1. **Loads** — the real file, through its real loader, from the repo path an operator deploys.
2. **Named-TBD mutation goes RED** — the same file with exactly ONE approved leaf flipped back
   to ``null`` must refuse with that loader's own typed error (mutation lens: delete the
   fail-closed branch and this turns green).
3. **Still-undetermined leaves refuse, by name** — the proposal's §6 "확인 불가 · 미확정" list
   was deliberately NOT filled (``currentness.yaml::required_dimensions``,
   ``finality.yaml::value_date``/``source_revision``/``proof_recipe_id``,
   ``monitor_coverage.yaml::bounds``, ``safety_activation.yaml::members``). Each one's refusal
   is pinned WITH THE KEY NAME, so filling it later is a deliberate act that must update this
   test — never a silent change of what the deployment claims.

Hermetic (``tos/runtime/tests/conftest.py`` D1.4): the repo files are only ever **read**; every
write goes into ``tmp_path``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
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
from tos_runtime.compose._pending_dimensions import (
    PendingDimensionConfigError,
    load_pending_currentness_dimensions,
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
from tos_runtime.safety.deviation import DeviationConfigError, DeviationService
from tos_runtime.safety.incident import IncidentConfigError, IncidentService
from tos_runtime.safety.monitoring import MonitoringConfigError, MonitoringService
from tos_runtime.safety.profile import SafetyProfileConfigError, SafetyProfileService
from tos_runtime.time.config import TimeConfigError, load_time_config
from tos_runtime.venue.activation import (
    ActivationMembersConfigError,
    load_activation_members,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

# parents[0]=compose, [1]=tests, [2]=runtime, [3]=tos, [4]=repo root — the same
# depth-from-file arithmetic ``test_deploy_config.py`` already uses in this directory.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEPLOY_DIR = _REPO_ROOT / "config" / "tos_runtime" / "paper"

#: This deployment's own environment label — the two loaders that template
#: ``{environment_label}`` need one, and ``coordinator_preconditions.yaml``'s adopted posture
#: is written for a non-live label.
_ENVIRONMENT_LABEL = "non-live-test"

#: The provenance line every file adopted by this wave must carry (``config/tos_runtime/
#: README.md``'s own rule: "never add a value here without that citation").
_PROVENANCE = "docs/plans/2026-09-18-tos-config-value-proposal.md"
_APPROVAL_DATES = ("2026-09-18", "2026-09-23")

#: The proposal §0 sentence every adopted file must carry verbatim — a value table that boots
#: is not a safety posture, and a reader of the file must see that where the value is, not
#: only in the plan.
_NOT_A_SAFETY_POSTURE = "첫 부팅 프로파일이지 운영 안전 태세가 아니다"

#: Files this wave adopted (A-2). ``strategies/`` and ``construction.yaml`` are deliberately
#: NOT here — see ``test_construction_yaml_is_not_adopted_and_run_refuses`` and the plan's
#: §7.8 landing record for why.
_ADOPTED_BY_THIS_WAVE: tuple[str, ...] = (
    "time.yaml",
    "authority.yaml",
    "release.yaml",
    "currentness.yaml",
    "currentness_dimensions.yaml",
    "risk_attestations.yaml",
    "egress_coordinates.yaml",
    "broker_scopes.yaml",
    "engine.yaml",
    "engine_driver.yaml",
    "coordinator_preconditions.yaml",
    "finality.yaml",
    "safety_envelope.yaml",
    "safety_profile.yaml",
    "safety_activation.yaml",
    "safety_deviations.yaml",
    "safety_incidents.yaml",
    "monitor_coverage.yaml",
)


# ============================================================================
# Helpers
# ============================================================================


def _read(name: str) -> str:
    return (_DEPLOY_DIR / name).read_text(encoding="utf-8")


def _mapping(name: str) -> dict[str, Any]:
    raw = yaml.safe_load(_read(name))
    assert isinstance(raw, dict), f"{name} did not load as a mapping"
    return raw


def _deploy_copy(tmp_path: Path, *names: str) -> Path:
    """Copy the named REAL deploy files into ``tmp_path`` so a test may mutate them.

    Only the repo files are read; every write lands under ``tmp_path`` (D1.4 write guard).
    """
    dest = tmp_path / "deploy"
    dest.mkdir(exist_ok=True)
    for name in names:
        (dest / name).write_text(_read(name), encoding="utf-8")
    return dest


def _set_null(path: Path, dotted: str) -> None:
    """Flip exactly one leaf of ``path`` back to ``null`` (named-TBD), asserting it was
    filled first — a mutation that silently no-ops would prove nothing."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cursor: Any = raw
    keys = dotted.split(".")
    for key in keys[:-1]:
        cursor = cursor[key]
    assert cursor[keys[-1]] is not None, f"{path.name}:{dotted} was already null"
    cursor[keys[-1]] = None
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _no_op_observer() -> Any:
    raise AssertionError("observer must not be reached during config load")


def _monitoring_service(config_dir: Path) -> MonitoringService:
    """Construct the service purely to exercise its config load — every injected observer
    raises, so a test that accidentally drove an observation would fail loudly rather than
    silently measure nothing."""
    return MonitoringService(
        config_path=config_dir / "monitor_coverage.yaml",
        evidence_tip_observer=lambda: _no_op_observer(),
        time_health_observer=lambda: _no_op_observer(),
        inbox_unconsumed_observer=lambda: _no_op_observer(),
        monotonic_ns=lambda: _no_op_observer(),
        evidence_recorder=lambda *_args, **_kwargs: _no_op_observer(),
    )


def _safety_mesh_documents(config_dir: Path) -> SafetyProfileService:
    return SafetyProfileService(
        envelope_path=config_dir / "safety_envelope.yaml",
        profile_path=config_dir / "safety_profile.yaml",
        activation_path=config_dir / "safety_activation.yaml",
    )


# ============================================================================
# The table — one row per file that LOADS today
# ============================================================================


@dataclass(frozen=True)
class _LoadablePin:
    """One adopted file that loads cleanly, plus the one leaf a mutation nulls."""

    #: Human label / pytest id.
    label: str
    #: Every deploy file the loader needs present in the config dir.
    files: tuple[str, ...]
    #: Called with the config DIRECTORY — a multi-document loader needs more than one path.
    load: Callable[[Path], object]
    #: The loader's own typed refusal.
    error: type[Exception]
    #: ``<file>::<dotted.key>`` — the leaf the named-TBD mutation flips to null.
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
        label="currentness_dimensions.yaml",
        files=("currentness_dimensions.yaml",),
        load=lambda d: load_pending_currentness_dimensions(
            d / "currentness_dimensions.yaml"
        ),
        error=PendingDimensionConfigError,
        mutate=("currentness_dimensions.yaml", "CONTEXT.bound_digest"),
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
        mutate=("egress_coordinates.yaml", "endpoint.value"),
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
        label="safety_envelope+profile+activation",
        files=("safety_envelope.yaml", "safety_profile.yaml", "safety_activation.yaml"),
        load=_safety_mesh_documents,
        error=SafetyProfileConfigError,
        mutate=("safety_activation.yaml", "not_expired"),
    ),
    _LoadablePin(
        label="safety_deviations.yaml",
        files=("safety_deviations.yaml",),
        load=lambda d: DeviationService(deviations_path=d / "safety_deviations.yaml"),
        error=DeviationConfigError,
        mutate=("safety_deviations.yaml", "deviations.active_set.is_complete"),
    ),
    _LoadablePin(
        label="safety_incidents.yaml",
        files=("safety_incidents.yaml",),
        load=lambda d: IncidentService(config_path=d / "safety_incidents.yaml"),
        error=IncidentConfigError,
        mutate=("safety_incidents.yaml", "incidents.active_set.is_current"),
    ),
)


def _loadable_ids() -> Iterator[str]:
    for pin in _LOADABLE:
        yield pin.label


@pytest.mark.parametrize("pin", _LOADABLE, ids=list(_loadable_ids()))
def test_real_deploy_file_loads_through_its_real_loader(pin: _LoadablePin) -> None:
    """A-2: the file an operator actually deploys is read by the loader that reads it at
    boot — never a fixture shaped like it."""
    pin.load(_DEPLOY_DIR)


@pytest.mark.parametrize("pin", _LOADABLE, ids=list(_loadable_ids()))
def test_named_tbd_mutation_of_one_approved_value_refuses(
    pin: _LoadablePin, tmp_path: Path
) -> None:
    """Mutation lens: the SAME real values with exactly one approved leaf flipped back to
    ``null`` (named-TBD) must refuse with that loader's own typed error, NAMING the leaf.
    Deleting the loader's fail-closed branch turns this green.

    The message check is what keeps the pin non-vacuous: without it, a refusal for some
    unrelated reason (a malformed copy, a different missing file) would pass as "the guard
    fired"."""
    config_dir = _deploy_copy(tmp_path, *pin.files)
    file_name, dotted = pin.mutate
    leaf = dotted.split(".")[-1]
    _set_null(config_dir / file_name, dotted)
    with pytest.raises(pin.error, match=leaf):
        pin.load(config_dir)


# ============================================================================
# Provenance — README.md's own rule
# ============================================================================


@pytest.mark.parametrize("name", _ADOPTED_BY_THIS_WAVE)
def test_adopted_file_cites_its_approval_provenance(name: str) -> None:
    """``config/tos_runtime/README.md``: "never add a value here without that citation".
    An un-cited value is indistinguishable from an unapproved one."""
    text = _read(name)
    assert _PROVENANCE in text, f"{name} does not cite the value proposal"
    for date in _APPROVAL_DATES:
        assert date in text, f"{name} does not carry the {date} approval date"


@pytest.mark.parametrize("name", _ADOPTED_BY_THIS_WAVE)
def test_adopted_file_says_it_is_not_a_safety_posture(name: str) -> None:
    """Proposal §0, binding: "채택되는 각 파일에 이 문장을 주석으로 박는다" — a reader
    holding the file must see that this is a first-boot profile, not an operational safety
    posture, without having to find the plan."""
    assert _NOT_A_SAFETY_POSTURE in _read(
        name
    ), f"{name} omits the proposal §0 sentence"


# ============================================================================
# The ⚠ values — the proposal §4.1 rows an operator was asked to look at
# ============================================================================


def test_live_authorization_state_is_the_only_supported_posture() -> None:
    """Proposal §1 [S] — the single value ``compose/_preconditions.py``'s
    ``_SUPPORTED_LIVE_AUTHORIZATION_STATES`` accepts, and the technical enforcement point of
    CLAUDE.md's non-negotiable "real-money futures order paths are permanently
    policy-blocked"."""
    assert (
        _mapping("coordinator_preconditions.yaml")["live_authorization_state"]
        == "NOT_AUTHORIZED"
    )


def test_nonlive_broker_consuming_is_not_admitted() -> None:
    """Proposal §4.1 ⚠ — the narrower posture. Turning this on is a separate operator
    approval, taken together with a broker-reaching ``active_scope``."""
    admitted = _mapping("coordinator_preconditions.yaml")["nonlive_broker_consuming"][
        "admitted"
    ]
    assert admitted is False


def test_active_scope_is_the_only_non_broker_reaching_scope() -> None:
    """Proposal §4.1 ⚠ — ``SYNTHETIC_FUTURES_ORDER`` is the one scope in the table that
    reaches no broker at all. ``REAL_ORDER`` is permanently policy-blocked (CLAUDE.md);
    ``MOCK_STOCK_ORDER``/``REAL_READ`` make external calls, which the A-5 boot target
    (local hermetic only, operator decision 2026-09-23) excludes."""
    assert _mapping("broker_scopes.yaml")["active_scope"] == "SYNTHETIC_FUTURES_ORDER"


def test_broker_scopes_body_is_the_shipped_example_plus_one_line() -> None:
    """The deploy file was COPIED from ``broker_scopes.example.yaml``, never hand-retyped:
    the only body line that differs is the one named-TBD field the proposal adopted. A
    hand-edited scope table would drift from the example the compose e2e suite exercises.
    """
    example_lines = (
        (_REPO_ROOT / "tos" / "runtime" / "config" / "broker_scopes.example.yaml")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    deploy_lines = _read("broker_scopes.yaml").splitlines()
    # The deploy file is the example verbatim with a provenance header prepended, so the
    # example's own line count is the tail of the deploy file.
    assert len(deploy_lines) > len(example_lines)
    body = deploy_lines[-len(example_lines) :]
    differing = [(a, b) for a, b in zip(example_lines, body, strict=True) if a != b]
    assert len(differing) == 1, f"expected exactly one changed line, got {differing}"
    example_line, deploy_line = differing[0]
    assert example_line == "active_scope: null"
    assert deploy_line.startswith("active_scope: SYNTHETIC_FUTURES_ORDER")


def test_release_admission_is_admit_paired_with_no_restriction() -> None:
    """Proposal §4.1 ⚠ — ``ADMIT`` (never the non-existent ``ADMITTED`` the proposal's own
    draft carried) must be paired with ``restriction_present: false``; and the pairing only
    admits anything while the restriction snapshot itself resolves (SCI-INV-014)."""
    release = _mapping("release.yaml")
    assert release["admission_result"] == "ADMIT"
    assert release["restriction_present"] is False
    assert release["restriction_state_resolved"] is True


def test_all_six_risk_attestations_are_operator_asserted() -> None:
    """Proposal §4.1 ⚠ — six step 6/7 admission witnesses with NO Phase 2 producer. These
    are operator attestations, not measurements: three of the six are properties the kernel
    docstrings themselves say Phase 2 cannot decide."""
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


# ============================================================================
# Cross-file consistency the loaders cannot see on their own
# ============================================================================


def test_time_trading_calendar_version_matches_the_deployed_calendar() -> None:
    """``calendar/owner.py:170-179`` refuses to boot (``SessionCalendarMismatch``) when the
    two versions are both known and disagree — the ONE cross-file equality in this set that
    the runtime itself enforces."""
    assert (
        _mapping("time.yaml")["trading_calendar_version"]
        == _mapping("calendar.yaml")["calendar_version"]
    )


def test_profile_targets_the_deployed_envelope_generation() -> None:
    """``RuntimeSafetyProfile`` must pin the exact envelope generation it operates under."""
    envelope = _mapping("safety_envelope.yaml")["envelope"]
    profile = _mapping("safety_profile.yaml")["profile"]
    assert profile["target_envelope_id"] == envelope["envelope_id"]
    assert profile["target_envelope_generation"] == envelope["envelope_generation"]


def test_activation_pins_the_deployed_profile_generation() -> None:
    activation = _mapping("safety_activation.yaml")["activation"]
    profile = _mapping("safety_profile.yaml")["profile"]
    assert activation["profile_generation"] == profile["profile_generation"]


def test_time_safety_profile_version_names_the_deployed_profile() -> None:
    """``time.yaml``'s ``safety_profile_version`` is recorded on every issued
    ``TimeHealthSnapshot``. Nothing in the runtime cross-checks it today (measured: compose
    passes no ``expected_safety_profile_version``), so this pin is what keeps the two from
    drifting into naming different generations."""
    assert (
        _mapping("time.yaml")["safety_profile_version"]
        == _mapping("safety_profile.yaml")["profile"]["profile_id"]
    )


@pytest.mark.parametrize(
    ("name", "dotted"),
    [
        ("safety_envelope.yaml", "envelope.envelope_generation"),
        ("safety_profile.yaml", "profile.profile_generation"),
        ("safety_deviations.yaml", "deviations.active_set.active_set_generation"),
        ("safety_incidents.yaml", "incidents.active_set.active_set_generation"),
        ("monitor_coverage.yaml", "coverage.manifest.coverage_generation"),
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
        ("safety_envelope.yaml", "envelope.envelope_id"),
        ("safety_profile.yaml", "profile.profile_id"),
        ("safety_activation.yaml", "activation.activation_id"),
        ("safety_deviations.yaml", "deviations.active_set.active_set_id"),
        ("safety_incidents.yaml", "incidents.active_set.active_set_id"),
        ("monitor_coverage.yaml", "coverage.manifest.coverage_manifest_id"),
    ],
)
def test_identifiers_follow_the_proposal_naming_rule(name: str, dotted: str) -> None:
    """Proposal §4.3: identifiers are names, not measurements — ``tos-paper-<what>-g<gen>``,
    used consistently."""
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert isinstance(cursor, str)
    assert cursor.startswith("tos-paper-"), cursor
    assert cursor.endswith("-g1"), cursor


@pytest.mark.parametrize(
    ("name", "dotted"),
    [
        ("safety_envelope.yaml", "envelope.governed_dimensions"),
        ("safety_envelope.yaml", "envelope.permitted_scope"),
        ("safety_envelope.yaml", "envelope.prohibited_fallbacks"),
        ("safety_profile.yaml", "profile.governed_dimensions"),
        ("safety_activation.yaml", "activation.approval_ids"),
        ("safety_activation.yaml", "activation.compatibility_attestation_refs"),
        ("safety_deviations.yaml", "deviations.applicable_decision_ids"),
        ("safety_deviations.yaml", "deviations.members"),
        ("safety_incidents.yaml", "incidents.applicable_incident_ids"),
        ("safety_incidents.yaml", "incidents.members"),
    ],
)
def test_empty_lists_are_explicitly_empty_never_null(name: str, dotted: str) -> None:
    """Proposal §4.3: "아직 지배할 차원도, 기록된 승인도, 발생한 이탈·사고도 없다.
    **빈 것이 사실이다.**" An explicit ``[]`` is a positive statement; ``null`` is a
    refusal. Substituting one for the other claims a different fact."""
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert cursor == []


# ============================================================================
# Still-undetermined leaves — the proposal §6 list, pinned BY KEY NAME
# ============================================================================


def test_currentness_required_dimensions_is_still_undetermined() -> None:
    """Proposal §6 item 6: copying the 21-member ``MANDATED_DIMENSION_FLOOR`` verbatim makes
    ``policy_covers_mandated_dimensions`` a tautology (a past bug). A meaningful,
    independently editable declaration is a DESIGN decision that has not been taken, so the
    leaf stays ``null`` and the loader refuses — by design, and named here so filling it
    later is deliberate."""
    assert _mapping("currentness.yaml")["required_dimensions"] is None
    with pytest.raises(CurrentnessConfigError, match="required_dimensions"):
        load_currentness_config(_DEPLOY_DIR / "currentness.yaml")


def test_currentness_b_capability_claim_to_send_is_the_transcribed_bound() -> None:
    """Proposal §2.3 [A] — VER-002 carries 500 for this key under
    ``applicable_scope: non-live-test``, which is exactly this deployment, but that entry is
    ``RECHECK``/``MEASURE``: a provisional value awaiting measurement, not an approved
    measurement."""
    assert _mapping("currentness.yaml")["B_capability_claim_to_send"] == 500


@pytest.mark.parametrize("key", ["value_date", "source_revision", "proof_recipe_id"])
def test_finality_undetermined_keys_are_still_null(key: str) -> None:
    """Proposal §6 items 1-2. Re-measured in A-2: ADR-002-030 §29 is titled "Open
    Implementation Questions" and its Q3 asks WHICH finality recipes apply — it names no
    approved identifier at all, so ``proof_recipe_id`` is not merely unfound, it does not
    yet exist. Inventing one would assert "proved under an approved recipe"."""
    assert _mapping("finality.yaml")[key] is None


def test_finality_refuses_while_those_keys_are_undetermined() -> None:
    with pytest.raises(FinalityConfigError, match="value_date"):
        load_finality_config(_DEPLOY_DIR / "finality.yaml")


def test_finality_currency_and_release_proof_wait_are_adopted() -> None:
    """Proposal §4.2 — KRW (KRX, KST/원화 native repo) and 60000 ms aligned with VER-002's
    approved ``MAX_live_authorization_validity_ms``. The wait bound only RECORDS an evidence
    row (incident candidate); it changes no state, so over-sizing it is the safe direction.
    """
    finality = _mapping("finality.yaml")
    assert finality["currency"] == "KRW"
    assert finality["release_proof_wait_ms"] == 60_000


@pytest.mark.parametrize(
    "bound",
    ["max_evidence_tip_stall_ms", "healthy_time_states", "max_inbox_unconsumed"],
)
def test_monitor_coverage_bounds_are_still_undetermined(bound: str) -> None:
    """Proposal §6 item 5: "상위 원천 미확인". These three are the monitoring thresholds —
    wrong values either blind the monitor or cry wolf. No VER-002 key names them and no
    baseline measurement exists, so they stay ``null``."""
    assert _mapping("monitor_coverage.yaml")["coverage"]["bounds"][bound] is None


def test_monitor_coverage_refuses_while_its_bounds_are_undetermined(
    tmp_path: Path,
) -> None:
    config_dir = _deploy_copy(tmp_path, "monitor_coverage.yaml")
    with pytest.raises(MonitoringConfigError):
        _monitoring_service(config_dir)


def test_activation_members_is_still_undetermined_and_refuses() -> None:
    """Proposal §3 [D] — ``members`` is DERIVED from
    ``print-policy-digests --config-dir <dir>``, never hand-written. A-3 (2026-09-23) ran
    that command and it REFUSED: ``venue_constraint_policy.yaml``'s ``scope.accounts`` is
    still the operator-fill ``"TBD"`` the 2026-09-16 adoption deliberately left (that file's
    own header: "the paper account number (never committed here)"), and the value proposal's
    scope was "the 19 files not yet in ``config/tos_runtime/paper/`` + construction.yaml",
    so it supplies no value for it.

    ``members`` therefore stays ``null``. Substituting ``[]`` would claim a different fact —
    "nothing is activated" — which the example's own comment forbids without an operator
    decision."""
    assert _mapping("safety_activation.yaml")["members"] is None
    with pytest.raises(ActivationMembersConfigError, match="members"):
        load_activation_members(_DEPLOY_DIR / "safety_activation.yaml")


def test_activation_derived_digests_stay_null_because_no_derivation_exists() -> None:
    """Proposal §3 row 3 / §6 item 3: the derivation procedure for
    ``envelope_digest``/``profile_digest``/``bundle_digest`` was UNCONFIRMED. A-3 measured
    it: ``print-policy-digests`` prints only the five governed POLICY documents'
    id/generation/digest, and no other subcommand computes an envelope/profile/bundle
    digest. The kernel record types all three ``X | None``, so ``null`` loads — this is a
    missing derivation, not a missing refusal."""
    activation = _mapping("safety_activation.yaml")["activation"]
    for key in ("envelope_digest", "profile_digest", "bundle_digest"):
        assert activation[key] is None
    _safety_mesh_documents(_DEPLOY_DIR)


# ============================================================================
# A-4 — the construction/critical-input correlation
# ============================================================================


def _critical_input_field_keys(config_dir: Path) -> frozenset[str]:
    loaded = load_critical_input_policy(
        config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME,
        scheme=_critical_input_scheme(),
    )
    fields: Mapping[str, Any] | Any = loaded.fields
    return frozenset(str(key) for key in fields)


def _critical_input_scheme() -> Any:
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

    return get_scheme(EV_L1_PROVISIONAL_VERSION)


def test_construction_price_field_keys_match_the_deployed_critical_input_policy() -> (
    None
):
    """A-4, both branches of proposal §5.4 — whichever one the deployment lands on:

    * If BOTH files are deployed, ``price_field_key``/``shape_price_field_key`` MUST name
      fields the deployed ``critical_input_policy.yaml`` actually declares. The construction
      loader cannot see that file (its own module docstring says so), so this is the only
      place the correlation is checked.
    * If NEITHER is deployed, that is the other branch — ``run`` refuses before compose on
      the missing ``construction.yaml`` (pinned below), so no construction ever prices.

    A half-adopted pair (one without the other) is the failure this refuses outright.
    """
    construction_path = _DEPLOY_DIR / CONSTRUCTION_CONFIG_NAME
    policy_path = _DEPLOY_DIR / CRITICAL_INPUT_POLICY_CONFIG_NAME
    if not construction_path.is_file():
        # Branch 2, asserted rather than skipped: a skip would make this pin inert exactly
        # when it matters. The pair must be absent TOGETHER — a lone
        # critical_input_policy.yaml would leave `run` refusing on the missing
        # construction.yaml while the deployment looked half-wired.
        assert not policy_path.is_file(), (
            "critical_input_policy.yaml is adopted but construction.yaml is not — "
            "proposal §5.4 admits only 'both' or 'neither'"
        )
        return
    # Branch 1: both adopted — the correlation the construction loader cannot check itself.
    assert policy_path.is_file(), (
        "construction.yaml and critical_input_policy.yaml must be adopted TOGETHER — "
        "the construction loader cannot cross-check the policy file itself"
    )
    construction = load_construction_config(construction_path)
    declared = _critical_input_field_keys(_DEPLOY_DIR)
    assert construction.price_field_key in declared
    assert construction.shape_price_field_key in declared


def test_construction_yaml_is_not_adopted_and_run_refuses_on_it() -> None:
    """A-5's measured refusal, pinned. ``construction.yaml`` has no approved instance: the
    value proposal names it in scope (§0) but tabulates no value for any of its seven leaves,
    and its ``account``/``instrument`` must equal the venue/OCP policies' ``scope.accounts``/
    ``scope.instruments`` — which those files' own headers mark operator-fill and "never
    committed here". Inventing them would put a fabricated account coordinate into a
    committed deployment file.

    When an operator adopts it, this test goes RED and must be replaced by the correlation
    pin above — that is the point."""
    assert not (_DEPLOY_DIR / CONSTRUCTION_CONFIG_NAME).is_file()
    with pytest.raises(ConstructionConfigError, match="not found"):
        load_construction_config(_DEPLOY_DIR / CONSTRUCTION_CONFIG_NAME)
