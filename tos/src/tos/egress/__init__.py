"""Egress Gateway, Credential, Route, and Commit-Proof Security pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-013 (Egress Gateway, Credential, Route, and Commit-Proof Security — "EGRESS")
part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-egress-commit-proof-design.md`` (v1.1, operator-delegated auto-ratified
2026-07-26). It authors the **egress-boundary structural / coordinate model** — the Quorum Commit
Certificate structural completeness, the quorum coordinate currency, the quorum threshold shape, the
evidence-receipt-is-not-a-QCC rejection, the replay / substitution classification, the capability /
permit single-use, the exact binding, the credential-route disjointness, and the not-Phase-1 thin
model properties (egress-generation monotonicity, stale-principal rejection, monotonic denial
non-revival) — over five digest-bound artifacts plus injected value models (design #22 §2).

**This is the thinnest L1 surface in the series; the maximum risk is over-realization (design #22
§0.1/§1/§6b).** EGRESS does **not** re-implement cryptographic / signature / quorum-consensus /
bypass-resistance / credential-custody / route-confinement / rotation / failover / compromise
runtime — those are all **+Security** or injected **verified-flags** consumed with ``is True``. L1
owns only structure, chain-digest consistency, coordinate equality / currency, distinct-count over
injected flags, ``classify_record_pair`` replay / substitution, single-use, and the monotonic
non-revival state machine. No predicate claims to "verify" a signature or "resist" a bypass.

**The two-layer commit-proof boundary (design #22 §0.4b/§3.5 — the key architecture decision).** rcl
(ADR-002-002) owns the ADR-002-012 Commit Proof (the quorum commitment coordinates:
``AuthoritativeSnapshot`` / ``RclTransitionRecord`` / ``LedgerCommandRecord`` / ``writer_fenced`` /
``TransmissionCapability`` / ``claim_capability``); EGRESS owns the **Quorum Commit Certificate**
(QCC) — the egress-boundary aggregating artifact that **carries** the rcl Commit Proof as one of its
bound claims and verifies the §11.1 claim-set completeness, the coordinate currency, and the
threshold shape. ADR §5.7 line 129 verbatim: "The bare ADR-002-012 Commit Proof is necessary but not
sufficient at final egress; the full Quorum Commit Certificate claim set in §11.1 SHALL be
satisfied." EGRESS re-authors **no** rcl commit-proof coordinate, ``writer_fenced``,
``claim_capability``, or ``TransmissionCapability``; it consumes them as injected scalars / verdicts.

**QCC != evidence commit receipt (design #22 §0.4d/§5.4).** An evidence ``EvidenceCommitReceipt`` is
single-signer, ``UNVERIFIED``, and all-false (``evidence/receipt.py:11-12``) — structurally not a
QCC. ``evidence_receipt_is_not_quorum_proof`` is the pure realization of ADR §21.4's leader-receipt
rejection; EGRESS re-authors no evidence receipt / segment-commitment. **command conformance = ioc
axis; egress-scope coordinates = EGRESS axis (design #22 §0.4c)** — ``exact_binding_holds`` consumes
the ioc ``ConformanceResult`` verdict and the capsule ``egress_request_digest`` and adds only the
egress-scope coordinate equality (defence-in-depth, re-authoring neither).

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #22 §0.2/§4.6): it
has **no** send / transmit / sign / re-arm / clear-latch / rotate / failover method — the structural
absence of a transmit method is this package's identity (§4.7 constructive-absence canary; the
structure tests assert it). It **cannot** transmit to a broker, create a route, grant a credential,
arm a generation, or re-arm (all-false :class:`~tos.egress._base.AllFalseEgressAuthority`,
EGRESS-INV-005/010). It produces decision **verdicts** and forward record artifacts; the owning
runtime (a future Broker Egress Gateway / Final Egress Trust Boundary service, +Security) enforces
them. A positive result comes only from positive proof, everything else is denial (design #22
§4.1/§4.3 — the structural seal against the fail-open lesson).

**Truthy-sentinel discipline (design #22 §2.2/§4.7 — #13/#14 M1 adopted from the start).**
``EgressAdmission`` (ADMIT / DENY), ``CommitProofValidity`` (VALID / INVALID / UNKNOWN), and
``RestrictiveLatchState`` (CLEAR / DENY_LATCHED) are **truthy-untestable** ``StrEnum``s (``__bool__``
raises ``TypeError``), so a consumer's ``if admission:`` misuse raises rather than reading ``DENY`` /
``INVALID`` / ``UNKNOWN`` / ``DENY_LATCHED`` as an admission. The mandated gates are
``admission is EgressAdmission.ADMIT`` / ``validity is CommitProofValidity.VALID`` /
``state is RestrictiveLatchState.CLEAR``, and ``bool | None`` flags use ``is True`` / ``is not
True`` / ``is False``.

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + ``CanonicalDecimal``) + ``tos.ordering``
(append-only generation order). It imports **no** sibling — ``tos.afg`` / ``tos.are`` /
``tos.authority`` / ``tos.brokercap`` / ``tos.capsule`` / ``tos.dsl`` / ``tos.evidence`` / ``tos.hag``
/ ``tos.iap`` / ``tos.ioc`` / ``tos.liveauth`` / ``tos.orthostate`` / ``tos.protective`` / ``tos.rcl``
/ ``tos.recon`` / ``tos.replacement`` / ``tos.sbr`` / ``tos.spg`` / ``tos.time`` / ``tos.venue`` and
every sibling that landed later (``tos.nontrade`` / ``tos.cur`` / ``tos.sci`` / ``tos.posttrade``) and any future one are all excluded by the
§7.1 **allowlist** closure test (``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``,
``tos.egress``}) — **sibling edge 0** (design #22 §0.3/§3.4). The rcl ``claim_capability`` /
``TransmissionCapability`` / ``writer_fenced``, ioc ``derived_command_conformance`` /
``mutation_fence_holds``, evidence ``EvidenceCommitReceipt``, and capsule ``Bindings`` are
**re-authored not at all and imported not at all** (produced facts injected as scalars / verdicts /
digests). **PROMOTE 0** — the digest / ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for all five artifacts (design #22 §2.1/§3.1): each is
an immutable issued record; a same-id / different-bytes forgery, re-issue, or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (EGRESS-EV-004/005).

**Completion discipline (design #22 §1).** ``EGRESS-EV-001..013`` are all NOT_IMPLEMENTED. Two rows
(004 QCC Validation, 005 Replay / Substitution) carry an ``EV-L1`` slice (core, ``EV-L1/3+
Security``); one row (001 Credential / Route Inventory) is predicate-only (``EV-L2/3+Security``); the
other ten (002 / 003 / 006-013) are not-Phase-1 (L3+/L5+ runtime security). Phase 1 authors the
L1-decidable structural / coordinate substrate and closes **no** EGRESS-EV item — even the two core
rows carry ``/3`` (integration / adversarial) plus +Security (quorum consensus / cryptographic
signature / bypass resistance) residue (authoring is not evidence, VER-002-001 §5; ADR §23 line 618
"Written cases are not completed evidence"; §26 line 708 "Authorship ... does not satisfy this
gate"). Tag for any claim: "structural / coordinate predicate substrate only; EGRESS-EV-001..013
remain NOT_IMPLEMENTED pending EV-L2/L3 integration, adversarial, and +Security evidence;
**EV-L1-complete claim forbidden**; cryptographic validity is an injected verified-flag; L1 is
structure / chain / generation only; no ADR acceptance, restricted-live, or production is
authorized."

Public surface groups by module:

* :mod:`tos.egress.vocabulary` — the EGRESS-axis StrEnums (truthy-untestable ``EgressAdmission`` /
  ``CommitProofValidity`` / ``RestrictiveLatchState`` + closed ``SignerRole``).
* :mod:`tos.egress.records` — the five digest-bound artifacts + the all-false ``AllFalseEgressAuthority``.
* :mod:`tos.egress.state` — the injected value / input models + the ``tos.ordering`` generation REUSE.
* :mod:`tos.egress.predicates` — the core §5.1-§5.7 + predicate-only §6.1 + not-Phase-1 §6b decision
  rules.
"""

from __future__ import annotations

from tos.egress._base import (
    AllFalseEgressAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.egress.predicates import (
    capability_and_permit_single_use,
    credential_route_authority_disjoint,
    egress_generation_monotonic,
    evidence_receipt_is_not_quorum_proof,
    exact_binding_holds,
    monotonic_denial_no_revival,
    quorum_commit_certificate_structurally_complete,
    quorum_coordinates_current,
    quorum_threshold_structurally_met,
    replay_or_substitution_detected,
    stale_principal_structurally_rejected,
)
from tos.egress.records import (
    ActiveEgressPrincipalSet,
    EgressGeneration,
    EgressRequestRecord,
    QuorumCommitCertificate,
    ReplayObservation,
)
from tos.egress.state import (
    ClaimObservation,
    CommitProofCoordinates,
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressEvent,
    EgressPrincipal,
    SignerCoordinate,
    TrialClaims,
    generation_monotone,
)
from tos.egress.vocabulary import (
    CommitProofValidity,
    EgressAdmission,
    RestrictiveLatchState,
    SignerRole,
)

__all__ = [
    # base (reused core + egress-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseEgressAuthority",
    # vocabulary
    "EgressAdmission",
    "CommitProofValidity",
    "RestrictiveLatchState",
    "SignerRole",
    # records — the five digest-bound artifacts
    "QuorumCommitCertificate",
    "EgressRequestRecord",
    "EgressGeneration",
    "ActiveEgressPrincipalSet",
    "ReplayObservation",
    # state — injected value / input models + ordering REUSE
    "SignerCoordinate",
    "EgressCoordinateSet",
    "CredentialRouteInventoryEntry",
    "CommitProofCoordinates",
    "TrialClaims",
    "EgressPrincipal",
    "ClaimObservation",
    "EgressEvent",
    "generation_monotone",
    # core §5 predicates
    "quorum_commit_certificate_structurally_complete",
    "quorum_coordinates_current",
    "quorum_threshold_structurally_met",
    "evidence_receipt_is_not_quorum_proof",
    "replay_or_substitution_detected",
    "capability_and_permit_single_use",
    "exact_binding_holds",
    # predicate-only §6.1
    "credential_route_authority_disjoint",
    # not-Phase-1 thin model §6b
    "egress_generation_monotonic",
    "stale_principal_structurally_rejected",
    "monotonic_denial_no_revival",
]
