"""``tos_runtime.riskstate._action_flow_policy_loader`` — the Action Flow Policy INSTANCE
document loader (TOS risk state service wave, plan §2.1/§4.1; DR-0003 §2.1).

Split out of :mod:`tos_runtime.riskstate.policies` (team-lead disposition 2026-09-16, review
of PR #704 item T1) — that module is now a thin re-export shim, mirroring
:mod:`tos_runtime.venue.config`'s own split; no behavioural difference from having this
inline in ``policies.py``. See ``policies.py``'s own module docstring for the shared DR-0002
``_model_view``/``_runtime`` discipline both this loader and its Aggregate Risk Policy
sibling (:mod:`tos_runtime.riskstate._aggregate_risk_policy_loader`) follow.

**Kernel field shape actually measured.** ``tos.afg.records.ActionFlowPolicy
._COVERED_FIELDS`` (``tos/src/tos/afg/records.py:394-406``) names ``governed_dimensions``,
``governed_scopes``, ``governed_action_classes``, ``bundle_member_kind`` in addition to the
ARE-shared ``policy_generation``/``policy_version``/``signer_identity``/``approval_identity``
/``evidence_package_ref`` — so this loader's ``_model_view`` carries one more field than its
ARE sibling's.

**``side_tokens`` — lane b addition (plan §4.1 deviation, reported).**
:class:`~tos_runtime.riskstate.position.EvidencePositionReader` needs the two recognized
outbound-side tokens as REQUIRED, non-default constructor arguments (no runtime-authored
literal). Sourced from this SAME governed instance's ``_runtime.side_tokens: {buy, sell}``
mapping rather than a new config surface — cross-checked at wiring time against the venue
policy's own ``allowed_sides`` set (:mod:`tos_runtime.compose._riskstate_wiring`).

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

from tos.afg import (
    ActionClassKind,
    ActionFlowDimensionKind,
    ActionFlowPolicy,
    ActionFlowScopeKind,
    ScopeIndependenceEvidence,
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
    "ACTION_FLOW_POLICY_CONFIG_NAME",
    "DeploymentFlowFacts",
    "LoadedActionFlowPolicy",
    "load_action_flow_policy",
]

#: The runtime INSTANCE file name (distinct from the tos-spec TEMPLATE file name).
ACTION_FLOW_POLICY_CONFIG_NAME = "action_flow_policy.yaml"

_AFG_ARTIFACT_TYPE = "ACTION_FLOW_POLICY"

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

#: The AFG policy's scope-array keys (template order) — all explicit lists. ``account_scope``
#: additionally passes :func:`_require_account_scope_singleton` (exactly one entry, never
#: ``"TBD"``/empty — the same phantom-scope gate the venue/ARE loaders apply; team-lead
#: disposition 2026-09-16, found while landing the real deploy file).
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
    policy_version = require_filled_str(mv_raw, "policy_version", path, "_model_view")
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
    bundle_member_kind = require_filled_str(
        mv_raw, "bundle_member_kind", path, "_model_view"
    )
    # optional_str (W-A A-0 round 2, kernel round #4 K-3 precedent): PRESENT-required,
    # null-or-string, and — unlike the inline check this replaces — also refuses the
    # template's own "TBD" placeholder for these three operator-fill identity fields
    # (the SAME check venue/_order_construction_policy_loader.py's own signer_identity/
    # approval_identity/evidence_package_ref already get).
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
        magnitude = require_nonnegative_decimal(
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


def _require_account_scope_singleton(raw: Mapping[str, Any], path: Path) -> str:
    """``account_scope`` is the ONE deployment coordinate this policy binds (v1 single live
    scope, plan §2.1) and the real deploy file ships it as the operator-fill marker ``["TBD"]``
    (config/tos_runtime/paper/action_flow_policy.yaml) — the same phantom-scope gate the
    venue/ARE loaders apply: exactly one entry, never ``"TBD"``/empty (team-lead disposition
    2026-09-16, found while landing the real file). Split out of :func:`load_action_flow_policy`
    for that function's own 100-line budget."""
    account_entries = require_str_list(
        raw["account_scope"], path, "policy.account_scope"
    )
    if len(account_entries) != 1:
        raise VenuePolicyConfigError(
            f"{path}: policy.account_scope must be a list of EXACTLY one string for a single "
            f"live scope (v1, plan §2.1) — got {len(account_entries)}"
        )
    if account_entries[0] == "TBD" or not account_entries[0].strip():
        raise VenuePolicyConfigError(
            f"{path}: policy.account_scope is still 'TBD'/empty (named-TBD) — fill the "
            "deployment coordinate before activation"
        )
    return account_entries[0]


def load_action_flow_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedActionFlowPolicy:
    """Load, fail-closed-validate, and kernel-issue an Action Flow Policy INSTANCE document
    from ``path`` (an instance of ``ACTION-FLOW-POLICY-template.yaml`` — see this module's own
    docstring).

    Raises:
        VenuePolicyConfigError: the same class of refusal :func:`~tos_runtime.riskstate
            ._aggregate_risk_policy_loader.load_aggregate_risk_policy` raises, plus: a
            ``_runtime.limits`` key is missing or not a non-negative decimal; a
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
        require_explicit_list_str(raw, key, path, "policy")
    _require_account_scope_singleton(raw, path)
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
        mapping_keys=RISK_TEMPLATE_MAPPING_KEYS,
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
