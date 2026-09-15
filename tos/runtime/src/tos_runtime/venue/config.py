"""tos_runtime.venue.config — Venue Constraint Policy / Order Construction Policy loaders.

TOS venue constraint service wave, plan §2 decisions 1/2/6, §4.1
(``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``).

Venue is a governance-authored, activation-gated CONTENT artifact
(ADR-002-019 §5.1/§8; ADR-002-020 §5.2/§9) — this module is the loader half
of "policy = governance document" (plan §2 decision 1): it reads two YAML
documents and issues the two kernel policy artifacts through their own
``.issue(scheme, ...)`` constructors, so the returned ``canonical_digest`` is
a REAL kernel digest, never a runtime-invented string. It judges no
admissibility itself — ``tos.venue.state.session_phase_admits`` /
``tos.venue.predicates.order_shape_admissible`` (via
``tos.egressgw.construction.fold_venue_admissibility``) are the sole judges,
exercised only in :mod:`tos_runtime.venue.service`.

Fail-closed discipline (mirrors :mod:`tos_runtime.calendar.config`'s own
module docstring, the idiom this module copies): a missing file, a
non-mapping top level, a missing required key, or a required scalar left
``null`` (named-TBD) all refuse to load — never a silent default. The four
``allowed_*`` shape-constraint lists, ``admitting_phase_rules``,
``required_constraint_classes``, and ``dependency_closure.edges`` must each
be an EXPLICIT list (``[]`` accepted as a deliberate "none declared"; a
missing key or ``null`` is refused as still-TBD).

**Deliberate exception — six numeric ``shape_constraints`` bounds.**
``price_min``/``price_max``/``tick_size``/``lot_size``/``min_quantity``/
``max_quantity`` MAY be ``null`` = "no source" (plan §2 decision 2; ADR-002-019
§9: "None alone proves current admissibility unless the active policy
explicitly defines the fact"). A ``null`` bound is passed straight through to
the kernel's ``VenueShapeConstraints`` — ``order_shape_admissible`` already
returns ``UNKNOWN`` on a ``None`` bound
(``tos/src/tos/venue/predicates.py::order_shape_admissible``), which is the
honest semantics for a constraint the operator has not yet sourced. Each
null bound's field name is recorded on
:attr:`LoadedVenuePolicy.null_shape_bounds` so a caller (the boot-time
``VENUE_POLICY_BOUND`` evidence row, :mod:`tos_runtime.venue.service`) can
disclose exactly which facts are absent, never silently.

``OrderConstructionPolicy`` is issued with ``signer_identity``/
``approval_identity``/``evidence_package_ref`` all ``None`` — DELIBERATE, not
a gap: the kernel's own ``construct_candidate_command``
(``tos/src/tos/egressgw/construction.py``) issues its own
``OrderConstructionPolicy`` from the SAME three coordinates
(``policy_id``/``policy_generation``/``policy_version``) with those same
three fields ``None`` too, so a loader that filled them would diverge from
the kernel's own issuance and manufacture a ``classify_record_pair``
``CRITICAL_CONFLICT`` — "same id, different bytes" — exactly the forgery
shape the kernel's independent-id discipline exists to catch (plan §2
decision 6). Filling those three fields for real is deferred to a kernel
signature change (plan §6 decision 4, "커널 라운드 #4 후보").

Firewall (R1, runtime scope): stdlib + ``pyyaml`` + ``tos.*`` only — no
``shared.*``, no ``os.environ``, no ``subprocess``, no
``importlib.import_module`` (``tools/tos_firewall_check.py`` scans tests
too).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import CanonicalizationScheme
from tos.egressgw import VenueQuantityConstraint
from tos.ioc import OrderConstructionPolicy, QuantityUnitKind
from tos.venue import (
    ActionClass,
    ActionPhaseAdmission,
    ConstraintClass,
    ConstraintDependencyClosure,
    DependencyEdge,
    VenueConstraintPolicy,
    VenueShapeConstraints,
)

__all__ = [
    "VENUE_POLICY_CONFIG_NAME",
    "ORDER_CONSTRUCTION_POLICY_CONFIG_NAME",
    "VenuePolicyConfigError",
    "VenuePolicyScope",
    "LoadedVenuePolicy",
    "load_venue_constraint_policy",
    "LoadedOrderConstructionPolicy",
    "load_order_construction_policy",
]

VENUE_POLICY_CONFIG_NAME = "venue_constraint_policy.yaml"
ORDER_CONSTRUCTION_POLICY_CONFIG_NAME = "order_construction_policy.yaml"

#: ``shape_constraints`` bounds honestly allowed to be ``null`` (module docstring).
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

#: The eight required (non-nullable) ``scope`` scalar fields — ``currency`` is
#: the one nullable scope scalar and is handled separately.
_SCOPE_SCALAR_FIELDS: tuple[str, ...] = (
    "environment",
    "broker",
    "account",
    "venue",
    "market_segment",
    "product_type",
    "instrument",
    "instrument_class",
)


class VenuePolicyConfigError(RuntimeError):
    """A venue / order-construction policy YAML is missing, malformed, carries
    an unfilled (named-TBD) required field, an unknown ``ActionClass`` /
    ``ConstraintClass`` / ``QuantityUnitKind`` token, or (for the Order
    Construction Policy) a ``canonicalization_version`` that does not match
    the injected compose scheme — fail-closed at load, never a silent
    default (module docstring)."""


@dataclass(frozen=True)
class VenuePolicyScope:
    """The structured venue policy scope (plan §4.1).

    Kept alongside the kernel's flattened ``VenueConstraintPolicy.scope``
    string (produced by :func:`_scope_identity`) so a later cross-check
    (plan §2 decision 5, lane b) can compare ``environment``/``account``/
    ``instrument``/``instrument_class`` against compose's own configured
    coordinates without re-parsing the composed string.
    """

    environment: str
    broker: str
    account: str
    venue: str
    market_segment: str
    product_type: str
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


@dataclass(frozen=True)
class LoadedOrderConstructionPolicy:
    """A loaded, kernel-issued Order Construction Policy plus its wire-codec
    declaration (plan §4.1)."""

    policy: OrderConstructionPolicy
    canonicalization_version: str
    wire_codec_kind: str | None
    wire_fields: frozenset[str]


# ===========================================================================
# shared YAML primitives (mirrors tos_runtime.calendar.config's own idiom)
# ===========================================================================


def _load_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise VenuePolicyConfigError(f"{label} config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VenuePolicyConfigError(
            f"{label} config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise VenuePolicyConfigError(
            f"{label} config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise VenuePolicyConfigError(
            f"{path}: {label} config must be a top-level mapping"
        )
    return raw


def _require_str(raw: dict[str, Any], key: str, path: Path, ctx: str) -> str:
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still null (named-TBD) or not a non-empty string"
        )
    return value


def _require_int(raw: dict[str, Any], key: str, path: Path, ctx: str) -> int:
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still null (named-TBD) or not an int"
        )
    return value


def _require_list(raw: dict[str, Any], key: str, path: Path, ctx: str) -> list[Any]:
    if key not in raw or raw[key] is None:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} must be an explicit list ([] accepted; "
            "a missing key or null is a named-TBD gap)"
        )
    value = raw[key]
    if not isinstance(value, list):
        raise VenuePolicyConfigError(f"{path}: {ctx} {key!r} must be a list")
    return value


def _require_mapping_key(raw: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise VenuePolicyConfigError(f"{path}: {key!r} must be an explicit mapping")
    return value


def _as_decimal(value: int | None) -> Decimal | None:
    """``VenueShapeConstraints``'s numeric bounds are plain ``int`` (venue is
    the kernel's own opaque-scaled-int convention, ``tos.venue.records``),
    while ``VenueQuantityConstraint`` (egressgw) carries them as
    ``CanonicalDecimal``. ``Decimal(int)`` is always exact — no precision
    loss — so this is a type-coordinate bridge, never a rounding."""
    return None if value is None else Decimal(value)


def _require_str_list(entries: list[Any], path: Path, ctx: str) -> tuple[str, ...]:
    for entry in entries:
        if not isinstance(entry, str):
            raise VenuePolicyConfigError(f"{path}: {ctx} entries must be strings")
    return tuple(entries)


# ===========================================================================
# venue_constraint_policy.yaml
# ===========================================================================


def _parse_scope(raw: dict[str, Any], path: Path) -> VenuePolicyScope:
    scope_raw = _require_mapping_key(raw, "scope", path)
    scalars = {
        field: _require_str(scope_raw, field, path, f"scope.{field}")
        for field in _SCOPE_SCALAR_FIELDS
    }
    currency = scope_raw.get("currency")
    if currency is not None and not isinstance(currency, str):
        raise VenuePolicyConfigError(f"{path}: scope.currency must be a string or null")
    unit_token = _require_str(scope_raw, "quantity_unit", path, "scope.quantity_unit")
    try:
        quantity_unit = QuantityUnitKind(unit_token)
    except ValueError as exc:
        raise VenuePolicyConfigError(
            f"{path}: scope.quantity_unit {unit_token!r} is not a known QuantityUnitKind"
        ) from exc
    return VenuePolicyScope(
        environment=scalars["environment"],
        broker=scalars["broker"],
        account=scalars["account"],
        venue=scalars["venue"],
        market_segment=scalars["market_segment"],
        product_type=scalars["product_type"],
        instrument=scalars["instrument"],
        instrument_class=scalars["instrument_class"],
        currency=currency,
        quantity_unit=quantity_unit,
    )


def _scope_identity(scope: VenuePolicyScope) -> str:
    """The composed scope identity string the kernel ``VenueConstraintPolicy
    .scope`` field carries (plan §4.1: "a single scope identity string
    composed deterministically from the scope block, e.g.
    'env/broker/account/venue/segment/product/instrument'")."""
    return "/".join(
        (
            scope.environment,
            scope.broker,
            scope.account,
            scope.venue,
            scope.market_segment,
            scope.product_type,
            scope.instrument,
        )
    )


def _parse_admitting_phase_rules(
    raw: dict[str, Any], path: Path
) -> tuple[ActionPhaseAdmission, ...]:
    entries = _require_list(raw, "admitting_phase_rules", path, "policy")
    rules = []
    for i, entry in enumerate(entries):
        ctx = f"admitting_phase_rules[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        action_token = _require_str(entry, "action", path, ctx)
        try:
            action = ActionClass(action_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx} action {action_token!r} is not a known ActionClass"
            ) from exc
        phases = _require_list(entry, "admitting_phases", path, ctx)
        phase_strs = _require_str_list(phases, path, f"{ctx}.admitting_phases")
        rules.append(
            ActionPhaseAdmission(action=action, admitting_phases=frozenset(phase_strs))
        )
    return tuple(rules)


def _parse_required_constraint_classes(
    raw: dict[str, Any], path: Path
) -> frozenset[ConstraintClass]:
    entries = _require_list(raw, "required_constraint_classes", path, "policy")
    classes: set[ConstraintClass] = set()
    for token in entries:
        if not isinstance(token, str):
            raise VenuePolicyConfigError(
                f"{path}: required_constraint_classes entries must be strings"
            )
        try:
            classes.add(ConstraintClass(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: required_constraint_classes {token!r} is not a known ConstraintClass"
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
                f"{path}: shape_constraints missing required key {name!r} "
                "(pass null explicitly if the source is absent)"
            )
        value = sc_raw[name]
        if value is None:
            bounds[name] = None
            null_bounds.append(name)
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            raise VenuePolicyConfigError(
                f"{path}: shape_constraints.{name} must be an int or null"
            )
        bounds[name] = value
    return bounds, tuple(null_bounds)


def _parse_shape_constraints(
    raw: dict[str, Any], path: Path
) -> tuple[VenueShapeConstraints, tuple[str, ...]]:
    sc_raw = _require_mapping_key(raw, "shape_constraints", path)
    bounds, null_bounds = _parse_numeric_bounds(sc_raw, path)
    allowed_sets: dict[str, frozenset[str]] = {}
    for key in _SHAPE_ALLOWED_SET_KEYS:
        entries = _require_list(sc_raw, key, path, "shape_constraints")
        allowed_sets[key] = frozenset(
            _require_str_list(entries, path, f"shape_constraints.{key}")
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
    dc_raw = _require_mapping_key(raw, "dependency_closure", path)
    entries = _require_list(dc_raw, "edges", path, "dependency_closure")
    edges = []
    for i, entry in enumerate(entries):
        ctx = f"dependency_closure.edges[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        node = _require_str(entry, "node", path, ctx)
        dependents = _require_list(entry, "dependents", path, ctx)
        dependent_strs = _require_str_list(dependents, path, f"{ctx}.dependents")
        edges.append(DependencyEdge(node=node, dependents=frozenset(dependent_strs)))
    return ConstraintDependencyClosure(edges=tuple(edges))


def load_venue_constraint_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedVenuePolicy:
    """Load, fail-closed-validate, and kernel-issue a Venue Constraint Policy
    from ``path`` (shaped like plan §4.1's ``venue_constraint_policy.yaml``
    v1 key list; module docstring).

    Raises:
        VenuePolicyConfigError: the file is missing/unreadable/not valid
            YAML/not a mapping; any required key is absent or still ``null``
            (except the six honestly-nullable ``shape_constraints`` bounds,
            module docstring); an ``action``/``required_constraint_classes``
            token is not a known kernel enum member; or ``scope
            .quantity_unit`` is not a known ``QuantityUnitKind``.
    """
    raw = _load_mapping(path, "venue constraint policy")
    policy_id = _require_str(raw, "policy_id", path, "policy")
    policy_generation = _require_int(raw, "policy_generation", path, "policy")
    scope = _parse_scope(raw, path)
    admitting_phase_rules = _parse_admitting_phase_rules(raw, path)
    required_constraint_classes = _parse_required_constraint_classes(raw, path)
    shape_constraints, null_bounds = _parse_shape_constraints(raw, path)
    dependency_closure = _parse_dependency_closure(raw, path)

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


# ===========================================================================
# order_construction_policy.yaml
# ===========================================================================


def _parse_wire_codec(
    raw: dict[str, Any], path: Path
) -> tuple[str | None, frozenset[str]]:
    if "wire_codec" not in raw:
        raise VenuePolicyConfigError(
            f"{path}: missing required key 'wire_codec' (pass null explicitly "
            "for a synthetic transport)"
        )
    value = raw["wire_codec"]
    if value is None:
        return None, frozenset()
    if not isinstance(value, dict):
        raise VenuePolicyConfigError(f"{path}: 'wire_codec' must be a mapping or null")
    kind = _require_str(value, "kind", path, "wire_codec")
    fields = _require_list(value, "wire_fields", path, "wire_codec")
    field_strs = _require_str_list(fields, path, "wire_codec.wire_fields")
    return kind, frozenset(field_strs)


def load_order_construction_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedOrderConstructionPolicy:
    """Load, fail-closed-validate, and kernel-issue an Order Construction
    Policy from ``path`` (plan §4.1's ``order_construction_policy.yaml`` v1
    key list; module docstring — ``signer_identity``/``approval_identity``/
    ``evidence_package_ref`` are deliberately left ``None`` so this loader's
    digest matches the kernel's own ``construct_candidate_command`` issuance
    from the same three coordinates).

    Raises:
        VenuePolicyConfigError: the file is missing/unreadable/not valid
            YAML/not a mapping; any required key is absent or still ``null``;
            ``canonicalization_version`` does not equal ``scheme.version``;
            or ``wire_codec`` is present but malformed.
    """
    raw = _load_mapping(path, "order construction policy")
    policy_id = _require_str(raw, "policy_id", path, "policy")
    policy_generation = _require_int(raw, "policy_generation", path, "policy")
    policy_version = _require_str(raw, "policy_version", path, "policy")
    canonicalization_version = _require_str(
        raw, "canonicalization_version", path, "policy"
    )
    if canonicalization_version != scheme.version:
        raise VenuePolicyConfigError(
            f"{path}: canonicalization_version {canonicalization_version!r} != "
            f"the injected compose scheme's version {scheme.version!r} — refusing "
            "(plan §2 decision 6)"
        )
    wire_codec_kind, wire_fields = _parse_wire_codec(raw, path)

    policy = OrderConstructionPolicy.issue(
        scheme=scheme,
        policy_id=policy_id,
        policy_generation=policy_generation,
        policy_version=policy_version,
        signer_identity=None,
        approval_identity=None,
        evidence_package_ref=None,
    )
    assert isinstance(policy, OrderConstructionPolicy)
    return LoadedOrderConstructionPolicy(
        policy=policy,
        canonicalization_version=canonicalization_version,
        wire_codec_kind=wire_codec_kind,
        wire_fields=wire_fields,
    )
