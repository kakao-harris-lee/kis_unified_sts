"""wdr-local base re-export shim + all-false deviation authority effect (design #26 §2/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from :mod:`tos.canonical`
(design #26 §3.1 — "재정의 금지"; **PROMOTE 0**: ``IndependentIdArtifact`` is already core from
design #6). The five digest-bound WDR citizens (``SafetyDeviationPolicy`` /
``SafetyDeviationRequest`` / ``SafetyDeviationDecision`` / ``ResidualRiskAcceptanceRecord`` /
``ActiveDeviationSet`` — gate-status line 793 "the **five** deviation templates") inherit
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``): the id is separately issued, so a
same-id / different-covered-bytes forged, re-issued, or replayed record is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #26 §2.1/§3.1 — WDR-EV-001/012). This module
is a thin re-export shim (the ``tos.rlp._base`` / ``tos.cur._base`` / ``tos.egress._base``
precedent), so ``from tos.wdr._base import IndependentIdArtifact`` reads locally while the definition
stays single-sourced in core.

The one wdr-local addition is :class:`AllFalseDeviationAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction (WDR-INV-001; §7 "Policy, request, decision,
acceptance, review, ticket, evidence, and active-set artifacts create **no** capacity, protection,
Safety Authority, Live Authorization, capability, transmission, HALT clear, production scope, or
re-arm authority" + §1 "broker permission, protective classification"). The all-false authority
*contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh** here (the rcl
``AllFalseAuthority`` / egress ``AllFalseEgressAuthority`` / cur ``AllFalseCurrentnessAuthority`` / rlp
``AllFalseTrialAuthority`` precedent, design #26 §2.4/§3.3) rather than imported from a sibling: wdr
imports **no** sibling (sibling edge 0, design #26 §0.3/§3.4), and the flag names are
deviation-specific, so the all-false contract is re-expressed with a note — exactly the codebase's
REPLICATE-WITH-NOTE convention for pure authority contracts.

``deviation artifact != authority``: WDR-INV-001 line 148 — a Safety Deviation Policy / Request /
Decision / Residual-Risk Acceptance Record / Active Deviation Set is **governed content / a
non-authorizing decision, not permission**. Holding one creates no capacity, protection, Safety
Authority, Live Authorization, capability, transmission, HALT clear, production scope, re-arm, broker
permission, or protective classification. Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling ``tos.*``
(design #26 §0.3).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "AllFalseDeviationAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseDeviationAuthority(FrozenModel):
    """Authority effect of a deviation artifact — every flag forced ``false`` (WDR-INV-001; §7).

    The pure-model realization of ``deviation artifact != authority`` (WDR-INV-001; ADR-002-026 §7): a
    Safety Deviation Policy / Request / Decision / Residual-Risk Acceptance Record / Active Deviation
    Set permits nothing at runtime — it creates / mutates / releases no capacity, classifies / creates
    no protection, issues no Live Authorization / capability, transmits nothing, clears no HALT,
    creates no production scope, re-arms nothing, and grants no broker permission. WDR-INV-001 line 148
    verbatim: "Policy, request, decision, acceptance, review, ticket, evidence, and active-set
    artifacts create **no** capacity, protection, Safety Authority, Live Authorization, capability,
    transmission, HALT clear, production scope, or re-arm authority" (+ §1 line 21 "broker permission,
    protective classification"). Authority comes only from the positive §5/§6 structural / polarity
    predicates plus the owning +Security / +Broker runtime and the human governance steps — never from
    the mere existence / possession of a deviation artifact. Isomorphic to the rcl ``AllFalseAuthority``
    / egress ``AllFalseEgressAuthority`` / cur ``AllFalseCurrentnessAuthority`` / rlp
    ``AllFalseTrialAuthority`` all-false blocks (authored locally-fresh, **not** imported — wdr has
    sibling edge 0, design #26 §0.3/§2.4; the flag names are deviation-specific). Any ``True`` authority
    flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth; the §5/§6 predicates
    re-derive authority from positive proof and never read this block as a grant, §6.2).
    """

    creates_capacity: bool = False
    creates_protection: bool = False
    creates_safety_authority: bool = False
    issues_live_authorization: bool = False
    creates_capability: bool = False
    transmits: bool = False
    clears_halt: bool = False
    creates_production_scope: bool = False
    re_arms: bool = False
    grants_broker_permission: bool = False
    classifies_protection: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseDeviationAuthority:
        """Reject construction if any authority flag is ``True`` (WDR-INV-001; §7)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(deviation artifact != authority — WDR-INV-001 / ADR-002-026 §7; a Safety "
                    "Deviation Policy / Request / Decision / Residual-Risk Acceptance Record / "
                    "Active Deviation Set cannot create or release capacity, classify or create "
                    "protection, create Safety Authority, issue Live Authorization or capability, "
                    "transmit, clear a HALT, create production scope, re-arm, or grant broker "
                    "permission — it is governed content / a non-authorizing decision, not "
                    "permission)"
                )
        return self
