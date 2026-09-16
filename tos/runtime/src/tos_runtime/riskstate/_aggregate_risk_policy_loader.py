"""``tos_runtime.riskstate._aggregate_risk_policy_loader`` — the Aggregate Risk Policy
INSTANCE document loader (TOS risk state service wave, plan §2.1/§4.1; DR-0003 §2.1 — "An
Aggregate Risk Policy instance ... follows DR-0002 §2.1 and §2.2 verbatim").

Split out of :mod:`tos_runtime.riskstate.policies` (team-lead disposition 2026-09-16, review
of PR #704 item T1) — that module is now a thin re-export shim, mirroring
:mod:`tos_runtime.venue.config`'s own split into ``_venue_policy_loader.py`` /
``_order_construction_policy_loader.py``; no behavioural difference from having this inline
in ``policies.py``. See ``policies.py``'s own module docstring for the shared DR-0002
``_model_view``/``_runtime`` discipline both this loader and its Action Flow Policy sibling
(:mod:`tos_runtime.riskstate._action_flow_policy_loader`) follow.

**Kernel field shape actually measured.**
``tos.are.records.AggregateRiskPolicy.governed_dimensions`` is a bare
``tuple[RiskDimensionKind, ...]`` (dimension TOKENS, not descriptor objects) —
``tos/src/tos/are/records.py:345``.

**Dimension-id convention (plan §0 survey "픽스처 관용구", reused not invented).** Dimension
ids are ``f"{scope}::{dimension}"`` (matching ``tos_runtime/tests/compose/conftest.py``'s own
``safety_envelope.yaml`` convention this loader's ``_runtime.dimension_ids`` keys are
cross-checked against) — the loader REQUIRES each ``_runtime.dimension_ids`` YAML key to
equal exactly ``f"{scope}::{dimension}"`` for its own nested ``scope``/``dimension`` pair
(fail-closed on drift, never a silently-accepted arbitrary key).

**What this module does NOT do (lane a boundary, plan §4.1).** It issues neither policy
against a Hard Safety Envelope — the ``injected_envelope_max``/HSE dimension cross-check
(plan §2.1) is a LANE B wiring-time responsibility (:mod:`tos_runtime.compose
._riskstate_wiring`), run once both this policy AND the HSE are loaded; this loader has no
HSE input and performs no such check. It does not activate the policy
(``tos_runtime.venue.activation.require_member_activated`` is lane b's job).

Firewall (R1, runtime scope): stdlib + ``pyyaml`` (transitively, via the reused primitives) +
``tos.*`` + ``tos_runtime.venue._policy_primitives`` + ``tos_runtime.riskstate
._riskstate_primitives`` only — no ``shared.*``, no
``os.environ``/``subprocess``/``importlib.import_module`` (``tools/tos_firewall_check.py``
scans tests too).
"""

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

#: The runtime INSTANCE file name (distinct from the tos-spec TEMPLATE file name).
AGGREGATE_RISK_POLICY_CONFIG_NAME = "aggregate_risk_policy.yaml"

_ARE_ARTIFACT_TYPE = "AGGREGATE_RISK_POLICY"

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
        magnitude = require_nonnegative_decimal(
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
        require_explicit_list_str(raw, key, path, "policy")
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
        required_scenario_kinds=required_scenario_kinds,
        required_scopes=required_scopes,
        applicable_risk_scopes=applicable_tokens,
        unit=unit,
        instrument_scope=singleton_scopes["instrument_scope"],
        account_scope=singleton_scopes["account_scope"],
    )
