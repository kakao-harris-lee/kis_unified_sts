"""``TimeEvaluationPacer`` — the periodic time-health evaluation the ``run`` loop owes the time"""

from __future__ import annotations

import sys
from collections.abc import Callable

__all__ = ["TimeEvaluationPacer"]


class TimeEvaluationPacer:
    """Decides, inside each scheduler pass and after its intake read, whether to evaluate time"""

    def __init__(
        self,
        *,
        evaluate: Callable[[], object],
        session_known_closed: Callable[[], bool],
        closed_interval_ms: int,
        monotonic_ms: Callable[[], int],
    ) -> None:
        """Wire the pacer."""
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
        """Evaluate when due, and answer whether this pass may go on to decide."""
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
