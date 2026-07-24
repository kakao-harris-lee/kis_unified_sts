"""Safety Authority vocabulary — capability types, states, transition reasons.

Spec terms = code terms (design §2, boundary design #1 §2.4). The enums are authored
verbatim from ADR-002-003 §9.2 (capability types), §7 (authority-state precedence),
and §10.2 (epoch-advancement triggers).

Pure module: stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class CapabilityType(StrEnum):
    """The 10 capability types (ADR-002-003 §9.2 line 341-354, verbatim).

    "The names do not determine economic safety" (§9.2 line 356) — restrictive vs
    permissive classification is a separate predicate (§5.3), not the type name.
    HALT / CONTAIN / REARM / LIMIT_ACTIVATION are capability *types* on one capability
    record; there is no separate record class per type (design §2.2).
    """

    NORMAL_RISK_INCREASING = "NORMAL_RISK_INCREASING"
    NORMAL_RISK_REDUCING = "NORMAL_RISK_REDUCING"
    DEGRADED_PROTECTIVE = "DEGRADED_PROTECTIVE"
    CANCEL_REQUEST = "CANCEL_REQUEST"
    PROTECTIVE_CANCEL_OR_REPLACE = "PROTECTIVE_CANCEL_OR_REPLACE"
    HALT = "HALT"
    CONTAIN = "CONTAIN"
    RECONCILIATION_ONLY = "RECONCILIATION_ONLY"
    REARM = "REARM"
    LIMIT_ACTIVATION = "LIMIT_ACTIVATION"


class AuthorityState(StrEnum):
    """The 5 authority-state precedence levels (ADR-002-003 §7 line 228-233, verbatim).

    Ordered by :data:`PRECEDENCE_RANK` (higher = safer / dominant). A transition
    toward a higher rank is a *safer-state* transition (broadly triggerable); a
    transition toward a lower rank is a *permissive* transition (requires current
    Safety Authority, §7 line 239).
    """

    HALTED = "HALTED"
    CONTAINED = "CONTAINED"
    DEGRADED_PROTECTIVE = "DEGRADED_PROTECTIVE"
    LIVE_RESTRICTED = "LIVE_RESTRICTED"
    LIVE_NORMAL = "LIVE_NORMAL"


#: Safety precedence rank (higher = safer / more dominant; ADR-002-003 §7 line
#: 227-233). ``HALTED`` dominates all; ``LIVE_NORMAL`` is dominated by all.
PRECEDENCE_RANK: dict[AuthorityState, int] = {
    AuthorityState.HALTED: 4,
    AuthorityState.CONTAINED: 3,
    AuthorityState.DEGRADED_PROTECTIVE: 2,
    AuthorityState.LIVE_RESTRICTED: 1,
    AuthorityState.LIVE_NORMAL: 0,
}

#: Capability types that dominate any outstanding permissive capability regardless of
#: issue order (restrictive-dominating; SA-INV-010, §7 line 239-242, §20 line 746).
RESTRICTIVE_DOMINATING_TYPES: frozenset[CapabilityType] = frozenset(
    {CapabilityType.HALT, CapabilityType.CONTAIN}
)


class AuthorityTransitionReason(StrEnum):
    """The 8 epoch-advancement triggers (ADR-002-003 §10.2 line 385-394, verbatim).

    Epoch advancement is required after at least these triggers; the transition
    record's ``transition_reason`` is one of them (spec term = code term, §2.3).
    """

    SAFETY_AUTHORITY_FAILOVER = "SAFETY_AUTHORITY_FAILOVER"
    DETECTED_DUPLICATE_ACTIVE_AUTHORITY = "DETECTED_DUPLICATE_ACTIVE_AUTHORITY"
    LOSS_OF_LEADER_OWNERSHIP = "LOSS_OF_LEADER_OWNERSHIP"
    UNCERTAIN_LEADER_TERMINATION = "UNCERTAIN_LEADER_TERMINATION"
    SAFETY_CRITICAL_CREDENTIAL_CHANGE = "SAFETY_CRITICAL_CREDENTIAL_CHANGE"
    PARTITION_RECOVERY_UNKNOWN_REACHABILITY = "PARTITION_RECOVERY_UNKNOWN_REACHABILITY"
    SECURITY_INCIDENT_AFFECTING_AUTHORITY_INTEGRITY = (
        "SECURITY_INCIDENT_AFFECTING_AUTHORITY_INTEGRITY"
    )
    EXPLICIT_ADMINISTRATIVE_REVOCATION = "EXPLICIT_ADMINISTRATIVE_REVOCATION"
