"""``tos_runtime.riskstate._aggregate_risk_policy_loader`` — the Aggregate Risk Policy"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos.are import (
    AdverseScenarioKind,
    AggregateRiskPolicy,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityComponent, CapacityVector

from tos_runtime.riskstate._riskstate_primitives import (
    RISK_TEMPLATE_MAPPING_KEYS,
    require_explicit_list_str,
    require_nonnegative_decimal,
)
from tos_runtime.venue._policy_primitives import (
    ACCEPTED_SCHEMA_VERSION,
    VenuePolicyConfigError,
    check_canonical_digest,
    load_mapping,
    optional_str,
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
    "AGGREGATE_RISK_POLICY_CONFIG_NAME",
    "LoadedAggregateRiskPolicy",
    "load_aggregate_risk_policy",
]

AGGREGATE_RISK_POLICY_CONFIG_NAME = "aggregate_risk_policy.yaml"

_ARE_ARTIFACT_TYPE = "AGGREGATE_RISK_POLICY"

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

_ARE_SINGLETON_SCOPE_KEYS: tuple[str, ...] = ("instrument_scope", "account_scope")
_ARE_LIST_SCOPE_KEYS: tuple[str, ...] = (
    "environment_scope",
    "safety_cell_scope",
    "legal_portfolio_scope",
    "strategy_scope",
    "venue_scope",
    "currency_scope",
)


def _require_singleton_scope(raw: Mapping[str, Any], key: str, path: Path) -> str:
    """Like :func:`tos_runtime.venue._policy_primitives.require_singleton_list_str`, but for a"""
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


@dataclass(frozen=True)
class LoadedAggregateRiskPolicy:
    """A loaded, kernel-issued Aggregate Risk Policy plus its ``_runtime`` derived facts"""

    policy: AggregateRiskPolicy
    dimension_ids: Mapping[tuple[RiskScopeKind, RiskDimensionKind], str]
    effective_limits: CapacityVector
    envelope_max: CapacityVector
    required_scenario_kinds: frozenset[AdverseScenarioKind]
    required_scopes: frozenset[RiskScopeKind]
    applicable_risk_scopes: tuple[str, ...]
    unit: str
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
    policy_version = require_filled_str(mv_raw, "policy_version", path, "_model_view")
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
    signer_identity = optional_str(mv_raw, "signer_identity", path, "_model_view")
    approval_identity = optional_str(mv_raw, "approval_identity", path, "_model_view")
    evidence_package_ref = optional_str(
        mv_raw, "evidence_package_ref", path, "_model_view"
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
        magnitude = require_nonnegative_decimal(
            value, path, f"_runtime.effective_limits[{dimension_id!r}]"
        )
        components.append(
            CapacityComponent(dimension_id=dimension_id, magnitude=magnitude, unit=unit)
        )
    return CapacityVector(components=tuple(components))


def _parse_are_envelope_max(
    runtime_raw: dict[str, Any],
    path: Path,
    *,
    dimension_ids: dict[tuple[RiskScopeKind, RiskDimensionKind], str],
    unit: str,
) -> CapacityVector:
    """``_runtime.envelope_max`` — step 6's ``injected_envelope_max`` ceiling (module"""
    envelope_raw = require_mapping_key(runtime_raw, "envelope_max", path)
    known_ids = frozenset(dimension_ids.values())
    components: list[CapacityComponent] = []
    for dimension_id, value in envelope_raw.items():
        if dimension_id not in known_ids:
            raise VenuePolicyConfigError(
                f"{path}: _runtime.envelope_max key {dimension_id!r} is not among "
                f"_runtime.dimension_ids' own values {sorted(known_ids)!r}"
            )
        magnitude = require_nonnegative_decimal(
            value, path, f"_runtime.envelope_max[{dimension_id!r}]"
        )
        components.append(
            CapacityComponent(dimension_id=dimension_id, magnitude=magnitude, unit=unit)
        )
    missing = sorted(known_ids - frozenset(envelope_raw))
    if missing:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.envelope_max declares no ceiling for governed dimension "
            f"id(s) {missing!r} — every ARE-governed dimension must have a real envelope "
            "ceiling"
        )
    return CapacityVector(components=tuple(components))


def _parse_are_runtime_sets(
    runtime_raw: dict[str, Any], path: Path
) -> tuple[frozenset[AdverseScenarioKind], frozenset[RiskScopeKind], tuple[str, ...]]:
    """The three ``_runtime`` token-set fields ``required_scenario_kinds``/"""
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
    """The two singleton scope strings + the list-scope/``global_scope_included`` presence"""
    singleton_scopes = {
        key: _require_singleton_scope(raw, key, path)
        for key in _ARE_SINGLETON_SCOPE_KEYS
    }
    for key in _ARE_LIST_SCOPE_KEYS:
        require_explicit_list_str(raw, key, path, "policy")
    if not isinstance(raw.get("global_scope_included"), bool):
        raise VenuePolicyConfigError(
            f"{path}: policy.global_scope_included must be a bool"
        )
    return singleton_scopes


def load_aggregate_risk_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedAggregateRiskPolicy:
    """Load, fail-closed-validate, and kernel-issue an Aggregate Risk Policy INSTANCE document"""
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
    unit = require_filled_str(runtime_raw, "unit", path, "_runtime")
    dimension_ids = _parse_are_dimension_ids(
        runtime_raw,
        path,
        governed_dimensions=governed_dimensions,
        governed_scopes=governed_scopes,
    )
    effective_limits = _parse_are_effective_limits(
        runtime_raw, path, dimension_ids=dimension_ids, unit=unit
    )
    envelope_max = _parse_are_envelope_max(
        runtime_raw, path, dimension_ids=dimension_ids, unit=unit
    )
    required_scenario_kinds, required_scopes, applicable_tokens = (
        _parse_are_runtime_sets(runtime_raw, path)
    )

    require_template_shape(
        raw,
        path,
        list_keys=_ARE_TEMPLATE_LIST_KEYS,
        mapping_keys=RISK_TEMPLATE_MAPPING_KEYS,
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
        envelope_max=envelope_max,
        required_scenario_kinds=required_scenario_kinds,
        required_scopes=required_scopes,
        applicable_risk_scopes=applicable_tokens,
        unit=unit,
        instrument_scope=singleton_scopes["instrument_scope"],
        account_scope=singleton_scopes["account_scope"],
    )
