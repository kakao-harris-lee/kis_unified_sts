"""venue-local base re-export shim + all-false venue-gate authority (design #19 §2 / §3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from
:mod:`tos.canonical` (design #19 §3.1 — no new digest-binding base). The three core
venue citizens (``VenueConstraintPolicy`` / ``VenueConstraintSnapshot`` /
``OrderAdmissibilityDecision``) inherit :class:`~tos.canonical.IndependentIdArtifact`
(``id != f(digest)``): the policy / snapshot / decision id is separately issued, so a
same-id / different-bytes forged, re-issued, contradictory, or replayed record is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #19 §2.1/§3.1 — the
capsule ``VenueConstraintPolicyRef`` / ``VenueConstraintSnapshotRef`` /
``OrderAdmissibilityDecisionRef`` ``capsule.py:130-150`` id/generation/digest shape).
This module is a thin re-export shim (the ``tos.sbr._base`` / ``tos.ioc._base``
precedent), so ``from tos.venue._base import IndependentIdArtifact`` reads locally while
the definition stays single-sourced in core.

The one venue-local addition is :class:`VenueGateAuthorityEffect` — an authority block
whose every declared boolean flag is forced ``false`` at construction. The all-false
authority *contract* is **not** in ``tos.canonical``, so it is authored **locally,
fresh** here (the ioc ``AllFalseConstructionAuthority`` ``_base.py:54`` / sbr
``RecoveryAuthorityEffect`` ``_base.py:58`` / rcl ``AllFalseAuthority`` precedent, design
#19 §4.6/§6.7) rather than imported from a sibling: venue imports **no** sibling (sibling
edge 0, design #19 §0.3/§0.4c), so the all-false contract is replicated with a note,
exactly the codebase's REPLICATE-WITH-NOTE convention for pure authority contracts
(design #19 §0.4d).

``admissibility != authority``: VTG-INV-011 line 189 verbatim "Constraint evaluation
cannot approve, mutate capacity, issue authority, classify protection, transmit, clear
HALT, or re-arm." An Order Admissibility Decision is a **safety fact, not permission**
(§1 line 21-23). Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #19 §0.3).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "VenueGateAuthorityEffect",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class VenueGateAuthorityEffect(FrozenModel):
    """Authority effect of a venue-gate artifact — every flag forced ``false`` (VTG-INV-011).

    The pure-model realization of ``admissibility != authority`` (VTG-INV-011 line 189;
    ADR-002-019 §7 line 213; §14 line 341 "explicit non-authorizing flags"): a Venue
    Constraint Gate approves nothing, mutates no capacity, issues no authority, classifies
    no protection, transmits nothing, clears no HALT, and re-arms nothing (§1 line 21-23 —
    an Order Admissibility Decision is a safety fact, not permission). Isomorphic to the
    ioc ``AllFalseConstructionAuthority`` / sbr ``RecoveryAuthorityEffect`` / rcl
    ``AllFalseAuthority`` all-false blocks (authored locally-fresh, **not** imported —
    venue has sibling edge 0, design #19 §0.3/§0.4c/§0.4d). Any ``True`` authority flag
    makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators,
    so a consuming runtime re-checks the invariant with
    :func:`~tos.venue.predicates.gate_authority_separated` (defence in depth — never trust
    an un-validated block).
    """

    approves: bool = False
    mutates_capacity: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    transmits: bool = False
    clears_halt: bool = False
    rearms: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> VenueGateAuthorityEffect:
        """Reject construction if any authority flag is ``True`` (VTG-INV-011 line 189)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(admissibility != authority — VTG-INV-011 line 189; a Venue Constraint "
                    "Gate cannot approve, mutate capacity, issue authority, classify "
                    "protection, transmit, clear HALT, or re-arm — an Order Admissibility "
                    "Decision is a safety fact, not permission, §1 line 21-23)"
                )
        return self
