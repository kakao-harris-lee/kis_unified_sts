"""Same-identity / different-content record-pair classifier — promoted core."""

from __future__ import annotations

from enum import StrEnum


class RecordPairKind(StrEnum):
    """Classification of two ledger records by shared identity vs canonical bytes."""

    IDEMPOTENT_DUP = "IDEMPOTENT_DUP"
    CRITICAL_CONFLICT = "CRITICAL_CONFLICT"
    DIVERGENT_EMISSION = "DIVERGENT_EMISSION"
    DISTINCT = "DISTINCT"
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
    """Classify two records by shared identity vs canonical bytes (pure)."""
    if a_digest is None or b_digest is None:
        return RecordPairKind.NOT_COMPARABLE
    same_bytes = a_digest == b_digest
    same_identity = a_identity is not None and a_identity == b_identity
    if same_identity:
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
