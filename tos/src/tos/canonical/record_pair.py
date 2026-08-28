"""Same-identity / different-content record-pair classifier — promoted core.

Promoted out of ``tos.evidence.predicates`` into ``tos.canonical`` (RCL design
§0.4b/§3.1c) so both ``tos.evidence`` and ``tos.rcl`` share **one** pure classifier
without importing each other. ``tos.rcl`` is the *upstream* Safety Commit Log and
``tos.evidence`` is a downstream projection (ADR-002-012 §19 line 478), so a
``tos.rcl -> tos.evidence`` edge would be a layering inversion; both packages
instead depend one-directionally on ``tos.canonical`` (the ordering /
canonicalization PROMOTE precedent).

It is a pure ``(identity, digest) -> kind`` classifier over the
:class:`~tos.canonical.DigestBoundArtifact` domain: because a ledger citizen's
identity is INDEPENDENT of its ``canonical_digest`` (``id != f(digest)``; canonical
§3.1 (b)), a same-identity / different-bytes pair is a **Critical integrity
conflict** to CONTAIN (both observations preserved, never merged / last-write-wins),
and a same-identity / same-bytes pair is an idempotent duplicate — a distinction
that ``id = f(digest)`` would make vacuous (ADR-002-012 §9 line 270 "duplicate
identity with different content"; RCLP-INV-006; ADR-002-016 §12).

``tos.evidence`` keeps a thin envelope-taking shim delegating here, so every
existing evidence path (and ERI-EV-004) stays green unchanged.

Pure module: stdlib only; no ``shared.*``, no ``tos.*`` beyond this module.
"""

from __future__ import annotations

from enum import StrEnum


class RecordPairKind(StrEnum):
    """Classification of two ledger records by shared identity vs canonical bytes.

    Serves both evidence records and RCL commands / reservations. A same-primary-id
    / different-bytes pair is the Critical integrity conflict; a same-idempotency /
    different-bytes pair is a divergent emission (the evidence-only idempotency axis
    — RCL passes no idempotency id and so never produces ``DIVERGENT_EMISSION``).
    """

    #: Same primary id (or idempotency id) + same canonical bytes — a duplicate.
    IDEMPOTENT_DUP = "IDEMPOTENT_DUP"
    #: Same primary id + different canonical bytes — a Critical integrity conflict.
    CRITICAL_CONFLICT = "CRITICAL_CONFLICT"
    #: Same idempotency id + different bytes — a divergent logical emission.
    DIVERGENT_EMISSION = "DIVERGENT_EMISSION"
    #: No shared identity constraint is violated.
    DISTINCT = "DISTINCT"
    #: At least one record is pre-issuance (null digest) — not a ledger citizen.
    NOT_COMPARABLE = "NOT_COMPARABLE"


def classify_record_pair(
    a_identity: str | None,
    a_digest: str | None,
    b_identity: str | None,
    b_digest: str | None,
    *,
    a_idempotency_id: str | None = None,
    b_idempotency_id: str | None = None,
) -> RecordPairKind:
    """Classify two records by shared identity vs canonical bytes (pure).

    Semantics (invariant across evidence records and RCL commands / reservations):

    * either digest ``None`` (a pre-issuance DRAFT, not a ledger citizen) =>
      ``NOT_COMPARABLE`` — never a false conflict (canonical MINOR-1 discipline).
    * same primary ``identity`` => same bytes is ``IDEMPOTENT_DUP``; different bytes
      is ``CRITICAL_CONFLICT`` (contain both; no last-write-wins merge).
    * else same ``idempotency_id`` => same bytes is ``IDEMPOTENT_DUP``; different
      bytes is ``DIVERGENT_EMISSION`` (the evidence idempotency axis; RCL passes no
      idempotency id and so never reaches this branch).
    * otherwise ``DISTINCT``.

    Args:
        a_identity: The first record's independent primary identity (or ``None``).
        a_digest: The first record's canonical digest (``None`` if pre-issuance).
        b_identity: The second record's independent primary identity (or ``None``).
        b_digest: The second record's canonical digest (``None`` if pre-issuance).
        a_idempotency_id: Optional idempotency id of the first record (evidence
            axis; RCL leaves it ``None``).
        b_idempotency_id: Optional idempotency id of the second record.

    Returns:
        The :class:`RecordPairKind`.
    """
    if a_digest is None or b_digest is None:
        return RecordPairKind.NOT_COMPARABLE
    same_bytes = a_digest == b_digest
    same_identity = a_identity is not None and a_identity == b_identity
    if same_identity:
        # Same primary id: identical bytes is a duplicate; differing bytes is the
        # §12 / §9 Critical conflict (independent of any idempotency id).
        return (
            RecordPairKind.IDEMPOTENT_DUP
            if same_bytes
            else RecordPairKind.CRITICAL_CONFLICT
        )
    same_idem = a_idempotency_id is not None and a_idempotency_id == b_idempotency_id
    if same_idem:
        return (
            RecordPairKind.IDEMPOTENT_DUP
            if same_bytes
            else RecordPairKind.DIVERGENT_EMISSION
        )
    return RecordPairKind.DISTINCT
