"""egress-local base re-export shim + all-false egress authority effect (design #22 §2 / §3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from :mod:`tos.canonical`
(design #22 §3.1 — "재정의 금지"; **PROMOTE 0**: ``IndependentIdArtifact`` is already core from
design #6). The five digest-bound EGRESS citizens (``QuorumCommitCertificate`` /
``EgressRequestRecord`` / ``EgressGeneration`` / ``ActiveEgressPrincipalSet`` /
``ReplayObservation``) inherit :class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``):
the id is separately issued, so a same-id / different-bytes forged, re-issued, or replayed record
is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #22 §2.1/§5.5 —
EGRESS-EV-004/005). This module is a thin re-export shim (the ``tos.hag._base`` /
``tos.venue._base`` / ``tos.liveauth._base`` precedent), so ``from tos.egress._base import
IndependentIdArtifact`` reads locally while the definition stays single-sourced in core.

The one egress-local addition is :class:`AllFalseEgressAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction (EGRESS-INV-005/010; §4.3
"QCC-is-not-authority"). The all-false authority *contract* is **not** in ``tos.canonical``, so it
is authored **locally, fresh** here (the rcl ``AllFalseAuthority`` ``_base.py`` / liveauth
``LiveAuthorizationEffect`` ``_base.py:75`` / hag ``HumanAuthorityEffect`` precedent, design #22
§2.4) rather than imported from a sibling: egress imports **no** sibling (sibling edge 0, design
#22 §0.3/§3.4), and the flag names are egress-specific, so the all-false contract is re-expressed
with a note — exactly the codebase's REPLICATE-WITH-NOTE convention for pure authority contracts
(design #22 §2.4).

``QCC != authority``: EGRESS-INV-005/010 / §4.3 — a Quorum Commit Certificate / Egress Request /
Egress Generation / Active Egress Principal Set is **verified data, not permission**. Holding one
transmits nothing, creates no route, grants no credential, arms no generation, and re-arms nothing
(§8 line 231 "no authority outside the committed set"; §10 EGRESS-INV-010 "administrators cannot
create a broker-order mutation merely by exercising administrative access"). Any ``True`` flag makes
the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #22 §0.3).
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
    "AllFalseEgressAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseEgressAuthority(FrozenModel):
    """Authority effect of an egress artifact — every flag forced ``false`` (EGRESS-INV-005/010).

    The pure-model realization of ``QCC != authority`` (EGRESS-INV-005/010; ADR-002-013 §4.3 / §8
    line 231 / §10): a Quorum Commit Certificate / Egress Request Record / Egress Generation /
    Active Egress Principal Set (and any external-activity artifact, §6b) permits nothing at
    runtime — it transmits to no broker, creates no route, grants no credential, arms no egress
    generation, and re-arms nothing. Authority comes only from the positive §5 structural /
    coordinate predicates plus the owning +Security runtime — never from the mere existence /
    possession of a verified QCC (§10 EGRESS-INV-010 "Credential, route, deployment, consensus, and
    secret-store administrators cannot create a broker-order mutation merely by exercising
    administrative access"). Isomorphic to the rcl ``AllFalseAuthority`` / liveauth
    ``LiveAuthorizationEffect`` / hag ``HumanAuthorityEffect`` all-false blocks (authored
    locally-fresh, **not** imported — egress has sibling edge 0, design #22 §0.3/§2.4; the flag
    names are egress-specific). Any ``True`` authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth; the §5 predicates
    re-derive authority from positive proof and never read this block as a grant, §4.3).
    """

    permits_transmission: bool = False
    creates_route: bool = False
    grants_credential: bool = False
    arms_generation: bool = False
    re_arms: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseEgressAuthority:
        """Reject construction if any authority flag is ``True`` (EGRESS-INV-005/010; §4.3)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(QCC != authority — EGRESS-INV-005/010 / ADR-002-013 §4.3/§8/§10; a Quorum "
                    "Commit Certificate / Egress Request / Egress Generation / Active Egress "
                    "Principal Set cannot transmit to a broker, create a route, grant a "
                    "credential, arm an egress generation, or re-arm — it is verified data, not "
                    "permission)"
                )
        return self
