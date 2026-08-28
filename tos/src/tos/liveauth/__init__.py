"""Live Authorization pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-007 (Live Authorization, Limit Governance, and Re-arm) part of
IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-24-tos-live-authorization-design.md`` (v1.1). The third and last
§2 core of track A (Time → Authority → **Live Authorization**).

This package is **pure, non-transmitting, authorization-granting-nothing, and clock-free**
(design §0.2/§4.1): frozen pydantic models over injected state + conservative fail-closed
predicates. It implements **no** egress / fenced single-use capability / human dual-control
authentication / safety-configuration activation / consensus — those are runtime
(EV-L2/L3 + Security; §0.2). It imports only ``pydantic`` + stdlib + ``tos.canonical``
(digest substrate + the already-core ``IndependentIdArtifact`` + ``classify_record_pair``)
+ ``tos.ordering`` (issue-sequence / lifecycle audit) + ``tos.time`` (TRUSTED / freshness)
+ ``tos.authority`` (epoch / precedence / dominance / re-arm / capability — the **second**
ratified sibling→sibling edge, design §0.4b/§3.5) — no ``numpy`` / ``pandas`` / ``yaml``,
no ``shared.*``, and — because RCL is the capacity-side sibling — neither ``tos.rcl`` nor
``tos.capsule`` / ``tos.evidence`` / ``tos.dsl`` (design §0.3/§3.3 layering; RCL capacity,
safety-config, recovery, and capsules are referenced only as scalars). Actively verified
by the §7.1 import-closure test in ``tos/tests/liveauth``. The dependency diamond
``liveauth → {authority, time}`` + ``authority → time`` is acyclic (time / authority never
reference liveauth). **PROMOTE 0건** — ``IndependentIdArtifact`` is already core (design #6).

Identity is **independent, not** ``f(digest)`` (design §3.1): so a same-authorization-id /
different-bytes forgery / replay conflict (§8.3) stays representable and detectable.

**Completion discipline (design §1):** every ``REARM-EV-001..012`` has a register minimum
of EV-L2+, so Phase 1 closes **no** REARM-EV item — these are EV-L1 *predicate substrate
only*. Tag for any claim: "EV-L1 predicate substrate only; REARM-EV-### remains
NOT_IMPLEMENTED pending EV-L2/L3 (001/004/005/010 +Security) fault injection."

Public surface groups by module:

* :mod:`tos.liveauth.vocabulary` — lifecycle states + dual-control path kinds.
* :mod:`tos.liveauth.records` — the 3 ledger citizens (authorization / transition /
  re-arm-approval).
* :mod:`tos.liveauth.state` — injected predicate-input / verdict-output models.
* :mod:`tos.liveauth.predicates` — validity / scope / lifecycle / layering / dual-control
  / re-arm / expansion / HALT predicates.
"""

from __future__ import annotations

from tos.liveauth._base import (
    AllFalseAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
    LiveAuthorizationEffect,
)
from tos.liveauth.predicates import (
    atomic_activation_ok,
    authorization_revived_by_nothing,
    continuous_validity,
    fresh_authorization_identity,
    halt_dominates_authorization,
    in_place_expansion_admissible,
    is_live,
    layering_within_bounds,
    live_authorization_transition_allowed,
    no_automatic_rearm,
    partial_rearm_scope_narrows,
    rearm_admissible,
    rearm_dual_control_satisfied,
    scope_covers,
)
from tos.liveauth.records import (
    LiveAuthorization,
    LiveAuthorizationTransitionRecord,
    ReArmApprovalRecord,
)
from tos.liveauth.state import (
    ContinuousValidityInputs,
    DualControlAttestation,
    InPlaceExpansionInputs,
    LimitLayering,
    LiveAuthorizationScope,
    ReArmOutcome,
    Safe053VariantAttestation,
)
from tos.liveauth.vocabulary import LiveAuthorizationState, ReArmPathKind
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # base
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    "LiveAuthorizationEffect",
    # ordering (reused core — issue-sequence / lifecycle audit)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "LiveAuthorizationState",
    "ReArmPathKind",
    # records
    "LiveAuthorization",
    "LiveAuthorizationTransitionRecord",
    "ReArmApprovalRecord",
    # state
    "ContinuousValidityInputs",
    "DualControlAttestation",
    "InPlaceExpansionInputs",
    "LimitLayering",
    "LiveAuthorizationScope",
    "ReArmOutcome",
    "Safe053VariantAttestation",
    # predicates
    "atomic_activation_ok",
    "authorization_revived_by_nothing",
    "continuous_validity",
    "fresh_authorization_identity",
    "halt_dominates_authorization",
    "in_place_expansion_admissible",
    "is_live",
    "layering_within_bounds",
    "live_authorization_transition_allowed",
    "no_automatic_rearm",
    "partial_rearm_scope_narrows",
    "rearm_admissible",
    "rearm_dual_control_satisfied",
    "scope_covers",
]
