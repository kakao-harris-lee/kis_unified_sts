"""hag-local base re-export shim + all-false human-authority effect (design #20 §2 / §3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from
:mod:`tos.canonical` (design #20 §3.1 — "재정의 금지"; **PROMOTE 0건**:
``IndependentIdArtifact`` is already core from design #6). The eight digest-bound HAG
citizens (``HumanAuthorityPolicy`` / ``EffectivePrincipalGraph`` / ``HumanApprovalRequest``
/ ``HumanApprovalAttestation`` / ``HumanApprovalSet`` / ``ApprovalSetConsumptionRecord`` /
``HumanHaltCommand`` / ``HumanDelegationRecord``) inherit
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``): the id is separately
issued, so a same-id / different-bytes forged, re-issued, contradictory, or replayed record
is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #20 §2.1/§5.8 —
HAG-EV-002/004/012). This module is a thin re-export shim (the ``tos.venue._base`` /
``tos.liveauth._base`` precedent), so ``from tos.hag._base import IndependentIdArtifact``
reads locally while the definition stays single-sourced in core.

The one hag-local addition is :class:`HumanAuthorityEffect` — an authority block whose every
declared boolean flag is forced ``false`` at construction (HAG-INV-004; §4.3
"approval-is-not-authority"). The all-false authority *contract* is **not** in
``tos.canonical``, so it is authored **locally, fresh** here (the liveauth
``LiveAuthorizationEffect`` ``_base.py:75`` / iap ``ApprovalAuthorityEffect`` / venue
``VenueGateAuthorityEffect`` precedent, design #20 §2.4) rather than imported from a sibling:
hag imports **no** sibling (sibling edge 0, design #20 §0.3/§0.4c), and the flag names are
human-authority-specific, so the all-false contract is re-expressed with a note — exactly the
codebase's REPLICATE-WITH-NOTE convention for pure authority contracts (design #20 §2.4).

``approval != authority``: HAG-INV-004 / §4.3 — a Human Approval Request / Attestation / Set /
Consumption / Halt Command / Delegation is a **safety datum, not permission**. It cannot mutate
capacity, activate configuration, issue Live Authorization, clear a deny latch, transmit to a
broker, or re-arm (§5.6 line — "not Live Authorization and grants no broker or capacity
authority"). Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling
``tos.*`` (design #20 §0.3).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "HumanAuthorityEffect",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class HumanAuthorityEffect(FrozenModel):
    """Authority effect of a human-authority artifact — every flag forced ``false`` (HAG-INV-004).

    The pure-model realization of ``approval != authority`` (HAG-INV-004; ADR-002-015 §4.3 /
    §5.6): a Human Approval Request / Attestation / Set / Consumption Record / Halt Command /
    Delegation approves nothing at runtime — it mutates no capacity, activates no configuration,
    issues no Live Authorization, clears no deny latch, transmits to no broker, and re-arms
    nothing. Authority comes only from positive proof downstream (a satisfied human quorum plus a
    governed downstream issuer, §4.3) — never from the mere existence of an approval datum
    (§10 line 314 "Silence, timeout, absence, emoji, chat acknowledgement ... is not approval").
    Isomorphic to the liveauth ``LiveAuthorizationEffect`` / iap ``ApprovalAuthorityEffect`` /
    venue ``VenueGateAuthorityEffect`` all-false blocks (authored locally-fresh, **not**
    imported — hag has sibling edge 0, design #20 §0.3/§0.4c/§2.4; the flag names are
    human-authority-specific). Any ``True`` authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime re-checks the invariant with
    :func:`~tos.hag.predicates.human_authority_effect_separated` (defence in depth — never trust
    an un-validated block; §4.3).
    """

    mutates_capacity: bool = False
    activates_configuration: bool = False
    issues_live_authorization: bool = False
    clears_deny_latch: bool = False
    transmits_to_broker: bool = False
    re_arms: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> HumanAuthorityEffect:
        """Reject construction if any authority flag is ``True`` (HAG-INV-004; §4.3)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(approval != authority — HAG-INV-004 / ADR-002-015 §4.3/§5.6; a human "
                    "approval / attestation / set / halt / delegation cannot mutate capacity, "
                    "activate configuration, issue Live Authorization, clear a deny latch, "
                    "transmit to a broker, or re-arm — it is a safety datum, not permission)"
                )
        return self
