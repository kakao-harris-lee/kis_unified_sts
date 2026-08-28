"""afg-local base re-export shim + all-false governor authority (design #16 §0.4e).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #16 §3.1 — no new digest-binding base). The
five ``tos.afg`` digest-bound citizens — the append-only, generation-immutable
``ActionFlowPolicy`` / ``ActionFlowStateSnapshot`` / ``ActionFlowDecision`` /
``ActionFlowPermit`` — are each an :class:`~tos.canonical.IndependentIdArtifact`
(governance / evaluation / commitment-assigned identity, ``id != f(digest)``, so a
same-id / different-bytes re-issuance, forged decision, contradictory decision, or
double-spend permit stays a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``;
design #16 §2.1/§3.1/§0.4e). This module is a thin re-export shim (the ``tos.are._base``
/ ``tos.spg._base`` / ``tos.rcl._base`` precedent), so ``from tos.afg._base import
IndependentIdArtifact`` reads locally while the definition stays single-sourced in core.

The one afg-local addition is :class:`AllFalseActionFlowAuthority` — an authority block
whose every declared boolean flag is forced ``false`` at construction. The all-false
authority *contract* is **not** in ``tos.canonical``, so it is authored **locally,
fresh** here (the rcl ``_base.py`` ``AllFalseAuthority`` / are ``AllFalseAggregate
Authority`` precedent, design #16 §0.4e) rather than imported from ``tos.rcl``: the
single ``afg -> rcl`` sibling edge (§0.4c) exists **only** to REUSE the
``CapacityVector`` type + ``aggregate_usage`` / ``effective_limit`` arithmetic, and
keeping the authority contract local keeps that edge single-purpose.

``decision != authority``: ADR-002-022 §1 line 17 verbatim "A ``GRANT`` is not capacity
or permission to send"; §5.5 line 129 "The permit ... is **not** Live Authorization, a
Transmission Capability, broker permission"; §7 line 220 "Governor SHALL NOT mutate a
budget, issue authority, or transmit"; §7 line 229 "The Action Flow Governor SHALL NOT
hold a live broker credential, signer, session, route, or endpoint capability"
(AFG-INV-011). Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` other than the ``CapacityVector`` REUSE elsewhere (design #16 §0.3).
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
    "AllFalseActionFlowAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseActionFlowAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #16 §0.4e).

    The pure-model realization of ``decision != authority`` (AFG-INV-011; ADR-002-022 §1
    line 17, §7 line 220/229): an Action Flow Governor decision / ``GRANT`` / permit /
    snapshot creates no capacity, mutates no budget, issues no authority, permits no
    transmission, holds no broker credential, and re-arms nothing. Any ``True`` authority
    flag makes the artifact unconstructable. Subclasses declare the exact flag names for
    their artifact. Isomorphic to the rcl ``RclAuthorityEffect`` / are
    ``AggregateRiskAuthorityEffect`` all-false blocks (authored locally-fresh, **not**
    imported — the ``afg -> rcl`` edge is ``CapacityVector``-only, §0.4c/§0.4e).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators
    and could forge a ``True`` flag, so a consuming runtime still re-checks the invariant
    with :func:`~tos.afg.predicates.governor_grants_no_authority` (defence in depth —
    never trust an un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseActionFlowAuthority:
        """Reject construction if any authority flag is ``True`` (AFG-INV-011)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(decision != authority — AFG-INV-011; a GRANT is not capacity or "
                    "permission to send, and a permit is not a Transmission Capability)"
                )
        return self
