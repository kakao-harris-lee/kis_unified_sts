"""``_TimeoutTracker`` — :class:`~tos_runtime.engine.driver.EngineDriver`'s per-scope pending-"""

from __future__ import annotations

from dataclasses import dataclass, field

from tos.engine.records import InstrumentKey

__all__ = ["_PendingAttempt", "_TimeoutTracker"]


@dataclass
class _PendingAttempt:
    """One outstanding, not-yet-resulted attempt this driver is timing (item 4)."""

    attempt_id: str
    started_at_ms: int
    timed_out: bool = False


@dataclass
class _TimeoutTracker:
    """Per-scope pending-attempt bookkeeping for :class:`EngineDriver`'s timeout injection."""

    max_send_result_wait_ms: int
    pending: dict[tuple[str, str], _PendingAttempt] = field(default_factory=dict)

    @staticmethod
    def _key(key: InstrumentKey) -> tuple[str, str]:
        return (key.account, key.instrument)

    def observe_handoff(
        self, key: InstrumentKey, *, attempt_id: str, now_ms: int
    ) -> None:
        """Record a fresh SENT_UNCONFIRMED hand-off as pending a result."""
        self.pending[self._key(key)] = _PendingAttempt(
            attempt_id=attempt_id, started_at_ms=now_ms
        )

    def observe_result(self, key: InstrumentKey, *, attempt_id: str) -> None:
        """Clear the pending entry ONLY when it names the SAME attempt (independent review"""
        tracker_key = self._key(key)
        pending = self.pending.get(tracker_key)
        if pending is not None and pending.attempt_id == attempt_id:
            del self.pending[tracker_key]

    def due(self, *, now_ms: int) -> tuple[tuple[InstrumentKey, str], ...]:
        """Return ``(instrument_key, attempt_id)`` pairs whose wait bound has elapsed and have"""
        due: list[tuple[InstrumentKey, str]] = []
        for (account, instrument), pending in self.pending.items():
            if pending.timed_out:
                continue
            if now_ms - pending.started_at_ms >= self.max_send_result_wait_ms:
                pending.timed_out = True
                due.append(
                    (
                        InstrumentKey(account=account, instrument=instrument),
                        pending.attempt_id,
                    )
                )
        return tuple(due)
