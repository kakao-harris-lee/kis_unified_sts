"""Hermetic unit tests for ``tos_runtime.marketfeed.scheduler`` (TOS tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decisions 5/7/8, lane D).

Pure-function coverage only — :func:`decide_tick` never touches I/O, so these tests never touch
``tmp_path``/sqlite/the journal at all (that end-to-end wiring lives in
``tos/runtime/tests/compose/test_marketfeed_wiring.py``). Also covers
:class:`~tos_runtime.marketfeed.scheduler.MultiInstrumentRefused` at construction — plan §5
mutation M9 ("다심볼 거부 제거 -> (10) red").
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from tos.engine import time_admits
from tos.time import FreshnessVerdict, HealthState, SessionContext, freshness_verdict
from tos_runtime.marketfeed.ports import RawObservation, TickOutcome
from tos_runtime.marketfeed.scheduler import (
    MultiInstrumentRefused,
    TickDecision,
    TickResult,
    TickScheduler,
    decide_tick,
)
from tos_runtime.marketfeed.store import SqliteSnapshotStore
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
from tos_runtime.time.config import TrustworthyTimeConfig

from ._fixtures import CLOSE_BAR_ONE, INSTRUMENT, SCHEME, loaded_policy

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
    """``decide_tick`` with a baseline of admitting values — one keyword override per test
    isolates exactly the ONE check under test, mirroring the plan's own per-mutation red
    list."""
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
    """Absence is restrictive, never permissive (module docstring) — no wall-clock reading to
    derive a session context from is treated exactly like a positively closed one."""
    decision = _decide(session_context=None)
    assert decision.outcome is TickOutcome.SKIPPED_SESSION_CLOSED


def test_skips_no_observation_when_the_batch_is_empty() -> None:
    decision = _decide(observations=())
    assert decision.outcome is TickOutcome.SKIPPED_NO_OBSERVATION
    assert decision.observation is None


def test_skips_not_newer_when_as_of_equals_the_store_high_water_mark() -> None:
    """The CIS's own distinctness obligation (module docstring; plan §5 mutation M2) —
    independent of whatever filtering the intake itself already did."""
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
    """The interval gate never fires when either wall-clock reading is unavailable — absence
    narrows admission everywhere ELSE in this codebase, but here there is nothing to compare,
    so the gate simply does not apply (mirrors the session/no-observation checks running first
    and independently)."""
    assert _decide(now_ms=None).outcome is TickOutcome.TICKED
    assert _decide(last_tick_wall_clock_ms=None).outcome is TickOutcome.TICKED


def test_session_gate_runs_before_the_no_observation_gate() -> None:
    """Check order (module docstring): session, then observation existence, then
    distinctness, then interval — each a DIFFERENTLY named absence."""
    decision = _decide(session_context=_CLOSED_SESSION, observations=())
    assert decision.outcome is TickOutcome.SKIPPED_SESSION_CLOSED


def test_multi_instrument_refused_at_construction() -> None:
    """Plan §2 decision 8 / §5 mutation M9 — a config naming more than one instrument is
    refused at ``TickScheduler`` construction, before any other collaborator is ever touched
    (the refusal is this class's very first statement), so every other keyword argument below
    can safely stay a type-incompatible placeholder — none of them is ever read."""
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


# ----------------------------------------------------------------------------
# run_forever — the thin loop (module docstring: "the ONLY place time.sleep is called")
# ----------------------------------------------------------------------------


def _build_scheduler(
    tmp_path: Path,
    *,
    poll_interval_ms: int,
    before_decide: Callable[[], bool] | None = None,
    intake: Any = None,
    store: Any = None,
    time_service: Any = None,
    session_owner: Any = None,
) -> TickScheduler:
    """A real :class:`TickScheduler`, built with the real
    :func:`~tos_runtime.marketfeed.policy.load_critical_input_policy` output (reused from
    ``_fixtures.loaded_policy`` rather than hand-rolled) plus ``MagicMock`` doubles for every
    OTHER collaborator (:class:`~tos_runtime.marketfeed.ports.ObservationIntake`/
    ``DurableSnapshotStore``/time-projection/time-service/session-owner/inbox/evidence-store).
    ``run_forever`` never reads any of those directly — it only ever calls ``self.tick_once()``
    — so for the loop tests below this scheduler exists purely as something to monkeypatch
    ``tick_once`` onto, never to exercise a real tick path (that path already has its own
    dedicated coverage in this module and in ``tests/compose/test_marketfeed_wiring.py``).

    The four collaborator overrides exist for the ``SKIPPED_TIME_NOT_EVALUATED`` test, which
    drives the REAL ``tick_once`` and therefore needs to see which of them were touched.
    """
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
        time_projection=MagicMock(),
        time_service=time_service if time_service is not None else MagicMock(),
        session_owner=session_owner if session_owner is not None else MagicMock(),
        driver=None,
        inbox=MagicMock(),
        evidence_store=MagicMock(),
        poll_interval_ms=poll_interval_ms,
        before_decide=before_decide,
    )


def _stop_after(n: int):
    """A ``stop`` double that returns ``False`` for its first ``n`` calls, then ``True`` —
    ``run_forever``'s own loop checks ``stop()`` BEFORE every pass, so this yields exactly
    ``n`` ``tick_once``/``sleep`` calls before the loop exits."""
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
    """Pins the loop's own thinness (team-lead review finding, 2026-09-16: ``run_forever`` had
    zero coverage — its own docstring described the injection seam this test now actually
    uses). Never re-tests ``tick_once``'s own logic — ``tick_once`` is replaced with a counting
    double, so this test demonstrates ONLY: ``stop()`` gates every pass, ``tick_once()`` runs
    once per admitted pass, and ``sleep()`` is called with the scheduler's OWN CONFIGURED
    interval (750 ms here, deliberately not the common 1000 ms default elsewhere in this
    module) — never a hardcoded one."""
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
    """Plan 2026-09-27 §2.1 (issue #809): the ``before_decide`` hook moved INSIDE ``tick_once``,
    so this loop no longer consults it — every admitted pass calls ``tick_once`` exactly once,
    whatever that pass's outcome turns out to be. Mutation: put the hook back in the loop (``if
    self._before_decide is None or self._before_decide(): self.tick_once()``) -> ``tick_calls ==
    2`` -> red."""
    hook_calls = 0

    def before_decide() -> bool:
        nonlocal hook_calls
        hook_calls += 1
        return False  # would have suppressed the pass under the OLD loop

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
    assert hook_calls == 0  # the loop itself never calls it — tick_once does
    assert sleep_calls == [0.75, 0.75, 0.75]


# ----------------------------------------------------------------------------
# tick_once — the read order: intake FIRST, wall-clock reading SECOND
# (plan ``docs/plans/2026-09-27-tos-freshness-read-order-plan.md`` §2.1, issue #809)
# ----------------------------------------------------------------------------


def test_tick_once_reports_time_not_evaluated_after_polling_and_consumes_nothing(
    tmp_path: Path,
) -> None:
    """A ``False`` from ``before_decide`` (the evaluation was due and failed) is a NAMED absence
    that happens AFTER the intake was read and BEFORE anything downstream of the reading.

    Four things are pinned here, each a separate mutation:

    1. the outcome is ``SKIPPED_TIME_NOT_EVALUATED`` — mutation: return ``SKIPPED_NO_OBSERVATION``
       instead -> red (the two absences are different facts: an observation may well exist);
    2. ``intake.poll`` DID run, with the store's own high-water mark — mutation: move the hook
       back before the poll -> ``poll`` never called -> red;
    3. ``store.put`` did NOT run — mutation: put on a failed evaluation -> red (that would
       consume the observation and no later pass could ever re-read it);
    4. neither the wall-clock reading nor the session context was taken — both live downstream of
       a reading this pass does not have.
    """
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


# ----------------------------------------------------------------------------
# the same read order, end to end through the REAL store / issuers / kernel resolver
# ----------------------------------------------------------------------------

#: How far one ``evaluate()`` advances the fake service's cached reading.
_EVALUATION_STEP_MS = 500
#: How long after the LAST evaluation's reading a collector stamped its line. Deliberately larger
#: than ``MAX_future_timestamp_tolerance_ms`` below (200 > 50): under the OLD order — evaluate,
#: then read the journal — that line is read against a reading taken BEFORE it, ``source_age``
#: comes out ``-200``, and the kernel answers ``CONFLICTED``. Under the new order the pass's own
#: evaluation happens after the read, so the same line is ``+300`` old and FRESH.
_APPENDED_AFTER_MS = 200
#: An arbitrary concrete epoch-ms reading — nothing in this file depends on its value.
_START_READING_MS = 1_790_557_200_000

_READ_ORDER_INSTRUMENT_CLASS = "krx-index-futures"


class _AdvancingTimeService:
    """A time service whose ``evaluate()`` advances the reading ``wall_clock_now()`` returns.

    Fakes exactly ONE property of the real
    :class:`~tos_runtime.time.service.TrustworthyTimeService`, the load-bearing one here
    (``time/service.py:697-711``): ``wall_clock_now()`` hands back the reading the LAST
    ``evaluate()`` cached — it never takes a fresh one. Everything else that class does (health
    degradation, reference reads, evidence) is irrelevant to the read ORDER and is deliberately
    absent rather than imitated. Local to this module, per this package's own fakes convention
    (``test_time_projection.py``'s module docstring).
    """

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
    """A driver double that records the event it was handed — the tick payload (and therefore its
    projected time coordinates) is what these tests judge, and it is not otherwise observable
    from a :class:`TickResult`."""

    def __init__(self) -> None:
        self.events: list[object] = []

    def enqueue_and_run(self, event: object) -> None:
        self.events.append(event)


class _SessionOpeningBetweenReadingsOwner:
    """A session owner that answers from the time service's CURRENT reading rather than holding a
    constant — the shape the real :class:`~tos_runtime.calendar.owner.SessionFactsOwner` has
    (``calendar/owner.py:269-277``: ``session_context`` derives from a wall-clock reading). Open
    only at or after ``opens_at_ms``, which these tests place BETWEEN the reading a pass starts
    with and the one its own evaluation produces — the 08:45 boundary case plan
    ``docs/plans/2026-09-27-tos-freshness-read-order-plan.md`` §5 names."""

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
    """An intake that stamps each polled observation ``as_of = wall_clock_now() +
    _APPENDED_AFTER_MS`` — i.e. a collector that appended its line AFTER the reading currently
    cached by the time service, which is the exact case #809 is about. WHICH reading that is
    depends entirely on the order under test: this pass's (old order — the evaluation already
    ran) or the previous pass's (new order — it has not)."""

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


class _FixedObservationIntake:
    """One unchanging observation, filtered the way
    :class:`~tos_runtime.marketfeed.journal.JsonLinesObservationJournal` filters — so "the next
    pass re-reads the same line" is a claim about the DURABLE store's high-water mark, not about
    an intake that forgot it had already served it. ``polls`` records the mark each poll was
    asked from."""

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
    """An observation carrying both fields ``_fixtures.VALID_POLICY_YAML`` declares, so the
    policy-derived field states are VALID and the resolver publishes a non-empty value view —
    without one, ``as_of`` would be ``None`` at the projection and every verdict below would
    collapse to ``UNKNOWN`` for a reason that has nothing to do with the read order."""
    return RawObservation(
        raw_event_id=raw_event_id,
        instrument=INSTRUMENT,
        as_of_ms=as_of_ms,
        fields=(("close", CLOSE_BAR_ONE), ("session", "REGULAR")),
        source_id="read-order-collector",
    )


def _read_order_time_config() -> TrustworthyTimeConfig:
    """``config/tos_runtime/paper/time.yaml``'s own approved values (the deployment this defect
    was measured on), transcribed — not a set of numbers chosen to make the assertions below
    come out. ``MAX_future_timestamp_tolerance_ms: 50`` is VER-002 L1074."""
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
) -> TickScheduler:
    """A :class:`TickScheduler` whose snapshot store, policy, issuers, time projection and kernel
    resolver are all REAL — only the time service, the session owner, the intake and the driver
    are doubles, and each for a stated reason (see their own docstrings). ``before_decide``
    defaults to the pacer's own shape: evaluate, then admit."""
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
            snapshot_age_bound=20,  # config/tos_runtime/paper/marketfeed.yaml
            interval_width=10,  # config/tos_runtime/paper/marketfeed.yaml
        ),
        time_service=time_service,  # type: ignore[arg-type]
        session_owner=session_owner,  # type: ignore[arg-type]
        driver=driver,  # type: ignore[arg-type]
        inbox=MagicMock(),
        evidence_store=MagicMock(),
        poll_interval_ms=400,  # config/tos_runtime/paper/marketfeed.yaml
        before_decide=(
            before_decide if before_decide is not None else evaluate_then_admit
        ),
    )


def test_an_observation_appended_since_the_last_evaluation_reads_fresh_not_conflicted(
    tmp_path: Path,
) -> None:
    """THE #809 regression. A collector appends a line stamped 200 ms after the reading the time
    service currently holds, and the pass then runs.

    * OLD order (evaluate, then read the journal): that reading IS this pass's, so the line is
      200 ms in the FUTURE — ``source_age == -200``, past ``MAX_future_timestamp_tolerance_ms``
      (50), and the kernel answers ``CONFLICTED``. The tick is consumed with no decision.
    * NEW order (read the journal, then evaluate): the line was stamped against the PREVIOUS
      reading, this pass's evaluation has moved on by ``_EVALUATION_STEP_MS``, so the same line
      is ``+300`` ms old and FRESH.

    Every verdict below is the REAL kernel predicate over the REAL projected coordinates carried
    by the event the driver was handed — nothing is recomputed here. Mutation: move the hook back
    before the poll -> ``source_age == -200`` -> red.

    The last assertion pins the OTHER half of the order, which the verdicts above cannot see:
    ``source_age`` is computed by :class:`~tos_runtime.marketfeed.time_projection
    .RuntimeTimeProjection` from its own ``wall_clock_now()`` at resolve time, which is after the
    hook whatever the surrounding order is. The pass's ``now_ms`` — what issues the snapshot and
    paces the next tick — is a SEPARATE read, and ``_last_tick_wall_clock_ms`` is the only place
    it survives the call. Mutation: hoist ``now_ms``/``session_context`` back above the poll
    (hook still after it) -> that value is the PRE-evaluation reading -> red.
    """
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
    assert time_service.evaluations == 1  # still exactly one evaluation per pass
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
    """The success path's half of #809: ``now_ms`` AND the session context are read AFTER the
    hook, so the pass decides on the reading its own evaluation produced.

    The session opens 1 ms after the reading this pass starts with — the 08:45 boundary the plan
    ``docs/plans/2026-09-27-tos-freshness-read-order-plan.md`` §5 names. Reading the session from
    the post-evaluation reading sees it open and ticks; reading it from the reading the pass
    started with sees it closed and answers ``SKIPPED_SESSION_CLOSED``, deferring a real tick by
    a whole pass for no reason but read order.

    Mutation: hoist ``now_ms``/``session_context`` back above the poll (leaving the hook after
    it) -> ``SKIPPED_SESSION_CLOSED``, no event, ``_last_tick_wall_clock_ms`` still ``None`` ->
    red. A behaviour difference, not a call-order assertion on a mock.
    """
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
    # The reading that issued this tick and now paces the next one is the POST-evaluation one.
    assert (
        scheduler._last_tick_wall_clock_ms  # noqa: SLF001 — the only surviving copy of now_ms
        == _START_READING_MS + _EVALUATION_STEP_MS
    )

    store.close()


def test_a_failed_evaluation_leaves_the_observation_for_the_next_pass(
    tmp_path: Path,
) -> None:
    """The consequence of skipping WITHOUT a ``store.put`` (``ports.py``'s own
    ``SKIPPED_TIME_NOT_EVALUATED`` docstring), proven against the REAL durable store: the
    high-water mark does not advance, the second poll is asked from the SAME mark, and the very
    same observation ticks.

    Mutation: ``store.put`` on a failed evaluation -> the second poll is asked from the advanced
    mark, returns nothing, and the second pass is ``SKIPPED_NO_OBSERVATION`` -> red.
    """
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
    ]  # the same mark both times — nothing was consumed
    assert store.latest_as_of(instrument=INSTRUMENT) == intake.as_of_ms
    assert len(driver.events) == 1

    store.close()
