"""Possibly-live attempt reconstruction (TOS Phase 5 W1; plan §2 decision 2; Phase 3 carryover"""

from __future__ import annotations

from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.engine.records import event_identity

from tos_runtime.engine.inbox import SqliteEventInbox

__all__ = ["PossiblyLiveAttempt", "reconstruct_possibly_live_attempts"]


@dataclass(frozen=True)
class PossiblyLiveAttempt:
    """One inbox row caught in the finding-#3 crash window (module docstring)."""

    event_id: str
    inbox_seq: int
    handling_started_evidence_seq: int
    handling_started_generation: int


def reconstruct_possibly_live_attempts(
    inbox: SqliteEventInbox, *, scheme: CanonicalizationScheme
) -> tuple[PossiblyLiveAttempt, ...]:
    """Reconstruct every possibly-live attempt from the durable inbox alone (module docstring)."""
    attempts: list[PossiblyLiveAttempt] = []
    for seq, event in inbox.replay():
        if inbox.is_consumed(seq):
            continue
        started = inbox.handling_started_receipt(seq)
        if started is None:
            continue
        evidence_seq, generation = started
        attempts.append(
            PossiblyLiveAttempt(
                event_id=event_identity(event, scheme=scheme),
                inbox_seq=seq,
                handling_started_evidence_seq=evidence_seq,
                handling_started_generation=generation,
            )
        )
    return tuple(attempts)
