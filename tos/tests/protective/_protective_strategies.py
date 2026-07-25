"""Shared valid-artifact builders + strategies for the protective property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #11 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 REJECT lesson):

* a ``PHYSICALLY_RESERVED`` declaration built here carries real ``reservation_mechanism_
  evidenced`` + ``failure_independence_evidenced`` + ``evidence_reference`` (never the
  "reserved with empty evidence" illegal fixture);
* an **undeclared** domain is genuinely absent from the ``declarations`` tuple (the
  ``drop_domain`` helper), **not** a ``guarantee_level=UNAVAILABLE`` declaration — the two
  resolve the same but are distinct fixtures and are built distinctly (design #11 §7);
* a ``PROTECTIVE_PROVEN`` comparison carries real ``final < current`` / ``worst <= no-action``
  magnitudes (a contradictory comparison is an illegal fixture).

The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.protective import (
    AggregateRiskComparison,
    ContainedEmergencyInputs,
    DeRestrictionInputs,
    GuaranteeLevel,
    HardEnvelopeRef,
    IntermediateStateWitness,
    ProtectiveActionEnvelope,
    ProtectiveCapacityProfile,
    ProtectiveLeaseAdmissibilityScope,
    ProtectiveResourceDomain,
    ProtectiveResourceDomainDeclaration,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

# ---------------------------------------------------------------------------
# Enum / scalar strategies
# ---------------------------------------------------------------------------

DOMAINS = st.sampled_from(list(ProtectiveResourceDomain))
LEVELS = st.sampled_from(list(GuaranteeLevel))
#: The three non-reserved guarantee levels (never reserved — §3.1.4 line 144).
NON_RESERVED_LEVELS = st.sampled_from(
    [
        GuaranteeLevel.PRIORITIZED_ONLY,
        GuaranteeLevel.BEST_EFFORT,
        GuaranteeLevel.UNAVAILABLE,
    ]
)
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: An injected non-negative integer bound (+ ``None`` for the fail-closed direction; §8).
OPT_BOUND = st.none() | st.integers(min_value=0, max_value=1000)


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


def reserved_declaration(
    domain: ProtectiveResourceDomain = ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH,
    level: GuaranteeLevel = GuaranteeLevel.PHYSICALLY_RESERVED,
    **overrides: Any,
) -> ProtectiveResourceDomainDeclaration:
    """A genuinely-reserved declaration with real evidence flags (§7 clean fixture)."""
    # The effective level may come from the positional ``level`` or a ``guarantee_level``
    # override; the common-mode note is attached whenever the effective level is
    # LOGICALLY_RESERVED (so LOGICALLY_RESERVED stays a genuinely-reserved clean fixture).
    effective_level = overrides.get("guarantee_level", level)
    base: dict[str, Any] = {
        "domain": domain,
        "guarantee_level": level,
        "reservation_mechanism_evidenced": True,
        "failure_independence_evidenced": True,
        "evidence_reference": "ev-1",
    }
    if effective_level is GuaranteeLevel.LOGICALLY_RESERVED:
        base["common_mode_note"] = "shares serialized session"
    base.update(overrides)
    return ProtectiveResourceDomainDeclaration(**base)


def all_domains_declared(
    level: GuaranteeLevel = GuaranteeLevel.PHYSICALLY_RESERVED,
) -> tuple[ProtectiveResourceDomainDeclaration, ...]:
    """A declaration for **every** required domain (a genuinely complete profile)."""
    return tuple(
        reserved_declaration(domain=domain, level=level)
        for domain in ProtectiveResourceDomain
    )


def drop_domain(
    dropped: ProtectiveResourceDomain,
    level: GuaranteeLevel = GuaranteeLevel.PHYSICALLY_RESERVED,
) -> tuple[ProtectiveResourceDomainDeclaration, ...]:
    """Every required domain **except** ``dropped`` — genuinely absent (§7 undeclared fixture)."""
    return tuple(
        reserved_declaration(domain=domain, level=level)
        for domain in ProtectiveResourceDomain
        if domain is not dropped
    )


# ---------------------------------------------------------------------------
# Envelopes / scope
# ---------------------------------------------------------------------------


def action_envelope(**overrides: Any) -> ProtectiveActionEnvelope:
    """A protective action envelope with concrete, subordinate magnitudes."""
    base: dict[str, Any] = {
        "permitted_action_classes": ("PROTECTIVE_CANCEL_OR_REPLACE",),
        "max_quantity": Decimal("1.0"),
        "max_notional": Decimal("10.0"),
        "max_gross_increase": Decimal("1.0"),
        "max_margin": Decimal("1.0"),
        "max_action_rate": Decimal("1.0"),
        "max_duration": Decimal("1.0"),
    }
    base.update(overrides)
    return ProtectiveActionEnvelope(**base)


def hard_envelope(**overrides: Any) -> HardEnvelopeRef:
    """A Hard Safety Envelope whose axes dominate the protective envelope (subordinate)."""
    base: dict[str, Any] = {
        "max_quantity": Decimal("10.0"),
        "max_notional": Decimal("100.0"),
        "max_gross_increase": Decimal("10.0"),
        "max_margin": Decimal("10.0"),
        "max_action_rate": Decimal("10.0"),
        "max_duration": Decimal("10.0"),
    }
    base.update(overrides)
    return HardEnvelopeRef(**base)


def lease_scope(**overrides: Any) -> ProtectiveLeaseAdmissibilityScope:
    """A pre-proven lease-admissibility scope marker with a concrete staleness tolerance."""
    base: dict[str, Any] = {
        "pre_proven_accounts": ("acct-1",),
        "staleness_tolerance": "adr-002-019-ref",
    }
    base.update(overrides)
    return ProtectiveLeaseAdmissibilityScope(**base)


# ---------------------------------------------------------------------------
# ProtectiveCapacityProfile
# ---------------------------------------------------------------------------


def profile_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Profile issuance kwargs with every required covered field concrete + all 7 domains."""
    base: dict[str, Any] = {
        "profile_id": "prof-1",
        "profile_version": "v1",
        "approver_identity": "approver-1",
        "declarations": all_domains_declared(),
        "action_envelope": action_envelope(),
        "lease_admissibility_scope": lease_scope(),
    }
    base.update(overrides)
    return base


def issue_profile(**overrides: Any) -> ProtectiveCapacityProfile:
    """Issue a valid :class:`ProtectiveCapacityProfile` (all required covered fields concrete)."""
    return ProtectiveCapacityProfile.issue(
        scheme=SCHEME, **profile_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Classification inputs (§6.1 / §6.2)
# ---------------------------------------------------------------------------


def proven_comparison(**overrides: Any) -> AggregateRiskComparison:
    """A comparison whose final risk is genuinely below current (a real protective move)."""
    base: dict[str, Any] = {
        "final_conservative_risk": Decimal("1.0"),
        "current_conservative_risk": Decimal("5.0"),
        "no_action_risk": Decimal("5.0"),
        "already_exceeded_regime": False,
    }
    base.update(overrides)
    return AggregateRiskComparison(**base)


def proven_intermediate(**overrides: Any) -> IntermediateStateWitness:
    """An intermediate witness whose worst state is no worse than no-action, bounded space."""
    base: dict[str, Any] = {
        "worst_intermediate_risk": Decimal("4.0"),
        "credible_space_bounded": True,
        "no_credible_intermediate_increases_exceedance": True,
    }
    base.update(overrides)
    return IntermediateStateWitness(**base)


# ---------------------------------------------------------------------------
# De-restriction / emergency inputs (§8.5 / §8.3.1)
# ---------------------------------------------------------------------------


def admissible_derestriction(**overrides: Any) -> DeRestrictionInputs:
    """De-restriction inputs that (with no forbidden sole basis) satisfy all four conditions."""
    base: dict[str, Any] = {
        "reconciled_authoritative_state": True,
        "safety_authority_current": True,
        "hard_and_runtime_profile_valid": True,
        "critical_input_trust_restored": True,
        "explicit_safety_authority_decision": True,
        "dominating_halt_or_incident": False,
    }
    base.update(overrides)
    return DeRestrictionInputs(**base)


def admissible_emergency(**overrides: Any) -> ContainedEmergencyInputs:
    """CONTAINED emergency inputs with all five §8.3.1 conjuncts positively True."""
    base: dict[str, Any] = {
        "in_preapproved_bounded_set": True,
        "reduce_only_by_construction": True,
        "within_bounded_emergency_envelope": True,
        "independently_authorized": True,
        "potentially_live_final_quantity_rule_preserved": True,
    }
    base.update(overrides)
    return ContainedEmergencyInputs(**base)


# ---------------------------------------------------------------------------
# Reserve sufficiency / account minimum maps
# ---------------------------------------------------------------------------


def sufficient_forecast(
    value: Decimal = Decimal("10.0"),
) -> dict[ProtectiveResourceDomain, Decimal]:
    """A per-domain forecast capacity that meets any modest minimum."""
    return dict.fromkeys(ProtectiveResourceDomain, value)


def approved_minimum(
    value: Decimal = Decimal("1.0"),
) -> dict[ProtectiveResourceDomain, Decimal]:
    """A per-domain approved minimum below the sufficient forecast."""
    return dict.fromkeys(ProtectiveResourceDomain, value)
