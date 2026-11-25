"""egress-local base re-export shim + all-false egress authority effect (design #22 §2 / §3.1)."""

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
    """Authority effect of an egress artifact — every flag forced ``false`` (EGRESS-INV-005/010)."""

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
