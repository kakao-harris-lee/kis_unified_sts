"""cur-local base re-export shim + all-false currentness authority effect (design #23 §2/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from :mod:`tos.canonical`
(design #23 §3.1 — "재정의 금지"; **PROMOTE 0**: ``IndependentIdArtifact`` is already core from
design #6). The four digest-bound CUR citizens (``SafetyCurrentnessVector`` /
``EgressCurrentnessProof`` / ``RestrictiveFenceRecord`` / ``CurrentnessPolicy``) inherit
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``): the id is separately issued, so
a same-id / different-bytes forged, re-issued, or replayed record is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #23 §2.1/§3.1 — CUR-EV-001/004). This module
is a thin re-export shim (the ``tos.egress._base`` / ``tos.venue._base`` / ``tos.hag._base``
precedent), so ``from tos.cur._base import IndependentIdArtifact`` reads locally while the
definition stays single-sourced in core.

The one cur-local addition is :class:`AllFalseCurrentnessAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction (CUR-INV-005; §6.13 "a vector / proof is
verified data, not permission"). The all-false authority *contract* is **not** in ``tos.canonical``,
so it is authored **locally, fresh** here (the rcl ``AllFalseAuthority`` / liveauth
``LiveAuthorizationEffect`` ``_base.py:75`` / egress ``AllFalseEgressAuthority`` precedent, design
#23 §2.4) rather than imported from a sibling: cur imports **no** sibling (sibling edge 0, design #23
§0.3/§3.4), and the flag names are currentness-specific, so the all-false contract is re-expressed
with a note — exactly the codebase's REPLICATE-WITH-NOTE convention for pure authority contracts.

``currentness != authority``: CUR-INV-005 / §1 line 21 — a Safety Currentness Vector / Egress
Currentness Proof / Restrictive Fence Record / Currentness Policy is **verified ordering data, not
permission**. Holding one creates no approval, Intent, capacity, protection, Live Authorization,
Transmission Capability, broker permission, HALT clear, or re-arm authority (§1 line 21 verbatim: "a
currentness sequencer ... does not invent facts, decide business safety, mutate capacity, issue Live
Authorization, classify protection, or transmit"). Any ``True`` flag makes the artifact
unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #23 §0.3).
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
    "AllFalseCurrentnessAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseCurrentnessAuthority(FrozenModel):
    """Authority effect of a currentness artifact — every flag forced ``false`` (CUR-INV-005; §6.13).

    The pure-model realization of ``currentness != authority`` (CUR-INV-005; ADR-002-024 §1 line 21
    / §6.13): a Safety Currentness Vector / Egress Currentness Proof / Restrictive Fence Record /
    Currentness Policy permits nothing at runtime — it approves nothing, mutates / releases no
    capacity, issues no authority / capability, classifies no protection, transmits nothing, clears
    no HALT, and re-arms nothing. CUR-INV-005 line 159 verbatim: "Currentness sequencing and proof
    construction create **no** approval, Intent, capacity, protection, Live Authorization,
    Transmission Capability, broker permission, HALT clear, or re-arm authority." Authority comes
    only from the positive §5/§6 structural / coordinate predicates plus the owning +Security
    runtime — never from the mere existence / possession of a verified currentness artifact.
    Isomorphic to the rcl ``AllFalseAuthority`` / liveauth ``LiveAuthorizationEffect`` / egress
    ``AllFalseEgressAuthority`` all-false blocks (authored locally-fresh, **not** imported — cur has
    sibling edge 0, design #23 §0.3/§2.4; the flag names are currentness-specific). Any ``True``
    authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth; the §5/§6 predicates
    re-derive authority from positive proof and never read this block as a grant, §6.13).
    """

    approves: bool = False
    mutates_capacity: bool = False
    releases_capacity: bool = False
    issues_authority: bool = False
    issues_capability: bool = False
    classifies_protection: bool = False
    transmits: bool = False
    clears_halt: bool = False
    re_arms: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseCurrentnessAuthority:
        """Reject construction if any authority flag is ``True`` (CUR-INV-005; §6.13)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(currentness != authority — CUR-INV-005 / ADR-002-024 §1 line 21 / §6.13; a "
                    "Safety Currentness Vector / Egress Currentness Proof / Restrictive Fence "
                    "Record / Currentness Policy cannot approve, mutate or release capacity, issue "
                    "authority or capability, classify protection, transmit, clear a HALT, or "
                    "re-arm — it is verified ordering data, not permission)"
                )
        return self
