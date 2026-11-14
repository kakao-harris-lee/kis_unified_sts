"""Hermetic test for :func:`tos_runtime.compose._boot_integrity.verify_engine_replay_or_halt`'s"""

from __future__ import annotations

import json
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import event_identity
from tos.engine.vocabulary import CommitmentStep
from tos_runtime.compose._boot_integrity import (
    EngineReplayDiverged,
    verify_engine_replay_or_halt,
)
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource
from .test_replay import _AlwaysRefusedPreconditions
from .test_replay_stage import _replay_build_core

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_NO_TIMEOUT_WITHIN_TEST = 10**12


def _driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    *,
    transmit: object = None,
    preconditions: object = None,
) -> EngineDriver:
    kwargs: dict[str, Any] = (
        {} if preconditions is None else {"preconditions": preconditions}
    )
    return EngineDriver(
        core=fx.build_core(
            stages=fx.admitting_stages(),
            transmit=transmit,
            sink=EngineEvidenceSinkAdapter(evidence_store),
            **kwargs,
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


def test_boot_proceeds_and_records_a_non_halt_evidence_row_for_an_unverifiable_receipt(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review finding R1: a fingerprint-less (pre-CR6) ``DECISION_TICK`` receipt must not"""
    gateway = fx.FakeGateway()
    driver = _driver(inbox, evidence_store, emergency_log, transmit=gateway)
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
    assert verdict.ok
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
    """Control: an untampered boot (every receipt carries its fingerprint) must NOT record the"""
    gateway = fx.FakeGateway()
    driver = _driver(inbox, evidence_store, emergency_log, transmit=gateway)
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


def test_p12_a_coordinator_refused_tick_is_never_misattributed_as_unverifiable(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review #2 finding S1, reproduced exactly. Two ticks coexist: tick 1 is refused by the"""
    refused_driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        preconditions=_AlwaysRefusedPreconditions(),
    )
    refused_result = refused_driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert refused_result.halt_reason is not None
    assert refused_result.halt_reason.value == "AUTHORITY_NOT_CURRENT"

    gateway = fx.FakeGateway()
    handed_off_driver = _driver(inbox, evidence_store, emergency_log, transmit=gateway)
    handed_off_result = handed_off_driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert (
        handed_off_result.flow is not None and handed_off_result.flow.handed_off is True
    )
    admitted_events = [event for _seq, event in inbox.replay()]
    assert len(admitted_events) == 2
    handed_off_event_id = _event_id_of(admitted_events[1])

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    updated = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"flow_fingerprint\":', '\"flow_fingerprint_DISABLED\":') "
        "WHERE kind = 'EVENT_CONSUMED' AND payload_json LIKE ?",
        (f"%{handed_off_event_id}%",),
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
    assert verdict.ok
    assert verdict.uncompared == 1
    assert verdict.total_compared == 1
    assert verdict.has_unverifiable_receipts is True

    (row,) = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_RECEIPTS_UNVERIFIABLE'"
    ).fetchall()
    payload = json.loads(row[0])["payload"]
    assert payload["count"] == len(payload["event_ids"]) == 1
    assert payload["event_ids"] == [handed_off_event_id]


def test_the_unverifiable_row_still_lands_when_a_different_event_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review #2 finding S2, reproduced exactly. A boot with BOTH a genuine divergence (tick"""
    denied_stages = fx.admitting_stages(
        denied_steps={CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "denied for S2 test"}
    )
    driver1 = EngineDriver(
        core=fx.build_core(
            stages=denied_stages, sink=EngineEvidenceSinkAdapter(evidence_store)
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
    driver1.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver2 = EngineDriver(
        core=fx.build_core(
            stages=denied_stages, sink=EngineEvidenceSinkAdapter(evidence_store)
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
    driver2.enqueue_and_run(fx.decision_tick_event(seq=2))
    admitted_events = [event for _seq, event in inbox.replay()]
    assert len(admitted_events) == 2
    event_ids = {
        1: _event_id_of(admitted_events[0]),
        2: _event_id_of(admitted_events[1]),
    }

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    updated_fp = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"flow_fingerprint\":', '\"flow_fingerprint_DISABLED\":') "
        "WHERE kind = 'EVENT_CONSUMED' AND payload_json LIKE ?",
        (f"%{event_ids[1]}%",),
    )
    assert updated_fp.rowcount == 1
    (row,) = evidence_store.connection.execute(
        "SELECT rowid, payload_json FROM entries WHERE kind = 'EVENT_CONSUMED' "
        "AND payload_json LIKE ?",
        (f"%{event_ids[2]}%",),
    ).fetchall()
    rowid, payload_json = row
    payload = json.loads(payload_json)
    payload["payload"]["outcome_digest"] = "TAMPERED-DIGEST"
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = ? WHERE rowid = ?",
        (json.dumps(payload), rowid),
    )

    with pytest.raises(EngineReplayDiverged):
        verify_engine_replay_or_halt(
            inbox,
            evidence_store,
            emergency_log,
            _replay_build_core(evidence_store),
            scheme=SCHEME,
            window_events=100,
        )

    diverged_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()
    assert diverged_rows[0] == 1
    unverifiable_rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_RECEIPTS_UNVERIFIABLE'"
    ).fetchall()
    assert len(unverifiable_rows) == 1
    unverifiable_payload = json.loads(unverifiable_rows[0][0])["payload"]
    assert unverifiable_payload["event_ids"] == [event_ids[1]]


def _event_id_of(event: object) -> str:
    return event_identity(event, scheme=SCHEME)  # type: ignore[arg-type]
