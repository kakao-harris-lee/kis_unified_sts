"""Hermetic test for :func:`tos_runtime.compose._boot_integrity.verify_engine_replay_or_halt`'s
own re-review finding R1 (2026-09-09) addition: a NON-halt ``REPLAY_RECEIPTS_UNVERIFIABLE``
evidence row, appended when the boot proceeds but at least one receipt's flow fingerprint could
not be verified.

Placed alongside :mod:`tos_runtime.engine`'s own tests (not under ``tests/compose/``) purely for
fixture reuse — this function needs only the same low-level ``inbox``/``evidence_store``/
``emergency_log`` fixtures :mod:`test_replay_stage` already uses, not the full compose stack
(``config_dir``/``data_dir``/``custody_root``) ``tests/compose/conftest.py`` provides.
"""

from __future__ import annotations

import json

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.compose._boot_integrity import verify_engine_replay_or_halt
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay_stage import EventCorrelatingCore, RecordedStage
from tos_runtime.engine.replay_transmit import RecordedTransmit, any_recorded_hand_off
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_NO_TIMEOUT_WITHIN_TEST = 10**12


def _replay_build_core(evidence_store: SqliteEvidenceStore):
    def factory():
        recorded_stage = RecordedStage(evidence_store)
        core = fx.build_core(
            stages=dict.fromkeys(fx.admitting_stages(), recorded_stage),
            transmit=(
                RecordedTransmit(evidence_store)
                if any_recorded_hand_off(evidence_store)
                else None
            ),
        )
        return EventCorrelatingCore(
            core=core, recorded_stage=recorded_stage, scheme=SCHEME
        )

    return factory


def test_boot_proceeds_and_records_a_non_halt_evidence_row_for_an_unverifiable_receipt(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review finding R1: a fingerprint-less (pre-CR6) ``DECISION_TICK`` receipt must not
    block the boot (its digest half was verified; a legacy receipt is not evidence of
    divergence) — but the fact that its flow half is unverifiable must be durably, visibly
    recorded, never silently discarded.
    """
    gateway = fx.FakeGateway()
    driver = EngineDriver(
        core=fx.build_core(
            stages=fx.admitting_stages(),
            transmit=gateway,
            sink=EngineEvidenceSinkAdapter(evidence_store),
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="boot-integrity-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    updated = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"flow_fingerprint\":', '\"flow_fingerprint_DISABLED\":') "
        "WHERE kind = 'EVENT_CONSUMED'"
    )
    assert updated.rowcount == 1

    verdict = verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=100,
    )
    assert verdict.ok  # boot proceeds — never raises EngineReplayDiverged
    assert verdict.has_unverifiable_receipts is True

    (row,) = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_RECEIPTS_UNVERIFIABLE'"
    ).fetchall()
    payload = json.loads(row[0])["payload"]
    assert payload["count"] == 1
    assert len(payload["event_ids"]) == 1


def test_boot_records_no_unverifiable_row_when_every_receipt_carries_a_fingerprint(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Control: an untampered boot (every receipt carries its fingerprint) must NOT record the
    ``REPLAY_RECEIPTS_UNVERIFIABLE`` evidence row at all — it is not a routine, always-present
    marker; it only appears when something is genuinely unverifiable."""
    gateway = fx.FakeGateway()
    driver = EngineDriver(
        core=fx.build_core(
            stages=fx.admitting_stages(),
            transmit=gateway,
            sink=EngineEvidenceSinkAdapter(evidence_store),
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="boot-integrity-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True

    verdict = verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=100,
    )
    assert verdict.ok
    assert verdict.has_unverifiable_receipts is False

    rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_RECEIPTS_UNVERIFIABLE'"
    ).fetchone()
    assert rows[0] == 0
