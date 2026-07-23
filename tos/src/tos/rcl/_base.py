"""RCL-local base classes (RCL design §2, §3.1, §4.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED verbatim from
:mod:`tos.canonical` (RCL design §0.4a/§3.1 — "재정의 금지"). This module adds only
the RCL-local pieces:

* :class:`IndependentIdArtifact` — a ``DigestBoundArtifact`` whose id is an
  **independent** injected field, ``id != f(digest)`` (RCL design §3.1 (b)/§2.1).
  Every RCL ledger citizen (reservation, command, transition, capability,
  protective pool/lease, snapshot) is a ledger member with a service-assigned
  identity — ``reservation_id`` is never reused after terminal release
  (ADR-002-002 §9 line 502), ``command_identity`` is the coordinate of same-id /
  different-content conflict detection (ADR-002-012 §9 line 270; RCLP-INV-006).
  ``id = f(digest)`` would make that detection vacuous. Defined RCL-locally so the
  ``tos.rcl`` import closure stays free of ``tos.evidence`` (RCL is evidence's
  *upstream* — design §0.3/§3.1 layering).
* :class:`AllFalseAuthority` — an authority block whose every declared boolean flag
  is forced ``false`` at construction (RCL design §4.1 layer 1; ADR-002-002 §7.1
  line 322-331; ADR-002-012 §1 line 31). ``capacity != authority``: a grant /
  decision / capability / snapshot is a non-authoritative artifact — any ``True``
  flag makes it unconstructable (the full "no capacity-mutation / broker path
  anywhere" proof is EV-L2/L3; RCLP-EV-002/007). Isomorphic to the capsule
  ``SnapshotAuthority._all_authority_false`` and evidence ``AllFalseFlags``.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no
``tos.evidence`` / ``tos.capsule`` (RCL design §0.3).
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

__all__ = [
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class IndependentIdArtifact(DigestBoundArtifact):
    """Digest-bound RCL ledger citizen with an INDEPENDENT (non-derived) id (§3.1).

    Reuses the ``canonical_digest == H_ver(canonicalize(covered))`` verification and
    the required-covered completeness of :class:`~tos.canonical.DigestBoundArtifact`,
    but does **not** derive its id from the digest. The subclass names its
    independent id field via ``_ID_FIELD``; once issued (non-DRAFT) that id must be
    concrete (non-null, not the ``"TBD"`` template placeholder). Keeping identity
    orthogonal to the digest is what lets an append-only Safety Commit Log represent
    and detect an ADR-012 §9 "duplicate identity with different content" conflict
    (RCLP-INV-006) — a fact ``id = f(digest)`` would make vacuous (RCL design
    §2.1/§3.1).
    """

    _ID_FIELD: ClassVar[str]

    @model_validator(mode="after")
    def _require_independent_id_when_issued(self) -> IndependentIdArtifact:
        """An issued RCL ledger citizen needs a concrete, independent id (§2.1)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        artifact_id = getattr(self, self._ID_FIELD)
        if artifact_id is None or artifact_id == "TBD":
            raise ArtifactIntegrityError(
                f"issued RCL artifact requires a concrete {self._ID_FIELD} "
                "(independent identity, not derived from digest) — RCL §2.1/§3.1"
            )
        return self


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design §4.1).

    The pure-model realization of ``capacity != authority`` (RCLP-INV-001/012;
    ADR-002-002 §7.1; ADR-002-012 §1 line 31, §10 line 282-290): a grant / decision
    / capability / snapshot grants no authority. Any ``True`` authority flag makes
    the artifact unconstructable. Subclasses declare the exact flag names for their
    artifact. Isomorphic to the capsule / evidence all-false blocks.
    """

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (RCLP-INV-001)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(capacity != authority — RCLP-INV-001/012; only a committed "
                    "RCL transition may mutate capacity)"
                )
        return self
