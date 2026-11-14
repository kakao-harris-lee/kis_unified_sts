"""Broker environment/operation capability axes + closed routing whitelist (plan §5)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from tos.brokercap._base import ArtifactIntegrityError, FrozenModel
from tos.brokercap.records import BrokerEvidenceRef, ProfileKey
from tos.brokercap.vocabulary import Admissibility, BrokerEnvironment

__all__ = [
    "AssetScope",
    "AuthorizationClass",
    "BrokerEnvironment",
    "CapabilityProvenance",
    "CapabilityTuple",
    "ClaimKind",
    "EconomicEffect",
    "OperationClass",
    "ProbeManifest",
    "ProvenanceClass",
    "credential_principal_separation_ok",
    "endpoint_binding_from_profile_ok",
    "mock_order_without_position_or_cash",
    "provenance_admits_claim",
    "routing_admissibility",
]


class OperationClass(StrEnum):
    """The broker-operation-class axis (plan §5.1 verbatim)."""

    MARKET_DATA_READ = "MARKET_DATA_READ"
    ACCOUNT_READ = "ACCOUNT_READ"
    CAPABILITY_PROBE = "CAPABILITY_PROBE"
    ORDER_SEND = "ORDER_SEND"
    CANCEL_REPLACE = "CANCEL_REPLACE"


class EconomicEffect(StrEnum):
    """The economic-effect axis (plan §5.1 verbatim)."""

    NONE = "NONE"
    BROKER_RESOURCE_ONLY = "BROKER_RESOURCE_ONLY"
    POSITION_OR_CASH = "POSITION_OR_CASH"


class AssetScope(StrEnum):
    """The asset-scope axis (plan §5.1 verbatim)."""

    STOCK = "STOCK"
    FUTURES = "FUTURES"


class AuthorizationClass(StrEnum):
    """The authorization-class axis (plan §5.1's 3 members + the v1.1 correction's 4th)."""

    NON_AUTHORIZING_READ = "NON_AUTHORIZING_READ"
    MOCK_ORDER = "MOCK_ORDER"
    REAL_ORDER = "REAL_ORDER"
    SYNTHETIC_ORDER = "SYNTHETIC_ORDER"


_ORDER_MUTATING_OPERATIONS: frozenset[OperationClass] = frozenset(
    {OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE}
)
_ORDER_AUTHORIZATIONS: frozenset[AuthorizationClass] = frozenset(
    {AuthorizationClass.MOCK_ORDER, AuthorizationClass.REAL_ORDER}
)


class CapabilityTuple(FrozenModel):
    """The closed 5-axis capability tuple (plan §5.1; slice plan §3 decision 3)."""

    environment: BrokerEnvironment
    operation_class: OperationClass
    economic_effect: EconomicEffect
    asset_scope: AssetScope
    authorization_class: AuthorizationClass

    @model_validator(mode="after")
    def _no_axis_contradiction(self) -> CapabilityTuple:
        """Reject the axis combinations §3 decision 3 (v1.1) makes structurally impossible."""
        synthetic_order_exempt = (
            self.environment is BrokerEnvironment.SYNTHETIC
            and self.authorization_class is AuthorizationClass.SYNTHETIC_ORDER
        )
        if (
            self.operation_class in _ORDER_MUTATING_OPERATIONS
            and self.economic_effect is EconomicEffect.NONE
            and not synthetic_order_exempt
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: ORDER_SEND/CANCEL_REPLACE cannot coexist with "
                "EconomicEffect.NONE — an order-mutating operation always has an economic "
                "effect, except the SYNTHETIC x SYNTHETIC_ORDER exemption (slice plan §3 "
                "decision 3, v1.1)"
            )
        if (
            self.authorization_class is AuthorizationClass.NON_AUTHORIZING_READ
            and self.operation_class in _ORDER_MUTATING_OPERATIONS
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: NON_AUTHORIZING_READ cannot coexist with "
                "ORDER_SEND/CANCEL_REPLACE — a non-authorizing read never sends or amends "
                "an order (slice plan §3 decision 3)"
            )
        if (
            self.environment is BrokerEnvironment.SYNTHETIC
            and self.authorization_class in _ORDER_AUTHORIZATIONS
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: SYNTHETIC environment cannot coexist with "
                "REAL_ORDER/MOCK_ORDER — synthetic data never authorizes an actual broker "
                "order (slice plan §3 decision 3)"
            )
        if (
            self.authorization_class is AuthorizationClass.SYNTHETIC_ORDER
            and self.environment is not BrokerEnvironment.SYNTHETIC
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: SYNTHETIC_ORDER cannot coexist with a non-SYNTHETIC "
                "environment — a synthetic fill is only meaningful inside the SYNTHETIC "
                "environment (slice plan §3 decision 3, v1.1 rule 3′)"
            )
        if (
            self.environment is BrokerEnvironment.BROKER_PRODUCTION
            and self.operation_class in _ORDER_MUTATING_OPERATIONS
            and self.asset_scope is AssetScope.FUTURES
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: BROKER_PRODUCTION x ORDER_SEND/CANCEL_REPLACE x FUTURES "
                "is rejected by the validated-construction seal — the real futures account "
                "is never funded with margin and real-money futures order paths are "
                "policy-blocked (root CLAUDE.md non-negotiable rules; slice plan §3-A R-1)"
            )
        return self


_READ_CLASS_OPERATIONS: frozenset[OperationClass] = frozenset(
    {
        OperationClass.MARKET_DATA_READ,
        OperationClass.ACCOUNT_READ,
        OperationClass.CAPABILITY_PROBE,
    }
)

_READ_CLASS_ADMISSIBLE: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=environment,
        operation_class=operation,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )
    for environment in BrokerEnvironment
    for operation in _READ_CLASS_OPERATIONS
    for asset in AssetScope
)

_SYNTHETIC_ORDER_OPERATIONS: frozenset[OperationClass] = frozenset(
    {OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE}
)

_SYNTHETIC_ORDER_ADMISSIBLE: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=BrokerEnvironment.SYNTHETIC,
        operation_class=operation,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
    )
    for operation in _SYNTHETIC_ORDER_OPERATIONS
    for asset in AssetScope
)

_ADMISSIBLE_WHITELIST: frozenset[CapabilityTuple] = (
    _READ_CLASS_ADMISSIBLE | _SYNTHETIC_ORDER_ADMISSIBLE
)

_MOCK_STOCK_ORDER_OPERATIONS: frozenset[OperationClass] = frozenset(
    {OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE}
)

_REDUCED_WHITELIST: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=operation,
        economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.MOCK_ORDER,
    )
    for operation in _MOCK_STOCK_ORDER_OPERATIONS
)


_MOCK_SCOPE_AUTHORIZATIONS: frozenset[AuthorizationClass] = frozenset(
    {AuthorizationClass.MOCK_ORDER, AuthorizationClass.NON_AUTHORIZING_READ}
)
_NO_POSITION_OR_CASH_EFFECTS: frozenset[EconomicEffect] = frozenset(
    {EconomicEffect.NONE, EconomicEffect.BROKER_RESOURCE_ONLY}
)


def mock_order_without_position_or_cash(
    capability_tuples: tuple[CapabilityTuple, ...],
) -> bool:
    """Whether a scope's tuples are a MOCK order class that moves no position or cash."""
    if not capability_tuples:
        return False
    return all(
        isinstance(t, CapabilityTuple)
        and t.environment is BrokerEnvironment.BROKER_SIMULATION
        and isinstance(t.authorization_class, AuthorizationClass)
        and t.authorization_class in _MOCK_SCOPE_AUTHORIZATIONS
        and isinstance(t.economic_effect, EconomicEffect)
        and t.economic_effect in _NO_POSITION_OR_CASH_EFFECTS
        for t in capability_tuples
    )


def routing_admissibility(
    capability_tuple: CapabilityTuple,
    *,
    profile_evidence_ok: bool | None = None,
) -> Admissibility:
    """The closed, rule-derived whitelist verdict for one capability tuple (§3-A R-2)."""
    if capability_tuple in _ADMISSIBLE_WHITELIST:
        return Admissibility.ADMISSIBLE
    if capability_tuple in _REDUCED_WHITELIST:
        if profile_evidence_ok is True:
            return Admissibility.REDUCED
        return Admissibility.PROHIBITED
    return Admissibility.PROHIBITED


def endpoint_binding_from_profile_ok(
    capability_tuple: CapabilityTuple,
    profile_key: ProfileKey | None,
    *,
    environment_binding: Mapping[BrokerEnvironment, str],
    asset_binding: Mapping[AssetScope, str],
) -> bool:
    """Whether the tuple's environment/asset axes exactly bind to a Profile Key (§5.3 (i))."""
    if profile_key is None:
        return False
    expected_environment = environment_binding.get(capability_tuple.environment)
    expected_instrument_class = asset_binding.get(capability_tuple.asset_scope)
    if expected_environment is None or expected_instrument_class is None:
        return False
    if profile_key.environment is None or profile_key.instrument_class is None:
        return False
    return (
        profile_key.environment == expected_environment
        and profile_key.instrument_class == expected_instrument_class
    )


def credential_principal_separation_ok(
    read_principal: str | None,
    order_principal: str | None,
) -> bool:
    """Whether the read and order credentials are separate principals (§5.3 (ii))."""
    if not read_principal or not order_principal:
        return False
    return read_principal != order_principal


class ProbeManifest(FrozenModel):
    """The probe-manifest record shape (plan §5.3 last bullet; slice plan §3 decision 5.iv)."""

    emits_orders: Literal[False] = False
    allowed_methods: tuple[str, ...]
    retention: str
    ttl: str
    provenance: str


class ProvenanceClass(StrEnum):
    """Where one capability fact came from (upstream plan Phase 4 작업 3; slice plan §5-A)."""

    OFFICIAL_SDK = "OFFICIAL_SDK"
    OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT"
    INTERNAL_CLIENT = "INTERNAL_CLIENT"
    CONTROLLED_GET_PROBE = "CONTROLLED_GET_PROBE"


class ClaimKind(StrEnum):
    """The kind of claim a :class:`CapabilityProvenance` is asked to admit (slice plan §5-A)."""

    MEASURED_BOUND = "MEASURED_BOUND"
    DOCUMENTED_LIMIT = "DOCUMENTED_LIMIT"
    REAL_ORDER_CAPABILITY = "REAL_ORDER_CAPABILITY"


_NON_MEASURING_CLASSES: frozenset[ProvenanceClass] = frozenset(
    {ProvenanceClass.OFFICIAL_DOCUMENT, ProvenanceClass.INTERNAL_CLIENT}
)


class CapabilityProvenance(FrozenModel):
    """Where one capability fact came from, plus its evidence anchor (slice plan §5-A)."""

    provenance_class: ProvenanceClass
    source_ref: str
    captured_at: str
    evidence_ref: BrokerEvidenceRef | None = None
    probe_manifest: ProbeManifest | None = None

    @model_validator(mode="after")
    def _probe_manifest_iff_controlled_probe(self) -> CapabilityProvenance:
        """Reject a CONTROLLED_GET_PROBE without a manifest, or any other class with one."""
        is_probe = self.provenance_class is ProvenanceClass.CONTROLLED_GET_PROBE
        has_manifest = self.probe_manifest is not None
        if is_probe and not has_manifest:
            raise ArtifactIntegrityError(
                "CapabilityProvenance: CONTROLLED_GET_PROBE requires a probe_manifest — a "
                "controlled probe without its manifest is an unaccountable probe (slice "
                "plan §5-A)"
            )
        if not is_probe and has_manifest:
            raise ArtifactIntegrityError(
                "CapabilityProvenance: only CONTROLLED_GET_PROBE may carry a probe_manifest "
                f"— {self.provenance_class} is not a probe (slice plan §5-A)"
            )
        return self


def provenance_admits_claim(
    provenance: CapabilityProvenance | None,
    claim_kind: ClaimKind | None,
) -> bool:
    """Whether ``provenance`` admits a claim of ``claim_kind`` (slice plan §5-A)."""
    if provenance is None or claim_kind is None:
        return False
    if claim_kind is ClaimKind.REAL_ORDER_CAPABILITY:
        return False
    if (
        claim_kind is ClaimKind.MEASURED_BOUND
        and provenance.provenance_class in _NON_MEASURING_CLASSES
    ):
        return False
    return provenance.evidence_ref is not None
