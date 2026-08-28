"""ioc-local base re-export shim + all-false construction-authority base (design #14 §0.4d).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #14 §3.1 — "재정의 금지"). ``tos.ioc`` authors
**no** new digest-binding base: its five digest-bound citizens — the append-only,
generation-immutable ``ApprovedIntentContract`` / ``AuthorizedConstructionEnvelope`` /
``OrderConstructionPolicy`` / ``CanonicalBrokerCommand`` / ``OrderConformanceProof`` — are
each an :class:`~tos.canonical.IndependentIdArtifact` (governance / issuance-assigned
identity, ``id != f(digest)``, so a same-id / different-bytes forged / re-issued /
contradictory command / proof stays a detectable ``classify_record_pair``
``CRITICAL_CONFLICT``; design #14 §2.1/§3.1). This module is a thin re-export shim (the
``tos.are._base`` / ``tos.rcl._base`` precedent), so ``from tos.ioc._base import
IndependentIdArtifact`` reads locally while the definition stays single-sourced in the core.

The one ioc-local addition is :class:`AllFalseConstructionAuthority` — an authority block
whose every declared boolean flag is forced ``false`` at construction. The all-false authority
*contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here (the rcl
``_base.py`` ``AllFalseAuthority`` / are ``AllFalseAggregateAuthority`` precedent, design #14
§0.4d) rather than imported from ``tos.rcl``: the single ``ioc -> rcl`` sibling edge (§0.4c)
exists **only** to REUSE the ``CapacityVector`` type for ``EconomicEffectEnvelope``, and keeping
the authority contract local keeps that edge single-purpose. ``construction != authority``: order
construction is non-authorizing (IOC-INV-011 line 197; ADR-002-020 §7 line 219 "The compiler
cannot approve, mutate capacity, issue authority, classify protection, choose permissive
admissibility, transmit, clear HALT, or re-arm") — any ``True`` flag makes the artifact
unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` other than the ``CapacityVector`` REUSE elsewhere (design #14 §0.3).
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
    "AllFalseConstructionAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseConstructionAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #14 §0.4d).

    The pure-model realization of ``construction != authority`` (IOC-INV-011 line 197; ADR-002-
    020 §7 line 219): order construction approves nothing, mutates no capacity, issues no
    authority, classifies no protection, chooses no admissibility, transmits nothing, clears no
    HALT, and re-arms nothing. Any ``True`` authority flag makes the artifact unconstructable.
    Subclasses declare the exact flag names for their artifact. Isomorphic to the rcl
    ``AllFalseAuthority`` / are ``AllFalseAggregateAuthority`` / capsule / evidence all-false
    blocks (authored locally-fresh, not imported — the ``ioc -> rcl`` edge is
    ``CapacityVector``-only, §0.4c/§0.4d).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators and
    could forge a ``True`` flag, so a consuming runtime still re-checks the invariant with
    :func:`~tos.ioc.predicates.construction_grants_no_authority` (defence in depth — never trust
    an un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseConstructionAuthority:
        """Reject construction if any authority flag is ``True`` (IOC-INV-011)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(construction != authority — IOC-INV-011; order construction cannot "
                    "approve, mutate capacity, issue authority, classify protection, choose "
                    "admissibility, transmit, clear HALT, or re-arm)"
                )
        return self
