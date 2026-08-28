"""Shared valid-artifact builders + strategies for the brokercap property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #10 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 REJECT lesson):

* a ``VERIFIED`` declaration built here carries a real ``evidence_reference`` +
  ``assurance_level`` (never the "VERIFIED with empty evidence" illegal fixture);
* an **undeclared** dimension is genuinely absent from the ``declarations`` tuple (the
  ``undeclared_required`` helper), **not** a ``status=UNKNOWN`` declaration — the two are
  treated the same by the predicate but are distinct fixtures and are built distinctly;
* a ``CONTRADICTORY`` fixture carries a real conflicting observation pair.

The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.brokercap import (
    AssuranceLevel,
    BrokerCapabilityProfile,
    BrokerEvidenceRef,
    CapabilityDeclaration,
    CapabilityDimension,
    CapabilityStatus,
    ConformanceClass,
    FallbackSpec,
    FinalQuantityEvidence,
    FinalQuantityProofRule,
    LiveScope,
    ObservedBehavior,
    ProfileKey,
    ProfileVersion,
    ProhibitedProof,
    RequiredCapabilitySet,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

# ---------------------------------------------------------------------------
# Enum / scalar strategies
# ---------------------------------------------------------------------------

STATUSES = st.sampled_from(list(CapabilityStatus))
DIMENSIONS = st.sampled_from(list(CapabilityDimension))
LEVELS = st.sampled_from(list(AssuranceLevel))
CLASSES = st.sampled_from(list(ConformanceClass))
PROHIBITED_PROOFS = st.sampled_from(list(ProhibitedProof))
#: The five non-authorizing statuses (§5.3 line 146 — never authorize).
NON_AUTHORIZING_STATUSES = st.sampled_from(
    [
        CapabilityStatus.DOCUMENTED_NOT_VERIFIED,
        CapabilityStatus.UNSUPPORTED,
        CapabilityStatus.CONTRADICTORY,
        CapabilityStatus.UNKNOWN,
        CapabilityStatus.EXPIRED,
    ]
)
#: Injected bool | None flag (fail-closed on None / False).
TRIBOOL = st.sampled_from([True, False, None])
#: An injected non-negative integer bound (+ None for the fail-closed direction; §8).
OPT_BOUND = st.none() | st.integers(min_value=0, max_value=1000)


# ---------------------------------------------------------------------------
# Value builders
# ---------------------------------------------------------------------------


def verified_declaration(
    dimension: CapabilityDimension = CapabilityDimension.ORDER_IDENTITY,
    level: AssuranceLevel = AssuranceLevel.LEVEL_3_RESTRICTED_PRODUCTION,
    **overrides: Any,
) -> CapabilityDeclaration:
    """A genuinely-VERIFIED declaration with a real evidence reference (§7 clean fixture)."""
    base: dict[str, Any] = {
        "dimension": dimension,
        "status": CapabilityStatus.VERIFIED,
        "assurance_level": level,
        "evidence_reference": "ev-1",
    }
    base.update(overrides)
    return CapabilityDeclaration(**base)


def profile_key(**overrides: Any) -> ProfileKey:
    """A profile key with a concrete environment + credential scope."""
    base: dict[str, Any] = {
        "broker_id": "broker-x",
        "environment": "live",
        "credential_scope": "trade",
    }
    base.update(overrides)
    return ProfileKey(**base)


def profile_version(**overrides: Any) -> ProfileVersion:
    """A concrete immutable profile version block."""
    base: dict[str, Any] = {
        "profile_version": "v1",
        "effective_date": "2026-07-25",
        "approver_identity": "approver-1",
    }
    base.update(overrides)
    return ProfileVersion(**base)


def live_scope(**overrides: Any) -> LiveScope:
    """A live scope with a scale-normalized quantity risk limit."""
    base: dict[str, Any] = {
        "quantity_risk_limit": Decimal("1.0"),
        "action_classes": ("entry",),
    }
    base.update(overrides)
    return LiveScope(**base)


def fqp_rule(**overrides: Any) -> FinalQuantityProofRule:
    """A Final Quantity Proof rule naming all 7 prohibited proofs + a §15.4 terminal marker."""
    base: dict[str, Any] = {
        "order_type": "LIMIT",
        "prohibited_proofs": frozenset(ProhibitedProof),
        "no_later_change_asserted": True,
    }
    base.update(overrides)
    return FinalQuantityProofRule(**base)


def complete_fqp_evidence(**overrides: Any) -> FinalQuantityEvidence:
    """A fully-satisfied §15.2 Final Quantity evidence bundle (all conjuncts True)."""
    base: dict[str, Any] = {
        "broker_order_identity_or_bounded_effect": True,
        "final_cumulative_filled_quantity": True,
        "zero_remaining_executable_quantity": True,
        "corrections_busts_late_events_handled": True,
        "evidence_source_provenance": True,
        "within_valid_window": True,
        "ordering_waiting_rule_satisfied": True,
        "sole_prohibited_basis": None,
    }
    base.update(overrides)
    return FinalQuantityEvidence(**base)


def conservative_fallback(**overrides: Any) -> FallbackSpec:
    """A monotone-restrictive fallback (does not widen; conservative; tied to scope)."""
    base: dict[str, Any] = {
        "widens_capability": False,
        "conservative": True,
        "tied_to_authority_and_risk_scope": True,
    }
    base.update(overrides)
    return FallbackSpec(**base)


def broker_evidence(**overrides: Any) -> BrokerEvidenceRef:
    """A concrete broker-evidence reference with a same-environment coordinate."""
    base: dict[str, Any] = {
        "evidence_id": "bev-1",
        "digest": "d1",
        "environment": "live",
    }
    base.update(overrides)
    return BrokerEvidenceRef(**base)


def observed_clean(**overrides: Any) -> ObservedBehavior:
    """An observation consistent with the declaration (no contradiction flag set)."""
    return ObservedBehavior(**overrides)


def observed_drift(
    dimension: CapabilityDimension = CapabilityDimension.SUBMISSION_IDEMPOTENCY,
    **overrides: Any,
) -> ObservedBehavior:
    """A genuine contradiction observation (a real conflicting pair — §7 CONTRADICTORY fixture)."""
    base: dict[str, Any] = {
        "dimension": dimension,
        "duplicate_order_despite_idempotency": True,
    }
    base.update(overrides)
    return ObservedBehavior(**base)


# ---------------------------------------------------------------------------
# RequiredCapabilitySet
# ---------------------------------------------------------------------------


def required_set(
    dimensions: frozenset[CapabilityDimension] = frozenset(
        {CapabilityDimension.ORDER_IDENTITY}
    ),
    level: AssuranceLevel = AssuranceLevel.LEVEL_3_RESTRICTED_PRODUCTION,
    **overrides: Any,
) -> RequiredCapabilitySet:
    """A required set gated open (minimum-live gate satisfied) — the positive fixture."""
    base: dict[str, Any] = {
        "required_dimensions": dimensions,
        "required_level": level,
        "minimum_live_gate_satisfied": True,
    }
    base.update(overrides)
    return RequiredCapabilitySet(**base)


# ---------------------------------------------------------------------------
# BrokerCapabilityProfile
# ---------------------------------------------------------------------------


def profile_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Profile issuance kwargs with every required covered field concrete + one VERIFIED decl."""
    base: dict[str, Any] = {
        "profile_id": "prof-1",
        "profile_key": profile_key(),
        "profile_version": profile_version(),
        "conformance_class": ConformanceClass.CLASS_A_DETERMINISTIC_LIVE,
        "declarations": (verified_declaration(),),
        "live_scope": live_scope(),
    }
    base.update(overrides)
    return base


def issue_profile(**overrides: Any) -> BrokerCapabilityProfile:
    """Issue a valid :class:`BrokerCapabilityProfile` (all required covered fields concrete)."""
    return BrokerCapabilityProfile.issue(
        scheme=SCHEME, **profile_required_kwargs(**overrides)
    )
