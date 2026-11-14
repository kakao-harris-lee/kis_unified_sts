"""Brokercap value models + the append-only Broker Capability Profile (design #10 §2)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.brokercap._base import (
    ArtifactIntegrityError,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.brokercap.vocabulary import (
    AssuranceLevel,
    AssuranceSource,
    BrokerEnvironment,
    CapabilityDimension,
    CapabilityStatus,
    ConformanceClass,
    ProhibitedProof,
)
from tos.canonical import CanonicalDecimal


class ProfileKey(FrozenModel):
    """The 10-coordinate profile key (ADR-002-004 §7.1 line 245-256 verbatim)."""

    broker_id: str | None = None
    api_product: str | None = None
    api_version: str | None = None
    environment: str | None = None
    account_type: str | None = None
    market: str | None = None
    instrument_class: str | None = None
    order_type: str | None = None
    session_type: str | None = None
    credential_scope: str | None = None


class ProfileVersion(FrozenModel):
    """The 7-field profile version block (ADR-002-004 §7.2 line 264-270 verbatim)."""

    profile_version: str | None = None
    effective_date: str | None = None
    evidence_package_version: str | None = None
    approver_identity: str | None = None
    expiration_or_revalidation_date: str | None = None
    superseded_version_link: str | None = None
    change_reason: str | None = None


class CapabilityDeclaration(FrozenModel):
    """One dimension's capability declaration (ADR-002-004 §5.2 / §21 Capability Matrix)."""

    dimension: CapabilityDimension | None = None
    status: CapabilityStatus | None = None
    assurance_level: AssuranceLevel | None = None
    evidence_reference: str | None = None
    restriction: str | None = None
    restriction_approved: bool | None = None
    fallback_reference: str | None = None
    assurance_sources: tuple[AssuranceSource, ...] = ()


class LiveScope(FrozenModel):
    """The live-scope envelope a profile authorizes (ADR-002-004 §5.10 line 183; §21)."""

    account_scope: str | None = None
    instrument_scope: str | None = None
    order_type_scope: str | None = None
    quantity_risk_limit: CanonicalDecimal | None = None
    session_scope: str | None = None
    action_classes: tuple[str, ...] = ()
    mode: str | None = None
    reduced_off_unattended_partition_protection: bool | None = None


class FinalQuantityProofRule(FrozenModel):
    """A Final Quantity Proof recipe for an order type (ADR-002-004 §15 line 843-867)."""

    order_type: str | None = None
    prohibited_proofs: frozenset[ProhibitedProof] = frozenset()
    no_later_change_asserted: bool | None = None
    late_event_window_defined: bool | None = None


class RequiredCapabilitySet(FrozenModel):
    """The injected required-capability set for an action class (ADR-002-004 §11; §5.1)."""

    required_dimensions: frozenset[CapabilityDimension] = frozenset()
    required_level: AssuranceLevel | None = None
    minimum_live_gate_satisfied: bool | None = None
    approved_fallback_dimensions: frozenset[CapabilityDimension] = frozenset()


class FallbackSpec(FrozenModel):
    """An injected fallback specification for a deficient dimension (ADR §13; §5.3)."""

    widens_capability: bool | None = None
    conservative: bool | None = None
    tied_to_authority_and_risk_scope: bool | None = None


class ObservedBehavior(FrozenModel):
    """Injected observed behavior for the drift predicate (ADR-002-004 §20.1 line 1006-1016)."""

    dimension: CapabilityDimension | None = None
    duplicate_order_despite_idempotency: bool = False
    event_before_declared_impossible: bool = False
    missing_sequence: bool = False
    late_fill_beyond_window: bool = False
    query_omission_beyond_bound: bool = False
    unexpected_rate_limit: bool = False
    session_behavior_change: bool = False
    unknown_status_code: bool = False
    unit_multiplier_mismatch: bool = False


class BrokerEvidenceRef(FrozenModel):
    """An injected scalar reference to broker evidence (design #10 §3.5)."""

    evidence_id: str | None = None
    generation: int | None = None
    digest: str | None = None
    environment: str | None = None


class FinalQuantityEvidence(FrozenModel):
    """Injected observed evidence for a Final Quantity Proof (ADR-002-004 §15.2 line 843-851)."""

    broker_order_identity_or_bounded_effect: bool | None = None
    final_cumulative_filled_quantity: bool | None = None
    zero_remaining_executable_quantity: bool | None = None
    corrections_busts_late_events_handled: bool | None = None
    evidence_source_provenance: bool | None = None
    within_valid_window: bool | None = None
    ordering_waiting_rule_satisfied: bool | None = None
    sole_prohibited_basis: ProhibitedProof | None = None


class UncertainSendVerdict(FrozenModel):
    """The restrictive verdict for an uncertain send (ADR-002-004 §12.4 line 640-646)."""

    no_retry: bool = True
    no_capacity_release: bool = True
    no_assume_rejection: bool = True
    no_new_conflicting_in_containment: bool = True
    start_reconciliation: bool = True
    enter_unknown_or_contained: bool = True


_NON_LIVE_MODE = "NON_LIVE"


class BrokerCapabilityProfile(IndependentIdArtifact):
    """An append-only, version-immutable Broker Capability Profile (ADR-002-004 §7; §21)."""

    _ID_FIELD: ClassVar[str] = "profile_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "profile_key",
        "profile_version",
        "conformance_class",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "profile_key",
            "profile_version",
            "declarations",
            "conformance_class",
            "live_scope",
            "final_quantity_proof_rules",
            "evidence_package_ref",
            "environment_class",
        }
    )

    profile_id: str | None = None

    profile_key: ProfileKey | None = None
    profile_version: ProfileVersion | None = None
    declarations: tuple[CapabilityDeclaration, ...] = ()
    conformance_class: ConformanceClass | None = None
    live_scope: LiveScope | None = None
    final_quantity_proof_rules: tuple[FinalQuantityProofRule, ...] = ()
    evidence_package_ref: str | None = None
    environment_class: BrokerEnvironment | None = None

    profile_order: int | None = None

    @model_validator(mode="after")
    def _simulation_is_non_live(self) -> BrokerCapabilityProfile:
        """A profile claiming the simulation class may not also describe live trading."""
        if self.environment_class is not BrokerEnvironment.BROKER_SIMULATION:
            return self
        scope = self.live_scope
        if scope is None or scope.mode != _NON_LIVE_MODE or scope.action_classes:
            raise ArtifactIntegrityError(
                "BrokerCapabilityProfile: environment_class BROKER_SIMULATION requires a "
                f"live_scope with mode {_NON_LIVE_MODE!r} and no live action classes"
            )
        return self

    def declaration_for(
        self, dimension: CapabilityDimension
    ) -> CapabilityDeclaration | None:
        """Return the declaration for ``dimension``, or ``None`` if **undeclared**."""
        for decl in self.declarations:
            if decl.dimension is dimension:
                return decl
        return None
