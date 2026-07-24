"""Authority-local base classes (Safety Authority design §2, §3.1, §4.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design §0.4a/§3.1 — "재정의 금지"). This module
adds only the authority-local pieces:

* :class:`AllFalseAuthority` — an authority block whose every declared boolean flag
  is forced ``false`` at construction (design §4.1 layer 2; ADR-002-003 §8.1 line
  257 "SHALL NOT directly transmit broker orders or mutate risk capacity"). A Safety
  Authority artifact (capability / epoch-transition / lease-ownership record) is a
  **non-transmitting datum**: any ``True`` authority flag makes it unconstructable
  (the full "no authority path anywhere" proof is EV-L2/L3 + Security; SA-EV-008/013).
  Isomorphic to the capsule ``SnapshotAuthority._all_authority_false``, the time /
  evidence / rcl / dsl all-false blocks — **authority-local, flag names differ**, so
  local re-expression is justified (design §3.3; NOT a PROMOTE — cf. the
  ``IndependentIdArtifact`` PROMOTE which has no per-package variation).
* :class:`AuthorityEffect` — the concrete all-false block carried by every authority
  artifact, with the five flags of design §4.1 layer 2.

``IndependentIdArtifact`` (design §2.1: capability / epoch-transition / lease-ownership
records are ledger citizens with an INDEPENDENT, service-assigned id, ``id != f(digest)``
— so a same-id / different-bytes forgery / replay stays representable and detectable via
``classify_record_pair``, §3.1) is re-exported from :mod:`tos.canonical` (design §0.4c
PROMOTE — beside ``IdDerivedArtifact``), so ``from tos.authority._base import
IndependentIdArtifact`` mirrors the rcl / dsl shim pattern.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no
``tos.rcl`` / ``tos.capsule`` / ``tos.evidence`` (design §0.3).
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
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "AuthorityEffect",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design §4.1).

    The pure-model realization of ``authority != enforcement`` (SA-INV-003; §8.1 line
    257; §1 line 17 "A Safety Authority instance may calculate or sign a decision,
    but an execution path may accept a permissive decision only when it can prove
    [6 things]"). Holding, signing, or computing a capability confers no runtime
    effect: any ``True`` authority flag makes the artifact unconstructable. Subclasses
    declare the exact flag names for their artifact. Isomorphic to the capsule /
    time / evidence / rcl / dsl all-false blocks (authority-local, §3.3).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (SA-INV-003)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(authority != enforcement — SA-INV-003; a capability grants no "
                    "runtime effect, only egress independent verification can, §1/§8.1)"
                )
        return self


class AuthorityEffect(AllFalseAuthority):
    """Runtime effect of a Safety Authority artifact — all five flags false (§4.1).

    Design §4.1 layer 2: no authority artifact is current authority by possession,
    transmits, mutates capacity, releases capacity, or re-arms. ``capacity`` is RCL's
    (only a committed RCL transition may mutate it — the capacity-side sibling), and
    egress is the final broker gate (only it can authorize transmission, §1 cond 6).
    Any ``True`` value raises :class:`ArtifactIntegrityError` (ADR-002-003 §8.1 line
    257; §16.3; SA-INV-011/013).
    """

    is_current_authority_by_possession: bool = False
    self_transmits: bool = False
    self_mutates_capacity: bool = False
    self_releases_capacity: bool = False
    self_rearms: bool = False
