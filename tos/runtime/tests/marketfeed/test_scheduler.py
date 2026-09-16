"""Hermetic unit tests for ``tos_runtime.marketfeed.scheduler`` (TOS tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decisions 5/7/8, lane D).

Pure-function coverage only — :func:`decide_tick` never touches I/O, so these tests never touch
``tmp_path``/sqlite/the journal at all (that end-to-end wiring lives in
``tos/runtime/tests/compose/test_marketfeed_wiring.py``). Also covers
:class:`~tos_runtime.marketfeed.scheduler.MultiInstrumentRefused` at construction — plan §5
mutation M9 ("다심볼 거부 제거 -> (10) red").
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tos.time import SessionContext
from tos_runtime.marketfeed.ports import RawObservation, TickOutcome
from tos_runtime.marketfeed.scheduler import (
    MultiInstrumentRefused,
    TickResult,
    TickScheduler,
    decide_tick,
)

from ._fixtures import INSTRUMENT, SCHEME, loaded_policy

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


def _decide(**overrides: object) -> object:
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


def _build_scheduler(tmp_path: Path, *, poll_interval_ms: int) -> TickScheduler:
    """A real :class:`TickScheduler`, built with the real
    :func:`~tos_runtime.marketfeed.policy.load_critical_input_policy` output (reused from
    ``_fixtures.loaded_policy`` rather than hand-rolled) plus ``MagicMock`` doubles for every
    OTHER collaborator (:class:`~tos_runtime.marketfeed.ports.ObservationIntake`/
    ``DurableSnapshotStore``/time-projection/time-service/session-owner/inbox/evidence-store).
    ``run_forever`` never reads any of those directly — it only ever calls ``self.tick_once()``
    — so this scheduler exists purely as something to monkeypatch ``tick_once`` onto below,
    never to exercise a real tick path (that path already has its own dedicated coverage in
    this module and in ``tests/compose/test_marketfeed_wiring.py``)."""
    return TickScheduler(
        instruments=(INSTRUMENT,),
        instrument_class="krx-index-futures",
        account="acct-run-forever",
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
        evidence_store=MagicMock(),
        poll_interval_ms=poll_interval_ms,
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
