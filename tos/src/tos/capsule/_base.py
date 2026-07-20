"""Shared frozen-model infrastructure for tos capsule artifacts (design §2, §4).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True)``),
the model realization of ADR-002-018 §12 (line 328) "A Capsule is immutable":
no field is mutable in place, so any change forces a new object -> new digest ->
new identity (design §4.1).

This module provides:

* :class:`FrozenModel` — the frozen, ``extra="forbid"`` base for every model.
* :class:`ArtifactStatus` — lifecycle marker (excluded from the digest, §3.2).
* :class:`SnapshotAuthority` / :class:`CapsuleAuthority` — authority blocks whose
  every flag is forced ``false`` (CII-INV-011, design §4.4).
* :class:`PolicyRef` — the ``{policy_id, policy_generation, canonical_digest}``
  reference shared by snapshot and capsule.
* :class:`DigestBoundArtifact` — the digest/id self-verification mixin that
  enforces ``canonical_digest == H_ver(canonicalize(covered))`` and the derived
  ``id = f(digest)`` binding (design §4.1, CII-INV-003).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from tos.capsule.canonicalization import CanonicalizationScheme, get_scheme


class CapsuleIntegrityError(ValueError):
    """A frozen artifact violates a construction-time integrity invariant.

    Subclasses ``ValueError`` so pydantic surfaces it as a validation failure,
    making malformed artifacts *unconstructable* (design §4.1).
    """


class ArtifactStatus(StrEnum):
    """Lifecycle marker for a digest-bound artifact (design §3.2 item 2).

    Excluded from the digest preimage so that identity is stable across the
    issuance lifecycle (CII-INV-003 requires a single "same exact digest" bound
    across states). ``DRAFT`` is the pre-issuance state in which the digest and
    id are not yet computed (design §3.2 TBD/null handling).
    """

    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class FrozenModel(BaseModel):
    """Immutable, schema-strict base for every tos capsule model (design §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SnapshotAuthority(FrozenModel):
    """Snapshot authority block — every flag forced ``false`` (design §4.4).

    Matches ``CRITICAL-INPUT-SNAPSHOT-template.yaml`` lines 44-50. The pure-model
    realization of CII-INV-011: this kernel grants no authority. A ``True`` value
    makes the artifact unconstructable (the full "no authority path anywhere"
    proof is EV-L2/L3, design §0.2/§4.4).
    """

    grants_approval: bool = False
    creates_capacity: bool = False
    creates_live_authorization: bool = False
    creates_protective_classification: bool = False
    permits_broker_transmission: bool = False
    permits_rearm: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> SnapshotAuthority:
        """Reject construction if any authority flag is ``True`` (CII-INV-011)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise CapsuleIntegrityError(
                    f"{type(self).__name__}.{name} must be false (CII-INV-011)"
                )
        return self


class CapsuleAuthority(SnapshotAuthority):
    """Capsule authority block (adds ``permits_automatic_rearm``; design §4.4).

    Matches ``DECISION-CONTEXT-CAPSULE-template.yaml`` lines 75-82.
    """

    permits_automatic_rearm: bool = False


class PolicyRef(FrozenModel):
    """Reference to a governing Critical Input Policy (design §2.6/§2.7).

    Matches the ``critical_input_policy`` block in both templates: a content
    reference only (id + generation + digest), never the policy body.
    """

    policy_id: str | None = None
    policy_generation: int | None = None
    canonical_digest: str | None = None


def derive_id(prefix: str, digest: str) -> str:
    """Derive an artifact id from its digest (``id = f(digest)``; design §4.1).

    Deterministic ``{prefix}-{digest}`` binding so that arbitrary id reattachment
    or digest substitution fails the :class:`DigestBoundArtifact` check. The
    external-assignment alternative is deferred to Phase-0 (design §9.2 item 6).

    Args:
        prefix: The artifact-type prefix (e.g. ``"dcc"``, ``"cis"``).
        digest: The canonical digest.

    Returns:
        The derived id string.
    """
    return f"{prefix}-{digest}"


class DigestBoundArtifact(FrozenModel):
    """Mixin enforcing the digest + ``id = f(digest)`` binding (design §4.1).

    Subclasses declare, as class variables, the name of their id field
    (``_ID_FIELD``), the id prefix (``_ID_PREFIX``), and the covered
    (digest-preimage) top-level field names (``_COVERED_FIELDS`` — the Layer-1
    set, design §3.3). Subclasses must also expose ``status``,
    ``canonical_digest`` and ``canonicalization_version`` fields.

    On every construction with a non-``DRAFT`` status the ``after`` validator
    recomputes the digest over the covered content and rejects any mismatch or
    any id that is not ``derive_id(prefix, digest)`` — this is what makes
    mutate / union / partial-refresh / digest-substitution unconstructable
    (CII-EV-007 core, design §4.1). ``DRAFT`` artifacts are pre-issuance and skip
    verification (their digest/id are not yet computed, design §3.2).
    """

    _ID_FIELD: ClassVar[str]
    _ID_PREFIX: ClassVar[str]
    _COVERED_FIELDS: ClassVar[frozenset[str]]
    # Dotted paths of the safety-load-bearing covered fields that MUST be concrete
    # for an artifact to reach a non-DRAFT (ISSUED) status (design §3.2: a covered
    # field left ``TBD``/``null`` keeps the artifact pre-issuance). Subclasses fix
    # this set; the derivation from the canonical template's ``TBD`` (must-fill)
    # vs ``null`` (optional) markers is documented on each subclass.
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ()

    # Layer-0 identity + meta, shared by every digest-bound artifact and excluded
    # from the covered digest preimage (design §3.2). Subclasses add their own
    # type-specific id field (``_ID_FIELD``) and Layer-1 covered content.
    canonical_digest: str | None = None
    status: ArtifactStatus = ArtifactStatus.DRAFT
    canonicalization_version: str | None = None

    def missing_required_fields(self) -> list[str]:
        """Return the ``_REQUIRED_COVERED`` dotted paths that are not concrete.

        A path is *missing* when any component along it is absent, ``None``, or
        the literal ``"TBD"`` template placeholder (design §3.2). This is the
        completeness predicate both the construction guard and the fail-closed
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

        The §3.2 self-exclusion set (identity outputs, ``status``,
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
        """Enforce digest, ``id = f(digest)``, and required-covered (design §4.1/§3.2)."""
        artifact_id = getattr(self, self._ID_FIELD)
        if self.status == ArtifactStatus.DRAFT:
            # Pre-issuance: digest/id are not yet computed and MUST be null so a
            # DRAFT cannot smuggle a forged digest/id past the ISSUED-only checks
            # (MINOR-3). Required-covered completeness is deferred to issuance.
            if self.canonical_digest is not None or artifact_id is not None:
                raise CapsuleIntegrityError(
                    "DRAFT artifact must have null canonical_digest and id "
                    f"(stored digest={self.canonical_digest!r}, id={artifact_id!r}) — §3.2"
                )
            return self

        digest = self.canonical_digest
        if digest is None:
            raise CapsuleIntegrityError(
                "issued artifact requires a concrete canonical_digest (§3.2)"
            )
        scheme: CanonicalizationScheme = get_scheme(self.canonicalization_version)
        expected_digest = scheme.compute_digest(self.covered_content())
        if digest != expected_digest:
            raise CapsuleIntegrityError(
                "canonical_digest does not match canonicalize(covered) "
                f"(stored={digest!r}, expected={expected_digest!r}) — CII-INV-003"
            )
        expected_id = derive_id(self._ID_PREFIX, expected_digest)
        if artifact_id != expected_id:
            raise CapsuleIntegrityError(
                f"{self._ID_FIELD} must equal f(digest) "
                f"(stored={artifact_id!r}, expected={expected_id!r}) — §4.1"
            )
        missing = self.missing_required_fields()
        if missing:
            raise CapsuleIntegrityError(
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
        """Issue an artifact: compute its digest and derive its id (design §4.1).

        Builds a transient ``DRAFT`` to extract the covered content, computes the
        digest with ``scheme``, derives ``id = f(digest)``, then constructs the
        final artifact — which re-runs :meth:`_verify_digest_identity`.

        Args:
            scheme: The canonicalization scheme to bind (its ``version`` is
                recorded as ``canonicalization_version``).
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
