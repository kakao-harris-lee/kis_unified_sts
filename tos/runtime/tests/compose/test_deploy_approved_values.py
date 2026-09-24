"""Compose e2e pins for the REAL deployed values under ``config/tos_runtime/paper/``
adopted by W-A / A-2..A-5 (``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md``
§4 W-A; value table ``docs/plans/2026-09-18-tos-config-value-proposal.md``, adopted by the
operator 2026-09-18 and confirmed as-proposed 2026-09-23).

Sibling of :mod:`.test_deploy_config` (which pins the deployed ``calendar.yaml``),
:mod:`.test_deploy_policies` and :mod:`.test_deploy_risk_policies` — same discipline, wider
surface: **every newly approved file is loaded by the loader that actually reads it at boot**,
not by a stand-in shaped like it.

**Coverage claim, stated exactly (review-794 HIGH-2 fixed this sentence).** The first cut of
this module claimed "every adopted value a reader would call load-bearing is pinned". It was
not true: the pins were all of the shape "null it out and the loader refuses", which leaves the
**"approved value silently becomes a DIFFERENT unapproved value"** path wide open — a reviewer
demonstrated 17 such edits (``MAX_time_source_precision_ms`` 50 → 5000, ``tz_db_version``
``2026c`` → ``1999a``, ``endpoint.value`` → a real KIS production URL, …) that left the whole
suite GREEN. That is the project-memory failure shape "가드가 자기가 막는다고 말한 것을
허용한다", and its failure mode is silence.

What is true now, mechanically:

* **Every leaf of all 18 adopted files is either value-pinned in :data:`_VALUE_PINS` or listed
  in :data:`_UNPINNED_BY_DESIGN` with a one-line reason.**
  :func:`test_every_adopted_leaf_is_pinned_or_explicitly_unpinned` enumerates the files and
  fails on a leaf in neither set, so a leaf added later cannot go silently unpinned — and
  :func:`test_no_pin_names_a_leaf_that_no_longer_exists` fails on the reverse drift.
* :func:`test_approved_value_is_unchanged` then compares each pinned leaf to its approved
  value, and :func:`test_a_value_pin_actually_fires` proves the comparison is live by mutating
  real values in a scratch copy (including the ⚠ ``replay_window_events`` case review-794
  HIGH-1 caught: ``1000000`` → ``1``, still a positive int, previously GREEN).

Three further kinds of pin live here:

1. **Loads** — the real file, through its real loader, from the repo path an operator deploys.
2. **Named-TBD mutation goes RED** — the same file with exactly ONE approved leaf flipped back
   to ``null`` must refuse with that loader's own typed error, naming the leaf.
3. **Still-undetermined leaves refuse, by name** — the proposal's §6 "확인 불가 · 미확정" list
   that survived the 2026-09-23 operator answers (``finality.yaml::value_date`` /
   ``source_revision`` / ``proof_recipe_id``, ``safety_activation.yaml::members``). Each one's
   refusal is pinned WITH THE KEY NAME, so filling it later is a deliberate act.

**Mutation methodology — text substitution, never a ``yaml.safe_dump`` round-trip.** A round
trip drops every header comment, which makes the *provenance* tests fire and turns the suite
RED for a reason that has nothing to do with the mutated value. review-794 hit exactly that and
called the resulting "all RED" vacuous. :func:`_text_set_null` / :func:`_text_set_value` edit
the one line and leave the file otherwise byte-identical.

Hermetic (``tos/runtime/tests/conftest.py`` D1.4): the repo files are only ever **read**; every
write goes into ``tmp_path``.
"""

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

from ._loader_probe import format_table, refusing_labels, run_probes

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
#: NOT here — see ``test_construction_yaml_is_not_adopted_and_run_refuses_on_it`` and the
#: plan's §7.8 landing record for why.
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
# The value-pin table — one entry per leaf of the 18 adopted files
# ============================================================================
#
# Key: ``"<file>::<dotted.leaf.path>"``. A "leaf" is any node that is not a mapping, so a LIST
# is one leaf pinned as a whole (``required_dimensions``, ``healthy_time_states``,
# ``capsule_terminus_fields.value``, every ``[]``) — pinning a list wholesale is what makes
# "someone quietly dropped one of the 21 mandated dimensions" a RED.
#
# These are the values review-794 traced back to the proposal row by row ("값 추적 — 제안표
# 대조 전건 일치"); this table is the mechanical guard that they stay those values.
_VALUE_PINS: dict[str, Any] = {
    # --- time.yaml -------------------------------------------------------
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
    "time.yaml::tz_db_version": "2026c",
    "time.yaml::trading_calendar_version": "krx-2026.09",
    "time.yaml::verification_profile_version": "VERIFICATION-PROFILE-002-v2.1",
    "time.yaml::safety_profile_version": "tos-paper-profile-g1",
    # --- authority.yaml --------------------------------------------------
    "authority.yaml::containment_bound_ms": 1000,
    "authority.yaml::trading_approval_policy_generation": 1,
    # --- release.yaml ----------------------------------------------------
    "release.yaml::expected_code_digest": "8bc76e443ca844620b99e0d7766e1b6ca55ae48518dc120a84ce7b3dbbc478d9",
    "release.yaml::expected_dependency_set_digest": "20559763a1132fc75f71f3d83e99512f4b0d9cdde9e0df61b54b9d2459f98d8b",
    "release.yaml::admission_result": "ADMIT",
    "release.yaml::restriction_state_resolved": True,
    "release.yaml::restriction_present": False,
    "release.yaml::restriction.restriction_id": None,
    "release.yaml::restriction.restriction_generation": None,
    "release.yaml::restriction.trigger_class": None,
    # --- currentness.yaml ------------------------------------------------
    "currentness.yaml::B_capability_claim_to_send": 500,
    "currentness.yaml::required_dimensions": [
        "ACTION_FLOW",
        "AGGREGATE_RISK",
        "COMMIT_LOG",
        "CONSTRAINT",
        "CONSTRUCTION",
        "CONTEXT",
        "CRITICAL_INPUT",
        "CURRENTNESS_POLICY",
        "DECISION_PROOF_INTENT",
        "DEVIATION",
        "EGRESS_IDENTITY",
        "ENVIRONMENT_SCOPE",
        "INCIDENT",
        "MONITORING",
        "POST_TRADE",
        "RECOVERY",
        "RELEASE",
        "SAFETY_AUTHORITY",
        "SAFETY_ENVELOPE_PROFILE",
        "TRADING_APPROVAL",
        "TRUSTWORTHY_TIME",
    ],
    # --- currentness_dimensions.yaml -------------------------------------
    "currentness_dimensions.yaml::CONTEXT.bound_generation": 1,
    "currentness_dimensions.yaml::CONTEXT.bound_digest": "tos-paper-context-bound-g1",
    "currentness_dimensions.yaml::CONTEXT.restrictive_floor": 0,
    "currentness_dimensions.yaml::CONTEXT.positively_established": True,
    "currentness_dimensions.yaml::CRITICAL_INPUT.bound_generation": 1,
    "currentness_dimensions.yaml::CRITICAL_INPUT.bound_digest": "tos-paper-critical-input-bound-g1",
    "currentness_dimensions.yaml::CRITICAL_INPUT.restrictive_floor": 0,
    "currentness_dimensions.yaml::CRITICAL_INPUT.positively_established": True,
    "currentness_dimensions.yaml::EGRESS_IDENTITY.bound_generation": 1,
    "currentness_dimensions.yaml::EGRESS_IDENTITY.bound_digest": "tos-paper-egress-identity-bound-g1",
    "currentness_dimensions.yaml::EGRESS_IDENTITY.restrictive_floor": 0,
    "currentness_dimensions.yaml::EGRESS_IDENTITY.positively_established": True,
    # --- risk_attestations.yaml ------------------------------------------
    "risk_attestations.yaml::numerically_safe.attested": True,
    "risk_attestations.yaml::valuation_ok.attested": True,
    "risk_attestations.yaml::all_fields_attributed.attested": True,
    "risk_attestations.yaml::limit_source_is_injected_envelope.attested": True,
    "risk_attestations.yaml::economic_commitment_exclusive.attested": True,
    "risk_attestations.yaml::flow_commitment_exclusive.attested": True,
    # --- egress_coordinates.yaml -----------------------------------------
    "egress_coordinates.yaml::endpoint.value": "synthetic://paper/order",
    "egress_coordinates.yaml::action.value": "NEW_ORDER",
    "egress_coordinates.yaml::method.value": "SUBMIT",
    "egress_coordinates.yaml::route_identity.value": "synthetic-route",
    "egress_coordinates.yaml::credential_generation.value": 0,
    "egress_coordinates.yaml::broker_session_generation.value": 0,
    "egress_coordinates.yaml::egress_generation.value": 1,
    "egress_coordinates.yaml::active_principal.value": "egressgw-{environment_label}",
    "egress_coordinates.yaml::capsule_terminus_fields.value": ["account", "instrument"],
    # --- broker_scopes.yaml ----------------------------------------------
    "broker_scopes.yaml::active_scope": "SYNTHETIC_FUTURES_ORDER",
    # --- engine.yaml -----------------------------------------------------
    "engine.yaml::dsl_evaluation_budget_steps": 1000,
    "engine.yaml::max_unresolved_send_per_scope": 1,
    # --- engine_driver.yaml ----------------------------------------------
    "engine_driver.yaml::replay_window_events": 1000000,
    # --- coordinator_preconditions.yaml ----------------------------------
    "coordinator_preconditions.yaml::live_authorization_state": "NOT_AUTHORIZED",
    "coordinator_preconditions.yaml::nonlive_broker_consuming.admitted": False,
    # --- finality.yaml ---------------------------------------------------
    "finality.yaml::currency": "KRW",
    "finality.yaml::release_proof_wait_ms": 60000,
    "finality.yaml::value_date": None,
    "finality.yaml::source_revision": None,
    "finality.yaml::proof_recipe_id": None,
    # --- safety_envelope.yaml --------------------------------------------
    "safety_envelope.yaml::envelope.envelope_id": "tos-paper-envelope-g1",
    "safety_envelope.yaml::envelope.envelope_generation": 1,
    "safety_envelope.yaml::envelope.envelope_version.version": "1",
    "safety_envelope.yaml::envelope.envelope_version.effective_date": "2026-09-23",
    "safety_envelope.yaml::envelope.envelope_version.evidence_package_version": None,
    "safety_envelope.yaml::envelope.envelope_version.approver_identity": "operator (System Owner) — 2026-09-18 승인 · 2026-09-23 채택",
    "safety_envelope.yaml::envelope.envelope_version.expiration_or_revalidation_date": None,
    "safety_envelope.yaml::envelope.envelope_version.superseded_version_link": None,
    "safety_envelope.yaml::envelope.envelope_version.change_classification": None,
    "safety_envelope.yaml::envelope.governed_dimensions": [],
    "safety_envelope.yaml::envelope.permitted_scope": [],
    "safety_envelope.yaml::envelope.prohibited_fallbacks": [],
    "safety_envelope.yaml::envelope.residual_risk_ceiling": None,
    "safety_envelope.yaml::envelope.evidence_package_ref": None,
    # --- safety_profile.yaml ---------------------------------------------
    "safety_profile.yaml::profile.profile_id": "tos-paper-profile-g1",
    "safety_profile.yaml::profile.profile_generation": 1,
    "safety_profile.yaml::profile.profile_version.version": "1",
    "safety_profile.yaml::profile.profile_version.effective_date": "2026-09-23",
    "safety_profile.yaml::profile.profile_version.evidence_package_version": None,
    "safety_profile.yaml::profile.profile_version.approver_identity": "operator (System Owner) — 2026-09-18 승인 · 2026-09-23 채택",
    "safety_profile.yaml::profile.profile_version.expiration_or_revalidation_date": None,
    "safety_profile.yaml::profile.profile_version.superseded_version_link": None,
    "safety_profile.yaml::profile.profile_version.change_classification": None,
    "safety_profile.yaml::profile.target_envelope_id": "tos-paper-envelope-g1",
    "safety_profile.yaml::profile.target_envelope_generation": 1,
    "safety_profile.yaml::profile.governed_dimensions": [],
    "safety_profile.yaml::profile.scope": [],
    "safety_profile.yaml::profile.permitted_behaviors": [],
    "safety_profile.yaml::profile.fallback_rules": [],
    "safety_profile.yaml::profile.evidence_package_ref": None,
    # --- safety_activation.yaml ------------------------------------------
    "safety_activation.yaml::activation.activation_id": "tos-paper-activation-g1",
    "safety_activation.yaml::activation.profile_generation": 1,
    "safety_activation.yaml::activation.envelope_digest": None,
    "safety_activation.yaml::activation.profile_digest": None,
    "safety_activation.yaml::activation.bundle_digest": None,
    "safety_activation.yaml::activation.scope": [],
    "safety_activation.yaml::activation.approval_ids": [],
    "safety_activation.yaml::activation.compatibility_attestation_refs": [],
    "safety_activation.yaml::activation.predecessor_generation": None,
    "safety_activation.yaml::activation.restrictive_generation_effects": [],
    "safety_activation.yaml::not_expired": True,
    "safety_activation.yaml::members": None,
    # --- safety_deviations.yaml ------------------------------------------
    "safety_deviations.yaml::deviations.active_set.active_set_id": "tos-paper-deviation-set-g1",
    "safety_deviations.yaml::deviations.active_set.active_set_generation": 1,
    "safety_deviations.yaml::deviations.active_set.deviation_generation": 1,
    "safety_deviations.yaml::deviations.active_set.is_complete": True,
    "safety_deviations.yaml::deviations.active_set.combined_within_envelope": True,
    "safety_deviations.yaml::deviations.applicable_decision_ids": [],
    "safety_deviations.yaml::deviations.members": [],
    # --- safety_incidents.yaml -------------------------------------------
    "safety_incidents.yaml::incidents.active_set.active_set_id": "tos-paper-incident-set-g1",
    "safety_incidents.yaml::incidents.active_set.active_set_generation": 1,
    "safety_incidents.yaml::incidents.active_set.incident_generation": 1,
    "safety_incidents.yaml::incidents.active_set.safety_cell": "tos-paper-cell-g1",
    "safety_incidents.yaml::incidents.active_set.shared_dependencies": [],
    "safety_incidents.yaml::incidents.active_set.is_complete": True,
    "safety_incidents.yaml::incidents.active_set.is_current": True,
    "safety_incidents.yaml::incidents.applicable_incident_ids": [],
    "safety_incidents.yaml::incidents.members": [],
    # --- monitor_coverage.yaml -------------------------------------------
    "monitor_coverage.yaml::coverage.manifest.coverage_manifest_id": "tos-paper-coverage-manifest-g1",
    "monitor_coverage.yaml::coverage.manifest.coverage_generation": 1,
    "monitor_coverage.yaml::coverage.manifest.coverage_manifest_digest": "tos-paper-coverage-manifest-digest-g1",
    "monitor_coverage.yaml::coverage.manifest.policy_digest": "tos-paper-coverage-policy-digest-g1",
    "monitor_coverage.yaml::coverage.manifest.is_complete": True,
    "monitor_coverage.yaml::coverage.items.evidence-tip-currency.restrictive_response_present": True,
    "monitor_coverage.yaml::coverage.items.evidence-tip-currency.alert_path_present": True,
    "monitor_coverage.yaml::coverage.items.evidence-tip-currency.evidence_path_present": True,
    "monitor_coverage.yaml::coverage.items.evidence-tip-currency.currentness_rule_present": True,
    "monitor_coverage.yaml::coverage.items.evidence-tip-currency.closure_1_to_12_complete": True,
    "monitor_coverage.yaml::coverage.items.evidence-tip-currency.criticality": "CRITICAL",
    "monitor_coverage.yaml::coverage.items.time-service-health.restrictive_response_present": True,
    "monitor_coverage.yaml::coverage.items.time-service-health.alert_path_present": True,
    "monitor_coverage.yaml::coverage.items.time-service-health.evidence_path_present": True,
    "monitor_coverage.yaml::coverage.items.time-service-health.currentness_rule_present": True,
    "monitor_coverage.yaml::coverage.items.time-service-health.closure_1_to_12_complete": True,
    "monitor_coverage.yaml::coverage.items.time-service-health.criticality": "CRITICAL",
    "monitor_coverage.yaml::coverage.items.inbox-backlog.restrictive_response_present": True,
    "monitor_coverage.yaml::coverage.items.inbox-backlog.alert_path_present": True,
    "monitor_coverage.yaml::coverage.items.inbox-backlog.evidence_path_present": True,
    "monitor_coverage.yaml::coverage.items.inbox-backlog.currentness_rule_present": True,
    "monitor_coverage.yaml::coverage.items.inbox-backlog.closure_1_to_12_complete": True,
    "monitor_coverage.yaml::coverage.items.inbox-backlog.criticality": "CRITICAL",
    "monitor_coverage.yaml::coverage.bounds.max_evidence_tip_stall_ms": 60000,
    "monitor_coverage.yaml::coverage.bounds.healthy_time_states": ["TRUSTED"],
    "monitor_coverage.yaml::coverage.bounds.max_inbox_unconsumed": 100,
}


#: Leaves deliberately NOT value-pinned here, each with the one-line reason.
#:
#: A key ending in ``*`` covers every leaf under that dotted prefix. The ONLY entries are
#: ``broker_scopes.yaml``'s scope table, and they are not unguarded: the file is a verbatim
#: copy of the shipped example and
#: :func:`test_broker_scopes_body_is_the_shipped_example_plus_one_line` pins that byte-for-byte
#: — a STRONGER guard than a value pin, since it catches an added, removed or reordered line
#: too, not only a changed value. ``active_scope`` is the one line that legitimately differs,
#: and it IS value-pinned above.
_UNPINNED_BY_DESIGN: dict[str, str] = {
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


# ============================================================================
# Helpers
# ============================================================================


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
    """Leaves that are neither value-pinned nor exempted — the completeness gate's own
    measurement, taken as a function of ``config_dir`` so the gate can be proven live against
    a scratch copy rather than only asserted against the repo."""
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
    """Copy REAL deploy files into ``tmp_path`` so a test may mutate them — the named ones,
    or ALL 18 when no name is given (the value-pin check reads every file).

    Only the repo files are read; every write lands under ``tmp_path`` (D1.4 write guard).
    """
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
    """Rewrite the one YAML line holding ``dotted_key``'s scalar so it holds
    ``new_value_text``.

    Text substitution, never a ``yaml.safe_dump`` round-trip (module docstring): the round trip
    drops every header comment, which fires the provenance tests and produces a RED that proves
    nothing.

    ``dotted_key``'s leading segments are block ANCHORS (``route_identity.value`` ⇒ the
    ``value:`` inside the ``route_identity:`` block), which is what makes a key that repeats —
    ``value`` nine times in ``egress_coordinates.yaml``, ``attested`` six times in
    ``risk_attestations.yaml`` — addressable without ambiguity. The final segment must match
    exactly once after the anchors, so a mutation can neither silently no-op nor hit an
    unintended key.
    """
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
    # Anchored search: the first hit after the anchor block is the addressed one. Unanchored:
    # the key must be unique in the whole file.
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
    """Flip one scalar leaf back to ``null`` (named-TBD), asserting it was filled first — a
    mutation that silently no-ops would prove nothing."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert (
        _resolve_dotted(raw, dotted_key) is not None
    ), f"{path.name}:{dotted_key} was already null"
    _substitute_scalar_line(path, dotted_key, "null")


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
# The completeness gate — no leaf may be silently unpinned
# ============================================================================


def test_every_adopted_leaf_is_pinned_or_explicitly_unpinned() -> None:
    """review-794 HIGH-2, the class fix rather than the instance fix: it is not enough to add
    the ten bounds the reviewer happened to measure — a leaf added to any of these files later
    must not be able to arrive unpinned and unnoticed.

    Every leaf is either in :data:`_VALUE_PINS` or in :data:`_UNPINNED_BY_DESIGN` with a
    reason. Nothing else is admissible."""
    unaccounted = _unaccounted_leaves(_DEPLOY_DIR)
    assert not unaccounted, (
        "these adopted leaves are neither value-pinned nor listed in _UNPINNED_BY_DESIGN "
        f"with a reason: {unaccounted}"
    )


def test_the_completeness_gate_actually_fires(tmp_path: Path) -> None:
    """Dead-check guard: a gate that can never report anything is not a gate. Add a leaf to a
    scratch copy and :func:`_unaccounted_leaves` must name it — otherwise the test above would
    pass forever regardless of what the files grow."""
    config_dir = _deploy_copy(tmp_path)
    (config_dir / "engine.yaml").write_text(
        _read("engine.yaml") + "\nleaf_added_by_this_test: 7\n", encoding="utf-8"
    )
    assert "engine.yaml::leaf_added_by_this_test" in _unaccounted_leaves(config_dir)


def test_no_pin_names_a_leaf_that_no_longer_exists() -> None:
    """The reverse drift: a pin left behind after its leaf was renamed or removed silently
    stops guarding anything (the repo's own "레지스트리 + 고정 안 된 위성" failure shape)."""
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
    """The value itself — this is the path review-794 HIGH-2 found empty: an approved value
    quietly becoming a DIFFERENT, still-structurally-valid, unapproved value."""
    name, _, dotted = ref.partition("::")
    cursor: Any = _mapping(name)
    for key in dotted.split("."):
        cursor = cursor[key]
    assert cursor == _VALUE_PINS[ref]


@pytest.mark.parametrize(
    ("name", "key", "unapproved_text"),
    [
        # review-794 HIGH-1 verbatim: still a positive int, so the loader's own
        # `_require_positive_int` accepts it and the old null-only pin stayed GREEN.
        ("engine_driver.yaml", "replay_window_events", "1"),
        # review-794 HIGH-2 table rows — each was GREEN before this module had value pins.
        ("time.yaml", "MAX_time_source_precision_ms", "5000"),
        ("time.yaml", "MAX_process_suspension_ms", "999999"),
        ("time.yaml", "MIN_time_independent_reference_count", "99"),
        ("time.yaml", "tz_db_version", '"1999a"'),
        ("engine.yaml", "max_unresolved_send_per_scope", "50"),
        ("authority.yaml", "containment_bound_ms", "99999"),
        ("currentness_dimensions.yaml", "CONTEXT.positively_established", "false"),
        (
            "safety_deviations.yaml",
            "deviations.active_set.combined_within_envelope",
            "false",
        ),
        ("safety_incidents.yaml", "incidents.active_set.is_current", "false"),
        ("monitor_coverage.yaml", "coverage.bounds.max_inbox_unconsumed", "999999"),
    ],
)
def test_a_value_pin_actually_fires(
    name: str, key: str, unapproved_text: str, tmp_path: Path
) -> None:
    """Proves the pins are LIVE, not merely present: change a real approved value to another
    structurally-valid-but-unapproved one in a scratch copy and the pin check must name that
    leaf. Without this, :data:`_VALUE_PINS` could drift into a decorative registry.

    ``currentness_dimensions.yaml``'s ``positively_established`` and the two safety-mesh
    booleans are deliberately in this list: they are the PR's own disclosed deviations, and
    flipping one is the exact "positive safety assertion silently becomes false" edit.
    """
    config_dir = _deploy_copy(tmp_path)
    _substitute_scalar_line(config_dir / name, key, unapproved_text)
    mismatches = _mismatched_pins(config_dir)
    assert any(ref == f"{name}::{key}" for ref, _, _ in mismatches), (
        f"changing {name}::{key} to {unapproved_text} did not trip any value pin "
        f"(mismatches: {mismatches})"
    )


# ============================================================================
# Loads + named-TBD mutation
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
    #: ``(<file>, <scalar key>)`` — the leaf the named-TBD mutation flips to null.
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
    """A-2: the file an operator actually deploys is read by the loader that reads it at
    boot — never a fixture shaped like it."""
    pin.load(_DEPLOY_DIR)


@pytest.mark.parametrize("pin", _LOADABLE, ids=_loadable_ids())
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
    file_name, key = pin.mutate
    _text_set_null(config_dir / file_name, key)
    with pytest.raises(pin.error, match=re.escape(key.split(".")[-1])):
        pin.load(config_dir)


# ============================================================================
# The committed loader probe (review-794 MEDIUM-4)
# ============================================================================

#: Every probe label that REFUSES against the deployed config today, with why. The landing
#: record (§7.8) quotes this partition; pinning it BY NAME is what keeps the record and the
#: loaders from drifting apart. Each entry is a real, named blocker — not a tolerated failure.
_EXPECTED_REFUSALS: dict[str, str] = {
    "finality.yaml": "제안표 §6 1·2항 — value_date/source_revision/proof_recipe_id 추천값 없음",
    "safety_activation.yaml::members": "제안표 §3 [D] — print-policy-digests 가 막혀 도출 불가",
    "venue_constraint_policy.yaml": "2026-09-16 채택분의 운영자-기입 scope.accounts",
    "order_construction_policy.yaml": "2026-09-16 채택분의 운영자-기입 scope.accounts",
    "aggregate_risk_policy.yaml": "2026-09-16 채택분의 운영자-기입 instrument_scope",
    "action_flow_policy.yaml": "2026-09-16 채택분의 운영자-기입 account_scope",
    "construction.yaml": "미채택 — 제안표가 7개 리프에 값을 주지 않는다(A-4)",
    "strategies/": "제안표 §6 7항 — 전략 DSL 은 부팅용 임의값 금지",
}


def test_loader_probe_partition_is_as_recorded() -> None:
    """review-794 MEDIUM-4: the landing record's "N PASS / M REFUSE" must be re-derivable.

    :mod:`._loader_probe` is that probe, committed; this pins its partition BY NAME, so the
    §7.8 number cannot drift from what the loaders actually do. A newly-filled operator
    coordinate turns this RED — which is the point: the record must be updated with it.
    """
    outcomes = run_probes(_DEPLOY_DIR)
    assert refusing_labels(outcomes) == frozenset(_EXPECTED_REFUSALS), format_table(
        outcomes
    )
    passed = sum(1 for outcome in outcomes if outcome.passed)
    assert (passed, len(outcomes)) == (17, 25), format_table(outcomes)


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
# These duplicate _VALUE_PINS deliberately: the table is the mechanical net, and these carry
# the REASON an operator needs when one of them goes red.


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

    This is also what backs every ``broker_scopes.yaml`` entry in
    :data:`_UNPINNED_BY_DESIGN` — a byte pin is strictly stronger than a value pin there.
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


def test_replay_window_covers_the_whole_inbox() -> None:
    """Proposal §4.2 ⚠ (review-794 HIGH-1): the file's own header warns that a window smaller
    than the whole inbox can report a FALSE divergence from lost ledger context. The loader
    only requires a POSITIVE int, so ``1`` passes it — the approved value is the guard.
    """
    assert _mapping("engine_driver.yaml")["replay_window_events"] == 1_000_000


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
# The 2026-09-23 operator answers
# ============================================================================


def test_required_dimensions_is_the_whole_mandated_floor() -> None:
    """Operator 2026-09-23 "그대로 사용" — proposal §6 item 6 had left this a design call;
    the answer is the kernel's own ``MANDATED_DIMENSION_FLOOR``, as the earlier value table
    (``docs/plans/2026-09-12-tos-operator-value-proposals.md`` §2, grade C) already
    recommended.

    Compared against the KERNEL, not a transcribed literal: a floor member added later must
    show up here as RED, because a policy declaring FEWER than the floor makes
    ``policy_covers_mandated_dimensions`` honestly false and refuses to boot."""
    from tos.cur import MANDATED_DIMENSION_FLOOR

    declared = _mapping("currentness.yaml")["required_dimensions"]
    assert declared == sorted(key.value for key in MANDATED_DIMENSION_FLOOR)
    assert len(declared) == 21


def test_monitor_coverage_bounds_use_the_earlier_recommended_values() -> None:
    """Operator 2026-09-23 "추천 값이 있으면 활용". Proposal §6 item 5 called these "상위
    원천 미확인"; re-searching the repo found ``docs/plans/2026-09-12-tos-operator-value-
    proposals.md`` §4 recommending exactly these three (grade C, "서버 실측 후 하향")."""
    bounds = _mapping("monitor_coverage.yaml")["coverage"]["bounds"]
    assert bounds["max_evidence_tip_stall_ms"] == 60_000
    assert bounds["healthy_time_states"] == ["TRUSTED"]
    assert bounds["max_inbox_unconsumed"] == 100


def test_healthy_time_states_is_the_narrowest_honest_declaration() -> None:
    """``TRUSTED`` is the only ``tos.time.HealthState`` member that means "time is
    trustworthy"; naming any other would widen what this monitor calls healthy."""
    from tos.time import HealthState

    declared = _mapping("monitor_coverage.yaml")["coverage"]["bounds"][
        "healthy_time_states"
    ]
    assert declared == ["TRUSTED"]
    assert set(declared) < {member.value for member in HealthState}


# ============================================================================
# Still-undetermined leaves — pinned BY KEY NAME
# ============================================================================


@pytest.mark.parametrize("key", ["value_date", "source_revision", "proof_recipe_id"])
def test_finality_undetermined_keys_are_still_null(key: str) -> None:
    """Proposal §6 items 1-2, re-searched under the 2026-09-23 "추천 값이 있으면 활용"
    answer and still unfilled — each for its own measured reason (the file header carries
    them):

    * ``proof_recipe_id`` — ADR-002-030 §29 is titled "Open Implementation Questions" and its
      Q3 names no approved identifier at all; the 2026-09-12 table grades it **M** ("개발 측
      값 제안 없음"). Not merely unfound: it does not yet exist.
    * ``source_revision`` — grade **M** (the deploy git SHA, which the commit writing this file
      cannot know).
    * ``value_date`` — a recommendation EXISTS (2026-09-12 §5, ``T+2``, grade B) but its stated
      basis is the KRX **stock** settlement date while this deployment's adopted scope is
      ``SYNTHETIC_FUTURES_ORDER``. Applying it would be a wrong value wearing a citation.
    """
    assert _mapping("finality.yaml")[key] is None


def test_finality_refuses_while_those_keys_are_undetermined() -> None:
    with pytest.raises(FinalityConfigError, match="value_date"):
        load_finality_config(_DEPLOY_DIR / "finality.yaml")


def test_activation_members_is_still_undetermined_and_refuses() -> None:
    """Proposal §3 [D] — ``members`` is DERIVED from
    ``print-policy-digests --config-dir <dir>``, never hand-written. A-3 (2026-09-23) ran
    that command and it REFUSED: ``venue_constraint_policy.yaml``'s ``scope.accounts`` is
    still the operator-fill ``"TBD"`` the 2026-09-16 adoption deliberately left (that file's
    own header: "the paper account number (never committed here)").

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


def _critical_input_scheme() -> Any:
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

    return get_scheme(EV_L1_PROVISIONAL_VERSION)


def _critical_input_field_keys(config_dir: Path) -> frozenset[str]:
    loaded = load_critical_input_policy(
        config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME,
        scheme=_critical_input_scheme(),
    )
    return frozenset(str(key) for key in loaded.fields)


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
