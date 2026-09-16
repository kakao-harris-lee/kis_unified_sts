"""tos_runtime.venue._order_construction_policy_loader — the Order
Construction Policy half of ``tos_runtime.venue.config`` (split out purely
for that module's own size budget — ``config/tos_size_budget.yaml``, module
ceiling 1000 lines; no behavioural difference from having this inline
there).

See :mod:`tos_runtime.venue.config`'s own module docstring for the full
``_model_view``/``_runtime`` discipline, the single-live-scope rule, the
``canonical_digest`` tamper/stale cross-check, and the deliberate
``signer_identity``/``approval_identity``/``evidence_package_ref`` ``None``
choice this module implements for the Order Construction Policy INSTANCE
document specifically.

**(a′) wave, lane A** (``docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md``
§4 lane A; values per ``docs/plans/2026-09-16-tos-ocp-sizing-values-proposal.md``,
adopted by the operator 2026-09-16). Prior to this wave the OCP instance stated its
construction rules as **prose only** (``direction_side_and_position_effect_rules``,
``price_tick_lot_quantity_and_rounding_rules``, …) and ``_runtime`` carried only
``canonicalization_version``/``wire_codec``. This module adds a THIRD ``_runtime`` sibling
block, ``construction``, that makes those same prose rules machine-readable into
:class:`~tos_runtime.venue.construction_rules.ConstructionRules` (the (a′) wave's committed,
lane-A-read-only contract) — a **new policy generation** (``policy_generation: 2``), not a
field bolted onto generation 1, because a governed policy's content is generation-immutable
(this module's own ``canonical_digest`` tamper/stale check is exactly that discipline). Every
leaf here is fail-closed exactly like every other ``_runtime``/``_model_view`` leaf this module
already reads: a missing ``_runtime.construction`` block, a still-``TBD``/``null`` leaf, or a
malformed value refuses the load — with the ONE documented exception
(:func:`_parse_sizing`'s ``max_notional``, which is an OPTIONAL ceiling and legitimately
``null``, per ``SizingBound``'s own consuming code at ``egressgw/construction.py:525``, guarded
``is not None``).

Firewall (R1, runtime scope): stdlib + ``tos.*`` only — no ``shared.*``.
"""

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

#: The runtime INSTANCE file name (distinct from the tos-spec TEMPLATE file
#: name — this is what an environment's config directory actually carries).
ORDER_CONSTRUCTION_POLICY_CONFIG_NAME = "order_construction_policy.yaml"

_OCP_ARTIFACT_TYPE = "ORDER_CONSTRUCTION_POLICY"

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

#: The OCP ``scope`` block's single-live-scope list keys. ``order_types`` joined this set in
#: the (a′) wave (previously an unrestricted, uninterpreted list — ``config.py``'s own module
#: docstring said so): :func:`_build_authorized_axes` now DERIVES the ``ORDER_TYPE`` conformance
#: axis binding from it, and a derived axis needs exactly one authoritative value, the same
#: reason ``environments``/``brokers``/``accounts``/``instruments`` are singletons already.
_OCP_SCOPE_SINGLETON_KEYS: tuple[str, ...] = (
    "environments",
    "brokers",
    "accounts",
    "instruments",
    "order_types",
)

#: ``_parse_ocp_scope``'s return-tuple field names, in ``_OCP_SCOPE_SINGLETON_KEYS`` order —
#: only ``environment``/``order_type`` are actually returned (the other three are validated for
#: shape but have no (a′) consumer yet, matching every other loader in this package that
#: validates a coordinate without threading it through).
_OCP_SCOPE_SINGLETON_FIELD_NAMES: tuple[str, ...] = (
    "environment",
    "broker",
    "account",
    "instrument",
    "order_type",
)

#: The OCP ``scope`` block's remaining explicit-list keys (any length).
_OCP_SCOPE_LIST_KEYS: tuple[str, ...] = (
    "safety_cells",
    "venues",
    "market_segments",
    "contracts",
)

#: :class:`~tos.egressgw.SizingBound`'s required (never-``null``) numeric leaves under
#: ``_runtime.construction.sizing`` — everything EXCEPT ``max_notional`` (optional ceiling,
#: :func:`_parse_sizing`) and ``lot_rounding``/``admitted_quantity_bases`` (non-numeric, parsed
#: separately). Order matches the operator-adopted proposal table
#: (``docs/plans/2026-09-16-tos-ocp-sizing-values-proposal.md`` §2).
_SIZING_REQUIRED_INT_FIELDS: tuple[str, ...] = (
    "max_quantity",
    "min_quantity",
    "lot_size",
    "risk_budget",
    "per_unit_risk",
)

#: The two axes :func:`_build_authorized_axes` derives from ``scope`` rather than reading from
#: an authored ``_runtime.construction.axes`` entry — re-declaring either there would restate a
#: fact ``scope.environments``/``scope.order_types`` already carries and risk the two drifting
#: apart (plan §2 decision 1's "read the values OCP already declares" instinct, applied to axes
#: too).
_AUTHORIZED_AXES_DERIVED_FROM_SCOPE: frozenset[ConformanceAxis] = frozenset(
    {ConformanceAxis.ENVIRONMENT, ConformanceAxis.ORDER_TYPE}
)


@dataclass(frozen=True)
class LoadedOrderConstructionPolicy:
    """A loaded, kernel-issued Order Construction Policy plus its wire-codec
    declaration, its own document ``construction_generation`` (plan §4.1 +
    team-lead correction 2026-09-15), and its (a′)-wave
    :class:`~tos_runtime.venue.construction_rules.ConstructionRules` — the
    machine-readable form of the same construction rules the document's own
    prose rule-lists already state."""

    policy: OrderConstructionPolicy
    canonicalization_version: str
    wire_codec_kind: str | None
    wire_fields: frozenset[str]
    construction_generation: int | None
    construction_rules: ConstructionRules


def _parse_ocp_scope(raw: dict[str, Any], path: Path) -> tuple[str, str]:
    """Validate the OCP ``scope`` block's shape and return the two singleton coordinates the
    (a′) wave's ``authorized_axes`` derivation consumes (``environment``, ``order_type``) —
    every other scope key is validated for shape only and discarded, as before.
    ``action_classes`` is validated against the kernel ``ActionClass`` enum (team-lead review
    MEDIUM, 2026-09-15 — the same check the venue-policy loader already runs, previously missing
    here entirely: an OCP document with an unknown/misspelled ``action_classes`` token loaded
    silently); that result is still discarded — OCP runs no ``action_classes`` cross-check.
    """
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
    return singletons["environment"], singletons["order_type"]


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
    return require_str(mv_raw, "policy_version", path, "_model_view")


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
    """Parse ``_runtime.construction.sizing`` into a kernel
    :class:`~tos.egressgw.SizingBound`.

    Every leaf below refuses on missing/``null``/malformed EXCEPT
    ``max_notional``: it is an OPTIONAL governance ceiling
    (``egressgw/construction.py:525`` guards it ``is not None`` — a bound
    ``None`` there is simply "no notional ceiling", not a denial), so
    ``null`` is accepted and legitimate (proposal table §2, ``max_notional``
    row). ``SizingBound.quantity_unit`` is deliberately left ``None`` here —
    the OCP document carries no quantity-unit fact (the venue policy's own
    ``_runtime.quantity_unit`` is that source); a consumer that assembles the
    final envelope is expected to fill it from there, not invent one here.
    """
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
    construction_raw: dict[str, Any], path: Path, *, environment: str, order_type: str
) -> tuple[AxisBinding, ...]:
    """Build the envelope's non-derived authorized axis bindings: ``ENVIRONMENT``/
    ``ORDER_TYPE`` are DERIVED from ``scope.environments``/``scope.order_types`` (never
    restated under ``_runtime.construction.axes`` — see
    ``_AUTHORIZED_AXES_DERIVED_FROM_SCOPE``), every other axis (e.g. ``TIF``) is authored
    explicitly there. A :data:`~tos.egressgw.DERIVED_AXES` member
    (``QUANTITY``/``PRICE``/``UNIT``) in the authored list refuses at load, with a clearer
    message than the kernel envelope validator's own later refusal
    (``ProposedConstructionEnvelope._no_derived_axis_is_pre_declared``, ADR-002-020 §10:284
    "ambiguity is denial") would give — the whole point of catching it here is not letting a
    document author discover this only when step 2 denies at runtime.
    """
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
                f"{path}: {ctx} restates {axis.value}, which is derived from "
                "scope.environments/scope.order_types — do not re-declare it under "
                "_runtime.construction.axes (a second declaration risks drifting apart "
                "from the scope value)"
            )
        value = require_str(entry, "value", path, ctx)
        authored.append(AxisBinding(axis=axis, value=value))
    derived = (
        AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value=environment),
        AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value=order_type),
    )
    return derived + tuple(authored)


def _parse_action_class_shape(
    construction_raw: dict[str, Any], path: Path
) -> dict[ActionClass, ActionClassShape]:
    """Parse ``_runtime.construction.action_class_shape`` — the machine-readable form of the
    document's own ``direction_side_and_position_effect_rules`` prose. Refuses a mapping that
    declares ``NEW_LONG`` without its ``NEW_SHORT`` mirror (or vice versa): "Futures must
    preserve long/short symmetry" (``CLAUDE.md``) is a repo non-negotiable, and an asymmetric
    mapping is a policy defect, not a narrower scope."""
    raw_map = require_mapping_key(construction_raw, "action_class_shape", path)
    shapes: dict[ActionClass, ActionClassShape] = {}
    for token, entry in raw_map.items():
        ctx = f"_runtime.construction.action_class_shape.{token}"
        try:
            action = ActionClass(token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: action_class_shape key {token!r} is not a known ActionClass"
            ) from exc
        if not isinstance(entry, dict):
            raise VenuePolicyConfigError(f"{path}: {ctx} must be a mapping")
        side = require_str(entry, "side", path, ctx)
        position_effect = require_str(entry, "position_effect", path, ctx)
        direction = require_str(entry, "direction", path, ctx)
        shapes[action] = ActionClassShape(
            side=side, position_effect=position_effect, direction=direction
        )
    has_long = ActionClass.NEW_LONG in shapes
    has_short = ActionClass.NEW_SHORT in shapes
    if has_long != has_short:
        present, missing = (
            (ActionClass.NEW_LONG, ActionClass.NEW_SHORT)
            if has_long
            else (ActionClass.NEW_SHORT, ActionClass.NEW_LONG)
        )
        raise VenuePolicyConfigError(
            f"{path}: action_class_shape declares {present.value} but not its "
            f"{missing.value} mirror — long/short symmetry is a repo non-negotiable "
            "(CLAUDE.md: 'Futures must preserve long/short symmetry. Entry/exit direction "
            "follows signal_direction') and a mapping that admits one side but not the "
            "other is a policy error, not a narrower scope"
        )
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
        dimension_id = require_str(entry, "dimension_id", path, ctx)
        basis_token = require_str(entry, "basis", path, ctx)
        try:
            basis = EffectBasis(basis_token)
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.basis {basis_token!r} is not a known EffectBasis"
            ) from exc
        unit = require_str(entry, "unit", path, ctx)
        scale = require_str(entry, "scale", path, ctx)
        specs.append(
            EffectDimensionSpec(
                dimension_id=dimension_id, basis=basis, unit=unit, scale=scale
            )
        )
    return tuple(specs)


def _parse_construction_rules(
    raw: dict[str, Any], path: Path, *, environment: str, order_type: str
) -> ConstructionRules:
    """Parse ``_runtime.construction`` into a
    :class:`~tos_runtime.venue.construction_rules.ConstructionRules` — the (a′) wave's whole
    point: making machine-readable what the document's rule-list prose above already states.
    A missing ``_runtime.construction`` block refuses like every other required ``_runtime``
    sibling (``construction_rules.py`` docstring: "types only ... lane A fills these from the
    OCP document")."""
    runtime_raw = require_mapping_key(raw, "_runtime", path)
    construction_raw = require_mapping_key(runtime_raw, "construction", path)
    sizing_bound = _parse_sizing(construction_raw, path)
    authorized_axes = _build_authorized_axes(
        construction_raw, path, environment=environment, order_type=order_type
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
    """Load, fail-closed-validate, and kernel-issue an Order Construction
    Policy INSTANCE document from ``path`` (an instance of
    ``ORDER-CONSTRUCTION-POLICY-template.yaml`` — see
    :mod:`tos_runtime.venue.config`'s own module docstring;
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
            (``environments``/``brokers``/``accounts``/``instruments``/
            ``order_types``) does not carry exactly one non-empty,
            non-``"TBD"`` string; ``_model_view.policy_generation`` does not
            equal the top-level ``policy_generation``; ``_runtime
            .canonicalization_version`` does not equal ``scheme.version``;
            ``_runtime.wire_codec`` is present but malformed;
            ``scope.action_classes`` carries an unknown ``ActionClass``
            token; ``effective_from``/``review_due`` is absent (may be
            ``null``, but the key itself must be present) or
            present-and-not-``null``-and-not-a-string; any template
            rule-list/``authority``/``evidence`` key is absent or not
            list/mapping-shaped; OR (a′) wave) ``_runtime.construction`` is
            absent or any of its leaves is missing/``null``/malformed EXCEPT
            ``sizing.max_notional`` (an optional ceiling — ``null`` is
            accepted); ``sizing.admitted_quantity_bases`` contains the
            template placeholder ``"TBD"``; ``sizing.lot_rounding`` is not a
            known ``LotRoundingPolicy``; an ``axes`` entry names an unknown
            ``ConformanceAxis``, a :data:`~tos.egressgw.DERIVED_AXES` member
            (``QUANTITY``/``PRICE``/``UNIT``), or restates ``ENVIRONMENT``/
            ``ORDER_TYPE`` (both derived from ``scope`` instead);
            ``action_class_shape`` names an unknown ``ActionClass`` or
            declares ``NEW_LONG``/``NEW_SHORT`` without its mirror; or an
            ``effect_dimensions`` entry names an unknown ``EffectBasis``.
    """
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

    environment, order_type = _parse_ocp_scope(raw, path)
    policy_version = _parse_ocp_model_view(
        raw, path, top_level_policy_generation=policy_generation
    )
    canonicalization_version, wire_codec_kind, wire_fields = _parse_ocp_runtime_block(
        raw, path, scheme=scheme
    )
    construction_rules = _parse_construction_rules(
        raw, path, environment=environment, order_type=order_type
    )

    require_template_shape(
        raw,
        path,
        list_keys=_OCP_TEMPLATE_LIST_KEYS,
        mapping_keys=TEMPLATE_MAPPING_KEYS,
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
    check_canonical_digest(raw, path, policy.canonical_digest, "policy")

    return LoadedOrderConstructionPolicy(
        policy=policy,
        canonicalization_version=canonicalization_version,
        wire_codec_kind=wire_codec_kind,
        wire_fields=wire_fields,
        construction_generation=construction_generation,
        construction_rules=construction_rules,
    )
