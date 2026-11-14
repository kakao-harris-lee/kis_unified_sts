"""tos_runtime.venue._venue_policy_loader — the Venue Constraint Policy half"""

from __future__ import annotations

import re
from collections.abc import Callable
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
    PriceBandTick,
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
from tos_runtime.venue.band_journal import (
    BAND_SOURCE_KIND_PRODUCER_JOURNAL,
    ProducerJournalBandSource,
)
from tos_runtime.venue.band_source import (
    BAND_SOURCE_BOUND_TRADING_DATE_KST,
    BAND_SOURCE_FAILURE_UNKNOWN,
    BAND_SOURCE_KIND_KIS_QUOTE_GET,
    BAND_SOURCE_READ_ON_TOKENS,
    BandSourceConfig,
    KisQuoteGetBandSource,
    band_source_digest,
)

__all__ = [
    "VENUE_POLICY_CONFIG_NAME",
    "VenuePolicyScope",
    "LoadedVenuePolicy",
    "load_venue_constraint_policy",
]

VENUE_POLICY_CONFIG_NAME = "venue_constraint_policy.yaml"

_VENUE_ARTIFACT_TYPE = "VENUE_CONSTRAINT_POLICY"

_NULLABLE_SHAPE_BOUNDS: tuple[str, ...] = (
    "price_min",
    "price_max",
    "tick_size",
    "lot_size",
    "min_quantity",
    "max_quantity",
)

_SHAPE_ALLOWED_SET_KEYS: tuple[str, ...] = (
    "allowed_order_types",
    "allowed_tifs",
    "allowed_sides",
    "allowed_position_effects",
)

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

_VENUE_SCOPE_SINGLETON_KEYS: tuple[str, ...] = (
    "environments",
    "brokers",
    "accounts",
    "venues",
    "market_segments",
    "instruments",
)

_VENUE_SCOPE_SINGLETON_FIELD_NAMES: tuple[str, ...] = (
    "environment",
    "broker",
    "account",
    "venue",
    "market_segment",
    "instrument",
)

_VENUE_SCOPE_LIST_KEYS: tuple[str, ...] = ("safety_cells", "contracts")

_QUOTE_TR_ID_PATTERN = re.compile(r"^FH[A-Z]{3}\d{8}$")


@dataclass(frozen=True)
class VenuePolicyScope:
    """The structured venue policy scope (plan §4.1, corrected field set —"""

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
    """A loaded, kernel-issued Venue Constraint Policy plus its structured"""

    policy: VenueConstraintPolicy
    scope: VenuePolicyScope
    quantity_constraint: VenueQuantityConstraint
    null_shape_bounds: tuple[str, ...]
    band_source: BandSourceConfig | None = None
    band_source_digest: str | None = None
    price_scale: int | None = None


def _as_decimal(value: int | None) -> Decimal | None:
    """``VenueShapeConstraints``'s numeric bounds are plain ``int`` (venue is"""
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
    """The composed scope identity string the kernel ``VenueConstraintPolicy"""
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
) -> tuple[str, QuantityUnitKind, str | None, dict[str, Any]]:
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
    return instrument_class, quantity_unit, currency, runtime_raw


def _require_positive_int_key(
    raw: dict[str, Any], key: str, path: Path, ctx: str
) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.{key} must be a positive int, got {value!r} — a band source "
            "cannot be enabled with an unbounded or absent value here (plan §4.1)"
        )
    return value


_BAND_SOURCE_KIND_KEYS: dict[str, frozenset[str]] = {
    BAND_SOURCE_KIND_KIS_QUOTE_GET: frozenset(
        {"tr_id", "upper_field", "lower_field", "basis_field", "timeout_ms"}
    ),
    BAND_SOURCE_KIND_PRODUCER_JOURNAL: frozenset(
        {"band_journal_path", "approved_source_prefixes"}
    ),
}

_BAND_SOURCE_KINDS: frozenset[str] = frozenset(_BAND_SOURCE_KIND_KEYS)


def _refuse_keys_of_the_other_kind(
    block: dict[str, Any], kind: str, path: Path, ctx: str
) -> None:
    """Refuse a leaf that belongs to a DIFFERENT ``band_source.kind``."""
    foreign = sorted(
        set(block)
        & frozenset().union(
            *(keys for other, keys in _BAND_SOURCE_KIND_KEYS.items() if other != kind)
        )
        - _BAND_SOURCE_KIND_KEYS[kind]
    )
    if foreign:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.kind is {kind!r} but the block declares {foreign!r}, which "
            f"belong(s) to another kind and is read by nothing on this path — "
            f"{kind!r} reads {sorted(_BAND_SOURCE_KIND_KEYS[kind])!r}"
        )


def _parse_band_source(
    runtime_raw: dict[str, Any], path: Path
) -> BandSourceConfig | None:
    """Parse ``_runtime.band_source`` (plan §4.1's YAML block), or ``None``."""
    block = runtime_raw.get("band_source")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise VenuePolicyConfigError(
            f"{path}: _runtime.band_source must be a mapping or null, got {block!r}"
        )
    ctx = "_runtime.band_source"
    kind = require_filled_str(block, "kind", path, ctx)
    if kind not in _BAND_SOURCE_KINDS:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.kind {kind!r} is not one of {sorted(_BAND_SOURCE_KINDS)!r} — the "
            "runtime has no reader for any other kind, and a declared-but-unreadable source "
            "would boot as 'band always None', indistinguishable from a broker outage"
        )
    bound = require_filled_str(block, "bound", path, ctx)
    if bound != BAND_SOURCE_BOUND_TRADING_DATE_KST:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.bound {bound!r} is not "
            f"{BAND_SOURCE_BOUND_TRADING_DATE_KST!r} — the trading-date bond (plan §4.4a) is "
            "the only invalidation this runtime implements"
        )
    failure = require_filled_str(block, "failure", path, ctx)
    if failure != BAND_SOURCE_FAILURE_UNKNOWN:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.failure {failure!r} is not {BAND_SOURCE_FAILURE_UNKNOWN!r} — "
            "every read/validation failure is band None and therefore kernel UNKNOWN "
            "(plan §4.6); no other failure response exists to declare"
        )
    read_on = tuple(
        require_str_list(require_list(block, "read_on", path, ctx), path, ctx)
    )
    unknown_tokens = sorted(set(read_on) - BAND_SOURCE_READ_ON_TOKENS)
    if unknown_tokens or not read_on:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.read_on {list(read_on)!r} must be a non-empty subset of "
            f"{sorted(BAND_SOURCE_READ_ON_TOKENS)!r} — a token outside that set names a read "
            "instant nothing implements (plan §4.3)"
        )
    common: dict[str, Any] = {
        "kind": kind,
        "instrument": require_filled_str(block, "instrument", path, ctx),
        "price_scale": _require_positive_int_key(block, "price_scale", path, ctx),
        "bound": bound,
        "read_on": read_on,
        "failure": failure,
    }
    _refuse_keys_of_the_other_kind(block, kind, path, ctx)
    if kind == BAND_SOURCE_KIND_KIS_QUOTE_GET:
        tr_id = require_filled_str(block, "tr_id", path, ctx)
        if not _QUOTE_TR_ID_PATTERN.match(tr_id):
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.tr_id {tr_id!r} does not match the measured KIS quotations TR "
                "id shape ('FH' + 3 letters + 8 digits — "
                "tos_runtime.transport.kis_quote.config's own module docstring records the "
                "measurement and its citations)"
            )
        return KisQuoteGetBandSource(
            tr_id=tr_id,
            upper_field=require_filled_str(block, "upper_field", path, ctx),
            lower_field=require_filled_str(block, "lower_field", path, ctx),
            basis_field=require_filled_str(block, "basis_field", path, ctx),
            timeout_ms=_require_positive_int_key(block, "timeout_ms", path, ctx),
            **common,
        )
    prefixes = tuple(
        require_str_list(
            require_list(block, "approved_source_prefixes", path, ctx),
            path,
            f"{ctx}.approved_source_prefixes",
        )
    )
    if not prefixes or any(not prefix.strip() for prefix in prefixes):
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.approved_source_prefixes {list(prefixes)!r} must be a non-empty "
            "list of non-empty strings — an empty list approves no writer (so the band is "
            "permanently absent) and an empty ENTRY approves every one of them (2026-10-15 "
            "plan §3.4 C1; the same rule tools/tos_cp3/bootproof_guard.py applies to its own "
            "list)"
        )
    return ProducerJournalBandSource(
        band_journal_path=require_filled_str(block, "band_journal_path", path, ctx),
        approved_source_prefixes=prefixes,
        **common,
    )


def _cross_check_band_source(
    band_source: BandSourceConfig | None,
    *,
    runtime_raw: dict[str, Any],
    scope_instrument: str,
    shape_constraints: VenueShapeConstraints,
    transport_instrument_reader: Callable[[], str | None] | None,
    path: Path,
) -> int | None:
    """The cross-document rules a DECLARED band source must satisfy, and the"""
    if band_source is None:
        if "price_scale" not in runtime_raw:
            return None
        return _require_positive_int_key(runtime_raw, "price_scale", path, "_runtime")
    if (
        shape_constraints.price_min is not None
        or shape_constraints.price_max is not None
    ):
        raise VenuePolicyConfigError(
            f"{path}: _runtime.band_source is declared AND "
            f"_model_view.shape_constraints.price_min/price_max carry literals "
            f"({shape_constraints.price_min!r}/{shape_constraints.price_max!r}) — two sources "
            "for one bound; the band source fills them, so the literals must be null"
        )
    if band_source.instrument != scope_instrument:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.band_source.instrument {band_source.instrument!r} != "
            f"scope.instruments' sole element {scope_instrument!r} — a band read for one "
            "contract would be folded onto another contract's policy (plan §4.4b; "
            "ADR-002-019:357 'wrong contract/account mapping')"
        )
    price_scale = _require_positive_int_key(
        runtime_raw, "price_scale", path, "_runtime"
    )
    if price_scale != band_source.price_scale:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.price_scale {price_scale!r} != "
            f"_runtime.band_source.price_scale {band_source.price_scale!r} — the band and the "
            "order price would be compared in different units (plan §4.1 가격 척도)"
        )
    if band_source.kind != BAND_SOURCE_KIND_KIS_QUOTE_GET:
        return price_scale
    transport_instrument = (
        None if transport_instrument_reader is None else transport_instrument_reader()
    )
    if transport_instrument is None:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.band_source is declared but this deployment carries no "
            "kis_quote transport document — the band GET reuses that document's host seal and "
            "paths, so there is nothing to read it through (plan §4.1)"
        )
    if transport_instrument != band_source.instrument:
        raise VenuePolicyConfigError(
            f"{path}: kis_quote transport instrument {transport_instrument!r} != "
            f"_runtime.band_source.instrument {band_source.instrument!r} — a config whose two "
            "contract declarations disagree is an operations error on its face (plan §4.4b's "
            "config-consistency rule; it becomes a GUARD once the same transport is also the "
            "order price's source)"
        )
    return price_scale


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


def _parse_price_band_ticks(
    sc_raw: dict[str, Any], path: Path
) -> tuple[PriceBandTick, ...] | None:
    """``_model_view.shape_constraints.price_band_ticks`` — the kernel's per-price-band tick"""
    raw = sc_raw.get("price_band_ticks")
    if raw is None:
        return None
    ctx = f"{path}: _model_view.shape_constraints.price_band_ticks"
    if not isinstance(raw, list) or not raw:
        raise VenuePolicyConfigError(
            f"{ctx} must be a non-empty list of rows, or null for no table"
        )
    rows: list[PriceBandTick] = []
    for index, row in enumerate(raw):
        if not isinstance(row, dict) or set(row) != {"band_min", "band_max", "tick"}:
            raise VenuePolicyConfigError(
                f"{ctx}[{index}] must be a mapping of exactly band_min/band_max/tick"
            )
        values = [row["band_min"], row["band_max"], row["tick"]]
        if any(not isinstance(v, int) or isinstance(v, bool) for v in values):
            raise VenuePolicyConfigError(f"{ctx}[{index}] values must be ints")
        band_min, band_max, tick = values
        if tick <= 0:
            raise VenuePolicyConfigError(f"{ctx}[{index}].tick must be positive")
        if band_min <= 0:
            raise VenuePolicyConfigError(f"{ctx}[{index}].band_min must be positive")
        if band_min > band_max:
            raise VenuePolicyConfigError(f"{ctx}[{index}] band_min > band_max")
        if rows and band_min <= rows[-1].band_max:
            raise VenuePolicyConfigError(
                f"{ctx}[{index}] overlaps or precedes row {index - 1} — rows must be "
                "ascending and disjoint"
            )
        rows.append(PriceBandTick(band_min=band_min, band_max=band_max, tick=tick))
    return tuple(rows)


def _parse_shape_constraints(
    raw: dict[str, Any], path: Path
) -> tuple[VenueShapeConstraints, tuple[str, ...]]:
    sc_raw = require_mapping_key(raw, "shape_constraints", path)
    bounds, null_bounds = _parse_numeric_bounds(sc_raw, path)
    price_band_ticks = _parse_price_band_ticks(sc_raw, path)
    if price_band_ticks is not None:
        if bounds["tick_size"] is not None:
            raise VenuePolicyConfigError(
                f"{path}: _model_view.shape_constraints.price_band_ticks is declared AND "
                f"tick_size carries a literal ({bounds['tick_size']!r}) — the table governs "
                "every price, so tick_size must be null"
            )
        null_bounds = tuple(name for name in null_bounds if name != "tick_size")
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
        price_band_ticks=price_band_ticks,
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


def _build_venue_scope(
    raw: dict[str, Any], path: Path
) -> tuple[
    VenuePolicyScope, frozenset[ActionClass], dict[str, Any], BandSourceConfig | None
]:
    """The ``scope`` block plus the ``_runtime`` block it is completed from — split out of"""
    (
        environment,
        broker,
        account,
        venue,
        market_segment,
        instrument,
        scope_action_classes,
    ) = _parse_venue_scope(raw, path)
    instrument_class, quantity_unit, currency, runtime_raw = _parse_venue_runtime_block(
        raw, path
    )
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
    return (
        scope,
        scope_action_classes,
        runtime_raw,
        _parse_band_source(runtime_raw, path),
    )


def load_venue_constraint_policy(
    path: Path,
    *,
    scheme: CanonicalizationScheme,
    band_transport_instrument_reader: Callable[[], str | None] | None = None,
) -> LoadedVenuePolicy:
    """Load, fail-closed-validate, and kernel-issue a Venue Constraint Policy"""
    raw = load_mapping(path, "venue constraint policy")
    require_exact_str(raw, "artifact_type", _VENUE_ARTIFACT_TYPE, path, "policy")
    require_exact_str(raw, "schema_version", ACCEPTED_SCHEMA_VERSION, path, "policy")
    require_issued_status(raw, path)
    policy_id = require_filled_str(raw, "policy_id", path, "policy")
    policy_generation = require_int(raw, "policy_generation", path, "policy")
    require_nullable_str_key_present(raw, "effective_from", path, "policy")
    require_nullable_str_key_present(raw, "review_due", path, "policy")

    scope, scope_action_classes, runtime_raw, band_source = _build_venue_scope(
        raw, path
    )

    mv_raw = require_mapping_key(raw, "_model_view", path)
    admitting_phase_rules = _parse_admitting_phase_rules(mv_raw, path)
    required_constraint_classes = _parse_required_constraint_classes(mv_raw, path)
    shape_constraints, null_bounds = _parse_shape_constraints(mv_raw, path)
    dependency_closure = _parse_dependency_closure(mv_raw, path)
    _cross_check_admitting_actions_in_scope(
        admitting_phase_rules, scope_action_classes, path
    )
    price_scale = _cross_check_band_source(
        band_source,
        runtime_raw=runtime_raw,
        scope_instrument=scope.instrument,
        shape_constraints=shape_constraints,
        transport_instrument_reader=band_transport_instrument_reader,
        path=path,
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
        band_source=band_source,
        band_source_digest=(
            None if band_source is None else band_source_digest(band_source)
        ),
        price_scale=price_scale,
    )
