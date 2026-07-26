"""Action Flow Governance pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-022 (Action-Flow Budgeting, Retry-Storm Containment, and
Protective-Traffic Preservation — "AFG") part of IMPLEMENTATION-PLAN-002 §4 Phase 1
(EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-action-flow-budgeting-design.md`` (v1.1, operator-ratified
2026-07-26). It authors the **action-flow decision rules** — complete-scope /
no-local-headroom, bounded amplification + complete cause lineage, exact binding +
single-use permit + atomic economic-and-flow coverage, no-manufactured-refill + generation
fencing, no-blind-retry, cancel-ACK-is-not-a-Final-Quantity-Proof + bounded oscillation,
conservative action classification, protective-reserve exclusivity, currentness /
invalidation, partition lease exclusivity, all-false authority separation, and non-revival
+ economic continuity — over a five-artifact digest-bound data model.

It is a **decision kernel, not a rate limiter and not a ledger** (design #16 §0.2): the
capacity arithmetic, serialization, and the atomic economic + action-flow commit are
rcl-owned (ADR §1 line 19; AFG-INV-004); the protective reserve classification / lease
admissibility / retry budget are protective-owned; broker capability is brokercap-owned;
the transmission-attempt and broker-order state machines are orthostate-owned;
trustworthy time is time-owned; the exact broker-command bytes are ADR-002-020 (IOC)
-owned; and the final egress is ADR-002-013 runtime. afg consumes every one of those as an
**injected produced scalar / bool / token** and re-authors none of them.

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #16
§0.2/§4.6): frozen pydantic models over injected state plus conservative fail-closed
predicates. It **cannot** transmit, mutate capacity, issue a capability, consume or claim a
permit, set a live scope, or re-arm — it produces decision **bools** / scalars / a
forward-only decision artifact and a permit record; the owning runtime (a future Action
Flow Governor / Snapshot Assembly / RCL-admission / Final Egress service) enforces them.
There is no "assume-zero" / "assume-within" / "assume-grant" path: ``GRANT`` / ``True``
comes only from positive proof, everything else is ``UNKNOWN`` / ``DENY`` / ``False``
(design #16 §4.1 — the structural seal against the #6 fail-open lesson).

**Truthy-sentinel discipline (design #16 §2.2-1).** ``ActionFlowResult`` is a ``StrEnum``,
so ``DENY`` and ``UNKNOWN`` are *truthy*: every consuming gate SHALL test
``result is ActionFlowResult.GRANT`` (identity), never ``if result:``. The same holds for
the injected protective ``Admissibility`` verdict (only the ``ADMISSIBLE`` token passes —
``TRAPPED`` / ``PROHIBITED`` / ``None`` deny) and for ``bool | None`` flags
(``is True`` / ``is not True`` normalization).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``CanonicalDecimal`` + ``CanonicalizationScheme``) +
``tos.ordering`` (append-only generation / decision / permit / snapshot order) + the rcl
:class:`~tos.rcl.CapacityVector` **type** and its ``aggregate_usage`` / ``effective_limit``
arithmetic for the action-flow vector and headroom check (the single ``afg -> rcl``
sibling edge, design #16 §0.4c; rcl does not import afg, so the edge is acyclic — the #8
orthostate -> rcl / #13 are -> rcl precedent). It imports **no** other sibling —
``tos.protective`` / ``tos.spg`` / ``tos.orthostate`` / ``tos.brokercap`` / ``tos.time`` /
``tos.recon`` / ``tos.are`` / ``tos.ioc`` / ``tos.iap`` / ``tos.liveauth`` /
``tos.authority`` / ``tos.capsule`` / ``tos.evidence`` / ``tos.dsl`` and any future sibling
are all excluded by the §7.1 **allowlist** closure test (``tos.*`` closure ⊆
{``tos.canonical``, ``tos.ordering``, ``tos.rcl``, ``tos.afg``}), which stays robust as new
siblings are added. **PROMOTE 0** — ``CanonicalDecimal`` is already core.

Identity is **independent, not** ``f(digest)`` (design #16 §3.1/§0.4e): each policy /
snapshot / decision / permit generation is an immutable record; a legitimate revalidation
or supersession is a new independent id, and a same-id / different-bytes re-issuance,
forgery, contradictory decision, or double-spent permit is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #16 §1).** ``AFG-EV-001..012`` are all predicate /
coordinate substrate. Five rows (001 / 002 / 004 / 007 / 008) carry an ``EV-L1`` slice in
EVIDENCE-REGISTER-002 — the orchestrator's advance count of "six" was corrected to **five**
by measurement — and even those five carry ``/3`` / ``+Security`` / ``+Broker`` residue;
the other seven (003 / 005 / 006 / 009 / 010 / 011 / 012) are minimum ``EV-L2``. Phase 1
authors the L1-decidable substrate and closes **no** AFG-EV item (authoring is not
evidence, VER-002-001 §5; ADR §27 line 631 "Writing or registering the case does not
satisfy it"). Tag for any claim: "predicate / coordinate substrate only; AFG-EV-001..012
remain NOT_IMPLEMENTED pending EV-L2/L3 fault injection, adversarial, +Security, and
+Broker evidence; **EV-L1-complete claim forbidden**; no ADR acceptance, restricted-live,
or production is authorized."

Public surface groups by module:

* :mod:`tos.afg.vocabulary` — the action-flow-axis StrEnums, the Gap-1 dimension-id
  convention, and the injected sibling coordinate tokens.
* :mod:`tos.afg.records` — the four digest-bound artifacts + the value / injected-input
  models + the all-false governor effect + the ``ActionFlowVector`` REUSE alias.
* :mod:`tos.afg.predicates` — the core §5.1/§5.2/§5.3 + predicate-only
  §6.1/§6.2/§6.3/§6.4/§6.6/§6.7 decision rules + the produced rcl seam.
* :mod:`tos.afg.state` — the temporal §5.3-lifecycle / §5.4 / §6.5 / §6.8 predicates
  (permit single-use, refill integrity, generation fence, currentness, non-revival) +
  the ``tos.ordering`` REUSE.
"""

from __future__ import annotations

from tos.afg._base import (
    AllFalseActionFlowAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.afg.predicates import (
    action_class_conservative,
    action_flow_decision,
    action_flow_vector_of,
    amplification_bounded,
    applicable_action_flow_scopes_of,
    atomic_economic_flow_coverage,
    cancel_ack_not_final_quantity_proof,
    cause_lineage_complete,
    changed_command_is_new_action,
    decision_content_ref,
    envelope_not_enlarged,
    governor_grants_no_authority,
    headroom_within_limits,
    no_blind_retry,
    oscillation_bounded,
    partition_lease_exclusive,
    priority_is_not_reserve,
    reserve_exclusive,
    scope_graph_complete,
    shared_limit_conservative,
)
from tos.afg.records import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionFlowDecision,
    ActionFlowGovernorEffect,
    ActionFlowPermit,
    ActionFlowPolicy,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    CurrentnessTrigger,
    ObservedAmplification,
    PermitConsumptionState,
    ProtectiveFlowReserveClaim,
    ScopeIndependenceEvidence,
)
from tos.afg.state import (
    action_flow_generation_monotone,
    backlog_is_not_authority,
    currentness_invalidation,
    decision_is_forward_only,
    economic_effect_persists,
    generation_fenced,
    is_material,
    non_revival_holds,
    permit_not_merged,
    permit_release_admissible,
    permit_single_use,
    queue_does_not_extend_validity,
    refill_conservative,
    restart_counter_assumption_admissible,
)
from tos.afg.vocabulary import (
    ACTION_CLASS_CONSERVATISM_ORDER,
    ACTION_FLOW_DIMENSION_IDS,
    ACTION_FLOW_SCOPE_BREADTH_ORDER,
    ADMISSIBILITY_ADMISSIBLE,
    ATTEMPT_STATE_SEND_FAILED_PROVEN,
    ATTEMPT_STATE_SENT_UNCONFIRMED,
    BROKER_ORDER_STATE_CANCELLED,
    BROKER_ORDER_STATE_UNKNOWN,
    MATERIAL_CHANGE_KINDS,
    RESERVED_GUARANTEE_TOKENS,
    ActionClassKind,
    ActionFlowDimensionKind,
    ActionFlowResult,
    ActionFlowScopeKind,
    DocumentedScopeStatus,
    MaterialChangeKind,
    action_flow_dimension_id,
    broadest_scope,
    is_action_flow_dimension_id,
    most_conservative_action_class,
    narrowest_scope,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # base (reused core + afg-local all-false governor authority)
    "AllFalseActionFlowAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — append-only generation / decision / permit order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "ActionClassKind",
    "ActionFlowDimensionKind",
    "ActionFlowResult",
    "ActionFlowScopeKind",
    "DocumentedScopeStatus",
    "MaterialChangeKind",
    "ACTION_CLASS_CONSERVATISM_ORDER",
    "ACTION_FLOW_DIMENSION_IDS",
    "ACTION_FLOW_SCOPE_BREADTH_ORDER",
    "ADMISSIBILITY_ADMISSIBLE",
    "ATTEMPT_STATE_SEND_FAILED_PROVEN",
    "ATTEMPT_STATE_SENT_UNCONFIRMED",
    "BROKER_ORDER_STATE_CANCELLED",
    "BROKER_ORDER_STATE_UNKNOWN",
    "MATERIAL_CHANGE_KINDS",
    "RESERVED_GUARANTEE_TOKENS",
    "action_flow_dimension_id",
    "broadest_scope",
    "is_action_flow_dimension_id",
    "most_conservative_action_class",
    "narrowest_scope",
    # records
    "ActionAmplificationEnvelope",
    "ActionCause",
    "ActionFlowDecision",
    "ActionFlowGovernorEffect",
    "ActionFlowPermit",
    "ActionFlowPolicy",
    "ActionFlowStateSnapshot",
    "ActionFlowVector",
    "CurrentnessTrigger",
    "ObservedAmplification",
    "PermitConsumptionState",
    "ProtectiveFlowReserveClaim",
    "ScopeIndependenceEvidence",
    # core §5 predicates
    "amplification_bounded",
    "atomic_economic_flow_coverage",
    "action_flow_decision",
    "cause_lineage_complete",
    "changed_command_is_new_action",
    "envelope_not_enlarged",
    "generation_fenced",
    "headroom_within_limits",
    "permit_single_use",
    "permit_release_admissible",
    "refill_conservative",
    "scope_graph_complete",
    "shared_limit_conservative",
    # §12 queue / merge / backlog (M8)
    "backlog_is_not_authority",
    "permit_not_merged",
    "queue_does_not_extend_validity",
    # predicate-only §6 predicates
    "action_class_conservative",
    "cancel_ack_not_final_quantity_proof",
    "currentness_invalidation",
    "economic_effect_persists",
    "governor_grants_no_authority",
    "is_material",
    "no_blind_retry",
    "non_revival_holds",
    "oscillation_bounded",
    "partition_lease_exclusive",
    "priority_is_not_reserve",
    "reserve_exclusive",
    "restart_counter_assumption_admissible",
    # ordering / structural contracts
    "action_flow_generation_monotone",
    "decision_is_forward_only",
    # produced rcl seam (§3.4)
    "action_flow_vector_of",
    "applicable_action_flow_scopes_of",
    "decision_content_ref",
]
