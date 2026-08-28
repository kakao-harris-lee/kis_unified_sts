"""sbr-local base re-export shim + all-false recovery authority (design #17 §2 / §0.4).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #17 §3.1 — no new digest-binding base). The
content-addressed sbr citizens (``RecoveryTrigger`` / ``RecoveryInventoryCut`` /
``RecoveryObligation``) inherit :class:`~tos.canonical.DigestBoundArtifact` directly (the
``tos.evidence`` precedent — a digest-bound record with no ``f(digest)`` id derivation),
while the issued-identity citizens (``RecoverySession`` / ``RecoveryEvidencePackage`` /
``RecoveryReadinessDecision``) inherit :class:`~tos.canonical.IndependentIdArtifact`
(``id != f(digest)``, so a same-id / different-bytes forged, re-issued, contradictory, or
replayed record stays a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``; design
#17 §2.1/§3.1). This module is a thin re-export shim (the ``tos.afg._base`` /
``tos.rcl._base`` precedent), so ``from tos.sbr._base import IndependentIdArtifact`` reads
locally while the definition stays single-sourced in core.

The one sbr-local addition is :class:`RecoveryAuthorityEffect` — an authority block whose
every declared boolean flag is forced ``false`` at construction. The all-false authority
*contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here (the
rcl ``AllFalseAuthority`` ``_base.py:55`` / afg ``AllFalseActionFlowAuthority``
``_base.py:58`` precedent, design #17 §4.6/§6.7) rather than imported from a sibling: SBR
imports **no** sibling (sibling edge 0, design #17 §0.3/§0.4c), so the all-false contract is
replicated with a note, exactly the codebase's REPLICATE-WITH-NOTE convention for pure
authority/non-revival contracts (design #17 §0.4d).

``readiness != authority``: SBR-INV-003 line 154 verbatim "No Recovery Session, package,
obligation result, readiness decision, operator action, health result, or replay result
creates capacity, Live Authorization, capability, protective classification, broker
transmission, or re-arm permission." §16 line 424: the readiness decision is explicitly
non-authorizing. Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #17 §0.3).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
)

__all__ = [
    "RecoveryAuthorityEffect",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class RecoveryAuthorityEffect(FrozenModel):
    """Authority effect of a recovery artifact — every flag forced ``false`` (SBR-INV-003).

    The pure-model realization of ``readiness != authority`` (SBR-INV-003 line 154; ADR §7
    line 212; §16 line 424 "explicit no-authority"): no Recovery Session, package, obligation
    result, or readiness decision creates capacity, issues Live Authorization, issues a
    capability, classifies protective, transmits to a broker, or grants re-arm. Isomorphic to
    the rcl ``RclAuthorityEffect`` / afg ``ActionFlowGovernorEffect`` all-false blocks
    (authored locally-fresh, **not** imported — SBR has sibling edge 0, design #17
    §0.3/§0.4c/§0.4d). Any ``True`` authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so
    a consuming runtime re-checks the invariant with
    :func:`~tos.sbr.predicates.recovery_authority_separated` (defence in depth — never trust
    an un-validated block).
    """

    creates_capacity: bool = False
    issues_live_auth: bool = False
    issues_capability: bool = False
    classifies_protective: bool = False
    transmits_broker: bool = False
    grants_rearm: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> RecoveryAuthorityEffect:
        """Reject construction if any authority flag is ``True`` (SBR-INV-003 line 154)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(readiness != authority — SBR-INV-003 line 154; a Recovery Session / "
                    "package / obligation result / readiness decision creates no capacity, "
                    "Live Authorization, capability, protective classification, broker "
                    "transmission, or re-arm permission)"
                )
        return self
