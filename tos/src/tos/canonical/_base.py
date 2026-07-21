"""Shared digest-binding substrate for tos artifacts (design #4 §3.1 PROMOTE).

Promoted to ``tos.canonical`` so both ``tos.capsule`` and ``tos.evidence`` share
one digest-binding substrate (design #4 §0.4/§3.1). ``tos.capsule._base`` remains
a thin re-export shim (plus the capsule-local authority/policy blocks), so
existing ``from tos.capsule._base import ...`` paths are unchanged.

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True)``),
the model realization of "an artifact is immutable" (ADR-002-018 §12 / design #2
§4.1): no field is mutable in place, so any change forces a new object -> new
digest (design §4.1/§4.2).

This module provides two layers (design #4 §3.1 (b) — split digest verification
from id derivation):

* :class:`DigestBoundArtifact` — the **base**: enforces
  ``canonical_digest == H_ver(canonicalize(covered))`` and required-covered
  completeness. It does **not** derive an id. ``tos.evidence`` artifacts inherit
  this directly because evidence identity is an INDEPENDENT injected field, not
  ``f(digest)`` (design #4 §2.1/§3.1 — so §12 same-id/different-bytes conflict
  remains representable and detectable).
* :class:`IdDerivedArtifact` — the **subclass**: additionally enforces
  ``id = derive_id(prefix, digest)``. ``tos.capsule`` capsule/snapshot inherit
  this because they are immutable content-addressed artifacts (design #2 §4.1).

* :class:`ArtifactStatus` — lifecycle marker (excluded from the digest, §3.2).
* :class:`ArtifactIntegrityError` — construction-time integrity violation
  (``tos.capsule`` re-exports it as ``CapsuleIntegrityError``).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from tos.canonical.canonicalization import CanonicalizationScheme, get_scheme


class ArtifactIntegrityError(ValueError):
    """A frozen artifact violates a construction-time integrity invariant.

    Subclasses ``ValueError`` so pydantic surfaces it as a validation failure,
    making malformed artifacts *unconstructable* (design §4.1/§4.2).
    """


class ArtifactStatus(StrEnum):
    """Lifecycle marker for a digest-bound artifact (design §3.2 item 2).

    Excluded from the digest preimage so that identity is stable across the
    issuance lifecycle (a single "same exact digest" bound must span states).
    ``DRAFT`` is the pre-issuance state in which the digest (and, for id-derived
    artifacts, the id) is not yet computed (design §3.2/§3.3 TBD/null handling).
    """

    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class FrozenModel(BaseModel):
    """Immutable, schema-strict base for every tos artifact model (design §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")


def derive_id(prefix: str, digest: str) -> str:
    """Derive an artifact id from its digest (``id = f(digest)``; design #2 §4.1).

    Deterministic ``{prefix}-{digest}`` binding so that arbitrary id reattachment
    or digest substitution fails the :class:`IdDerivedArtifact` check. Used only
    by content-addressed artifacts (capsule/snapshot); evidence records take an
    INDEPENDENT id (design #4 §3.1). The external-assignment alternative is
    deferred to Phase-0 (design #2 §9.2 item 6).

    Args:
        prefix: The artifact-type prefix (e.g. ``"dcc"``, ``"cis"``).
        digest: The canonical digest.

    Returns:
        The derived id string.
    """
    return f"{prefix}-{digest}"


class DigestBoundArtifact(FrozenModel):
    """Base enforcing ``canonical_digest == H_ver(canonicalize(covered))`` (§4.1).

    Subclasses declare, as class variables, the covered (digest-preimage)
    top-level field names (``_COVERED_FIELDS`` — the Layer-1 set, design §3.3) and
    must expose ``canonical_digest``/``status``/``canonicalization_version``
    fields (all inherited here).

    On every construction with a non-``DRAFT`` status the ``after`` validator
    recomputes the digest over the covered content and rejects any mismatch —
    this is what makes mutate / union / partial-refresh / digest-substitution
    unconstructable. ``DRAFT`` artifacts are pre-issuance and skip verification
    (their digest is not yet computed, design §3.2/§3.3).

    This base derives **no** id. :class:`IdDerivedArtifact` overrides the id hooks
    to bind ``id = derive_id(prefix, digest)``; evidence artifacts leave the hooks
    as no-ops and carry an independent, non-derived id (design #4 §3.1).
    """

    _COVERED_FIELDS: ClassVar[frozenset[str]]
    # Dotted paths of the safety-load-bearing covered fields that MUST be concrete
    # for an artifact to reach a non-DRAFT (ISSUED) status (design §3.2: a covered
    # field left ``TBD``/``null`` keeps the artifact pre-issuance). Subclasses fix
    # this set; the derivation from the canonical template's ``TBD`` (must-fill)
    # vs ``null`` (optional) markers is documented on each subclass.
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ()

    # Layer-0 meta, shared by every digest-bound artifact and excluded from the
    # covered digest preimage (design §3.2/§3.3). Subclasses add their own
    # id field(s) and Layer-1 covered content.
    canonical_digest: str | None = None
    status: ArtifactStatus = ArtifactStatus.DRAFT
    canonicalization_version: str | None = None

    # ---- id hooks (no-op in the base; overridden by IdDerivedArtifact) --------

    def _verify_id_binding(self, expected_digest: str) -> None:
        """Hook: verify the id binding for an ISSUED artifact (base: no id)."""
        del expected_digest  # base derives no id; IdDerivedArtifact overrides

    def _verify_draft_id_null(self) -> None:
        """Hook: verify a DRAFT artifact's id is unset (base: no id)."""
        return None

    def missing_required_fields(self) -> list[str]:
        """Return the ``_REQUIRED_COVERED`` dotted paths that are not concrete.

        A path is *missing* when any component along it is absent, ``None``, or
        the literal ``"TBD"`` template placeholder (design §3.2). This is the
        completeness predicate both the construction guard and any fail-closed
        authorization predicate consume, so the two can never diverge.

        Returns:
            The unmet required dotted paths (empty when all are concrete).
        """
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
        """Return the digest preimage: the Layer-1 covered fields (design §3.3).

        The §3.2/§3.3 self-exclusion set (identity outputs, ``status``,
        ``canonicalization_version`` meta, and any Layer-2 back-references) is
        excluded simply by not being listed in ``_COVERED_FIELDS``. The result is
        JSON-native (``mode="json"``) so the canonicalizer sees only
        ``None``/``bool``/number/``str``/list/dict.

        Returns:
            A plain, JSON-native mapping of covered field name to value.
        """
        return self.model_dump(mode="json", include=set(self._COVERED_FIELDS))

    @model_validator(mode="after")
    def _verify_digest_identity(self) -> DigestBoundArtifact:
        """Enforce digest + required-covered (+ id hooks) (design §4.1/§4.2/§3.2)."""
        if self.status == ArtifactStatus.DRAFT:
            # Pre-issuance: the digest is not yet computed and MUST be null so a
            # DRAFT cannot smuggle a forged digest past the ISSUED-only checks.
            # Required-covered completeness is deferred to issuance.
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
    ) -> DigestBoundArtifact:
        """Issue an artifact: compute its digest over the covered content (§4.1).

        Builds a transient ``DRAFT`` to extract the covered content, computes the
        digest with ``scheme``, then constructs the final artifact — which
        re-runs :meth:`_verify_digest_identity`. This base does not touch any id
        field (evidence identity is injected via ``content``); id-derived
        artifacts override this to also derive the id.

        Args:
            scheme: The canonicalization scheme to bind (its ``version`` is
                recorded as ``canonicalization_version``).
            status: The issued lifecycle status (default ``ISSUED``).
            **content: The Layer-1 (and Phase-1-null Layer-2) field values plus,
                for evidence artifacts, the independent id field, excluding
                ``canonical_digest`` and ``canonicalization_version``.

        Returns:
            The issued, digest-verified artifact.
        """
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
    """Digest-bound artifact whose id is derived: ``id = f(digest)`` (design #2 §4.1).

    Adds, as class variables, the name of the id field (``_ID_FIELD``) and the id
    prefix (``_ID_PREFIX``). Construction rejects any id that is not
    ``derive_id(prefix, digest)`` (and requires a null id while ``DRAFT``), so
    arbitrary id reattachment or digest substitution is unconstructable. Used by
    the immutable content-addressed capsule/snapshot artifacts; evidence records
    do NOT use this (design #4 §3.1 — independent identity).
    """

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
    ) -> IdDerivedArtifact:
        """Issue an id-derived artifact: compute the digest and derive the id (§4.1).

        Args:
            scheme: The canonicalization scheme to bind.
            status: The issued lifecycle status (default ``ISSUED``; may be a
                later non-``DRAFT`` state such as ``SUPERSEDED``).
            **content: The Layer-1 (and Phase-1-null Layer-2) field values,
                excluding the id, ``canonical_digest`` and
                ``canonicalization_version`` fields.

        Returns:
            The issued, digest-verified artifact.
        """
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
