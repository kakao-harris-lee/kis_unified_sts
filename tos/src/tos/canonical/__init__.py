"""tos.canonical — shared digest-binding substrate (design #4 §0.4/§3.1 PROMOTE)."""

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
    CanonicalDecimal,
    CanonicalizationScheme,
    DigestFactory,
    EVL1ProvisionalCanonicalizer,
    get_scheme,
    register_scheme,
)
from tos.canonical.record_pair import RecordPairKind, classify_record_pair

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "IdDerivedArtifact",
    "IndependentIdArtifact",
    "FrozenModel",
    "derive_id",
    "EV_L1_PROVISIONAL_VERSION",
    "CanonicalDecimal",
    "CanonicalizationScheme",
    "DigestFactory",
    "EVL1ProvisionalCanonicalizer",
    "get_scheme",
    "register_scheme",
    "RecordPairKind",
    "classify_record_pair",
]
