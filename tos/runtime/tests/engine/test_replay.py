"""Hermetic tests for :func:`tos_runtime.engine.replay.replay_engine` (TOS Phase 3 Wave 1
Lane A-R; plan §1.1 "재생 digest 동일").

Every scenario here uses ``transmit=None`` for BOTH the original run and the replay's
``build_core`` factory — the fully side-effect-free scope :mod:`tos_runtime.engine.replay`'s own
module docstring documents (see "Side-effect scope, reported precisely").
"""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import replay_engine
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _driver(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> EngineDriver:
    return EngineDriver(
        core=fx.build_core(transmit=None),
        inbox=inbox,
        evidence_store=evidence_store,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=None,
    )


def test_identical_replay_matches_for_every_event(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    driver = _driver(inbox, evidence_store)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    driver.enqueue_and_run(fx.decision_tick_event(seq=3))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 3
    assert verdict.diverged == ()


def test_window_events_limits_the_replay_to_the_most_recent_n(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A windowed replay is only sound when the events outside the window carry no ledger state
    into the ones inside it — here every tick is a defined no-action (never proposes, never
    touches the reservation ledger), so each event's outcome is independent of the others and a
    1-event window genuinely matches (see :func:`tos_runtime.engine.replay.replay_engine`'s own
    module docstring for the path-dependency caveat this test is deliberately avoiding).
    """
    registry = fx.registry_with(fx.never_fires_policy())
    driver = EngineDriver(
        core=fx.build_core(registry=registry, transmit=None),
        inbox=inbox,
        evidence_store=evidence_store,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=None,
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    driver.enqueue_and_run(fx.decision_tick_event(seq=3))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(registry=registry, transmit=None),
        scheme=SCHEME,
        window_events=1,
    )
    assert verdict.ok
    assert verdict.total_compared == 1


def test_zero_or_negative_window_is_rejected(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    with pytest.raises(ValueError, match="positive int or None"):
        replay_engine(
            inbox,
            evidence_store,
            emergency_log,
            lambda: fx.build_core(transmit=None),
            scheme=SCHEME,
            window_events=0,
        )


def test_mutated_recorded_outcome_digest_is_detected_as_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Mutation test (plan §1.1 "재생 비교 제거 red" companion): tamper with the recorded
    ``outcome_digest`` a real ``EVENT_CONSUMED`` receipt carries — replay must catch it, not
    silently agree."""
    driver = _driver(inbox, evidence_store)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    # Test-only tamper of the durably recorded digest (never how production code writes evidence
    # — evidence.sqlite3's entries table is append/no-update by trigger; this bypasses that
    # trigger deliberately, as a test double for "the recorded baseline was corrupted").
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"outcome_digest\":', '\"outcome_digest_untouched\":') "
        "WHERE kind = 'EVENT_CONSUMED'"
    )

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    halts = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()[0]
    assert halts == 1


def test_events_outside_the_recorded_baseline_are_skipped_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """An admitted-but-not-yet-consumed row (no ``EVENT_CONSUMED`` receipt to compare against)
    must not be reported as a divergence — there is nothing to diverge FROM."""
    inbox.enqueue(fx.decision_tick_event(seq=1))  # enqueued directly, never processed

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 0
