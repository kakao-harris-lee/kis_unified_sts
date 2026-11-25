"""Broker Capability Profile INSTANCE loader (Phase 4 plan §2 decision 3)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from tos.brokercap.predicates import profile_version_current
from tos.brokercap.records import (
    BrokerCapabilityProfile,
    CapabilityDeclaration,
    FinalQuantityProofRule,
    LiveScope,
    ProfileKey,
    ProfileVersion,
)
from tos.brokercap.routing import CapabilityProvenance, ProvenanceClass
from tos.brokercap.vocabulary import (
    AssuranceLevel,
    AssuranceSource,
    BrokerEnvironment,
    CapabilityDimension,
    CapabilityStatus,
    ProhibitedProof,
)
from tos.canonical import ArtifactStatus

from tos_runtime.transport.endpoint import (
    EndpointOrigin,
    EndpointOriginError,
    endpoint_origin,
)

__all__ = [
    "REAL_ENVIRONMENT",
    "BrokerInstanceConfigError",
    "InstanceDocument",
    "instance_version_current",
    "load_instance_document",
    "load_instance_documents",
    "select_document",
]


REAL_ENVIRONMENT = "REAL_PROD"


class BrokerInstanceConfigError(Exception):
    """The instance file is missing/unreadable/malformed, or a block that"""


@dataclass(frozen=True)
class InstanceDocument:
    """One parsed Broker Capability Profile INSTANCE document (plan §2 decision 3)."""

    artifact_id: str | None
    environment: str | None
    status: str | None
    approvers: tuple[str, ...]
    rest_base: str | None
    profile: BrokerCapabilityProfile
    declared_dimensions: frozenset[CapabilityDimension]
    verified_dimensions: frozenset[CapabilityDimension]
    provenance: tuple[CapabilityProvenance, ...]
    unmapped_sources: tuple[str, ...]
    environment_class_binding: tuple[str | None, str, BrokerEnvironment] | None = None

    @property
    def environment_class_host_bound(self) -> bool:
        """Whether the profile's ``environment_class`` is the one the loader tied to THIS"""
        return self.environment_class_binding is not None and (
            self.environment_class_binding
            == (self.environment, self.rest_base, self.profile.environment_class)
        )


_ASSURANCE_SOURCE_TO_PROVENANCE_CLASS: dict[AssuranceSource, ProvenanceClass | None] = {
    AssuranceSource.OFFICIAL_SPECIFICATION: ProvenanceClass.OFFICIAL_DOCUMENT,
    AssuranceSource.BROKER_CONTRACTUAL_STATEMENT: ProvenanceClass.OFFICIAL_DOCUMENT,
    AssuranceSource.BROKER_SUPPORT_CONFIRMATION: ProvenanceClass.OFFICIAL_DOCUMENT,
    AssuranceSource.CONTROLLED_SANDBOX_TEST: None,
    AssuranceSource.CONTROLLED_PRODUCTION_PROBE: None,
    AssuranceSource.FAULT_INJECTION_RESULT: None,
    AssuranceSource.OBSERVED_LIVE_EVIDENCE: None,
    AssuranceSource.INDEPENDENT_OPERATIONAL_REVIEW: None,
}

_PROFILE_KEY_FIELDS = (
    "broker_id",
    "api_product",
    "api_version",
    "environment",
    "account_type",
    "market",
    "instrument_class",
    "order_type",
    "session_type",
    "credential_scope",
)

_LIVE_SCOPE_FIELDS = (
    "account_scope",
    "instrument_scope",
    "order_type_scope",
    "quantity_risk_limit",
    "session_scope",
    "action_classes",
    "mode",
    "reduced_off_unattended_partition_protection",
)

_TBD = "TBD"


def _read_rest_base(profile_identity: dict[str, Any]) -> str | None:
    """Read ``profile_identity._kis.endpoints.rest_base`` as a plain scalar (T2 lane C —"""
    kis_block = profile_identity.get("_kis")
    if not isinstance(kis_block, dict):
        return None
    endpoints = kis_block.get("endpoints")
    if not isinstance(endpoints, dict):
        return None
    rest_base = endpoints.get("rest_base")
    return rest_base if isinstance(rest_base, str) and rest_base else None


def _tbd_to_none(value: Any) -> Any:
    """Map the template's ``"TBD"`` placeholder to ``None`` (never a value)."""
    return None if value == _TBD else value


def _require_dict(raw: Any, key: str, *, context: str) -> dict[str, Any]:
    block = raw.get(key) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise BrokerInstanceConfigError(
            f"{context}: missing or non-mapping {key!r} block — refusing to "
            "invent one"
        )
    return block


def _require_model_view(block: dict[str, Any], *, context: str) -> dict[str, Any]:
    model_view = block.get("_model_view")
    if not isinstance(model_view, dict):
        raise BrokerInstanceConfigError(
            f"{context}: block carries no `_model_view` mapping — this "
            "module reads only `_model_view` blocks (never a template-shaped "
            "key) and refuses to invent one"
        )
    return model_view


def _to_enum(enum_cls: type, value: Any, *, context: str) -> Any:
    """Coerce ``value`` to an exact member of ``enum_cls``, or fail closed."""
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise BrokerInstanceConfigError(
            f"{context}: {value!r} is not a valid {enum_cls.__name__} member "
            "— the `_model_view` value must already be exact kernel "
            "vocabulary; this module does not translate template spellings"
        ) from exc


def _build_profile_key(profile_identity: dict[str, Any], *, context: str) -> ProfileKey:
    model_view = _require_model_view(
        profile_identity, context=f"{context}.profile_identity"
    )
    kwargs = {name: model_view.get(name) for name in _PROFILE_KEY_FIELDS}
    try:
        return ProfileKey(**kwargs)
    except Exception as exc:
        raise BrokerInstanceConfigError(
            f"{context}: profile_identity._model_view did not build a valid "
            f"ProfileKey: {exc}"
        ) from exc


def _build_profile_version(profile_identity: dict[str, Any]) -> ProfileVersion:
    """Build ``ProfileVersion`` from the ``profile_identity`` scalars (not `_model_view`)."""
    approvers = profile_identity.get("approvers") or []
    approver_identity = approvers[0] if approvers else None
    return ProfileVersion(
        profile_version=_tbd_to_none(profile_identity.get("profile_version")),
        effective_date=_tbd_to_none(profile_identity.get("effective_from")),
        evidence_package_version=_tbd_to_none(
            profile_identity.get("evidence_package_version")
        ),
        approver_identity=approver_identity,
        expiration_or_revalidation_date=_tbd_to_none(
            profile_identity.get("expires_at")
        ),
        superseded_version_link=_tbd_to_none(
            profile_identity.get("superseded_version_link")
        ),
        change_reason=_tbd_to_none(profile_identity.get("change_reason")),
    )


def _build_live_scope(raw: dict[str, Any], *, context: str) -> LiveScope:
    live_scope_block = _require_dict(raw, "live_scope", context=context)
    model_view = _require_model_view(live_scope_block, context=f"{context}.live_scope")
    kwargs: dict[str, Any] = {}
    for name in _LIVE_SCOPE_FIELDS:
        value = model_view.get(name)
        if name == "action_classes":
            value = tuple(value) if value is not None else ()
        kwargs[name] = value
    try:
        return LiveScope(**kwargs)
    except Exception as exc:
        raise BrokerInstanceConfigError(
            f"{context}.live_scope: `_model_view` did not build a valid "
            f"LiveScope: {exc}"
        ) from exc


def _provenance_for_sources(
    sources: tuple[AssuranceSource, ...],
    *,
    source_ref: str,
    captured_at: str,
) -> tuple[tuple[CapabilityProvenance, ...], tuple[str, ...]]:
    """Map ``sources`` through the closed table, splitting mapped / unmapped."""
    produced: list[CapabilityProvenance] = []
    unmapped: list[str] = []
    for source in sources:
        provenance_class = _ASSURANCE_SOURCE_TO_PROVENANCE_CLASS.get(source)
        if provenance_class is None:
            unmapped.append(source.value)
            continue
        produced.append(
            CapabilityProvenance(
                provenance_class=provenance_class,
                source_ref=source_ref,
                captured_at=captured_at,
            )
        )
    return tuple(produced), tuple(unmapped)


def _build_declarations(
    raw: dict[str, Any], *, captured_at: str, context: str
) -> tuple[
    tuple[CapabilityDeclaration, ...],
    frozenset[CapabilityDimension],
    frozenset[CapabilityDimension],
    tuple[CapabilityProvenance, ...],
    tuple[str, ...],
]:
    capabilities = _require_dict(raw, "capabilities", context=context)
    declarations: list[CapabilityDeclaration] = []
    declared: set[CapabilityDimension] = set()
    verified: set[CapabilityDimension] = set()
    provenance: list[CapabilityProvenance] = []
    unmapped: list[str] = []

    for name, block in capabilities.items():
        block_context = f"{context}.capabilities.{name}"
        if not isinstance(block, dict):
            raise BrokerInstanceConfigError(
                f"{block_context}: capability block is not a mapping"
            )
        model_view = _require_model_view(block, context=block_context)

        if model_view.get("dimension") is None:
            continue

        dimension = _to_enum(
            CapabilityDimension, model_view.get("dimension"), context=block_context
        )
        status = _to_enum(
            CapabilityStatus, model_view.get("status"), context=block_context
        )
        assurance_level = _to_enum(
            AssuranceLevel, model_view.get("assurance_level"), context=block_context
        )
        raw_sources = model_view.get("assurance_sources") or []
        sources = tuple(
            _to_enum(AssuranceSource, source, context=block_context)
            for source in raw_sources
        )

        declaration = CapabilityDeclaration(
            dimension=dimension,
            status=status,
            assurance_level=assurance_level,
            evidence_reference=model_view.get("evidence_reference"),
            restriction=model_view.get("restriction"),
            restriction_approved=model_view.get("restriction_approved"),
            fallback_reference=model_view.get("fallback_reference"),
            assurance_sources=sources,
        )
        declarations.append(declaration)
        declared.add(dimension)
        if status is CapabilityStatus.VERIFIED:
            verified.add(dimension)

        block_provenance, block_unmapped = _provenance_for_sources(
            sources, source_ref=name, captured_at=captured_at
        )
        provenance.extend(block_provenance)
        unmapped.extend(block_unmapped)

    return (
        tuple(declarations),
        frozenset(declared),
        frozenset(verified),
        tuple(provenance),
        tuple(unmapped),
    )


def _build_fqp_rules(
    raw: dict[str, Any], *, context: str
) -> tuple[FinalQuantityProofRule, ...]:
    """Build the Final Quantity Proof recipes from `final_quantity_proof.recipes[]`."""
    fqp_block = raw.get("final_quantity_proof")
    if not isinstance(fqp_block, dict):
        return ()
    recipes = fqp_block.get("recipes") or []
    rules: list[FinalQuantityProofRule] = []
    for index, recipe in enumerate(recipes):
        recipe_context = f"{context}.final_quantity_proof.recipes[{index}]"
        if not isinstance(recipe, dict):
            raise BrokerInstanceConfigError(
                f"{recipe_context}: recipe is not a mapping"
            )
        model_view = _require_model_view(recipe, context=recipe_context)
        prohibited = tuple(
            _to_enum(ProhibitedProof, proof, context=recipe_context)
            for proof in (model_view.get("prohibited_proofs") or [])
        )
        rules.append(
            FinalQuantityProofRule(
                order_type=model_view.get("order_type"),
                prohibited_proofs=frozenset(prohibited),
                no_later_change_asserted=model_view.get("no_later_change_asserted"),
                late_event_window_defined=model_view.get("late_event_window_defined"),
            )
        )
    return tuple(rules)


def _build_environment_class(
    profile_identity: dict[str, Any], *, context: str
) -> BrokerEnvironment | None:
    """``profile_identity._model_view.environment_class`` as the kernel enum, or ``None``."""
    model_view = profile_identity.get("_model_view")
    raw = model_view.get("environment_class") if isinstance(model_view, dict) else None
    if raw is None:
        return None
    try:
        return BrokerEnvironment(raw)
    except ValueError as exc:
        raise BrokerInstanceConfigError(
            f"{context}: profile_identity.environment_class {raw!r} is not one of "
            f"{[member.value for member in BrokerEnvironment]}"
        ) from exc


def _build_instance_document(
    raw: dict[str, Any], *, path: Path, index: int
) -> InstanceDocument:
    context = f"{path}[doc {index}]"
    profile_identity = _require_dict(raw, "profile_identity", context=context)
    profile_key = _build_profile_key(profile_identity, context=context)
    profile_version = _build_profile_version(profile_identity)
    live_scope = _build_live_scope(raw, context=context)

    artifact_id = profile_identity.get("artifact_id")
    captured_at = _tbd_to_none(profile_identity.get("effective_from")) or "UNKNOWN"

    (
        declarations,
        declared_dimensions,
        verified_dimensions,
        provenance,
        unmapped_sources,
    ) = _build_declarations(raw, captured_at=captured_at, context=context)
    fqp_rules = _build_fqp_rules(raw, context=context)

    environment_class = _build_environment_class(profile_identity, context=context)
    try:
        profile = BrokerCapabilityProfile(
            status=ArtifactStatus.DRAFT,
            canonical_digest=None,
            canonicalization_version=None,
            profile_id=artifact_id,
            profile_key=profile_key,
            profile_version=profile_version,
            declarations=declarations,
            conformance_class=None,
            live_scope=live_scope,
            final_quantity_proof_rules=fqp_rules,
            environment_class=environment_class,
        )
    except Exception as exc:
        raise BrokerInstanceConfigError(
            f"{context}: profile did not validate: {exc}"
        ) from exc

    approvers_raw = profile_identity.get("approvers") or []
    return InstanceDocument(
        artifact_id=artifact_id,
        environment=profile_identity.get("environment"),
        status=profile_identity.get("status"),
        approvers=tuple(approvers_raw),
        rest_base=_read_rest_base(profile_identity),
        profile=profile,
        declared_dimensions=declared_dimensions,
        verified_dimensions=verified_dimensions,
        provenance=provenance,
        unmapped_sources=unmapped_sources,
    )


def _raw_identity(raw: object) -> dict[str, Any]:
    identity = raw.get("profile_identity") if isinstance(raw, dict) else None
    return identity if isinstance(identity, dict) else {}


def _raw_class(raw: object) -> object:
    model_view = _raw_identity(raw).get("_model_view")
    return model_view.get("environment_class") if isinstance(model_view, dict) else None


@dataclass(frozen=True)
class _HostIndex:
    """The host facts every class claim is checked against, read off the RAW documents (so a"""

    real_origin: EndpointOrigin | None
    simulation_origins: frozenset[EndpointOrigin]
    simulation_unparseable: bool


def _origin_or_none(rest_base: str | None) -> EndpointOrigin | None:
    if rest_base is None:
        return None
    try:
        return endpoint_origin(rest_base)
    except EndpointOriginError:
        return None


def _host_index(raw_docs: list[Any]) -> _HostIndex:
    real = [
        d for d in raw_docs if _raw_identity(d).get("environment") == REAL_ENVIRONMENT
    ]
    real_origin = (
        _origin_or_none(_read_rest_base(_raw_identity(real[0])))
        if len(real) == 1
        else None
    )
    simulation_hosts = [
        _read_rest_base(_raw_identity(d))
        for d in raw_docs
        if _raw_class(d) == BrokerEnvironment.BROKER_SIMULATION.value
    ]
    origins = [_origin_or_none(h) for h in simulation_hosts if h is not None]
    return _HostIndex(
        real_origin,
        frozenset(o for o in origins if o is not None),
        any(o is None for o in origins),
    )


def _bind_environment_class(
    document: InstanceDocument, hosts: _HostIndex, *, context: str
) -> InstanceDocument:
    """Tie the profile's declared class to its own host — the SAME host facts the kis-mock"""
    declared = document.profile.environment_class
    if declared is None:
        return document
    host = document.rest_base
    if host is None:
        raise BrokerInstanceConfigError(
            f"{context}: environment_class {declared.value} declared without a known "
            "_kis.endpoints.rest_base — the class cannot be tied to a host"
        )
    try:
        origin = endpoint_origin(host)
    except EndpointOriginError as exc:
        raise BrokerInstanceConfigError(
            f"{context}: environment_class {declared.value} declared on a rest_base that "
            f"cannot be normalized — the class cannot be tied to a host: {exc}"
        ) from exc
    if declared is BrokerEnvironment.BROKER_SIMULATION:
        if document.environment == REAL_ENVIRONMENT or (
            hosts.real_origin is not None and origin.host == hosts.real_origin.host
        ):
            raise BrokerInstanceConfigError(
                f"{context}: BROKER_SIMULATION declared on the REAL host / document "
                f"({host!r} resolves to {origin}) — a production profile cannot be "
                "relabelled simulation"
            )
        if hosts.real_origin is None:
            return document
    elif declared is BrokerEnvironment.BROKER_PRODUCTION:
        if hosts.simulation_unparseable or origin.host in {
            o.host for o in hosts.simulation_origins
        }:
            raise BrokerInstanceConfigError(
                f"{context}: BROKER_PRODUCTION declared on a host a simulation document uses "
                "(or one no simulation host can be proven distinct from)"
            )
    else:
        raise BrokerInstanceConfigError(
            f"{context}: environment_class {declared.value} is not a broker environment "
            "(BROKER_SIMULATION or BROKER_PRODUCTION)"
        )
    return replace(
        document, environment_class_binding=(document.environment, host, declared)
    )


def _read_instance_text(path: Path, expected_sha256: str | None) -> str:
    """The instance file's text — and, when ``expected_sha256`` is given (the render pin,"""
    if not path.is_file():
        raise BrokerInstanceConfigError(
            f"broker profile instance file not found: {path}"
        )
    if expected_sha256 is not None and path.resolve() != path.absolute():
        raise BrokerInstanceConfigError(
            f"broker profile instance path {path} goes through a symlink "
            f"(resolves to {path.resolve()}) — the render pinned the resolved file; "
            "refusing to boot"
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file could not be read: {path}"
        ) from exc
    if expected_sha256 is not None:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise BrokerInstanceConfigError(
                f"broker profile instance file {path} changed since the render: sha256 "
                f"{actual} != rendered {expected_sha256} — refusing to boot on a profile "
                "the render did not bind"
            )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file is not UTF-8: {path}"
        ) from exc


def load_instance_documents(
    path: Path, *, expected_sha256: str | None = None
) -> tuple[InstanceDocument, ...]:
    """Load every YAML document in the Broker Capability Profile INSTANCE file at ``path``."""
    text = _read_instance_text(path, expected_sha256)
    try:
        raw_docs = list(yaml.safe_load_all(text))
    except yaml.YAMLError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file is not valid YAML: {path}"
        ) from exc

    documents: list[InstanceDocument] = []
    hosts = _host_index(raw_docs)
    for index, raw in enumerate(raw_docs):
        if not isinstance(raw, dict):
            raise BrokerInstanceConfigError(
                f"{path}[doc {index}]: top-level YAML document must be a mapping"
            )
        document = _build_instance_document(raw, path=path, index=index)
        documents.append(
            _bind_environment_class(document, hosts, context=f"{path}[doc {index}]")
        )
    return tuple(documents)


def load_instance_document(
    path: Path, *, environment: str, expected_sha256: str | None = None
) -> InstanceDocument:
    """Load and build ONLY the single document in ``path`` whose own"""
    text = _read_instance_text(path, expected_sha256)
    try:
        raw_docs = list(yaml.safe_load_all(text))
    except yaml.YAMLError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file is not valid YAML: {path}"
        ) from exc

    matches = [
        (index, raw)
        for index, raw in enumerate(raw_docs)
        if isinstance(raw, dict)
        and isinstance(raw.get("profile_identity"), dict)
        and raw["profile_identity"].get("environment") == environment
    ]
    if len(matches) != 1:
        raise BrokerInstanceConfigError(
            f"{path}: expected exactly one raw document with "
            f"profile_identity.environment={environment!r}, found {len(matches)}"
        )
    index, raw = matches[0]
    document = _build_instance_document(raw, path=path, index=index)
    return _bind_environment_class(
        document, _host_index(raw_docs), context=f"{path}[doc {index}]"
    )


def select_document(
    documents: tuple[InstanceDocument, ...], *, environment: str
) -> InstanceDocument:
    """Select the single ``documents`` entry whose ``environment`` matches exactly."""
    matches = [
        document for document in documents if document.environment == environment
    ]
    if len(matches) != 1:
        raise BrokerInstanceConfigError(
            f"expected exactly one instance document for environment={environment!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def instance_version_current(
    document: InstanceDocument, *, degraded_since_authorization: bool | None
) -> bool:
    """Whether ``document``'s profile version is current (plan §2 decision 3)."""
    presented = (
        document.profile.profile_version.profile_version
        if document.profile.profile_version is not None
        else None
    )
    active = presented if document.approvers else None
    not_expired = document.status != "EXPIRED"
    return profile_version_current(
        active_version=active,
        presented_version=presented,
        not_expired=not_expired,
        degraded_since_authorization=degraded_since_authorization,
    )
