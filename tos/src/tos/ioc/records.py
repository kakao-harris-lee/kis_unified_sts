"""ioc value models + injected inputs + the five digest-bound artifacts (design #14 §2)."""

from __future__ import annotations

from typing import ClassVar

from tos.ioc._base import (
    AllFalseConstructionAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.ioc.vocabulary import ConformanceAxis, ConformanceResult
from tos.rcl import CapacityVector

__all__ = [
    "OrderConstructionAuthorityEffect",
    "AxisBinding",
    "MaterialCommandChange",
    "EconomicEffectEnvelope",
    "ApprovedIntentContract",
    "AuthorizedConstructionEnvelope",
    "OrderConstructionPolicy",
    "CanonicalBrokerCommand",
    "OrderConformanceProof",
]


EconomicEffectEnvelope = CapacityVector


class OrderConstructionAuthorityEffect(AllFalseConstructionAuthority):
    """Authority effect of order construction — every flag false (IOC-INV-011 / §7 line 219)."""

    approves: bool = False
    mutates_capacity: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    chooses_admissibility: bool = False
    transmits: bool = False
    clears_halt: bool = False
    rearms: bool = False


class AxisBinding(FrozenModel):
    """One conformance axis' bound value (design #14 §5.1 — the exact-match unit)."""

    axis: ConformanceAxis | None = None
    value: str | None = None


class MaterialCommandChange(FrozenModel):
    """Whether a command change is material (ADR-002-020 §5.8 line 145)."""

    is_material: bool | None = None

    def resolved_material(self) -> bool:
        """Whether the change is material — unknown materiality is material (§5.8 line 145)."""
        return self.is_material is not False


class ApprovedIntentContract(IndependentIdArtifact):
    """An append-only, generation-immutable Approved Intent Contract (ADR-002-020 §5.1 / §8)."""

    _ID_FIELD: ClassVar[str] = "intent_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "intent_generation",
        "intent_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_generation",
            "intent_version",
            "proposal_id",
            "proposal_digest",
            "decision_context_capsule_id",
            "decision_context_capsule_digest",
            "critical_input_snapshot_digest",
            "orthostate_intent_identity",
            "authorized_axis_bindings",
            "issuer_identity",
            "approval_identity",
            "authority_effect",
        }
    )

    intent_id: str | None = None

    intent_generation: int | None = None
    intent_version: str | None = None
    proposal_id: str | None = None
    proposal_digest: str | None = None
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    critical_input_snapshot_digest: str | None = None
    orthostate_intent_identity: str | None = None
    authorized_axis_bindings: tuple[AxisBinding, ...] = ()
    issuer_identity: str | None = None
    approval_identity: str | None = None
    authority_effect: OrderConstructionAuthorityEffect = (
        OrderConstructionAuthorityEffect()
    )

    intent_order: int | None = None

    def axis_value(self, axis: ConformanceAxis) -> str | None:
        """Return the authorized value for ``axis`` (``None`` if absent / UNKNOWN)."""
        for binding in self.authorized_axis_bindings:
            if binding.axis == axis:
                return binding.value
        return None


class AuthorizedConstructionEnvelope(IndependentIdArtifact):
    """An append-only Authorized Construction Envelope (ADR-002-020 §5.3 / §8)."""

    _ID_FIELD: ClassVar[str] = "envelope_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("envelope_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "envelope_generation",
            "authorized_axis_bindings",
            "policy_binding_id",
        }
    )

    envelope_id: str | None = None

    envelope_generation: int | None = None
    authorized_axis_bindings: tuple[AxisBinding, ...] = ()
    policy_binding_id: str | None = None

    envelope_order: int | None = None

    def authorized_axes(self) -> dict[ConformanceAxis, str | None]:
        """The closed set of authorized ``{axis: value}`` (empty => open/absent => denial)."""
        return {
            binding.axis: binding.value
            for binding in self.authorized_axis_bindings
            if binding.axis is not None
        }


class OrderConstructionPolicy(IndependentIdArtifact):
    """An append-only, spg-governed Order Construction Policy (ADR-002-020 §5.2 / §9)."""

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    policy_id: str | None = None

    policy_generation: int | None = None
    policy_version: str | None = None
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    policy_order: int | None = None


class CanonicalBrokerCommand(IndependentIdArtifact):
    """An append-only Canonical Broker Command (ADR-002-020 §5.4 / §14)."""

    _ID_FIELD: ClassVar[str] = "command_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("command_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "command_generation",
            "proposal_id",
            "proposal_digest",
            "axis_bindings",
            "authority_effect",
        }
    )

    command_id: str | None = None

    command_generation: int | None = None
    proposal_id: str | None = None
    proposal_digest: str | None = None
    axis_bindings: tuple[AxisBinding, ...] = ()
    authority_effect: OrderConstructionAuthorityEffect = (
        OrderConstructionAuthorityEffect()
    )

    command_order: int | None = None

    def axis_value(self, axis: ConformanceAxis) -> str | None:
        """Return the declared value for ``axis`` (``None`` if absent / UNKNOWN)."""
        for binding in self.axis_bindings:
            if binding.axis == axis:
                return binding.value
        return None


class OrderConformanceProof(IndependentIdArtifact):
    """An append-only, non-authorizing Order Conformance Proof (ADR-002-020 §5.6 / §14)."""

    _ID_FIELD: ClassVar[str] = "proof_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("proof_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "proof_generation",
            "policy_digest",
            "envelope_digest",
            "command_digest",
            "effect_digest",
            "input_digest",
            "output_digest",
            "aggregate_risk_decision_id",
            "aggregate_risk_decision_generation",
            "aggregate_risk_decision_digest",
            "venue_admissibility_decision_digest",
            "broker_capability_profile_digest",
            "required_authority_scope",
            "conformance_result",
            "authority_effect",
        }
    )

    proof_id: str | None = None

    proof_generation: int | None = None
    policy_digest: str | None = None
    envelope_digest: str | None = None
    command_digest: str | None = None
    effect_digest: str | None = None
    input_digest: str | None = None
    output_digest: str | None = None
    aggregate_risk_decision_id: str | None = None
    aggregate_risk_decision_generation: int | None = None
    aggregate_risk_decision_digest: str | None = None
    venue_admissibility_decision_digest: str | None = None
    broker_capability_profile_digest: str | None = None
    required_authority_scope: tuple[str, ...] = ()
    conformance_result: ConformanceResult | None = None
    authority_effect: OrderConstructionAuthorityEffect = (
        OrderConstructionAuthorityEffect()
    )

    proof_order: int | None = None
