"""Safety Authority pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-003 (Safety Authority Validity, Epoch Fencing, and Partition
Behavior) part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design
contract ``docs/plans/2026-07-23-tos-safety-authority-design.md`` (v1.1).

This package is **pure, non-transmitting, authority-free, and clock-free** (design
§0.2/§4.1): frozen pydantic models over injected state + conservative fail-closed
predicates. It implements **no** leader election / consensus / epoch registry / fencing
enforcement / egress — those are runtime (EV-L2/L3; §0.2). It imports only ``pydantic``
+ stdlib + ``tos.canonical`` (digest substrate + the promoted ``IndependentIdArtifact``
+ ``classify_record_pair``) + ``tos.ordering`` (issue / HALT-vs-permissive order) +
``tos.time`` (lease monotonic validity — the ratified first sibling→sibling edge,
design §0.4b/§3.4) — no ``numpy`` / ``pandas`` / ``yaml``, no ``shared.*``, and — because
RCL is the capacity-side sibling — neither ``tos.rcl`` nor ``tos.capsule`` /
``tos.evidence`` (design §0.3/§3.3 layering; RCL capacity + time snapshots are referenced
only as scalars). Actively verified by the §7.1 import-closure test in
``tos/tests/authority``.

Identity is **independent, not** ``f(digest)`` (design §3.1): so a same-capability-id /
different-bytes forgery / replay conflict (§18.3; §9.3) stays representable and detectable.

**Completion discipline (design §1):** every ``SA-EV-001..015`` has a register minimum
of EV-L2+, so Phase 1 closes **no** SA-EV item — these are EV-L1 *predicate substrate
only*. Tag for any claim: "EV-L1 predicate substrate only; SA-EV-### remains
NOT_IMPLEMENTED pending EV-L2/L3 (008 +Broker, 013 +Security) fault injection."

Public surface groups by module:

* :mod:`tos.authority.vocabulary` — capability types, authority-state precedence,
  transition reasons.
* :mod:`tos.authority.records` — the 3 ledger citizens (capability / epoch-transition /
  lease-ownership).
* :mod:`tos.authority.state` — injected predicate-input / verdict-output models.
* :mod:`tos.authority.predicates` — epoch / validity / dominance / lease / partition /
  re-arm predicates.
"""

from __future__ import annotations

from tos.authority._base import (
    AllFalseAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    AuthorityEffect,
    IndependentIdArtifact,
)
from tos.authority.predicates import (
    authority_epoch_current,
    authority_epoch_fenced,
    currentness_admissible,
    degraded_lease_invalidated,
    degraded_lease_valid,
    halt_denies,
    is_restrictive_dominating_type,
    lease_scope_exclusive,
    overlapping_reassignment_forbidden,
    partition_authority_verdict,
    permissive_capability_valid,
    permissive_transition_allowed,
    rearm_gate,
    recovery_generation_revives_nothing,
    restrictive_dominates,
    restrictive_may_apply_when_stale,
    safer_transition_allowed,
)
from tos.authority.records import (
    AuthorityEpochTransitionRecord,
    DegradedLeaseOwnershipRecord,
    SafetyAuthorityCapability,
)
from tos.authority.state import (
    AuthorityEpochState,
    CapabilityValidityInputs,
    CurrentnessWitness,
    GenerationVector,
    LeaseReassignmentInputs,
    PartitionAuthorityVerdict,
    RearmChecklist,
    RearmVerdict,
)
from tos.authority.vocabulary import (
    PRECEDENCE_RANK,
    RESTRICTIVE_DOMINATING_TYPES,
    AuthorityState,
    AuthorityTransitionReason,
    CapabilityType,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # base
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "AuthorityEffect",
    "IndependentIdArtifact",
    # ordering (reused core — issue / HALT-vs-permissive sequence audit)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "AuthorityState",
    "AuthorityTransitionReason",
    "CapabilityType",
    "PRECEDENCE_RANK",
    "RESTRICTIVE_DOMINATING_TYPES",
    # records
    "AuthorityEpochTransitionRecord",
    "DegradedLeaseOwnershipRecord",
    "SafetyAuthorityCapability",
    # state
    "AuthorityEpochState",
    "CapabilityValidityInputs",
    "CurrentnessWitness",
    "GenerationVector",
    "LeaseReassignmentInputs",
    "PartitionAuthorityVerdict",
    "RearmChecklist",
    "RearmVerdict",
    # predicates
    "authority_epoch_current",
    "authority_epoch_fenced",
    "currentness_admissible",
    "degraded_lease_invalidated",
    "degraded_lease_valid",
    "halt_denies",
    "is_restrictive_dominating_type",
    "lease_scope_exclusive",
    "overlapping_reassignment_forbidden",
    "partition_authority_verdict",
    "permissive_capability_valid",
    "permissive_transition_allowed",
    "rearm_gate",
    "recovery_generation_revives_nothing",
    "restrictive_dominates",
    "restrictive_may_apply_when_stale",
    "safer_transition_allowed",
]
