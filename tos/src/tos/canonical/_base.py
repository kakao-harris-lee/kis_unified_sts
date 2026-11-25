"""Shared digest-binding substrate for tos artifacts (design #4 §3.1 PROMOTE)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator

from tos.canonical._canonical_json import CanonicalJsonMixin
from tos.canonical.canonicalization import CanonicalizationScheme, get_scheme


class ArtifactIntegrityError(ValueError):
    """A frozen artifact violates a construction-time integrity invariant."""


class ArtifactStatus(StrEnum):
    """Lifecycle marker for a digest-bound artifact (design §3.2 item 2)."""

    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class FrozenModel(CanonicalJsonMixin, BaseModel):
    """Immutable, schema-strict base for every tos artifact model (design §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


def derive_id(prefix: str, digest: str) -> str:
    """Derive an artifact id from its digest (``id = f(digest)``; design #2 §4.1)."""
    return f"{prefix}-{digest}"


class DigestBoundArtifact(FrozenModel):
    """Base enforcing ``canonical_digest == H_ver(canonicalize(covered))`` (§4.1)."""

    _COVERED_FIELDS: ClassVar[frozenset[str]]
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ()

    canonical_digest: str | None = None
    status: ArtifactStatus = ArtifactStatus.DRAFT
    canonicalization_version: str | None = None

    def _verify_id_binding(self, expected_digest: str) -> None:
        """Hook: verify the id binding for an ISSUED artifact (base: no id)."""
        del expected_digest

    def _verify_draft_id_null(self) -> None:
        """Hook: verify a DRAFT artifact's id is unset (base: no id)."""
        return None

    def missing_required_fields(self) -> list[str]:
        """Return the ``_REQUIRED_COVERED`` dotted paths that are not concrete."""
        missing: list[str] = []
        for path in self._REQUIRED_COVERED:
            value: Any = self
            for part in path.split("."):
                value = getattr(value, part, None)
                if value is None:
                    break
            if value is None or value == "TBD":
                missing.append(path)
        return missing

    def covered_content(self) -> dict[str, Any]:
        """Return the digest preimage: the Layer-1 covered fields (design §3.3)."""
        return self.model_dump(mode="json", include=set(self._COVERED_FIELDS))

    @model_validator(mode="after")
    def _verify_digest_identity(self) -> DigestBoundArtifact:
        """Enforce digest + required-covered (+ id hooks) (design §4.1/§4.2/§3.2)."""
        if self.status == ArtifactStatus.DRAFT:
            if self.canonical_digest is not None:
                raise ArtifactIntegrityError(
                    "DRAFT artifact must have null canonical_digest "
                    f"(stored digest={self.canonical_digest!r}) — §3.2"
                )
            self._verify_draft_id_null()
            return self

        digest = self.canonical_digest
        if digest is None:
            raise ArtifactIntegrityError(
                "issued artifact requires a concrete canonical_digest (§3.2)"
            )
        scheme: CanonicalizationScheme = get_scheme(self.canonicalization_version)
        expected_digest = scheme.compute_digest(self.covered_content())
        if digest != expected_digest:
            raise ArtifactIntegrityError(
                "canonical_digest does not match canonicalize(covered) "
                f"(stored={digest!r}, expected={expected_digest!r}) — §4.1"
            )
        self._verify_id_binding(expected_digest)
        missing = self.missing_required_fields()
        if missing:
            raise ArtifactIntegrityError(
                "issued artifact is missing required safety-load-bearing covered "
                f"fields (must be concrete, not TBD/null): {missing} — §3.2"
            )
        return self

    @classmethod
    def issue(
        cls,
        *,
        scheme: CanonicalizationScheme,
        status: ArtifactStatus = ArtifactStatus.ISSUED,
        **content: Any,
    ) -> Self:
        """Issue an artifact: compute its digest over the covered content (§4.1)."""
        draft_kwargs: dict[str, Any] = dict(content)
        draft_kwargs["canonical_digest"] = None
        draft_kwargs["status"] = ArtifactStatus.DRAFT
        draft_kwargs["canonicalization_version"] = scheme.version
        draft = cls(**draft_kwargs)

        digest = scheme.compute_digest(draft.covered_content())

        issued_kwargs: dict[str, Any] = dict(content)
        issued_kwargs["canonical_digest"] = digest
        issued_kwargs["status"] = status
        issued_kwargs["canonicalization_version"] = scheme.version
        return cls(**issued_kwargs)


class IdDerivedArtifact(DigestBoundArtifact):
    """Digest-bound artifact whose id is derived: ``id = f(digest)`` (design #2 §4.1)."""

    _ID_FIELD: ClassVar[str]
    _ID_PREFIX: ClassVar[str]

    def _verify_draft_id_null(self) -> None:
        """A DRAFT id-derived artifact must have a null id (design §3.2)."""
        artifact_id = getattr(self, self._ID_FIELD)
        if artifact_id is not None:
            raise ArtifactIntegrityError(
                "DRAFT artifact must have null id "
                f"(stored {self._ID_FIELD}={artifact_id!r}) — §3.2"
            )

    def _verify_id_binding(self, expected_digest: str) -> None:
        """An ISSUED id-derived artifact's id must equal ``f(digest)`` (§4.1)."""
        artifact_id = getattr(self, self._ID_FIELD)
        expected_id = derive_id(self._ID_PREFIX, expected_digest)
        if artifact_id != expected_id:
            raise ArtifactIntegrityError(
                f"{self._ID_FIELD} must equal f(digest) "
                f"(stored={artifact_id!r}, expected={expected_id!r}) — §4.1"
            )

    @classmethod
    def issue(
        cls,
        *,
        scheme: CanonicalizationScheme,
        status: ArtifactStatus = ArtifactStatus.ISSUED,
        **content: Any,
    ) -> Self:
        """Issue an id-derived artifact: compute the digest and derive the id (§4.1)."""
        id_field = cls._ID_FIELD
        draft_kwargs: dict[str, Any] = dict(content)
        draft_kwargs[id_field] = None
        draft_kwargs["canonical_digest"] = None
        draft_kwargs["status"] = ArtifactStatus.DRAFT
        draft_kwargs["canonicalization_version"] = scheme.version
        draft = cls(**draft_kwargs)

        digest = scheme.compute_digest(draft.covered_content())

        issued_kwargs: dict[str, Any] = dict(content)
        issued_kwargs[id_field] = derive_id(cls._ID_PREFIX, digest)
        issued_kwargs["canonical_digest"] = digest
        issued_kwargs["status"] = status
        issued_kwargs["canonicalization_version"] = scheme.version
        return cls(**issued_kwargs)


class IndependentIdArtifact(DigestBoundArtifact):
    """Digest-bound artifact with an INDEPENDENT (non-derived) id (design #4 §3.1)."""

    _ID_FIELD: ClassVar[str]

    @model_validator(mode="after")
    def _require_independent_id_when_issued(self) -> IndependentIdArtifact:
        """An issued artifact needs a concrete, independent id (design #4 §3.1)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        artifact_id = getattr(self, self._ID_FIELD)
        if artifact_id is None or artifact_id == "TBD":
            raise ArtifactIntegrityError(
                f"issued artifact requires a concrete {self._ID_FIELD} "
                "(independent identity, not derived from digest) — canonical §3.1"
            )
        return self
