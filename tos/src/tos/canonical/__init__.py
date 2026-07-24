"""tos.canonical — shared digest-binding substrate (design #4 §0.4/§3.1 PROMOTE).

The canonicalization + digest-binding core promoted out of ``tos.capsule`` so
both ``tos.capsule`` and ``tos.evidence`` depend on it in one direction, with no
capsule <-> evidence import (design #4 §3.1 layering). ``tos.capsule`` re-exports
these symbols through thin shims, so existing import paths are unchanged.

Two artifact layers (design #4 §3.1 (b)); the base plus its two id-strategy
subclasses now all live here (design #6 §0.4c PROMOTE):

* :class:`DigestBoundArtifact` — digest verification only; **no** id derivation
  (evidence records take an independent, non-``f(digest)`` id).
* :class:`IdDerivedArtifact` — adds ``id = derive_id(prefix, digest)`` (capsule /
  snapshot content-addressed artifacts).
* :class:`IndependentIdArtifact` — an INDEPENDENT injected id (``id != f(digest)``)
  for ledger citizens whose same-id/different-bytes conflict must stay detectable
  (``tos.rcl`` / ``tos.dsl`` / ``tos.authority``; ``tos.rcl._base`` / ``tos.dsl._base``
  re-export it as thin shims).

Pure package: ``pydantic`` + stdlib only (design §0.3).
"""

from __future__ import annotations

from tos.canonical._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IdDerivedArtifact,
    IndependentIdArtifact,
    derive_id,
)
from tos.canonical.canonicalization import (
    EV_L1_PROVISIONAL_VERSION,
    CanonicalizationScheme,
    DigestFactory,
    EVL1ProvisionalCanonicalizer,
    get_scheme,
    register_scheme,
)
from tos.canonical.record_pair import RecordPairKind, classify_record_pair

__all__ = [
    # base substrate
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "IdDerivedArtifact",
    "IndependentIdArtifact",
    "FrozenModel",
    "derive_id",
    # canonicalization
    "EV_L1_PROVISIONAL_VERSION",
    "CanonicalizationScheme",
    "DigestFactory",
    "EVL1ProvisionalCanonicalizer",
    "get_scheme",
    "register_scheme",
    # record-pair classifier (promoted; RCL design §0.4b/§3.1c)
    "RecordPairKind",
    "classify_record_pair",
]
