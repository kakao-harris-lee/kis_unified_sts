"""Schema-ledger boot-check tests (TOS Phase 5 W4 plan §2 decision 3).

Exercises the real wiring in the four runtime-owned durable stores (evidence, RCL, inbox,
marketfeed) — never only the generic :func:`~tos_runtime.operations.schema_ledger
.ensure_schema_current` helper in isolation — so a regression in any store's own constructor
call site is caught here, not just a regression in the shared helper.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION, SqliteEventInbox
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, SqliteEvidenceStore
from tos_runtime.marketfeed.store import MARKETFEED_SCHEMA_VERSION, SqliteSnapshotStore
from tos_runtime.operations.schema_ledger import (
    SCHEMA_LEDGER_TABLE_SQL,
    SchemaVersionRefused,
    compute_schema_shape_digest,
    ensure_schema_current,
    file_is_fresh,
)
from tos_runtime.operations.schema_migrations import (
    EVIDENCE_MIGRATIONS,
    MARKETFEED_MIGRATIONS,
    RCL_MIGRATIONS,
    SchemaMigrationRefused,
    apply_migrations,
    schema_version,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.schema import RCL_SCHEMA_VERSION

from .conftest import FixedKeyProvider

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


# -- fresh-file genesis stamp, per real store -------------------------------------------------


def test_evidence_store_stamps_created_ledger_row_on_a_fresh_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    assert store.connection.execute("PRAGMA user_version").fetchone()[0] == (
        EVIDENCE_SCHEMA_VERSION
    )
    rows = store.connection.execute(
        "SELECT version, applied_by FROM schema_ledger"
    ).fetchall()
    assert rows == [(EVIDENCE_SCHEMA_VERSION, "CREATED")]
    store.close()


def test_rcl_log_stamps_created_ledger_row_on_a_fresh_file(tmp_path: Path) -> None:
    evidence = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    rcl = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence)
    assert rcl._conn.execute("PRAGMA user_version").fetchone()[0] == RCL_SCHEMA_VERSION
    rows = rcl._conn.execute("SELECT version, applied_by FROM schema_ledger").fetchall()
    assert rows == [(RCL_SCHEMA_VERSION, "CREATED")]
    rcl.close()
    evidence.close()


def test_inbox_stamps_created_ledger_row_on_a_fresh_file(tmp_path: Path) -> None:
    inbox = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=_SCHEME)
    assert inbox._conn.execute("PRAGMA user_version").fetchone()[0] == (
        INBOX_SCHEMA_VERSION
    )
    rows = inbox._conn.execute(
        "SELECT version, applied_by FROM schema_ledger"
    ).fetchall()
    assert rows == [(INBOX_SCHEMA_VERSION, "CREATED")]
    inbox.close()


# -- reopen at the SAME version passes silently ------------------------------------------------


def test_reopening_a_store_at_the_current_version_passes_silently(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.sqlite3"
    store1 = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    store1.close()
    store2 = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    # Still exactly one ledger row — reopening at the current version never re-stamps.
    rows = store2.connection.execute("SELECT version FROM schema_ledger").fetchall()
    assert rows == [(EVIDENCE_SCHEMA_VERSION,)]
    store2.close()


# -- M3: a behind (or ahead) user_version refuses boot, mechanically ---------------------------


def test_a_behind_user_version_refuses_boot(tmp_path: Path) -> None:
    """(M3) If the ``user_version`` check were removed, a file stamped at a version BEHIND the
    code's own would boot successfully instead of refusing — this assertion is exactly what
    would go red under that mutation."""
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    store.close()

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    with pytest.raises(SchemaVersionRefused, match="BEHIND"):
        SqliteEvidenceStore(path, key_provider=FixedKeyProvider())


def test_an_ahead_user_version_also_refuses_boot(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    store.close()

    conn = sqlite3.connect(str(path))
    conn.execute(f"PRAGMA user_version = {EVIDENCE_SCHEMA_VERSION + 1}")
    conn.close()

    with pytest.raises(SchemaVersionRefused, match="AHEAD"):
        SqliteEvidenceStore(path, key_provider=FixedKeyProvider())


def test_inbox_behind_user_version_refuses_boot(tmp_path: Path) -> None:
    path = tmp_path / "inbox.sqlite3"
    inbox = SqliteEventInbox(path, scheme=_SCHEME)
    inbox.close()

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    with pytest.raises(SchemaVersionRefused, match="BEHIND"):
        SqliteEventInbox(path, scheme=_SCHEME)


# -- schema_ledger itself is append-only, mechanically -----------------------------------------


def test_schema_ledger_table_rejects_update_and_delete(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    conn = store.connection
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE schema_ledger SET applied_by = 'TAMPERED'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM schema_ledger")
    store.close()


# -- generic helper behavior --------------------------------------------------------------------


def test_file_is_fresh_true_before_any_table_and_false_after(tmp_path: Path) -> None:
    path = tmp_path / "bare.sqlite3"
    conn = sqlite3.connect(str(path))
    assert file_is_fresh(conn) is True
    conn.execute("CREATE TABLE t (x INTEGER)")
    assert file_is_fresh(conn) is False
    conn.close()


def test_compute_schema_shape_digest_is_stable_and_sensitive_to_shape(
    tmp_path: Path,
) -> None:
    path_a = tmp_path / "a.sqlite3"
    path_b = tmp_path / "b.sqlite3"
    conn_a = sqlite3.connect(str(path_a))
    conn_a.execute("CREATE TABLE t (x INTEGER, y TEXT)")
    conn_b = sqlite3.connect(str(path_b))
    conn_b.execute("CREATE TABLE t (x INTEGER, y TEXT)")

    digest_a = compute_schema_shape_digest(conn_a, ("t",))
    digest_b = compute_schema_shape_digest(conn_b, ("t",))
    assert digest_a == digest_b

    conn_b.execute("ALTER TABLE t ADD COLUMN z INTEGER")
    digest_b_changed = compute_schema_shape_digest(conn_b, ("t",))
    assert digest_b_changed != digest_a
    conn_a.close()
    conn_b.close()


def test_ensure_schema_current_fresh_file_uses_the_given_migration_digest(
    tmp_path: Path,
) -> None:
    path = tmp_path / "generic.sqlite3"
    conn = sqlite3.connect(str(path))
    was_fresh = file_is_fresh(conn)
    conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY)")
    ensure_schema_current(
        conn,
        store_name="widgets-store",
        schema_version=7,
        was_fresh=was_fresh,
        migration_digest="digest-under-test",
        monotonic_ns=lambda: 42,
    )
    row = conn.execute(
        "SELECT version, applied_at_monotonic_ns, migration_digest, applied_by "
        "FROM schema_ledger"
    ).fetchone()
    assert row == (7, 42, "digest-under-test", "CREATED")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    conn.close()


# -- schema_migrations.apply_migrations ----------------------------------------------------------


def test_apply_migrations_brings_a_pre_ledger_file_to_baseline(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    store.close()

    # Simulate a file created before this wave: no schema_ledger table, user_version 0.
    conn = sqlite3.connect(str(path))
    conn.execute("DROP TABLE schema_ledger")
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    apply_migrations(path, "evidence")

    assert schema_version(path) == EVIDENCE_SCHEMA_VERSION
    conn = sqlite3.connect(str(path))
    rows = conn.execute(
        "SELECT version, applied_by FROM schema_ledger ORDER BY version ASC"
    ).fetchall()
    # Every registered migration, in order — the evidence store moved past baseline when the
    # growth plan's §2 A2 index landed, so a pre-ledger file climbs the whole ladder in one run.
    assert rows == [(migration.version, "MIGRATE") for migration in EVIDENCE_MIGRATIONS]
    conn.close()

    # Migrated file now boots cleanly.
    reopened = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    reopened.close()


def test_apply_migrations_refuses_a_shape_it_does_not_recognize(tmp_path: Path) -> None:
    path = tmp_path / "bad_evidence.sqlite3"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE entries (seq INTEGER PRIMARY KEY, kind TEXT)")
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    with pytest.raises(SchemaMigrationRefused, match="entries"):
        apply_migrations(path, "evidence")


def test_apply_migrations_is_a_noop_once_already_at_target(tmp_path: Path) -> None:
    path = tmp_path / "rcl.sqlite3"
    # Build a real RCL log directly at baseline via its own constructor.
    evidence = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    rcl = SqliteCommitLog(path, evidence_port=evidence)
    rcl.close()
    evidence.close()

    apply_migrations(path, "rcl")  # should not raise, nothing to do
    conn = sqlite3.connect(str(path))
    rows = conn.execute("SELECT version, applied_by FROM schema_ledger").fetchall()
    conn.close()
    assert rows == [(RCL_MIGRATIONS[-1].version, "CREATED")]


# -- marketfeed store: schema-version-drift regression pattern -------------------------------
#
# This wave has hit the same shape three times: a registry paired with a hand-maintained
# satellite that nothing pins them equal. `STORE_MIGRATIONS` vs `compose/cli.py`'s hardcoded
# `path_by_store` dict (fixed in 4bdb291a); `backup_set.py`'s `_last_seq_for` hardcoded table
# dict (lane E); and here, a THIRD instance — `MARKETFEED_SCHEMA_VERSION`
# (`tos_runtime.marketfeed.store`) and `MARKETFEED_MIGRATIONS[-1].version`
# (`tos_runtime.operations.schema_migrations`) are two hand-maintained integers in two files,
# harmless today only because both happen to be ``1``. Bump only one and the failure is a
# PERMANENT DEADLOCK with a CLI that reports success: a v1 data dir meets code expecting v2,
# `SqliteSnapshotStore.__init__` refuses with `SchemaVersionRefused(BEHIND)`, the operator runs
# `migrate` — and `apply_migrations` silently no-ops because ITS OWN `target_version` never
# moved. Reboot, refused again.
#
# The test below is deliberately NOT a comparison of the two constants to each other in the
# abstract (that would pass even if BOTH constants were bumped in lockstep incorrectly, or
# neither reflects what the real file ends up stamped with). It goes through the REAL file and
# the REAL `apply_migrations`, the same shape as `test_apply_migrations_is_a_noop_once_already
# _at_target` above for RCL — so it catches drift in either direction: `MARKETFEED_SCHEMA_VERSION`
# ahead of `MARKETFEED_MIGRATIONS[-1].version` fails the assert directly; the reverse makes the
# store's own genesis stamp disagree with what `apply_migrations` would consider "current".


def test_apply_migrations_is_a_noop_once_already_at_target_marketfeed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "marketfeed.sqlite3"
    store = SqliteSnapshotStore(path)
    store.close()

    apply_migrations(path, "marketfeed")  # should not raise, nothing to do

    conn = sqlite3.connect(str(path))
    rows = conn.execute("SELECT version, applied_by FROM schema_ledger").fetchall()
    conn.close()
    assert rows == [(MARKETFEED_MIGRATIONS[-1].version, "CREATED")]
    # Pins the two hand-maintained integers together through the real construction path, not
    # merely against each other.
    assert MARKETFEED_MIGRATIONS[-1].version == MARKETFEED_SCHEMA_VERSION


def test_apply_migrations_stamps_a_truly_fresh_marketfeed_file(tmp_path: Path) -> None:
    """``migrate`` may run against a data-dir path no store has ever opened (a fresh deploy) —
    ``apply_migrations`` alone must be able to bring an empty file to baseline."""
    path = tmp_path / "marketfeed.sqlite3"
    path.touch()

    apply_migrations(path, "marketfeed")

    assert schema_version(path) == MARKETFEED_MIGRATIONS[-1].version
    conn = sqlite3.connect(str(path))
    rows = conn.execute("SELECT version, applied_by FROM schema_ledger").fetchall()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    conn.close()
    assert rows == [(MARKETFEED_MIGRATIONS[-1].version, "MIGRATE")]
    assert {"snapshots", "preimages", "schema_ledger"} <= tables

    # The migrated-from-scratch file now boots cleanly through the real store.
    reopened = SqliteSnapshotStore(path)
    reopened.close()


def test_apply_migrations_refuses_a_marketfeed_shape_it_does_not_recognize(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad_marketfeed.sqlite3"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE snapshots (snapshot_id TEXT PRIMARY KEY, extra_column TEXT)"
    )
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    with pytest.raises(SchemaMigrationRefused, match="snapshots"):
        apply_migrations(path, "marketfeed")


def test_apply_migrations_refuses_an_unknown_store_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown store_name"):
        apply_migrations(tmp_path / "whatever.sqlite3", "not-a-real-store")


def test_schema_version_reads_a_closed_file(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    store.close()
    assert schema_version(path) == EVIDENCE_SCHEMA_VERSION


# -- RCL v1 -> v2 promotion (kernel round #4 K-4: reservations gains committed_vector_json) ---


def test_rcl_v1_data_dir_promotes_to_v2_preserving_existing_rows(
    tmp_path: Path,
) -> None:
    """A genuinely pre-existing v1 RCL file (built from ``RCL_MIGRATIONS[0]``'s own registered
    baseline statements — never this test's own ad hoc DDL) promotes to v2 via
    :func:`apply_migrations`, and the reservation row committed under v1 survives unchanged —
    the v2 migration is a bare ``ALTER TABLE ... ADD COLUMN`` (nullable), never a rebuild.
    """
    path = tmp_path / "rcl.sqlite3"
    baseline = RCL_MIGRATIONS[0]
    assert baseline.version == 1

    conn = sqlite3.connect(str(path))
    for statement in baseline.statements:
        conn.execute(statement)
    conn.execute(
        "INSERT INTO reservations (reservation_id, state, last_seq, scope_account, "
        "scope_instrument) VALUES (?, ?, ?, ?, ?)",
        ("resv-v1-legacy", "POTENTIALLY_LIVE", 7, "acct-1", "K200F"),
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    assert schema_version(path) == 1

    apply_migrations(path, "rcl")

    assert schema_version(path) == RCL_MIGRATIONS[-1].version
    assert (
        RCL_MIGRATIONS[-1].version == RCL_SCHEMA_VERSION
    )  # same lockstep pin as marketfeed's

    conn = sqlite3.connect(str(path))
    columns = {row[1] for row in conn.execute("PRAGMA table_info(reservations)")}
    assert "committed_vector_json" in columns
    row = conn.execute(
        "SELECT reservation_id, state, last_seq, scope_account, scope_instrument, "
        "committed_vector_json FROM reservations WHERE reservation_id = ?",
        ("resv-v1-legacy",),
    ).fetchone()
    conn.close()
    # The v1 row's original five columns are byte-for-byte preserved; the new column is a
    # legitimate NULL (no committed vector was ever recorded under v1), never a fabricated one.
    assert row == ("resv-v1-legacy", "POTENTIALLY_LIVE", 7, "acct-1", "K200F", None)

    # The promoted file now boots cleanly through the real log, and the real projection
    # confirms the preserved row is genuinely usable, not merely present as raw bytes.
    evidence = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    rcl = SqliteCommitLog(path, evidence_port=evidence)
    try:
        rows = list(rcl.reservation_rows())
        assert len(rows) == 1
        reservation_id, state, last_seq, scope = rows[0]
        assert (reservation_id, state.value, last_seq) == (
            "resv-v1-legacy",
            "POTENTIALLY_LIVE",
            7,
        )
        assert (scope.account, scope.instrument) == ("acct-1", "K200F")
        assert rcl.reservation_committed_vector("resv-v1-legacy") is None
    finally:
        rcl.close()
        evidence.close()


# -- evidence v1 -> v2 promotion (evidence growth plan §2 A2: entries_kind_seq index) ---------
#
# The measurement this migration answers to is in that plan's §7: every boot/recovery reader
# issues `WHERE kind = ?`/`WHERE kind IN (...)` over `entries`, and without an index each one
# is a full table scan whose cost grows with TOTAL history rather than with the kind asked for.
# The tests below pin the three properties that make the migration safe to run against a real
# paper store: the index really lands, no row's content moves, and the chain still verifies.

_INDEX_NAME = "entries_kind_seq"

#: Two real reader shapes, verbatim from `tos_runtime.engine.replay` (:194) and
#: `tos_runtime.recon.evidence_reader` (:150) — `EXPLAIN QUERY PLAN` over these is what proves
#: the index is actually reachable by the queries it was added for, rather than merely present.
_READER_SHAPES: tuple[tuple[str, tuple[object, ...]], ...] = (
    ("SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", ("ALPHA",)),
    (
        "SELECT payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq ASC",
        ("ALPHA", "BETA"),
    ),
    ("SELECT COUNT(*) FROM entries WHERE kind = ?", ("ABSENT",)),
)


def _index_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'entries'"
        )
    }


def _entry_rows(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Every column of every row, in seq order — the "did any byte move?" fixture."""
    return conn.execute(
        "SELECT seq, segment_id, kind, record_class, runtime_identity_json, payload_json, "
        "entry_digest, chain_digest, key_generation, appended_at_monotonic_ns "
        "FROM entries ORDER BY seq ASC"
    ).fetchall()


_SEEDED_ROWS = 4


def _seed_evidence(path: Path) -> None:
    """Append a few real, chained entries through the real store, then close it."""
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    try:
        for index in range(_SEEDED_ROWS):
            store.append(
                {"n": index, "note": "seeded"},
                kind="ALPHA" if index % 2 == 0 else "BETA",
                record_class="ALPHA" if index % 2 == 0 else "BETA",
            )
    finally:
        store.close()


def _build_v1_evidence_file(tmp_path: Path, path: Path) -> None:
    """Write the file a v1 deployment would have left behind, with a REAL chain in it.

    Built from ``EVIDENCE_MIGRATIONS[0]``'s own registered baseline statements — never this
    test's ad hoc DDL, the same discipline
    :func:`test_rcl_v1_data_dir_promotes_to_v2_preserving_existing_rows` follows. The rows are
    copied verbatim out of a throwaway store the CURRENT code seeded, so their
    ``entry_digest``/``chain_digest`` are genuine and the chain folds from genesis exactly as a
    v1 store's own would have.

    A v2 file cannot simply be demoted instead: its ``schema_ledger`` already holds the
    ``(2, CREATED)`` genesis row, ``version`` is that table's PRIMARY KEY, and the table is
    append-only by trigger — so ``apply_migrations`` would hit an ``IntegrityError`` inserting
    its own v2 row, which is an artefact of the demotion and not a fact about the migration.
    """
    donor = tmp_path / "donor.sqlite3"
    _seed_evidence(donor)
    donor_conn = sqlite3.connect(str(donor))
    try:
        rows = _entry_rows(donor_conn)
    finally:
        donor_conn.close()

    conn = sqlite3.connect(str(path))
    try:
        for statement in EVIDENCE_MIGRATIONS[0].statements:
            conn.execute(statement)
        conn.execute(SCHEMA_LEDGER_TABLE_SQL)
        conn.execute(
            "INSERT INTO schema_ledger "
            "(version, applied_at_monotonic_ns, migration_digest, applied_by) "
            "VALUES (?, ?, ?, ?)",
            (1, 0, EVIDENCE_MIGRATIONS[0].statements_digest, "CREATED"),
        )
        conn.executemany(
            "INSERT INTO entries (seq, segment_id, kind, record_class, "
            "runtime_identity_json, payload_json, entry_digest, chain_digest, "
            "key_generation, appended_at_monotonic_ns) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    finally:
        conn.close()


def test_evidence_v2_is_the_registered_head_migration() -> None:
    """The same lockstep pin marketfeed/RCL already carry: the store's own constant and the
    migration registry's head are two hand-maintained integers in two files, and a bump to one
    alone is a permanent deadlock (`migrate` no-ops, boot keeps refusing)."""
    assert EVIDENCE_MIGRATIONS[-1].version == EVIDENCE_SCHEMA_VERSION == 2


def test_a_fresh_evidence_file_gets_the_kind_index_at_genesis(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    try:
        assert _INDEX_NAME in _index_names(store.connection)
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2
    finally:
        store.close()


def test_a_v1_evidence_file_refuses_boot_and_names_migrate(tmp_path: Path) -> None:
    """The operator-visible half of the rollout: a v1 file does not silently boot slow, and
    does not silently self-migrate — it refuses, pointing at the ``migrate`` CLI."""
    path = tmp_path / "evidence.sqlite3"
    _build_v1_evidence_file(tmp_path, path)

    with pytest.raises(SchemaVersionRefused, match="BEHIND"):
        SqliteEvidenceStore(path, key_provider=FixedKeyProvider())


def test_a_refused_v1_boot_does_not_build_the_index(tmp_path: Path) -> None:
    """Boot is a check, never a migration (`operations.schema_ledger`'s own contract).

    Without the ``was_fresh`` guard in ``SqliteEvidenceStore.__init__`` this is exactly what
    would go red: ``CREATE INDEX IF NOT EXISTS`` is NOT the no-op that the ``CREATE TABLE``/
    ``CREATE TRIGGER`` statements beside it are, so a refused boot would still have written a
    full index into the file first — and would rebuild one an operator had just dropped to roll
    the migration back.
    """
    path = tmp_path / "evidence.sqlite3"
    _build_v1_evidence_file(tmp_path, path)

    with pytest.raises(SchemaVersionRefused):
        SqliteEvidenceStore(path, key_provider=FixedKeyProvider())

    conn = sqlite3.connect(str(path))
    try:
        assert _INDEX_NAME not in _index_names(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        conn.close()


def test_evidence_v1_promotes_to_v2_without_moving_a_single_row_byte(
    tmp_path: Path,
) -> None:
    """The migration's whole safety claim, asserted rather than argued: an index is an
    auxiliary structure, so every row's content, ``entry_digest`` and ``chain_digest`` are
    identical before and after, and the chain still verifies under the same key."""
    path = tmp_path / "evidence.sqlite3"
    _build_v1_evidence_file(tmp_path, path)
    assert schema_version(path) == 1

    conn = sqlite3.connect(str(path))
    try:
        before = _entry_rows(conn)
        assert _INDEX_NAME not in _index_names(conn)
    finally:
        conn.close()
    assert len(before) == _SEEDED_ROWS

    apply_migrations(path, "evidence")

    assert schema_version(path) == EVIDENCE_SCHEMA_VERSION
    conn = sqlite3.connect(str(path))
    try:
        after = _entry_rows(conn)
        assert _INDEX_NAME in _index_names(conn)
        ledger = conn.execute(
            "SELECT version, applied_by FROM schema_ledger ORDER BY version ASC"
        ).fetchall()
    finally:
        conn.close()

    assert after == before
    # The file was genesis-stamped at v2 and demoted by hand, so the only ledger row this
    # migration adds is the v2 MIGRATE one — the v1 row never existed on this file.
    assert (2, "MIGRATE") in ledger

    # The promoted file boots through the real store, and its chain still verifies.
    provider = FixedKeyProvider()
    reopened = SqliteEvidenceStore(path, key_provider=provider)
    try:
        key_generation, key_bytes = provider.current()
        assert reopened.verify({key_generation: key_bytes}) is True
        detailed = reopened.verify_detailed({key_generation: key_bytes})
        assert (detailed.ok, detailed.verified_links) == (True, _SEEDED_ROWS)
    finally:
        reopened.close()


def test_apply_migrations_brings_a_pre_ledger_evidence_file_all_the_way_to_v2(
    tmp_path: Path,
) -> None:
    """A file predating the schema ledger entirely (no ``schema_ledger`` table,
    ``user_version = 0``) runs BOTH registered migrations in one ``migrate``, ending indexed
    and bootable — the path a real pre-W4 paper data dir takes."""
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(f"DROP INDEX IF EXISTS {_INDEX_NAME}")
        conn.execute("DROP TABLE schema_ledger")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()

    apply_migrations(path, "evidence")

    assert schema_version(path) == EVIDENCE_SCHEMA_VERSION
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT version, applied_by FROM schema_ledger ORDER BY version ASC"
        ).fetchall()
        assert _INDEX_NAME in _index_names(conn)
    finally:
        conn.close()
    assert rows == [(1, "MIGRATE"), (2, "MIGRATE")]

    reopened = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    reopened.close()


def test_reader_query_shapes_scan_before_the_index_and_seek_after(
    tmp_path: Path,
) -> None:
    """``EXPLAIN QUERY PLAN`` over the real reader shapes, on the SAME file before and after.

    The "before" half is what makes this test live: an index that exists but that the readers'
    own query shape cannot use would still satisfy a bare "the index is present" assertion.
    """
    path = tmp_path / "evidence.sqlite3"
    _build_v1_evidence_file(tmp_path, path)

    conn = sqlite3.connect(str(path))
    try:
        for sql, params in _READER_SHAPES:
            plan = " ".join(
                str(part)
                for row in conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)
                for part in row
            )
            assert _INDEX_NAME not in plan, sql
            assert "SCAN entries" in plan, sql
    finally:
        conn.close()

    apply_migrations(path, "evidence")

    conn = sqlite3.connect(str(path))
    try:
        for sql, params in _READER_SHAPES:
            plan = " ".join(
                str(part)
                for row in conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)
                for part in row
            )
            assert _INDEX_NAME in plan, sql
            assert "SCAN entries" not in plan, sql
    finally:
        conn.close()


def test_appends_still_work_and_stay_chained_after_the_index_lands(
    tmp_path: Path,
) -> None:
    """The write side of the migration's cost: an index is maintained on every insert. The
    append path must still commit, still chain, and still be readable THROUGH the new index.
    """
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)

    provider = FixedKeyProvider()
    store = SqliteEvidenceStore(path, key_provider=provider)
    try:
        receipt = store.append(
            {"n": 99}, kind="ALPHA", record_class="ALPHA", segment_id=None
        )
        assert receipt.seq == _SEEDED_ROWS
        key_generation, key_bytes = provider.current()
        assert store.verify({key_generation: key_bytes}) is True
        rows = store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            ("ALPHA",),
        ).fetchall()
        assert len(rows) == 3
    finally:
        store.close()


# -- HIGH-1 (review 2026-09-30): the documented rollback must be reversible ---------------------
#
# The runbook (docs/runbooks/tos-paper-boot.md §4-A) tells an operator how to roll v2 back. Both
# tests below were RED before the `apply_migrations` fix: (1) the ledger's surviving v2 row made
# a re-`migrate` abort with `IntegrityError UNIQUE constraint failed: schema_ledger.version`,
# stranding the file at v1 with no index — refused by v2 code and unreachable by `migrate`;
# (2) an index dropped while `user_version` stayed at 2 was invisible to every check
# (`compute_schema_shape_digest` reads `PRAGMA table_info`, which does not see indexes) and
# `migrate` no-op'd, so nothing could rebuild it.

#: The rollback the runbook prints, verbatim. Kept as literal SQL, split exactly as an operator
#: would paste it, so this test fails if the runbook and the code ever disagree about the
#: procedure rather than merely about its wording.
_RUNBOOK_ROLLBACK_SQL: tuple[str, ...] = (
    "DROP INDEX IF EXISTS entries_kind_seq",
    "PRAGMA user_version = 1",
)


def _run_rollback(path: Path, statements: tuple[str, ...]) -> None:
    conn = sqlite3.connect(str(path))
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


def test_the_runbook_rollback_can_be_rolled_forward_again(tmp_path: Path) -> None:
    """The whole point of documenting a rollback: it has to be reversible."""
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)
    _run_rollback(path, _RUNBOOK_ROLLBACK_SQL)

    conn = sqlite3.connect(str(path))
    try:
        assert _INDEX_NAME not in _index_names(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        # The v2 ledger row SURVIVES the rollback — schema_ledger is append-only and `version`
        # is its PRIMARY KEY, which is exactly what used to make the roll-forward abort.
        assert (2,) in conn.execute("SELECT version FROM schema_ledger").fetchall()
    finally:
        conn.close()

    outcome = apply_migrations(path, "evidence")

    assert outcome.applied == (2,)
    # Applied but NOT re-ledgered: the row was already there, and an append-only ledger records
    # "first applied here", not a run count.
    assert outcome.ledgered == ()
    assert schema_version(path) == EVIDENCE_SCHEMA_VERSION
    conn = sqlite3.connect(str(path))
    try:
        assert _INDEX_NAME in _index_names(conn)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM schema_ledger WHERE version = 2"
            ).fetchone()[0]
            == 1
        )
    finally:
        conn.close()

    # And the rolled-forward file boots and still verifies.
    provider = FixedKeyProvider()
    store = SqliteEvidenceStore(path, key_provider=provider)
    try:
        key_generation, key_bytes = provider.current()
        assert store.verify({key_generation: key_bytes}) is True
    finally:
        store.close()


def test_migrate_rebuilds_an_index_dropped_at_the_current_version(
    tmp_path: Path,
) -> None:
    """The half-rollback: index gone, ``user_version`` still 2.

    Nothing refuses this state — v2 code boots and silently runs every by-kind read as a full
    scan — so ``migrate`` has to be able to notice and repair it. Before the repair pass it
    could not: its loop skips every version ``<= current_version``.
    """
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)
    _run_rollback(path, ("DROP INDEX entries_kind_seq",))

    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert _INDEX_NAME not in _index_names(conn)
    finally:
        conn.close()
    # The state really is undetectable by the boot check — this is why the repair exists.
    SqliteEvidenceStore(path, key_provider=FixedKeyProvider()).close()

    outcome = apply_migrations(path, "evidence")

    assert outcome.applied == ()
    assert outcome.repaired == (_INDEX_NAME,)
    assert outcome.changed is True
    conn = sqlite3.connect(str(path))
    try:
        assert _INDEX_NAME in _index_names(conn)
        # No second ledger row was invented for a repair — it is not a migration.
        assert conn.execute("SELECT COUNT(*) FROM schema_ledger").fetchone()[0] == 1
    finally:
        conn.close()


def test_migrate_on_a_healthy_file_reports_no_change(tmp_path: Path) -> None:
    """The repair pass must be a no-op on a healthy file, or every `migrate` would look like it
    had found damage."""
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)

    outcome = apply_migrations(path, "evidence")

    assert (outcome.applied, outcome.repaired, outcome.changed) == ((), (), False)
    assert outcome.from_version == outcome.to_version == EVIDENCE_SCHEMA_VERSION


def test_a_non_idempotent_migration_is_never_re_run_by_the_repair_pass(
    tmp_path: Path,
) -> None:
    """RCL v2 is a bare ``ALTER TABLE ... ADD COLUMN``, which raises "duplicate column name" on a
    second run — so it declares NO ``repair_statements`` and the repair pass must leave it alone.

    This is the test that keeps the repair pass from being generalized into "re-run the head
    migration", which would break the moment a store's head migration changes column shape.
    """
    assert RCL_MIGRATIONS[-1].repair_statements == ()
    evidence = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    rcl = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence)
    rcl.close()
    evidence.close()

    first = apply_migrations(tmp_path / "rcl.sqlite3", "rcl")
    second = apply_migrations(tmp_path / "rcl.sqlite3", "rcl")

    assert first.changed is False
    assert second.changed is False
