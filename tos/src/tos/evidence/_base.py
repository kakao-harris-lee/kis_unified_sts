"""Evidence-local base classes (design #4 §2, §3.1, §4.6).

Evidence artifacts reuse the promoted digest-binding substrate
(:class:`tos.canonical.DigestBoundArtifact`) but adopt an **independent**,
non-derived identity: ``id != f(digest)`` (design #4 §3.1 (b) / §2.1). Keeping
identity orthogonal to the content digest is what lets an append-only ledger
*represent and detect* a §12 "same record id + different canonical bytes =
Critical integrity conflict" — a fact that ``id = f(digest)`` would make vacuous.

Two shared bases live here:

* :class:`EvidenceArtifact` — a ``DigestBoundArtifact`` (digest verification +
  required-covered completeness) that additionally requires its independent id
  field to be concrete once issued. The base ``_verify_draft_id_null`` /
  ``_verify_id_binding`` hooks stay no-ops (evidence identity may be present in a
  DRAFT and is never digest-derived).
* :class:`AllFalseFlags` — an authority block whose every declared boolean flag
  is forced ``false`` at construction (design #4 §4.6 — evidence is not
  authority; a ``True`` value is unconstructable, the full "no authority path"
  proof is EV-L2/L3).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

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
    """Authority block: every declared boolean flag forced ``false`` (design §4.6).

    The pure-model realization of ERI-INV-001/014 (evidence is not authority):
    any ``True`` authority flag makes the artifact unconstructable. Subclasses
    declare the exact template flag names for their artifact.
    """

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
    """Digest-bound evidence artifact with an INDEPENDENT (non-derived) id (§3.1).

    Reuses the ``canonical_digest == H_ver(canonicalize(covered))`` verification
    of :class:`~tos.canonical.DigestBoundArtifact` but does **not** derive its id
    from the digest. Instead the subclass names its independent id field via
    ``_ID_FIELD``; that id must be concrete (non-null, not the ``"TBD"`` template
    placeholder) once the artifact is issued (non-DRAFT). This keeps the id
    orthogonal to the digest so same-id/different-bytes conflicts remain
    detectable (design #4 §2.1/§3.1/§4.2).

    The inherited ``canonical_digest`` field is the artifact's own canonical
    record/content digest; per-subclass docstrings map it to the template's
    specifically named self-digest (``content_digest`` for EIP/Replay, the
    record digest for the envelope) — design #4 §3.2.
    """

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
