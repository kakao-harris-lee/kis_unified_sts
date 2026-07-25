"""Broker Capability pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-004 (Broker Capability Requirements and Fallbacks) part of
IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-25-tos-broker-capability-design.md`` (v1.1). It represents what a
broker actually guarantees as a **versioned, evidence-backed Broker Capability Profile**,
and authors the admissibility / fallback / version-enforcement / drift / environment-binding
/ Final-Quantity-Proof predicates by which a capability deficiency **reduces or prohibits**
live scope (ADR §1 line 32).

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #10
§0.2/§4.5): frozen pydantic models over injected state + conservative fail-closed
predicates. It **cannot** transmit / retry / mutate capacity / issue authorization / set a
KnowledgeState — it produces decision **bools** / scalars; the owning runtime (a future
Broker Adapter, ADR §19/§27) enforces them. There is no "assume-admissible" path anywhere:
``ADMISSIBLE`` / ``True`` comes only from positive proof, everything else is restrictive
(design #10 §4.1 — the structural seal against the #6 fail-open REJECT lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + the already-core ``CanonicalDecimal``,
design #10 §0.4c) + ``tos.ordering`` (append-only profile-version order) — no ``numpy`` /
``pandas`` / ``yaml``, no ``shared.*``, and — as the decision-side **upstream** capability
model — **none** of its consumers / siblings ``tos.liveauth`` / ``tos.orthostate`` /
``tos.recon`` / ``tos.rcl`` / ``tos.evidence`` / ``tos.capsule`` / ``tos.time`` /
``tos.authority`` / ``tos.dsl`` (design #10 §0.3/§3.4/§3.5 — **sibling edge 0**; the three
consumers already declared injected ``bool | None`` / ``str | None`` seams, the evidence
store is a downstream projection, and freshness / horizons are injected flags). Actively
verified by the §7.1 import-closure test in ``tos/tests/brokercap``. **PROMOTE 0건** —
``CanonicalDecimal`` is already core (design #9 §0.4c).

Identity is **independent, not** ``f(digest)`` (design #10 §3.1): each profile version is an
immutable record; a legitimate revalidation / supersession is a new ``profile_id``, a same-id
/ different-bytes re-issuance is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #10 §1):** ``BC-EV-001..022`` are all predicate / coordinate
substrate (register minimum EV-L2+; ``-015`` / ``-020`` +Security) — there is **no** EV-L1
slice and Phase 1 closes **no** BC-EV item (authoring is not evidence, VER-002-001 §5). Tag
for any claim: "predicate / coordinate substrate only; BC-EV-001..022 remain
NOT_IMPLEMENTED pending EV-L2/L3 (+Broker/+Security/Profile-dependent) fault injection,
adversarial, chaos, broker-profile, and security evidence; no core tier (EV-L1 slice 0);
EV-L1-complete claim forbidden."

Public surface groups by module:

* :mod:`tos.brokercap.vocabulary` — the 9 capability-CLASS StrEnums.
* :mod:`tos.brokercap.records` — the digest-bound profile + value / injected-input models.
* :mod:`tos.brokercap.predicates` — admissibility / fallback / uncertain-send / version /
  drift / FQP / environment / partition predicates.
"""

from __future__ import annotations

from tos.brokercap._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.brokercap.predicates import (
    active_conformance_class,
    active_profile_version,
    apply_drift,
    broker_capability_added,
    broker_capability_sufficient,
    broker_evidence_admissible_under_profile,
    capability_admissible,
    credential_scope_declared_ok,
    drift_detected,
    environment_binding_ok,
    external_detection_ok,
    fallback_admissible,
    fqp_adequate,
    partition_class_scope_ok,
    partition_protective_class,
    profile_version_current,
    rate_admission_ok,
    same_order_retry_allowed,
    uncertain_send_policy,
)
from tos.brokercap.records import (
    BrokerCapabilityProfile,
    BrokerEvidenceRef,
    CapabilityDeclaration,
    FallbackSpec,
    FinalQuantityEvidence,
    FinalQuantityProofRule,
    LiveScope,
    ObservedBehavior,
    ProfileKey,
    ProfileVersion,
    RequiredCapabilitySet,
    UncertainSendVerdict,
)
from tos.brokercap.vocabulary import (
    ASSURANCE_LEVEL_RANK,
    AUTHORIZING_STATUSES,
    NON_LIVE_OR_SUPERVISED_CLASSES,
    AcknowledgementState,
    Admissibility,
    AssuranceLevel,
    AssuranceSource,
    CapabilityDimension,
    CapabilityStatus,
    ConformanceClass,
    ProhibitedProof,
    ReplaceSemantics,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

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
    "ASSURANCE_LEVEL_RANK",
    "AUTHORIZING_STATUSES",
    "NON_LIVE_OR_SUPERVISED_CLASSES",
    "AcknowledgementState",
    "Admissibility",
    "AssuranceLevel",
    "AssuranceSource",
    "CapabilityDimension",
    "CapabilityStatus",
    "ConformanceClass",
    "ProhibitedProof",
    "ReplaceSemantics",
    # records
    "BrokerCapabilityProfile",
    "BrokerEvidenceRef",
    "CapabilityDeclaration",
    "FallbackSpec",
    "FinalQuantityEvidence",
    "FinalQuantityProofRule",
    "LiveScope",
    "ObservedBehavior",
    "ProfileKey",
    "ProfileVersion",
    "RequiredCapabilitySet",
    "UncertainSendVerdict",
    # predicates
    "active_conformance_class",
    "active_profile_version",
    "apply_drift",
    "broker_capability_added",
    "broker_capability_sufficient",
    "broker_evidence_admissible_under_profile",
    "capability_admissible",
    "credential_scope_declared_ok",
    "drift_detected",
    "environment_binding_ok",
    "external_detection_ok",
    "fallback_admissible",
    "fqp_adequate",
    "partition_class_scope_ok",
    "partition_protective_class",
    "profile_version_current",
    "rate_admission_ok",
    "same_order_retry_allowed",
    "uncertain_send_policy",
]
