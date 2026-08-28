"""Protective-capacity pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-001 (Degraded-Mode Protective Capacity) part of IMPLEMENTATION-PLAN-002
§4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-25-tos-degraded-mode-protective-capacity-design.md`` (v1.1). It authors
the **completeness** of "which resource domain protective capacity spans and what guarantee
level each domain holds" (``domain_enumeration_complete`` / ``guarantee_level_resolved`` —
PRD-EV-001 / PRD-EV-002 substrate), and the protective-action classification / degraded-mode
de-restriction / partition-time lease-admissibility / protective ownership+cancellation /
bounded-retry / time-untrusted / envelope / reserve-sufficiency **decision predicates** by
which a protective deficiency reduces or prohibits an action (ADR §1).

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #11
§0.2/§4.5): frozen pydantic models over injected state + conservative fail-closed predicates.
It **cannot** transmit / retry / mutate capacity / issue authorization / set a mode — it
produces decision **bools** / ``Admissibility`` verdicts; the owning runtime (a future
Protective Action Controller, ADR §5) enforces them. There is no "assume-admissible" path
anywhere: ``ADMISSIBLE`` / ``True`` comes only from positive proof, everything else is
restrictive (design #11 §4.1 — the structural seal against the #6 fail-open REJECT lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + the already-core ``CanonicalDecimal``,
design #11 §0.4c) + ``tos.ordering`` (append-only profile-version order) — no ``numpy`` /
``pandas`` / ``yaml``, no ``shared.*``, and — as the decision-side **producer** of the
protective bools — **none** of its consumers / siblings ``tos.rcl`` / ``tos.authority`` /
``tos.liveauth`` / ``tos.orthostate`` / ``tos.recon`` / ``tos.evidence`` / ``tos.capsule`` /
``tos.time`` / ``tos.dsl`` / ``tos.brokercap`` (design #11 §0.3/§3.4/§3.5 — **sibling edge
0**; capacity arithmetic is rcl's, the mode enum / precedence is authority's, and freshness /
verdicts are injected flags). Actively verified by the §7.1 import-closure test in
``tos/tests/protective``. **PROMOTE 0건** — ``CanonicalDecimal`` / ``IndependentIdArtifact`` are
already core (design #9 / #6 §0.4c).

Identity is **independent, not** ``f(digest)`` (design #11 §3.1): each profile version is an
immutable record; a legitimate revalidation / supersession is a new ``profile_id``, a same-id
/ different-bytes re-issuance is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #11 §1):** ``PRD-EV-001`` (``EV-L1/3+Broker``) / ``PRD-EV-002``
(``EV-L1/3``) each carry an EV-L1 slice (a core tier exists), but Phase 1 closes **no** PRD-EV
item (the ``/3`` integration + ``+Broker`` profile evidence remain; authoring is not evidence,
VER-002-001 §5). Tag for any claim: "core = the PRD-EV-001/002 L1 slice only (``/3`` / ``+Broker``
remain); predicate-only substrate for other-ADR EV families (all EV-L2+, closes nothing);
capacity / mode / precedence are rcl / authority's (not re-authored). 닫는 PRD-EV = 0건.
EV-L1-complete claim forbidden."

Public surface groups by module:

* :mod:`tos.protective.vocabulary` — the local guarantee / ownership / domain / admissibility
  / outcome / transition StrEnums.
* :mod:`tos.protective.records` — the digest-bound profile + value / injected-input models.
* :mod:`tos.protective.predicates` — the domain-enumeration / guarantee-level / classification
  / de-restriction / partition-lease / cancellation / retry / time-untrusted / envelope /
  sufficiency predicates.
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.protective._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.protective.predicates import (
    account_minimum_preserved,
    cancellation_admissible,
    contained_emergency_admissible,
    derestriction_admissible,
    domain_enumeration_complete,
    envelope_subordinate,
    guarantee_assignment_complete,
    guarantee_level_resolved,
    is_reserved_guarantee,
    mode_permits_protective,
    partition_lease_admissible,
    protective_capacity_exhausted,
    protective_classification,
    protective_classification_present,
    protective_coverage_added,
    protective_leases_reconciled,
    reserve_sufficiency,
    retry_admissible,
    time_untrusted_protective_admissible,
)
from tos.protective.records import (
    AggregateRiskComparison,
    ContainedEmergencyInputs,
    DeRestrictionInputs,
    HardEnvelopeRef,
    IntermediateStateWitness,
    ProtectiveActionEnvelope,
    ProtectiveCapacityProfile,
    ProtectiveLeaseAdmissibilityScope,
    ProtectiveResourceDomainDeclaration,
)
from tos.protective.vocabulary import (
    REQUIRED_PROTECTIVE_DOMAINS,
    Admissibility,
    DegradedModeTransition,
    GuaranteeLevel,
    ProtectiveActionKind,
    ProtectiveActionOutcome,
    ProtectiveOwnership,
    ProtectiveResourceDomain,
)

__all__ = [
    # base
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — append-only profile-version order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "REQUIRED_PROTECTIVE_DOMAINS",
    "Admissibility",
    "DegradedModeTransition",
    "GuaranteeLevel",
    "ProtectiveActionKind",
    "ProtectiveActionOutcome",
    "ProtectiveOwnership",
    "ProtectiveResourceDomain",
    # records
    "AggregateRiskComparison",
    "ContainedEmergencyInputs",
    "DeRestrictionInputs",
    "HardEnvelopeRef",
    "IntermediateStateWitness",
    "ProtectiveActionEnvelope",
    "ProtectiveCapacityProfile",
    "ProtectiveLeaseAdmissibilityScope",
    "ProtectiveResourceDomainDeclaration",
    # predicates
    "account_minimum_preserved",
    "cancellation_admissible",
    "contained_emergency_admissible",
    "derestriction_admissible",
    "domain_enumeration_complete",
    "envelope_subordinate",
    "guarantee_assignment_complete",
    "guarantee_level_resolved",
    "is_reserved_guarantee",
    "mode_permits_protective",
    "partition_lease_admissible",
    "protective_capacity_exhausted",
    "protective_classification",
    "protective_classification_present",
    "protective_coverage_added",
    "protective_leases_reconciled",
    "reserve_sufficiency",
    "retry_admissible",
    "time_untrusted_protective_admissible",
]
