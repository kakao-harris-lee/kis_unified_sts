"""Orthogonal Trading State pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-005 (Intent, Transmission Attempt, Broker Order, and Knowledge
State Model) part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design
contract ``docs/plans/2026-07-25-tos-orthogonal-state-design.md`` (v1.1). It authors the
**five orthogonal state dimensions** as a frozen, non-transmitting product + conservative
fail-closed coupling / direction / ownership / restart predicates.

This package is **pure, non-transmitting, and clock-free** (design #8 §0.2/§4.6): frozen
pydantic models over injected state + conservative fail-closed predicates. It implements
**no** persistence / durable restart / egress / runtime coupling enforcement — those are
EV-L2/L3 (§0.2). It imports only ``pydantic`` + stdlib + ``tos.canonical`` (digest
substrate + the already-core ``IndependentIdArtifact`` + ``classify_record_pair``) +
``tos.ordering`` (append-only observation / transition order) + ``tos.rcl`` (the Capacity
dimension — ``CapacityState`` + ``capacity_at_least_as_conservative`` +
``transition_allowed``, the **third** ratified sibling→sibling edge, design #8 §0.4b/§3.4)
— no ``numpy`` / ``pandas`` / ``yaml``, no ``shared.*``, and — because Knowledge is a
decision-side axis upstream of the evidence *ledger* (a downstream projection) — neither
``tos.evidence`` nor ``tos.capsule`` / ``tos.time`` / ``tos.authority`` / ``tos.liveauth``
/ ``tos.dsl`` (design #8 §0.3/§3.5 layering; evidence / capsule / authority-epoch /
freshness are referenced only as scalars or injected flags). Actively verified by the
§7.1 import-closure test in ``tos/tests/orthostate``. The dependency ``orthostate → rcl →
{canonical, ordering}`` is acyclic (rcl never references orthostate). **PROMOTE 0건** —
``IndependentIdArtifact`` and ``classify_record_pair`` are already core (designs #5/#6);
the one ratified rcl touch is the additive ``capacity_at_least_as_conservative`` comparator
(design #8 §3.4b/§9.1).

Identity is **independent, not** ``f(digest)`` (design #8 §3.1): so a same-composite-id /
different-bytes forgery / replay conflict stays representable and detectable
(``classify_record_pair`` => ``CRITICAL_CONFLICT``), and each observation is a fresh id
(append-only, §2.3).

**Completion discipline (design #8 §1):** ``STATE-EV-001`` / ``STATE-EV-003`` have an
EV-L1 slice authored here but their ``/2`` (durable persistence) / ``/3`` (runtime
coupling enforcement) tails remain; ``STATE-EV-002`` / ``004`` / ``005`` are predicate
substrate only (register minimum EV-L2+). Phase 1 closes **no** STATE-EV item — authoring
is not evidence (VER-002-001 §5). Tag for any claim: "EV-L1 slice / predicate substrate
only; STATE-EV-### remains NOT_IMPLEMENTED pending EV-L2/L3 fault injection, durable
persistence, runtime coupling enforcement, and real restart."

Public surface groups by module:

* :mod:`tos.orthostate.vocabulary` — the four local dimension enums + StateDimension /
  TransitionAuthority / ConservatismBasis (Capacity is REUSED from ``tos.rcl``).
* :mod:`tos.orthostate.records` — the two ledger citizens (composite observation +
  dimension transition record).
* :mod:`tos.orthostate.state` — injected coupling side-conditions.
* :mod:`tos.orthostate.predicates` — coupling / conservative-direction / transition-
  legality / ownership / restart predicates.
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.orthostate._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.orthostate.predicates import (
    attempt_transition_allowed,
    conservative_direction_ok,
    coupling_violations,
    intent_transition_allowed,
    knowledge_transition_allowed,
    may_transition,
    no_coupling_violation,
    reconstruct_conservative,
)
from tos.orthostate.records import CompositeState, DimensionTransitionRecord
from tos.orthostate.state import CouplingSideConditions
from tos.orthostate.vocabulary import (
    WEAK_BASES,
    BrokerOrderState,
    ConservatismBasis,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)

__all__ = [
    # base
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — observation / transition order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "BrokerOrderState",
    "ConservatismBasis",
    "IntentState",
    "KnowledgeState",
    "StateDimension",
    "TransitionAuthority",
    "TransmissionAttemptState",
    "WEAK_BASES",
    # records
    "CompositeState",
    "DimensionTransitionRecord",
    # state
    "CouplingSideConditions",
    # predicates
    "attempt_transition_allowed",
    "conservative_direction_ok",
    "coupling_violations",
    "intent_transition_allowed",
    "knowledge_transition_allowed",
    "may_transition",
    "no_coupling_violation",
    "reconstruct_conservative",
]
