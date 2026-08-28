"""Shared valid-artifact builders + strategies for the Live Authorization tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design §0.3). The ``issue_*``
/ ``*_required_kwargs`` builders populate every safety-load-bearing covered field each
artifact's issuance guard demands, so a "valid" fixture is genuinely valid (never the
all-null coverage illusion). The ``valid_*`` predicate-input builders return state that
makes the corresponding predicate positively ``True`` (guards fire on the True side too);
callers override single fields to exercise each fail-closed branch. The reserved ``"TBD"``
placeholder is excluded from required-field text (a past flaky-test lesson).
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.authority import (
    AuthorityEpochState,
    AuthorityState,
    CurrentnessWitness,
    RearmChecklist,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.liveauth import (
    ContinuousValidityInputs,
    DualControlAttestation,
    InPlaceExpansionInputs,
    LimitLayering,
    LiveAuthorization,
    LiveAuthorizationScope,
    LiveAuthorizationTransitionRecord,
    ReArmApprovalRecord,
    ReArmPathKind,
    Safe053VariantAttestation,
)
from tos.liveauth.predicates import (
    _INJECTED_CONTINUOUS_CONDITIONS,
    _PROPORTIONAL_EXPANSION_FLAGS,
    _SAFE053_CONTROLS,
    _VARIANT_ENVIRONMENTAL_PREREQUISITES,
)
from tos.time import HealthState

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved
#: ``"TBD"`` placeholder the issuance guard rejects — design §2.2/§3.2).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

#: A non-negative integer coordinate strategy (epochs / sequences / bounds; no float).
NON_NEGATIVE_INT = st.integers(min_value=0, max_value=1000)

#: The 14 authority re-arm prerequisites (quorum-path checklist all-True set).
_ALL_REARM_PREREQUISITES: tuple[str, ...] = (
    *_VARIANT_ENVIRONMENTAL_PREREQUISITES,
    "explicit_human_dual_control_complete",
)


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def full_scope(**overrides: Any) -> LiveAuthorizationScope:
    """A concrete, non-empty scope in every one of the seven dimensions."""
    base: dict[str, Any] = {
        "accounts": frozenset({"acct-1"}),
        "strategies": frozenset({"strat-1"}),
        "instrument_classes": frozenset({"equity"}),
        "venues": frozenset({"venue-1"}),
        "sessions": frozenset({"regular"}),
        "order_types": frozenset({"LIMIT"}),
        "action_classes": frozenset({"OPEN"}),
    }
    base.update(overrides)
    return LiveAuthorizationScope(**base)


def wide_scope(**overrides: Any) -> LiveAuthorizationScope:
    """A scope that is a strict superset of :func:`full_scope` in ``accounts``."""
    return full_scope(accounts=frozenset({"acct-1", "acct-2"}), **overrides)


# ---------------------------------------------------------------------------
# Live Authorization record
# ---------------------------------------------------------------------------


def authorization_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Authorization issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "authorization_id": "auth-1",
        "issuer_identity": "iss-1",
        "authority_domain": "acct-1",
        "safety_authority_epoch": 5,
        "live_authorization_scope": full_scope(),
        "hard_safety_envelope_version": "h-1",
        "runtime_safety_profile_version": "r-1",
        "broker_capability_profile_version": "b-1",
        "issue_sequence": 1,
        "activation_condition": "on-approval",
    }
    base.update(overrides)
    return base


def issue_authorization(**overrides: Any) -> LiveAuthorization:
    """Issue a valid :class:`LiveAuthorization`."""
    return LiveAuthorization.issue(
        scheme=SCHEME, **authorization_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Live Authorization Transition Record
# ---------------------------------------------------------------------------


def transition_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Transition issuance kwargs with every required covered field concrete."""
    from tos.liveauth import LiveAuthorizationState

    base: dict[str, Any] = {
        "transition_id": "tr-1",
        "authorization_id": "auth-1",
        "from_state": LiveAuthorizationState.ISSUED,
        "to_state": LiveAuthorizationState.ACTIVE,
        "transition_reason": "activation",
    }
    base.update(overrides)
    return base


def issue_transition(**overrides: Any) -> LiveAuthorizationTransitionRecord:
    """Issue a valid :class:`LiveAuthorizationTransitionRecord`."""
    return LiveAuthorizationTransitionRecord.issue(
        scheme=SCHEME, **transition_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Re-arm Approval Record
# ---------------------------------------------------------------------------


def approval_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Approval issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "approval_record_id": "appr-1",
        "requested_scope": full_scope(),
        "dual_control_path": ReArmPathKind.QUORUM,
    }
    base.update(overrides)
    return base


def issue_approval(**overrides: Any) -> ReArmApprovalRecord:
    """Issue a valid :class:`ReArmApprovalRecord`."""
    return ReArmApprovalRecord.issue(
        scheme=SCHEME, **approval_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Continuous-validity inputs
# ---------------------------------------------------------------------------


def valid_continuous_validity_inputs(**overrides: Any) -> ContinuousValidityInputs:
    """Inputs that (with :func:`issue_authorization`) make ``continuous_validity`` True.

    Epoch floor / domain align with :func:`authorization_required_kwargs` (epoch 5,
    domain ``acct-1``); time is TRUSTED; no dominating restriction; freshness positive;
    all ten injected conditions True.
    """
    base: dict[str, Any] = {
        "authority_epoch_state": AuthorityEpochState(
            authority_domain="acct-1", current_epoch_floor=5
        ),
        "currentness_witness": CurrentnessWitness(
            present=True, within_containment_bound=True, conflicting=False
        ),
        "dominating_state": AuthorityState.LIVE_NORMAL,
        "outstanding_capabilities": (),
        "time_health_state": HealthState.TRUSTED,
        "snapshot_age_bound": 10,
        "max_consumer_age_ms": 1000,
        "max_live_authorization_validity": 5000,
        "authorization_elapsed": 100,
        "source_transport_uncertainty": 10,
        "max_drift_error": 10,
        "suspension_uncertainty": 10,
        "safety_margin": 10,
        **dict.fromkeys(_INJECTED_CONTINUOUS_CONDITIONS, True),
    }
    base.update(overrides)
    return ContinuousValidityInputs(**base)


# ---------------------------------------------------------------------------
# Re-arm checklists + dual control
# ---------------------------------------------------------------------------


def armable_checklist(**overrides: Any) -> RearmChecklist:
    """A checklist with all 14 prerequisites True and distinct dual-control principals."""
    base: dict[str, Any] = dict.fromkeys(_ALL_REARM_PREREQUISITES, True)
    base["limit_enlarger_principal"] = "principal-A"
    base["armer_principal"] = "principal-B"
    base.update(overrides)
    return RearmChecklist(**base)


def variant_checklist(**overrides: Any) -> RearmChecklist:
    """A checklist with the 13 variant-path environmental prerequisites True.

    The SoD prerequisite (``explicit_human_dual_control_complete``) is left None — the
    variant path does not read it (SoD is owned by ``rearm_dual_control_satisfied``).
    """
    base: dict[str, Any] = dict.fromkeys(_VARIANT_ENVIRONMENTAL_PREREQUISITES, True)
    base["limit_enlarger_principal"] = "principal-A"
    base["armer_principal"] = "principal-A"
    base.update(overrides)
    return RearmChecklist(**base)


def full_variant(**overrides: Any) -> Safe053VariantAttestation:
    """A SAFE-053 variant with all seven compensating controls True."""
    base: dict[str, Any] = dict.fromkeys(_SAFE053_CONTROLS, True)
    base.update(overrides)
    return Safe053VariantAttestation(**base)


def quorum_attestation(**overrides: Any) -> DualControlAttestation:
    """A quorum (two distinct principals + count >= 2) dual-control attestation."""
    base: dict[str, Any] = {
        "armer_principal": "principal-B",
        "limit_change_approver_principal": "principal-A",
        "distinct_approver_count": 2,
        "path": ReArmPathKind.QUORUM,
    }
    base.update(overrides)
    return DualControlAttestation(**base)


def solo_variant_attestation(**overrides: Any) -> DualControlAttestation:
    """A SAFE-053 solo-variant dual-control attestation (same principal + full variant)."""
    base: dict[str, Any] = {
        "armer_principal": "principal-A",
        "limit_change_approver_principal": "principal-A",
        "variant": full_variant(),
        "path": ReArmPathKind.GOVERNED_SINGLE_OPERATOR,
    }
    base.update(overrides)
    return DualControlAttestation(**base)


# ---------------------------------------------------------------------------
# Limit layering + §14.1 expansion inputs
# ---------------------------------------------------------------------------


def valid_layering(**overrides: Any) -> LimitLayering:
    """A limit stack satisfying per-action <= live-auth <= runtime-profile <= hard-envelope."""
    base: dict[str, Any] = {
        "governed_dimension": "quantity",
        "per_action_limit": 1,
        "live_authorization_limit": 2,
        "runtime_safety_profile_limit": 3,
        "hard_safety_envelope_limit": 4,
        "runtime_safety_profile_version": "r-1",
        "hard_safety_envelope_version": "h-1",
    }
    base.update(overrides)
    return LimitLayering(**base)


def valid_expansion_inputs(**overrides: Any) -> InPlaceExpansionInputs:
    """§14.1 inputs that make ``in_place_expansion_admissible`` True (with ``existing-1``)."""
    base: dict[str, Any] = {
        "delta_scope": full_scope(accounts=frozenset({"acct-2"})),
        "new_delta_authorization_id": "delta-1",
        "existing_authorization_id": "existing-1",
        "continuous_validity_unbroken": True,
        "dual_control": quorum_attestation(),
        "progressive_promotion_gate_satisfied": True,
        **dict.fromkeys(_PROPORTIONAL_EXPANSION_FLAGS, True),
    }
    base.update(overrides)
    return InPlaceExpansionInputs(**base)
