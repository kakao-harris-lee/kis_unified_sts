"""Risk Capacity Ledger pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-002 (Aggregate Risk-Capacity Commitment) + ADR-002-012 (RCL
Persistence, Consensus, Writer Fencing) part of IMPLEMENTATION-PLAN-002 §4 Phase 1
(EV-L1), per the ratified design contract
``docs/plans/2026-07-21-tos-risk-capacity-ledger-design.md`` (v1.1).

This package is **pure, non-transmitting, and authority-free** (design §0.2/§4.1):
frozen pydantic models over injected state, and conservative fail-closed predicates.
It implements **no** consensus / quorum / replication / persistence I/O / egress —
those are runtime (EV-L2/L3). It imports only ``pydantic`` + stdlib (incl.
``decimal``) + ``tos.canonical`` (digest substrate + the promoted
``classify_record_pair``) + ``tos.ordering`` (committed order / Log Revision) — no
``numpy`` / ``pandas`` / ``yaml``, no ``shared.*``, and — because RCL is the
**upstream** Safety Commit Log while ``tos.evidence`` is a downstream projection —
neither ``tos.evidence`` nor its sibling ``tos.capsule`` (design §0.3/§3.1 layering),
actively verified by the §7.1 import-closure test in ``tos/tests/rcl``.

Identity is **independent, not** ``f(digest)`` (design §3.1): so a same-command-id /
different-canonical-bytes conflict (ADR-012 §9 line 270; RCLP-INV-006) stays
representable and detectable.

Nothing here accepts any RCLP-EV or RC-EV (design §1): it is the EV-L1 slice /
predicate substrate only — RCLP-EV-001/005/006 are partial (``/3`` quorum / fault
injection / egress tails remain), and all RC-EV plus the other RCLP-EV are
NOT_IMPLEMENTED (EV-L2/L3 fault injection).
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.rcl._base import (
    AllFalseAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.rcl.authority import GrantDecisionRef, RclAuthorityEffect
from tos.rcl.predicates import (
    apply_benefit,
    apply_committed,
    available_headroom,
    capability_authorization_valid,
    capacity_at_least_as_conservative,
    claim_capability,
    committed_usage,
    credible_union_capacity,
    fold_commands,
    grant_authorizes_exact_request,
    grants_no_authority,
    partition_verdict,
    recovery_generation_revives_nothing,
    snapshot_admissible_for_restore,
    transition_allowed,
    within_limits,
    writer_fenced,
)
from tos.rcl.records import (
    AuthoritativeSnapshot,
    LedgerCommandRecord,
    ProtectiveLease,
    ProtectivePool,
    RclTransitionRecord,
    ReservationRecord,
    SnapshotCompleteness,
    TransmissionCapability,
)
from tos.rcl.state import (
    AppliedCommand,
    ApplyOutcome,
    ClaimOutcome,
    ClaimRecord,
    CommittedReservation,
    CredibleHistory,
    FenceCoordinates,
    LedgerState,
    PartitionVerdict,
    WriterFenceState,
)
from tos.rcl.vector import (
    BenefitClaim,
    BenefitProof,
    CapacityComponent,
    CapacityVector,
    DimensionDescriptor,
    aggregate_usage,
    effective_limit,
)
from tos.rcl.vocabulary import (
    WEAK_CAUSES,
    ApplyReason,
    CapacityState,
    CommandType,
    TransitionCause,
)

__all__ = [
    # base
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "CapacityState",
    "CommandType",
    "TransitionCause",
    "ApplyReason",
    "WEAK_CAUSES",
    # vector
    "BenefitClaim",
    "BenefitProof",
    "CapacityComponent",
    "CapacityVector",
    "DimensionDescriptor",
    "aggregate_usage",
    "effective_limit",
    # authority
    "GrantDecisionRef",
    "RclAuthorityEffect",
    # records
    "AuthoritativeSnapshot",
    "LedgerCommandRecord",
    "ProtectiveLease",
    "ProtectivePool",
    "RclTransitionRecord",
    "ReservationRecord",
    "SnapshotCompleteness",
    "TransmissionCapability",
    # state
    "AppliedCommand",
    "ApplyOutcome",
    "ClaimOutcome",
    "ClaimRecord",
    "CommittedReservation",
    "CredibleHistory",
    "FenceCoordinates",
    "LedgerState",
    "PartitionVerdict",
    "WriterFenceState",
    # predicates
    "apply_benefit",
    "apply_committed",
    "available_headroom",
    "capability_authorization_valid",
    "capacity_at_least_as_conservative",
    "claim_capability",
    "committed_usage",
    "credible_union_capacity",
    "fold_commands",
    "grant_authorizes_exact_request",
    "grants_no_authority",
    "partition_verdict",
    "recovery_generation_revives_nothing",
    "snapshot_admissible_for_restore",
    "transition_allowed",
    "within_limits",
    "writer_fenced",
]
