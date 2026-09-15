"""tos_runtime.venue.config — Venue Constraint Policy / Order Construction Policy loaders.

TOS venue constraint service wave, plan §2 decisions 1/2/6, §4.1
(``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``), CORRECTED
per team-lead 2026-09-15: the runtime instance YAML documents this module
loads are INSTANCES of the two tos-spec verification templates —
``tos-spec/src/part-1-foundation/verification/VENUE-CONSTRAINT-POLICY-template.yaml``
and ``.../ORDER-CONSTRUCTION-POLICY-template.yaml`` — not a bespoke,
runtime-invented key set.

**``_model_view`` / ``_runtime`` discipline — the one rule this module never
breaks** (mirrors :mod:`tos_runtime.brokercap.instance`'s own stated
discipline, its module docstring's "the one rule this module never breaks").
The template's own top-level keys (``artifact_type``, ``schema_version``,
``policy_id``, ``policy_generation``, ``canonical_digest``, ``status``,
``scope``, and the long run of rule-list / ``authority`` / ``evidence``
governance keys) are read EITHER directly as plain scalars/lists — when the
template's own vocabulary already matches what the kernel needs (identity
scalars, the ``scope`` list block) — OR only for PRESENCE/shape fidelity
(every rule-list key, ``approved_by``, ``authority``, ``evidence`` — this
module stores nothing from them and interprets nothing; a governance
document with an author-editable rule-list is not consulted for kernel
construction). Two SIBLING top-level blocks the templates do not themselves
define carry the kernel-typed content this loader actually builds records
from: ``_model_view`` (kernel-field-named values, already in the kernel's own
enum vocabulary — never "fixed" from a template spelling) and ``_runtime``
(runtime-only facts with no template counterpart at all, e.g.
``instrument_class``/``quantity_unit``/``canonicalization_version``). A
missing ``_model_view``/``_runtime`` block, or a value that is not already
exact kernel vocabulary, is a refusal — never invented (module docstring,
:class:`VenuePolicyConfigError`).

**``schema_version`` is a hardcoded constant, never a tos-spec read.** The
runtime does not import or read ``tos-spec`` at all (§0.3 sibling-edge
discipline — spec and runtime are separate distributions). The accepted value
(:data:`_ACCEPTED_SCHEMA_VERSION`) is copied by hand from the two templates'
own ``schema_version: "1.0-DRAFT"`` line and must be bumped by hand if a
future spec PR changes it.

**``status`` must be ``ISSUED`` (the kernel's own ``ArtifactStatus.ISSUED``
value).** A document still carrying the template's own ``status: DRAFT``
default is refused outright — "a DRAFT policy cannot be activated" — never
silently promoted.

**``canonical_digest``: ``"TBD"`` is accepted, anything else must match.**
This loader ALWAYS recomputes the digest itself via the kernel's own
``.issue()`` (never trusts a document-supplied digest as input); the
document's own ``canonical_digest`` field is then checked only as an
independent cross-check — the template placeholder ``"TBD"`` passes (the
document has not yet recorded a digest), and any other string must equal the
freshly computed one exactly, or the load refuses (tamper/stale detection —
an operator who edited the policy's content without re-running the issuing
tool would otherwise silently drift).

**The single-live-scope rule (v1).** The template's ``scope`` list fields
allow an arbitrary set (a governed policy MAY one day scope multiple
environments/venues at once); v1 of this loader only supports EXACTLY one
live scope, so ``environments``/``brokers``/``accounts``/``venues``/
``market_segments``/``instruments`` (venue policy) and ``environments``/
``brokers``/``accounts``/``instruments`` (Order Construction Policy) must
each carry exactly one string — zero or two-or-more is refused. The other
``scope`` list keys (``safety_cells``, ``contracts``, and — OCP only —
``venues``/``market_segments``) are accepted as explicit lists of any length
(may be empty) for schema fidelity only; nothing is read from them.
``action_classes`` is validated as a list of kernel ``ActionClass`` tokens
(venue policy: cross-checked below; OCP: schema fidelity only, no
cross-check — the plan names no OCP-side use of it). ``order_types`` (OCP
only) is an explicit list of strings, not further typed (no kernel
order-type enum is named in scope for this loader).

**Scope/admission cross-check (venue policy only).** Every
``_model_view.admitting_phase_rules[*].action`` must be a member of
``scope.action_classes`` — a policy that admits an action outside its own
declared scope is refused at load (a scope-declaration bug, not a runtime
admissibility judgement; this loader still authors no
``OrderAdmissibilityResult``).

Fail-closed discipline throughout (mirrors :mod:`tos_runtime.calendar.config`'s
own module docstring): a missing file, a non-mapping top level, a missing
required key, or a required scalar left ``null`` (named-TBD) all refuse to
load — never a silent default. Explicit-list keys accept ``[]`` as a
deliberate "none declared"; a missing key or ``null`` is refused as
still-TBD.

**Deliberate exception — six numeric ``shape_constraints`` bounds** (inside
``_model_view``). ``price_min``/``price_max``/``tick_size``/``lot_size``/
``min_quantity``/``max_quantity`` MAY be ``null`` = "no source" (plan §2
decision 2; ADR-002-019 §9: "None alone proves current admissibility unless
the active policy explicitly defines the fact"). A ``null`` bound is passed
straight through to the kernel's ``VenueShapeConstraints`` —
``order_shape_admissible`` already returns ``UNKNOWN`` on a ``None`` bound —
the honest semantics for a constraint the operator has not yet sourced. Each
null bound's field name is recorded on
:attr:`LoadedVenuePolicy.null_shape_bounds`.

``OrderConstructionPolicy`` is issued with ``signer_identity``/
``approval_identity``/``evidence_package_ref`` all ``None`` — DELIBERATE, not
a gap: the kernel's own ``construct_candidate_command`` issues its own
``OrderConstructionPolicy`` from the SAME three coordinates
(``policy_id``/``policy_generation``/``policy_version``) with those same
three fields ``None`` too, so a loader that filled them would manufacture a
``classify_record_pair`` ``CRITICAL_CONFLICT`` — "same id, different bytes"
(plan §2 decision 6). Filling those three fields for real is deferred to a
kernel signature change (plan §6 decision 4, "커널 라운드 #4 후보").

Firewall (R1, runtime scope): stdlib + ``pyyaml`` + ``tos.*`` only — no
``shared.*``, no ``os.environ``, no ``subprocess``, no
``importlib.import_module`` (``tools/tos_firewall_check.py`` scans tests
too). This module never reads ``tos-spec`` (a separate, non-runtime
distribution) — the templates are cited above for a human reader only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import ArtifactStatus, CanonicalizationScheme
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

#: The runtime INSTANCE file names (distinct from the tos-spec TEMPLATE file
#: names cited in the module docstring — these are what an environment's
#: config directory actually carries).
VENUE_POLICY_CONFIG_NAME = "venue_constraint_policy.yaml"
ORDER_CONSTRUCTION_POLICY_CONFIG_NAME = "order_construction_policy.yaml"

#: Hand-copied from both templates' own ``schema_version: "1.0-DRAFT"`` line
#: (module docstring — never read from tos-spec at runtime). Bump by hand if
#: a future tos-spec PR changes either template's schema_version.
_ACCEPTED_SCHEMA_VERSION = "1.0-DRAFT"

_VENUE_ARTIFACT_TYPE = "VENUE_CONSTRAINT_POLICY"
_OCP_ARTIFACT_TYPE = "ORDER_CONSTRUCTION_POLICY"

#: The template's reserved not-yet-computed digest placeholder.
_TBD_DIGEST = "TBD"

#: The template's reserved not-yet-filled identity placeholder.
_TBD_STR = "TBD"

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

#: The VENUE-CONSTRAINT-POLICY-template.yaml top-level rule-list keys this loader
#: only checks for presence/shape (list-typed) — content unread, uninterpreted
#: (module docstring). Order matches the template file.
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

#: The ORDER-CONSTRUCTION-POLICY-template.yaml top-level rule-list keys —
#: same presence-only discipline. Order matches the template file.
_OCP_TEMPLATE_LIST_KEYS: tuple[str, ...] = (
    "intent_schema_versions",
    "authorized_construction_envelope_schema_versions",
    "canonical_broker_command_schema_versions",
    "economic_effect_envelope_schema_versions",
    "order_conformance_proof_schema_versions",
    "field_presence_and_mapping_rules",
    "account_instrument_contract_and_route_rules",
    "direction_side_and_position_effect_rules",
    "unit_multiplier_currency_and_numeric_rules",
    "price_tick_lot_quantity_and_rounding_rules",
    "order_type_time_in_force_expiration_and_mode_rules",
    "split_aggregation_retry_cancel_amend_and_replace_rules",
    "canonicalization_and_duplicate_field_rules",
    "serializer_sdk_signer_and_actual_outbound_rules",
    "compiler_dependency_and_compatibility_rules",
    "economic_effect_and_capacity_rules",
    "invalidation_and_failure_responses",
    "common_mode_requirements",
    "residual_risks",
    "approved_by",
)

#: Both templates carry these two top-level MAPPING keys (not lists) — same
#: presence-only discipline.
_TEMPLATE_MAPPING_KEYS: tuple[str, ...] = ("authority", "evidence")

#: The venue-policy ``scope`` block's single-live-scope (exactly one entry)
#: list keys (module docstring).
_VENUE_SCOPE_SINGLETON_KEYS: tuple[str, ...] = (
    "environments",
    "brokers",
    "accounts",
    "venues",
    "market_segments",
    "instruments",
)

#: The venue-policy ``scope`` block's remaining explicit-list keys (any length).
_VENUE_SCOPE_LIST_KEYS: tuple[str, ...] = ("safety_cells", "contracts")

#: The OCP ``scope`` block's single-live-scope list keys (module docstring —
#: OCP does not require a single ``venues``/``market_segments`` entry).
_OCP_SCOPE_SINGLETON_KEYS: tuple[str, ...] = (
    "environments",
    "brokers",
    "accounts",
    "instruments",
)

#: The OCP ``scope`` block's remaining explicit-list keys (any length).
_OCP_SCOPE_LIST_KEYS: tuple[str, ...] = (
    "safety_cells",
    "venues",
    "market_segments",
    "contracts",
    "order_types",
)


class VenuePolicyConfigError(RuntimeError):
    """A venue / order-construction policy instance YAML is missing,
    malformed, fails the ``artifact_type``/``schema_version``/``status``
    template-identity checks, carries an unfilled (named-TBD) required
    field, a ``canonical_digest`` that does not match the freshly computed
    one, an unknown ``ActionClass``/``ConstraintClass``/``QuantityUnitKind``
    token, a ``scope`` singleton violation, an ``admitting_phase_rules``
    action outside its own declared ``scope.action_classes``, or (for the
    Order Construction Policy) a ``canonicalization_version`` that does not
    match the injected compose scheme — fail-closed at load, never a silent
    default (module docstring)."""


@dataclass(frozen=True)
class VenuePolicyScope:
    """The structured venue policy scope (plan §4.1, corrected field set —
    the template's ``scope`` block has no ``product_type`` key at all).

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
    declaration and its own document ``construction_generation`` (plan §4.1
    + team-lead correction 2026-09-15)."""

    policy: OrderConstructionPolicy
    canonicalization_version: str
    wire_codec_kind: str | None
    wire_fields: frozenset[str]
    construction_generation: int | None


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


def _require_filled_str(raw: dict[str, Any], key: str, path: Path, ctx: str) -> str:
    """Like :func:`_require_str`, but ALSO refuses the template's own
    ``"TBD"`` placeholder string (identity fields must be genuinely filled,
    module docstring)."""
    value = _require_str(raw, key, path, ctx)
    if value == _TBD_STR:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still the template placeholder {_TBD_STR!r}"
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


def _optional_int(raw: dict[str, Any], key: str, path: Path, ctx: str) -> int | None:
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise VenuePolicyConfigError(f"{path}: {ctx} {key!r} must be an int or null")
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


def _require_exact_str(
    raw: dict[str, Any], key: str, expected: str, path: Path, ctx: str
) -> None:
    value = raw.get(key)
    if value != expected:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} must equal {expected!r} (got {value!r})"
        )


def _require_issued_status(raw: dict[str, Any], path: Path) -> None:
    status = raw.get("status")
    if status != ArtifactStatus.ISSUED.value:
        raise VenuePolicyConfigError(
            f"{path}: 'status' must be {ArtifactStatus.ISSUED.value!r} — a "
            f"DRAFT (or any other non-ISSUED) policy cannot be activated "
            f"(got {status!r})"
        )


def _check_canonical_digest(
    raw: dict[str, Any], path: Path, computed_digest: str | None, ctx: str
) -> None:
    """Cross-check the document's own ``canonical_digest`` against the
    freshly kernel-computed ``computed_digest`` (module docstring's tamper/
    stale-detection discipline). ``"TBD"`` always passes; any other value
    must equal ``computed_digest`` exactly."""
    value = raw.get("canonical_digest")
    if value == _TBD_DIGEST:
        return
    if not isinstance(value, str):
        raise VenuePolicyConfigError(
            f"{path}: {ctx} canonical_digest must be a string or "
            f"{_TBD_DIGEST!r} (got {value!r})"
        )
    if value != computed_digest:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} canonical_digest {value!r} != the freshly "
            f"computed digest {computed_digest!r} — refusing (tamper/stale "
            "detection, module docstring)"
        )


def _require_template_shape(
    raw: dict[str, Any],
    path: Path,
    *,
    list_keys: tuple[str, ...],
    mapping_keys: tuple[str, ...],
) -> None:
    """Presence/shape-only fidelity check over every template rule-list /
    governance-mapping key this loader never interprets (module docstring)."""
    for key in list_keys:
        _require_list(raw, key, path, "policy")
    for key in mapping_keys:
        _require_mapping_key(raw, key, path)


def _parse_action_classes(
    scope_raw: dict[str, Any], path: Path, ctx: str
) -> frozenset[ActionClass]:
    entries = _require_list(scope_raw, "action_classes", path, ctx)
    classes: set[ActionClass] = set()
    for token in entries:
        if not isinstance(token, str):
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.action_classes entries must be strings"
            )
        try:
            classes.add(ActionClass(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.action_classes {token!r} is not a known ActionClass"
            ) from exc
    return frozenset(classes)


def _require_singleton_list_str(
    scope_raw: dict[str, Any], key: str, path: Path, ctx: str
) -> str:
    entries = _require_list(scope_raw, key, path, ctx)
    values = _require_str_list(entries, path, f"{ctx}.{key}")
    if len(values) != 1:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.{key} must be a list of EXACTLY one string for a "
            f"single live scope (v1) — got {len(values)}"
        )
    return values[0]


# ===========================================================================
# venue_constraint_policy.yaml
# ===========================================================================


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


def _parse_venue_scope(
    raw: dict[str, Any], path: Path
) -> tuple[str, str, str, str, str, str, frozenset[ActionClass]]:
    scope_raw = _require_mapping_key(raw, "scope", path)
    singletons = {
        field_name: _require_singleton_list_str(scope_raw, key, path, "scope")
        for key, field_name in zip(
            _VENUE_SCOPE_SINGLETON_KEYS, _VENUE_SCOPE_SINGLETON_FIELD_NAMES, strict=True
        )
    }
    for key in _VENUE_SCOPE_LIST_KEYS:
        entries = _require_list(scope_raw, key, path, "scope")
        _require_str_list(entries, path, f"scope.{key}")
    action_classes = _parse_action_classes(scope_raw, path, "scope")
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
    runtime_raw = _require_mapping_key(raw, "_runtime", path)
    instrument_class = _require_str(runtime_raw, "instrument_class", path, "_runtime")
    unit_token = _require_str(runtime_raw, "quantity_unit", path, "_runtime")
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
    entries = _require_list(raw, "admitting_phase_rules", path, "_model_view")
    rules = []
    for i, entry in enumerate(entries):
        ctx = f"_model_view.admitting_phase_rules[{i}]"
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
    entries = _require_list(raw, "required_constraint_classes", path, "_model_view")
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
    sc_raw = _require_mapping_key(raw, "shape_constraints", path)
    bounds, null_bounds = _parse_numeric_bounds(sc_raw, path)
    allowed_sets: dict[str, frozenset[str]] = {}
    for key in _SHAPE_ALLOWED_SET_KEYS:
        entries = _require_list(sc_raw, key, path, "_model_view.shape_constraints")
        allowed_sets[key] = frozenset(
            _require_str_list(entries, path, f"_model_view.shape_constraints.{key}")
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
    entries = _require_list(dc_raw, "edges", path, "_model_view.dependency_closure")
    edges = []
    for i, entry in enumerate(entries):
        ctx = f"_model_view.dependency_closure.edges[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        node = _require_str(entry, "node", path, ctx)
        dependents = _require_list(entry, "dependents", path, ctx)
        dependent_strs = _require_str_list(dependents, path, f"{ctx}.dependents")
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
    ``VENUE-CONSTRAINT-POLICY-template.yaml`` — module docstring).

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
            .quantity_unit`` is not a known ``QuantityUnitKind``; or any
            template rule-list/``authority``/``evidence`` key is absent or
            not list/mapping-shaped.
    """
    raw = _load_mapping(path, "venue constraint policy")
    _require_exact_str(raw, "artifact_type", _VENUE_ARTIFACT_TYPE, path, "policy")
    _require_exact_str(raw, "schema_version", _ACCEPTED_SCHEMA_VERSION, path, "policy")
    _require_issued_status(raw, path)
    policy_id = _require_filled_str(raw, "policy_id", path, "policy")
    policy_generation = _require_int(raw, "policy_generation", path, "policy")

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

    mv_raw = _require_mapping_key(raw, "_model_view", path)
    admitting_phase_rules = _parse_admitting_phase_rules(mv_raw, path)
    required_constraint_classes = _parse_required_constraint_classes(mv_raw, path)
    shape_constraints, null_bounds = _parse_shape_constraints(mv_raw, path)
    dependency_closure = _parse_dependency_closure(mv_raw, path)
    _cross_check_admitting_actions_in_scope(
        admitting_phase_rules, scope_action_classes, path
    )

    _require_template_shape(
        raw,
        path,
        list_keys=_VENUE_TEMPLATE_LIST_KEYS,
        mapping_keys=_TEMPLATE_MAPPING_KEYS,
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
    _check_canonical_digest(raw, path, policy.canonical_digest, "policy")

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


def _parse_ocp_scope(raw: dict[str, Any], path: Path) -> None:
    """Validate the OCP ``scope`` block's shape (module docstring) — nothing
    is stored from it; the loader's typed content lives in ``_model_view``/
    ``_runtime`` only."""
    scope_raw = _require_mapping_key(raw, "scope", path)
    for key in _OCP_SCOPE_SINGLETON_KEYS:
        _require_singleton_list_str(scope_raw, key, path, "scope")
    for key in _OCP_SCOPE_LIST_KEYS:
        entries = _require_list(scope_raw, key, path, "scope")
        _require_str_list(entries, path, f"scope.{key}")


def _parse_ocp_model_view(
    raw: dict[str, Any], path: Path, *, top_level_policy_generation: int
) -> str:
    mv_raw = _require_mapping_key(raw, "_model_view", path)
    generation = _require_int(mv_raw, "policy_generation", path, "_model_view")
    if generation != top_level_policy_generation:
        raise VenuePolicyConfigError(
            f"{path}: _model_view.policy_generation {generation!r} != top-level "
            f"policy_generation {top_level_policy_generation!r} — refusing"
        )
    return _require_str(mv_raw, "policy_version", path, "_model_view")


def _parse_wire_codec(
    raw: dict[str, Any], path: Path
) -> tuple[str | None, frozenset[str]]:
    if "wire_codec" not in raw:
        raise VenuePolicyConfigError(
            f"{path}: _runtime missing required key 'wire_codec' (pass null "
            "explicitly for a synthetic transport)"
        )
    value = raw["wire_codec"]
    if value is None:
        return None, frozenset()
    if not isinstance(value, dict):
        raise VenuePolicyConfigError(
            f"{path}: _runtime.wire_codec must be a mapping or null"
        )
    kind = _require_str(value, "kind", path, "_runtime.wire_codec")
    fields = _require_list(value, "wire_fields", path, "_runtime.wire_codec")
    field_strs = _require_str_list(fields, path, "_runtime.wire_codec.wire_fields")
    return kind, frozenset(field_strs)


def _parse_ocp_runtime_block(
    raw: dict[str, Any], path: Path, *, scheme: CanonicalizationScheme
) -> tuple[str, str | None, frozenset[str]]:
    runtime_raw = _require_mapping_key(raw, "_runtime", path)
    canonicalization_version = _require_str(
        runtime_raw, "canonicalization_version", path, "_runtime"
    )
    if canonicalization_version != scheme.version:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.canonicalization_version {canonicalization_version!r} "
            f"!= the injected compose scheme's version {scheme.version!r} — refusing "
            "(plan §2 decision 6)"
        )
    wire_codec_kind, wire_fields = _parse_wire_codec(runtime_raw, path)
    return canonicalization_version, wire_codec_kind, wire_fields


def load_order_construction_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedOrderConstructionPolicy:
    """Load, fail-closed-validate, and kernel-issue an Order Construction
    Policy INSTANCE document from ``path`` (an instance of
    ``ORDER-CONSTRUCTION-POLICY-template.yaml`` — module docstring;
    ``signer_identity``/``approval_identity``/``evidence_package_ref`` are
    deliberately left ``None`` so this loader's digest matches the kernel's
    own ``construct_candidate_command`` issuance from the same three
    coordinates).

    Raises:
        VenuePolicyConfigError: the file is missing/unreadable/not valid
            YAML/not a mapping; ``artifact_type``/``schema_version`` do not
            match the accepted constants; ``status`` is not ``ISSUED``;
            ``policy_id``/``policy_generation`` are absent, ``null``, or
            still ``"TBD"``; ``canonical_digest`` is present but does not
            match the freshly computed digest; any ``scope`` singleton key
            does not carry exactly one string; ``_model_view
            .policy_generation`` does not equal the top-level
            ``policy_generation``; ``_runtime.canonicalization_version``
            does not equal ``scheme.version``; ``_runtime.wire_codec`` is
            present but malformed; or any template rule-list/``authority``/
            ``evidence`` key is absent or not list/mapping-shaped.
    """
    raw = _load_mapping(path, "order construction policy")
    _require_exact_str(raw, "artifact_type", _OCP_ARTIFACT_TYPE, path, "policy")
    _require_exact_str(raw, "schema_version", _ACCEPTED_SCHEMA_VERSION, path, "policy")
    _require_issued_status(raw, path)
    policy_id = _require_filled_str(raw, "policy_id", path, "policy")
    policy_generation = _require_int(raw, "policy_generation", path, "policy")
    construction_generation = _optional_int(
        raw, "construction_generation", path, "policy"
    )

    _parse_ocp_scope(raw, path)
    policy_version = _parse_ocp_model_view(
        raw, path, top_level_policy_generation=policy_generation
    )
    canonicalization_version, wire_codec_kind, wire_fields = _parse_ocp_runtime_block(
        raw, path, scheme=scheme
    )

    _require_template_shape(
        raw,
        path,
        list_keys=_OCP_TEMPLATE_LIST_KEYS,
        mapping_keys=_TEMPLATE_MAPPING_KEYS,
    )

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
    _check_canonical_digest(raw, path, policy.canonical_digest, "policy")

    return LoadedOrderConstructionPolicy(
        policy=policy,
        canonicalization_version=canonicalization_version,
        wire_codec_kind=wire_codec_kind,
        wire_fields=wire_fields,
        construction_generation=construction_generation,
    )
