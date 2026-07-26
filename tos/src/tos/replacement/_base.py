"""replacement-local base re-export shim + all-false authority (design #18 §0.4e).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #18 §3.1 — **PROMOTE 0**: every primitive
this package needs is already core). The two ``tos.replacement`` digest-bound citizens
— the append-only, generation-immutable ``ReplacementAuthorization`` and
``ReplacementWorkflowRecord`` — are each an
:class:`~tos.canonical.IndependentIdArtifact` (governance / workflow-assigned identity,
``id != f(digest)``), so a same-id / different-bytes re-issuance, forged authorization,
contradictory authorization, or double-commit workflow stays a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #18 §2.1/§3.1/§0.4e). This module
is a thin re-export shim (the ``tos.afg._base`` / ``tos.are._base`` / ``tos.rcl._base``
precedent), so ``from tos.replacement._base import IndependentIdArtifact`` reads locally
while the definition stays single-sourced in core.

The one replacement-local addition is :class:`AllFalseReplacementAuthority` — an
authority block whose every declared boolean flag is forced ``false`` at construction.
The all-false authority *contract* is **not** in ``tos.canonical``, so it is authored
**locally, fresh** here (the rcl ``AllFalseAuthority`` / are ``AllFalseAggregate
Authority`` / afg ``AllFalseActionFlowAuthority`` precedent, design #18 §0.4e) rather
than imported from a sibling: ``tos.replacement`` keeps **sibling edge 0** (design #18
§0.4b/§0.4c), so there is no edge over which to import one.

``label != authority``: ADR-002-011 §5 line 137 verbatim "No lifecycle label by itself
authorizes capacity release or removal of protection"; §5 line 139 "No lifecycle label
or 'protective' classification proves that cancel, amend, replace, reduce-only, or new
protection is executable"; §9 line 245 "Workflow completion, timeout, authority expiry,
cancel ACK, or local terminal state is insufficient". Any ``True`` flag makes the
artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #18 §0.3).
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
    "AllFalseReplacementAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseReplacementAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #18 §0.4e).

    The pure-model realization of ``label != authority`` (ADR-002-011 §5 line 137/139,
    §9 line 245, §1 line 21): a replacement workflow label, an authorization record, a
    completeness bool, or a :class:`~tos.replacement.vocabulary.ReplacementOutcome`
    releases no capacity, removes no protection, transmits nothing, issues no authority,
    holds no broker credential, overrides no Cancellation Arbiter, and declares no
    completion. Any ``True`` authority flag makes the artifact unconstructable.
    Subclasses declare the exact flag names for their artifact. Isomorphic to the rcl
    ``RclAuthorityEffect`` / are ``AggregateRiskAuthorityEffect`` / afg
    ``ActionFlowGovernorEffect`` all-false blocks (authored locally-fresh, **not**
    imported — ``tos.replacement`` holds sibling edge 0, design #18 §0.4b/§0.4e).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips
    validators and could forge a ``True`` flag, so a consuming runtime still re-checks
    the invariant with
    :func:`~tos.replacement.state.workflow_label_grants_nothing` (defence in depth —
    never trust an un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseReplacementAuthority:
        """Reject construction if any authority flag is ``True`` (§5 line 137)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(label != authority — ADR-002-011 §5 line 137: no lifecycle label "
                    "by itself authorizes capacity release or removal of protection)"
                )
        return self
