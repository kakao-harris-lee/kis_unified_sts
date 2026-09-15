"""tos_runtime.riskstate.policies — Aggregate Risk Policy / Action Flow Policy INSTANCE
document loaders (TOS risk state service wave, plan §2.1/§4.1;
``docs/plans/2026-09-16-tos-risk-state-service-plan.md``; DR-0003 §2.1 — "An Aggregate Risk
Policy instance and an Action Flow Policy instance follow DR-0002 §2.1 and §2.2 verbatim").

**Mirrors the venue loaders exactly, extended, not reinvented.** This module reuses
:mod:`tos_runtime.venue._policy_primitives` by import (fail-closed YAML primitives, the
``status: ISSUED``-only rule, the ``canonical_digest`` TBD-or-exact cross-check, presence-only
template rule-list/mapping-key shape fidelity, ``require_singleton_list_str``) — no primitive is
copied. An INSTANCE document is: the FULL key set of
``tos-spec/src/part-1-foundation/verification/AGGREGATE-RISK-POLICY-template.yaml`` /
``ACTION-FLOW-POLICY-template.yaml`` (every template key present; rule lists are data this
loader never interprets) plus two sibling blocks NEITHER template declares —
``_model_view`` (the kernel record's own ``_COVERED_FIELDS``) and ``_runtime`` (runtime-only
facts the kernel record does not carry) — the same DR-0002 idiom
:mod:`tos_runtime.venue._venue_policy_loader` / ``_order_construction_policy_loader`` already
realize for the Venue Constraint Policy / Order Construction Policy (those two blocks are NOT
part of the tos-spec template file itself; they are a runtime config-authoring convention, as
:mod:`tests.venue._documents`'s own module docstring confirms for the venue pair).

**What this module does NOT do (lane a boundary, plan §4.1).** It issues neither policy
against a Hard Safety Envelope — the ARE ``injected_envelope_max``/HSE dimension cross-check
(plan §2.1 row "ARE ``injected_envelope_max``") is a LANE B wiring-time responsibility, run
once both this policy AND the HSE are loaded; this loader has no HSE input and performs no such
check. It does not activate either policy (``tos_runtime.venue.activation
.require_member_activated`` is lane b's job, called with the new
``AGGREGATE_RISK_POLICY``/``ACTION_FLOW_POLICY`` member kinds — plan §4.1's own closing line).

**Kernel field shapes actually measured (not assumed).**
``tos.are.records.AggregateRiskPolicy.governed_dimensions`` is a bare
``tuple[RiskDimensionKind, ...]`` (dimension TOKENS, not descriptor objects) —
``tos/src/tos/are/records.py:345``. ``tos.afg.records.ActionFlowPolicy._COVERED_FIELDS``
(``tos/src/tos/afg/records.py:394-406``) names ``governed_dimensions``, ``governed_scopes``,
``governed_action_classes``, ``bundle_member_kind`` in addition to the ARE-shared
``policy_generation``/``policy_version``/``signer_identity``/``approval_identity``
/``evidence_package_ref`` — so the AFG ``_model_view`` carries one more field than the ARE one.

**Dimension-id convention (plan §0 survey "픽스처 관용구", reused not invented).** ARE
dimension ids are ``f"{scope}::{dimension}"`` (matching
``tos_runtime/tests/compose/conftest.py``'s own ``safety_envelope.yaml`` convention this
loader's ``_runtime.dimension_ids`` keys are cross-checked against) — the loader REQUIRES each
``_runtime.dimension_ids`` YAML key to equal exactly ``f"{scope}::{dimension}"`` for its own
nested ``scope``/``dimension`` pair (fail-closed on drift, never a silently-accepted arbitrary
key).

Firewall (R1, runtime scope): stdlib + ``pyyaml`` (transitively, via the reused primitives) +
``tos.*`` + ``tos_runtime.venue._policy_primitives`` only — no ``shared.*``, no
``os.environ``/``subprocess``/``importlib.import_module`` (``tools/tos_firewall_check.py``
scans tests too).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from tos.afg import (
    ActionClassKind,
    ActionFlowDimensionKind,
    ActionFlowPolicy,
    ActionFlowScopeKind,
    ScopeIndependenceEvidence,
)
from tos.are import (
    AdverseScenarioKind,
    AggregateRiskPolicy,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityComponent, CapacityVector

from tos_runtime.venue._policy_primitives import (
    ACCEPTED_SCHEMA_VERSION,
    TEMPLATE_MAPPING_KEYS,
    VenuePolicyConfigError,
    check_canonical_digest,
    load_mapping,
    require_exact_str,
    require_filled_str,
    require_int,
    require_issued_status,
    require_list,
    require_mapping_key,
    require_nullable_str_key_present,
    require_str,
    require_str_list,
    require_template_shape,
)

__all__ = [
    "VenuePolicyConfigError",
    "AGGREGATE_RISK_POLICY_CONFIG_NAME",
    "ACTION_FLOW_POLICY_CONFIG_NAME",
    "LoadedAggregateRiskPolicy",
    "load_aggregate_risk_policy",
    "DeploymentFlowFacts",
    "LoadedActionFlowPolicy",
    "load_action_flow_policy",
]

#: The runtime INSTANCE file names (distinct from the tos-spec TEMPLATE file names).
AGGREGATE_RISK_POLICY_CONFIG_NAME = "aggregate_risk_policy.yaml"
ACTION_FLOW_POLICY_CONFIG_NAME = "action_flow_policy.yaml"

_ARE_ARTIFACT_TYPE = "AGGREGATE_RISK_POLICY"
_AFG_ARTIFACT_TYPE = "ACTION_FLOW_POLICY"

#: Both templates carry a ``hard_safety_envelope``/``runtime_safety_profile`` top-level
#: mapping block (``{envelope_id|profile_id, generation, canonical_digest}``, all null/TBD in
#: the template) alongside ``authority``/``evidence`` — same presence-only discipline (this
#: loader never interprets their content; the actual HSE cross-check is a lane b concern, see
#: module docstring).
_RISK_TEMPLATE_MAPPING_KEYS: tuple[str, ...] = (
    *TEMPLATE_MAPPING_KEYS,
    "hard_safety_envelope",
    "runtime_safety_profile",
)

#: AGGREGATE-RISK-POLICY-template.yaml top-level rule-list keys this loader only checks for
#: presence/shape (list-typed) — content unread, uninterpreted. Order matches the template file.
_ARE_TEMPLATE_LIST_KEYS: tuple[str, ...] = (
    "risk_dimensions",
    "scope_aggregation_rules",
    "valuation_and_uncertainty_rules",
    "scenario_set_requirements",
    "netting_hedge_and_correlation_rules",
    "margin_collateral_and_liquidity_rules",
    "numerical_safety_rules",
    "dependency_closure_rules",
    "compatibility_requirements",
    "invalidation_conditions",
    "approved_by",
)

#: The ARE policy's scope-array keys (template order). ``instrument_scope``/``account_scope``
#: are required single-entry (v1, plan §2.1); every other array is an explicit list of any
#: length (``[]`` accepted).
_ARE_SINGLETON_SCOPE_KEYS: tuple[str, ...] = ("instrument_scope", "account_scope")
_ARE_LIST_SCOPE_KEYS: tuple[str, ...] = (
    "environment_scope",
    "safety_cell_scope",
    "legal_portfolio_scope",
    "strategy_scope",
    "venue_scope",
    "currency_scope",
)

#: ACTION-FLOW-POLICY-template.yaml top-level rule-list keys — same presence-only discipline.
_AFG_TEMPLATE_LIST_KEYS: tuple[str, ...] = (
    "action_classes",
    "resource_dimensions_and_units",
    "scope_aggregation_and_shared_limit_rules",
    "rate_burst_queue_and_in_flight_limits",
    "cause_amplification_limits",
    "retry_reconnect_replay_and_redelivery_rules",
    "protective_flow_reservations",
    "trustworthy_time_and_refill_rules",
    "atomic_risk_and_flow_commitment_rules",
    "invalidation_and_containment_rules",
    "recovery_and_non_revival_rules",
    "compatibility_requirements",
    "approved_by",
)

#: The AFG policy's scope-array keys (template order) — all explicit lists, no v1 singleton
#: requirement is named for this policy in plan §2.1 (unlike ARE's instrument/account pair).
_AFG_LIST_SCOPE_KEYS: tuple[str, ...] = (
    "environment_scope",
    "safety_cell_scope",
    "broker_scope",
    "legal_portfolio_scope",
    "account_scope",
    "credential_session_route_and_endpoint_scope",
    "venue_and_instrument_scope",
    "strategy_intent_and_cause_scope",
)

#: The AFG ``_runtime.limits`` mapping's four fixed keys (plan §4.1).
_AFG_LIMIT_KEYS: tuple[str, ...] = (
    "hard_limit",
    "runtime_limit",
    "envelope_max",
    "decision_effective_limit",
)

#: The AFG ``_runtime.scope_independence`` mapping's eight boolean axes
#: (:class:`~tos.afg.ScopeIndependenceEvidence`'s own six separation axes plus the two "basis is
#: only ..." negatives — ``tos/src/tos/afg/records.py:145-156``).
_SCOPE_INDEPENDENCE_BOOL_KEYS: tuple[str, ...] = (
    "allocation_separated",
    "refill_separated",
    "broker_enforcement_separated",
    "credential_session_state_separated",
    "failure_domain_separated",
    "final_route_separated",
    "basis_is_local_counter_only",
    "basis_is_scheduler_priority_only",
)

#: :class:`DeploymentFlowFacts`'s three fixed field names, in declaration order — the ONLY
#: three afg admission witnesses this wave treats as a governed-instance DECLARATION rather
#: than an observation (DR-0003 §2.3's own "declared" list, the last three of its four
#: declaration bullets: "whether concurrent consumers share one envelope, whether a duplicate
#: event may create a new allowance, and whether the envelope resets on a duplicate").
_DEPLOYMENT_FACT_KEYS: tuple[str, ...] = (
    "concurrent_consumers_share_one_envelope",
    "envelope_reset_on_duplicate",
    "duplicate_event_created_new_allowance",
)


def _require_explicit_list_str(
    raw: Mapping[str, Any], key: str, path: Path, ctx: str
) -> tuple[str, ...]:
    entries = require_list(dict(raw), key, path, ctx)
    return require_str_list(entries, path, f"{ctx}.{key}")


def _require_singleton_scope(raw: Mapping[str, Any], key: str, path: Path) -> str:
    """Like :func:`tos_runtime.venue._policy_primitives.require_singleton_list_str`, but for a
    TOP-LEVEL policy scope array (the ARE template has no nested ``scope:`` mapping the way the
    venue templates do — every scope array is a direct top-level key)."""
    entries = require_list(dict(raw), key, path, "policy")
    values = require_str_list(entries, path, f"policy.{key}")
    if len(values) != 1:
        raise VenuePolicyConfigError(
            f"{path}: policy.{key} must be a list of EXACTLY one string for a single live "
            f"scope (v1, plan §2.1) — got {len(values)}"
        )
    if values[0] == "TBD" or not values[0].strip():
        raise VenuePolicyConfigError(
            f"{path}: policy.{key} is still 'TBD'/empty (named-TBD) — fill the deployment "
            "coordinate before activation"
        )
    return values[0]


def _require_nonnegative_decimal(value: Any, path: Path, ctx: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise VenuePolicyConfigError(
            f"{path}: {ctx} must be a decimal-shaped string or int"
        )
    try:
        magnitude = Decimal(str(value))
    except InvalidOperation as exc:
        raise VenuePolicyConfigError(f"{path}: {ctx} is not a valid decimal") from exc
    if magnitude < 0:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} must be non-negative (got {magnitude})"
        )
    return magnitude


# ===========================================================================
# Aggregate Risk Policy
# ===========================================================================


@dataclass(frozen=True)
class LoadedAggregateRiskPolicy:
    """A loaded, kernel-issued Aggregate Risk Policy plus its ``_runtime`` derived facts
    (plan §4.1). ``dimension_ids`` keys are (scope, dimension) — the Python-side INVERSE of
    the YAML ``_runtime.dimension_ids`` mapping (which keys by the composed id string) — so a
    caller can resolve a governed (scope, dimension) pair straight to its dimension id without
    re-parsing the ``"<SCOPE>::<DIMENSION>"`` convention."""

    policy: AggregateRiskPolicy
    dimension_ids: Mapping[tuple[RiskScopeKind, RiskDimensionKind], str]
    effective_limits: CapacityVector
    required_scenario_kinds: frozenset[AdverseScenarioKind]
    required_scopes: frozenset[RiskScopeKind]
    applicable_risk_scopes: tuple[str, ...]
    unit: str
    #: Top-level ``instrument_scope``/``account_scope`` singleton strings (lane b addition —
    #: validated but previously discarded; a wiring-time cross-check needs the actual values).
    instrument_scope: str
    account_scope: str


def _parse_are_model_view(
    raw: dict[str, Any], path: Path, *, top_level_generation: int
) -> tuple[
    int,
    str,
    tuple[RiskDimensionKind, ...],
    tuple[RiskScopeKind, ...],
    str | None,
    str | None,
    str | None,
]:
    mv_raw = require_mapping_key(raw, "_model_view", path)
    generation = require_int(mv_raw, "policy_generation", path, "_model_view")
    if generation != top_level_generation:
        raise VenuePolicyConfigError(
            f"{path}: _model_view.policy_generation {generation!r} != top-level "
            f"aggregate_risk_generation {top_level_generation!r} — refusing"
        )
    policy_version = require_str(mv_raw, "policy_version", path, "_model_view")
    dim_entries = require_list(mv_raw, "governed_dimensions", path, "_model_view")
    dim_tokens = require_str_list(dim_entries, path, "_model_view.governed_dimensions")
    governed_dimensions: list[RiskDimensionKind] = []
    for token in dim_tokens:
        try:
            governed_dimensions.append(RiskDimensionKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.governed_dimensions {token!r} is not a known "
                "RiskDimensionKind"
            ) from exc
    scope_entries = require_list(mv_raw, "governed_scopes", path, "_model_view")
    scope_tokens = require_str_list(scope_entries, path, "_model_view.governed_scopes")
    governed_scopes: list[RiskScopeKind] = []
    for token in scope_tokens:
        try:
            governed_scopes.append(RiskScopeKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.governed_scopes {token!r} is not a known RiskScopeKind"
            ) from exc
    signer_identity = mv_raw.get("signer_identity")
    approval_identity = mv_raw.get("approval_identity")
    evidence_package_ref = mv_raw.get("evidence_package_ref")
    for name, value in (
        ("signer_identity", signer_identity),
        ("approval_identity", approval_identity),
        ("evidence_package_ref", evidence_package_ref),
    ):
        if "_model_view" not in raw or name not in mv_raw:
            raise VenuePolicyConfigError(
                f"{path}: _model_view missing required key {name!r}"
            )
        if value is not None and not isinstance(value, str):
            raise VenuePolicyConfigError(
                f"{path}: _model_view.{name} must be a string or null"
            )
    return (
        generation,
        policy_version,
        tuple(governed_dimensions),
        tuple(governed_scopes),
        signer_identity,
        approval_identity,
        evidence_package_ref,
    )


def _parse_are_dimension_ids(
    runtime_raw: dict[str, Any],
    path: Path,
    *,
    governed_dimensions: tuple[RiskDimensionKind, ...],
    governed_scopes: tuple[RiskScopeKind, ...],
) -> dict[tuple[RiskScopeKind, RiskDimensionKind], str]:
    ids_raw = require_mapping_key(runtime_raw, "dimension_ids", path)
    governed_dimension_set = frozenset(governed_dimensions)
    governed_scope_set = frozenset(governed_scopes)
    result: dict[tuple[RiskScopeKind, RiskDimensionKind], str] = {}
    for dimension_id, entry in ids_raw.items():
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(
                f"{path}: _runtime.dimension_ids[{dimension_id!r}] must be a mapping"
            )
        ctx = f"_runtime.dimension_ids[{dimension_id!r}]"
        scope_token = require_str(entry, "scope", path, ctx)
        dimension_token = require_str(entry, "dimension", path, ctx)
        try:
            scope = RiskScopeKind(scope_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.scope {scope_token!r} is not a known RiskScopeKind"
            ) from exc
        try:
            dimension = RiskDimensionKind(dimension_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.dimension {dimension_token!r} is not a known RiskDimensionKind"
            ) from exc
        expected_id = f"{scope_token}::{dimension_token}"
        if dimension_id != expected_id:
            raise VenuePolicyConfigError(
                f"{path}: {ctx} key {dimension_id!r} != the required "
                f"'<scope>::<dimension>' convention {expected_id!r}"
            )
        if scope not in governed_scope_set:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.scope {scope_token!r} is not among the policy's own "
                f"_model_view.governed_scopes {sorted(s.value for s in governed_scope_set)!r}"
            )
        if dimension not in governed_dimension_set:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.dimension {dimension_token!r} is not among the policy's own "
                f"_model_view.governed_dimensions "
                f"{sorted(d.value for d in governed_dimension_set)!r}"
            )
        result[(scope, dimension)] = dimension_id
    return result


def _parse_are_effective_limits(
    runtime_raw: dict[str, Any],
    path: Path,
    *,
    dimension_ids: dict[tuple[RiskScopeKind, RiskDimensionKind], str],
    unit: str,
) -> CapacityVector:
    limits_raw = require_mapping_key(runtime_raw, "effective_limits", path)
    known_ids = frozenset(dimension_ids.values())
    components: list[CapacityComponent] = []
    for dimension_id, value in limits_raw.items():
        if dimension_id not in known_ids:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.effective_limits key {dimension_id!r} is not among "
                f"_runtime.dimension_ids' own values {sorted(known_ids)!r}"
            )
        magnitude = _require_nonnegative_decimal(
            value, path, f"_runtime.effective_limits[{dimension_id!r}]"
        )
        components.append(
            CapacityComponent(dimension_id=dimension_id, magnitude=magnitude, unit=unit)
        )
    return CapacityVector(components=tuple(components))


def _parse_are_runtime_sets(
    runtime_raw: dict[str, Any], path: Path
) -> tuple[frozenset[AdverseScenarioKind], frozenset[RiskScopeKind], tuple[str, ...]]:
    """The three ``_runtime`` token-set fields ``required_scenario_kinds``/
    ``required_scopes``/``applicable_risk_scopes`` — split out of
    :func:`load_aggregate_risk_policy` purely for that function's own 100-line size budget
    (``config/tos_size_budget.yaml``); no behavioural difference from having this inline.
    """
    scenario_entries = require_list(
        runtime_raw, "required_scenario_kinds", path, "_runtime"
    )
    scenario_tokens = require_str_list(
        scenario_entries, path, "_runtime.required_scenario_kinds"
    )
    required_scenario_kinds: set[AdverseScenarioKind] = set()
    for token in scenario_tokens:
        try:
            required_scenario_kinds.add(AdverseScenarioKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.required_scenario_kinds {token!r} is not a known "
                "AdverseScenarioKind"
            ) from exc
    scope_entries = require_list(runtime_raw, "required_scopes", path, "_runtime")
    scope_tokens = require_str_list(scope_entries, path, "_runtime.required_scopes")
    required_scopes: set[RiskScopeKind] = set()
    for token in scope_tokens:
        try:
            required_scopes.add(RiskScopeKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.required_scopes {token!r} is not a known RiskScopeKind"
            ) from exc
    applicable_entries = require_list(
        runtime_raw, "applicable_risk_scopes", path, "_runtime"
    )
    applicable_tokens = require_str_list(
        applicable_entries, path, "_runtime.applicable_risk_scopes"
    )
    for token in applicable_tokens:
        try:
            RiskScopeKind(token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.applicable_risk_scopes {token!r} is not a known "
                "RiskScopeKind"
            ) from exc
    return (
        frozenset(required_scenario_kinds),
        frozenset(required_scopes),
        tuple(applicable_tokens),
    )


def _parse_are_top_level_scopes(raw: dict[str, Any], path: Path) -> dict[str, str]:
    """The two singleton scope strings + the list-scope/``global_scope_included`` presence
    checks — split out for :func:`load_aggregate_risk_policy`'s own 100-line size budget.
    """
    singleton_scopes = {
        key: _require_singleton_scope(raw, key, path)
        for key in _ARE_SINGLETON_SCOPE_KEYS
    }
    for key in _ARE_LIST_SCOPE_KEYS:
        _require_explicit_list_str(raw, key, path, "policy")
    if not isinstance(raw.get("global_scope_included"), bool):
        raise VenuePolicyConfigError(
            f"{path}: policy.global_scope_included must be a bool"
        )
    return singleton_scopes


def load_aggregate_risk_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedAggregateRiskPolicy:
    """Load, fail-closed-validate, and kernel-issue an Aggregate Risk Policy INSTANCE document
    from ``path`` (an instance of ``AGGREGATE-RISK-POLICY-template.yaml`` — see this module's
    own docstring).

    Raises:
        VenuePolicyConfigError: the file is missing/unreadable/not valid YAML/not a mapping;
            ``artifact_type``/``schema_version`` do not match the accepted constants;
            ``status`` is not ``ISSUED``; ``policy_id``/``policy_generation`` are absent,
            ``null``, or still ``"TBD"``; ``instrument_scope``/``account_scope`` do not carry
            exactly one string each; a ``_model_view``/``_runtime`` block is absent or a
            ``governed_dimensions``/``governed_scopes``/``required_scenario_kinds``
            /``required_scopes`` token is not a known kernel enum member; a
            ``_runtime.dimension_ids`` key does not equal its own
            ``"<scope>::<dimension>"`` convention, or names a (scope, dimension) pair outside
            the policy's own ``governed_scopes``/``governed_dimensions``; a
            ``_runtime.effective_limits`` key is not among ``_runtime.dimension_ids``' own
            values, or its magnitude is not a non-negative decimal; ``canonical_digest`` is
            present but does not match the freshly computed digest; or any template
            rule-list/``authority``/``evidence``/``hard_safety_envelope``
            /``runtime_safety_profile`` key is absent or not list/mapping-shaped.
    """
    raw = load_mapping(path, "aggregate risk policy")
    require_exact_str(raw, "artifact_type", _ARE_ARTIFACT_TYPE, path, "policy")
    require_exact_str(raw, "schema_version", ACCEPTED_SCHEMA_VERSION, path, "policy")
    require_issued_status(raw, path)
    policy_id = require_filled_str(raw, "policy_id", path, "policy")
    top_level_generation = require_int(raw, "aggregate_risk_generation", path, "policy")
    require_nullable_str_key_present(raw, "effective_from", path, "policy")
    require_nullable_str_key_present(raw, "review_due", path, "policy")

    singleton_scopes = _parse_are_top_level_scopes(raw, path)

    (
        model_view_generation,
        policy_version,
        governed_dimensions,
        governed_scopes,
        signer_identity,
        approval_identity,
        evidence_package_ref,
    ) = _parse_are_model_view(raw, path, top_level_generation=top_level_generation)

    runtime_raw = require_mapping_key(raw, "_runtime", path)
    unit = require_str(runtime_raw, "unit", path, "_runtime")
    dimension_ids = _parse_are_dimension_ids(
        runtime_raw,
        path,
        governed_dimensions=governed_dimensions,
        governed_scopes=governed_scopes,
    )
    effective_limits = _parse_are_effective_limits(
        runtime_raw, path, dimension_ids=dimension_ids, unit=unit
    )
    required_scenario_kinds, required_scopes, applicable_tokens = (
        _parse_are_runtime_sets(runtime_raw, path)
    )

    require_template_shape(
        raw,
        path,
        list_keys=_ARE_TEMPLATE_LIST_KEYS,
        mapping_keys=_RISK_TEMPLATE_MAPPING_KEYS,
    )

    policy = AggregateRiskPolicy.issue(
        scheme=scheme,
        policy_id=policy_id,
        policy_generation=model_view_generation,
        policy_version=policy_version,
        governed_dimensions=governed_dimensions,
        governed_scopes=governed_scopes,
        signer_identity=signer_identity,
        approval_identity=approval_identity,
        evidence_package_ref=evidence_package_ref,
    )
    assert isinstance(policy, AggregateRiskPolicy)
    check_canonical_digest(raw, path, policy.canonical_digest, "policy")

    return LoadedAggregateRiskPolicy(
        policy=policy,
        dimension_ids=dimension_ids,
        effective_limits=effective_limits,
        required_scenario_kinds=required_scenario_kinds,
        required_scopes=required_scopes,
        applicable_risk_scopes=applicable_tokens,
        unit=unit,
        instrument_scope=singleton_scopes["instrument_scope"],
        account_scope=singleton_scopes["account_scope"],
    )


# ===========================================================================
# Action Flow Policy
# ===========================================================================


@dataclass(frozen=True)
class DeploymentFlowFacts:
    """The three admission witnesses DR-0003 §2.3 names as **declarations**, never
    observations: "whether concurrent consumers share one envelope, whether a duplicate event
    may create a new allowance, and whether the envelope resets on a duplicate." Every field is
    an explicit ``bool`` — the loader refuses a ``null`` (fail-closed; a deployment fact left
    unfilled cannot be assumed either polarity). This dataclass carries NOTHING the loader
    itself observed; it is a typed transcription of the operator's own governed declaration.
    """

    concurrent_consumers_share_one_envelope: bool
    envelope_reset_on_duplicate: bool
    duplicate_event_created_new_allowance: bool


@dataclass(frozen=True)
class LoadedActionFlowPolicy:
    """A loaded, kernel-issued Action Flow Policy plus its ``_runtime`` derived facts
    (plan §4.1)."""

    policy: ActionFlowPolicy
    flow_dimension_id: str
    limits: Mapping[str, CapacityVector]
    scope_independence: ScopeIndependenceEvidence
    covered_scopes: tuple[ActionFlowScopeKind, ...]
    required_scopes: frozenset[ActionFlowScopeKind]
    applicable_action_flow_scopes: tuple[str, ...]
    action_class_map: Mapping[Any, ActionClassKind]
    deployment_facts: DeploymentFlowFacts
    #: ``(buy_side_token, sell_side_token)`` — lane b addition (plan §4.1 deviation, reported):
    #: :class:`~tos_runtime.riskstate.position.EvidencePositionReader` needs these as REQUIRED,
    #: non-default arguments; sourced from this instance's own ``_runtime.side_tokens:
    #: {buy, sell}`` (cross-checked at wiring time, :mod:`tos_runtime.compose._riskstate_wiring`).
    side_tokens: tuple[str, str]


def _parse_afg_model_view(
    raw: dict[str, Any], path: Path, *, top_level_generation: int
) -> tuple[
    int,
    str,
    tuple[ActionFlowDimensionKind, ...],
    tuple[ActionFlowScopeKind, ...],
    tuple[ActionClassKind, ...],
    str,
    str | None,
    str | None,
    str | None,
]:
    mv_raw = require_mapping_key(raw, "_model_view", path)
    generation = require_int(mv_raw, "policy_generation", path, "_model_view")
    if generation != top_level_generation:
        raise VenuePolicyConfigError(
            f"{path}: _model_view.policy_generation {generation!r} != top-level "
            f"action_flow_generation {top_level_generation!r} — refusing"
        )
    policy_version = require_str(mv_raw, "policy_version", path, "_model_view")
    dim_entries = require_list(mv_raw, "governed_dimensions", path, "_model_view")
    dim_tokens = require_str_list(dim_entries, path, "_model_view.governed_dimensions")
    governed_dimensions: list[ActionFlowDimensionKind] = []
    for token in dim_tokens:
        try:
            governed_dimensions.append(ActionFlowDimensionKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.governed_dimensions {token!r} is not a known "
                "ActionFlowDimensionKind"
            ) from exc
    scope_entries = require_list(mv_raw, "governed_scopes", path, "_model_view")
    scope_tokens = require_str_list(scope_entries, path, "_model_view.governed_scopes")
    governed_scopes: list[ActionFlowScopeKind] = []
    for token in scope_tokens:
        try:
            governed_scopes.append(ActionFlowScopeKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.governed_scopes {token!r} is not a known "
                "ActionFlowScopeKind"
            ) from exc
    class_entries = require_list(mv_raw, "governed_action_classes", path, "_model_view")
    class_tokens = require_str_list(
        class_entries, path, "_model_view.governed_action_classes"
    )
    governed_action_classes: list[ActionClassKind] = []
    for token in class_tokens:
        try:
            governed_action_classes.append(ActionClassKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.governed_action_classes {token!r} is not a known "
                "ActionClassKind"
            ) from exc
    bundle_member_kind = require_str(mv_raw, "bundle_member_kind", path, "_model_view")
    signer_identity = mv_raw.get("signer_identity")
    approval_identity = mv_raw.get("approval_identity")
    evidence_package_ref = mv_raw.get("evidence_package_ref")
    for name in ("signer_identity", "approval_identity", "evidence_package_ref"):
        if name not in mv_raw:
            raise VenuePolicyConfigError(
                f"{path}: _model_view missing required key {name!r}"
            )
        value = mv_raw[name]
        if value is not None and not isinstance(value, str):
            raise VenuePolicyConfigError(
                f"{path}: _model_view.{name} must be a string or null"
            )
    return (
        generation,
        policy_version,
        tuple(governed_dimensions),
        tuple(governed_scopes),
        tuple(governed_action_classes),
        bundle_member_kind,
        signer_identity,
        approval_identity,
        evidence_package_ref,
    )


def _parse_afg_limits(
    runtime_raw: dict[str, Any], path: Path, *, flow_dimension_id: str
) -> dict[str, CapacityVector]:
    limits_raw = require_mapping_key(runtime_raw, "limits", path)
    limits: dict[str, CapacityVector] = {}
    for key in _AFG_LIMIT_KEYS:
        if key not in limits_raw:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.limits missing required key {key!r}"
            )
        magnitude = _require_nonnegative_decimal(
            limits_raw[key], path, f"_runtime.limits.{key}"
        )
        limits[key] = CapacityVector(
            components=(
                CapacityComponent(dimension_id=flow_dimension_id, magnitude=magnitude),
            )
        )
    return limits


def _parse_scope_independence(
    runtime_raw: dict[str, Any], path: Path
) -> ScopeIndependenceEvidence:
    si_raw = require_mapping_key(runtime_raw, "scope_independence", path)
    scope_token = require_str(si_raw, "scope", path, "_runtime.scope_independence")
    try:
        scope = ActionFlowScopeKind(scope_token)
    except ValueError as exc:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.scope_independence.scope {scope_token!r} is not a known "
            "ActionFlowScopeKind"
        ) from exc
    bools: dict[str, bool] = {}
    for key in _SCOPE_INDEPENDENCE_BOOL_KEYS:
        if key not in si_raw:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.scope_independence missing required key {key!r}"
            )
        value = si_raw[key]
        if not isinstance(value, bool):
            raise VenuePolicyConfigError(
                f"{path}: _runtime.scope_independence.{key} must be an explicit true/false "
                "(a null scope-independence axis is UNKNOWN, never assumed either way)"
            )
        bools[key] = value
    return ScopeIndependenceEvidence(scope=scope, **bools)


def _parse_action_class_map(
    runtime_raw: dict[str, Any],
    path: Path,
    *,
    governed_action_classes: tuple[ActionClassKind, ...],
) -> dict[Any, ActionClassKind]:
    """Also cross-checks every value against ``governed_action_classes`` (folded in here,
    not the caller, purely for that function's own 100-line size budget)."""
    from tos.venue import (
        ActionClass,  # local import: keeps the top-level import list minimal
    )

    map_raw = require_mapping_key(runtime_raw, "action_class_map", path)
    result: dict[Any, ActionClassKind] = {}
    for key, value in map_raw.items():
        try:
            venue_class = ActionClass(key)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.action_class_map key {key!r} is not a known "
                "tos.venue.ActionClass"
            ) from exc
        if not isinstance(value, str):
            raise VenuePolicyConfigError(
                f"{path}: _runtime.action_class_map[{key!r}] must be a string"
            )
        try:
            kind = ActionClassKind(value)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.action_class_map[{key!r}] value {value!r} is not a known "
                "ActionClassKind"
            ) from exc
        if kind not in governed_action_classes:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.action_class_map maps onto {kind!r}, which is not among "
                f"_model_view.governed_action_classes "
                f"{sorted(c.value for c in governed_action_classes)!r}"
            )
        result[venue_class] = kind
    return result


def _parse_deployment_facts(
    runtime_raw: dict[str, Any], path: Path
) -> DeploymentFlowFacts:
    facts_raw = require_mapping_key(runtime_raw, "deployment_facts", path)
    values: dict[str, bool] = {}
    for key in _DEPLOYMENT_FACT_KEYS:
        if key not in facts_raw:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.deployment_facts missing required key {key!r}"
            )
        value = facts_raw[key]
        if not isinstance(value, bool):
            raise VenuePolicyConfigError(
                f"{path}: _runtime.deployment_facts.{key} must be an explicit true/false — "
                "this is a governed DECLARATION (DR-0003 §2.3), never observed or defaulted"
            )
        values[key] = value
    return DeploymentFlowFacts(**values)


def _parse_afg_runtime_scope_sets(
    runtime_raw: dict[str, Any], path: Path
) -> tuple[
    tuple[ActionFlowScopeKind, ...], frozenset[ActionFlowScopeKind], tuple[str, ...]
]:
    """The three ``_runtime`` scope-set fields ``covered_scopes``/``required_scopes``/
    ``applicable_action_flow_scopes`` — split out of :func:`load_action_flow_policy` purely
    for that function's own 100-line size budget; no behavioural difference from having this
    inline."""
    covered_entries = require_list(runtime_raw, "covered_scopes", path, "_runtime")
    covered_tokens = require_str_list(covered_entries, path, "_runtime.covered_scopes")
    covered_scopes: list[ActionFlowScopeKind] = []
    for token in covered_tokens:
        try:
            covered_scopes.append(ActionFlowScopeKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.covered_scopes {token!r} is not a known ActionFlowScopeKind"
            ) from exc

    required_entries = require_list(runtime_raw, "required_scopes", path, "_runtime")
    required_tokens = require_str_list(
        required_entries, path, "_runtime.required_scopes"
    )
    required_scopes: set[ActionFlowScopeKind] = set()
    for token in required_tokens:
        try:
            required_scopes.add(ActionFlowScopeKind(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.required_scopes {token!r} is not a known ActionFlowScopeKind"
            ) from exc

    applicable_entries = require_list(
        runtime_raw, "applicable_action_flow_scopes", path, "_runtime"
    )
    applicable_tokens = require_str_list(
        applicable_entries, path, "_runtime.applicable_action_flow_scopes"
    )
    for token in applicable_tokens:
        try:
            ActionFlowScopeKind(token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.applicable_action_flow_scopes {token!r} is not a known "
                "ActionFlowScopeKind"
            ) from exc
    return tuple(covered_scopes), frozenset(required_scopes), tuple(applicable_tokens)


def _parse_side_tokens(runtime_raw: dict[str, Any], path: Path) -> tuple[str, str]:
    """``_runtime.side_tokens: {buy, sell}`` (:class:`LoadedActionFlowPolicy`'s own docstring)
    — fail-closed on a missing block, a missing/blank string, or equal tokens."""
    side_raw = require_mapping_key(runtime_raw, "side_tokens", path)
    buy = require_filled_str(side_raw, "buy", path, "_runtime.side_tokens")
    sell = require_filled_str(side_raw, "sell", path, "_runtime.side_tokens")
    if buy == sell:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.side_tokens.buy and .sell are both {buy!r} — the two tokens "
            "must be distinct to distinguish a directional buy from a directional sell"
        )
    return (buy, sell)


def _parse_afg_runtime_core(
    runtime_raw: dict[str, Any],
    path: Path,
    *,
    governed_dimensions: tuple[ActionFlowDimensionKind, ...],
    governed_scopes: tuple[ActionFlowScopeKind, ...],
) -> tuple[str, dict[str, CapacityVector], ScopeIndependenceEvidence, tuple[str, str]]:
    """``flow_dimension_id``/``limits``/``scope_independence``/``side_tokens`` — split out for
    :func:`load_action_flow_policy`'s own 100-line size budget."""
    flow_dimension_id = require_str(runtime_raw, "flow_dimension_id", path, "_runtime")
    if flow_dimension_id not in {d.value for d in governed_dimensions}:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.flow_dimension_id {flow_dimension_id!r} is not among "
            f"_model_view.governed_dimensions "
            f"{sorted(d.value for d in governed_dimensions)!r}"
        )
    limits = _parse_afg_limits(runtime_raw, path, flow_dimension_id=flow_dimension_id)
    scope_independence = _parse_scope_independence(runtime_raw, path)
    if scope_independence.scope not in governed_scopes:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.scope_independence.scope {scope_independence.scope!r} is not "
            f"among _model_view.governed_scopes {sorted(s.value for s in governed_scopes)!r}"
        )
    side_tokens = _parse_side_tokens(runtime_raw, path)
    return flow_dimension_id, limits, scope_independence, side_tokens


def load_action_flow_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedActionFlowPolicy:
    """Load, fail-closed-validate, and kernel-issue an Action Flow Policy INSTANCE document
    from ``path`` (an instance of ``ACTION-FLOW-POLICY-template.yaml`` — see this module's own
    docstring).

    Raises:
        VenuePolicyConfigError: the same class of refusal :func:`load_aggregate_risk_policy`
            raises, plus: a ``_runtime.limits`` key is missing or not a non-negative decimal; a
            ``_runtime.scope_independence`` axis is missing or not an explicit bool; a
            ``_runtime.action_class_map`` key/value is not a known ``tos.venue.ActionClass``
            / ``ActionClassKind``; a ``_runtime.deployment_facts`` axis is missing or not an
            explicit bool.
    """
    raw = load_mapping(path, "action flow policy")
    require_exact_str(raw, "artifact_type", _AFG_ARTIFACT_TYPE, path, "policy")
    require_exact_str(raw, "schema_version", ACCEPTED_SCHEMA_VERSION, path, "policy")
    require_issued_status(raw, path)
    policy_id = require_filled_str(raw, "policy_id", path, "policy")
    top_level_generation = require_int(raw, "action_flow_generation", path, "policy")
    require_nullable_str_key_present(raw, "effective_from", path, "policy")
    require_nullable_str_key_present(raw, "review_due", path, "policy")

    for key in _AFG_LIST_SCOPE_KEYS:
        _require_explicit_list_str(raw, key, path, "policy")
    global_scope_included = raw.get("global_scope_included")
    if not isinstance(global_scope_included, bool):
        raise VenuePolicyConfigError(
            f"{path}: policy.global_scope_included must be a bool"
        )

    (
        model_view_generation,
        policy_version,
        governed_dimensions,
        governed_scopes,
        governed_action_classes,
        bundle_member_kind,
        signer_identity,
        approval_identity,
        evidence_package_ref,
    ) = _parse_afg_model_view(raw, path, top_level_generation=top_level_generation)

    runtime_raw = require_mapping_key(raw, "_runtime", path)
    flow_dimension_id, limits, scope_independence, side_tokens = (
        _parse_afg_runtime_core(
            runtime_raw,
            path,
            governed_dimensions=governed_dimensions,
            governed_scopes=governed_scopes,
        )
    )

    covered_scopes, required_scopes, applicable_tokens = _parse_afg_runtime_scope_sets(
        runtime_raw, path
    )

    action_class_map = _parse_action_class_map(
        runtime_raw, path, governed_action_classes=governed_action_classes
    )
    deployment_facts = _parse_deployment_facts(runtime_raw, path)

    require_template_shape(
        raw,
        path,
        list_keys=_AFG_TEMPLATE_LIST_KEYS,
        mapping_keys=_RISK_TEMPLATE_MAPPING_KEYS,
    )

    policy = ActionFlowPolicy.issue(
        scheme=scheme,
        policy_id=policy_id,
        policy_generation=model_view_generation,
        policy_version=policy_version,
        governed_dimensions=governed_dimensions,
        governed_scopes=governed_scopes,
        governed_action_classes=governed_action_classes,
        bundle_member_kind=bundle_member_kind,
        signer_identity=signer_identity,
        approval_identity=approval_identity,
        evidence_package_ref=evidence_package_ref,
    )
    assert isinstance(policy, ActionFlowPolicy)
    check_canonical_digest(raw, path, policy.canonical_digest, "policy")

    return LoadedActionFlowPolicy(
        policy=policy,
        flow_dimension_id=flow_dimension_id,
        limits=limits,
        scope_independence=scope_independence,
        covered_scopes=covered_scopes,
        required_scopes=required_scopes,
        applicable_action_flow_scopes=applicable_tokens,
        action_class_map=action_class_map,
        deployment_facts=deployment_facts,
        side_tokens=side_tokens,
    )
