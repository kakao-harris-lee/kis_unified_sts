"""are-local base re-export shim + all-false authority base (design #13 §0.4d).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #13 §3.1 — "재정의 금지"). ``tos.are`` authors
**no** new digest-binding base: its four digest-bound citizens — the append-only,
generation-immutable ``AggregateRiskPolicy`` / ``AggregateRiskStateSnapshot`` /
``AdverseScenarioSet`` / ``AggregateRiskDecision`` — are each an
:class:`~tos.canonical.IndependentIdArtifact` (governance / evaluation-assigned identity,
``id != f(digest)``, so a same-id / different-bytes re-issuance / forged / contradictory
decision stays a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``; design #13
§2.1/§3.1). This module is a thin re-export shim (the ``tos.spg._base`` /
``tos.rcl._base`` precedent), so ``from tos.are._base import IndependentIdArtifact`` reads
locally while the definition stays single-sourced in the core.

The one are-local addition is :class:`AllFalseAggregateAuthority` — an authority block
whose every declared boolean flag is forced ``false`` at construction. The all-false
authority *contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh**
here (the rcl ``_base.py`` ``AllFalseAuthority`` precedent, design #13 §0.4d) rather than
imported from ``tos.rcl``: the single ``are -> rcl`` sibling edge (§0.4c) exists **only** to
REUSE the ``CapacityVector`` type for the final ``AdverseIncrement[s,d]``, and keeping the
authority contract local keeps that edge single-purpose. ``capacity != authority``: a GRANT
/ decision / snapshot is a non-authoritative representation (ARE-INV-009 line 185; ADR §1
line 17 "A ``GRANT`` is not capacity, Live Authorization, a Transmission Capability, or
broker permission") — any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` other than the ``CapacityVector`` REUSE elsewhere (design #13 §0.3).
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
    "AllFalseAggregateAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseAggregateAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #13 §0.4d).

    The pure-model realization of ``capacity != authority`` (ARE-INV-009 line 185; ADR-002-021
    §1 line 17, §7 line 217 "Evaluator ... SHALL NOT mutate capacity"): a GRANT / decision /
    snapshot grants no authority — it creates no capacity, permits no transmission, issues no
    Live Authorization, obtains no broker permission, and re-arms nothing. Any ``True``
    authority flag makes the artifact unconstructable. Subclasses declare the exact flag names
    for their artifact. Isomorphic to the rcl ``AllFalseAuthority`` / capsule / evidence
    all-false blocks (authored locally-fresh, not imported — the ``are -> rcl`` edge is
    ``CapacityVector``-only, §0.4c/§0.4d).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators and
    could forge a ``True`` flag, so a consuming runtime still re-checks the invariant with
    :func:`~tos.are.predicates.grants_no_authority` (defence in depth — never trust an
    un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAggregateAuthority:
        """Reject construction if any authority flag is ``True`` (ARE-INV-009)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(capacity != authority — ARE-INV-009; a GRANT is not capacity, "
                    "Live Authorization, a Transmission Capability, or broker permission)"
                )
        return self
