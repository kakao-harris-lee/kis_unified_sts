"""iap-local base re-export shim + all-false approval-authority base (design #15 §2.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #15 §3.1 — "재정의 금지"). ``tos.iap`` authors
**no** new digest-binding base: its four digest-bound citizens — the append-only,
generation-immutable ``TradingApprovalPolicy`` / ``ProposalApprovalRequest`` /
``IndependentApprovalDecision`` / ``ApprovalConsumptionRecord`` — are each an
:class:`~tos.canonical.IndependentIdArtifact` (governance / issuance-assigned identity,
``id != f(digest)``, so a same-id / different-bytes forged / re-issued request / decision /
consumption record stays a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``; design
#15 §2.1/§3.1/§0.4d). This module is a thin re-export shim (the ``tos.ioc._base`` /
``tos.are._base`` precedent), so ``from tos.iap._base import IndependentIdArtifact`` reads
locally while the definition stays single-sourced in the core.

The one iap-local addition is :class:`AllFalseApprovalAuthority` — an authority block whose
every declared boolean flag is forced ``false`` at construction. The all-false authority
*contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here (the ioc
``AllFalseConstructionAuthority`` / rcl ``AllFalseAuthority`` / are ``AllFalseAggregateAuthority``
precedent, design #15 §2.1). Unlike ioc — whose single ``ioc -> rcl`` sibling edge exists to
REUSE ``CapacityVector`` (design #14 §0.4c) — ``tos.iap`` has **sibling edge 0** (design #15
§0.4b/§0.4c): it imports only ``tos.canonical`` + ``tos.ordering``, so authoring the authority
contract locally is the *only* option, not a choice to keep an edge single-purpose.
``approval != authority``: Independent Approval is a non-authorizing business gate (IAP-INV-005
line 150; ADR-002-023 §7 "Approval cannot mutate capacity, create headroom, issue authority,
classify protection, transmit, clear HALT, or re-arm") — any ``True`` flag makes the artifact
unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #15 §0.3 — sibling edge 0).
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
    "AllFalseApprovalAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseApprovalAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #15 §2.1 / §7).

    The pure-model realization of ``approval != authority`` (IAP-INV-005 line 150; ADR-002-023
    §7): Independent Approval approves no capacity mutation, creates no headroom, issues no
    authority, classifies no protection, transmits nothing, clears no HALT, and re-arms nothing.
    ``APPROVE`` is a non-authorizing business gate — it is *not* equivalent to
    ``AUTHORIZED_FOR_CAPACITY``, capacity commitment, Live Authorization, capability issuance, or
    transmission (§11 line 294). Any ``True`` authority flag makes the artifact unconstructable.
    Subclasses declare the exact flag names for their artifact. Isomorphic to the ioc
    ``AllFalseConstructionAuthority`` / rcl ``AllFalseAuthority`` / are ``AllFalseAggregateAuthority``
    all-false blocks (authored locally-fresh, not imported — sibling edge 0, §0.4b/§0.4c).

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators and
    could forge a ``True`` flag, so a consuming runtime still re-checks the invariant with
    :func:`~tos.iap.predicates.approval_grants_no_authority` (defence in depth — never trust an
    un-validated block).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseApprovalAuthority:
        """Reject construction if any authority flag is ``True`` (IAP-INV-005 line 150)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(approval != authority — IAP-INV-005; Independent Approval cannot "
                    "mutate capacity, create headroom, issue authority, classify protection, "
                    "transmit, clear HALT, or re-arm)"
                )
        return self
