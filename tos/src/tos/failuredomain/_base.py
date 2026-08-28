"""failuredomain-local base re-export shim + all-false authority (design #27 §3.1/§2.2).

``FrozenModel`` and ``ArtifactIntegrityError`` are REUSED verbatim from
:mod:`tos.canonical` (design #27 §3.1 — **PROMOTE 0**). ``tos.failuredomain`` authors **no**
new base class and takes **no** digest-bound citizen: **Q1 확정** (design #27 §0.4b/§3.1) —
:class:`~tos.failuredomain.records.FailureDomainAllocationEntry` and
:class:`~tos.failuredomain.records.IsolationClaim` are **document-level plain frozen record
shapes**, not runtime artifacts. There is no Phase-1 digest consumer and no forgery-detection
path for a matrix row, so ``DigestBoundArtifact`` / ``IndependentIdArtifact`` /
``IdDerivedArtifact`` are **deliberately not adopted** (matrix identity, digest binding, and
registry are deferred to the deployment-profile approval and the evidence layer, design #27
§0.2/§3.1). This module is a thin re-export shim (the ``tos.recon._base`` /
``tos.nontrade._base`` / ``tos.rcl._base`` precedent) so ``from tos.failuredomain._base import
FrozenModel`` reads locally while the definition stays single-sourced in the core.

The one failuredomain-local addition is :class:`AllFalseFailureDomainAuthority` — an authority
block whose every declared boolean flag is forced ``false`` at construction. The all-false
authority *contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here
(the rcl ``AllFalseAuthority`` / are ``AllFalseAggregateAuthority`` / nontrade
``AllFalseNonTradeAuthority`` precedent, design #27 §2.2): ``tos.failuredomain`` keeps
**sibling edge 0** (design #27 §0.3/§3.1), so there is no edge over which to import one.

``isolation coordinate != authority``: ADR-002-009 §1 line 15 verbatim "**Separate processes,
services, containers, nodes, or names do not by themselves prove isolation.**" §1 line 32
verbatim: an isolation property that cannot be positively established "SHALL NOT be converted
into permission by redundancy count, operator confidence, a healthy dashboard, replay
capability, or an audit trail." §4.3 line 92 verbatim "**A cell boundary is not proven merely
by labels or namespaces.**" A matrix row, a Safety Cell scope, an ``IsolationKind``, or an
``IsolationClaim`` therefore grants nothing, proves nothing, enforces nothing, and transmits
nothing — any ``True`` flag makes the artifact unconstructable (design #27 §2.2, the design #4
§4.6 ``_all_authority_false`` spirit).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*``, no ``tos.ordering`` (design #27 §0.3 — the matrix carries no causal append-only
order).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel

__all__ = [
    "AllFalseFailureDomainAuthority",
    "ArtifactIntegrityError",
    "FrozenModel",
]


class AllFalseFailureDomainAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #27 §2.2).

    The pure-model realization of ``isolation coordinate != authority`` (ADR-002-009 §1 line
    15 / line 32, §4.3 line 92): a failure-domain taxonomy value, a Safety Cell scope, an
    :class:`~tos.failuredomain.vocabulary.IsolationKind`, an
    :class:`~tos.failuredomain.vocabulary.IsolationClaimStatus`, a matrix row, or an
    isolation claim grants no authority, releases no capacity, transmits nothing, establishes
    no permission, proves no isolation, and enforces no containment. Any ``True`` authority
    flag makes the artifact unconstructable. Subclasses declare the exact flag names for
    their artifact. Isomorphic to the rcl ``RclAuthorityEffect`` / are
    ``AggregateRiskAuthorityEffect`` / nontrade ``AllFalseNonTradeAuthority`` all-false blocks
    (authored locally-fresh, **not** imported — ``tos.failuredomain`` holds sibling edge 0,
    design #27 §0.3).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators and
    could forge a ``True`` flag, so a consuming runtime still re-checks the invariant on the
    block itself (defence in depth — never trust an un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseFailureDomainAuthority:
        """Reject construction if any authority flag is ``True`` (ADR §1 line 15/32, §4.3)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(isolation coordinate != authority — ADR-002-009 §1 line 15: separate "
                    "processes, services, containers, nodes, or names do not by themselves "
                    "prove isolation; §1 line 32: an unestablished isolation property SHALL "
                    "NOT be converted into permission)"
                )
        return self
