"""DSL-local base classes (design 2026-07-21-tos-strategy-dsl-design §2.5).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IdDerivedArtifact``, ``ArtifactStatus``, ``derive_id``, ``ArtifactIntegrityError``)
is reused verbatim from :mod:`tos.canonical` (design §0 REUSE, "재정의 금지"). This
module adds only the DSL-local pieces:

* :class:`AllFalseAuthority` — the authority block every DSL artifact carries,
  mirroring ``PROPOSAL-APPROVAL-REQUEST-template.yaml`` lines 72-82 (all ten flags
  forced ``false``). It is the pure-model realization of RFC-008 §8 ("candidate
  only"), §11 items 1-6/11, and SOS-INV-005: an authored artifact grants no
  approval, capacity, live-authorization, transmission, or protective status. Any
  ``True`` flag makes the artifact unconstructable (the full "no authority path
  anywhere" proof is EV-L2/L3; design §0 미구현).
* :class:`DecisionContextCapsuleRef` — the content-addressed ``(capsule_id,
  canonical_digest)`` binding a Proposal / Outcome records for the exact Decision
  Context Capsule it consumed (RFC-008 §8 "bind the exact Capsule identity and
  digest"; PROPOSAL-APPROVAL-REQUEST-template.yaml lines 31-33).

Firewall (design §firewall / 설계 #1 §3.2): ``pydantic`` + stdlib + ``tos.*`` only.
No ``importlib``/``__import__``/``exec``/``eval``, no ``os.environ``/``getenv``, no
network stdlib, no ``shared.*`` operational packages, no ``numpy``/``pandas``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IdDerivedArtifact,
    derive_id,
)

__all__ = [
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DecisionContextCapsuleRef",
    "DigestBoundArtifact",
    "FrozenModel",
    "IdDerivedArtifact",
    "IndependentIdArtifact",
    "derive_id",
]


class IndependentIdArtifact(DigestBoundArtifact):
    """Digest-bound artifact with an INDEPENDENT (non-derived) id (design §2.3/§2.4).

    Reuses the digest verification + required-covered completeness of
    :class:`~tos.canonical.DigestBoundArtifact`, but — like the evidence records of
    ``tos.evidence`` — its id is an independent injected field, **not**
    ``f(digest)`` (design §2.3: Outcome / enforcement-evidence records are ledger
    citizens, not content-addressed authored artifacts). The subclass names its id
    field via ``_ID_FIELD``; once issued (non-DRAFT) that id must be concrete
    (non-null, not the ``"TBD"`` placeholder). Defined DSL-locally to keep the
    ``tos.dsl`` import closure free of ``tos.evidence`` (design §firewall).
    """

    _ID_FIELD: ClassVar[str]

    @model_validator(mode="after")
    def _require_independent_id_when_issued(self) -> IndependentIdArtifact:
        """An issued artifact needs a concrete, independent id (design §2.3/§2.4)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        artifact_id = getattr(self, self._ID_FIELD)
        if artifact_id is None or artifact_id == "TBD":
            raise ArtifactIntegrityError(
                f"issued artifact requires a concrete {self._ID_FIELD} "
                "(independent identity, not derived from digest) — design §2.3/§2.4"
            )
        return self


#: The ten authority flags of ``PROPOSAL-APPROVAL-REQUEST-template.yaml`` L72-82.
#: Named as a constant so the validator and any downstream check consume one set.
_AUTHORITY_FLAGS: tuple[str, ...] = (
    "grants_approval",
    "creates_intent",
    "mutates_capacity",
    "creates_live_authorization",
    "creates_protective_classification",
    "creates_transmission_capability",
    "permits_broker_transmission",
    "clears_halt",
    "permits_rearm",
    "permits_automatic_rearm",
)


class AllFalseAuthority(FrozenModel):
    """Authored-artifact authority block — every flag forced ``false`` (design §2.5).

    Anchored to ``PROPOSAL-APPROVAL-REQUEST-template.yaml`` lines 72-82 (the
    downstream Approval consumer's vocabulary; ADR-002-020 not redefined). A DSL
    artifact is a *candidate* only (RFC-008 §8): it approves nothing, creates no
    intent, mutates no capacity, arms no live authorization, transmits nothing, and
    confers no protective classification. Any ``True`` value raises
    :class:`ArtifactIntegrityError` (SOS-INV-005; RFC-008 §11 items 1-6/11).
    """

    grants_approval: bool = False
    creates_intent: bool = False
    mutates_capacity: bool = False
    creates_live_authorization: bool = False
    creates_protective_classification: bool = False
    creates_transmission_capability: bool = False
    permits_broker_transmission: bool = False
    clears_halt: bool = False
    permits_rearm: bool = False
    permits_automatic_rearm: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (SOS-INV-005)."""
        for name in _AUTHORITY_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — an authored "
                    "artifact is a candidate only, it grants no authority "
                    "(RFC-008 §8/§11; SOS-INV-005)"
                )
        return self


class DecisionContextCapsuleRef(FrozenModel):
    """Content-addressed bind to the consumed Decision Context Capsule (design §2.2).

    Mirrors ``PROPOSAL-APPROVAL-REQUEST-template.yaml`` lines 31-33: identity +
    digest only, never the capsule body. A Proposal / Outcome binds the *exact*
    Capsule it consumed (RFC-008 §8), so a re-run over a different Capsule is a
    different, separately-identified artifact.
    """

    capsule_id: str | None = None
    canonical_digest: str | None = None
