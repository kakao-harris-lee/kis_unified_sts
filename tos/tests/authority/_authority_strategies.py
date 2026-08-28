"""Shared valid-artifact builders + strategies for the Safety Authority tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design §0.3). The
``issue_*`` / ``*_required_kwargs`` builders populate every safety-load-bearing covered
field each artifact's issuance guard demands, so a "valid" fixture is genuinely valid
(never the all-null coverage illusion). The reserved ``"TBD"`` placeholder is excluded
from required-field text (a past flaky-test lesson).
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.authority import (
    AuthorityEpochState,
    AuthorityTransitionReason,
    CapabilityType,
    CapabilityValidityInputs,
    CurrentnessWitness,
    DegradedLeaseOwnershipRecord,
    SafetyAuthorityCapability,
)
from tos.authority.records import AuthorityEpochTransitionRecord
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.time import TimeContinuityIdentity

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved
#: ``"TBD"`` placeholder the issuance guard rejects — design §2.2/§3.2).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

#: A non-negative integer coordinate strategy (epochs / sequences / bounds; no float).
NON_NEGATIVE_INT = st.integers(min_value=0, max_value=1000)


# ---------------------------------------------------------------------------
# Safety Authority Capability
# ---------------------------------------------------------------------------


def capability_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Capability issuance kwargs with every required covered field concrete.

    Includes the two numeric claims (``maximum_quantity`` / risk-vector link) so a
    fixture is *consumption*-valid, not just ISSUED-reachable — the validity predicate's
    numeric-claim precondition (§5.2 Gap) needs them present.
    """
    base: dict[str, Any] = {
        "capability_id": "cap-1",
        "capability_type": CapabilityType.NORMAL_RISK_INCREASING,
        "issuer_identity": "iss-1",
        "authority_domain": "acct-1",
        "safety_authority_epoch": 5,
        "subject_service_identity": "svc-1",
        "environment_and_mode": "live",
        "account_scope": "acct-1",
        "permitted_action_class": "OPEN",
        "issue_sequence": 1,
        "hard_safety_envelope_version": "h-1",
        "runtime_safety_profile_version": "r-1",
        "maximum_quantity": 10,
        "maximum_risk_vector_effect_or_reservation_identity": "rsv-1",
        "nonce": "nonce-1",
    }
    base.update(overrides)
    return base


def issue_capability(**overrides: Any) -> SafetyAuthorityCapability:
    """Issue a valid :class:`SafetyAuthorityCapability`."""
    return SafetyAuthorityCapability.issue(
        scheme=SCHEME, **capability_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Authority Epoch Transition Record
# ---------------------------------------------------------------------------


def transition_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Transition issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "transition_id": "tr-1",
        "authority_domain": "acct-1",
        "old_epoch": 4,
        "new_epoch": 5,
        "leader_identity": "leader-1",
        "transition_reason": AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    }
    base.update(overrides)
    return base


def issue_transition(**overrides: Any) -> AuthorityEpochTransitionRecord:
    """Issue a valid :class:`AuthorityEpochTransitionRecord`."""
    return AuthorityEpochTransitionRecord.issue(
        scheme=SCHEME, **transition_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Degraded Lease Ownership Record
# ---------------------------------------------------------------------------


def anchor(**overrides: Any) -> TimeContinuityIdentity:
    """A concrete, continuous monotonic anchor (all identity coordinates present)."""
    base: dict[str, Any] = {
        "host_or_runtime_id": "host-1",
        "boot_id": "boot-1",
        "process_id": "proc-1",
        "monotonic_anchor_id": "mono-1",
        "monotonic_anchor_value": 100,
    }
    base.update(overrides)
    return TimeContinuityIdentity(**base)


def lease_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Lease-ownership issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "lease_ownership_id": "lo-1",
        "receipt_process_identity": "proc-1",
        "host_or_runtime_identity": "host-1",
        "safety_authority_epoch": 5,
        "capability_digest": "capdigest-1",
        "exclusive_scope": "acct-1/ES/PROTECT",
        "referenced_capacity_lease_id": "rcl-lease-1",
    }
    base.update(overrides)
    return base


def issue_lease(**overrides: Any) -> DegradedLeaseOwnershipRecord:
    """Issue a valid :class:`DegradedLeaseOwnershipRecord`.

    Populates the RCL scalar references + monotonic anchor a validity check needs;
    callers override the exclusivity key (``exclusive_scope`` /
    ``referenced_capacity_lease_id``) and anchor to exercise the guards.
    """
    base: dict[str, Any] = {
        "local_monotonic_anchor": anchor(),
        "referenced_protective_pool_identity": "rcl-pool-1",
        "current_owner_identity": "owner-1",
        "approved_maximum_duration": 5000,
        "drift_and_suspension_assumptions": "assumptions-profile-1",
    }
    base.update(overrides)
    return DegradedLeaseOwnershipRecord.issue(
        scheme=SCHEME, **lease_required_kwargs(**base)
    )


# ---------------------------------------------------------------------------
# Injected predicate-input helpers
# ---------------------------------------------------------------------------


def epoch_state(
    *, authority_domain: str | None = "acct-1", current_epoch_floor: int | None = 5
) -> AuthorityEpochState:
    """A concrete per-domain epoch-floor state."""
    return AuthorityEpochState(
        authority_domain=authority_domain, current_epoch_floor=current_epoch_floor
    )


def fresh_witness(**overrides: Any) -> CurrentnessWitness:
    """An admissible online currentness witness (present, in-bound, not conflicting)."""
    base: dict[str, Any] = {
        "present": True,
        "within_containment_bound": True,
        "witness_source": "registry-1",
        "conflicting": False,
    }
    base.update(overrides)
    return CurrentnessWitness(**base)


def valid_inputs(**overrides: Any) -> CapabilityValidityInputs:
    """Validity inputs that (with a current epoch + valid capability) pass all of §5.2."""
    base: dict[str, Any] = {
        "currentness": fresh_witness(),
        "revocation_status": "not_revoked",
        "superseded": False,
        "consumed": False,
        "issuer_key_status": "valid",
        "environment_and_mode_matches": True,
        "dominating_restriction": False,
    }
    base.update(overrides)
    return CapabilityValidityInputs(**base)


#: The additive-term kwargs feeding ``conservative_usable_lifetime`` with a positive
#: remaining lifetime (usable) — callers override to exercise the negative-term guard.
def positive_lifetime_terms(**overrides: Any) -> dict[str, Any]:
    """Time-term kwargs yielding a positive usable lifetime (a lease still usable)."""
    base: dict[str, Any] = {
        "issued_lifetime": 5000,
        "elapsed_monotonic": 100,
        "source_transport_uncertainty": 10,
        "max_drift_error": 10,
        "suspension_uncertainty": 10,
        "safety_margin": 10,
    }
    base.update(overrides)
    return base


def valid_lease_kwargs(**overrides: Any) -> dict[str, Any]:
    """Keyword args for ``degraded_lease_valid`` that make a lease valid (all 7 conditions)."""
    from tos.authority import AuthorityState
    from tos.time import HealthState

    base: dict[str, Any] = {
        "protective_classification_present": True,
        "broker_capability_permits": True,
        "dominating_state": AuthorityState.DEGRADED_PROTECTIVE,
        "health_state": HealthState.DEGRADED_HOLDOVER,
        "continuity_now": anchor(),
        "suspension_ms": 0,
        "max_suspension_ms": 2000,
        **positive_lifetime_terms(),
    }
    base.update(overrides)
    return base
