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

Firewall (R1, runtime scope): stdlib + ``tos.*`` only — no ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos.canonical import CanonicalizationScheme
from tos.ioc import OrderConstructionPolicy

from tos_runtime.venue._policy_primitives import (
    ACCEPTED_SCHEMA_VERSION,
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

#: The OCP ``scope`` block's single-live-scope list keys (OCP does not
#: require a single ``venues``/``market_segments`` entry, unlike the venue
#: policy loader).
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


def _parse_ocp_scope(raw: dict[str, Any], path: Path) -> None:
    """Validate the OCP ``scope`` block's shape — nothing is stored from it;
    the loader's typed content lives in ``_model_view``/``_runtime`` only.
    ``action_classes`` is validated against the kernel ``ActionClass`` enum
    (team-lead review MEDIUM, 2026-09-15 — the same check the venue-policy
    loader already runs, previously missing here entirely: an OCP document
    with an unknown/misspelled ``action_classes`` token loaded silently).
    The result is discarded — OCP runs no cross-check against it."""
    scope_raw = require_mapping_key(raw, "scope", path)
    for key in _OCP_SCOPE_SINGLETON_KEYS:
        require_singleton_list_str(scope_raw, key, path, "scope")
    for key in _OCP_SCOPE_LIST_KEYS:
        entries = require_list(scope_raw, key, path, "scope")
        require_str_list(entries, path, f"scope.{key}")
    parse_action_classes(scope_raw, path, "scope")


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
            does not carry exactly one string; ``_model_view
            .policy_generation`` does not equal the top-level
            ``policy_generation``; ``_runtime.canonicalization_version``
            does not equal ``scheme.version``; ``_runtime.wire_codec`` is
            present but malformed; ``scope.action_classes`` carries an
            unknown ``ActionClass`` token; ``effective_from``/``review_due``
            is absent (may be ``null``, but the key itself must be present)
            or present-and-not-``null``-and-not-a-string; or any template
            rule-list/``authority``/``evidence`` key is absent or not
            list/mapping-shaped.
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

    _parse_ocp_scope(raw, path)
    policy_version = _parse_ocp_model_view(
        raw, path, top_level_policy_generation=policy_generation
    )
    canonicalization_version, wire_codec_kind, wire_fields = _parse_ocp_runtime_block(
        raw, path, scheme=scheme
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
    )
