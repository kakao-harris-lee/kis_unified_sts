"""``TimeEvaluationPacer`` — the periodic time-health evaluation the ``run`` loop owes the time
service (plan ``docs/plans/2026-09-26-tos-periodic-time-eval-and-witness-wiring-plan.md`` §2 W1,
operator disposition §6.1-1 = option (나)).

**Why this exists.** :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now`
returns the reading of the LAST :meth:`~tos_runtime.time.service.TrustworthyTimeService.evaluate`
cycle, and compose runs that cycle only at boot (``compose/_wiring.py``'s own "ongoing cycles
remain the caller's job" note). Without a caller that keeps evaluating, every wall-clock read in
``run`` is frozen at boot: :func:`~tos_runtime.marketfeed.scheduler.decide_tick` sees a zero
interval and answers ``SKIPPED_INTERVAL`` after the first tick, and a boot while the session is
closed never sees the session open.

**Cadence (option 나).** Evaluate once in every scheduler pass unless the session is KNOWN closed
(ticks happen only in an open session, and the tick interval is measured on evaluation readings,
so the evaluation cadence bounds the tick cadence); while known closed, evaluate once per
``closed_interval_ms`` so the opening is noticed within that interval. The session judgement
itself reads the last evaluation, so "stop evaluating while closed" would never see the session
open — hence a slow cadence, not none.

**Position inside the pass: after the intake read, before the decision** (plan
``docs/plans/2026-09-27-tos-freshness-read-order-plan.md`` §2.1; issue #809). :meth:`before_decide`
is named for that position. The pacing rules below are unchanged by the move — only *where*
``TickScheduler`` calls them is. Reading the journal before this evaluation is what keeps a line
appended between two passes from looking future-dated against a reading taken before it
(``scheduler.py``'s own read-order paragraph).

**Unknown is not closed** (review finding, PR #806). When the last evaluation left time
untrusted there is no reading, so no session context — that is "unknown", and it is paced like
open: recovering trust takes consecutive evaluations (SYNCHRONIZING → TRUSTED), and backing off
to the closed interval there would stop ticks for minutes in the middle of a session.

The closed-interval clock is the injected monotonic source (the SAME one the time service uses):
it paces a loop, it is never a trusted time reading and never reaches evidence or the kernel.

**An evaluation failure skips that pass's decision; it never stops the loop** (plan §2 W1-3). A
tick issued after a failed evaluation would carry the previous, stale reading. The pass is
reported to stderr (the runtime's refusal convention), the scheduler answers
``TickOutcome.SKIPPED_TIME_NOT_EVALUATED`` without consuming what it polled. ⚠ The next pass
retries on the same observation only when the intake re-serves it: either because its ``poll``
is a pure function of ``after_as_of_ms`` (the journal), or because it reads that argument as the
consumption signal and re-emits its still-pending quote (``kis_quote``) — the re-read is the
intake's property, never this pacer's (``ports.py``'s own ``SKIPPED_TIME_NOT_EVALUATED``
docstring). Degradation across repeated failures stays the time service's own rule — no second
judgement is made here.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.*`` only.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

__all__ = ["TimeEvaluationPacer"]


class TimeEvaluationPacer:
    """Decides, inside each scheduler pass and after its intake read, whether to evaluate time
    health and whether the pass may go on to decide (module docstring)."""

    def __init__(
        self,
        *,
        evaluate: Callable[[], object],
        session_known_closed: Callable[[], bool],
        closed_interval_ms: int,
        monotonic_ms: Callable[[], int],
    ) -> None:
        """Wire the pacer.

        Args:
            evaluate: The time service's own ``evaluate`` (one health-check cycle).
            session_known_closed: ``True`` only when the last evaluation's reading places the
                session closed — ``False`` when open AND when unknown (no trusted reading).
            closed_interval_ms: The evaluation spacing while the session is known closed
                (``marketfeed.yaml::time_evaluate_closed_interval_ms``).
            monotonic_ms: The injected monotonic clock (milliseconds).

        Raises:
            ValueError: ``closed_interval_ms`` is not a positive integer.
        """
        if (
            isinstance(closed_interval_ms, bool)
            or not isinstance(closed_interval_ms, int)
            or closed_interval_ms <= 0
        ):
            raise ValueError(
                "closed_interval_ms must be a positive integer, got "
                f"{closed_interval_ms!r}"
            )
        self._evaluate = evaluate
        self._session_known_closed = session_known_closed
        self._closed_interval_ms = closed_interval_ms
        self._monotonic_ms = monotonic_ms
        self._last_evaluated_ms: int | None = None

    def _due(self, now_ms: int) -> bool:
        if self._last_evaluated_ms is None or not self._session_known_closed():
            return True
        return now_ms - self._last_evaluated_ms >= self._closed_interval_ms

    def before_decide(self) -> bool:
        """Evaluate when due, and answer whether this pass may go on to decide.

        Returns:
            ``False`` iff an evaluation was due and failed (never decide on a stale reading);
            ``True`` otherwise — including a known-closed pass that was not due, whose decision
            reads the last (closed) evaluation and skips on the session gate.
        """
        now_ms = self._monotonic_ms()
        if not self._due(now_ms):
            return True
        try:
            self._evaluate()
        except Exception as exc:  # noqa: BLE001 - module docstring: never stop the loop
            print(
                "run: time evaluation failed, tick skipped this pass — "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return False
        self._last_evaluated_ms = now_ms
        return True
