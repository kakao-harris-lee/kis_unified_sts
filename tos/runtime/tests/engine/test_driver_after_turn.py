"""Hermetic tests for :meth:`tos_runtime.engine.driver.EngineDriver.bind_after_turn` (TOS Phase"""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12


@pytest.fixture
def driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: FakeMonotonicSource,
) -> EngineDriver:
    """The one driver under test, on this test's own durable stores."""
    core = fx.build_core()
    return EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="after-turn-tests",
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )


def _admit(driver: EngineDriver, inbox: SqliteEventInbox, *, seq: int) -> None:
    """Durably admit a DECISION_TICK event WITHOUT processing it (mirrors"""
    stamped = driver._stamp(fx.decision_tick_event(seq=seq))
    inbox.enqueue(stamped)


def test_run_once_fires_after_turn_exactly_once_when_a_turn_was_processed(
    driver: EngineDriver,
    inbox: SqliteEventInbox,
) -> None:
    calls: list[int] = []
    driver.bind_after_turn(lambda: calls.append(1))
    _admit(driver, inbox, seq=1)

    result = driver.run_once()

    assert result is not None
    assert calls == [1]


def test_run_once_does_not_fire_after_turn_when_idle(driver: EngineDriver) -> None:
    calls: list[int] = []
    driver.bind_after_turn(lambda: calls.append(1))

    result = driver.run_once()

    assert result is None
    assert calls == []


def test_run_once_with_no_bound_callback_costs_nothing(
    driver: EngineDriver,
    inbox: SqliteEventInbox,
) -> None:
    _admit(driver, inbox, seq=1)

    result = driver.run_once()

    assert result is not None
    assert driver.after_turn_failures == 0
    assert driver.after_turn_last_error is None


def test_run_until_idle_fires_after_turn_once_per_processed_event(
    driver: EngineDriver,
    inbox: SqliteEventInbox,
) -> None:
    calls: list[int] = []
    driver.bind_after_turn(lambda: calls.append(1))
    _admit(driver, inbox, seq=1)
    _admit(driver, inbox, seq=2)
    _admit(driver, inbox, seq=3)

    results = driver.run_until_idle()

    assert len(results) == 3
    assert calls == [1, 1, 1]


def test_run_until_idle_on_an_empty_inbox_never_fires(driver: EngineDriver) -> None:
    calls: list[int] = []
    driver.bind_after_turn(lambda: calls.append(1))

    results = driver.run_until_idle()

    assert results == ()
    assert calls == []


def test_enqueue_and_run_fires_after_turn_exactly_once(driver: EngineDriver) -> None:
    calls: list[int] = []
    driver.bind_after_turn(lambda: calls.append(1))

    result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    assert result is not None
    assert calls == [1]


def test_enqueue_and_run_called_twice_fires_after_turn_twice(
    driver: EngineDriver,
) -> None:
    calls: list[int] = []
    driver.bind_after_turn(lambda: calls.append(1))

    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))

    assert calls == [1, 1]


def test_a_raising_after_turn_callback_does_not_stop_run_until_idle_and_is_counted(
    driver: EngineDriver,
    inbox: SqliteEventInbox,
) -> None:
    def _boom() -> None:
        raise RuntimeError("exporter broke")

    driver.bind_after_turn(_boom)
    _admit(driver, inbox, seq=1)
    _admit(driver, inbox, seq=2)

    results = driver.run_until_idle()

    assert len(results) == 2
    assert driver.after_turn_failures == 2
    assert driver.after_turn_last_error is not None
    assert "exporter broke" in driver.after_turn_last_error


def test_a_raising_after_turn_callback_does_not_stop_run_once(
    driver: EngineDriver,
    inbox: SqliteEventInbox,
) -> None:
    def _boom() -> None:
        raise ValueError("nope")

    driver.bind_after_turn(_boom)
    _admit(driver, inbox, seq=1)

    result = driver.run_once()

    assert result is not None
    assert driver.after_turn_failures == 1
    assert driver.after_turn_last_error is not None
    assert "nope" in driver.after_turn_last_error


def test_after_turn_last_error_reflects_the_most_recent_failure_only(
    driver: EngineDriver,
    inbox: SqliteEventInbox,
) -> None:
    attempt = {"n": 0}

    def _boom() -> None:
        attempt["n"] += 1
        raise RuntimeError(f"failure #{attempt['n']}")

    driver.bind_after_turn(_boom)
    _admit(driver, inbox, seq=1)
    _admit(driver, inbox, seq=2)

    driver.run_until_idle()

    assert driver.after_turn_failures == 2
    assert driver.after_turn_last_error is not None
    assert "failure #2" in driver.after_turn_last_error
