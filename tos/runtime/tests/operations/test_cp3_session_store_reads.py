"""The tos half of the CP-3 §3.6 extractor hinge: columns AND payload bytes.

``tools/tos_cp3/session_inputs.py`` (CP-3 plan 2026-10-10 §3.6, PR-3) reads a
tenant session's ``marketfeed.sqlite3``, ``evidence.sqlite3`` and
``inbox.sqlite3`` as plain sqlite files to produce B3's two session-derived
inputs. It cannot import ``tos_runtime`` — the firewall is bidirectional — and
this package cannot import ``tools``, so neither side can check the other
directly.

The committed fixture ``fixtures/cp3-session-store-reads.json`` is the hinge,
in two halves:

``reads``
    every (table, column) the extractor selects, checked here against the
    registered migrations and used there to build its fixture stores.

``payloads``
    the EXACT ``payload_json`` bytes the real stores write, produced here by
    driving :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` through
    :class:`~tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter` and
    :class:`~tos_runtime.engine.inbox.SqliteEventInbox`, and replayed there as
    the extractor's input.

The second half exists because the first was not enough. PR-3's first cut read
``entries.payload_json`` as if it were the engine record; the store wraps it
(``{"payload": …, "masked_keys": …}``), so every field came back ``None`` —
and the tools-side tests missed it because they wrote flat rows of their own
invention (Claude-lane BLOCKER, 2026-10-14). A fixture of invented bytes tests
the invention; these are the store's own.

Hermetic (D1.4): sqlite under ``tmp_path``, one committed file read, no
socket, no clock.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import CriticalInputSnapshot, FieldEvaluation, FieldState
from tos.dsl.context_value import ContextValue, ContextValueView
from tos.engine.records import EngineEvent, EngineEvidenceRecord
from tos.engine.vocabulary import EvidenceKind, HaltReason
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION, SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, SqliteEvidenceStore
from tos_runtime.marketfeed.store import (
    MARKETFEED_FILE_NAME,
    MARKETFEED_SCHEMA_VERSION,
    SqliteSnapshotStore,
)
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME, INBOX_FILE_NAME
from tos_runtime.operations.schema_migrations import STORE_MIGRATIONS

from ..engine import _fixtures as fx
from ..engine.conftest import FakeMonotonicSource
from ..evidence.conftest import FixedKeyProvider
from ..marketfeed import _store_fixtures as mf

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cp3-session-store-reads.json"
)

#: ``store name in STORE_MIGRATIONS`` -> ``(file name, running schema version)``
#: as the store modules themselves declare them.
DECLARED = {
    "marketfeed": (MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION),
    "evidence": (EVIDENCE_FILE_NAME, EVIDENCE_SCHEMA_VERSION),
    "inbox": (INBOX_FILE_NAME, INBOX_SCHEMA_VERSION),
}

#: The capsule sequence numbers the fixture's two ticks are issued with. The
#: evidence records below quote the SAME capsule ids, because the extractor's
#: join is exactly that equality and a fixture whose two halves never meet
#: could not exercise it.
TICK_SEQS = (1, 2)

#: ``tick seq -> (EVENT_HANDLING_STARTED seq, EVENT_CONSUMED seq)``. These are
#: the numbers a real :class:`EngineDriver` run over two ticks writes — the
#: shape, including the ``0`` first seq that makes a truthiness test wrong
#: where an ``is None`` test is right. Proven live, against the driver itself,
#: by :func:`test_the_drivers_receipts_bracket_the_decision_records_it_writes`.
STAMPS = {1: (0, 16), 2: (17, 26)}

#: The tenant instrument the extractor's own tests use, so the snapshot rows
#: here and the sessions there name one contract month.
INSTRUMENT = "A05611"
AS_OF_MS = 1_760_000_000_000

#: A bound no test here reaches (mirrors ``tests/engine/test_driver.py``'s own
#: constant): nothing below exercises timeout injection.
_NO_TIMEOUT_WITHIN_TEST = 10**12


@pytest.fixture(scope="module")
def pinned() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return document


# ---------------------------------------------------------------------------
# Half 1 — the columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("store", sorted(DECLARED))
def test_the_extractor_pins_this_stores_file_name_and_version(
    store: str, pinned: dict[str, Any]
) -> None:
    """The file name and schema version the extractor was written against.

    Concrete failing input: an ``EVIDENCE_SCHEMA_VERSION`` bump to 3. The
    extractor pins 2 and would refuse every session store on this host with
    "pinned to 2" — correct behaviour, but nobody would learn why until a
    genesis post-mortem. This turns that bump red in the PR that makes it.
    """
    file_name, version = DECLARED[store]
    assert pinned[store]["file_name"] == file_name
    assert pinned[store]["schema_version"] == version
    assert version == max(
        migration.version for migration in STORE_MIGRATIONS[store]
    ), "the store's running version is not the latest registered migration"


@pytest.mark.parametrize("store", sorted(DECLARED))
def test_every_column_the_extractor_reads_is_one_the_migrations_declare(
    store: str, pinned: dict[str, Any]
) -> None:
    """Column-level, not table-level: a rename is the drift that matters.

    Concrete failing input: ``preimages.raw_event_id`` renamed to
    ``observation_id``. Both tables still exist, the version may or may not
    move, and the extractor's ``SELECT snapshot_id, raw_event_id FROM
    preimages`` becomes a sqlite ``OperationalError`` against a real session —
    after the session, when it cannot be re-run.
    """
    declared: dict[str, set[str]] = {}
    for migration in STORE_MIGRATIONS[store]:
        for table, columns in migration.expected_tables.items():
            declared.setdefault(table, set()).update(columns)
    for table, columns in pinned[store]["reads"].items():
        assert (
            table in declared
        ), f"{store}.{table} is not a table these migrations create"
        missing = sorted(set(columns) - declared[table])
        assert not missing, f"{store}.{table} no longer declares {missing}"


# ---------------------------------------------------------------------------
# Half 2 — the payload bytes the extractor parses
# ---------------------------------------------------------------------------


def real_evidence_payloads(tmp_path: Path) -> list[dict[str, str]]:
    """Three engine records through the REAL store, as stored.

    One emitted no-action (the shape every genesis bar is expected to take),
    one withheld decision (no capsule id — the extractor's positional
    fallback), and one capacity-denied flow halt.
    """
    store = SqliteEvidenceStore(
        tmp_path / EVIDENCE_FILE_NAME,
        key_provider=FixedKeyProvider(),
        monotonic_ns=lambda: 0,
    )
    try:
        sink = EngineEvidenceSinkAdapter(store)
        capsules = [fx.issue_capsule(seq=seq) for seq in TICK_SEQS]
        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.DECISION_OUTCOME_EMITTED,
                instrument_key=fx.instrument_key(),
                halt_reason=HaltReason.NO_ACTION_OUTCOME,
                outcome_type="NoActionOutcome",
                outcome_digest="oc-digest-1",
                capsule_id=capsules[0].capsule_id,
                capsule_digest=capsules[0].canonical_digest,
                detail="fixture: no-action emitted",
            )
        )
        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.FLOW_HALTED,
                instrument_key=fx.instrument_key(),
                halt_reason=HaltReason.AT_MOST_ONE_EXPOSURE_HELD,
                detail="fixture: capacity denial",
            )
        )
        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.DECISION_WITHHELD,
                instrument_key=fx.instrument_key(),
                halt_reason=HaltReason.REGISTRY_MISSING,
                detail="fixture: withheld, carries no capsule id",
            )
        )
    finally:
        store.close()
    conn = sqlite3.connect(tmp_path / EVIDENCE_FILE_NAME)
    try:
        rows = list(conn.execute("SELECT kind, payload_json FROM entries ORDER BY seq"))
    finally:
        conn.close()
    return [{"kind": kind, "payload_json": payload} for kind, payload in rows]


def value_view(snapshot_id: str) -> ContextValueView:
    """One resolved Critical Input value, bound to ``snapshot_id``.

    The extractor's value-view counts read this surface; a fixture in which
    every tick published ``null`` would exercise only one of its three shapes.
    """
    return ContextValueView(
        snapshot_id=snapshot_id,
        snapshot_canonical_digest=f"sd-{snapshot_id}",
        values=(
            ContextValue(
                field_key="close_x100",
                value=451_250,
                as_of=AS_OF_MS,
                payload_digest="pd-fixture",
                observation_ref="raw-fixture",
            ),
        ),
        canonical_digest="vv-digest-fixture",
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )


def tick_event(seq: int, *, with_view: bool) -> EngineEvent:
    """The fixture tick, optionally carrying a resolved value view."""
    event = fx.decision_tick_event(seq=seq)
    if not with_view:
        return event
    payload = event.decision_tick
    assert payload is not None
    bound = payload.capsule.critical_input_snapshot.snapshot_id
    assert bound is not None
    return event.model_copy(
        update={
            "decision_tick": payload.model_copy(
                update={"value_view": value_view(bound)}
            )
        }
    )


def real_inbox_payloads(tmp_path: Path) -> list[dict[str, Any]]:
    """Two admitted ``DECISION_TICK`` events through the REAL inbox, as stored.

    Each row is marked handling-started and consumed through the real
    :meth:`SqliteEventInbox.mark_handling_started` /
    :meth:`~SqliteEventInbox.mark_consumed`, with the ``evidence_seq`` values a
    real driver run writes (``STAMPS``; the live proof is
    :func:`test_the_drivers_receipts_bracket_the_decision_records_it_writes`).
    Those two columns are the durable bracket the extractor attributes a
    capsule-less decision record by.
    """
    inbox = SqliteEventInbox(
        tmp_path / INBOX_FILE_NAME, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
    )
    try:
        for seq in TICK_SEQS:
            receipt = inbox.enqueue(tick_event(seq, with_view=seq == TICK_SEQS[1]))
            started, consumed = STAMPS[seq]
            inbox.mark_handling_started(receipt.seq, evidence_seq=started, generation=1)
            inbox.mark_consumed(receipt.seq, evidence_seq=consumed, generation=1)
    finally:
        inbox.close()
    conn = sqlite3.connect(tmp_path / INBOX_FILE_NAME)
    try:
        rows = list(
            conn.execute(
                "SELECT kind, payload_json, handling_started_evidence_seq, "
                "consumed_evidence_seq FROM events ORDER BY seq"
            )
        )
    finally:
        conn.close()
    return [
        {
            "kind": kind,
            "payload_json": payload,
            "handling_started_evidence_seq": started,
            "consumed_evidence_seq": consumed,
        }
        for kind, payload, started, consumed in rows
    ]


def snapshot_cases() -> dict[str, tuple[CriticalInputSnapshot, str, Any]]:
    """One issued snapshot per FieldState shape plan §5 M5 distinguishes.

    ``valid`` is the healthy bar; ``stale`` carries a STALE field evaluation —
    the one M5's first number counts; ``unknown`` carries an UNKNOWN
    evaluation over a STALE OBSERVATION, which is the pair the extractor must
    report apart (``tos.marketfeed.value.value_field_state`` takes the worst
    of both, so neither surface stands for the other).
    """
    payload = mf.preimage(close=451_250)
    return {
        "valid": (
            mf.issue_snapshot(
                observations=(
                    mf.observation(
                        raw_event_id="raw-valid", payload=payload, as_of=AS_OF_MS
                    ),
                ),
                field_evaluations=(
                    FieldEvaluation(field_ref="close", state=FieldState.VALID),
                ),
                instruments=(INSTRUMENT,),
            ),
            "raw-valid",
            payload,
        ),
        "stale": (
            mf.issue_snapshot(
                observations=(
                    mf.observation(
                        raw_event_id="raw-stale",
                        payload=payload,
                        as_of=AS_OF_MS + 60_000,
                    ),
                ),
                field_evaluations=(
                    FieldEvaluation(field_ref="close", state=FieldState.STALE),
                ),
                instruments=(INSTRUMENT,),
            ),
            "raw-stale",
            payload,
        ),
        "unknown": (
            mf.issue_snapshot(
                observations=(
                    mf.observation(
                        raw_event_id="raw-unknown",
                        payload=payload,
                        as_of=AS_OF_MS + 120_000,
                        field_state=FieldState.STALE,
                    ),
                ),
                field_evaluations=(
                    FieldEvaluation(field_ref="close", state=FieldState.UNKNOWN),
                ),
                instruments=(INSTRUMENT,),
            ),
            "raw-unknown",
            payload,
        ),
    }


def real_marketfeed_snapshots(tmp_path: Path) -> dict[str, dict[str, Any]]:
    """Those three snapshots through the REAL snapshot store, as stored."""
    store = SqliteSnapshotStore(tmp_path / MARKETFEED_FILE_NAME, monotonic_ns=lambda: 0)
    cases = snapshot_cases()
    try:
        for snapshot, raw_event_id, preimage in cases.values():
            store.put(snapshot, {raw_event_id: preimage})
    finally:
        store.close()
    conn = sqlite3.connect(tmp_path / MARKETFEED_FILE_NAME)
    try:
        stored = {
            str(snapshot_id): (instrument, as_of_ms, snapshot_json)
            for snapshot_id, instrument, as_of_ms, snapshot_json in conn.execute(
                "SELECT snapshot_id, instrument, as_of_ms, snapshot_json FROM snapshots"
            )
        }
        covered = {
            str(snapshot_id): raw_event_id
            for snapshot_id, raw_event_id in conn.execute(
                "SELECT snapshot_id, raw_event_id FROM preimages"
            )
        }
    finally:
        conn.close()
    rows: dict[str, dict[str, Any]] = {}
    for name, (snapshot, _raw_event_id, _preimage) in cases.items():
        assert snapshot.snapshot_id is not None
        instrument, as_of_ms, snapshot_json = stored[snapshot.snapshot_id]
        rows[name] = {
            "snapshot_id": snapshot.snapshot_id,
            "instrument": instrument,
            "as_of_ms": as_of_ms,
            "snapshot_json": snapshot_json,
            "raw_event_id": covered[snapshot.snapshot_id],
        }
    return rows


def test_the_committed_evidence_payloads_are_what_the_store_writes(
    tmp_path: Path, pinned: dict[str, Any]
) -> None:
    """**The hinge that would have caught the BLOCKER.**

    Byte equality, not a projection: the extractor parses these exact strings,
    and the defect it missed was one level of nesting — ``{"payload": …}``
    around the record. A comparison of selected fields would have agreed with
    the broken reader as happily as with the fixed one.

    When this goes red the store's wire shape moved; regenerate the fixture in
    the same PR and check what ``session_inputs.py`` now reads.
    """
    assert real_evidence_payloads(tmp_path) == pinned["payloads"]["evidence_entries"]
    # and the nesting itself, named, so a reader of this file sees the trap
    first = json.loads(pinned["payloads"]["evidence_entries"][0]["payload_json"])
    assert set(first) == {"payload", "masked_keys"}
    assert first["payload"]["outcome_type"] == "NoActionOutcome"
    assert first["payload"]["capsule_id"]


def test_the_committed_inbox_payloads_are_what_the_inbox_writes(
    tmp_path: Path, pinned: dict[str, Any]
) -> None:
    """The keyed link's own hinge (Claude-lane MEDIUM M1).

    The extractor joins ``decision.capsule_id`` to this event's
    ``decision_tick.capsule.capsule_id`` and reads the bar's snapshot id from
    ``…capsule.critical_input_snapshot.snapshot_id``. Both paths are asserted
    here against bytes the real inbox wrote, so a field that moves inside
    ``EngineEvent`` is red here rather than silently unjoinable there.
    """
    assert real_inbox_payloads(tmp_path) == pinned["payloads"]["inbox_events"]
    rows = pinned["payloads"]["inbox_events"]
    event = json.loads(rows[0]["payload_json"])
    assert event["kind"] == "DECISION_TICK"
    assert event["decision_tick"]["capsule"]["capsule_id"]
    assert event["decision_tick"]["capsule"]["critical_input_snapshot"]["snapshot_id"]
    # Both shapes of the resolver's value_view surface, so the extractor's
    # counting path is exercised on real bytes rather than on one of them:
    # the first tick published none, the second a resolved view.
    assert event["decision_tick"]["value_view"] is None
    second = json.loads(rows[1]["payload_json"])["decision_tick"]["value_view"]
    assert second is not None and len(second["values"]) == 1
    # and the bracket columns the capsule-less attribution rests on
    for row in rows:
        assert row["handling_started_evidence_seq"] is not None
        assert row["consumed_evidence_seq"] > row["handling_started_evidence_seq"]


def test_the_committed_snapshot_rows_are_what_the_snapshot_store_writes(
    tmp_path: Path, pinned: dict[str, Any]
) -> None:
    """**M5's own hinge (Claude-lane MEDIUM R2).**

    ``snapshots.snapshot_json`` is ``CriticalInputSnapshot.model_dump_json()``,
    and the extractor counts STALE out of its ``field_evaluations[*].state``.
    Byte equality here, plus the states named, so that a FieldState rename or
    a moved key is red in the PR that makes it rather than a silent zero in a
    genesis count.
    """
    assert (
        real_marketfeed_snapshots(tmp_path)
        == pinned["payloads"]["marketfeed_snapshots"]
    )
    states = {
        name: json.loads(row["snapshot_json"])
        for name, row in pinned["payloads"]["marketfeed_snapshots"].items()
    }
    assert [
        evaluation["state"] for evaluation in states["stale"]["field_evaluations"]
    ] == [FieldState.STALE.value]
    assert [
        evaluation["state"] for evaluation in states["unknown"]["field_evaluations"]
    ] == [FieldState.UNKNOWN.value]
    # the other surface the same aggregate reads, carried by a DIFFERENT row
    assert [
        observation["field_state"] for observation in states["unknown"]["observations"]
    ] == [FieldState.STALE.value]
    assert [
        evaluation["state"] for evaluation in states["valid"]["field_evaluations"]
    ] == [FieldState.VALID.value]


def test_the_drivers_receipts_bracket_the_decision_records_it_writes(
    tmp_path: Path,
) -> None:
    """**The mechanism the capsule-less attribution rests on, on a real driver.**

    ``tools/tos_cp3/session_inputs.py`` attributes a ``DECISION_WITHHELD`` /
    ``COORDINATOR_PRECONDITION_REFUSED`` record — which names no capsule — to
    the unique admitted tick whose ``(handling_started_evidence_seq,
    consumed_evidence_seq]`` window contains the record's evidence ``seq``.
    That is only sound if the driver really writes those two receipts around
    the handler, stamps both onto the inbox row, and never interleaves two
    events' windows. All three are asserted here against
    :class:`~tos_runtime.engine.driver.EngineDriver` itself, with the kernel's
    own evidence going to the SAME durable store the extractor reads.

    When this goes red the extractor's unkeyed attribution has lost its
    ground — not a fixture to regenerate.
    """
    store = SqliteEvidenceStore(
        tmp_path / EVIDENCE_FILE_NAME, key_provider=FixedKeyProvider()
    )
    inbox = SqliteEventInbox(
        tmp_path / INBOX_FILE_NAME, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
    )
    emergency = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    driver = EngineDriver(
        core=fx.build_core(sink=EngineEvidenceSinkAdapter(store)),
        inbox=inbox,
        evidence_store=store,
        emergency_log=emergency,
        scheme=get_scheme(EV_L1_PROVISIONAL_VERSION),
        continuity_id="cp3-session-store-reads",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(inbox, store, emergency),
        finality_producer=fx.finality_producer(),
    )
    try:
        for seq in TICK_SEQS:
            driver.enqueue_and_run(fx.decision_tick_event(seq=seq))
    finally:
        store.close()
        inbox.close()

    conn = sqlite3.connect(tmp_path / EVIDENCE_FILE_NAME)
    try:
        entries = list(conn.execute("SELECT seq, kind FROM entries ORDER BY seq"))
    finally:
        conn.close()
    conn = sqlite3.connect(tmp_path / INBOX_FILE_NAME)
    try:
        rows = list(
            conn.execute(
                "SELECT seq, handling_started_evidence_seq, consumed_evidence_seq "
                "FROM events ORDER BY seq"
            )
        )
    finally:
        conn.close()

    assert len(rows) == len(TICK_SEQS)
    windows = []
    for _seq, started, consumed in rows:
        assert started is not None and consumed is not None
        assert consumed > started
        windows.append((started, consumed))
    # disjoint and ordered: one event is fully bookkept before the next pulls
    assert all(
        later[0] > earlier[1] for earlier, later in zip(windows, windows[1:])
    ), windows
    # the receipts are the window's own ends, by kind
    kinds = dict(entries)
    for started, consumed in windows:
        assert kinds[started] == "EVENT_HANDLING_STARTED"
        assert kinds[consumed] == "EVENT_CONSUMED"
    # and every decision record the kernel wrote is inside exactly one window
    decisions = [
        seq
        for seq, kind in entries
        if kind
        in {
            "DECISION_OUTCOME_EMITTED",
            "DECISION_WITHHELD",
            "DECISION_DEGRADED",
            "COORDINATOR_PRECONDITION_REFUSED",
        }
    ]
    assert len(decisions) == len(TICK_SEQS), entries
    for seq in decisions:
        holders = [window for window in windows if window[0] < seq <= window[1]]
        assert len(holders) == 1, (seq, windows)


def test_the_two_halves_of_the_fixture_name_the_same_capsules(
    pinned: dict[str, Any],
) -> None:
    """The evidence record and the tick must meet, or the join is untested.

    Without this a regeneration could leave the evidence half quoting one
    capsule and the inbox half admitting another; the tools-side join test
    would then refuse for the wrong reason and still look red-proof.
    """
    emitted = [
        json.loads(entry["payload_json"])["payload"]
        for entry in pinned["payloads"]["evidence_entries"]
        if entry["kind"] == "DECISION_OUTCOME_EMITTED"
    ]
    admitted = {
        json.loads(event["payload_json"])["decision_tick"]["capsule"]["capsule_id"]
        for event in pinned["payloads"]["inbox_events"]
    }
    assert emitted, "the fixture has no emitted-outcome record"
    assert {record["capsule_id"] for record in emitted} <= admitted


def test_the_scheme_the_fixture_was_built_under_is_still_the_registered_one() -> None:
    """The capsule ids above are digests. If the canonical scheme moves, the
    fixture's ids move with it — stated here so a reader of a red
    byte-comparison above knows where else to look."""
    assert get_scheme(EV_L1_PROVISIONAL_VERSION) is not None
    assert fx.SCHEME.version == EV_L1_PROVISIONAL_VERSION
