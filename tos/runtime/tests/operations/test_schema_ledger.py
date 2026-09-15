"""Schema-ledger boot-check tests (TOS Phase 5 W4 plan §2 decision 3).

Exercises the real wiring in the three runtime-owned durable stores (evidence, RCL, inbox) —
never only the generic :func:`~tos_runtime.operations.schema_ledger.ensure_schema_current`
helper in isolation — so a regression in any store's own constructor call site is caught here,
not just a regression in the shared helper.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION, SqliteEventInbox
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, SqliteEvidenceStore
from tos_runtime.operations.schema_ledger import (
    SchemaVersionRefused,
    compute_schema_shape_digest,
    ensure_schema_current,
    file_is_fresh,
)
from tos_runtime.operations.schema_migrations import (
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
    rows = conn.execute("SELECT version, applied_by FROM schema_ledger").fetchall()
    assert rows == [(EVIDENCE_SCHEMA_VERSION, "MIGRATE")]
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


def test_apply_migrations_refuses_an_unknown_store_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown store_name"):
        apply_migrations(tmp_path / "whatever.sqlite3", "not-a-real-store")


def test_schema_version_reads_a_closed_file(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    store.close()
    assert schema_version(path) == EVIDENCE_SCHEMA_VERSION
