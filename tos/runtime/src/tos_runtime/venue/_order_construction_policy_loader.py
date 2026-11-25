"""tos_runtime.venue._order_construction_policy_loader — the Order"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from tos.canonical import CanonicalizationScheme
from tos.egressgw import (
    DERIVED_AXES,
    EffectBasis,
    EffectDimensionSpec,
    LotRoundingPolicy,
    SizingBound,
)
from tos.ioc import AxisBinding, ConformanceAxis, OrderConstructionPolicy
from tos.venue import ActionClass

from tos_runtime.venue._policy_primitives import (
    ACCEPTED_SCHEMA_VERSION,
    TBD_STR,
    TEMPLATE_MAPPING_KEYS,
    VenuePolicyConfigError,
    check_canonical_digest,
    load_mapping,
    optional_int,
    optional_str,
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
from tos_runtime.venue.construction_rules import ActionClassShape, ConstructionRules

__all__ = [
    "ORDER_CONSTRUCTION_POLICY_CONFIG_NAME",
    "LoadedOrderConstructionPolicy",
    "load_order_construction_policy",
]

ORDER_CONSTRUCTION_POLICY_CONFIG_NAME = "order_construction_policy.yaml"

_OCP_ARTIFACT_TYPE = "ORDER_CONSTRUCTION_POLICY"

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

_OCP_SCOPE_SINGLETON_KEYS: tuple[str, ...] = (
    "environments",
    "brokers",
    "accounts",
    "instruments",
    "order_types",
)

_OCP_SCOPE_SINGLETON_FIELD_NAMES: tuple[str, ...] = (
    "environment",
    "broker",
    "account",
    "instrument",
    "order_type",
)

_OCP_SCOPE_LIST_KEYS: tuple[str, ...] = (
    "safety_cells",
    "venues",
    "market_segments",
    "contracts",
)

_SIZING_REQUIRED_INT_FIELDS: tuple[str, ...] = (
    "max_quantity",
    "min_quantity",
    "lot_size",
    "risk_budget",
    "per_unit_risk",
)

_AUTHORIZED_AXES_DERIVED_FROM_SCOPE: frozenset[ConformanceAxis] = frozenset(
    {
        ConformanceAxis.ENVIRONMENT,
        ConformanceAxis.ORDER_TYPE,
        ConformanceAxis.ACCOUNT,
        ConformanceAxis.INSTRUMENT,
    }
)


@dataclass(frozen=True)
class LoadedOrderConstructionPolicy:
    """A loaded, kernel-issued Order Construction Policy plus its wire-codec"""

    policy: OrderConstructionPolicy
    canonicalization_version: str
    wire_codec_kind: str | None
    wire_fields: frozenset[str]
    construction_generation: int | None
    construction_rules: ConstructionRules


def _parse_ocp_scope(raw: dict[str, Any], path: Path) -> tuple[str, str, str, str]:
    """Validate the OCP ``scope`` block's shape and return the four singleton coordinates the"""
    scope_raw = require_mapping_key(raw, "scope", path)
    singletons = {
        field_name: require_singleton_list_str(scope_raw, key, path, "scope")
        for key, field_name in zip(
            _OCP_SCOPE_SINGLETON_KEYS, _OCP_SCOPE_SINGLETON_FIELD_NAMES, strict=True
        )
    }
    for key in _OCP_SCOPE_LIST_KEYS:
        entries = require_list(scope_raw, key, path, "scope")
        require_str_list(entries, path, f"scope.{key}")
    parse_action_classes(scope_raw, path, "scope")
    return (
        singletons["environment"],
        singletons["order_type"],
        singletons["account"],
        singletons["instrument"],
    )


def _issue_ocp_policy(
    raw: dict[str, Any],
    path: Path,
    *,
    scheme: CanonicalizationScheme,
    policy_id: str,
    policy_generation: int,
    policy_version: str,
) -> OrderConstructionPolicy:
    """Read the three OCP covered fields ``OrderConstructionPolicy._COVERED_FIELDS`` already"""
    signer_identity = optional_str(raw, "signer_identity", path, "policy")
    approval_identity = optional_str(raw, "approval_identity", path, "policy")
    evidence_package_ref = optional_str(raw, "evidence_package_ref", path, "policy")
    policy = OrderConstructionPolicy.issue(
        scheme=scheme,
        policy_id=policy_id,
        policy_generation=policy_generation,
        policy_version=policy_version,
        signer_identity=signer_identity,
        approval_identity=approval_identity,
        evidence_package_ref=evidence_package_ref,
    )
    assert isinstance(policy, OrderConstructionPolicy)
    check_canonical_digest(raw, path, policy.canonical_digest, "policy")
    return policy


def _parse_ocp_model_view(
    raw: dict[str, Any], path: Path, *, top_level_policy_generation: int
) -> str:
    mv_raw = require_mapping_key(raw, "_model_view", path)
    generation = require_int(mv_raw, "policy_generation", path, "_model_view")
    if generation != top_level_policy_generation:
        raise VenuePolicyConfigError(
            f"{path}: _model_view.policy_generation {generation!r} != top-level "
            f"policy_generation {top_level_policy_generation!r} — refusing"
        )
    return require_filled_str(mv_raw, "policy_version", path, "_model_view")


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
    kind = require_str(value, "kind", path, "_runtime.wire_codec")
    fields = require_list(value, "wire_fields", path, "_runtime.wire_codec")
    field_strs = require_str_list(fields, path, "_runtime.wire_codec.wire_fields")
    if TBD_STR in field_strs:
        raise VenuePolicyConfigError(
            f"{path}: _runtime.wire_codec.wire_fields still carries the template "
            f"placeholder {TBD_STR!r} — operator-fill before activation"
        )
    return kind, frozenset(field_strs)


def _parse_ocp_runtime_block(
    raw: dict[str, Any], path: Path, *, scheme: CanonicalizationScheme
) -> tuple[str, str | None, frozenset[str]]:
    runtime_raw = require_mapping_key(raw, "_runtime", path)
    canonicalization_version = require_str(
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


def _parse_sizing(construction_raw: dict[str, Any], path: Path) -> SizingBound:
    """Parse ``_runtime.construction.sizing`` into a kernel"""
    sizing_raw = require_mapping_key(construction_raw, "sizing", path)
    ctx = "_runtime.construction.sizing"
    values = {
        name: require_int(sizing_raw, name, path, ctx)
        for name in _SIZING_REQUIRED_INT_FIELDS
    }
    max_notional = optional_int(sizing_raw, "max_notional", path, ctx)
    lot_rounding_token = require_str(sizing_raw, "lot_rounding", path, ctx)
    try:
        lot_rounding = LotRoundingPolicy(lot_rounding_token)
    except ValueError as exc:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.lot_rounding {lot_rounding_token!r} is not a known "
            "LotRoundingPolicy"
        ) from exc
    bases_entries = require_list(sizing_raw, "admitted_quantity_bases", path, ctx)
    bases = require_str_list(bases_entries, path, f"{ctx}.admitted_quantity_bases")
    if TBD_STR in bases:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.admitted_quantity_bases still carries the template "
            f"placeholder {TBD_STR!r} — operator-fill once the deployed strategy "
            "file's own quantity_basis is settled (OCP sizing proposal §4 ②); the "
            "paper instance is intentionally not bootable until then, the same "
            "state scope.accounts/scope.instruments are already in"
        )
    return SizingBound(
        risk_budget=Decimal(values["risk_budget"]),
        per_unit_risk=Decimal(values["per_unit_risk"]),
        lot_size=Decimal(values["lot_size"]),
        lot_rounding=lot_rounding,
        min_quantity=Decimal(values["min_quantity"]),
        max_quantity=Decimal(values["max_quantity"]),
        max_notional=None if max_notional is None else Decimal(max_notional),
        quantity_unit=None,
        admitted_quantity_bases=frozenset(bases),
    )


def _build_authorized_axes(
    construction_raw: dict[str, Any],
    path: Path,
    *,
    environment: str,
    order_type: str,
    account: str,
    instrument: str,
) -> tuple[AxisBinding, ...]:
    """Build the envelope's non-derived authorized axis bindings: ``ENVIRONMENT``/"""
    entries = require_list(construction_raw, "axes", path, "_runtime.construction")
    authored: list[AxisBinding] = []
    for i, entry in enumerate(entries):
        ctx = f"_runtime.construction.axes[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        axis_token = require_str(entry, "axis", path, ctx)
        try:
            axis = ConformanceAxis(axis_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.axis {axis_token!r} is not a known ConformanceAxis"
            ) from exc
        if axis in DERIVED_AXES:
            raise VenuePolicyConfigError(
                f"{path}: {ctx} declares the derived axis {axis.value} — "
                "QUANTITY/PRICE/UNIT are produced by the G5 derivation "
                "(tos.egressgw.construction.derive_order_size), never authorized here "
                "(ADR-002-020 §10:284 'ambiguity is denial'; the kernel "
                "ProposedConstructionEnvelope refuses this too, at a later, less specific point)"
            )
        if axis in _AUTHORIZED_AXES_DERIVED_FROM_SCOPE:
            raise VenuePolicyConfigError(
                f"{path}: {ctx} restates {axis.value}, which is derived from scope — do not "
                "re-declare it under _runtime.construction.axes (a second declaration risks "
                "drifting apart from the scope value)"
            )
        value = require_str(entry, "value", path, ctx)
        if value == TBD_STR:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.value for axis {axis.value} is still the template placeholder "
                f"{TBD_STR!r} — operator-fill before activation, the same discipline every "
                "other operator-fill leaf in this document already follows"
            )
        authored.append(AxisBinding(axis=axis, value=value))
    derived = (
        AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value=environment),
        AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value=order_type),
        AxisBinding(axis=ConformanceAxis.ACCOUNT, value=account),
        AxisBinding(axis=ConformanceAxis.INSTRUMENT, value=instrument),
    )
    return derived + tuple(authored)


_DIRECTION_NAMED_ACTION_CLASSES: frozenset[ActionClass] = frozenset(
    {ActionClass.NEW_LONG, ActionClass.NEW_SHORT}
)


def _refuse_missing_mirror(
    present: tuple[ActionClass, str], missing: tuple[ActionClass, str], path: Path
) -> None:
    raise VenuePolicyConfigError(
        f"{path}: action_class_shape declares "
        f"({present[0].value}, {present[1]}) but not its mirror "
        f"({missing[0].value}, {missing[1]}) — long/short symmetry is a repo non-negotiable "
        "(CLAUDE.md: 'Futures must preserve long/short symmetry. Entry/exit direction follows "
        "signal_direction') and a mapping that admits one direction of an action class but not "
        "its mirror is a policy error, not a narrower scope"
    )


def _check_action_class_shape_symmetry(
    shapes: dict[tuple[ActionClass, str], ActionClassShape], path: Path
) -> None:
    """Refuse an ``action_class_shape`` where a mirror pair has one arm declared but not the"""
    key_new_long = (ActionClass.NEW_LONG, "LONG")
    key_new_short = (ActionClass.NEW_SHORT, "SHORT")
    has_new_long = key_new_long in shapes
    has_new_short = key_new_short in shapes
    if has_new_long != has_new_short:
        present, missing = (
            (key_new_long, key_new_short)
            if has_new_long
            else (key_new_short, key_new_long)
        )
        _refuse_missing_mirror(present, missing, path)

    other_declared_classes = {
        action
        for action, _direction in shapes
        if action not in _DIRECTION_NAMED_ACTION_CLASSES
    }
    for action in sorted(other_declared_classes, key=lambda a: a.value):
        key_long = (action, "LONG")
        key_short = (action, "SHORT")
        has_long = key_long in shapes
        has_short = key_short in shapes
        if has_long != has_short:
            present, missing = (
                (key_long, key_short) if has_long else (key_short, key_long)
            )
            _refuse_missing_mirror(present, missing, path)


def _parse_action_class_shape(
    construction_raw: dict[str, Any], path: Path
) -> dict[tuple[ActionClass, str], ActionClassShape]:
    """Parse ``_runtime.construction.action_class_shape`` — the machine-readable form of the"""
    raw_map = require_mapping_key(construction_raw, "action_class_shape", path)
    shapes: dict[tuple[ActionClass, str], ActionClassShape] = {}
    for action_token, direction_map in raw_map.items():
        ctx = f"_runtime.construction.action_class_shape.{action_token}"
        try:
            action = ActionClass(action_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: action_class_shape key {action_token!r} is not a known ActionClass"
            ) from exc
        if not isinstance(direction_map, dict):
            raise VenuePolicyConfigError(
                f"{path}: {ctx} must be a mapping (direction -> {{side, position_effect}})"
            )
        for direction_token, entry in direction_map.items():
            if not isinstance(direction_token, str) or not direction_token.strip():
                raise VenuePolicyConfigError(
                    f"{path}: {ctx} direction key {direction_token!r} must be a non-empty string"
                )
            entry_ctx = f"{ctx}.{direction_token}"
            if not isinstance(entry, dict):
                raise VenuePolicyConfigError(f"{path}: {entry_ctx} must be a mapping")
            side = require_filled_str(entry, "side", path, entry_ctx)
            position_effect = require_filled_str(
                entry, "position_effect", path, entry_ctx
            )
            shapes[(action, direction_token)] = ActionClassShape(
                side=side, position_effect=position_effect
            )
    _check_action_class_shape_symmetry(shapes, path)
    return shapes


def _parse_effect_dimensions(
    construction_raw: dict[str, Any], path: Path
) -> tuple[EffectDimensionSpec, ...]:
    entries = require_list(
        construction_raw, "effect_dimensions", path, "_runtime.construction"
    )
    specs: list[EffectDimensionSpec] = []
    for i, entry in enumerate(entries):
        ctx = f"_runtime.construction.effect_dimensions[{i}]"
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        dimension_id = require_filled_str(entry, "dimension_id", path, ctx)
        basis_token = require_str(entry, "basis", path, ctx)
        try:
            basis = EffectBasis(basis_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.basis {basis_token!r} is not a known EffectBasis"
            ) from exc
        unit = require_filled_str(entry, "unit", path, ctx)
        scale = require_filled_str(entry, "scale", path, ctx)
        specs.append(
            EffectDimensionSpec(
                dimension_id=dimension_id, basis=basis, unit=unit, scale=scale
            )
        )
    return tuple(specs)


def _parse_construction_rules(
    raw: dict[str, Any],
    path: Path,
    *,
    environment: str,
    order_type: str,
    account: str,
    instrument: str,
) -> ConstructionRules:
    """Parse ``_runtime.construction`` into a"""
    runtime_raw = require_mapping_key(raw, "_runtime", path)
    construction_raw = require_mapping_key(runtime_raw, "construction", path)
    sizing_bound = _parse_sizing(construction_raw, path)
    authorized_axes = _build_authorized_axes(
        construction_raw,
        path,
        environment=environment,
        order_type=order_type,
        account=account,
        instrument=instrument,
    )
    action_class_shape = _parse_action_class_shape(construction_raw, path)
    effect_dimensions = _parse_effect_dimensions(construction_raw, path)
    return ConstructionRules(
        sizing_bound=sizing_bound,
        admitted_quantity_bases=sizing_bound.admitted_quantity_bases,
        authorized_axes=authorized_axes,
        action_class_shape=action_class_shape,
        effect_dimensions=effect_dimensions,
    )


def load_order_construction_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedOrderConstructionPolicy:
    """Load, fail-closed-validate, and kernel-issue an Order Construction"""
    raw = load_mapping(path, "order construction policy")
    require_exact_str(raw, "artifact_type", _OCP_ARTIFACT_TYPE, path, "policy")
    require_exact_str(raw, "schema_version", ACCEPTED_SCHEMA_VERSION, path, "policy")
    require_issued_status(raw, path)
    policy_id = require_filled_str(raw, "policy_id", path, "policy")
    policy_generation = require_int(raw, "policy_generation", path, "policy")
    require_nullable_str_key_present(raw, "effective_from", path, "policy")
    require_nullable_str_key_present(raw, "review_due", path, "policy")
    construction_generation = optional_int(
        raw, "construction_generation", path, "policy"
    )

    environment, order_type, account, instrument = _parse_ocp_scope(raw, path)
    policy_version = _parse_ocp_model_view(
        raw, path, top_level_policy_generation=policy_generation
    )
    canonicalization_version, wire_codec_kind, wire_fields = _parse_ocp_runtime_block(
        raw, path, scheme=scheme
    )
    construction_rules = _parse_construction_rules(
        raw,
        path,
        environment=environment,
        order_type=order_type,
        account=account,
        instrument=instrument,
    )

    require_template_shape(
        raw,
        path,
        list_keys=_OCP_TEMPLATE_LIST_KEYS,
        mapping_keys=TEMPLATE_MAPPING_KEYS,
    )

    policy = _issue_ocp_policy(
        raw,
        path,
        scheme=scheme,
        policy_id=policy_id,
        policy_generation=policy_generation,
        policy_version=policy_version,
    )

    return LoadedOrderConstructionPolicy(
        policy=policy,
        canonicalization_version=canonicalization_version,
        wire_codec_kind=wire_codec_kind,
        wire_fields=wire_fields,
        construction_generation=construction_generation,
        construction_rules=construction_rules,
    )
