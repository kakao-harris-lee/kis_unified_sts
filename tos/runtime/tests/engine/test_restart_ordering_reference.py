"""(#992) The boot replay hands its ordering coordinate to the live core it verified."""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import EngineCore, HaltReason, OrderingAdmission
from tos.ordering import OrderingEvent
from tos_runtime.compose._engine_wiring import verify_replay_or_halt
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12
_CONTINUITY_ID = "restart-ordering-tests"


def _live_core(evidence_store: SqliteEvidenceStore) -> EngineCore:
    """A core wired as compose wires the live one — a never-firing policy keeps the flow out."""
    return fx.build_core(
        registry=fx.registry_with(fx.never_fires_policy()),
        transmit=None,
        sink=EngineEvidenceSinkAdapter(evidence_store),
    )


def _driver(
    core: EngineCore,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> EngineDriver:
    return EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id=_CONTINUITY_ID,
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )


def _boot_replay(
    live_core: EngineCore,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
):
    """The boot-time re-derivation compose runs before the live core consumes anything."""
    return verify_replay_or_halt(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        registry=fx.registry_with(fx.never_fires_policy()),
        stages=fx.admitting_stages(),
        configuration=fx.engine_configuration(),
        scheme=SCHEME,
        window_events=100,
        live_core=live_core,
        instrument_key=fx.instrument_key(),
    )


def _stamped(sequence: int) -> OrderingEvent:
    """The coordinate :class:`EngineDriver` stamps onto its ``sequence``-th yielded event."""
    return OrderingEvent(
        event_id=f"{_CONTINUITY_ID}-{sequence}",
        source_continuity_id=_CONTINUITY_ID,
        source_native_sequence=sequence,
    )


def test_the_boot_replay_seats_the_last_consumed_coordinate(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """(#992) The restarted live core starts where the previous boot's last consumed event left"""
    first_boot = _live_core(evidence_store)
    driver = _driver(first_boot, inbox, evidence_store, emergency_log)
    for seq in (1, 2, 3):
        driver.enqueue_and_run(fx.decision_tick_event(seq=seq))
    assert first_boot.last_reference == _stamped(3)

    restarted = _live_core(evidence_store)
    assert restarted.last_reference is None
    verdict = _boot_replay(restarted, inbox, evidence_store, emergency_log)

    assert verdict.ok
    assert restarted.last_reference == _stamped(3)


def test_the_restart_refuses_what_the_next_boot_replay_would_refuse(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """(#992) The divergence itself: an out-of-order event after the restart is REVERSED live,"""
    driver = _driver(_live_core(evidence_store), inbox, evidence_store, emergency_log)
    for seq in (1, 2, 3):
        driver.enqueue_and_run(fx.decision_tick_event(seq=seq))

    restarted = _live_core(evidence_store)
    _boot_replay(restarted, inbox, evidence_store, emergency_log)

    rewound = fx.decision_tick_event(seq=9).decision_tick
    assert rewound is not None
    out_of_order = fx.decision_tick_event(seq=9).model_copy(
        update={"decision_tick": rewound.model_copy(update={"reference": _stamped(2)})}
    )
    result = restarted.handle(out_of_order)

    assert result.ordering is OrderingAdmission.REVERSED
    assert result.halt_reason is HaltReason.EVENT_ORDER_REVERSED


def test_an_empty_inbox_seats_nothing(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """(#992) A first boot has no replayed coordinate to hand over — the core stays pristine."""
    first_boot = _live_core(evidence_store)
    verdict = _boot_replay(first_boot, inbox, evidence_store, emergency_log)

    assert verdict.total_compared == 0
    assert first_boot.last_reference is None


def test_a_leaf_recorded_before_the_hand_off_still_replays_identically(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """(#992) A persistent leaf's receipts are re-derived across two further boots without"""
    driver = _driver(_live_core(evidence_store), inbox, evidence_store, emergency_log)
    for seq in (1, 2, 3):
        driver.enqueue_and_run(fx.decision_tick_event(seq=seq))

    second_boot = _live_core(evidence_store)
    first_verdict = _boot_replay(second_boot, inbox, evidence_store, emergency_log)
    second_driver = _driver(second_boot, inbox, evidence_store, emergency_log)
    for seq in (4, 5):
        second_driver.enqueue_and_run(fx.decision_tick_event(seq=seq))

    third_boot = _live_core(evidence_store)
    second_verdict = _boot_replay(third_boot, inbox, evidence_store, emergency_log)

    assert first_verdict.ok and first_verdict.diverged == ()
    assert second_verdict.ok and second_verdict.diverged == ()
    assert first_verdict.total_compared == 3
    assert second_verdict.total_compared == 5
    assert second_boot.last_reference == _stamped(5)
    assert third_boot.last_reference == _stamped(5)
