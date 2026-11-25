"""Pure brokercap predicates (design #10 §5, §6)."""

from __future__ import annotations

from tos.brokercap.records import (
    BrokerCapabilityProfile,
    BrokerEvidenceRef,
    CapabilityDeclaration,
    FallbackSpec,
    FinalQuantityEvidence,
    FinalQuantityProofRule,
    ObservedBehavior,
    RequiredCapabilitySet,
    UncertainSendVerdict,
)
from tos.brokercap.vocabulary import (
    ASSURANCE_LEVEL_RANK,
    AUTHORIZING_STATUSES,
    NON_LIVE_OR_SUPERVISED_CLASSES,
    Admissibility,
    AssuranceLevel,
    CapabilityDimension,
    CapabilityStatus,
)


def _declaration_authorizes(
    declaration: CapabilityDeclaration | None,
    required_level: AssuranceLevel | None,
) -> bool:
    """Whether a single declaration authorizes live behavior (ADR §5.3 line 146; §9 line 540)."""
    if declaration is None:
        return False
    if declaration.status not in AUTHORIZING_STATUSES:
        return False
    if (
        declaration.status is CapabilityStatus.VERIFIED_WITH_RESTRICTION
        and declaration.restriction_approved is not True
    ):
        return False
    if required_level is None:
        return False
    declared_rank = ASSURANCE_LEVEL_RANK.get(declaration.assurance_level)  # type: ignore[arg-type]
    required_rank = ASSURANCE_LEVEL_RANK.get(required_level)
    if declared_rank is None or required_rank is None:
        return False
    return declared_rank >= required_rank


def capability_admissible(
    profile: BrokerCapabilityProfile | None,
    action_class: str | None,
    required: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
) -> Admissibility:
    """The central admissibility verdict (ADR-002-004 §1 line 32; §5.2/§11; BC-INV-001/005/008)."""
    del action_class
    if profile is None or required is None:
        return Admissibility.PROHIBITED

    if required.required_dimensions:
        required_dimensions = required.required_dimensions
        required_level = required.required_level
    else:
        required_dimensions = frozenset(CapabilityDimension)
        required_level = AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED
    if required_level is None:
        return Admissibility.PROHIBITED
    if required.minimum_live_gate_satisfied is not True:
        return Admissibility.PROHIBITED
    if version_current is not True:
        return Admissibility.PROHIBITED

    deficient: set[CapabilityDimension] = set()
    for dimension in required_dimensions:
        declaration = profile.declaration_for(dimension)
        if not _declaration_authorizes(declaration, required_level):
            deficient.add(dimension)

    if not deficient:
        return Admissibility.ADMISSIBLE
    if deficient <= required.approved_fallback_dimensions:
        return Admissibility.REDUCED
    return Admissibility.PROHIBITED


def broker_capability_sufficient(
    profile: BrokerCapabilityProfile | None,
    requested_scope: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
) -> bool:
    """Whether the profile is sufficient for the requested scope (design #10 §5.2; §3.4)."""
    return (
        capability_admissible(
            profile, None, requested_scope, version_current=version_current
        )
        is Admissibility.ADMISSIBLE
    )


def broker_capability_added(
    profile: BrokerCapabilityProfile | None,
    delta_scope: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
    envelope_not_expanded: bool | None = None,
) -> bool:
    """Whether the enlarged (delta) scope is fully covered (ADR §14.1; design #10 §5.2)."""
    if envelope_not_expanded is not True:
        return False
    return (
        capability_admissible(
            profile, None, delta_scope, version_current=version_current
        )
        is Admissibility.ADMISSIBLE
    )


def active_profile_version(profile: BrokerCapabilityProfile | None) -> str | None:
    """The active profile version string, or ``None`` (design #10 §3.4 — scalar producer)."""
    if profile is None or profile.profile_version is None:
        return None
    return profile.profile_version.profile_version


def active_conformance_class(profile: BrokerCapabilityProfile | None) -> str | None:
    """The active conformance class as a scalar, or ``None`` (design #10 §3.4 — MINOR-2)."""
    if profile is None or profile.conformance_class is None:
        return None
    return profile.conformance_class.value


def fallback_admissible(fallback: FallbackSpec | None) -> bool:
    """Whether an approved fallback is monotone-restrictive (ADR line 34; §13; §23.9)."""
    if fallback is None:
        return False
    return (
        fallback.widens_capability is False
        and fallback.conservative is True
        and fallback.tied_to_authority_and_risk_scope is True
    )


def uncertain_send_policy(
    idempotency_proven: bool | None = None,
    *,
    timeout_elapsed: bool | None = None,
) -> UncertainSendVerdict:
    """The restrictive policy for an outcome-unknown send (ADR §12.4 line 640-646; §1 line 43)."""
    del idempotency_proven, timeout_elapsed
    return UncertainSendVerdict()


def same_order_retry_allowed(
    profile: BrokerCapabilityProfile | None,
    *,
    idempotency_proven_for_identity_and_window: bool | None = None,
) -> bool:
    """Whether the same order may be network-resent (ADR §12.5 line 650-652; BC-INV-002)."""
    if profile is None:
        return False
    if idempotency_proven_for_identity_and_window is not True:
        return False
    declaration = profile.declaration_for(CapabilityDimension.SUBMISSION_IDEMPOTENCY)
    return declaration is not None and declaration.status is CapabilityStatus.VERIFIED


def external_detection_ok(
    detect_bound: int | None,
    contain_bound: int | None,
    observed_latency: int | None,
) -> bool:
    """Whether external activity is detected + contained within bounds (ADR §16; BC-INV-006)."""
    if detect_bound is None or contain_bound is None or observed_latency is None:
        return False
    return observed_latency <= detect_bound and observed_latency <= contain_bound


def rate_admission_ok(
    ordinary_below_ceiling: bool | None,
    protective_headroom_reserved: bool | None,
) -> bool:
    """Whether ordinary traffic admits below the protective headroom (ADR §17.2 line 926-933)."""
    return ordinary_below_ceiling is True and protective_headroom_reserved is True


def profile_version_current(
    active_version: str | None,
    presented_version: str | None,
    not_expired: bool | None,
    degraded_since_authorization: bool | None,
) -> bool:
    """Whether the presented profile version is current (ADR §7.2/§19; BC-INV-008; §6.1)."""
    if active_version is None or presented_version is None:
        return False
    if active_version != presented_version:
        return False
    if not_expired is not True:
        return False
    return degraded_since_authorization is False


_DRIFT_OBSERVATION_FLAGS: tuple[str, ...] = (
    "duplicate_order_despite_idempotency",
    "event_before_declared_impossible",
    "missing_sequence",
    "late_fill_beyond_window",
    "query_omission_beyond_bound",
    "unexpected_rate_limit",
    "session_behavior_change",
    "unknown_status_code",
    "unit_multiplier_mismatch",
)


def drift_detected(
    declaration: CapabilityDeclaration,
    observed: ObservedBehavior,
) -> bool:
    """Whether observed behavior contradicts a declaration (ADR §20.1 line 1006-1016; §6.2)."""
    if (
        observed.dimension is not None
        and observed.dimension is not declaration.dimension
    ):
        return False
    return any(getattr(observed, flag) for flag in _DRIFT_OBSERVATION_FLAGS)


def apply_drift(
    declaration: CapabilityDeclaration,
    observed: ObservedBehavior,
) -> CapabilityDeclaration:
    """Apply drift restrictively — never widen (ADR §20.2 line 1022; §7.5; §4.3)."""
    if not drift_detected(declaration, observed):
        return declaration
    return declaration.model_copy(
        update={
            "status": CapabilityStatus.CONTRADICTORY,
            "assurance_level": AssuranceLevel.LEVEL_0_UNKNOWN,
        }
    )


_FQP_REQUIRED_CONJUNCTS: tuple[str, ...] = (
    "broker_order_identity_or_bounded_effect",
    "final_cumulative_filled_quantity",
    "zero_remaining_executable_quantity",
    "corrections_busts_late_events_handled",
    "evidence_source_provenance",
    "within_valid_window",
    "ordering_waiting_rule_satisfied",
)


def fqp_adequate(
    rule: FinalQuantityProofRule,
    evidence: FinalQuantityEvidence,
) -> bool:
    """Whether a Final Quantity Proof is adequate (ADR §15.2/§15.3/§15.4; design #10 §6.3)."""
    if evidence.sole_prohibited_basis is not None:
        return False
    if not (
        rule.no_later_change_asserted is True or rule.late_event_window_defined is True
    ):
        return False
    return all(
        getattr(evidence, conjunct) is True for conjunct in _FQP_REQUIRED_CONJUNCTS
    )


def environment_binding_ok(
    evidence_environment: str | None,
    scope_environment: str | None,
    inherited: bool | None,
) -> bool:
    """Whether evidence binds to the scope's environment (ADR §18.4/§13.14; BC-INV-009; §6.4)."""
    if evidence_environment is None or scope_environment is None:
        return False
    if evidence_environment != scope_environment:
        return False
    return inherited is False


def credential_scope_declared_ok(
    profile: BrokerCapabilityProfile | None,
    requested_scope: str | None,
) -> bool:
    """Whether the requested credential scope is within the declared scope (ADR §18.2; §6.4)."""
    if profile is None or profile.profile_key is None or requested_scope is None:
        return False
    declared = profile.profile_key.credential_scope
    return declared is not None and declared == requested_scope


def partition_protective_class(
    single_serialized_channel: bool | None,
    no_rapid_revocation: bool | None,
    shared_global_rate_limit: bool | None,
) -> bool:
    """Whether the three §13.15 weaknesses coincide (ADR §13.15 line 796; design #10 §6.5)."""
    return (
        single_serialized_channel is True
        and no_rapid_revocation is True
        and shared_global_rate_limit is True
    )


def partition_class_scope_ok(
    profile: BrokerCapabilityProfile | None,
    *,
    single_serialized_channel: bool | None,
    no_rapid_revocation: bool | None,
    shared_global_rate_limit: bool | None,
) -> bool:
    """Whether a partition-protective profile's scope is adequately reduced (ADR §13.15)."""
    if profile is None:
        return False
    if not partition_protective_class(
        single_serialized_channel, no_rapid_revocation, shared_global_rate_limit
    ):
        return True
    if profile.conformance_class in NON_LIVE_OR_SUPERVISED_CLASSES:
        return True
    return (
        profile.live_scope is not None
        and profile.live_scope.reduced_off_unattended_partition_protection is True
    )


def broker_evidence_admissible_under_profile(
    profile: BrokerCapabilityProfile | None,
    evidence_ref: BrokerEvidenceRef | None,
    required: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
) -> bool:
    """Whether broker evidence establishes a definite BROKER_ORDER state (design #10 §3.4)."""
    if evidence_ref is None:
        return False
    if evidence_ref.evidence_id is None and evidence_ref.digest is None:
        return False
    return (
        capability_admissible(profile, None, required, version_current=version_current)
        is Admissibility.ADMISSIBLE
    )
