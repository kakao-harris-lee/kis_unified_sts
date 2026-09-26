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

**Cadence (option 나).** Evaluate before every scheduler pass while the session is open (ticks
happen only then, and the tick interval is measured on evaluation readings, so the evaluation
cadence bounds the tick cadence); while closed, evaluate once per ``closed_interval_ms`` so the
opening is noticed within that interval. The session judgement itself reads the last evaluation,
so "stop evaluating while closed" would never see the session open — hence a slow cadence, not
none. The closed-interval clock is the process monotonic clock: it paces a loop, it is never a
trusted time reading and never reaches evidence or the kernel.

**An evaluation failure skips that pass's tick; it never stops the loop** (plan §2 W1-3). A
tick issued after a failed evaluation would carry the previous, stale reading. The pass is
reported to stderr (the runtime's refusal convention) and the next pass retries. Degradation
across repeated failures stays the time service's own rule — no second judgement is made here.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.*`` only.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

__all__ = ["TimeEvaluationPacer"]

_NS_PER_MS = 1_000_000


class TimeEvaluationPacer:
    """Decides, before each scheduler pass, whether to evaluate time health and whether the pass
    may tick (module docstring)."""

    def __init__(
        self,
        *,
        evaluate: Callable[[], object],
        session_is_open: Callable[[], bool],
        closed_interval_ms: int,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        """Wire the pacer.

        Args:
            evaluate: The time service's own ``evaluate`` (one health-check cycle).
            session_is_open: Whether the session is open at the last evaluation's reading.
            closed_interval_ms: The evaluation spacing while the session is closed
                (``marketfeed.yaml::time_evaluate_closed_interval_ms``).
            monotonic_ns: Injected monotonic clock — a test supplies a fake.

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
        self._session_is_open = session_is_open
        self._closed_interval_ns = closed_interval_ms * _NS_PER_MS
        self._monotonic_ns = monotonic_ns
        self._last_evaluated_ns: int | None = None

    def _due(self, now_ns: int) -> bool:
        if self._last_evaluated_ns is None or self._session_is_open():
            return True
        return now_ns - self._last_evaluated_ns >= self._closed_interval_ns

    def before_pass(self) -> bool:
        """Evaluate when due, and answer whether this pass may tick.

        Returns:
            ``False`` iff an evaluation was due and failed (never tick on a stale reading);
            ``True`` otherwise — including a closed-session pass that was not due, whose tick
            attempt reads the last (closed) evaluation and skips on the session gate.
        """
        now_ns = self._monotonic_ns()
        if not self._due(now_ns):
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
        self._last_evaluated_ns = now_ns
        return True
