"""``_TimeoutTracker`` — :class:`~tos_runtime.engine.driver.EngineDriver`'s per-scope pending-
attempt bookkeeping for timeout injection (module docstring item 4), factored out of
``engine/driver.py`` (size-budget discipline; mirrors the ``engine/finality_projection.py``
extraction from that same module).

Tracks, per scope, the monotonic reading at which a hand-off went ``POTENTIALLY_LIVE``/
``SENT_UNCONFIRMED`` with no result yet; once the injected ``max_send_result_wait_ms`` bound
elapses with no result, :meth:`_TimeoutTracker.due` reports it so the driver can enqueue a
synthetic ``EGRESS_RESULT(kind=TIMEOUT)`` (RFC-005 §11 "timeout = UNKNOWN, never rejection").

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine`` only.
"""

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

    #: The injected wait bound; always a concrete positive int (independent review finding #14
    #: — a ``None`` "disable injection entirely" escape hatch read as a fail-CLOSED default in
    #: the docstring it used to carry, but never injecting a TIMEOUT for a lost result is
    #: fail-SILENT (the attempt just sits ``SENT_UNCONFIRMED`` forever with no further evidence),
    #: not fail-closed. Compose has always supplied a concrete value anyway
    #: (``TrustworthyTimeConfig.max_send_result_wait_ms`` is itself non-optional and
    #: ``load_time_config`` refuses a null — ``time/config.py``), so this only removes an
    #: escape hatch nothing production-shaped ever used; a test that wants "never fires" now
    #: passes a very large bound instead of ``None``.
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
        """Clear the pending entry ONLY when it names the SAME attempt (independent review
        finding #7).

        Before this fix, ANY ``EGRESS_RESULT`` landing for the scope popped the pending entry —
        "applied or not", including a result naming a completely different (foreign/mismatched)
        attempt. The kernel itself refuses to apply such a result
        (``ResultDisposition.MISMATCHED_ATTEMPT`` / ``ORPHAN_NO_RESERVATION``), but the timeout
        watch for the GENUINELY pending attempt was silenced anyway — a lost result for the real
        attempt would then never surface as a ``TIMEOUT``, defeating the "결과 유실 ⇒ TIMEOUT"
        guarantee (plan §1.1) via any wrong-attempt-id result. Only an exact ``attempt_id`` match
        clears the watch now.
        """
        tracker_key = self._key(key)
        pending = self.pending.get(tracker_key)
        if pending is not None and pending.attempt_id == attempt_id:
            del self.pending[tracker_key]

    def due(self, *, now_ms: int) -> tuple[tuple[InstrumentKey, str], ...]:
        """Return ``(instrument_key, attempt_id)`` pairs whose wait bound has elapsed and have
        not already been timed out."""
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
