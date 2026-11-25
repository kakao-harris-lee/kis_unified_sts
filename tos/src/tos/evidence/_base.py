"""Evidence-local base classes (design #4 §2, §3.1, §4.6)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
)


class AllFalseFlags(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design §4.6)."""

    @model_validator(mode="after")
    def _all_false(self) -> AllFalseFlags:
        """Reject construction if any authority flag is ``True`` (ERI-INV-001/014)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(evidence is not authority — ERI-INV-001/014)"
                )
        return self


class EvidenceArtifact(DigestBoundArtifact):
    """Digest-bound evidence artifact with an INDEPENDENT (non-derived) id (§3.1)."""

    _ID_FIELD: ClassVar[str]

    @model_validator(mode="after")
    def _require_independent_id_when_issued(self) -> EvidenceArtifact:
        """An issued evidence artifact needs a concrete, independent id (§2.1)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        artifact_id = getattr(self, self._ID_FIELD)
        if artifact_id is None or artifact_id == "TBD":
            raise ArtifactIntegrityError(
                f"issued evidence artifact requires a concrete {self._ID_FIELD} "
                "(independent identity, not derived from digest) — §2.1/§3.1"
            )
        return self
