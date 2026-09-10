"""Surviving-mutation fix (independent-review pass, 2026-09-10): a failed
``recovery_composite_writer`` call in :meth:`~tos_runtime.engine.driver.EngineDriver
._project_orthostate_and_persist` must halt, never be silently skipped."""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12


class _RaisingCompositeWriter:
    """Simulates an unwritable ``tos.staterestore`` composite-state store."""

    def __call__(self, attempt_id: str, composite: object) -> None:
        del attempt_id, composite
        raise OSError("simulated unwritable composite-state store")


def _make_driver_with_composite_writer(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
    transmit: object,
) -> EngineDriver:
    core = fx.build_core(transmit=transmit)
    return EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="driver-composite-write-failure-tests",
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
        recovery_composite_writer=_RaisingCompositeWriter(),
    )


def test_composite_write_failure_halts_before_event_consumed(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    gateway = fx.FakeGateway()  # auto_ack=True -- ACK carries a real reservation
    driver = _make_driver_with_composite_writer(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
    )
    driver.bind_gateway(gateway)

    # The DECISION_TICK itself succeeds and hands off; the re-injected ACK EGRESS_RESULT is
    # what triggers OrthostateProjector.project() to return a real composite and, in turn, the
    # (raising) recovery_composite_writer call.
    with pytest.raises(OSError, match="simulated unwritable"):
        driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    consumed_rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchall()
    # Exactly one EVENT_CONSUMED: the DECISION_TICK's own. The re-injected EGRESS_RESULT that
    # triggered the failing write must NOT have one -- the write-before-receipt ordering held.
    assert len(consumed_rows) == 1

    halt_rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'COMPOSITE_STATE_WRITE_FAILED'"
    ).fetchall()
    assert len(halt_rows) == 1

    # The dual-path emergency log also carries it (record_halt's own contract).
    emergency_lines = emergency_log.path.read_text(encoding="utf-8").splitlines()
    assert any("COMPOSITE_STATE_WRITE_FAILED" in line for line in emergency_lines)
