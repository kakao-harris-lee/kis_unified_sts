"""The POST_TRADE currentness dimension's own read over release evidence."""

from __future__ import annotations

import json

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.reservation_identity import scope_reservation_id

__all__ = ["latest_release_is_conflict_free"]

_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
_HELD_KIND = "CAPACITY_RELEASE_HELD"
_NOT_CORROBORATED = "NOT_CORROBORATED"


def latest_release_is_conflict_free(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> bool:
    """Whether this scope's MOST RECENT recorded post-trade release evidence is conflict-free."""
    scope_id = scope_reservation_id(account, instrument)
    rows = evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq DESC",
        (_INTENT_KIND, _HELD_KIND),
    ).fetchall()
    for kind, payload_json in rows:
        decoded = json.loads(payload_json)["payload"]
        reservation_id = decoded.get("reservation_id")
        if not isinstance(reservation_id, str) or not (
            reservation_id == scope_id or reservation_id.startswith(f"{scope_id}-")
        ):
            continue
        if kind == _INTENT_KIND:
            return True
        return bool(decoded.get("reason") != _NOT_CORROBORATED)
    return True
