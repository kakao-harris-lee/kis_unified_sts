"""``RecordedTransmit`` — a side-effect-free ``Transmit`` stand-in for boot-time replay"""

from __future__ import annotations

import json
from dataclasses import dataclass

from tos.engine.records import AttemptRequest, SendHandoff

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "ReplayTransmitEvidenceMissing",
    "RecordedTransmit",
    "any_recorded_hand_off",
]

_SEND_HANDED_OFF_KIND = "SEND_HANDED_OFF"


class ReplayTransmitEvidenceMissing(RuntimeError):
    """Raised by :class:`RecordedTransmit` when no ``SEND_HANDED_OFF`` evidence exists for the"""


def _attempt_was_handed_off(
    evidence_store: SqliteEvidenceStore, attempt_id: str
) -> bool:
    """Whether a ``SEND_HANDED_OFF`` evidence record names exactly ``attempt_id``."""
    cur = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?", (_SEND_HANDED_OFF_KIND,)
    )
    for (payload_json,) in cur:
        payload = json.loads(payload_json).get("payload", {})
        if payload.get("attempt_id") == attempt_id:
            return True
    return False


def any_recorded_hand_off(evidence_store: SqliteEvidenceStore) -> bool:
    """Whether ANY attempt in this evidence store's history was ever handed off."""
    cur = evidence_store.connection.execute(
        "SELECT 1 FROM entries WHERE kind = ? LIMIT 1", (_SEND_HANDED_OFF_KIND,)
    )
    return cur.fetchone() is not None


@dataclass
class RecordedTransmit:
    """A ``Transmit`` (``tos.engine.sequencer.Transmit`` Protocol) stand-in that reproduces the"""

    evidence_store: SqliteEvidenceStore

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Reproduce the recorded hand-off for ``attempt``, or refuse (fail-closed)."""
        if not _attempt_was_handed_off(self.evidence_store, attempt.attempt_id):
            raise ReplayTransmitEvidenceMissing(
                f"no SEND_HANDED_OFF evidence recorded for attempt {attempt.attempt_id!r} — "
                "replay refuses to guess a hand-off the live run's own evidence does not "
                "corroborate (fail-closed, CR5 dispatch 2026-09-09)"
            )
        return SendHandoff(
            accepted_for_transmission=True, handoff_reference=attempt.attempt_id
        )
