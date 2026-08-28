"""Trustworthy Time pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-008 part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per
the ratified design contract
``docs/plans/2026-07-21-tos-trustworthy-time-design.md`` (v1.1).

This package is **pure, non-transmitting, authority-free, and clock-free** (time
design §0.2/§0.3): frozen pydantic models + conservative derived predicates over
**opaque injected time coordinates** — it never reads ``time``/``datetime``/
``monotonic``. It imports only ``pydantic`` + stdlib + ``tos.canonical`` (digest
substrate) + ``tos.ordering`` (promoted causal-order primitive) — no
``numpy``/``pandas``, no ``shared.config`` / ``shared.*``, no ``tos.capsule`` /
``tos.evidence`` (time design §0.3/§5 layering), no network/process/env access —
actively verified by the §7.1 import-closure test in ``tos/tests``.

The Time Health Snapshot identity is **independent, not** ``f(digest)`` (time
design §0.4a): so a wrong/declared-inconsistent generation/provenance stays
representable and detectable (ADR §8 line 208).

**Completion discipline (time design §1):** every TIME-EV-001..010 has a register
minimum of EV-L2+, so Phase 1 closes **no** TIME-EV item — these are EV-L1
*predicate substrate only*.

Public surface groups by module:

* :mod:`tos.time.domains` — time-domain / health-state / freshness / reason enums.
* :mod:`tos.time.elements` — authored snapshot element schemas + authority block.
* :mod:`tos.time.snapshot` — Time Health Snapshot (``DigestBoundArtifact``).
* :mod:`tos.time.ordering` — REUSE mapping onto ``tos.ordering.compare_order``.
* :mod:`tos.time.predicates` — continuity / lifetime / freshness / FSM / session /
  binding / source-independence predicates.
"""

from __future__ import annotations

from tos.time.domains import (
    FreshnessVerdict,
    HealthState,
    ReasonCode,
    TimeDomain,
)
from tos.time.elements import (
    AllFalseAuthority,
    Bounds,
    ConsumerReceiptAnchor,
    DiscontinuityStatus,
    EvaluatedMonotonicAnchor,
    MonotonicReading,
    ReferenceSource,
    SessionContext,
    SuspensionStatus,
    TimeAuthorityEffect,
    TimeContinuityIdentity,
    UncertaintyInterval,
)
from tos.time.ordering import (
    ordering_event_from_monotonic,
    ordering_event_from_reference_interval,
)
from tos.time.predicates import (
    anchor_valid,
    conservative_usable_lifetime,
    effective_snapshot_age_bound,
    effective_snapshot_age_bound_from_continuity,
    elapsed_within_continuity,
    freshness_verdict,
    health_transition_allowed,
    independent_reference_count,
    recovery_generation_revives_nothing,
    session_open_positively,
    snapshot_age_admissible,
    snapshot_consumer_binding_ok,
    snapshot_grants_no_authority,
    source_disagreement_within_bound,
    state_permits_new_normal_risk,
    transition_to_trusted_requires_new_generation,
)
from tos.time.snapshot import TimeHealthSnapshot

__all__ = [
    # domains
    "TimeDomain",
    "HealthState",
    "FreshnessVerdict",
    "ReasonCode",
    # elements
    "AllFalseAuthority",
    "TimeAuthorityEffect",
    "UncertaintyInterval",
    "TimeContinuityIdentity",
    "EvaluatedMonotonicAnchor",
    "MonotonicReading",
    "ReferenceSource",
    "Bounds",
    "SuspensionStatus",
    "DiscontinuityStatus",
    "SessionContext",
    "ConsumerReceiptAnchor",
    # snapshot
    "TimeHealthSnapshot",
    # ordering mapping (REUSE)
    "ordering_event_from_monotonic",
    "ordering_event_from_reference_interval",
    # predicates
    "elapsed_within_continuity",
    "anchor_valid",
    "conservative_usable_lifetime",
    "effective_snapshot_age_bound",
    "effective_snapshot_age_bound_from_continuity",
    "snapshot_age_admissible",
    "freshness_verdict",
    "health_transition_allowed",
    "transition_to_trusted_requires_new_generation",
    "recovery_generation_revives_nothing",
    "state_permits_new_normal_risk",
    "snapshot_grants_no_authority",
    "session_open_positively",
    "snapshot_consumer_binding_ok",
    "independent_reference_count",
    "source_disagreement_within_bound",
]
