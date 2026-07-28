"""Software Supply-Chain Integrity, Release-Artifact Admission, and Deployment Provenance
Governance (ADR-002-029 — "SCI") pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-029 part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1) per the ratified design
contract ``docs/plans/2026-07-28-tos-supply-chain-design.md`` (v1.3, operator-delegated
auto-ratification 2026-07-28). It authors the **release-admission predicate / model substrate** —
exact source identity and review integrity (SCI-EV-001), provenance-is-not-admission (SCI-EV-002),
dependency and toolchain closure completeness (SCI-EV-003), and independent admission plus complete
admitted-release-set (SCI-EV-006) — over nine digest-bound artifacts plus injected value models
(design #29 §2).

**SCI is a greenfield release-admission content producer that already has one landed downstream
consumer (design #29 §0.1-2/§0.4b).** Unlike WDR (#26), which had zero inbound deferral, ``tos.spg``
(ADR-002-014) carries the consumption slot ``SemanticValidationInputs.software_deployment_ok``
(``tos/src/tos/spg/records.py`` line 206, gated ``is not True`` at
``tos/src/tos/spg/predicates.py`` line 467) and defers four of the seven BundleMember items
("Release Generation, compatibility graph, runtime-attestation requirements ... software
compatibility manifests"; ``tos/src/tos/spg/vocabulary.py`` lines 185-187) to ADR-002-029/030. SCI
**produces** that verdict through :func:`~tos.sci.predicates.software_deployment_ok_verdict` and
takes **no import edge** to spg or to any other sibling. The name ``tos.sci`` is fixed by the
register prefix and by eight landed files that already enumerate it as a not-landed excluded package
(``egress/__init__.py`` line 65, ``cur/__init__.py`` line 51, ``rlp/__init__.py`` line 39,
``wdr/__init__.py`` line 47, plus their four import-closure tests) — a **stronger soft
load-bearing** than WDR's (design #29 §0.4a).

The two maximum risks are opposite (design #29 §0.1-5):

1. **over-realization** — cryptographic signature verification, reproducibility byte comparison,
   scan execution, SBOM parsing, registry retrieval, runtime measurement, effective-principal
   collapse, capacity arithmetic, configuration activation, the per-send currentness transaction,
   incident lifecycle, production promotion, evidence custody, recovery / re-arm, and the
   restriction-floor **advance** are all runtime / human / +Security / +Broker / sibling owned,
   never L1;
2. **duplication** — the spg Hard Safety Envelope and configuration activation, hag
   effective-principal collapse and quorum, rcl ``CapacityVector``, egress final-egress, cur Safety
   Currentness Vector **and** ``RestrictiveFenceRecord`` / ``fence_advances_floor``, evidence
   custody, liveauth Live Authorization, authority epoch, rlp production promotion, sbr Recovery
   Barrier, failuredomain's four RFC-002 §24.1 supply-chain **coordinates**, and posttrade's share
   of the spg deferral are **all injected-consumed**, re-authored not at all (design #29 §3.5).

The dsl ``AdmissibilityResult`` (``tos/src/tos/dsl/evidence.py`` line 58) is a **different
proposition**, not a seam: it is command admissibility and its own docstring (line 66) says it is
"separate from ADR-002-029 software-artifact admission".

This package is **pure, non-transmitting, non-mutating, and clock-free** (design #29 §0.2/§0.3): it
has **no** deploy / admit / activate / sign / transmit / arm / mutate / reserve / release /
clear-restriction method — the structural absence of such a method is part of its identity. It
**cannot** create capacity, approval, protection, live authority, broker permission, incident
closure, readiness, scope restoration, or re-arm (all-false
:class:`~tos.sci._base.AllFalseSupplyChainAuthority`, SCI-INV-001 line 155). A positive result comes
only from positive proof; everything else is denial (design #29 §5.0 — negative-polarity fields are
cleared by ``is False`` alone, never by ``is not True``).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair``) + ``tos.ordering`` (Release Generation and
restriction-floor order). It imports **no** sibling — every real sibling and any future one is
excluded by the §6.1 **allowlist** closure test (``tos.*`` closure ⊆ {``tos.canonical``,
``tos.ordering``, ``tos.sci``}) — **sibling edge 0** (design #29 §0.3/§3.4). **rcl edge 0** in
particular: §7 line 235 "Mutate or release capacity | **Risk Capacity Ledger only** | artifact
lifecycle never writes capacity", so the worst-credible economic-effect envelope is an injected
opaque coordinate, never a ``CapacityVector`` type (design #29 §0.4g). **PROMOTE 0** — the digest
and ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for all nine artifacts (design #29 §2.1/§0.4c): all
eight canonical templates carry an independent ``*_id`` beside a separate ``canonical_digest``, so a
same-id / different-**covered**-bytes forgery, re-issue, or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``, and a pre-issuance pair is ``NOT_COMPARABLE``.

**ADR-002-027 (``tos.sir``) — measured twice (design #29 §0.4f/§9.2-5).** ``git ls-files
tos/src/tos/sir/`` was **empty** when this package was started; the sibling **landed
mid-implementation**, so the planned deferral docstring was upgraded to a test-only seam
cross-check (``tos/tests/sci/test_seam_sir.py``). The runtime treatment is the same either way:
incident handoff is ADR-002-027; consumed as injected opaque generation; sibling not committed at
implementation start — **no ``tos.sir`` import, no ``tos.sir`` type**. ADR-002-030
(``tos.posttrade``) **is** landed too, and SCI takes no edge to it either — the two share the spg
BundleMember deferral by item split, not by import (design #29 §3.5).

**Completion discipline (design #29 §1) — the regime tag every claim carries.** Release-admission
predicate / model substrate only; ``SCI-EV-001..012`` are **all** ``NOT_IMPLEMENTED``; the four core
rows carry an ``EV-L1`` slice (001 ``EV-L1/3+Security``, 002 ``EV-L1/2/3+Security``, 003
``EV-L1/2/3+Security``, 006 ``EV-L1/3+Security``) and the other eight are not Phase-1 at all; and
**all twelve register rows carry ``+Security``** — the only ADR in the governance sextet for which
that is true — so **no SCI-EV is closed by code alone** and the organisational security-boundary
gate is entirely unmet. Effective-principal collapse, capacity arithmetic, configuration activation,
per-send egress binding, reproducibility comparison, runtime measurement, signature verification,
and restriction-floor advance are re-authored / runtime / human / +Security / +Broker / sibling
owned. L1 decides only admission structure, generation monotonicity, restriction non-revival,
mutable-name rejection, and all-false authority. **An EV-L1-complete claim is forbidden**, and
ADR-002-029 remains ``Proposed`` (§30 line 658: "This ADR authorizes architecture and implementation
planning only").

**Zero hardcoded numbers (design #29 §8).** The ten ADR §29 item 12 VERIFICATION-PROFILE-002 keys
(``B_supply_chain_compromise_detect``, ``B_release_restriction_to_authority_restrict``,
``B_release_restriction_to_egress_deny``, ``B_release_generation_fence``,
``B_runtime_artifact_drift_detect``, ``MAX_build_provenance_age_ms``,
``MAX_artifact_admission_decision_age_ms``, ``MAX_admitted_release_set_age_ms``,
``MAX_runtime_artifact_attestation_age_ms``, ``MAX_release_key_status_age_ms``) all exist already
with ``value: null`` and ``owner: TBD`` — SCI authors **no new key** and hardcodes **no number**;
every bound is injected.

This package names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``): broker finality and transmission are capability classes owned by the
Broker Adapter / Egress Gateway (§7 line 238; §23 line 449).
"""

from __future__ import annotations

from tos.sci._base import (
    AllFalseSupplyChainAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.sci.predicates import (
    active_currentness_is_negative_gate,
    admission_admits_only_positive,
    admitted_set_no_permissive_union,
    closure_complete_or_restrictive,
    independence_unproven_is_common_mode,
    mutable_name_is_not_identity,
    provenance_is_not_admission,
    release_artifact_identity_exact,
    release_generation_monotonic,
    restriction_is_monotonic_non_revival,
    rollback_is_new_generation,
    software_deployment_ok_verdict,
    source_identity_exact_and_reviewed,
    supply_chain_artifact_not_authority,
)
from tos.sci.records import (
    AdmittedReleaseSet,
    ArtifactAdmissionDecision,
    BuildProvenanceAttestation,
    DependencyToolchainClosureManifest,
    ReleaseArtifactManifest,
    ReleaseRestriction,
    RuntimeArtifactAttestation,
    SoftwareReleasePolicy,
    SourceRevisionManifest,
)
from tos.sci.state import (
    AdmissionBindingSet,
    AttestationTimeBinding,
    BuildProvenanceBinding,
    DecisionTimeBinding,
    DependencyAndToolchainBinding,
    DependencyClosureDigestSet,
    PolicyBinding,
    ReleaseArtifactBinding,
    ReleaseBinding,
    SoftwareReleasePolicyFieldGroups,
    SourceRevisionManifestBinding,
    SupplyChainScope,
    VerificationProfileBinding,
    generation_strictly_advances,
    restriction_floor_not_behind,
)
from tos.sci.vocabulary import (
    ACTIVE_CURRENTNESS_ITEMS,
    ADMISSION_PROTOCOL_STEPS,
    APPROVAL_GATE_ITEMS,
    AUTHORITY_OWNERSHIP_ACTIONS,
    MUTABLE_NAME_METACHARACTERS,
    MUTABLE_NAME_SENTINELS,
    PARTITION_FAILURE_MODES,
    SCI_ACCEPTANCE_CASE_TITLES,
    SCI_INVARIANT_TITLES,
    SOFTWARE_RELEASE_POLICY_FIELD_GROUPS,
    UNKNOWN_RESTRICTION_STATE,
    AdmissionResult,
    IndependenceResult,
    is_mutable_name_notation,
)

__all__ = [
    # base — reused core + the sci-local all-false authority
    "AllFalseSupplyChainAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    # vocabulary — the two tri-state enums, the mutable-name helper, the §4 anchors
    "AdmissionResult",
    "IndependenceResult",
    "MUTABLE_NAME_METACHARACTERS",
    "MUTABLE_NAME_SENTINELS",
    "UNKNOWN_RESTRICTION_STATE",
    "is_mutable_name_notation",
    "ACTIVE_CURRENTNESS_ITEMS",
    "ADMISSION_PROTOCOL_STEPS",
    "APPROVAL_GATE_ITEMS",
    "AUTHORITY_OWNERSHIP_ACTIONS",
    "PARTITION_FAILURE_MODES",
    "SCI_ACCEPTANCE_CASE_TITLES",
    "SCI_INVARIANT_TITLES",
    "SOFTWARE_RELEASE_POLICY_FIELD_GROUPS",
    # records — the nine digest-bound artifacts
    "AdmittedReleaseSet",
    "ArtifactAdmissionDecision",
    "BuildProvenanceAttestation",
    "DependencyToolchainClosureManifest",
    "ReleaseArtifactManifest",
    "ReleaseRestriction",
    "RuntimeArtifactAttestation",
    "SoftwareReleasePolicy",
    "SourceRevisionManifest",
    # state — injected value models, the §4 anchor views, and the two ordering helpers
    "AdmissionBindingSet",
    "AttestationTimeBinding",
    "BuildProvenanceBinding",
    "DecisionTimeBinding",
    "DependencyAndToolchainBinding",
    "DependencyClosureDigestSet",
    "PolicyBinding",
    "ReleaseArtifactBinding",
    "ReleaseBinding",
    "SoftwareReleasePolicyFieldGroups",
    "SourceRevisionManifestBinding",
    "SupplyChainScope",
    "VerificationProfileBinding",
    "generation_strictly_advances",
    "restriction_floor_not_behind",
    # predicates — five yolk + five cross-cutting + three supporting
    "source_identity_exact_and_reviewed",
    "provenance_is_not_admission",
    "closure_complete_or_restrictive",
    "admission_admits_only_positive",
    "admitted_set_no_permissive_union",
    "supply_chain_artifact_not_authority",
    "release_generation_monotonic",
    "rollback_is_new_generation",
    "restriction_is_monotonic_non_revival",
    "active_currentness_is_negative_gate",
    "software_deployment_ok_verdict",
    "mutable_name_is_not_identity",
    "independence_unproven_is_common_mode",
    "release_artifact_identity_exact",
]
