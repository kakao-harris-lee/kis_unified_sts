"""Hermetic unit tests for ``tos_runtime.marketfeed.scheduler`` (TOS tick-source wave, plan"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from tos.engine import time_admits
from tos.time import FreshnessVerdict, HealthState, SessionContext, freshness_verdict
from tos_runtime.marketfeed.ports import (
    MonotonicAnchoredObservation,
    RawObservation,
    TickOutcome,
)
from tos_runtime.marketfeed.scheduler import (
    MultiInstrumentRefused,
    PassBudget,
    TickDecision,
    TickResult,
    TickScheduler,
    decide_tick,
)
from tos_runtime.marketfeed.snapshot import SnapshotIssuer
from tos_runtime.marketfeed.store import SqliteSnapshotStore
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
from tos_runtime.time.config import TrustworthyTimeConfig

from ._fixtures import (
    BAR_ONE_AS_OF,
    CLOSE_BAR_ONE,
    INSTRUMENT,
    SCHEME,
    loaded_policy,
    observation,
)

_OPEN_SESSION = SessionContext(phase="CONTINUOUS", is_open=True)
_CLOSED_SESSION = SessionContext(phase="CLOSED", is_open=False)


def _observation(
    *, raw_event_id: str = "evt-1", as_of_ms: int = 1_000
) -> RawObservation:
    return RawObservation(
        raw_event_id=raw_event_id,
        instrument="ES",
        as_of_ms=as_of_ms,
        fields=(("close", 100),),
        source_id="test-source",
    )


def _decide(**overrides: object) -> TickDecision:
    """``decide_tick`` with a baseline of admitting values — one keyword override per test"""
    base: dict[str, object] = {
        "session_context": _OPEN_SESSION,
        "observations": (_observation(),),
        "latest_as_of_ms": None,
        "now_ms": 2_000,
        "last_tick_wall_clock_ms": None,
        "poll_interval_ms": 500,
    }
    base.update(overrides)
    return decide_tick(**base)  # type: ignore[arg-type]


def test_ticks_on_a_fresh_observation_with_an_open_session() -> None:
    decision = _decide()
    assert decision.outcome is TickOutcome.TICKED
    assert decision.observation is not None
    assert decision.observation.as_of_ms == 1_000


def test_skips_session_closed_when_session_is_positively_closed() -> None:
    decision = _decide(session_context=_CLOSED_SESSION)
    assert decision.outcome is TickOutcome.SKIPPED_SESSION_CLOSED
    assert decision.observation is None


def test_skips_session_closed_when_session_context_is_absent() -> None:
    """Absence is restrictive, never permissive (module docstring) — no wall-clock reading to"""
    decision = _decide(session_context=None)
    assert decision.outcome is TickOutcome.SKIPPED_SESSION_CLOSED


def test_skips_no_observation_when_the_batch_is_empty() -> None:
    decision = _decide(observations=())
    assert decision.outcome is TickOutcome.SKIPPED_NO_OBSERVATION
    assert decision.observation is None


def test_skips_not_newer_when_as_of_equals_the_store_high_water_mark() -> None:
    """The CIS's own distinctness obligation (module docstring; plan §5 mutation M2) —"""
    decision = _decide(
        observations=(_observation(as_of_ms=1_000),),
        latest_as_of_ms=1_000,
    )
    assert decision.outcome is TickOutcome.SKIPPED_NOT_NEWER


def test_skips_not_newer_when_as_of_is_older_than_the_store_high_water_mark() -> None:
    decision = _decide(
        observations=(_observation(as_of_ms=500),),
        latest_as_of_ms=1_000,
    )
    assert decision.outcome is TickOutcome.SKIPPED_NOT_NEWER


def test_ticks_when_as_of_is_strictly_newer_than_the_store_high_water_mark() -> None:
    decision = _decide(
        observations=(_observation(as_of_ms=1_500),),
        latest_as_of_ms=1_000,
    )
    assert decision.outcome is TickOutcome.TICKED
    assert decision.observation is not None
    assert decision.observation.as_of_ms == 1_500


def test_selects_the_newest_observation_among_a_batch() -> None:
    decision = _decide(
        observations=(
            _observation(raw_event_id="evt-1", as_of_ms=1_000),
            _observation(raw_event_id="evt-2", as_of_ms=3_000),
            _observation(raw_event_id="evt-3", as_of_ms=2_000),
        ),
    )
    assert decision.outcome is TickOutcome.TICKED
    assert decision.observation is not None
    assert decision.observation.raw_event_id == "evt-2"


def test_skips_interval_when_the_poll_interval_has_not_elapsed() -> None:
    decision = _decide(
        now_ms=2_000,
        last_tick_wall_clock_ms=1_800,
        poll_interval_ms=500,
    )
    assert decision.outcome is TickOutcome.SKIPPED_INTERVAL


def test_ticks_once_the_poll_interval_has_elapsed() -> None:
    decision = _decide(
        now_ms=2_400,
        last_tick_wall_clock_ms=1_800,
        poll_interval_ms=500,
    )
    assert decision.outcome is TickOutcome.TICKED


def test_ticks_when_now_ms_or_last_tick_is_unestablished() -> None:
    """The interval gate never fires when either wall-clock reading is unavailable — absence"""
    assert _decide(now_ms=None).outcome is TickOutcome.TICKED
    assert _decide(last_tick_wall_clock_ms=None).outcome is TickOutcome.TICKED


def test_session_gate_runs_before_the_no_observation_gate() -> None:
    """Check order (module docstring): session, then observation existence, then"""
    decision = _decide(session_context=_CLOSED_SESSION, observations=())
    assert decision.outcome is TickOutcome.SKIPPED_SESSION_CLOSED


def test_multi_instrument_refused_at_construction() -> None:
    """Plan §2 decision 8 / §5 mutation M9 — a config naming more than one instrument is"""
    with pytest.raises(MultiInstrumentRefused, match="FORWARD-OBLIGATION-MS1"):
        TickScheduler(
            instruments=("ES", "NQ"),
            instrument_class=None,  # type: ignore[arg-type]
            account=None,  # type: ignore[arg-type]
            direction=None,  # type: ignore[arg-type]
            quantity_basis=None,  # type: ignore[arg-type]
            unit=None,  # type: ignore[arg-type]
            policy=None,  # type: ignore[arg-type]
            scheme=None,  # type: ignore[arg-type]
            intake=None,  # type: ignore[arg-type]
            store=None,  # type: ignore[arg-type]
            time_projection=None,  # type: ignore[arg-type]
            time_service=None,  # type: ignore[arg-type]
            session_owner=None,  # type: ignore[arg-type]
            driver=None,
            inbox=None,  # type: ignore[arg-type]
            evidence_store=None,  # type: ignore[arg-type]
            poll_interval_ms=1_000,
        )


def test_multi_instrument_refused_on_an_empty_instruments_sequence() -> None:
    with pytest.raises(MultiInstrumentRefused):
        TickScheduler(
            instruments=(),
            instrument_class=None,  # type: ignore[arg-type]
            account=None,  # type: ignore[arg-type]
            direction=None,  # type: ignore[arg-type]
            quantity_basis=None,  # type: ignore[arg-type]
            unit=None,  # type: ignore[arg-type]
            policy=None,  # type: ignore[arg-type]
            scheme=None,  # type: ignore[arg-type]
            intake=None,  # type: ignore[arg-type]
            store=None,  # type: ignore[arg-type]
            time_projection=None,  # type: ignore[arg-type]
            time_service=None,  # type: ignore[arg-type]
            session_owner=None,  # type: ignore[arg-type]
            driver=None,
            inbox=None,  # type: ignore[arg-type]
            evidence_store=None,  # type: ignore[arg-type]
            poll_interval_ms=1_000,
        )


def _build_scheduler(
    tmp_path: Path,
    *,
    poll_interval_ms: int,
    before_decide: Callable[[], bool] | None = None,
    after_pass: Callable[[], None] | None = None,
    pass_budget: PassBudget | None = None,
    evidence_store: Any = None,
    intake: Any = None,
    store: Any = None,
    time_service: Any = None,
    session_owner: Any = None,
    time_projection: Any = None,
) -> TickScheduler:
    """A real :class:`TickScheduler`, built with the real"""
    return TickScheduler(
        instruments=(INSTRUMENT,),
        instrument_class="krx-index-futures",
        account="acct-run-forever",
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        policy=loaded_policy(tmp_path),
        scheme=SCHEME,
        intake=intake if intake is not None else MagicMock(),
        store=store if store is not None else MagicMock(),
        time_projection=(
            time_projection if time_projection is not None else MagicMock()
        ),
        time_service=time_service if time_service is not None else MagicMock(),
        session_owner=session_owner if session_owner is not None else MagicMock(),
        driver=None,
        inbox=MagicMock(),
        evidence_store=(evidence_store if evidence_store is not None else MagicMock()),
        poll_interval_ms=poll_interval_ms,
        before_decide=before_decide,
        after_pass=after_pass,
        pass_budget=pass_budget,
    )


def _stop_after(n: int):
    """A ``stop`` double that returns ``False`` for its first ``n`` calls, then ``True`` —"""
    calls = {"count": 0}

    def stop() -> bool:
        if calls["count"] >= n:
            return True
        calls["count"] += 1
        return False

    return stop


def test_run_forever_calls_tick_once_n_times_and_sleeps_the_configured_interval(
    tmp_path: Path,
) -> None:
    """Pins the loop's own thinness (team-lead review finding, 2026-09-16: ``run_forever`` had"""
    scheduler = _build_scheduler(tmp_path, poll_interval_ms=750)

    tick_calls = 0

    def fake_tick_once() -> TickResult:
        nonlocal tick_calls
        tick_calls += 1
        return TickResult(outcome=TickOutcome.SKIPPED_NO_OBSERVATION)

    scheduler.tick_once = fake_tick_once  # type: ignore[method-assign]

    sleep_calls: list[float] = []
    scheduler.run_forever(sleep=sleep_calls.append, stop=_stop_after(3))

    assert tick_calls == 3
    assert sleep_calls == [0.75, 0.75, 0.75]


def test_run_forever_calls_nothing_but_tick_once_and_sleep(tmp_path: Path) -> None:
    """Plan 2026-09-27 §2.1 (issue #809): the ``before_decide`` hook moved INSIDE ``tick_once``,"""
    hook_calls = 0

    def before_decide() -> bool:
        nonlocal hook_calls
        hook_calls += 1
        return False

    scheduler = _build_scheduler(
        tmp_path, poll_interval_ms=750, before_decide=before_decide
    )
    tick_calls = 0

    def fake_tick_once() -> TickResult:
        nonlocal tick_calls
        tick_calls += 1
        return TickResult(outcome=TickOutcome.SKIPPED_NO_OBSERVATION)

    scheduler.tick_once = fake_tick_once  # type: ignore[method-assign]
    sleep_calls: list[float] = []
    scheduler.run_forever(sleep=sleep_calls.append, stop=_stop_after(3))

    assert tick_calls == 3
    assert hook_calls == 0
    assert sleep_calls == [0.75, 0.75, 0.75]


def test_run_forever_runs_the_after_pass_hook_once_per_pass_after_the_tick(
    tmp_path: Path,
) -> None:
    """Order within a pass: ``tick_once`` -> ``after_pass`` -> ``sleep``, once each."""
    order: list[str] = []
    scheduler = _build_scheduler(
        tmp_path, poll_interval_ms=750, after_pass=lambda: order.append("after")
    )

    def fake_tick_once() -> TickResult:
        order.append("tick")
        return TickResult(outcome=TickOutcome.TICKED)

    scheduler.tick_once = fake_tick_once  # type: ignore[method-assign]
    scheduler.run_forever(
        sleep=lambda seconds: order.append(f"sleep:{seconds}"), stop=_stop_after(2)
    )

    assert order == ["tick", "after", "sleep:0.75"] * 2


def test_run_forever_runs_the_after_pass_hook_on_a_pass_that_produced_no_tick(
    tmp_path: Path,
) -> None:
    """A shut market is exactly when this must still run: ``tick_once`` returns"""
    hook_calls = 0

    def after_pass() -> None:
        nonlocal hook_calls
        hook_calls += 1

    scheduler = _build_scheduler(tmp_path, poll_interval_ms=400, after_pass=after_pass)
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.SKIPPED_SESSION_CLOSED
    )

    scheduler.run_forever(sleep=lambda _seconds: None, stop=_stop_after(3))

    assert hook_calls == 3


def test_a_raising_after_pass_hook_propagates_and_stops_the_loop(
    tmp_path: Path,
) -> None:
    """The same answer this module already gives for an unwritable evidence store"""
    ticks = 0

    def fake_tick_once() -> TickResult:
        nonlocal ticks
        ticks += 1
        return TickResult(outcome=TickOutcome.TICKED)

    def after_pass() -> None:
        raise RuntimeError("evidence store is unwritable")

    sleep_calls: list[float] = []
    scheduler = _build_scheduler(tmp_path, poll_interval_ms=400, after_pass=after_pass)
    scheduler.tick_once = fake_tick_once  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="unwritable"):
        scheduler.run_forever(sleep=sleep_calls.append, stop=_stop_after(3))

    assert ticks == 1
    assert sleep_calls == []


def test_tick_once_itself_never_runs_the_after_pass_hook(tmp_path: Path) -> None:
    """The hook belongs to the LOOP, not to a pass: a caller driving ``tick_once`` directly"""
    hook_calls = 0

    def after_pass() -> None:
        nonlocal hook_calls
        hook_calls += 1

    intake = MagicMock()
    intake.poll.return_value = (_observation(),)
    store = MagicMock()
    store.latest_as_of.return_value = None
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=lambda: False,
        after_pass=after_pass,
        intake=intake,
        store=store,
    )

    assert scheduler.tick_once().outcome is TickOutcome.SKIPPED_TIME_NOT_EVALUATED
    assert hook_calls == 0


class _SteppingMonotonic:
    """A monotonic source that advances by a scripted amount per reading — ``run_forever``"""

    def __init__(self, steps: list[int]) -> None:
        self._steps = steps
        self.value = 0
        self.reads = 0

    def now_ms(self) -> int:
        reading = self.value
        self.reads += 1
        self.value += self._steps[min(self.reads - 1, len(self._steps) - 1)]
        return reading


def _overrun_rows(evidence_store: Any) -> list[dict[str, Any]]:
    return [
        call.args[0]
        for call in evidence_store.append.call_args_list
        if call.kwargs.get("kind") == "MARKETFEED_PASS_OVERRUN"
    ]


def test_a_pass_that_outruns_the_reserved_window_records_both_halves(
    tmp_path: Path,
) -> None:
    """The row names the tick's share and the hook's share separately, against the window they"""
    monotonic = _SteppingMonotonic([10, 600, 0])
    evidence_store = MagicMock()
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        after_pass=lambda: None,
        pass_budget=PassBudget(monotonic=monotonic, allowance_ms=100),
        evidence_store=evidence_store,
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    scheduler.run_forever(sleep=lambda _s: None, stop=_stop_after(1))

    (row,) = _overrun_rows(evidence_store)
    assert row == {
        "instrument": INSTRUMENT,
        "budget_ms": 500,
        "pass_ms": 610,
        "tick_ms": 10,
        "after_pass_ms": 600,
        "poll_interval_ms": 400,
        "pass_allowance_ms": 100,
    }


def test_a_pass_the_compensation_absorbs_is_not_an_overrun(tmp_path: Path) -> None:
    """#949 r2 MEDIUM-3, the behaviour change: a 210 ms pass on a 400 ms interval is longer"""
    monotonic = _SteppingMonotonic([10, 200, 0])
    evidence_store = MagicMock()
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        after_pass=lambda: None,
        pass_budget=PassBudget(monotonic=monotonic, allowance_ms=100),
        evidence_store=evidence_store,
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    scheduler.run_forever(sleep=lambda _s: None, stop=_stop_after(1))

    assert _overrun_rows(evidence_store) == []


def test_the_sleep_is_shortened_by_what_the_pass_already_spent(tmp_path: Path) -> None:
    """#949 review HIGH, the fix itself: bar ages are measured against the tick-to-tick PERIOD,"""
    monotonic = _SteppingMonotonic([10, 200, 0])
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        after_pass=lambda: None,
        pass_budget=PassBudget(monotonic=monotonic, allowance_ms=1_000),
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    sleeps: list[float] = []
    scheduler.run_forever(sleep=sleeps.append, stop=_stop_after(1))

    assert sleeps == [0.19]


def test_a_pass_that_outran_the_whole_interval_sleeps_zero_not_negative(
    tmp_path: Path,
) -> None:
    """Clamped, never carried forward: the next pass starts at once (the overrun is already"""
    monotonic = _SteppingMonotonic([500, 100, 0])
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        after_pass=lambda: None,
        pass_budget=PassBudget(monotonic=monotonic, allowance_ms=1_000),
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    sleeps: list[float] = []
    scheduler.run_forever(sleep=sleeps.append, stop=_stop_after(1))

    assert sleeps == [0.0]


def test_without_a_pass_budget_the_sleep_is_the_plain_interval(tmp_path: Path) -> None:
    """No clock, no compensation — the pre-#949 loop, unchanged (and what a ``kis_quote``"""
    scheduler = _build_scheduler(
        tmp_path, poll_interval_ms=750, after_pass=lambda: None
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    sleeps: list[float] = []
    scheduler.run_forever(sleep=sleeps.append, stop=_stop_after(2))

    assert sleeps == [0.75, 0.75]


def test_a_pass_inside_its_budget_records_nothing(tmp_path: Path) -> None:
    """A healthy session must not pay an evidence append per pass."""
    monotonic = _SteppingMonotonic([5, 5, 0])
    evidence_store = MagicMock()
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        pass_budget=PassBudget(monotonic=monotonic, allowance_ms=100),
        evidence_store=evidence_store,
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    scheduler.run_forever(sleep=lambda _s: None, stop=_stop_after(3))

    assert _overrun_rows(evidence_store) == []


def test_without_a_pass_budget_the_loop_reads_no_clock_and_records_nothing(
    tmp_path: Path,
) -> None:
    """``pass_budget=None`` is the pre-#949 scheduler, unchanged: no measurement, no row — and"""
    evidence_store = MagicMock()
    scheduler = _build_scheduler(
        tmp_path, poll_interval_ms=400, evidence_store=evidence_store
    )
    scheduler.tick_once = lambda: TickResult(  # type: ignore[method-assign]
        outcome=TickOutcome.TICKED
    )

    scheduler.run_forever(sleep=lambda _s: None, stop=_stop_after(2))

    assert _overrun_rows(evidence_store) == []
    evidence_store.append.assert_not_called()


def test_tick_once_reports_time_not_evaluated_after_polling_and_consumes_nothing(
    tmp_path: Path,
) -> None:
    """A ``False`` from ``before_decide`` (the evaluation was due and failed) is a NAMED absence"""
    intake = MagicMock()
    intake.poll.return_value = (_observation(),)
    store = MagicMock()
    store.latest_as_of.return_value = None
    time_service = MagicMock()
    session_owner = MagicMock()

    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=lambda: False,
        intake=intake,
        store=store,
        time_service=time_service,
        session_owner=session_owner,
    )

    result = scheduler.tick_once()

    assert result.outcome is TickOutcome.SKIPPED_TIME_NOT_EVALUATED
    assert result.queued_until_recovery is False
    assert result.value_view is None
    intake.poll.assert_called_once_with(instrument=INSTRUMENT, after_as_of_ms=None)
    store.put.assert_not_called()
    time_service.wall_clock_now.assert_not_called()
    session_owner.session_context.assert_not_called()


_EVALUATION_STEP_MS = 500
_APPENDED_AFTER_MS = 200
_START_READING_MS = 1_790_557_200_000

_READ_ORDER_INSTRUMENT_CLASS = "krx-index-futures"


class _AdvancingTimeService:
    """A time service whose ``evaluate()`` advances the reading ``wall_clock_now()`` returns."""

    def __init__(self, *, start_ms: int, step_ms: int) -> None:
        self._reading = start_ms
        self._step = step_ms
        self.evaluations = 0
        self.health_state = HealthState.TRUSTED

    def evaluate(self) -> None:
        self.evaluations += 1
        self._reading += self._step

    def wall_clock_now(self) -> int:
        return self._reading


class _OpenSessionOwner:
    """A narrow double for the one method the scheduler and the time projection both read."""

    def __init__(self) -> None:
        self.context = SessionContext(
            tz_id="Asia/Seoul",
            tz_db_version="2026c",
            trading_calendar_version="krx-2026.09.1",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=None,
        )

    def session_context(self, instrument_class: str) -> SessionContext:
        del instrument_class
        return self.context


class _CapturingDriver:
    """A driver double that records the event it was handed — the tick payload (and therefore its"""

    def __init__(self) -> None:
        self.events: list[object] = []

    def enqueue_and_run(self, event: object) -> None:
        self.events.append(event)


class _SessionOpeningBetweenReadingsOwner:
    """A session owner that answers from the time service's CURRENT reading rather than holding a"""

    def __init__(
        self, time_service: _AdvancingTimeService, *, opens_at_ms: int
    ) -> None:
        self._time_service = time_service
        self._opens_at_ms = opens_at_ms

    def session_context(self, instrument_class: str) -> SessionContext:
        del instrument_class
        return SessionContext(
            tz_id="Asia/Seoul",
            tz_db_version="2026c",
            trading_calendar_version="krx-2026.09.1",
            phase=(
                "CONTINUOUS"
                if self._time_service.wall_clock_now() >= self._opens_at_ms
                else "CLOSED"
            ),
            is_open=self._time_service.wall_clock_now() >= self._opens_at_ms,
            tz_version_conflict=False,
            boundary_value=None,
        )


class _StampedSinceLastEvaluationIntake:
    """An intake that stamps each polled observation ``as_of = wall_clock_now() +"""

    def __init__(self, time_service: _AdvancingTimeService) -> None:
        self._time_service = time_service
        self._seq = 0

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> tuple[RawObservation, ...]:
        del instrument
        as_of_ms = self._time_service.wall_clock_now() + _APPENDED_AFTER_MS
        if after_as_of_ms is not None and as_of_ms <= after_as_of_ms:
            return ()
        self._seq += 1
        return (_read_order_observation(f"appended-{self._seq}", as_of_ms),)


_STALE_BY_MS = 10_000


class _StaleIntake:
    """An intake whose line is already older than the policy's freshness bound when the pass"""

    def __init__(self, time_service: _AdvancingTimeService) -> None:
        self._time_service = time_service

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> tuple[RawObservation, ...]:
        del instrument, after_as_of_ms
        as_of_ms = self._time_service.wall_clock_now() - _STALE_BY_MS
        return (_read_order_observation("stale-1", as_of_ms),)


class _FixedObservationIntake:
    """One unchanging observation, filtered the way"""

    def __init__(self, *, as_of_ms: int) -> None:
        self.as_of_ms = as_of_ms
        self.polls: list[int | None] = []

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> tuple[RawObservation, ...]:
        del instrument
        self.polls.append(after_as_of_ms)
        if after_as_of_ms is not None and self.as_of_ms <= after_as_of_ms:
            return ()
        return (_read_order_observation("fixed-1", self.as_of_ms),)


def _read_order_observation(raw_event_id: str, as_of_ms: int) -> RawObservation:
    """An observation carrying both fields ``_fixtures.VALID_POLICY_YAML`` declares, so the"""
    return RawObservation(
        raw_event_id=raw_event_id,
        instrument=INSTRUMENT,
        as_of_ms=as_of_ms,
        fields=(("close", CLOSE_BAR_ONE), ("session", "REGULAR")),
        source_id="read-order-collector",
    )


def _read_order_time_config() -> TrustworthyTimeConfig:
    """``config/tos_runtime/paper/time.yaml``'s own approved values (the deployment this defect"""
    return TrustworthyTimeConfig(
        max_time_source_precision_ms=50,
        max_time_transport_and_queue_uncertainty_ms=50,
        max_time_conservative_freshness_age_ms=1000,
        max_future_timestamp_tolerance_ms=50,
        max_process_suspension_ms=2000,
        max_time_source_disagreement_ms=50,
        min_time_independent_reference_count=1,
        max_clock_domain_conversion_uncertainty_ms=50,
        max_send_result_wait_ms=2000,
        max_critical_input_consumer_receipt_age_ms=1000,
        max_time_source_sequence_gap_ms=50,
        tz_db_version="2026c",
        trading_calendar_version="krx-2026.09.1",
        verification_profile_version="VERIFICATION-PROFILE-002-v2.1",
        safety_profile_version="tos-paper-profile-g1",
        time_health_snapshot_heartbeat_ms=60_000,
    )


def _read_order_scheduler(
    tmp_path: Path,
    *,
    time_service: _AdvancingTimeService,
    intake: object,
    store: SqliteSnapshotStore,
    driver: _CapturingDriver,
    before_decide: Callable[[], bool] | None = None,
    session_owner: object | None = None,
    evidence_store: Any = None,
) -> TickScheduler:
    """A :class:`TickScheduler` whose snapshot store, policy, issuers, time projection and kernel"""
    config = _read_order_time_config()
    if session_owner is None:
        session_owner = _OpenSessionOwner()

    def evaluate_then_admit() -> bool:
        time_service.evaluate()
        return True

    return TickScheduler(
        instruments=(INSTRUMENT,),
        instrument_class=_READ_ORDER_INSTRUMENT_CLASS,
        account="acct-read-order",
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        policy=loaded_policy(tmp_path),
        scheme=SCHEME,
        intake=intake,  # type: ignore[arg-type]
        store=store,
        time_projection=RuntimeTimeProjection(
            config=config,
            time_service=time_service,  # type: ignore[arg-type]
            session_owner=session_owner,  # type: ignore[arg-type]
            instrument_class=_READ_ORDER_INSTRUMENT_CLASS,
            snapshot_age_bound=20,
            interval_width=10,
        ),
        time_service=time_service,  # type: ignore[arg-type]
        session_owner=session_owner,  # type: ignore[arg-type]
        driver=driver,  # type: ignore[arg-type]
        inbox=MagicMock(),
        evidence_store=(evidence_store if evidence_store is not None else MagicMock()),
        poll_interval_ms=400,
        before_decide=(
            before_decide if before_decide is not None else evaluate_then_admit
        ),
    )


def test_an_observation_appended_since_the_last_evaluation_reads_fresh_not_conflicted(
    tmp_path: Path,
) -> None:
    """THE #809 regression. A collector appends a line stamped 200 ms after the reading the time"""
    time_service = _AdvancingTimeService(
        start_ms=_START_READING_MS, step_ms=_EVALUATION_STEP_MS
    )
    driver = _CapturingDriver()
    store = SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3")
    scheduler = _read_order_scheduler(
        tmp_path,
        time_service=time_service,
        intake=_StampedSinceLastEvaluationIntake(time_service),
        store=store,
        driver=driver,
    )

    result = scheduler.tick_once()

    assert result.outcome is TickOutcome.TICKED
    assert time_service.evaluations == 1
    assert len(driver.events) == 1
    time_inputs = driver.events[0].decision_tick.time  # type: ignore[attr-defined]
    assert time_inputs.source_age == _EVALUATION_STEP_MS - _APPENDED_AFTER_MS
    assert (
        freshness_verdict(
            source_age=time_inputs.source_age,
            delay_bounds=time_inputs.delay_bounds,
            max_age_bound=time_inputs.max_age_bound,
            future_tolerance=time_inputs.future_tolerance,
        )
        is FreshnessVerdict.FRESH
    )
    admitted, reason = time_admits(time_inputs)
    assert admitted is True, f"expected admission, got reason: {reason!r}"

    assert (
        scheduler._last_tick_wall_clock_ms  # noqa: SLF001 — see the docstring's last paragraph
        == _START_READING_MS + _EVALUATION_STEP_MS
    )

    store.close()


def test_a_session_that_opens_during_the_pass_is_seen_by_that_pass_not_the_next(
    tmp_path: Path,
) -> None:
    """The success path's half of #809: ``now_ms`` AND the session context are read AFTER the"""
    time_service = _AdvancingTimeService(
        start_ms=_START_READING_MS, step_ms=_EVALUATION_STEP_MS
    )
    driver = _CapturingDriver()
    store = SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3")
    scheduler = _read_order_scheduler(
        tmp_path,
        time_service=time_service,
        intake=_FixedObservationIntake(as_of_ms=_START_READING_MS),
        store=store,
        driver=driver,
        session_owner=_SessionOpeningBetweenReadingsOwner(
            time_service, opens_at_ms=_START_READING_MS + 1
        ),
    )

    result = scheduler.tick_once()

    assert result.outcome is TickOutcome.TICKED
    assert len(driver.events) == 1
    assert (
        scheduler._last_tick_wall_clock_ms  # noqa: SLF001 — the only surviving copy of now_ms
        == _START_READING_MS + _EVALUATION_STEP_MS
    )

    store.close()


def test_a_failed_evaluation_leaves_the_observation_for_the_next_pass(
    tmp_path: Path,
) -> None:
    """The consequence of skipping WITHOUT a ``store.put`` (``ports.py``'s own"""
    time_service = _AdvancingTimeService(
        start_ms=_START_READING_MS, step_ms=_EVALUATION_STEP_MS
    )
    driver = _CapturingDriver()
    store = SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3")
    intake = _FixedObservationIntake(as_of_ms=_START_READING_MS + _APPENDED_AFTER_MS)
    answers = iter([False, True])

    def before_decide() -> bool:
        time_service.evaluate()
        return next(answers)

    scheduler = _read_order_scheduler(
        tmp_path,
        time_service=time_service,
        intake=intake,
        store=store,
        driver=driver,
        before_decide=before_decide,
    )

    first = scheduler.tick_once()
    assert first.outcome is TickOutcome.SKIPPED_TIME_NOT_EVALUATED
    assert driver.events == []
    assert store.latest_as_of(instrument=INSTRUMENT) is None

    second = scheduler.tick_once()
    assert second.outcome is TickOutcome.TICKED
    assert intake.polls == [
        None,
        None,
    ]
    assert store.latest_as_of(instrument=INSTRUMENT) == intake.as_of_ms
    assert len(driver.events) == 1

    store.close()


def _real_time_projection(
    time_service: Any, session_owner: Any
) -> RuntimeTimeProjection:
    """The REAL projection over the paper-shaped config ``_read_order_time_config`` already"""
    return RuntimeTimeProjection(
        config=_read_order_time_config(),
        time_service=time_service,
        session_owner=session_owner,
        instrument_class=_READ_ORDER_INSTRUMENT_CLASS,
        snapshot_age_bound=20,
        interval_width=10,
    )


def _pending(
    *, requested_monotonic_ms: int = 1_000, received_monotonic_ms: int = 1_180
) -> MonotonicAnchoredObservation:
    return MonotonicAnchoredObservation(
        instrument=INSTRUMENT,
        fields=(("close", CLOSE_BAR_ONE), ("session", "REGULAR")),
        source_id="kis-quote-test",
        content_digest="d" * 64,
        requested_monotonic_ms=requested_monotonic_ms,
        received_monotonic_ms=received_monotonic_ms,
    )


def test_tick_once_anchors_a_pending_observation_on_the_request_instant(
    tmp_path: Path,
) -> None:
    """The mapping is asked for BOTH instants and the REQUEST one becomes ``as_of_ms`` —"""
    intake = MagicMock()
    intake.poll.return_value = (_pending(),)
    store = MagicMock()
    store.latest_as_of.return_value = None
    time_service = MagicMock()
    mapped = {1_000: 1_790_000_000_000, 1_180: 1_790_000_000_180}
    time_service.wall_clock_at_monotonic.side_effect = lambda mono_ms: mapped[mono_ms]
    time_service.wall_clock_now.return_value = 1_790_000_000_200
    time_service.health_state = HealthState.TRUSTED
    session_owner = MagicMock()
    session_owner.session_context.return_value = _OPEN_SESSION

    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=lambda: True,
        intake=intake,
        store=store,
        time_service=time_service,
        session_owner=session_owner,
        time_projection=_real_time_projection(time_service, session_owner),
    )
    scheduler.tick_once()

    store.put.assert_called_once()
    issued = store.put.call_args.args[0]
    assert issued.observations[0].time.source_event_time == 1_790_000_000_000


def test_tick_once_reports_time_unanchored_when_the_mapping_is_unavailable(
    tmp_path: Path,
) -> None:
    """``before_decide`` SUCCEEDED and the pass still cannot place the observation on the wall"""
    intake = MagicMock()
    intake.poll.return_value = (_pending(),)
    store = MagicMock()
    store.latest_as_of.return_value = None
    time_service = MagicMock()
    time_service.wall_clock_at_monotonic.return_value = None
    session_owner = MagicMock()
    session_owner.session_context.return_value = _OPEN_SESSION
    hook_calls = 0

    def before_decide() -> bool:
        nonlocal hook_calls
        hook_calls += 1
        return True

    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=before_decide,
        intake=intake,
        store=store,
        time_service=time_service,
        session_owner=session_owner,
    )

    result = scheduler.tick_once()

    assert result.outcome is TickOutcome.SKIPPED_TIME_UNANCHORED
    assert result.queued_until_recovery is False
    assert result.value_view is None
    assert hook_calls == 1
    store.put.assert_not_called()
    session_owner.session_context.assert_called_once()


def test_a_closed_session_is_reported_as_closed_not_as_unanchored(
    tmp_path: Path,
) -> None:
    """PR #812 review (MEDIUM). The shape a deployed ``kis_quote`` pass actually has outside"""
    intake = MagicMock()
    intake.poll.return_value = (_pending(),)
    store = MagicMock()
    store.latest_as_of.return_value = None
    time_service = MagicMock()
    time_service.wall_clock_at_monotonic.return_value = None
    session_owner = MagicMock()
    session_owner.session_context.return_value = _CLOSED_SESSION
    hook_calls = 0

    def before_decide() -> bool:
        """The pacer's not-due answer: admit the pass, evaluate nothing."""
        nonlocal hook_calls
        hook_calls += 1
        return True

    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=before_decide,
        intake=intake,
        store=store,
        time_service=time_service,
        session_owner=session_owner,
    )

    result = scheduler.tick_once()

    assert result.outcome is TickOutcome.SKIPPED_SESSION_CLOSED
    assert result.queued_until_recovery is False
    assert result.value_view is None
    assert hook_calls == 1
    store.put.assert_not_called()
    time_service.wall_clock_at_monotonic.assert_not_called()


def test_one_unmappable_observation_withholds_the_whole_batch(tmp_path: Path) -> None:
    """All-or-nothing (``_anchor_polled``'s own docstring): a batch silently reduced to its"""
    intake = MagicMock()
    intake.poll.return_value = (
        _pending(requested_monotonic_ms=1_000, received_monotonic_ms=1_100),
        _pending(requested_monotonic_ms=2_000, received_monotonic_ms=2_100),
    )
    store = MagicMock()
    store.latest_as_of.return_value = None
    time_service = MagicMock()
    time_service.wall_clock_at_monotonic.side_effect = lambda mono_ms: (
        None if mono_ms >= 2_000 else 1_790_000_000_000 + mono_ms
    )
    session_owner = MagicMock()
    session_owner.session_context.return_value = _OPEN_SESSION
    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=lambda: True,
        intake=intake,
        store=store,
        time_service=time_service,
        session_owner=session_owner,
    )

    assert scheduler.tick_once().outcome is TickOutcome.SKIPPED_TIME_UNANCHORED
    store.put.assert_not_called()


def test_a_raw_observation_is_never_re_anchored(tmp_path: Path) -> None:
    """The journal's own collector measured a real source event time; this module does not"""
    intake = MagicMock()
    intake.poll.return_value = (_observation(as_of_ms=1_790_000_000_000),)
    store = MagicMock()
    store.latest_as_of.return_value = None
    time_service = MagicMock()
    time_service.wall_clock_now.return_value = 1_790_000_000_500
    time_service.health_state = HealthState.TRUSTED
    session_owner = MagicMock()
    session_owner.session_context.return_value = _OPEN_SESSION

    scheduler = _build_scheduler(
        tmp_path,
        poll_interval_ms=400,
        before_decide=lambda: True,
        intake=intake,
        store=store,
        time_service=time_service,
        session_owner=session_owner,
        time_projection=_real_time_projection(time_service, session_owner),
    )
    scheduler.tick_once()

    time_service.wall_clock_at_monotonic.assert_not_called()
    store.put.assert_called_once()
    issued = store.put.call_args.args[0]
    assert issued.observations[0].time.source_event_time == 1_790_000_000_000


class TestTheFieldRefusalRow:
    """``MARKETFEED_FIELD_REFUSED`` — why an issued snapshot refused fields, in the store."""

    def _scheduler_with_capture(
        self, tmp_path: Path
    ) -> tuple[TickScheduler, list[tuple[dict[str, Any], str]]]:
        rows: list[tuple[dict[str, Any], str]] = []
        evidence = MagicMock()
        evidence.append.side_effect = lambda payload, **kw: rows.append(
            (payload, kw["kind"])
        )
        scheduler = TickScheduler(
            instruments=(INSTRUMENT,),
            instrument_class="krx-index-futures",
            account="acct-field-refusal",
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
            policy=loaded_policy(tmp_path),
            scheme=SCHEME,
            intake=MagicMock(),
            store=MagicMock(),
            time_projection=MagicMock(),
            time_service=MagicMock(),
            session_owner=MagicMock(),
            driver=None,
            inbox=MagicMock(),
            evidence_store=evidence,
            poll_interval_ms=400,
        )
        return scheduler, rows

    def _issue(self, tmp_path: Path, *, now_ms: int | None):
        """A REAL :class:`~tos_runtime.marketfeed.snapshot.SnapshotIssuer` run — the reason"""
        obs = observation()
        issued = SnapshotIssuer(
            policy=loaded_policy(tmp_path), scheme=SCHEME, account="acct-field-refusal"
        ).issue(obs, now_ms=now_ms)
        return obs, issued

    def test_a_stale_bar_records_both_sides_of_the_comparison(
        self, tmp_path: Path
    ) -> None:
        """The 2026-10-22 shape: a usable value refused on AGE. The fixture policy's bound is"""
        scheduler, rows = self._scheduler_with_capture(tmp_path)
        stale_now_ms = BAR_ONE_AS_OF + 10_000
        obs, issued = self._issue(tmp_path, now_ms=stale_now_ms)

        scheduler._record_field_refusals(issued, obs, now_ms=stale_now_ms)

        payload, kind = rows[0]
        assert len(rows) == 1
        assert kind == "MARKETFEED_FIELD_REFUSED"
        assert payload["raw_event_id"] == obs.raw_event_id
        assert payload["as_of_ms"] == BAR_ONE_AS_OF
        assert payload["evaluated_at_ms"] == stale_now_ms
        assert payload["age_ms"] == 10_000
        assert payload["stale_max_age_ms"] == [5_000]
        assert payload["refused_by_reason"] == {"stale": ["close", "session"]}
        assert (payload["fields_declared"], payload["fields_refused"]) == (2, 2)

    def test_a_fresh_bar_records_nothing(self, tmp_path: Path) -> None:
        """Diagnostics, not a log: the row exists only where there is something to explain."""
        scheduler, rows = self._scheduler_with_capture(tmp_path)
        obs, issued = self._issue(tmp_path, now_ms=BAR_ONE_AS_OF + 10)

        scheduler._record_field_refusals(issued, obs, now_ms=BAR_ONE_AS_OF + 10)

        assert rows == []

    def test_an_unestablished_clock_is_named_and_the_age_stays_absent(
        self, tmp_path: Path
    ) -> None:
        """The OTHER branch the 2026-10-22 investigation could not rule out from the store."""
        scheduler, rows = self._scheduler_with_capture(tmp_path)
        obs, issued = self._issue(tmp_path, now_ms=None)

        scheduler._record_field_refusals(issued, obs, now_ms=None)

        payload, _kind = rows[0]
        assert payload["refused_by_reason"] == {"now_ms_unknown": ["close", "session"]}
        assert payload["age_ms"] is None
        assert payload["evaluated_at_ms"] is None
        assert payload["stale_max_age_ms"] == []

    def test_the_row_is_written_on_the_real_tick_path(self, tmp_path: Path) -> None:
        """Wiring, not just a callable method: a REAL ``tick_once`` over a REAL store, policy,"""
        rows: list[tuple[dict[str, Any], str]] = []
        evidence = MagicMock()
        evidence.append.side_effect = lambda payload, **kw: rows.append(
            (payload, kw["kind"])
        )
        time_service = _AdvancingTimeService(
            start_ms=_START_READING_MS, step_ms=_EVALUATION_STEP_MS
        )
        scheduler = _read_order_scheduler(
            tmp_path,
            time_service=time_service,
            intake=_StaleIntake(time_service),
            store=SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3"),
            driver=_CapturingDriver(),
            evidence_store=evidence,
        )

        result = scheduler.tick_once()

        assert result.outcome is TickOutcome.TICKED
        refusals = [
            payload for payload, kind in rows if kind == "MARKETFEED_FIELD_REFUSED"
        ]
        assert len(refusals) == 1
        assert refusals[0]["refused_by_reason"] == {"stale": ["close", "session"]}
        assert refusals[0]["age_ms"] == _STALE_BY_MS + _EVALUATION_STEP_MS
        assert refusals[0]["stale_max_age_ms"] == [5_000]

    def test_the_row_is_appended_after_the_decision_not_before_it(
        self, tmp_path: Path
    ) -> None:
        """⛔ **Review LOW-5.** The append is a ``BEGIN IMMEDIATE``/``COMMIT``, and this row is"""
        order: list[str] = []
        evidence = MagicMock()
        evidence.append.side_effect = lambda *_a, **_kw: order.append("evidence")
        driver = _CapturingDriver()
        real_enqueue = driver.enqueue_and_run

        def spy_enqueue(event: Any) -> None:
            order.append("decision")
            real_enqueue(event)

        driver.enqueue_and_run = spy_enqueue  # type: ignore[method-assign]
        time_service = _AdvancingTimeService(
            start_ms=_START_READING_MS, step_ms=_EVALUATION_STEP_MS
        )
        scheduler = _read_order_scheduler(
            tmp_path,
            time_service=time_service,
            intake=_StaleIntake(time_service),
            store=SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3"),
            driver=driver,
            evidence_store=evidence,
        )

        assert scheduler.tick_once().outcome is TickOutcome.TICKED

        assert order == ["decision", "evidence"]

    def test_an_unwritable_evidence_store_stops_the_pass(self, tmp_path: Path) -> None:
        """A failed append PROPAGATES, like every other evidence row in this module."""
        evidence = MagicMock()
        evidence.append.side_effect = RuntimeError("evidence store is unwritable")
        time_service = _AdvancingTimeService(
            start_ms=_START_READING_MS, step_ms=_EVALUATION_STEP_MS
        )
        scheduler = _read_order_scheduler(
            tmp_path,
            time_service=time_service,
            intake=_StaleIntake(time_service),
            store=SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3"),
            driver=_CapturingDriver(),
            evidence_store=evidence,
        )

        with pytest.raises(RuntimeError, match="unwritable"):
            scheduler.tick_once()
