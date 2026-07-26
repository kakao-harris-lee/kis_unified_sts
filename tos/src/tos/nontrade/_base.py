"""nontrade-local base re-export shim + all-false authority (design #21 §0.4f/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #21 §3.1 — **PROMOTE 0**: every primitive this
package needs is already core). The two ``tos.nontrade`` digest-bound citizens — the
append-only, generation-immutable :class:`~tos.nontrade.records.NonTradeEventRecord` and
:class:`~tos.nontrade.records.CorrectionReversalRecord` — are each an
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``; design #21 §0.4f), so

* a same **primary** id / different-bytes pair stays a detectable
  ``classify_record_pair`` ``CRITICAL_CONFLICT`` (record forgery / contradictory event),
  and
* a same **idempotency** key / different-bytes pair stays a detectable
  ``DIVERGENT_EMISSION`` (two different corrections claiming one key)

— **two separate identity axes**, which ``id = f(digest)`` (the capsule
``IdDerivedArtifact``) would have made vacuous (design #21 §0.4f/§2.2-8). This module is a
thin re-export shim (the ``tos.replacement._base`` / ``tos.are._base`` / ``tos.rcl._base``
precedent), so ``from tos.nontrade._base import IndependentIdArtifact`` reads locally while
the definition stays single-sourced in core.

The one nontrade-local addition is :class:`AllFalseNonTradeAuthority` — an authority block
whose every declared boolean flag is forced ``false`` at construction. The all-false
authority *contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh**
here (the rcl ``AllFalseAuthority`` / are ``AllFalseAggregateAuthority`` / afg / iap /
replacement precedent, design #21 §0.4f) rather than imported from a sibling:
``tos.nontrade`` keeps **sibling edge 0** (design #21 §0.4b), so there is no edge over
which to import one.

``label != authority``: ADR-002-010 §6 line 144 verbatim "**No workflow state by itself
releases capacity, closes an instrument, proves final quantity, or grants authority.**"
§10 line 217 "Only the Risk Capacity Ledger may mutate capacity. The event processor ...
may propose a remap but SHALL NOT update capacity independently." §15 line 299 "An
operator selection, UI action, or reference-data flag SHALL NOT itself transmit an
instruction." §1 line 15: a non-trade event "SHALL NOT be fabricated as fills, silently
folded into position corrections, or treated as harmless reference-data changes." Any
``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #21 §0.3).
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
    "AllFalseNonTradeAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseNonTradeAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #21 §0.4f).

    The pure-model realization of ``label != authority`` (ADR-002-010 §6 line 144, §10
    line 217, §15 line 299, §1 line 15): a non-trade workflow label, an event record, a
    completeness bool, a :class:`~tos.nontrade.vocabulary.NonTradeDisposition`, or a
    :class:`~tos.nontrade.vocabulary.CorrectionReversalOutcome` releases no capacity,
    closes no instrument, proves no final quantity, grants no authority, transmits
    nothing, mutates no capacity, issues no admissibility, and fabricates no fill. Any
    ``True`` authority flag makes the artifact unconstructable. Subclasses declare the
    exact flag names for their artifact. Isomorphic to the rcl ``RclAuthorityEffect`` /
    are ``AggregateRiskAuthorityEffect`` / replacement ``ReplacementAuthorityEffect``
    all-false blocks (authored locally-fresh, **not** imported — ``tos.nontrade`` holds
    sibling edge 0, design #21 §0.4b/§0.4f).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators
    and could forge a ``True`` flag, so a consuming runtime still re-checks the invariant
    with :func:`~tos.nontrade.predicates.nontrade_authority_effect_all_false` (defence in
    depth — never trust an un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseNonTradeAuthority:
        """Reject construction if any authority flag is ``True`` (§6 line 144)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(label != authority — ADR-002-010 §6 line 144: no workflow state by "
                    "itself releases capacity, closes an instrument, proves final "
                    "quantity, or grants authority)"
                )
        return self
