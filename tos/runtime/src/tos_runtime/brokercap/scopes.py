"""Broker Scope loader + G-4 transport-nature/credential-route derivation"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from tos.brokercap import (
    Admissibility,
    AssetScope,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityProvenance,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
    ProfileKey,
    RequiredCapabilitySet,
    credential_principal_separation_ok,
    routing_admissibility,
)
from tos.egress import CredentialRouteInventoryEntry
from tos.egressgw import TransportNature

from tos_runtime.brokercap.instance_pin import render_pin
from tos_runtime.brokercap.scope_fields import (
    BrokerScopeConfigError,
    build_capability_tuple,
    build_profile_key,
    build_provenance,
    build_required_capability_set,
    reject_named_tbd_field,
    require,
)

__all__ = [
    "BrokerScope",
    "BrokerScopeConfigError",
    "BrokerScopesConfig",
    "EndpointClass",
    "PrincipalClass",
    "RequiredCapabilitySet",
    "ScopeDisposition",
    "ScopeInstanceBinding",
    "ScopeResolution",
    "credential_route_inventory",
    "load_broker_scopes",
    "refuse_principal_collision",
    "resolve_scope",
    "transport_nature",
]

_ENVIRONMENT_LABEL_TOKEN = "{environment_label}"

_RESTRICTIVENESS_RANK: dict[Admissibility, int] = {
    Admissibility.ADMISSIBLE: 0,
    Admissibility.REDUCED: 1,
    Admissibility.PROHIBITED: 2,
}


class PrincipalClass(StrEnum):
    """Which kind of credential/identity a scope's ``principal`` carries."""

    READ = "READ"
    ORDER = "ORDER"
    SYNTHETIC = "SYNTHETIC"


class EndpointClass(StrEnum):
    """Where a scope's traffic actually goes (structurally derives"""

    NONE = "NONE"
    BROKER_GET = "BROKER_GET"
    BROKER_ORDER = "BROKER_ORDER"
    SYNTHETIC = "SYNTHETIC"


class ScopeDisposition(StrEnum):
    """:func:`resolve_scope`'s verdict for one requested capability tuple."""

    ADMITTED = "ADMITTED"
    REDUCED = "REDUCED"
    UNSUPPORTED_DENY = "UNSUPPORTED_DENY"
    PROHIBITED = "PROHIBITED"


_READ_ENDPOINT_CLASSES: frozenset[EndpointClass] = frozenset({EndpointClass.BROKER_GET})
_READ_METHODS: frozenset[str] = frozenset({"GET"})
_READ_OPERATIONS: frozenset[OperationClass] = frozenset(
    {
        OperationClass.MARKET_DATA_READ,
        OperationClass.ACCOUNT_READ,
        OperationClass.CAPABILITY_PROBE,
    }
)
_READ_ECONOMIC_EFFECTS: frozenset[EconomicEffect] = frozenset({EconomicEffect.NONE})
_READ_AUTHORIZATIONS: frozenset[AuthorizationClass] = frozenset(
    {AuthorizationClass.NON_AUTHORIZING_READ}
)


@dataclass(frozen=True)
class ScopeInstanceBinding:
    """A scope's optional binding to one Broker Capability Profile INSTANCE"""

    environment: str
    degraded_since_authorization: bool | None = None


@dataclass(frozen=True)
class BrokerScope:
    """One named, runtime-configured Broker Capability scope (plan §2"""

    name: str
    capability_tuples: tuple[CapabilityTuple, ...]
    profile_key: ProfileKey
    principal_class: PrincipalClass
    principal: str
    endpoint_class: EndpointClass
    allowed_methods: tuple[str, ...]
    admissibility: Admissibility
    provenance: tuple[CapabilityProvenance, ...]
    inside_boundary: bool
    environment_binding: Mapping[BrokerEnvironment, str]
    asset_binding: Mapping[AssetScope, str]
    instance: ScopeInstanceBinding | None = None
    required_capability_set: RequiredCapabilitySet | None = None


@dataclass(frozen=True)
class BrokerScopesConfig:
    """The full loaded scope table (plan §2 decision 1)."""

    scopes: tuple[BrokerScope, ...]
    active_scope: BrokerScope
    environment_binding: Mapping[BrokerEnvironment, str]
    asset_binding: Mapping[AssetScope, str]
    instance_path: Path | None = None
    instance_sha256: str | None = None


@dataclass(frozen=True)
class ScopeResolution:
    """:func:`resolve_scope`'s result — ``scope`` is ``None`` iff"""

    scope: BrokerScope | None
    disposition: ScopeDisposition


def _most_restrictive(admissibilities: list[Admissibility]) -> Admissibility:
    return max(admissibilities, key=lambda a: _RESTRICTIVENESS_RANK[a])


def _build_scope_instance(
    raw: Mapping[str, Any] | None, context: str
) -> ScopeInstanceBinding | None:
    """Parse the optional ``instance`` block (plan §2 decision 4) — absent"""
    if raw is None:
        return None
    environment = raw.get("environment") if isinstance(raw, Mapping) else None
    if not isinstance(environment, str) or not environment:
        raise BrokerScopeConfigError(
            f"{context}: 'instance.environment' is still null (named-TBD) or "
            "not a string — refusing to load"
        )
    degraded_raw = (
        raw.get("degraded_since_authorization") if isinstance(raw, Mapping) else None
    )
    if degraded_raw is not None and not isinstance(degraded_raw, bool):
        raise BrokerScopeConfigError(
            f"{context}: 'instance.degraded_since_authorization' must be a "
            f"boolean or null, got {degraded_raw!r}"
        )
    return ScopeInstanceBinding(
        environment=environment, degraded_since_authorization=degraded_raw
    )


def _resolve_scope_binding(
    raw: Mapping[str, Any],
    field: str,
    member_type: type,
    default: Mapping[Any, str],
    *,
    scope_name: str,
    path: Path,
) -> Mapping[Any, str]:
    """Resolve one of a scope's OPTIONAL ``environment_binding``/"""
    override_raw = raw.get(field)
    if override_raw is None:
        return default
    return _load_binding(
        override_raw, f"scope {scope_name!r}.{field}", member_type, path
    )


@dataclass(frozen=True)
class _ScopeIdentity:
    """The identity-bearing fields :func:`_build_scope_identity` parses —"""

    principal_class: PrincipalClass
    principal: str
    inside_boundary: bool
    endpoint_class: EndpointClass


def _build_scope_identity(
    raw: Mapping[str, Any], *, environment_label: str, context: str
) -> _ScopeIdentity:
    """Parse ``principal_class``/``principal``/``inside_boundary``/"""
    principal_class_raw = require(
        raw.get("principal_class"), "principal_class", context
    )
    try:
        principal_class = PrincipalClass(principal_class_raw)
    except ValueError as exc:
        raise BrokerScopeConfigError(
            f"{context}: unknown principal_class {principal_class_raw!r}"
        ) from exc

    principal_raw = require(raw.get("principal"), "principal", context)
    if not isinstance(principal_raw, str):
        raise BrokerScopeConfigError(
            f"{context}: 'principal' must be a string, got {principal_raw!r}"
        )
    reject_named_tbd_field(principal_raw, "principal", context)
    principal = principal_raw.replace(_ENVIRONMENT_LABEL_TOKEN, environment_label)
    if not principal:
        raise BrokerScopeConfigError(
            f"{context}: principal resolves to an empty string"
        )

    inside_boundary = require(raw.get("inside_boundary"), "inside_boundary", context)
    if not isinstance(inside_boundary, bool):
        raise BrokerScopeConfigError(
            f"{context}: 'inside_boundary' must be a boolean, got {inside_boundary!r}"
        )

    endpoint_class_raw = require(raw.get("endpoint_class"), "endpoint_class", context)
    try:
        endpoint_class = EndpointClass(endpoint_class_raw)
    except ValueError as exc:
        raise BrokerScopeConfigError(
            f"{context}: unknown endpoint_class {endpoint_class_raw!r}"
        ) from exc

    return _ScopeIdentity(
        principal_class=principal_class,
        principal=principal,
        inside_boundary=inside_boundary,
        endpoint_class=endpoint_class,
    )


def _build_scope(
    raw: Mapping[str, Any],
    *,
    environment_label: str,
    default_environment_binding: Mapping[BrokerEnvironment, str],
    default_asset_binding: Mapping[AssetScope, str],
    path: Path,
) -> BrokerScope:
    name = require(raw.get("name"), "name", "scope")
    reject_named_tbd_field(name, "name", "scope")
    context = f"scope {name!r}"

    identity = _build_scope_identity(
        raw, environment_label=environment_label, context=context
    )

    allowed_methods_raw = require(
        raw.get("allowed_methods"), "allowed_methods", context
    )
    if not isinstance(allowed_methods_raw, list) or not allowed_methods_raw:
        raise BrokerScopeConfigError(
            f"{context}: 'allowed_methods' must be a non-empty list"
        )
    for entry in allowed_methods_raw:
        reject_named_tbd_field(entry, "allowed_methods", context)
    allowed_methods = tuple(allowed_methods_raw)

    tuples_raw = require(raw.get("capability_tuples"), "capability_tuples", context)
    if not isinstance(tuples_raw, list) or not tuples_raw:
        raise BrokerScopeConfigError(
            f"{context}: 'capability_tuples' must be a non-empty list"
        )
    capability_tuples = tuple(build_capability_tuple(t, name) for t in tuples_raw)

    profile_evidence_ok = raw.get("profile_evidence_ok")

    admissibility = _most_restrictive(
        [
            routing_admissibility(t, profile_evidence_ok=profile_evidence_ok)
            for t in capability_tuples
        ]
    )

    provenance = tuple(build_provenance(p, name) for p in (raw.get("provenance") or []))
    profile_key = build_profile_key(raw.get("profile_key"))
    instance = _build_scope_instance(raw.get("instance"), context)
    required_capability_set = build_required_capability_set(
        raw.get("required_capability_set"), name
    )
    environment_binding = _resolve_scope_binding(
        raw,
        "environment_binding",
        BrokerEnvironment,
        default_environment_binding,
        scope_name=name,
        path=path,
    )
    asset_binding = _resolve_scope_binding(
        raw,
        "asset_binding",
        AssetScope,
        default_asset_binding,
        scope_name=name,
        path=path,
    )

    return BrokerScope(
        name=name,
        capability_tuples=capability_tuples,
        profile_key=profile_key,
        principal_class=identity.principal_class,
        principal=identity.principal,
        endpoint_class=identity.endpoint_class,
        allowed_methods=allowed_methods,
        admissibility=admissibility,
        provenance=provenance,
        inside_boundary=identity.inside_boundary,
        environment_binding=environment_binding,
        asset_binding=asset_binding,
        instance=instance,
        required_capability_set=required_capability_set,
    )


def _check_instance_bindings(
    scopes: tuple[BrokerScope, ...],
    path: Path,
) -> None:
    """One source of truth (plan §2 decision 4; re-review follow-up to"""
    for scope in scopes:
        if scope.instance is None:
            continue
        for capability_tuple in scope.capability_tuples:
            expected = scope.environment_binding.get(capability_tuple.environment)
            if expected != scope.instance.environment:
                raise BrokerScopeConfigError(
                    f"{path}: scope {scope.name!r} declares instance.environment "
                    f"{scope.instance.environment!r} but its capability tuple "
                    f"environment {capability_tuple.environment.value!r} binds "
                    f"(via environment_binding) to {expected!r} — one source of "
                    "truth, refusing to load"
                )


def _resolve_instance_path(
    raw_value: Any, *, config_path: Path, scopes: tuple[BrokerScope, ...]
) -> Path | None:
    """Resolve the top-level ``instance_path`` (plan §2 decision 4) —"""
    any_scope_declares_instance = any(scope.instance is not None for scope in scopes)
    if raw_value is None:
        if any_scope_declares_instance:
            raise BrokerScopeConfigError(
                f"{config_path}: a scope declares an 'instance' block but the "
                "top-level 'instance_path' is still null — refusing to load"
            )
        return None
    if not isinstance(raw_value, str) or not raw_value:
        raise BrokerScopeConfigError(
            f"{config_path}: 'instance_path' must be a non-empty string"
        )
    candidate = Path(raw_value)
    return candidate if candidate.is_absolute() else config_path.parent / candidate


def _refuse_read_scope(
    path: Path, scope_name: str, field: str, value: object, allowed: frozenset[Any]
) -> BrokerScopeConfigError:
    """The refusal :func:`_check_read_scopes_are_read_only` raises, naming the scope,"""
    return BrokerScopeConfigError(
        f"{path}: scope {scope_name!r} declares principal_class READ but its "
        f"{field} {str(value)!r} is not read-only — a READ scope may carry only "
        f"{sorted(str(member) for member in allowed)} there; refusing to load"
    )


def _check_read_scopes_are_read_only(
    scopes: tuple[BrokerScope, ...], path: Path
) -> None:
    """Refuse a ``principal_class: READ`` scope whose own surface is not read-only"""
    for scope in scopes:
        if scope.principal_class is not PrincipalClass.READ:
            continue
        if scope.endpoint_class not in _READ_ENDPOINT_CLASSES:
            raise _refuse_read_scope(
                path,
                scope.name,
                "endpoint_class",
                scope.endpoint_class,
                _READ_ENDPOINT_CLASSES,
            )
        for method in scope.allowed_methods:
            if method not in _READ_METHODS:
                raise _refuse_read_scope(
                    path, scope.name, "allowed_methods entry", method, _READ_METHODS
                )
        for index, capability_tuple in enumerate(scope.capability_tuples):
            for axis, value, allowed in (
                ("operation_class", capability_tuple.operation_class, _READ_OPERATIONS),
                (
                    "economic_effect",
                    capability_tuple.economic_effect,
                    _READ_ECONOMIC_EFFECTS,
                ),
                (
                    "authorization_class",
                    capability_tuple.authorization_class,
                    _READ_AUTHORIZATIONS,
                ),
            ):
                if value not in allowed:
                    raise _refuse_read_scope(
                        path,
                        scope.name,
                        f"capability_tuples[{index}].{axis}",
                        value,
                        allowed,
                    )


def _check_principal_separation(scopes: tuple[BrokerScope, ...], path: Path) -> None:
    """Refuse when two DISTINCT scopes share a ``principal`` (plan §2"""
    for i, left in enumerate(scopes):
        for right in scopes[i + 1 :]:
            classes = {left.principal_class, right.principal_class}
            if classes == {PrincipalClass.READ, PrincipalClass.ORDER}:
                if credential_principal_separation_ok(left.principal, right.principal):
                    continue
            elif left.principal != right.principal:
                continue
            raise BrokerScopeConfigError(
                f"{path}: scopes {left.name!r} and {right.name!r} share principal "
                f"{left.principal!r} (principal classes {left.principal_class} / "
                f"{right.principal_class}) — refusing to load"
            )


def _check_no_duplicate_tuples(scopes: tuple[BrokerScope, ...], path: Path) -> None:
    """Refuse when the SAME capability tuple appears in two different"""
    seen: list[tuple[CapabilityTuple, str]] = []
    for scope in scopes:
        for candidate in scope.capability_tuples:
            for seen_tuple, seen_scope_name in seen:
                if seen_tuple == candidate:
                    raise BrokerScopeConfigError(
                        f"{path}: capability tuple {candidate!r} appears in both "
                        f"scope {seen_scope_name!r} and scope {scope.name!r} — "
                        "duplicate tuples across scopes are refused so "
                        "resolve_scope's single match stays structurally unique"
                    )
            seen.append((candidate, scope.name))


def _load_binding(
    raw: Any, field: str, member_type: type, path: Path
) -> dict[Any, str]:
    if not isinstance(raw, dict) or not raw:
        raise BrokerScopeConfigError(f"{path}: {field!r} must be a non-empty mapping")
    binding: dict[Any, str] = {}
    for key, value in raw.items():
        if value is None:
            raise BrokerScopeConfigError(
                f"{path}: {field}[{key!r}] is still null (named-TBD) — refusing to load"
            )
        if not isinstance(value, str):
            raise BrokerScopeConfigError(
                f"{path}: {field}[{key!r}] must be a string, got {value!r}"
            )
        reject_named_tbd_field(value, f"{field}[{key!r}]", str(path))
        try:
            binding[member_type(key)] = value
        except ValueError as exc:
            raise BrokerScopeConfigError(
                f"{path}: {field} names an unknown member {key!r}"
            ) from exc
    return binding


def load_broker_scopes(path: Path, *, environment_label: str) -> BrokerScopesConfig:
    """Load + fail-closed-validate the broker-scopes config from ``path``"""
    if not path.is_file():
        raise BrokerScopeConfigError(f"broker-scopes config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BrokerScopeConfigError(
            f"broker-scopes config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise BrokerScopeConfigError(
            f"broker-scopes config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise BrokerScopeConfigError(
            f"broker-scopes config file must be a top-level mapping: {path}"
        )

    environment_binding = _load_binding(
        raw.get("environment_binding"), "environment_binding", BrokerEnvironment, path
    )
    asset_binding = _load_binding(
        raw.get("asset_binding"), "asset_binding", AssetScope, path
    )

    scopes_raw = raw.get("scopes")
    if not isinstance(scopes_raw, list) or not scopes_raw:
        raise BrokerScopeConfigError(f"{path}: 'scopes' must be a non-empty list")
    scopes = tuple(
        _build_scope(
            s,
            environment_label=environment_label,
            default_environment_binding=environment_binding,
            default_asset_binding=asset_binding,
            path=path,
        )
        for s in scopes_raw
    )

    by_name: dict[str, BrokerScope] = {}
    for scope in scopes:
        if scope.name in by_name:
            raise BrokerScopeConfigError(f"{path}: duplicate scope name {scope.name!r}")
        by_name[scope.name] = scope

    _check_principal_separation(scopes, path)
    _check_no_duplicate_tuples(scopes, path)

    active_scope_name = raw.get("active_scope")
    if active_scope_name is None:
        raise BrokerScopeConfigError(
            f"{path}: 'active_scope' is still null (named-TBD) — refusing to load"
        )
    active_scope = by_name.get(active_scope_name)
    if active_scope is None:
        raise BrokerScopeConfigError(
            f"{path}: active_scope {active_scope_name!r} does not name a configured scope"
        )
    if active_scope.admissibility is Admissibility.PROHIBITED:
        raise BrokerScopeConfigError(
            f"{path}: active_scope {active_scope_name!r} is PROHIBITED — refusing to "
            "boot with a prohibited active scope"
        )

    _check_read_scopes_are_read_only(scopes, path)
    _check_instance_bindings(scopes, path)
    instance_path = _resolve_instance_path(
        raw.get("instance_path"), config_path=path, scopes=scopes
    )

    return BrokerScopesConfig(
        scopes=scopes,
        active_scope=active_scope,
        environment_binding=environment_binding,
        asset_binding=asset_binding,
        instance_path=instance_path,
        instance_sha256=render_pin(path, raw.get("instance_path")),
    )


def resolve_scope(
    config: BrokerScopesConfig, requested: CapabilityTuple
) -> ScopeResolution:
    """Resolve ``requested`` against ``config`` (plan §4 EC-1)."""
    for scope in config.scopes:
        if requested not in scope.capability_tuples:
            continue
        if scope.admissibility is Admissibility.PROHIBITED:
            return ScopeResolution(scope=scope, disposition=ScopeDisposition.PROHIBITED)
        if scope.admissibility is Admissibility.ADMISSIBLE:
            return ScopeResolution(scope=scope, disposition=ScopeDisposition.ADMITTED)
        return ScopeResolution(scope=scope, disposition=ScopeDisposition.REDUCED)
    return ScopeResolution(scope=None, disposition=ScopeDisposition.UNSUPPORTED_DENY)


_BROKER_REACHING_ENDPOINT_CLASSES = frozenset(
    {EndpointClass.BROKER_GET, EndpointClass.BROKER_ORDER}
)


def transport_nature(scope: BrokerScope) -> TransportNature:
    """Derive the active scope's :class:`~tos.egressgw.TransportNature`"""
    reaches = scope.endpoint_class in _BROKER_REACHING_ENDPOINT_CLASSES
    risk_relevant_live = any(
        t.authorization_class is AuthorizationClass.REAL_ORDER
        for t in scope.capability_tuples
    )
    return TransportNature(
        principal=scope.principal,
        reaches_broker=reaches,
        credential_bearing=reaches,
        route_bearing=reaches,
        risk_relevant_live=risk_relevant_live,
    )


def credential_route_inventory(
    config: BrokerScopesConfig, *, active_principal: str
) -> tuple[CredentialRouteInventoryEntry, ...]:
    """Derive the full credential-route inventory (G-4) — replaces the"""
    entries = tuple(
        CredentialRouteInventoryEntry(
            principal=scope.principal,
            usable_credential=scope.endpoint_class in _BROKER_REACHING_ENDPOINT_CLASSES,
            broker_route=scope.endpoint_class in _BROKER_REACHING_ENDPOINT_CLASSES,
            inside_boundary=scope.inside_boundary,
        )
        for scope in config.scopes
    )
    return entries + (
        CredentialRouteInventoryEntry(
            principal=active_principal,
            usable_credential=False,
            broker_route=False,
            inside_boundary=True,
        ),
    )


def refuse_principal_collision(
    config: BrokerScopesConfig, *, active_principal: str
) -> None:
    """Fail-closed boot refusal generalizing the old R2 literal comparison"""
    for scope in config.scopes:
        if scope.principal == active_principal:
            raise BrokerScopeConfigError(
                f"broker-scopes config: active_principal {active_principal!r} equals "
                f"scope {scope.name!r}'s own principal — a workload cannot assume a "
                "scope's identity as its own configured gateway principal "
                "(ADR-002-013 §8 non-transferable workload identity; generalizes G-4 "
                "boot refusal R2); refusing to compose"
            )
