"""Field-level parsing for the broker-scopes config — the layer BELOW the scope"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from tos.brokercap import (
    AssetScope,
    AssuranceLevel,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityDimension,
    CapabilityProvenance,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
    ProbeManifest,
    ProfileKey,
    ProvenanceClass,
    RequiredCapabilitySet,
)
from tos.brokercap.records import BrokerEvidenceRef

from tos_runtime._named_tbd import reject_named_tbd

__all__ = [
    "BrokerScopeConfigError",
    "as_str",
    "build_capability_tuple",
    "build_evidence_ref",
    "build_profile_key",
    "build_required_capability_set",
    "build_provenance",
    "reject_named_tbd_field",
    "require",
]


class BrokerScopeConfigError(Exception):
    """Raised when the broker-scopes config is missing, malformed, carries an"""


def require(value: Any, field: str, context: str) -> Any:
    if value is None:
        raise BrokerScopeConfigError(
            f"{context}: {field!r} is still null (named-TBD) — refusing to load"
        )
    return value


def reject_named_tbd_field(value: Any, field: str, context: str) -> None:
    reject_named_tbd(
        value, field=field, context=context, error_cls=BrokerScopeConfigError
    )


def as_str(value: Any) -> str:
    """Narrow an untyped YAML value to ``str`` for enum/model construction —"""
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {value!r}")
    return value


def build_capability_tuple(raw: Mapping[str, Any], scope_name: str) -> CapabilityTuple:
    """Validated construction only (never ``model_construct``) — a"""
    try:
        return CapabilityTuple(
            environment=BrokerEnvironment(as_str(raw.get("environment"))),
            operation_class=OperationClass(as_str(raw.get("operation_class"))),
            economic_effect=EconomicEffect(as_str(raw.get("economic_effect"))),
            asset_scope=AssetScope(as_str(raw.get("asset_scope"))),
            authorization_class=AuthorizationClass(
                as_str(raw.get("authorization_class"))
            ),
        )
    except (ValueError, ValidationError) as exc:
        raise BrokerScopeConfigError(
            f"scope {scope_name!r}: capability tuple rejected by the kernel — {exc}"
        ) from exc


def build_evidence_ref(raw: Mapping[str, Any] | None) -> BrokerEvidenceRef | None:
    if raw is None:
        return None
    return BrokerEvidenceRef(
        evidence_id=raw.get("evidence_id"),
        generation=raw.get("generation"),
        digest=raw.get("digest"),
        environment=raw.get("environment"),
    )


def build_provenance(raw: Mapping[str, Any], scope_name: str) -> CapabilityProvenance:
    manifest_raw = raw.get("probe_manifest")
    manifest: ProbeManifest | None = None
    if manifest_raw is not None:
        try:
            manifest = ProbeManifest(
                emits_orders=manifest_raw.get("emits_orders", False),
                allowed_methods=tuple(manifest_raw.get("allowed_methods") or ()),
                retention=manifest_raw.get("retention"),
                ttl=manifest_raw.get("ttl"),
                provenance=manifest_raw.get("provenance"),
            )
        except ValidationError as exc:
            raise BrokerScopeConfigError(
                f"scope {scope_name!r}: probe manifest rejected by the kernel — {exc}"
            ) from exc
    try:
        source_ref = as_str(raw.get("source_ref"))
        captured_at = as_str(raw.get("captured_at"))
        context = f"scope {scope_name!r}: provenance"
        reject_named_tbd_field(source_ref, "source_ref", context)
        reject_named_tbd_field(captured_at, "captured_at", context)
        return CapabilityProvenance(
            provenance_class=ProvenanceClass(as_str(raw.get("provenance_class"))),
            source_ref=source_ref,
            captured_at=captured_at,
            evidence_ref=build_evidence_ref(raw.get("evidence_ref")),
            probe_manifest=manifest,
        )
    except (ValueError, ValidationError) as exc:
        raise BrokerScopeConfigError(
            f"scope {scope_name!r}: provenance rejected by the kernel — {exc}"
        ) from exc


def build_profile_key(raw: Mapping[str, Any] | None) -> ProfileKey:
    raw = raw or {}
    return ProfileKey(
        broker_id=raw.get("broker_id"),
        api_product=raw.get("api_product"),
        api_version=raw.get("api_version"),
        environment=raw.get("environment"),
        account_type=raw.get("account_type"),
        market=raw.get("market"),
        instrument_class=raw.get("instrument_class"),
        order_type=raw.get("order_type"),
        session_type=raw.get("session_type"),
        credential_scope=raw.get("credential_scope"),
    )


def build_required_capability_set(
    raw: Mapping[str, Any] | None, scope_name: str
) -> RequiredCapabilitySet | None:
    """Parse the optional ``required_capability_set`` block (plan §2"""
    if raw is None:
        return None
    try:
        required_dimensions = frozenset(
            CapabilityDimension(as_str(d))
            for d in (raw.get("required_dimensions") or [])
        )
        required_level_raw = raw.get("required_level")
        required_level = (
            None
            if required_level_raw is None
            else AssuranceLevel(as_str(required_level_raw))
        )
        approved_fallback_dimensions = frozenset(
            CapabilityDimension(as_str(d))
            for d in (raw.get("approved_fallback_dimensions") or [])
        )
        return RequiredCapabilitySet(
            required_dimensions=required_dimensions,
            required_level=required_level,
            minimum_live_gate_satisfied=raw.get("minimum_live_gate_satisfied"),
            approved_fallback_dimensions=approved_fallback_dimensions,
        )
    except (ValueError, ValidationError) as exc:
        raise BrokerScopeConfigError(
            f"scope {scope_name!r}: required_capability_set rejected by the "
            f"kernel — {exc}"
        ) from exc
