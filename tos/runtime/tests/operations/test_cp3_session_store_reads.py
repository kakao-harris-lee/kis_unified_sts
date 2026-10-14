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
from tos.engine.records import EngineEvidenceRecord
from tos.engine.vocabulary import EvidenceKind, HaltReason
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION, SqliteEventInbox
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, SqliteEvidenceStore
from tos_runtime.marketfeed.store import (
    MARKETFEED_FILE_NAME,
    MARKETFEED_SCHEMA_VERSION,
)
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME, INBOX_FILE_NAME
from tos_runtime.operations.schema_migrations import STORE_MIGRATIONS

from ..engine import _fixtures as fx
from ..evidence.conftest import FixedKeyProvider

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


def real_inbox_payloads(tmp_path: Path) -> list[dict[str, str]]:
    """Two admitted ``DECISION_TICK`` events through the REAL inbox, as stored."""
    inbox = SqliteEventInbox(
        tmp_path / INBOX_FILE_NAME, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
    )
    try:
        for seq in TICK_SEQS:
            inbox.enqueue(fx.decision_tick_event(seq=seq))
    finally:
        inbox.close()
    conn = sqlite3.connect(tmp_path / INBOX_FILE_NAME)
    try:
        rows = list(conn.execute("SELECT kind, payload_json FROM events ORDER BY seq"))
    finally:
        conn.close()
    return [{"kind": kind, "payload_json": payload} for kind, payload in rows]


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
    event = json.loads(pinned["payloads"]["inbox_events"][0]["payload_json"])
    assert event["kind"] == "DECISION_TICK"
    assert event["decision_tick"]["capsule"]["capsule_id"]
    assert event["decision_tick"]["capsule"]["critical_input_snapshot"]["snapshot_id"]
    # value_view is the surface M5's "consumed STALE" count reads; absent here
    # (these fixtures publish none), and absence is itself one of the three
    # shapes the extractor counts.
    assert "value_view" in event["decision_tick"]


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
