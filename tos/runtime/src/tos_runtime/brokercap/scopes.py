"""Broker Scope loader + G-4 transport-nature/credential-route derivation
(TOS Phase 4 plan §2 decisions 1-2,
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md``).

A **scope** is a runtime-configured, named bundle of one or more kernel
:class:`~tos.brokercap.routing.CapabilityTuple` values plus the
transport/principal facts implied by how that scope reaches (or does not
reach) a broker. The kernel (``tos.brokercap``) carries no concrete broker
string at all (project memory ``tos-spec-broker-agnostic``); every concrete
coordinate a scope carries (``profile_key``, ``environment_binding``,
``asset_binding`` values) is **injected runtime configuration**, never a
kernel constant — this module itself names no broker.

**Decision 1 (scopes as runtime config).** :func:`load_broker_scopes` reads
``tos/runtime/config/broker_scopes.example.yaml``-shaped YAML and builds
each :class:`BrokerScope` by **validated** kernel construction —
``CapabilityTuple(...)`` the normal way, never an unvalidated pydantic
construction shortcut that skips model validators — so a config author
cannot create a
structurally-forbidden tuple (e.g. ``BROKER_PRODUCTION`` x order x
``FUTURES``, kernel rule 4) merely by editing YAML: the kernel's own
``pydantic.ValidationError`` is caught and re-raised as
:class:`BrokerScopeConfigError`, naming the offending scope (this closes
exit condition EC-3 — "futures REAL order capability is never created by
config/env alone"). Every scope's ``admissibility`` is stamped by the loader
via :func:`~tos.brokercap.routing.routing_admissibility`, taking the MOST
RESTRICTIVE verdict across the scope's own tuples (``PROHIBITED`` >
``REDUCED`` > ``ADMISSIBLE`` — any one ``PROHIBITED`` tuple makes the whole
scope ``PROHIBITED``, never diluted by a sibling tuple's better verdict).

The ``REAL_ORDER`` scope is **listed but always ``PROHIBITED``** — visibility
of the permanent block (root ``CLAUDE.md`` "real-money futures order paths
... are permanently blocked by policy"), never an opened path: no function in
this module (or its callers) reads a ``PROHIBITED`` scope's
``endpoint_class`` to route an actual call, and :func:`resolve_scope` never
widens a request across scopes (EC-1, below).

**Decision 2 (G-4 — transport identity derived from the active scope).**
:func:`transport_nature` and :func:`credential_route_inventory` replace the
three ``f"synthetic-paper-{environment_label}"`` literals
``tos_runtime.compose._wiring`` used to carry (config-gap G-4) — the
transport's own declared nature and the credential-route inventory are now
STRUCTURALLY DERIVED from the active scope's ``endpoint_class``/
``principal_class``, never a second, independently-typed literal that can
drift from the scope table. :func:`refuse_principal_collision` generalizes
the boot refusal ``_wiring.py`` used to hardcode as
``_refuse_active_principal_matching_transport_identity`` (R2) — a workload's
configured gateway ``active_principal`` colliding with ANY scope's own
principal (not just the one literal) is refused fail-closed at boot.

**EC-1 — no rewriting.** :func:`resolve_scope` admits a requested
:class:`~tos.brokercap.routing.CapabilityTuple` **only** when some
configured scope carries a tuple that is EXACTLY EQUAL to it (pydantic
model equality) — it never mutates ``requested``, never re-tries a
different ``environment``, and never falls through to a different scope. A
requested tuple absent from every scope is ``UNSUPPORTED_DENY`` with
``scope=None`` — never silently admitted through a wider (e.g.
``BROKER_PRODUCTION``) environment.

Named-TBD discipline (mirrors ``tos_runtime.compose._egress_coordinates``
exactly): every scope's structural fields (``name``, ``principal_class``,
``principal``, ``endpoint_class``, ``allowed_methods``,
``capability_tuples``) and the top-level ``active_scope``/
``environment_binding``/``asset_binding`` fields refuse to load when still
``null`` — fail-closed, never a silent default. ``profile_evidence_ok`` is
the ONE deliberate exception: ``null`` there is a legitimate, permanent
value (evidence not established), passed straight through to
:func:`~tos.brokercap.routing.routing_admissibility`, which already treats
``None``/``False`` identically.

This module reads no ambient process environment anywhere (pinned by a
negative-grep test) and constructs no kernel model via an unvalidated
pydantic construction shortcut (also pinned) — every kernel value here goes
through validated construction, so a config-side attempt to bypass a kernel
invariant fails at load, not silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from tos.brokercap import (
    Admissibility,
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
    credential_principal_separation_ok,
    routing_admissibility,
)
from tos.brokercap.records import BrokerEvidenceRef
from tos.egress import CredentialRouteInventoryEntry
from tos.egressgw import TransportNature

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

#: The ONLY templating this loader performs on ``principal`` (mirrors
#: ``tos_runtime.compose._egress_coordinates``'s ``active_principal`` rule).
_ENVIRONMENT_LABEL_TOKEN = "{environment_label}"

#: Most-restrictive-wins ordering for stamping one scope's admissibility
#: across all of its own capability tuples.
_RESTRICTIVENESS_RANK: dict[Admissibility, int] = {
    Admissibility.ADMISSIBLE: 0,
    Admissibility.REDUCED: 1,
    Admissibility.PROHIBITED: 2,
}


class BrokerScopeConfigError(Exception):
    """Raised when the broker-scopes config is missing, malformed, carries an
    unfilled (named-TBD) structural field, names an axis combination the
    kernel rejects (EC-3), or violates principal separation — fail-closed at
    load, never a silent default or a kernel-bypassing construction."""


class PrincipalClass(StrEnum):
    """Which kind of credential/identity a scope's ``principal`` carries."""

    READ = "READ"
    ORDER = "ORDER"
    SYNTHETIC = "SYNTHETIC"


class EndpointClass(StrEnum):
    """Where a scope's traffic actually goes (structurally derives
    :class:`~tos.egressgw.TransportNature`'s reach flags, see
    :func:`transport_nature`)."""

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


@dataclass(frozen=True)
class ScopeInstanceBinding:
    """A scope's optional binding to one Broker Capability Profile INSTANCE
    document (plan §2 decision 4, 작업 5 items 6/12). ``environment`` is the
    INSTANCE document's own ``profile_identity.environment`` scalar this
    scope binds to — the loader refuses when it disagrees with
    ``environment_binding[tuple.environment]`` for any of the scope's own
    capability tuples (one source of truth, never two independently-typed
    environment facts)."""

    environment: str
    #: Operator-attested drift signal (independent-review finding F5) — the
    #: SAME discipline ``profile_evidence_ok`` already applies: ``None`` is a
    #: legitimate, permanent "unknown until an authorization act exists"
    #: value, threaded straight into the kernel
    #: :func:`~tos.brokercap.predicates.profile_version_current` predicate's
    #: ``degraded_since_authorization`` argument, which denies on anything
    #: but ``False`` — never invented, never defaulted to a value that would
    #: make the predicate's degradation gate unconditionally pass or fail.
    degraded_since_authorization: bool | None = None


@dataclass(frozen=True)
class BrokerScope:
    """One named, runtime-configured Broker Capability scope (plan §2
    decision 1). ``admissibility`` is the loader-stamped, most-restrictive
    :func:`~tos.brokercap.routing.routing_admissibility` verdict across
    every one of ``capability_tuples`` — never re-derived by a caller.

    ``instance``/``required_capability_set`` (plan §2 decision 4, 작업 5
    items 6/12) are both optional — ``None`` when this scope declares
    neither block (e.g. the SYNTHETIC default scope, which needs no broker
    INSTANCE binding at all)."""

    name: str
    capability_tuples: tuple[CapabilityTuple, ...]
    profile_key: ProfileKey
    principal_class: PrincipalClass
    #: Already ``{environment_label}``-substituted by the loader.
    principal: str
    endpoint_class: EndpointClass
    allowed_methods: tuple[str, ...]
    admissibility: Admissibility
    provenance: tuple[CapabilityProvenance, ...]
    #: Independent-review finding F1 — whether this scope's own principal is
    #: inside the current workload's egress boundary (ADR-002-013 §8
    #: "non-transferable workload identity" / "no authority outside the
    #: committed set"). Required, never a hardcoded literal — feeds
    #: :func:`credential_route_inventory`'s per-entry
    #: ``CredentialRouteInventoryEntry.inside_boundary``, which the kernel's
    #: :func:`~tos.egress.predicates.credential_route_authority_disjoint`
    #: treats as the ONLY thing separating "this principal's usable
    #: credential and broker route are fine" from "an outside/unknown
    #: principal holds both" (a bypass candidate).
    inside_boundary: bool
    #: Independent-review finding F4 — this scope's OWN resolved
    #: (never-``None``) environment-axis binding table, used by
    #: :func:`~tos_runtime.brokercap.derive.derive_item6_item12` instead of
    #: the config-wide default when the scope's YAML declares its own
    #: ``environment_binding`` override block; otherwise the config-wide
    #: default, copied through unchanged.
    environment_binding: Mapping[BrokerEnvironment, str]
    #: Independent-review finding F4 — the asset-axis sibling of
    #: ``environment_binding`` (same override-or-default resolution).
    asset_binding: Mapping[AssetScope, str]
    #: The INSTANCE document environment this scope binds to, or ``None``.
    instance: ScopeInstanceBinding | None = None
    #: The kernel required-capability set for this scope's action, or ``None``.
    required_capability_set: RequiredCapabilitySet | None = None


@dataclass(frozen=True)
class BrokerScopesConfig:
    """The full loaded scope table (plan §2 decision 1)."""

    scopes: tuple[BrokerScope, ...]
    active_scope: BrokerScope
    #: Injected string-correspondence table (never a kernel constant) — see
    #: :func:`~tos.brokercap.routing.endpoint_binding_from_profile_ok`.
    environment_binding: Mapping[BrokerEnvironment, str]
    asset_binding: Mapping[AssetScope, str]
    #: The Broker Capability Profile INSTANCE file path (plan §2 decision 4)
    #: — resolved relative to the config file's own directory when given as
    #: a relative path in YAML. ``None`` only when no scope declares an
    #: ``instance`` block (nothing would ever read this path).
    instance_path: Path | None = None


@dataclass(frozen=True)
class ScopeResolution:
    """:func:`resolve_scope`'s result — ``scope`` is ``None`` iff
    ``disposition is UNSUPPORTED_DENY``."""

    scope: BrokerScope | None
    disposition: ScopeDisposition


# ===========================================================================
# Loader
# ===========================================================================


def _require(value: Any, field: str, context: str) -> Any:
    if value is None:
        raise BrokerScopeConfigError(
            f"{context}: {field!r} is still null (named-TBD) — refusing to load"
        )
    return value


def _as_str(value: Any) -> str:
    """Narrow an untyped YAML value to ``str`` for enum/model construction —
    a non-``str`` (including ``None``) raises ``ValueError``, caught by
    every caller's own ``except (ValueError, ValidationError)`` alongside a
    kernel-rejected axis combination (EC-3)."""
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {value!r}")
    return value


def _build_capability_tuple(raw: Mapping[str, Any], scope_name: str) -> CapabilityTuple:
    """Validated construction only (never ``model_construct``) — a
    structurally-forbidden axis combination (e.g. kernel rule 4:
    ``BROKER_PRODUCTION`` x order x ``FUTURES``) raises here, wrapped with
    the scope name (EC-3)."""
    try:
        return CapabilityTuple(
            environment=BrokerEnvironment(_as_str(raw.get("environment"))),
            operation_class=OperationClass(_as_str(raw.get("operation_class"))),
            economic_effect=EconomicEffect(_as_str(raw.get("economic_effect"))),
            asset_scope=AssetScope(_as_str(raw.get("asset_scope"))),
            authorization_class=AuthorizationClass(
                _as_str(raw.get("authorization_class"))
            ),
        )
    except (ValueError, ValidationError) as exc:
        raise BrokerScopeConfigError(
            f"scope {scope_name!r}: capability tuple rejected by the kernel — {exc}"
        ) from exc


def _build_evidence_ref(raw: Mapping[str, Any] | None) -> BrokerEvidenceRef | None:
    if raw is None:
        return None
    return BrokerEvidenceRef(
        evidence_id=raw.get("evidence_id"),
        generation=raw.get("generation"),
        digest=raw.get("digest"),
        environment=raw.get("environment"),
    )


def _build_provenance(raw: Mapping[str, Any], scope_name: str) -> CapabilityProvenance:
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
        return CapabilityProvenance(
            provenance_class=ProvenanceClass(_as_str(raw.get("provenance_class"))),
            source_ref=_as_str(raw.get("source_ref")),
            captured_at=_as_str(raw.get("captured_at")),
            evidence_ref=_build_evidence_ref(raw.get("evidence_ref")),
            probe_manifest=manifest,
        )
    except (ValueError, ValidationError) as exc:
        raise BrokerScopeConfigError(
            f"scope {scope_name!r}: provenance rejected by the kernel — {exc}"
        ) from exc


def _build_profile_key(raw: Mapping[str, Any] | None) -> ProfileKey:
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


def _most_restrictive(admissibilities: list[Admissibility]) -> Admissibility:
    return max(admissibilities, key=lambda a: _RESTRICTIVENESS_RANK[a])


def _build_scope_instance(
    raw: Mapping[str, Any] | None, context: str
) -> ScopeInstanceBinding | None:
    """Parse the optional ``instance`` block (plan §2 decision 4) — absent
    ⇒ ``None``; present but malformed ⇒ :class:`BrokerScopeConfigError`
    (named-TBD discipline applied to ``instance.environment`` once the
    block itself is present at all)."""
    if raw is None:
        return None
    environment = raw.get("environment") if isinstance(raw, Mapping) else None
    if not isinstance(environment, str) or not environment:
        raise BrokerScopeConfigError(
            f"{context}: 'instance.environment' is still null (named-TBD) or "
            "not a string — refusing to load"
        )
    # degraded_since_authorization is the ONE deliberate exception to
    # named-TBD for this block (finding F5, mirrors profile_evidence_ok):
    # `null` is a legitimate, permanent "no authorization act exists yet"
    # value, passed straight through — never invented, never silently
    # coerced to a value that would make the kernel's degradation gate
    # unconditionally pass.
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


def _build_required_capability_set(
    raw: Mapping[str, Any] | None, scope_name: str
) -> RequiredCapabilitySet | None:
    """Parse the optional ``required_capability_set`` block (plan §2
    decision 4) via **validated** kernel construction only — absent ⇒
    ``None``. ``minimum_live_gate_satisfied`` is passed straight through
    (``null`` is a legitimate, permanent value the kernel already treats as
    non-``True`` ⇒ ``PROHIBITED``, the same discipline ``profile_evidence_ok``
    already applies)."""
    if raw is None:
        return None
    try:
        required_dimensions = frozenset(
            CapabilityDimension(_as_str(d))
            for d in (raw.get("required_dimensions") or [])
        )
        required_level_raw = raw.get("required_level")
        required_level = (
            None
            if required_level_raw is None
            else AssuranceLevel(_as_str(required_level_raw))
        )
        approved_fallback_dimensions = frozenset(
            CapabilityDimension(_as_str(d))
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


def _resolve_scope_binding(
    raw: Mapping[str, Any],
    field: str,
    member_type: type,
    default: Mapping[Any, str],
    *,
    scope_name: str,
    path: Path,
) -> Mapping[Any, str]:
    """Resolve one of a scope's OPTIONAL ``environment_binding``/
    ``asset_binding`` override blocks (independent-review finding F4) — the
    scope's own block when present (validated the SAME way as the
    config-wide table), else ``default`` unchanged. This is how
    :func:`~tos_runtime.brokercap.derive.derive_item6_item12` gets a map
    that can actually discriminate a scope whose asset/environment axis
    would otherwise collide with every other scope's under the shared
    config-wide table (e.g. a SYNTHETIC scope sharing the KIS INSTANCE's
    single stock+futures instrument-class string)."""
    override_raw = raw.get(field)
    if override_raw is None:
        return default
    return _load_binding(
        override_raw, f"scope {scope_name!r}.{field}", member_type, path
    )


@dataclass(frozen=True)
class _ScopeIdentity:
    """The identity-bearing fields :func:`_build_scope_identity` parses —
    split out of :func:`_build_scope` purely for the function size budget
    (independent-review findings F1/F6 pushed ``_build_scope`` over the
    100-line function cap); no behavioural difference from having this
    inline."""

    principal_class: PrincipalClass
    principal: str
    inside_boundary: bool
    endpoint_class: EndpointClass


def _build_scope_identity(
    raw: Mapping[str, Any], *, environment_label: str, context: str
) -> _ScopeIdentity:
    """Parse ``principal_class``/``principal``/``inside_boundary``/
    ``endpoint_class`` — split out of :func:`_build_scope` purely for the
    function size budget."""
    principal_class_raw = _require(
        raw.get("principal_class"), "principal_class", context
    )
    try:
        principal_class = PrincipalClass(principal_class_raw)
    except ValueError as exc:
        raise BrokerScopeConfigError(
            f"{context}: unknown principal_class {principal_class_raw!r}"
        ) from exc

    principal_raw = _require(raw.get("principal"), "principal", context)
    if not isinstance(principal_raw, str):
        raise BrokerScopeConfigError(
            f"{context}: 'principal' must be a string, got {principal_raw!r}"
        )
    principal = principal_raw.replace(_ENVIRONMENT_LABEL_TOKEN, environment_label)
    if not principal:
        raise BrokerScopeConfigError(
            f"{context}: principal resolves to an empty string"
        )

    inside_boundary = _require(raw.get("inside_boundary"), "inside_boundary", context)
    if not isinstance(inside_boundary, bool):
        raise BrokerScopeConfigError(
            f"{context}: 'inside_boundary' must be a boolean, got {inside_boundary!r}"
        )

    endpoint_class_raw = _require(raw.get("endpoint_class"), "endpoint_class", context)
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
    name = _require(raw.get("name"), "name", "scope")
    context = f"scope {name!r}"

    identity = _build_scope_identity(
        raw, environment_label=environment_label, context=context
    )

    allowed_methods_raw = _require(
        raw.get("allowed_methods"), "allowed_methods", context
    )
    if not isinstance(allowed_methods_raw, list) or not allowed_methods_raw:
        raise BrokerScopeConfigError(
            f"{context}: 'allowed_methods' must be a non-empty list"
        )
    allowed_methods = tuple(allowed_methods_raw)

    tuples_raw = _require(raw.get("capability_tuples"), "capability_tuples", context)
    if not isinstance(tuples_raw, list) or not tuples_raw:
        raise BrokerScopeConfigError(
            f"{context}: 'capability_tuples' must be a non-empty list"
        )
    capability_tuples = tuple(_build_capability_tuple(t, name) for t in tuples_raw)

    # profile_evidence_ok is the ONE deliberate exception to named-TBD: null
    # is a legitimate, permanent "evidence not established" value, passed
    # straight through (module docstring).
    profile_evidence_ok = raw.get("profile_evidence_ok")

    admissibility = _most_restrictive(
        [
            routing_admissibility(t, profile_evidence_ok=profile_evidence_ok)
            for t in capability_tuples
        ]
    )

    provenance = tuple(
        _build_provenance(p, name) for p in (raw.get("provenance") or [])
    )
    profile_key = _build_profile_key(raw.get("profile_key"))
    instance = _build_scope_instance(raw.get("instance"), context)
    required_capability_set = _build_required_capability_set(
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
    environment_binding: Mapping[BrokerEnvironment, str],
    path: Path,
) -> None:
    """One source of truth (plan §2 decision 4): a scope's ``instance.
    environment`` must equal ``environment_binding[tuple.environment]`` for
    EVERY one of its own capability tuples — never a second, independently
    -typed environment fact that could silently disagree."""
    for scope in scopes:
        if scope.instance is None:
            continue
        for capability_tuple in scope.capability_tuples:
            expected = environment_binding.get(capability_tuple.environment)
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
    """Resolve the top-level ``instance_path`` (plan §2 decision 4) —
    relative to ``config_path``'s own directory when given as a relative
    string, absolute paths pass through unchanged. ``None`` is legitimate
    ONLY when no scope declares an ``instance`` block; a scope needing
    INSTANCE data with no path configured fails closed."""
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


def _check_principal_separation(scopes: tuple[BrokerScope, ...], path: Path) -> None:
    """Refuse when two DISTINCT scopes share a ``principal`` (plan §2
    decision 1; independent-review finding F2 generalizes this from
    "different classes only" to EVERY pair, including two scopes of the
    SAME ``principal_class``). The kernel
    :func:`~tos.brokercap.routing.credential_principal_separation_ok`
    predicate remains the documented anchor for the READ/ORDER pair
    specifically — the one invariant it was written to check; every other
    pair (same-class included) is refused by plain strict equality, so a
    config author cannot recreate a shared-principal bypass merely by
    giving two scopes matching classes."""
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
    """Refuse when the SAME capability tuple appears in two different
    scopes (independent-review finding F3). This is what makes
    :func:`resolve_scope`'s single match structurally unique — without it, a
    duplicate tuple listed in two scopes would resolve by YAML list order,
    letting an earlier (evidenced) scope's verdict silently promote a
    request a later scope would deny."""
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
        try:
            binding[member_type(key)] = value
        except ValueError as exc:
            raise BrokerScopeConfigError(
                f"{path}: {field} names an unknown member {key!r}"
            ) from exc
    return binding


def load_broker_scopes(path: Path, *, environment_label: str) -> BrokerScopesConfig:
    """Load + fail-closed-validate the broker-scopes config from ``path``
    (shaped like ``tos/runtime/config/broker_scopes.example.yaml``).

    Args:
        path: The config file (every named-TBD filled — at minimum
            ``active_scope``).
        environment_label: Substituted for the ``{environment_label}`` token
            in every scope's ``principal``, if present.

    Raises:
        BrokerScopeConfigError: The file is missing/unreadable/not valid
            YAML/not a mapping, a structural field is still ``null``
            (named-TBD), a capability tuple is rejected by the kernel (EC-3),
            two scopes of different principal classes share a principal, or
            ``active_scope`` does not name a configured, non-``PROHIBITED``
            scope.
    """
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

    # Global (config-wide) binding tables load FIRST — every scope's
    # per-scope override (finding F4) resolves against these as its default,
    # so scope construction below needs them already built.
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

    _check_instance_bindings(scopes, environment_binding, path)
    instance_path = _resolve_instance_path(
        raw.get("instance_path"), config_path=path, scopes=scopes
    )

    return BrokerScopesConfig(
        scopes=scopes,
        active_scope=active_scope,
        environment_binding=environment_binding,
        asset_binding=asset_binding,
        instance_path=instance_path,
    )


# ===========================================================================
# EC-1 — resolution never rewrites a requested tuple
# ===========================================================================


def resolve_scope(
    config: BrokerScopesConfig, requested: CapabilityTuple
) -> ScopeResolution:
    """Resolve ``requested`` against ``config`` (plan §4 EC-1).

    Only a scope carrying a tuple EXACTLY EQUAL to ``requested`` can be
    ``ADMITTED``/``REDUCED``/``PROHIBITED`` — this function never
    constructs a new tuple, never inspects (let alone rewrites)
    ``requested.environment``, and never falls through to a different
    scope's tuple. A requested tuple present in no scope is
    ``UNSUPPORTED_DENY`` with ``scope=None`` (never rewritten to something
    an existing scope does admit).

    Uniqueness across scopes is guaranteed by the loader
    (:func:`_check_no_duplicate_tuples`, independent-review finding F3) — no
    two scopes can carry the same tuple, so the first (and only) match this
    loop finds is, structurally, the ONLY match; this function does not
    itself need to guard against or pick among duplicates.
    """
    for scope in config.scopes:
        if requested not in scope.capability_tuples:
            continue
        if scope.admissibility is Admissibility.PROHIBITED:
            return ScopeResolution(scope=scope, disposition=ScopeDisposition.PROHIBITED)
        if scope.admissibility is Admissibility.ADMISSIBLE:
            return ScopeResolution(scope=scope, disposition=ScopeDisposition.ADMITTED)
        return ScopeResolution(scope=scope, disposition=ScopeDisposition.REDUCED)
    return ScopeResolution(scope=None, disposition=ScopeDisposition.UNSUPPORTED_DENY)


# ===========================================================================
# G-4 — transport nature / credential-route inventory derived from scopes
# ===========================================================================

#: Endpoint classes that actually reach a broker (structurally derives
#: TransportNature's reach flags — module docstring decision 2).
_BROKER_REACHING_ENDPOINT_CLASSES = frozenset(
    {EndpointClass.BROKER_GET, EndpointClass.BROKER_ORDER}
)


def transport_nature(scope: BrokerScope) -> TransportNature:
    """Derive the active scope's :class:`~tos.egressgw.TransportNature`
    (G-4) — replaces the ``_wiring.py`` literal
    ``TransportNature(principal=f"synthetic-paper-{environment_label}", ...)``.

    ``reaches_broker``/``credential_bearing``/``route_bearing`` are all
    ``True`` for ``BROKER_GET``/``BROKER_ORDER``, all ``False`` for
    ``SYNTHETIC``/``NONE``. ``risk_relevant_live`` is
    ``authorization_class is REAL_ORDER`` for ANY of the scope's tuples,
    regardless of endpoint class — the same structural fact
    :func:`credential_route_inventory` and :func:`resolve_scope` already key
    off, never a value type distinct from the scope's own tuples.
    """
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
    """Derive the full credential-route inventory (G-4) — replaces the
    ``_wiring.py`` literal pair of :class:`~tos.egress.CredentialRouteInventoryEntry`
    values.

    One entry per configured scope's own ``principal`` (``usable_credential``/
    ``broker_route`` are ``True`` iff the scope's ``endpoint_class`` is
    ``BROKER_GET``/``BROKER_ORDER``; ``inside_boundary`` is the scope's OWN
    ``inside_boundary`` config field, independent-review finding F1 — never
    a hardcoded literal, so a scope declared ``inside_boundary: false`` (an
    externally-reachable principal outside this workload's committed set,
    ADR-002-013 §8) is actually visible to the kernel's
    :func:`~tos.egress.predicates.credential_route_authority_disjoint`
    boundary check), PLUS the gateway's own ``active_principal`` entry —
    kept byte-for-byte identical to what ``_wiring.py`` built for it before
    (``usable_credential=False``, ``broker_route=False``,
    ``inside_boundary=True`` — the gateway's own workload identity is, by
    definition, always inside its own boundary).
    """
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
    """Fail-closed boot refusal generalizing the old R2 literal comparison
    (``_wiring.py``'s ``_refuse_active_principal_matching_transport_identity``)
    from ONE hardcoded transport identity to EVERY configured scope
    principal (module docstring decision 2).

    Raises:
        BrokerScopeConfigError: ``active_principal`` equals some scope's own
            principal — a workload cannot assume a scope's identity as its
            own configured gateway principal (ADR-002-013 §8 non-transferable
            workload identity).
    """
    for scope in config.scopes:
        if scope.principal == active_principal:
            raise BrokerScopeConfigError(
                f"broker-scopes config: active_principal {active_principal!r} equals "
                f"scope {scope.name!r}'s own principal — a workload cannot assume a "
                "scope's identity as its own configured gateway principal "
                "(ADR-002-013 §8 non-transferable workload identity; generalizes G-4 "
                "boot refusal R2); refusing to compose"
            )
