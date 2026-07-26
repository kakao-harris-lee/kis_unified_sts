"""Safe-Startup / Recovery-Barrier / Conservative-Resume pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-017 (Safe Startup, Recovery Barrier, and Conservative Resume
Coordination — "SBR") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified
design contract ``docs/plans/2026-07-26-tos-startup-recovery-design.md`` (v1.1,
operator-delegated auto-ratified 2026-07-26). It authors the **recovery-orchestration
decision rules** — complete inventory + obligation-graph closure, scope-expansion closure,
UNKNOWN conservatism + no-timeout-fallback, proven restricted isolation, continuous
readiness invalidation, non-revival, closed startup, egress / owner generation fencing,
non-atomic broker conservatism, HALT dominance, worst-credible-union restore, and all-false
authority separation — over an eight-model data substrate (design #17 §2).

SBR is a **recovery orchestrator, not a per-dimension judge** (design #17 §0.4b/§3.5): state
reconstruction is orthostate-owned, per-field confidence is recon-owned, capacity mutation is
rcl-owned, protective classification is protective-owned, HALT downgrade is protective-owned,
and the re-arm checklist / Live Authorization are authority / liveauth-owned. SBR **folds**
every one of those as an **injected produced scalar / bool / enum-token / verdict** and
re-authors none of them. It owns only the session state machine, inventory-cut completeness,
obligation-graph closure, readiness decision, scope / invalidation reachability closure, and
the ``recovery_generation`` fence *meaning* (authority carries the scalar, §0.4e).

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #17
§0.2/§4.6): frozen pydantic models over injected state plus conservative fail-closed
predicates. It **cannot** transmit, mutate capacity, issue a capability, re-arm, or clear a
HALT — it produces decision **bools** / verdicts / scalars and forward record artifacts; the
owning runtime (a future Recovery Coordinator / Safety Control Plane / authority re-arm /
final-egress service) enforces them. There is no "assume-complete" / "assume-isolated" /
"timeout-fallback" / "promote-UNKNOWN" / "revive" path: a positive result comes only from
positive proof, everything else is ``NOT_READY`` / ``False`` / non-satisfied (design #17
§4.1 — the structural seal against the #6 fail-open lesson).

**Truthy-sentinel discipline (design #17 §2.2(1)/§4.7 — #14 M1 adopted from the start).**
``ReadinessVerdict`` / ``SessionState`` / ``RecoveryBarrierState`` / ``ObligationResult`` are
**truthy-untestable** ``StrEnum``s (``__bool__`` raises ``TypeError``), so a consumer's
``if verdict:`` misuse raises rather than reading ``NOT_READY`` / a ``CLOSED_*`` barrier as
truthy permission — especially critical for the barrier (§9 line 257 "No barrier state alone
permits"). The mandated gates are ``verdict is ReadinessVerdict.READY`` /
``result is ObligationResult.SATISFIED``, and ``bool | None`` flags use ``is True`` /
``is not True``.

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``DigestBoundArtifact`` + the provisional canonicalizer +
``classify_record_pair``) + ``tos.ordering`` (append-only recovery-generation order). It
imports **no** sibling — ``tos.afg`` / ``tos.are`` / ``tos.authority`` / ``tos.brokercap`` /
``tos.capsule`` / ``tos.dsl`` / ``tos.evidence`` / ``tos.iap`` / ``tos.ioc`` / ``tos.liveauth``
/ ``tos.orthostate`` / ``tos.protective`` / ``tos.rcl`` / ``tos.recon`` / ``tos.spg`` /
``tos.time`` and any future sibling are all excluded by the §7.1 **allowlist** closure test
(``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``, ``tos.sbr``}) — **sibling edge 0**
(design #17 §0.3/§0.4c). The iap ``invalidation_closure`` isomorphism is **re-authored
locally** (:func:`~tos.sbr.predicates._reachability_closure`), never imported (PROMOTE and
import both rejected — design #17 §0.4d; DRY preserved at the property-test-contract level).
**PROMOTE 0** — the digest / ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for session / package / decision (design #17
§3.1/§0.4e): each is an immutable issued record; a same-id / different-bytes forgery,
re-issue, contradiction (readiness substitution §22), or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``. Trigger / inventory-cut / obligation are
content-addressed digest-bound records.

**Completion discipline (design #17 §1).** ``SBR-EV-001..012`` are all predicate / model
substrate. Five rows (004 / 006 / 007 / 009 / 012) carry an ``EV-L1`` slice in
EVIDENCE-REGISTER-002; the other seven (001 / 002 / 003 / 005 / 008 / 010 / 011) are minimum
``EV-L2`` (+Security ×5, +Broker ×1). Phase 1 authors the L1-decidable substrate and closes
**no** SBR-EV item — even the five carry ``/3`` residue (authoring is not evidence,
VER-002-001 §5; ADR §25 line 634 "Written cases are not completed evidence"). Tag for any
claim: "predicate / model substrate only; SBR-EV-001..012 remain NOT_IMPLEMENTED pending
EV-L2/L3 fault injection, adversarial, +Security, and +Broker evidence; **EV-L1-complete
claim forbidden**; no ADR acceptance, restricted-live, or production is authorized."

Public surface groups by module:

* :mod:`tos.sbr.vocabulary` — the recovery-axis StrEnums (truthy-untestable decision enums +
  input taxonomy tokens).
* :mod:`tos.sbr.records` — the eight models (trigger / inventory-cut / obligation + graph /
  session / package / decision) + injected inputs + the all-false authority effect.
* :mod:`tos.sbr.predicates` — the core §5.1-§5.7 + predicate-only §6.1-§6.7 decision rules +
  the shared reachability closure kernel.
* :mod:`tos.sbr.state` — the §10 session state machine + the produced seam scalars +
  the ``tos.ordering`` REUSE.
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.sbr._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    RecoveryAuthorityEffect,
)
from tos.sbr.predicates import (
    competing_owner_fenced,
    halt_dominates_recovery,
    non_atomic_broker_conservative,
    obligation_graph_closed,
    readiness_invalidated_by_change,
    recovery_authority_separated,
    recovery_completion_revives_nothing,
    recovery_inventory_complete,
    recovery_scope_closure,
    restore_worst_credible_union,
    restricted_isolation_proven,
    stale_generation_rejected_at_egress,
    start_closed,
    timeout_is_restrictive,
    unknown_stays_conservative,
)
from tos.sbr.records import (
    BrokerReadSequence,
    IsolationFacts,
    RecoveryBarrierPolicy,
    RecoveryEvidencePackage,
    RecoveryInventoryCut,
    RecoveryObligation,
    RecoveryObligationGraph,
    RecoveryReadinessDecision,
    RecoveryScope,
    RecoverySession,
    RecoveryTrigger,
)
from tos.sbr.state import (
    is_terminal_state,
    recovery_coordinator_evidence_complete,
    recovery_current,
    recovery_generation_monotone,
    recovery_generation_of,
    recovery_readiness_enlarged,
    session_transition_allowed,
)
from tos.sbr.vocabulary import (
    ObligationResult,
    OwnerStatus,
    ReadinessVerdict,
    RecoveryBarrierState,
    RecoveryMode,
    SelectionBasis,
    SessionState,
)

__all__ = [
    # base (reused core + sbr-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "RecoveryAuthorityEffect",
    # ordering (reused core — append-only recovery generation order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "RecoveryBarrierState",
    "SessionState",
    "ReadinessVerdict",
    "ObligationResult",
    "RecoveryMode",
    "SelectionBasis",
    "OwnerStatus",
    # records — the eight models + injected inputs
    "RecoveryTrigger",
    "RecoveryInventoryCut",
    "RecoveryObligation",
    "RecoveryObligationGraph",
    "RecoverySession",
    "RecoveryEvidencePackage",
    "RecoveryReadinessDecision",
    "RecoveryBarrierPolicy",
    "RecoveryScope",
    "IsolationFacts",
    "BrokerReadSequence",
    # core §5 predicates
    "recovery_inventory_complete",
    "obligation_graph_closed",
    "recovery_scope_closure",
    "unknown_stays_conservative",
    "timeout_is_restrictive",
    "restricted_isolation_proven",
    "readiness_invalidated_by_change",
    "recovery_completion_revives_nothing",
    # predicate-only §6 predicates
    "start_closed",
    "stale_generation_rejected_at_egress",
    "competing_owner_fenced",
    "non_atomic_broker_conservative",
    "halt_dominates_recovery",
    "restore_worst_credible_union",
    "recovery_authority_separated",
    # state machine + produced seam scalars
    "session_transition_allowed",
    "is_terminal_state",
    "recovery_generation_monotone",
    "recovery_coordinator_evidence_complete",
    "recovery_current",
    "recovery_readiness_enlarged",
    "recovery_generation_of",
]
