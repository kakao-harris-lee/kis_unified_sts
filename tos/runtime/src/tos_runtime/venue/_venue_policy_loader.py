"""tos_runtime.venue._venue_policy_loader — the Venue Constraint Policy half
of ``tos_runtime.venue.config`` (split out purely for that module's own size
budget — ``config/tos_size_budget.yaml``, module ceiling 1000 lines; no
behavioural difference from having this inline there).

See :mod:`tos_runtime.venue.config`'s own module docstring for the full
``_model_view``/``_runtime`` discipline, the single-live-scope rule, the
``canonical_digest`` tamper/stale cross-check, and the scope/admission
cross-check this module implements for the Venue Constraint Policy INSTANCE
document specifically.

Firewall (R1, runtime scope): stdlib + ``tos.*`` only — no ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from tos.canonical import CanonicalizationScheme
from tos.egressgw import VenueQuantityConstraint
from tos.ioc import QuantityUnitKind
from tos.venue import (
    ActionClass,
    ActionPhaseAdmission,
    ConstraintClass,
    ConstraintDependencyClosure,
    DependencyEdge,
    VenueConstraintPolicy,
    VenueShapeConstraints,
)

from tos_runtime.venue._policy_primitives import (
    ACCEPTED_SCHEMA_VERSION,
    TBD_STR,
    TEMPLATE_MAPPING_KEYS,
    VenuePolicyConfigError,
    check_canonical_digest,
    load_mapping,
    parse_action_classes,
    require_exact_str,
    require_filled_str,
    require_int,
    require_issued_status,
    require_list,
    require_mapping_key,
    require_nullable_str_key_present,
    require_singleton_list_str,
    require_str,
    require_str_list,
    require_template_shape,
)

__all__ = [
    "VENUE_POLICY_CONFIG_NAME",
    "VenuePolicyScope",
    "LoadedVenuePolicy",
    "load_venue_constraint_policy",
]

#: The runtime INSTANCE file name (distinct from the tos-spec TEMPLATE file
#: name — this is what an environment's config directory actually carries).
VENUE_POLICY_CONFIG_NAME = "venue_constraint_policy.yaml"

_VENUE_ARTIFACT_TYPE = "VENUE_CONSTRAINT_POLICY"

#: ``shape_constraints`` bounds honestly allowed to be ``null`` (config.py's
#: own module docstring — "no source" is passed straight through to the
#: kernel, never a fabricated bound).
_NULLABLE_SHAPE_BOUNDS: tuple[str, ...] = (
    "price_min",
    "price_max",
    "tick_size",
    "lot_size",
    "min_quantity",
    "max_quantity",
)

#: The four ``shape_constraints`` allowed-set keys — explicit list, ``[]`` accepted.
_SHAPE_ALLOWED_SET_KEYS: tuple[str, ...] = (
    "allowed_order_types",
    "allowed_tifs",
    "allowed_sides",
    "allowed_position_effects",
)

#: The VENUE-CONSTRAINT-POLICY-template.yaml top-level rule-list keys this loader
#: only checks for presence/shape (list-typed) — content unread, uninterpreted.
#: Order matches the template file.
_VENUE_TEMPLATE_LIST_KEYS: tuple[str, ...] = (
    "approved_sources",
    "source_continuity_rules",
    "session_phase_state_machines",
    "halt_suspension_and_tradability_rules",
    "instrument_and_contract_rules",
    "price_band_tick_and_lot_rules",
    "quantity_notional_and_rounding_rules",
    "order_type_time_in_force_and_routing_rules",
    "account_permission_rules",
    "margin_collateral_and_buying_power_rules",
    "borrow_locate_and_short_sale_rules",
    "settlement_currency_and_expiration_rules",
    "broker_capability_requirements",
    "corroboration_and_independence_rules",
    "dependency_and_invalidation_rules",
    "conservative_failure_responses",
    "protective_only_restrictions",
    "residual_risks",
    "approved_by",
)

#: The venue-policy ``scope`` block's single-live-scope (exactly one entry)
#: list keys.
_VENUE_SCOPE_SINGLETON_KEYS: tuple[str, ...] = (
    "environments",
    "brokers",
    "accounts",
    "venues",
    "market_segments",
    "instruments",
)

#: Maps each singleton scope key to the ``_parse_venue_scope`` return-tuple
#: position it fills — in ``_VENUE_SCOPE_SINGLETON_KEYS`` order.
_VENUE_SCOPE_SINGLETON_FIELD_NAMES: tuple[str, ...] = (
    "environment",
    "broker",
    "account",
    "venue",
    "market_segment",
    "instrument",
)

#: The venue-policy ``scope`` block's remaining explicit-list keys (any length).
_VENUE_SCOPE_LIST_KEYS: tuple[str, ...] = ("safety_cells", "contracts")


@dataclass(frozen=True)
class VenuePolicyScope:
    """The structured venue policy scope (plan §4.1, corrected field set —
    team-lead review 2026-09-15: the template's ``scope`` block declares NO
    product coordinate at all — ``environments``/``safety_cells``/
    ``brokers``/``accounts``/``venues``/``market_segments``/``instruments``/
    ``contracts``/``action_classes`` is the complete plural-list key set —
    so a ``product_type`` field on this dataclass would carry a fact the
    template has no slot for. ``instrument`` + ``market_segment`` carry that
    distinction instead (an instrument id is already product-specific within
    its market segment); this dataclass deliberately has no separate
    ``product_type`` field.

    Kept alongside the kernel's flattened ``VenueConstraintPolicy.scope``
    string (produced by :func:`_scope_identity` — the six single-entry
    coordinates joined in template-declaration order, ``environment``/
    ``broker``/``account``/``venue``/``market_segment``/``instrument``) so a
    later cross-check (plan §2 decision 5, lane b) can compare
    ``environment``/``account``/``instrument``/``instrument_class`` against
    compose's own configured coordinates without re-parsing the composed
    string.
    """

    environment: str
    broker: str
    account: str
    venue: str
    market_segment: str
    instrument: str
    instrument_class: str
    currency: str | None
    quantity_unit: QuantityUnitKind


@dataclass(frozen=True)
class LoadedVenuePolicy:
    """A loaded, kernel-issued Venue Constraint Policy plus its structured
    scope and its derived quantity constraint (plan §4.1)."""

    policy: VenueConstraintPolicy
    scope: VenuePolicyScope
    quantity_constraint: VenueQuantityConstraint
    null_shape_bounds: tuple[str, ...]


def _as_decimal(value: int | None) -> Decimal | None:
    """``VenueShapeConstraints``'s numeric bounds are plain ``int`` (venue is
    the kernel's own opaque-scaled-int convention, ``tos.venue.records``),
    while ``VenueQuantityConstraint`` (egressgw) carries them as
    ``CanonicalDecimal``. ``Decimal(int)`` is always exact — no precision
    loss — so this is a type-coordinate bridge, never a rounding."""
    return None if value is None else Decimal(value)


def _parse_venue_scope(
    raw: dict[str, Any], path: Path
) -> tuple[str, str, str, str, str, str, frozenset[ActionClass]]:
    scope_raw = require_mapping_key(raw, "scope", path)
    singletons = {
        field_name: require_singleton_list_str(scope_raw, key, path, "scope")
        for key, field_name in zip(
            _VENUE_SCOPE_SINGLETON_KEYS, _VENUE_SCOPE_SINGLETON_FIELD_NAMES, strict=True
        )
    }
    for key in _VENUE_SCOPE_LIST_KEYS:
        entries = require_list(scope_raw, key, path, "scope")
        require_str_list(entries, path, f"scope.{key}")
    action_classes = parse_action_classes(scope_raw, path, "scope")
    return (
        singletons["environment"],
        singletons["broker"],
        singletons["account"],
        singletons["venue"],
        singletons["market_segment"],
        singletons["instrument"],
        action_classes,
    )


def _scope_identity(scope: VenuePolicyScope) -> str:
    """The composed scope identity string the kernel ``VenueConstraintPolicy
    .scope`` field carries — the six single-live-scope coordinates, in the
    order the template lists them (``environments``/``brokers``/
    ``accounts``/``venues``/``market_segments``/``instruments``)."""
    return "/".join(
        (
            scope.environment,
            scope.broker,
            scope.account,
            scope.venue,
            scope.market_segment,
            scope.instrument,
        )
    )


def _parse_venue_runtime_block(
    raw: dict[str, Any], path: Path
) -> tuple[str, QuantityUnitKind, str | None]:
    runtime_raw = require_mapping_key(raw, "_runtime", path)
    instrument_class = require_str(runtime_raw, "instrument_class", path, "_runtime")
    unit_token = require_str(runtime_raw, "quantity_unit", path, "_runtime")
    try:
        quantity_unit = QuantityUnitKind(unit_token)
    except ValueError as exc:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.quantity_unit {unit_token!r} is not a known QuantityUnitKind"
        ) from exc
    currency = runtime_raw.get("currency")
    if currency is not None and not isinstance(currency, str):
        raise VenuePolicyConfigError(
            f"{path}: _runtime.currency must be a string or null"
        )
    return instrument_class, quantity_unit, currency


def _parse_admitting_phase_rules(
    raw: dict[str, Any], path: Path
) -> tuple[ActionPhaseAdmission, ...]:
    entries = require_list(raw, "admitting_phase_rules", path, "_model_view")
    rules = []
    for i, entry in enumerate(entries):
        ctx = f"_model_view.admitting_phase_rules[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        action_token = require_str(entry, "action", path, ctx)
        try:
            action = ActionClass(action_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx} action {action_token!r} is not a known ActionClass"
            ) from exc
        phases = require_list(entry, "admitting_phases", path, ctx)
        phase_strs = require_str_list(phases, path, f"{ctx}.admitting_phases")
        rules.append(
            ActionPhaseAdmission(action=action, admitting_phases=frozenset(phase_strs))
        )
    return tuple(rules)


def _parse_required_constraint_classes(
    raw: dict[str, Any], path: Path
) -> frozenset[ConstraintClass]:
    entries = require_list(raw, "required_constraint_classes", path, "_model_view")
    classes: set[ConstraintClass] = set()
    for token in entries:
        if not isinstance(token, str):
            raise VenuePolicyConfigError(
                f"{path}: _model_view.required_constraint_classes entries must be strings"
            )
        try:
            classes.add(ConstraintClass(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.required_constraint_classes {token!r} is not "
                "a known ConstraintClass"
            ) from exc
    return frozenset(classes)


def _parse_numeric_bounds(
    sc_raw: dict[str, Any], path: Path
) -> tuple[dict[str, int | None], tuple[str, ...]]:
    bounds: dict[str, int | None] = {}
    null_bounds: list[str] = []
    for name in _NULLABLE_SHAPE_BOUNDS:
        if name not in sc_raw:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.shape_constraints missing required key {name!r} "
                "(pass null explicitly if the source is absent)"
            )
        value = sc_raw[name]
        if value is None:
            bounds[name] = None
            null_bounds.append(name)
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            raise VenuePolicyConfigError(
                f"{path}: _model_view.shape_constraints.{name} must be an int or null"
            )
        bounds[name] = value
    return bounds, tuple(null_bounds)


def _parse_shape_constraints(
    raw: dict[str, Any], path: Path
) -> tuple[VenueShapeConstraints, tuple[str, ...]]:
    sc_raw = require_mapping_key(raw, "shape_constraints", path)
    bounds, null_bounds = _parse_numeric_bounds(sc_raw, path)
    allowed_sets: dict[str, frozenset[str]] = {}
    for key in _SHAPE_ALLOWED_SET_KEYS:
        entries = require_list(sc_raw, key, path, "_model_view.shape_constraints")
        allowed_sets[key] = frozenset(
            require_str_list(entries, path, f"_model_view.shape_constraints.{key}")
        )
    constraints = VenueShapeConstraints(
        price_min=bounds["price_min"],
        price_max=bounds["price_max"],
        tick_size=bounds["tick_size"],
        lot_size=bounds["lot_size"],
        min_quantity=bounds["min_quantity"],
        max_quantity=bounds["max_quantity"],
        allowed_order_types=allowed_sets["allowed_order_types"],
        allowed_tifs=allowed_sets["allowed_tifs"],
        allowed_sides=allowed_sets["allowed_sides"],
        allowed_position_effects=allowed_sets["allowed_position_effects"],
    )
    return constraints, null_bounds


def _parse_dependency_closure(
    raw: dict[str, Any], path: Path
) -> ConstraintDependencyClosure:
    dc_raw = require_mapping_key(raw, "dependency_closure", path)
    entries = require_list(dc_raw, "edges", path, "_model_view.dependency_closure")
    edges = []
    for i, entry in enumerate(entries):
        ctx = f"_model_view.dependency_closure.edges[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        node = require_filled_str(entry, "node", path, ctx)
        dependents = require_list(entry, "dependents", path, ctx)
        dependent_strs = require_str_list(dependents, path, f"{ctx}.dependents")
        if TBD_STR in dependent_strs:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.dependents still carries the template placeholder "
                f"{TBD_STR!r} — operator-fill before activation"
            )
        edges.append(DependencyEdge(node=node, dependents=frozenset(dependent_strs)))
    return ConstraintDependencyClosure(edges=tuple(edges))


def _cross_check_admitting_actions_in_scope(
    admitting_phase_rules: tuple[ActionPhaseAdmission, ...],
    scope_action_classes: frozenset[ActionClass],
    path: Path,
) -> None:
    for rule in admitting_phase_rules:
        if rule.action is not None and rule.action not in scope_action_classes:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.admitting_phase_rules declares action "
                f"{rule.action!r} which is not in scope.action_classes "
                f"{sorted(a.value for a in scope_action_classes)!r} — a policy "
                "may not admit an action outside its own declared scope"
            )


def load_venue_constraint_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedVenuePolicy:
    """Load, fail-closed-validate, and kernel-issue a Venue Constraint Policy
    INSTANCE document from ``path`` (an instance of
    ``VENUE-CONSTRAINT-POLICY-template.yaml`` — see
    :mod:`tos_runtime.venue.config`'s own module docstring).

    Raises:
        VenuePolicyConfigError: the file is missing/unreadable/not valid
            YAML/not a mapping; ``artifact_type``/``schema_version`` do not
            match the accepted constants; ``status`` is not ``ISSUED``;
            ``policy_id``/``policy_generation`` are absent, ``null``, or
            still ``"TBD"``; ``canonical_digest`` is present but does not
            match the freshly computed digest; any ``scope`` singleton key
            does not carry exactly one string; an ``action_classes`` /
            ``_model_view`` action token is not a known ``ActionClass``; an
            admitting-phase-rules action is outside the declared scope; a
            ``_model_view``/``_runtime`` block is absent; ``_runtime
            .quantity_unit`` is not a known ``QuantityUnitKind``;
            ``effective_from``/``review_due`` is absent (may be ``null``, but
            the key itself must be present) or present-and-not-``null``-and-
            not-a-string; or any template rule-list/``authority``/
            ``evidence`` key is absent or not list/mapping-shaped.
    """
    raw = load_mapping(path, "venue constraint policy")
    require_exact_str(raw, "artifact_type", _VENUE_ARTIFACT_TYPE, path, "policy")
    require_exact_str(raw, "schema_version", ACCEPTED_SCHEMA_VERSION, path, "policy")
    require_issued_status(raw, path)
    policy_id = require_filled_str(raw, "policy_id", path, "policy")
    policy_generation = require_int(raw, "policy_generation", path, "policy")
    require_nullable_str_key_present(raw, "effective_from", path, "policy")
    require_nullable_str_key_present(raw, "review_due", path, "policy")

    (
        environment,
        broker,
        account,
        venue,
        market_segment,
        instrument,
        scope_action_classes,
    ) = _parse_venue_scope(raw, path)
    instrument_class, quantity_unit, currency = _parse_venue_runtime_block(raw, path)
    scope = VenuePolicyScope(
        environment=environment,
        broker=broker,
        account=account,
        venue=venue,
        market_segment=market_segment,
        instrument=instrument,
        instrument_class=instrument_class,
        currency=currency,
        quantity_unit=quantity_unit,
    )

    mv_raw = require_mapping_key(raw, "_model_view", path)
    admitting_phase_rules = _parse_admitting_phase_rules(mv_raw, path)
    required_constraint_classes = _parse_required_constraint_classes(mv_raw, path)
    shape_constraints, null_bounds = _parse_shape_constraints(mv_raw, path)
    dependency_closure = _parse_dependency_closure(mv_raw, path)
    _cross_check_admitting_actions_in_scope(
        admitting_phase_rules, scope_action_classes, path
    )

    require_template_shape(
        raw,
        path,
        list_keys=_VENUE_TEMPLATE_LIST_KEYS,
        mapping_keys=TEMPLATE_MAPPING_KEYS,
    )

    policy = VenueConstraintPolicy.issue(
        scheme=scheme,
        policy_id=policy_id,
        policy_generation=policy_generation,
        scope=_scope_identity(scope),
        admitting_phase_rules=admitting_phase_rules,
        required_constraint_classes=required_constraint_classes,
        shape_constraints=shape_constraints,
        dependency_closure=dependency_closure,
    )
    assert isinstance(policy, VenueConstraintPolicy)
    check_canonical_digest(raw, path, policy.canonical_digest, "policy")

    quantity_constraint = VenueQuantityConstraint(
        lot_size=_as_decimal(shape_constraints.lot_size),
        min_quantity=_as_decimal(shape_constraints.min_quantity),
        max_quantity=_as_decimal(shape_constraints.max_quantity),
        quantity_unit=scope.quantity_unit,
    )
    return LoadedVenuePolicy(
        policy=policy,
        scope=scope,
        quantity_constraint=quantity_constraint,
        null_shape_bounds=null_bounds,
    )
