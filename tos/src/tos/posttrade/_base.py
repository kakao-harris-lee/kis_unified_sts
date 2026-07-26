"""posttrade-local base re-export shim + all-false consequence (design #24 §0.4f/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #24 §3.1 — **PROMOTE 0**: every primitive this
package needs is already core). The four ``tos.posttrade`` digest-bound citizens — the
append-only, generation-immutable
:class:`~tos.posttrade.records.EconomicObligationRecord`,
:class:`~tos.posttrade.records.PostTradeFinalityProof`,
:class:`~tos.posttrade.records.StatementCoverageManifest`, and
:class:`~tos.posttrade.records.PostTradeBreakRecord` — are each an
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``; design #24 §0.4f), so

* a same **primary** id / different-bytes pair stays a detectable
  ``classify_record_pair`` ``CRITICAL_CONFLICT`` (obligation forgery / a contradictory
  obligation version), and
* a same **idempotency** key / different-bytes pair stays a detectable
  ``DIVERGENT_EMISSION`` (two different fills claiming one commit key)

— **two separate identity axes**, which ``id = f(digest)`` (the capsule
``IdDerivedArtifact``) would have made vacuous (design #24 §0.4f/§3.1). This module is a
thin re-export shim (the ``tos.nontrade._base`` / ``tos.replacement._base`` /
``tos.are._base`` precedent), so ``from tos.posttrade._base import IndependentIdArtifact``
reads locally while the definition stays single-sourced in core.

The one posttrade-local addition is :class:`AllFalsePostTradeConsequence` — a consequence
block whose every declared boolean flag is forced ``false`` at construction. The all-false
*contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here (the
rcl ``AllFalseAuthority`` / nontrade ``AllFalseNonTradeAuthority`` / are / afg / iap /
replacement precedent, design #24 §0.4f) rather than imported from a sibling:
``tos.posttrade`` keeps **sibling edge 0** (design #24 §0.4b), so there is no edge over
which to import one.

``finality proves the LEG, not the CONSEQUENCE`` — the most load-bearing safety property of
ADR-002-030. §10 line 312 verbatim: "``SATISFIED_PENDING_FINALITY`` is not final.
``FINALITY_PROVEN`` proves only the exact declared leg and proof class. ``CLOSED``
preserves immutable lineage and can be superseded by a later correction without destructive
overwrite. **No lifecycle state creates capacity release, available cash, legal title, or
permission**." §1 line 21: "The Risk Capacity Ledger remains the sole capacity mutation and
serialization authority ... an obligation compiler, Reconciliation Service, PTOL, position
or cash projection, statement processor, evidence service, recovery workflow, operator, or
finality proof SHALL NOT create, change, quarantine, transfer, remap, or release capacity."
§1 line 31 / PTF-INV-016: "PTOL, reconciliation, statement, evidence, dashboard, recovery,
and operator identities SHALL NOT hold a usable external-economic credential and route."
Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #24 §0.3).
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
    "AllFalsePostTradeConsequence",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalsePostTradeConsequence(FrozenModel):
    """Consequence of any post-trade label / record / proof — every flag false (§4.7).

    The pure-model realization of ``finality proves the LEG, not the CONSEQUENCE``
    (ADR-002-030 §10 line 312, §1 line 21, §1 line 31, §21 line 492): an obligation
    lifecycle state, an :class:`~tos.posttrade.records.EconomicObligationRecord`, a
    :class:`~tos.posttrade.records.PostTradeFinalityProof` (including one whose obligation
    sits at ``FINALITY_PROVEN``), a completeness bool, an
    :class:`~tos.posttrade.vocabulary.ObligationCommitOutcome`, or a
    :class:`~tos.posttrade.vocabulary.PostTradeDisposition` releases no capacity, makes no
    cash available, proves no legal title, grants no permission, and authorizes no
    transmission.

    The **five** declared flags are the §4.7 / §10 line 312 verbatim four (capacity
    release, available cash, legal title, permission) plus the §1 line 31 / PTF-INV-016
    egress seal (external economic transmission). Any ``True`` value makes the artifact
    unconstructable. Isomorphic to the rcl ``AllFalseAuthority`` / nontrade
    ``AllFalseNonTradeAuthority`` blocks (authored locally-fresh, **not** imported —
    ``tos.posttrade`` holds sibling edge 0, design #24 §0.4b/§0.4f).

    **The absence is stronger than the flag.** ``releases_capacity`` is declared ``False``
    so a forged ``True`` is rejected loudly; but there is additionally **no field and no
    predicate anywhere in this package that could perform a release, hold a credential, name
    a route, or send** (design #24 §4.4/§4.7-3, PTF-INV-008/016). A §7 property asserts
    those phantom names stay absent from every model, so the structural absence cannot be
    re-introduced by a later edit.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators
    and could forge a ``True`` flag, so a consuming runtime still re-checks the invariant
    with :func:`~tos.posttrade.predicates.post_trade_consequence_all_false` (defence in
    depth — never trust an un-validated block).
    """

    # --- §10 line 312 verbatim four ---
    releases_capacity: bool = False
    makes_cash_available: bool = False
    proves_legal_title: bool = False
    grants_permission: bool = False
    # --- §1 line 31 / PTF-INV-016 egress seal ---
    authorizes_transmission: bool = False

    @model_validator(mode="after")
    def _all_consequences_false(self) -> AllFalsePostTradeConsequence:
        """Reject construction if any consequence flag is ``True`` (§10 line 312)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(finality proves the LEG, not the CONSEQUENCE — ADR-002-030 §10 "
                    "line 312: no lifecycle state creates capacity release, available "
                    "cash, legal title, or permission)"
                )
        return self
