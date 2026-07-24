"""Live-Authorization-local base classes (design §2, §4.1; ADR-002-007 §4.1/§8.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design §0.4d/§3.1 — "재정의 금지"; **PROMOTE 0건**:
``IndependentIdArtifact`` is already core from design #6). This module adds only the
liveauth-local pieces and re-exports the canonical substrate as a thin shim (the
``tos.authority._base`` / ``tos.rcl._base`` / ``tos.dsl._base`` pattern — no sibling
import edge):

* :class:`AllFalseAuthority` — an authority block whose every declared boolean flag is
  forced ``false`` at construction (design §4.1 layer 2; ADR-002-007 §8.1 line 242-244
  "``ACTIVE`` … is not inferred from the artifact merely being issued"). A Live
  Authorization / transition / approval artifact is a **non-transmitting datum**: any
  ``True`` flag makes it unconstructable (the full "no authority path anywhere" proof is
  EV-L3 + Security; REARM-EV-001/004/010 not-Phase-1). Isomorphic to the capsule
  ``SnapshotAuthority._all_authority_false`` and the authority / time / evidence / rcl /
  dsl all-false blocks — **liveauth-local, flag names differ**, so local re-expression is
  justified (design §3.3/§0.4f; NOT a PROMOTE).
* :class:`LiveAuthorizationEffect` — the concrete all-false block carried by every Live
  Authorization ledger citizen, with the six flags of design §4.1 layer 2.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no
``tos.rcl`` / ``tos.capsule`` / ``tos.evidence`` / ``tos.dsl`` (design §0.3).
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
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "LiveAuthorizationEffect",
]


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design §4.1).

    The pure-model realization of ``authorization != enforcement`` (ADR-002-007 §8.1
    line 242-244; §1 line 17 "The default operational state … SHALL be non-live"):
    holding, issuing, or signing a Live Authorization confers no runtime effect. Any
    ``True`` authority flag makes the artifact unconstructable. Subclasses declare the
    exact flag names for their artifact. Isomorphic to the authority / capsule / time /
    evidence / rcl / dsl all-false blocks (liveauth-local, §3.3).
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (ADR-002-007 §8.1)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(authorization != enforcement — ADR-002-007 §1/§8.1; issuing or "
                    "holding a Live Authorization grants no runtime effect, only final "
                    "broker egress independent verification can, §16)"
                )
        return self


class LiveAuthorizationEffect(AllFalseAuthority):
    """Runtime effect of a Live Authorization artifact — all six flags false (§4.1).

    Design §4.1 layer 2: no Live Authorization artifact is live by possession,
    transmits, arms itself, activates itself, expands its own scope, or revives itself.
    Transmission is the final broker egress gate (only it can authorize a send, §16;
    REARM-EV-010 not-Phase-1); re-arm issues a **new** authorization identity (§8.3),
    it does not self-revive. Any ``True`` value raises :class:`ArtifactIntegrityError`
    (ADR-002-007 §8.1 line 242-244; §1 line 38; §8.3 non-revival).
    """

    is_live_by_possession: bool = False
    self_transmits: bool = False
    self_arms: bool = False
    self_activates: bool = False
    self_expands_scope: bool = False
    self_revives: bool = False
