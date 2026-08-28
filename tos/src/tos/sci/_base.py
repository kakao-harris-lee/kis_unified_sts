"""sci-local base re-export shim + all-false supply-chain authority (design #29 §2/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from :mod:`tos.canonical`
(design #29 §3.1 — no re-definition; **PROMOTE 0**: ``IndependentIdArtifact`` is already core from
design #6). The nine digest-bound SCI citizens (the eight canonical-template artifacts —
``SoftwareReleasePolicy`` / ``SourceRevisionManifest`` / ``DependencyToolchainClosureManifest`` /
``BuildProvenanceAttestation`` / ``ReleaseArtifactManifest`` / ``ArtifactAdmissionDecision`` /
``AdmittedReleaseSet`` / ``RuntimeArtifactAttestation`` — plus the ADR-§5.11-derived
``ReleaseRestriction``) inherit :class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``):
all eight templates carry an independent ``*_id`` field beside a separate ``canonical_digest``
(design #29 §0.4c), so a same-id / different-covered-bytes forged, re-issued, or replayed record is
a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. This module is a thin re-export shim
(the ``tos.wdr._base`` / ``tos.rlp._base`` / ``tos.cur._base`` / ``tos.egress._base`` precedent), so
``from tos.sci._base import IndependentIdArtifact`` reads locally while the definition stays
single-sourced in core.

The one sci-local addition is :class:`AllFalseSupplyChainAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction (SCI-INV-001 line 155: "No policy,
manifest, provenance attestation, signature, admission decision, release set, deployment record,
runtime attestation, scan, test, or evidence artifact creates capacity, approval, protection, live
authority, broker permission, incident closure, readiness, scope restoration, or re-arm"). The
all-false authority *contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh**
here (the rcl ``AllFalseAuthority`` / egress ``AllFalseEgressAuthority`` / cur
``AllFalseCurrentnessAuthority`` / rlp ``AllFalseTrialAuthority`` / wdr ``AllFalseDeviationAuthority``
precedent, design #29 §2.4/§3.3) rather than imported from a sibling: sci imports **no** sibling
(sibling edge 0, design #29 §0.3/§3.4), and the flag names are supply-chain-specific. The cur
``AllFalseCurrentnessAuthority`` overlap is **pattern-only** — each is local, the field sets differ,
and there is no import (design #29 §3.5).

The declared set is the **union of the ``authority:`` block of all eight canonical templates**
(design #29 §2.4 / M2 — twenty field names, each an observed template field, not an invented one).
``creates_artifact_admission`` in particular is load-bearing: SCI-INV-004 ("Provenance Is Not
Correctness", ADR §6 line 167) is realized by :func:`~tos.sci.predicates.provenance_is_not_admission`
reading ``proves_semantic_correctness is False`` **and** ``creates_artifact_admission is False`` on
the build-provenance attestation — without the second flag that argument would be vacuous.

``supply-chain artifact != authority``: holding a policy / manifest / attestation / decision /
release set / restriction creates no capacity, approval, protection, live authority, broker
permission, incident closure, readiness, scope restoration, or re-arm. Any ``True`` flag makes the
artifact unconstructable.

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — all twelve
register rows carry ``+Security`` and the organisational security-boundary gate is entirely unmet;
an EV-L1-complete claim is forbidden (design #29 §1).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling ``tos.*``
(design #29 §0.3).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "AllFalseSupplyChainAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseSupplyChainAuthority(FrozenModel):
    """Authority effect of a supply-chain artifact — every flag ``false`` (SCI-INV-001; §7).

    The pure-model realization of ``supply-chain artifact != authority`` (SCI-INV-001, ADR-002-029
    §6 line 155; §7 line 221-241): a Software Release Policy / Source Revision Manifest / Dependency
    and Toolchain Closure Manifest / Build Provenance Attestation / Release Artifact Manifest /
    Artifact Admission Decision / Admitted Release Set / Runtime Artifact Attestation / Release
    Restriction permits nothing at runtime. §1 line 21 verbatim: an ``ADMIT`` "does not deploy
    software, activate configuration, issue Safety Authority or Live Authorization, mutate or
    release Risk Capacity Ledger capacity, classify protection, create a Transmission Capability,
    permit broker transmission, clear HALT, close an incident, establish recovery readiness, restore
    production scope, or re-arm."

    **The twenty field names are the union of the ``authority:`` block of the eight canonical
    templates** (design #29 §2.4 / M2), not invented flags:

    * ``active`` — every template except SOFTWARE-RELEASE-POLICY, which spells it ``policy_active``;
    * ``policy_active`` — SOFTWARE-RELEASE-POLICY only;
    * ``creates_source_approval`` — policy / source-revision / dependency / release-artifact /
      admission-decision / admitted-set;
    * ``creates_artifact_admission`` — policy / source-revision / dependency / provenance /
      release-artifact / admitted-set / runtime (**SCI-INV-004 load-bearing**, §5.2);
    * ``creates_artifact_admission_without_release_commit`` + ``commits_release_generation`` — the
      ARTIFACT-ADMISSION-DECISION variant (§15 step 8 vs step 9 separation);
    * ``proves_semantic_correctness`` — the BUILD-PROVENANCE-ATTESTATION variant (SCI-INV-004);
    * ``deploys_software`` / ``activates_configuration`` / ``creates_capacity`` /
      ``mutates_or_releases_capacity`` / ``creates_protective_classification`` /
      ``creates_live_authorization`` / ``creates_transmission_capability`` /
      ``permits_broker_transmission`` — every template;
    * ``clears_safety_state`` — source-revision / dependency / provenance / release-artifact;
    * ``clears_halt_latch_gap_restriction_or_incident`` — policy / admission-decision / admitted-set
      / runtime;
    * ``establishes_recovery_readiness`` / ``restores_scope`` / ``permits_rearm`` — every template.

    Every real owner is a sibling / runtime / human: capacity is the Risk Capacity Ledger's alone
    (§7 line 235 "Mutate or release capacity | Risk Capacity Ledger only"), configuration activation
    is ADR-002-014's (§7 line 233), restriction latch clearance is ADR-002-024's (§7 line 234),
    protection is the Protective Action Controller's (§7 line 236), incident lifecycle is
    ADR-002-027's (§7 line 237), transmission is the Broker Adapter / Egress Gateway's (§7 line
    238), and re-arm is ADR-002-017 then ADR-002-007/015's (§7 line 239). Authority comes only from
    those owners' independently granted verdicts, never from the mere existence or possession of a
    supply-chain artifact. Any ``True`` authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth; the §5 predicates
    re-derive every verdict from positive proof and never read this block as a grant, §5.6a).
    """

    active: bool = False
    policy_active: bool = False
    creates_source_approval: bool = False
    creates_artifact_admission: bool = False
    creates_artifact_admission_without_release_commit: bool = False
    commits_release_generation: bool = False
    proves_semantic_correctness: bool = False
    deploys_software: bool = False
    activates_configuration: bool = False
    creates_capacity: bool = False
    mutates_or_releases_capacity: bool = False
    creates_protective_classification: bool = False
    creates_live_authorization: bool = False
    creates_transmission_capability: bool = False
    permits_broker_transmission: bool = False
    clears_safety_state: bool = False
    clears_halt_latch_gap_restriction_or_incident: bool = False
    establishes_recovery_readiness: bool = False
    restores_scope: bool = False
    permits_rearm: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseSupplyChainAuthority:
        """Reject construction if any authority flag is ``True`` (SCI-INV-001; §7)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(supply-chain artifact != authority — SCI-INV-001 / ADR-002-029 §6 line "
                    "155, §7; a policy, manifest, provenance attestation, signature, admission "
                    "decision, release set, deployment record, runtime attestation, scan, test, "
                    "or evidence artifact creates no capacity, approval, protection, live "
                    "authority, broker permission, incident closure, readiness, scope "
                    "restoration, or re-arm)"
                )
        return self
