"""rlp-local base re-export shim + all-false trial authority effect (design #25 §2/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from :mod:`tos.canonical`
(design #25 §3.1 — "재정의 금지"; **PROMOTE 0**: ``IndependentIdArtifact`` is already core from
design #6). The five digest-bound RLP citizens (``TrialPolicy`` / ``ExactTrialPlan`` / ``TrialRun`` /
``TrialEvidencePackage`` / ``ProductionScopePromotionDecision``) inherit
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``): the id is separately issued, so
a same-id / different-bytes forged, re-issued, or replayed record is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #25 §2.1/§3.1 — RLP-EV-001/007). This module
is a thin re-export shim (the ``tos.cur._base`` / ``tos.egress._base`` / ``tos.hag._base``
precedent), so ``from tos.rlp._base import IndependentIdArtifact`` reads locally while the definition
stays single-sourced in core.

The one rlp-local addition is :class:`AllFalseTrialAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction (RLP-INV-001; §7 "a policy, plan, run
state, evidence, review, and promotion artifact create no ... authority"). The all-false authority
*contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here (the rcl
``AllFalseAuthority`` / egress ``AllFalseEgressAuthority`` / cur ``AllFalseCurrentnessAuthority``
precedent, design #25 §2.4/§3.3) rather than imported from a sibling: rlp imports **no** sibling
(sibling edge 0, design #25 §0.3/§3.4), and the flag names are trial-specific, so the all-false
contract is re-expressed with a note — exactly the codebase's REPLICATE-WITH-NOTE convention for pure
authority contracts.

``trial artifact != authority``: RLP-INV-001 line 150 — a Trial Policy / Exact Trial Plan / Trial
Run / Trial Evidence Package / Production Scope Promotion Decision is **verified data / a
non-authorizing decision, not permission**. Holding one creates no capacity, protection, Live
Authorization, capability, transmission, HALT clear, re-arm, or broker permission (RLP-INV-001 line
150 verbatim: "Policy, plan, run state, evidence, review, and promotion artifacts create **no**
capacity, protection, Live Authorization, capability, transmission, HALT clear, or re-arm
authority"). Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling ``tos.*``
(design #25 §0.3).
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
    "AllFalseTrialAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseTrialAuthority(FrozenModel):
    """Authority effect of a trial artifact — every flag forced ``false`` (RLP-INV-001; §7).

    The pure-model realization of ``trial artifact != authority`` (RLP-INV-001; ADR-002-025 §7): a
    Trial Policy / Exact Trial Plan / Trial Run / Trial Evidence Package / Production Scope Promotion
    Decision permits nothing at runtime — it creates / mutates / releases no capacity, classifies /
    creates no protection, issues no Live Authorization / capability, transmits nothing, clears no
    HALT, re-arms nothing, and grants no broker permission. RLP-INV-001 line 150 verbatim: "Policy,
    plan, run state, evidence, review, and promotion artifacts create **no** capacity, protection,
    Live Authorization, capability, transmission, HALT clear, or re-arm authority." Authority comes
    only from the positive §5/§6 structural / completeness predicates plus the owning +Security /
    +Broker runtime and the human governance steps — never from the mere existence / possession of a
    trial artifact. Isomorphic to the rcl ``AllFalseAuthority`` / egress ``AllFalseEgressAuthority`` /
    cur ``AllFalseCurrentnessAuthority`` all-false blocks (authored locally-fresh, **not** imported —
    rlp has sibling edge 0, design #25 §0.3/§2.4; the flag names are trial-specific). Any ``True``
    authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth; the §5/§6 predicates
    re-derive authority from positive proof and never read this block as a grant, §6.4).
    """

    creates_capacity: bool = False
    creates_protection: bool = False
    issues_live_authorization: bool = False
    issues_capability: bool = False
    transmits: bool = False
    clears_halt: bool = False
    re_arms: bool = False
    grants_broker_permission: bool = False
    classifies_protection: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseTrialAuthority:
        """Reject construction if any authority flag is ``True`` (RLP-INV-001; §7)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(trial artifact != authority — RLP-INV-001 / ADR-002-025 §7; a Trial Policy / "
                    "Exact Trial Plan / Trial Run / Trial Evidence Package / Production Scope "
                    "Promotion Decision cannot create or release capacity, classify or create "
                    "protection, issue Live Authorization or capability, transmit, clear a HALT, "
                    "re-arm, or grant broker permission — it is verified data / a non-authorizing "
                    "decision, not permission)"
                )
        return self
