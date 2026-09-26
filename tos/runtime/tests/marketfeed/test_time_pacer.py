"""Hermetic unit tests for ``tos_runtime.marketfeed.time_pacer`` (plan
``docs/plans/2026-09-26-tos-periodic-time-eval-and-witness-wiring-plan.md`` §2 W1, operator
disposition §6.1-1 = option (나): evaluate every pass while the session is open, once per
``closed_interval_ms`` while it is closed; a failed evaluation skips that pass's tick).

Every collaborator is a fake — the monotonic clock is a counter this module advances by hand.
"""

from __future__ import annotations

import pytest
from tos_runtime.marketfeed.time_pacer import TimeEvaluationPacer


class _Harness:
    def __init__(
        self, *, is_open: bool | None, closed_interval_ms: int = 60_000
    ) -> None:
        self.now_ms = 0
        #: True open · False closed · None unknown (no trusted reading, no session context)
        self.is_open = is_open
        self.evaluations = 0
        self.fail_next = 0
        self.pacer = TimeEvaluationPacer(
            evaluate=self._evaluate,
            session_known_closed=lambda: self.is_open is False,
            closed_interval_ms=closed_interval_ms,
            monotonic_ms=lambda: self.now_ms,
        )

    def _evaluate(self) -> None:
        if self.fail_next:
            self.fail_next -= 1
            raise OSError("evidence append failed")
        self.evaluations += 1

    def advance_ms(self, ms: int) -> None:
        self.now_ms += ms


def test_open_session_evaluates_before_every_pass() -> None:
    h = _Harness(is_open=True)
    for _ in range(5):
        assert h.pacer.before_pass() is True
        h.advance_ms(1_000)
    assert h.evaluations == 5


def test_closed_session_evaluates_once_per_interval() -> None:
    """Mutation: drop the closed-interval gate -> 60 evaluations -> red."""
    h = _Harness(is_open=False)
    for _ in range(60):  # 60 one-second passes
        assert h.pacer.before_pass() is True
        h.advance_ms(1_000)
    # First pass (never evaluated) plus the pass at t=60 s is outside this window.
    assert h.evaluations == 1
    assert h.pacer.before_pass() is True  # t = 60 s
    assert h.evaluations == 2


def test_closed_to_open_is_seen_within_one_closed_interval() -> None:
    """The opening is noticed by the first evaluation after it — at most one closed interval
    late — and from then on every pass evaluates. Mutation: never evaluate while closed ->
    the opening is never seen -> red."""
    h = _Harness(is_open=False, closed_interval_ms=60_000)
    h.pacer.before_pass()  # t = 0, evaluated, closed
    # The venue opens at t = 30 s, but the session judgement reads the last evaluation, so the
    # harness keeps answering "closed" until an evaluation runs.
    h.advance_ms(30_000)
    h.pacer.before_pass()
    assert h.evaluations == 1
    h.advance_ms(30_000)  # t = 60 s — due
    h.is_open = True  # what the fresh evaluation now reports
    h.pacer.before_pass()
    assert h.evaluations == 2
    h.advance_ms(1_000)
    h.pacer.before_pass()
    assert h.evaluations == 3  # open: every pass


def test_failed_evaluation_skips_the_tick_and_retries_next_pass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Never tick on a stale reading; never stop the loop. Mutation: return True on failure ->
    red."""
    h = _Harness(is_open=True)
    h.fail_next = 1
    assert h.pacer.before_pass() is False
    assert "time evaluation failed" in capsys.readouterr().err
    h.advance_ms(1_000)
    assert h.pacer.before_pass() is True
    assert h.evaluations == 1


def test_failed_evaluation_while_closed_retries_on_the_next_pass() -> None:
    """A failure does not restart the closed interval — the next pass is still due."""
    h = _Harness(is_open=False)
    h.fail_next = 1
    assert h.pacer.before_pass() is False
    h.advance_ms(1_000)
    assert h.pacer.before_pass() is True
    assert h.evaluations == 1


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, None])
def test_non_positive_or_non_int_interval_is_refused(bad: object) -> None:
    with pytest.raises(ValueError):
        TimeEvaluationPacer(
            evaluate=lambda: None,
            session_known_closed=lambda: False,
            closed_interval_ms=bad,  # type: ignore[arg-type]
            monotonic_ms=lambda: 0,
        )


def test_unknown_session_is_paced_like_open_not_closed() -> None:
    """Review finding (PR #806): a degraded evaluation leaves no trusted reading, so no session
    context. Treating that as closed backed off to the 60 s interval while recovery needs
    consecutive evaluations — ticks stopped for minutes mid-session. Unknown evaluates every
    pass. Mutation: treat ``None`` as closed -> 1 evaluation -> red."""
    h = _Harness(is_open=None)
    for _ in range(5):
        assert h.pacer.before_pass() is True
        h.advance_ms(1_000)
    assert h.evaluations == 5
