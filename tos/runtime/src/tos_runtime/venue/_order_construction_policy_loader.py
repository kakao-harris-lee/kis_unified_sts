"""tos_runtime.venue._order_construction_policy_loader — the Order
Construction Policy half of ``tos_runtime.venue.config`` (split out purely
for that module's own size budget — ``config/tos_size_budget.yaml``, module
ceiling 1000 lines; no behavioural difference from having this inline
there).

See :mod:`tos_runtime.venue.config`'s own module docstring for the full
``_model_view``/``_runtime`` discipline, the single-live-scope rule, and the
``canonical_digest`` tamper/stale cross-check.

**Kernel round #4 K-3.** ``signer_identity``/``approval_identity``/``evidence_package_ref``
are now READ from the instance document's own top-level keys (:func:`optional_str`) and
threaded into ``OrderConstructionPolicy.issue`` — previously this loader hardcoded all three to
``None`` regardless of what (if anything) the document declared. Every deployed instance today
leaves them ``null`` (a genuinely unbound coordinate, not a fabricated value — the operator has
not yet approved a signer/approval/evidence-package source), so today's digest is unchanged;
filling one in a future generation binds it into the issued policy's digest for the first time.

**(a′) wave, lane A** (``docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md``
§4 lane A; values per ``docs/plans/2026-09-16-tos-ocp-sizing-values-proposal.md``,
adopted by the operator 2026-09-16). Prior to this wave the OCP instance stated its
construction rules as **prose only** (``direction_side_and_position_effect_rules``,
``price_tick_lot_quantity_and_rounding_rules``, …) and ``_runtime`` carried only
``canonicalization_version``/``wire_codec``. This module adds a THIRD ``_runtime`` sibling
block, ``construction``, that makes those same prose rules machine-readable into
:class:`~tos_runtime.venue.construction_rules.ConstructionRules` (the (a′) wave's committed,
lane-A-read-only contract) — a **new policy generation** (``policy_generation: 2``), not a
field bolted onto generation 1, on the operational convention that a governed policy's content
does not change silently under an unchanged generation number. Every leaf here is fail-closed
exactly like every other ``_runtime``/``_model_view`` leaf this module already reads: a missing
``_runtime.construction`` block, a still-``TBD``/``null`` leaf, or a malformed value refuses the
load — with the ONE documented exception (:func:`_parse_sizing`'s ``max_notional``, which is an
OPTIONAL ceiling and legitimately ``null``, per ``SizingBound``'s own consuming code at
``egressgw/construction.py:525``, guarded ``is not None``).

⚠ **The generation bump above is convention, not something this loader's ``canonical_digest``
check mechanically enforces.** DR-0002 §2.3's coverage table is explicit: the OCP row's kernel
digest covers identity/generation/version only — ``policy_id`` / ``policy_generation`` /
``policy_version`` (``_REQUIRED_COVERED``) — and nothing else. ``_runtime`` content, including
every leaf :func:`_parse_construction_rules` reads, sits OUTSIDE that coverage. So an editor who
changes ``_runtime.construction.sizing.max_quantity`` (or any other construction leaf) while
leaving ``policy_generation`` unchanged passes :func:`~tos_runtime.venue._policy_primitives
.check_canonical_digest` silently — the tamper/stale check never looks at that content, so it
has nothing to fire on. Treat the generation bump as a discipline this module's callers must
keep by hand, not a guarantee this loader verifies.

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
#: ``environment``/``order_type``/``account``/``instrument`` are all four returned and threaded
#: into ``authorized_axes`` (review round 2026-09-16, PR #719 — ACCOUNT/INSTRUMENT were
#: previously validated for shape but silently never derived into an axis binding, the same
#: class of gap DIRECTION's own absence surfaced); only ``broker`` has no (a′) consumer yet,
#: matching every other loader in this package that validates a coordinate without threading it
#: through.
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

#: The four axes :func:`_build_authorized_axes` derives from ``scope`` rather than reading from
#: an authored ``_runtime.construction.axes`` entry — re-declaring any of them there would
#: restate a fact ``scope.environments``/``scope.order_types``/``scope.accounts``/
#: ``scope.instruments`` already carries and risk the two drifting apart (plan §2 decision 1's
#: "read the values OCP already declares" instinct, applied to axes too). ACCOUNT/INSTRUMENT
#: joined ENVIRONMENT/ORDER_TYPE here in the review round that caught DIRECTION missing
#: entirely (PR #719) — the same audit ("is every axis the contract names present in ``axes:``
#: or genuinely derived from ``scope``?") turned up that these two were silently absent too.
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


def _parse_ocp_scope(raw: dict[str, Any], path: Path) -> tuple[str, str, str, str]:
    """Validate the OCP ``scope`` block's shape and return the four singleton coordinates the
    (a′) wave's ``authorized_axes`` derivation consumes (``environment``, ``order_type``,
    ``account``, ``instrument``, in that order) — every other scope key is validated for shape
    only and discarded, as before. ``action_classes`` is validated against the kernel
    ``ActionClass`` enum (team-lead review MEDIUM, 2026-09-15 — the same check the venue-policy
    loader already runs, previously missing here entirely: an OCP document with an
    unknown/misspelled ``action_classes`` token loaded silently); that result is still
    discarded — OCP runs no ``action_classes`` cross-check.
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
    """Read the three OCP covered fields ``OrderConstructionPolicy._COVERED_FIELDS`` already
    declares (kernel round #4 K-3; ``ioc/records.py:277-285``) — ``signer_identity``,
    ``approval_identity``, ``evidence_package_ref`` — issue the kernel policy, and verify its
    ``canonical_digest`` against the document. Split out of
    :func:`load_order_construction_policy` purely for that function's own 100-line size
    budget (``config/tos_size_budget.yaml``) — no behavioural difference from having this
    inline there."""
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
    """Parse ``_runtime.construction.sizing`` into a kernel
    :class:`~tos.egressgw.SizingBound`.

    Every leaf below refuses on missing/``null``/malformed EXCEPT
    ``max_notional``: it is an OPTIONAL governance ceiling
    (``egressgw/construction.py:525`` guards it ``is not None`` — a bound
    ``None`` there is simply "no notional ceiling", not a denial), so
    ``null`` is accepted and legitimate (proposal table §2, ``max_notional``
    row).

    ``SizingBound.quantity_unit`` is DELIBERATELY left ``None`` here — not a gap to fill later,
    a boundary the OCP loader must not cross. The OCP document carries no quantity-unit fact of
    its own; the Venue Constraint Policy's own ``_runtime.quantity_unit``
    (:attr:`~tos_runtime.venue._venue_policy_loader.VenuePolicyScope.quantity_unit`) already IS
    that fact. If OCP declared a second one, the two would be the same value written in two YAML
    files with nothing pinning them to each other — the "registry with an unpinned satellite"
    class this repo keeps getting bitten by (``derive_order_size``,
    ``egressgw/construction.py:456``, already denies on exactly that disagreement:
    ``venue_constraint.quantity_unit is not bound.quantity_unit``). The wiring that assembles the
    final envelope (lane B/D) is expected to take the VCP-loaded value and fill it in there, so
    the two agree BY CONSTRUCTION — one source, read once — never by keeping two declarations in
    sync by hand.
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
    construction_raw: dict[str, Any],
    path: Path,
    *,
    environment: str,
    order_type: str,
    account: str,
    instrument: str,
) -> tuple[AxisBinding, ...]:
    """Build the envelope's non-derived authorized axis bindings: ``ENVIRONMENT``/
    ``ORDER_TYPE``/``ACCOUNT``/``INSTRUMENT`` are DERIVED from ``scope.environments``/
    ``scope.order_types``/``scope.accounts``/``scope.instruments`` (never restated under
    ``_runtime.construction.axes`` — see ``_AUTHORIZED_AXES_DERIVED_FROM_SCOPE``), every other
    axis the contract names (``DIRECTION``, ``TIF``) is authored explicitly there — neither has
    a ``scope.*`` home to derive from. A :data:`~tos.egressgw.DERIVED_AXES` member
    (``QUANTITY``/``PRICE``/``UNIT``) in the authored list refuses at load, with a clearer
    message than the kernel envelope validator's own later refusal
    (``ProposedConstructionEnvelope._no_derived_axis_is_pre_declared``, ADR-002-020 §10:284
    "ambiguity is denial") would give — the whole point of catching it here is not letting a
    document author discover this only when step 2 denies at runtime. An authored value that is
    still the template's own ``"TBD"`` placeholder refuses too, the same as every other
    operator-fill leaf this loader reads (e.g. ``DIRECTION: "TBD"`` on the shipped paper
    instance — no operator decision has bound this single, static composition to one trading
    direction yet, and passing that placeholder through as a real value would silently commit
    to one side of the long/short symmetry non-negotiable rather than refusing until an operator
    actually decides).

    ``SIDE`` is one of the seven axes :class:`~tos_runtime.venue.construction_rules
    .ConstructionRules`'s own ``authorized_axes`` docstring names, but this function does NOT
    derive or accept one: lane C's ``_shape_side_and_position_effect``
    (``tos_runtime/compose/_venue_wiring.py``) reads side from ``action_class_shape`` via the
    ``(action_class, direction)`` lookup, not from ``authorized_axes`` — no consumer reads a
    ``SIDE`` axis binding at all today. Adding one here would be a second, unconsulted
    declaration of the very same fact ``action_class_shape`` already derives per attempt —
    exactly the "two quantities" duplication class this wave exists to remove, applied to side
    instead of quantity. Left unresolved deliberately; flagged for the team lead / lane
    B rather than special-cased here.
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


#: ActionClass members whose NAME ITSELF encodes a trading direction — the CROSS-class mirror
#: shape: a ``NEW_LONG`` entry only ever makes sense at direction ``LONG`` (there is no
#: "NEW_LONG at direction SHORT"), so the mirror of a declared ``(NEW_LONG, LONG)`` is a declared
#: ``(NEW_SHORT, SHORT)``, never a second direction of ``NEW_LONG`` itself.
#:
#: Every OTHER ``ActionClass`` member — all 11 of the remaining 13 (``CLOSE``, ``INCREASE``,
#: ``DECREASE``, ``REVERSAL``, ``CANCEL``, ``AMEND``, ``REPLACE``, ``REDUCE_ONLY``,
#: ``PROTECTIVE``, ``EMERGENCY``, ``ROUTING_ALTERNATIVE`` — verified against ``tos.venue
#: .ActionClass`` directly) — is direction-agnostic BY NAME: if declared for one direction it
#: must be declared for the other, checked generically in :func:`_check_action_class_shape_symmetry`
#: with NO per-class table. An earlier revision of this check named only ``CLOSE`` in a second,
#: explicit mirror-pair table alongside this one — independent review (PR #719) designed a
#: mutation that declared a one-sided ``INCREASE`` entry and the loader loaded it anyway,
#: because ``INCREASE`` was not in that table. A table a future ``ActionClass`` member must be
#: remembered into is exactly the "registry with an unpinned satellite" class this repo has
#: already been bitten by; the fix closes the CLASS OF BUG, not the one instance — the general
#: rule below covers all 11 automatically, including any member added to the enum later, with no
#: code change here.
#:
#: "LONG"/"SHORT" are hardcoded here deliberately, not read from a kernel enum: no
#: ``DirectionKind`` enum exists (direction is a Phase-0-instance-injected axis value, like
#: ORDER_TYPE/TIF/ENVIRONMENT), and CLAUDE.md's own non-negotiable text ("Futures must preserve
#: long/short symmetry") already commits the repo to exactly these two tokens.
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
    """Refuse an ``action_class_shape`` where a mirror pair has one arm declared but not the
    other (see :func:`_refuse_missing_mirror`).

    **The within-class rule is deliberately UNIFORM across all 11 non-direction-named
    ``ActionClass`` members — no per-class exception list, on purpose** (PR #719 delta review,
    MEDIUM disposition, 2026-09-16). A fair reading of the rule: for order-management classes
    that reference an EXISTING order (``CANCEL``/``AMEND``/``REPLACE``) and the undocumented
    ``ROUTING_ALTERNATIVE``, a per-direction side may not be a meaningful fact at all, so a
    future author declaring one of them could be forced to invent a mirror entry — the same
    fabrication pattern this wave exists to prevent (see :data:`_DIRECTION_NAMED_ACTION_CLASSES`
    and the ``ConstructionRules.action_class_shape`` docstring on why a table was rejected here
    once already: PR #719's own HIGH finding, a per-class allowlist that a future ``ActionClass``
    member must be remembered into).

    The fix is NOT a second table naming which classes are exempt — that reintroduces exactly
    the "registry with an unpinned satellite" defect class this repo keeps getting bitten by,
    just for the exemption list instead of the mirror-pair list. So the rule stays uniform, and
    its known failure mode is **over-refusal**, deliberately the safe direction: an author who
    genuinely needs to declare ``CANCEL``/``AMEND``/``REPLACE``/``ROUTING_ALTERNATIVE`` hits a
    refusal here and has to decide whether direction is a meaningful fact for that class — the
    right prompt to raise as a design question, not a signal to reach for an exemption. Nothing
    declares those four today, so the present cost of leaving this uniform is zero.
    """
    # Cross-class mirror: NEW_LONG <-> NEW_SHORT (see _DIRECTION_NAMED_ACTION_CLASSES).
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

    # Within-class mirror: every OTHER declared class, checked generically against exactly the
    # two LONG/SHORT tokens — no table, no per-class allowlist (see the data note above).
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
    """Parse ``_runtime.construction.action_class_shape`` — the machine-readable form of the
    document's own ``direction_side_and_position_effect_rules`` prose. YAML shape: a mapping of
    ``ActionClass`` token -> mapping of ``direction`` token -> ``{side, position_effect}``
    (nested, not a flattened tuple key — YAML mapping keys are strings). Refuses when a mirror
    pair (see :func:`_check_action_class_shape_symmetry`) has one arm declared but not the
    other: "Futures must preserve long/short symmetry" (``CLAUDE.md``) is a repo non-negotiable,
    and an asymmetric mapping is a policy defect, not a narrower scope."""
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
    """Load, fail-closed-validate, and kernel-issue an Order Construction
    Policy INSTANCE document from ``path`` (an instance of
    ``ORDER-CONSTRUCTION-POLICY-template.yaml`` — see
    :mod:`tos_runtime.venue.config`'s own module docstring;
    ``signer_identity``/``approval_identity``/``evidence_package_ref`` are
    read from the document (kernel round #4 K-3) and passed through to the
    kernel's own ``OrderConstructionPolicy.issue`` unchanged — a document
    that leaves them ``null`` (every instance today) issues the exact same
    digest as before this round).

    Raises:
        VenuePolicyConfigError: the file is missing/unreadable/not valid
            YAML/not a mapping; ``artifact_type``/``schema_version`` do not
            match the accepted constants; ``status`` is not ``ISSUED``;
            ``policy_id``/``policy_generation`` are absent, ``null``, or
            still ``"TBD"``; ``signer_identity``/``approval_identity``/
            ``evidence_package_ref`` is present-but-not-a-string (``null`` is
            accepted); ``canonical_digest`` is present but does not
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
            (``QUANTITY``/``PRICE``/``UNIT``), restates ``ENVIRONMENT``/
            ``ORDER_TYPE``/``ACCOUNT``/``INSTRUMENT`` (all four derived from
            ``scope`` instead), or carries the template placeholder
            ``"TBD"`` as its value;
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
