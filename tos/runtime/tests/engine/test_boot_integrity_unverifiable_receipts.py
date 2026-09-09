"""Hermetic test for :func:`tos_runtime.compose._boot_integrity.verify_engine_replay_or_halt`'s
own re-review finding R1 (2026-09-09) addition: a NON-halt ``REPLAY_RECEIPTS_UNVERIFIABLE``
evidence row, appended when the boot proceeds but at least one receipt's flow fingerprint could
not be verified.

Placed alongside :mod:`tos_runtime.engine`'s own tests (not under ``tests/compose/``) purely for
fixture reuse — this function needs only the same low-level ``inbox``/``evidence_store``/
``emergency_log`` fixtures :mod:`test_replay_stage` already uses, not the full compose stack
(``config_dir``/``data_dir``/``custody_root``) ``tests/compose/conftest.py`` provides.

Re-review #2 finding S3 (2026-09-09): ``_replay_build_core`` used to be copied a third time here
(alongside :mod:`test_replay_stage`'s own copy and the shipped ``_engine_wiring.py::
_replay_core_factory``) — imported from :mod:`test_replay_stage` instead, so a future drift in
that shape cannot make this file silently verify a DIFFERENT boot-time core construction than the
shipped one.
"""

from __future__ import annotations

import json

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
    kwargs = {} if preconditions is None else {"preconditions": preconditions}
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
    """Re-review finding R1: a fingerprint-less (pre-CR6) ``DECISION_TICK`` receipt must not
    block the boot (its digest half was verified; a legacy receipt is not evidence of
    divergence) — but the fact that its flow half is unverifiable must be durably, visibly
    recorded, never silently discarded.
    """
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
    """Re-review #2 finding S1, reproduced exactly. Two ticks coexist: tick 1 is refused by the
    Coordinator gate (uncompared for reason ``"AUTHORITY_NOT_CURRENT"`` — the pipeline never ran
    for it at all); tick 2 hands off normally and has its ``flow_fingerprint`` disabled
    afterward (the P9 tamper). Only tick 2 is a genuine ``RECEIPT_FINGERPRINT_MISSING`` case —
    the evidence row must name EXACTLY tick 2's event id, with ``count == len(event_ids) == 1``,
    never inflating to ``count=2`` by conflating the two DIFFERENT ``uncompared`` reasons.
    """
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
    # The driver re-stamps `reference` on admission (its own yield-order counter), so the
    # caller-supplied `seq` above cannot be matched back — admission ORDER is what distinguishes
    # the two ticks instead: tick 1 (refused) was admitted first, tick 2 (handed off) second.
    admitted_events = [event for _seq, event in inbox.replay()]
    assert len(admitted_events) == 2
    handed_off_event_id = _event_id_of(admitted_events[1])

    # Disable ONLY tick 2's flow_fingerprint — tick 1's is irrelevant either way (it is refused
    # before the fingerprint check is ever reached), but targeting tick 2 specifically keeps this
    # test's premise ("exactly one genuinely unverifiable receipt") unambiguous.
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
    assert verdict.uncompared == 1  # the refused tick only
    assert verdict.total_compared == 1  # the handed-off tick's digest
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
    """Re-review #2 finding S2, reproduced exactly. A boot with BOTH a genuine divergence (tick
    2's recorded digest is corrupted) AND a legacy, fingerprint-less receipt (tick 1) must still
    durably record the ``REPLAY_RECEIPTS_UNVERIFIABLE`` row for tick 1 — the diagnostic case that
    most needs every available fact must not lose one just because
    ``verify_engine_replay_or_halt`` raises ``EngineReplayDiverged`` before returning.
    """
    # Both ticks are denied EARLY (well before step 9/ATOMIC_COMMIT) so neither ever touches the
    # reservation ledger — avoiding the DIFFERENT, already-documented "window_events path-
    # dependency" cross-tick interaction a shared replay ledger would otherwise introduce here
    # (module docstring of tos_runtime.engine.replay), which would confound this test's own,
    # narrower point.
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
    # Tick 1: disable its flow_fingerprint (the legacy-receipt half of this scenario).
    updated_fp = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"flow_fingerprint\":', '\"flow_fingerprint_DISABLED\":') "
        "WHERE kind = 'EVENT_CONSUMED' AND payload_json LIKE ?",
        (f"%{event_ids[1]}%",),
    )
    assert updated_fp.rowcount == 1
    # Tick 2: corrupt its recorded outcome_digest directly (the divergence half).
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

    # The halt record for the divergence exists...
    diverged_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()
    assert diverged_rows[0] == 1
    # ...AND the unverifiable-receipt fact is NOT lost just because the boot also diverged.
    unverifiable_rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_RECEIPTS_UNVERIFIABLE'"
    ).fetchall()
    assert len(unverifiable_rows) == 1
    unverifiable_payload = json.loads(unverifiable_rows[0][0])["payload"]
    assert unverifiable_payload["event_ids"] == [event_ids[1]]


def _event_id_of(event: object) -> str:
    return event_identity(event, scheme=SCHEME)  # type: ignore[arg-type]
