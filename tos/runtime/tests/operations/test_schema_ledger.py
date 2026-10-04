"""Schema-ledger boot-check tests (TOS Phase 5 W4 plan §2 decision 3).

Exercises the real wiring in the four runtime-owned durable stores (evidence, RCL, inbox,
marketfeed) — never only the generic :func:`~tos_runtime.operations.schema_ledger
.ensure_schema_current` helper in isolation — so a regression in any store's own constructor
call site is caught here, not just a regression in the shared helper.
"""

from __future__ import annotations

import copy
import hashlib
import pickle
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION, SqliteEventInbox
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, SqliteEvidenceStore
from tos_runtime.marketfeed.store import MARKETFEED_SCHEMA_VERSION, SqliteSnapshotStore
from tos_runtime.operations.schema_ledger import (
    SCHEMA_LEDGER_TRIGGER_NAMES,
    SchemaLedgerUnprotected,
    SchemaVersionDirection,
    SchemaVersionRefused,
    compute_schema_shape_digest,
    create_schema_ledger_objects,
    ensure_schema_current,
    file_is_fresh,
    open_or_create_schema,
    user_tables,
)
from tos_runtime.operations.schema_migrations import (
    EVIDENCE_MIGRATIONS,
    MARKETFEED_MIGRATIONS,
    RCL_MIGRATIONS,
    STORE_MIGRATIONS,
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


# -- T-2: moving the four stores onto the helper changed no store's shape ----------------------
#
# The #801 fix relocated four constructors' DDL into a transaction. That is a refactor of WHEN the
# statements run, and it must be nothing else: a fresh file must come out byte-identical, or every
# `migration_digest` already written into a deployed `schema_ledger` (and every backup taken from
# one) silently disagrees with what this code now produces.
#
# The values below were MEASURED on the pre-change tree (main `7d039339`, before
# `open_or_create_schema` existed) and pasted here — they are a golden record of the old code's
# output, not a restatement of the new code's. `_sql_digest` folds every object's own `sql` text,
# so a reordered, reworded or dropped statement moves it; the object list is pinned separately so
# a failure says WHICH object went missing rather than only "the digest moved".

_PRE_CHANGE_SHAPES: dict[str, tuple[tuple[tuple[str, str], ...], str, int, str]] = {
    "evidence": (
        (
            ("index", "entries_kind_seq"),
            ("table", "entries"),
            ("table", "outbox"),
            ("table", "schema_ledger"),
            ("trigger", "entries_no_delete"),
            ("trigger", "entries_no_update"),
            ("trigger", "schema_ledger_no_delete"),
            ("trigger", "schema_ledger_no_update"),
        ),
        "0fc7818cc7bce14be74a654946737ae9658a45b8d89e3c23064f1095d5de473d",
        2,
        "c9be86187b9602e8f2d720561b12aedf8f9b451fe540c9eb347282a55a0ce7b5",
    ),
    "inbox": (
        (
            ("index", "events_unconsumed"),
            ("table", "attempt_composites"),
            ("table", "attempt_finality_witness"),
            ("table", "events"),
            ("table", "new_risk_halt"),
            ("table", "schema_ledger"),
            ("trigger", "schema_ledger_no_delete"),
            ("trigger", "schema_ledger_no_update"),
        ),
        "b320cdc8dfb7d40183cf13b078259a62cf0bec7237863ffc29be66174305edb3",
        1,
        "f899aa98b0c37790f7eb094780445b7598d054c2a41d9945e391f8c89c4a8966",
    ),
    "marketfeed": (
        (
            ("index", "snapshots_instrument_as_of"),
            ("table", "preimages"),
            ("table", "schema_ledger"),
            ("table", "snapshots"),
            ("trigger", "schema_ledger_no_delete"),
            ("trigger", "schema_ledger_no_update"),
        ),
        "f00ed029ef22073f23f47a520c37861a19e1ed6e9166fa468e90012966d71599",
        1,
        "7c1633c8c0ef090fea2809c6dec2cfea61d405316721f0a8edba6f64a682db50",
    ),
    "rcl": (
        (
            ("table", "entries"),
            ("table", "epochs"),
            ("table", "reservations"),
            ("table", "schema_ledger"),
            ("trigger", "entries_no_delete"),
            ("trigger", "entries_no_update"),
            ("trigger", "epochs_no_delete"),
            ("trigger", "epochs_no_update"),
            ("trigger", "reservations_no_delete"),
            ("trigger", "schema_ledger_no_delete"),
            ("trigger", "schema_ledger_no_update"),
        ),
        "01220d07930ab0f332ace276f911f21f919fcf7f593973e013fe73c7c01028c5",
        2,
        "79967105de085c556ba837b3ed9969b21475489f0c6fbbbf9e20e8f2d46be2b2",
    ),
}


def _sqlite_objects(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    return sorted(
        (str(row[0]), str(row[1]), str(row[2] or ""))
        for row in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    )


def _build_fresh_store(store: str, tmp_path: Path) -> Path:
    """Create ``store``'s file through its REAL constructor and return the path."""
    path = tmp_path / f"{store}.sqlite3"
    if store == "evidence":
        SqliteEvidenceStore(path, key_provider=FixedKeyProvider()).close()
    elif store == "inbox":
        SqliteEventInbox(path, scheme=_SCHEME).close()
    elif store == "marketfeed":
        SqliteSnapshotStore(path).close()
    elif store == "rcl":
        evidence = SqliteEvidenceStore(
            tmp_path / "rcl-evidence.sqlite3", key_provider=FixedKeyProvider()
        )
        SqliteCommitLog(path, evidence_port=evidence).close()
        evidence.close()
    else:  # pragma: no cover - guards a typo in the parametrisation
        raise AssertionError(store)
    return path


@pytest.mark.parametrize(
    "store", sorted(_PRE_CHANGE_SHAPES), ids=sorted(_PRE_CHANGE_SHAPES)
)
def test_a_fresh_store_has_the_same_shape_as_before_the_atomic_genesis_change(
    store: str, tmp_path: Path
) -> None:
    expected_objects, expected_sql_digest, expected_version, expected_digest = (
        _PRE_CHANGE_SHAPES[store]
    )
    path = _build_fresh_store(store, tmp_path)

    conn = sqlite3.connect(str(path))
    try:
        objects = _sqlite_objects(conn)
        ledger = conn.execute(
            "SELECT version, migration_digest, applied_by FROM schema_ledger"
        ).fetchall()
        stamped = conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()

    assert tuple((kind, name) for kind, name, _ in objects) == expected_objects
    folded = hashlib.sha256(
        "\n".join(sql for _, _, sql in objects).encode("utf-8")
    ).hexdigest()
    assert folded == expected_sql_digest, (
        f"the {store} store's on-disk DDL text changed — a fresh file is no longer what the "
        "pre-#801 code produced"
    )
    # `applied_at_monotonic_ns` is deliberately excluded: it is a clock reading, so it is the one
    # column that legitimately differs between two runs of identical code.
    assert ledger == [(expected_version, expected_digest, "CREATED")]
    assert stamped == expected_version


# -- open_or_create_schema: the atomic-genesis helper (#801 plan T-1) --------------------------
#
# The four real stores go through this helper, and their own wiring is covered above and in
# `test_schema_genesis_concurrency.py`. These tests drive it directly, over a synthetic store, so
# each disposition (fresh / same / behind / ahead / DDL raises) is pinned without needing a real
# store that happens to sit at that version.

_WIDGET_DDL = "CREATE TABLE IF NOT EXISTS widgets (id INTEGER PRIMARY KEY, label TEXT)"


def _widget_ddl(conn: sqlite3.Connection, fresh: bool) -> None:
    """A synthetic store's DDL. ``fresh`` is threaded through to a genesis-only index, the same
    shape the evidence store's own ``entries_kind_seq`` uses."""
    conn.execute(_WIDGET_DDL)
    if fresh:
        conn.execute("CREATE INDEX IF NOT EXISTS widgets_label ON widgets (label)")


def _open_widgets(
    conn: sqlite3.Connection,
    *,
    schema_version: int = 3,
    create_ddl: Callable[[sqlite3.Connection, bool], None] = _widget_ddl,
) -> bool:
    return open_or_create_schema(
        conn,
        store_name="widgets-store",
        schema_version=schema_version,
        create_ddl=create_ddl,
        shape_tables=("widgets",),
        monotonic_ns=lambda: 4242,
    )


def _connect(path: Path) -> sqlite3.Connection:
    """A connection shaped like every real store's own: autocommit + WAL."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def test_open_or_create_schema_stamps_a_fresh_file_once(tmp_path: Path) -> None:
    conn = _connect(tmp_path / "widgets.sqlite3")
    try:
        assert _open_widgets(conn) is True
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        rows = conn.execute(
            "SELECT version, applied_at_monotonic_ns, migration_digest, applied_by "
            "FROM schema_ledger"
        ).fetchall()
        assert len(rows) == 1
        version, applied_at, digest, applied_by = rows[0]
        assert (version, applied_at, applied_by) == (3, 4242, "CREATED")
        # The digest really is this file's own shape, computed after the DDL ran — not a value
        # the caller could have passed in stale.
        assert digest == compute_schema_shape_digest(conn, ("widgets",))
        # `fresh` reached the DDL callable: the genesis-only index exists.
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = ?",
                ("widgets_label",),
            ).fetchone()[0]
            == 1
        )
    finally:
        conn.close()


def test_open_or_create_schema_passes_silently_at_the_same_version(
    tmp_path: Path,
) -> None:
    path = tmp_path / "widgets.sqlite3"
    first = _connect(path)
    try:
        _open_widgets(first)
    finally:
        first.close()

    second = _connect(path)
    try:
        assert _open_widgets(second) is False
        # Reopening never re-stamps, and never rebuilds the genesis-only index either.
        assert second.execute("SELECT COUNT(*) FROM schema_ledger").fetchone()[0] == 1
    finally:
        second.close()


@pytest.mark.parametrize(
    ("stamped", "expected"), ((2, "BEHIND"), (9, "AHEAD")), ids=("behind", "ahead")
)
def test_open_or_create_schema_refuses_a_disagreeing_version(
    tmp_path: Path, stamped: int, expected: str
) -> None:
    path = tmp_path / "widgets.sqlite3"
    first = _connect(path)
    try:
        _open_widgets(first)
        first.execute(f"PRAGMA user_version = {stamped}")
    finally:
        first.close()

    second = _connect(path)
    try:
        with pytest.raises(SchemaVersionRefused, match=expected):
            _open_widgets(second)
    finally:
        second.close()


def test_open_or_create_schema_rolls_a_failed_genesis_all_the_way_back(
    tmp_path: Path,
) -> None:
    """A DDL that raises mid-genesis must leave ZERO user tables (plan §4 T-1).

    This is the mutation "remove the ``ROLLBACK``": without it, sqlite's implicit rollback on
    close would still cover this synthetic case, but the caller's connection stays OPEN and in a
    failed transaction — the next statement on it (a retry, a second store's construction on the
    same connection, or the diagnostic read below) sees a file with half the schema in it. With
    the pre-#801 autocommit DDL it was not even a transaction: the ``widgets`` table simply
    stayed on disk, and the NEXT boot then read ``file_is_fresh = False`` on a file no genesis
    had ever stamped, i.e. exactly the false "BEHIND" refusal R-2 names.
    """
    path = tmp_path / "widgets.sqlite3"
    conn = _connect(path)

    def exploding_ddl(inner: sqlite3.Connection, fresh: bool) -> None:
        inner.execute(_WIDGET_DDL)
        del fresh
        raise RuntimeError("DDL blew up half way through")

    try:
        with pytest.raises(RuntimeError, match="blew up"):
            _open_widgets(conn, create_ddl=exploding_ddl)
        # Same live connection: the transaction is gone, not merely unfinished.
        assert user_tables(conn) == frozenset()
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        # And a retry on that same connection now performs an ordinary, clean genesis.
        assert _open_widgets(conn) is True
        assert conn.execute("SELECT COUNT(*) FROM schema_ledger").fetchone()[0] == 1
    finally:
        conn.close()


def test_open_or_create_schema_leaves_no_tables_after_a_failed_genesis_on_disk(
    tmp_path: Path,
) -> None:
    """The same claim, read back through a SEPARATE connection — the durable half."""
    path = tmp_path / "widgets.sqlite3"
    conn = _connect(path)

    def exploding_ddl(inner: sqlite3.Connection, fresh: bool) -> None:
        del fresh
        inner.execute(_WIDGET_DDL)
        raise RuntimeError("DDL blew up half way through")

    try:
        with pytest.raises(RuntimeError):
            _open_widgets(conn, create_ddl=exploding_ddl)
    finally:
        conn.close()

    reader = sqlite3.connect(str(path))
    try:
        assert user_tables(reader) == frozenset()
    finally:
        reader.close()


# -- review MEDIUM-1: a steady-state boot must not need the write lock -------------------------
#
# Before #801 a boot against an existing, current file took no write lock at all. Folding the DDL
# into `BEGIN IMMEDIATE` made every boot contend with whatever holds that lock — a live runtime
# appending evidence, an operator CLI (`rearm`/`ack-alert`/`rotate-key`), or a long
# `apply_migrations` index build. The lock-free fast path restores the old property; these tests
# pin both halves of it (it really is lock-free, and it really cannot wave a stale file through).


def test_an_already_current_file_boots_while_another_writer_holds_the_lock(
    tmp_path: Path,
) -> None:
    """RED before the fast path: this is the regression #801 introduced and MEDIUM-1 names.

    A second connection holds ``BEGIN IMMEDIATE`` for the whole boot, and the booting connection
    is given ``timeout=0`` so it cannot wait at all — the same shape as a runtime booting beside a
    live writer with ``SqliteCommitLog(sqlite_timeout_s=0)``. With the DDL inside an unconditional
    ``BEGIN IMMEDIATE`` this raises ``sqlite3.OperationalError: database is locked``.
    """
    path = tmp_path / "widgets.sqlite3"
    first = _connect(path)
    try:
        assert _open_widgets(first) is True
    finally:
        first.close()

    holder = _connect(path)
    booting = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN IMMEDIATE")

        assert _open_widgets(booting) is False

        # And it really was lock-free: the holder's transaction is still open and intact.
        assert holder.execute("PRAGMA user_version").fetchone()[0] == 3
        holder.execute("ROLLBACK")
    finally:
        booting.close()
        holder.close()


def test_the_fast_path_still_refuses_a_behind_or_ahead_version_under_a_held_lock(
    tmp_path: Path,
) -> None:
    """The fast path must not become a way to skip the version check.

    A disagreeing version is NOT the fast path, so it falls through to ``BEGIN IMMEDIATE`` — and
    with the lock held and ``timeout=0`` that surfaces as ``OperationalError``, i.e. still
    fail-closed. What must never happen is a silent pass.
    """
    path = tmp_path / "widgets.sqlite3"
    first = _connect(path)
    try:
        _open_widgets(first)
        first.execute("PRAGMA user_version = 2")
    finally:
        first.close()

    holder = _connect(path)
    booting = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            _open_widgets(booting)
        holder.execute("ROLLBACK")
    finally:
        booting.close()
        holder.close()

    # With the lock free, the very same file is refused on the version, as it always was.
    reopened = _connect(path)
    try:
        with pytest.raises(SchemaVersionRefused, match="BEHIND"):
            _open_widgets(reopened)
    finally:
        reopened.close()


def test_a_matching_version_without_a_schema_ledger_does_not_take_the_fast_path(
    tmp_path: Path,
) -> None:
    """The second half of the fast-path predicate, pinned.

    A file whose ``user_version`` matches but that carries no ``schema_ledger`` (a pre-ledger
    file, or one an operator demoted by dropping the table) must reach the transaction so the
    ledger DDL runs. A fast path keyed on the version alone would wave it through with no ledger.
    """
    path = tmp_path / "widgets.sqlite3"
    conn = _connect(path)
    try:
        _open_widgets(conn)
        conn.execute("DROP TRIGGER schema_ledger_no_update")
        conn.execute("DROP TRIGGER schema_ledger_no_delete")
        conn.execute("DROP TABLE schema_ledger")
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
    finally:
        conn.close()

    reopened = _connect(path)
    try:
        # Not fresh (widgets exists) and the version already matches, so this is the ordinary
        # "already current" outcome — but the ledger table is back, which only the transaction
        # could have done.
        assert _open_widgets(reopened) is False
        assert "schema_ledger" in user_tables(reopened)
        # No genesis row was invented for a file whose genesis it did not perform.
        assert reopened.execute("SELECT COUNT(*) FROM schema_ledger").fetchone()[0] == 0
    finally:
        reopened.close()


def test_a_v1_evidence_file_is_still_refused_and_never_fast_pathed(
    tmp_path: Path,
) -> None:
    """The real store, not the synthetic one: #816's v1 -> v2 refusal must survive the fast path.

    ``user_version`` 1 != ``EVIDENCE_SCHEMA_VERSION`` 2, so a v1 file cannot match the fast-path
    predicate and is refused exactly as before — and, as #816 requires, without the
    ``entries_kind_seq`` index having been built by the refused boot.
    """
    path = tmp_path / "evidence.sqlite3"
    _build_v1_evidence_file(tmp_path, path)

    with pytest.raises(SchemaVersionRefused, match="BEHIND"):
        SqliteEvidenceStore(path, key_provider=FixedKeyProvider())

    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert _INDEX_NAME not in _index_names(conn)
    finally:
        conn.close()


def test_a_real_store_boots_beside_a_held_write_lock(tmp_path: Path) -> None:
    """MEDIUM-1 through a REAL store, with the timeout the fault-③ suite already injects.

    ``SqliteCommitLog`` is the one store that takes ``sqlite_timeout_s``, so it is the one that
    can express "cannot wait at all" without a new config key. RED before the fast path.
    """
    evidence = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    path = tmp_path / "rcl.sqlite3"
    first = SqliteCommitLog(path, evidence_port=evidence)
    first.close()

    holder = sqlite3.connect(str(path), isolation_level=None)
    try:
        holder.execute("BEGIN IMMEDIATE")
        reopened = SqliteCommitLog(path, evidence_port=evidence, sqlite_timeout_s=0)
        reopened.close()
        holder.execute("ROLLBACK")
    finally:
        holder.close()
        evidence.close()


# -- review LOW-1/LOW-2: the helper's own contract ---------------------------------------------


def test_a_create_ddl_that_ends_the_transaction_surfaces_its_own_exception(
    tmp_path: Path,
) -> None:
    """LOW-1: the cleanup must never replace the diagnosis.

    A ``create_ddl`` that commits (or rolls back) before failing leaves no transaction for the
    handler's ``ROLLBACK``, and sqlite answers "cannot rollback - no transaction is active". If
    that escapes, the real failure is gone. RED before the wrapped ``ROLLBACK``.
    """
    path = tmp_path / "widgets.sqlite3"
    conn = _connect(path)

    def commits_then_raises(inner: sqlite3.Connection, fresh: bool) -> None:
        del fresh
        inner.execute(_WIDGET_DDL)
        inner.execute(
            "COMMIT"
        )  # ends the genesis transaction out from under the helper
        raise RuntimeError("the real failure, which must not be masked")

    try:
        with pytest.raises(RuntimeError, match="the real failure"):
            _open_widgets(conn, create_ddl=commits_then_raises)
    finally:
        conn.close()


def test_a_connection_not_in_autocommit_mode_is_refused_with_a_clear_error(
    tmp_path: Path,
) -> None:
    """LOW-2: a ``ValueError``, not an ``assert`` (``-O`` strips asserts) and not a mid-genesis
    sqlite error.

    With sqlite3's implicit transactions the explicit ``BEGIN IMMEDIATE`` raises "cannot start a
    transaction within a transaction" — after the caller believed it had a working store — so the
    precondition is checked before anything is touched.
    """
    path = tmp_path / "widgets.sqlite3"
    conn = sqlite3.connect(str(path))  # sqlite3's default: isolation_level == ""
    try:
        assert conn.isolation_level is not None
        with pytest.raises(ValueError, match="autocommit"):
            _open_widgets(conn)
        # Nothing was created before the refusal.
        assert user_tables(conn) == frozenset()
    finally:
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
        # The ledger's TRIGGERS too, not only its table: real v1 code created both (through
        # `ensure_schema_current`), so a fixture that skips them models an operator-demoted
        # file rather than the v1 deployment this helper claims to reproduce — and would hide
        # the trigger repair under a fixture artefact.
        create_schema_ledger_objects(conn)
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


# -- the genesis path and the migrate path must converge on ONE schema -------------------------
#
# `apply_migrations` has to be able to CREATE a `schema_ledger` (a pre-ledger file has none),
# and it used to create the TABLE alone — without the two append-only triggers the genesis path
# creates beside it. Nothing afterwards noticed: `compute_schema_shape_digest` reads
# `PRAGMA table_info`, which is blind to triggers, and `open_or_create_schema`'s steady-state
# fast path returns on "version matches AND the ledger table exists", so no later boot ran DDL
# that could repair them. Every pre-ledger data dir an operator brought up with `migrate` — the
# documented upgrade path — therefore kept a PERMANENTLY rewritable ledger.
#
# These three pin the property the plan's A2 claim rests on: a migrated file and a genesis file
# of the same version are the same schema, and the ledger is append-only on BOTH.


def _normalized_sqlite_objects(path: Path) -> list[tuple[str, str, str, str]]:
    """Every schema object as ``(type, name, tbl_name, sql)``, SQL whitespace collapsed.

    Whitespace is collapsed in the SQL ONLY: the same ``CREATE INDEX`` reaches sqlite indented
    differently from the store's own constant than from the migration's, so comparing raw text
    would fail on indentation rather than on the schema this test is about.

    ``type``, ``name`` and ``tbl_name`` are compared EXACTLY, which is what keeps that
    normalization honest (Codex review LOW): collapsing runs of whitespace could in principle
    conflate two different SQL texts (``DEFAULT 'a  b'`` versus ``DEFAULT 'a b'``), so the
    structural facts that actually decide whether the ledger is protected — does this trigger
    exist, and is it attached to ``schema_ledger`` — never pass through the normalizer.
    """
    conn = sqlite3.connect(str(path))
    try:
        return sorted(
            (str(row[0]), str(row[1]), str(row[2]), " ".join((row[3] or "").split()))
            for row in conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%'"
            )
        )
    finally:
        conn.close()


def _build_pre_ledger_evidence_file(path: Path) -> None:
    """A real pre-W4 file: genuine rows and chain, no ``schema_ledger`` at all, version 0.

    ``DROP TABLE`` takes that table's triggers with it, which is precisely the state a data dir
    predating the ledger is in — and the state ``migrate`` has to be able to finish correctly.
    """
    _seed_evidence(path)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(f"DROP INDEX IF EXISTS {_INDEX_NAME}")
        conn.execute("DROP TABLE schema_ledger")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()


def test_a_migrated_file_converges_on_the_genesis_schema(tmp_path: Path) -> None:
    """A file ``migrate`` brought to v2 and a file genesis created at v2 are the SAME schema.

    This is the assertion the evidence growth plan's A2 safety argument needs and did not have:
    "both paths converge" was argued in prose while the migrated file was missing two triggers.
    """
    genesis = tmp_path / "genesis.sqlite3"
    _seed_evidence(genesis)

    migrated = tmp_path / "migrated.sqlite3"
    _build_pre_ledger_evidence_file(migrated)
    apply_migrations(migrated, "evidence")

    assert (
        schema_version(migrated) == schema_version(genesis) == EVIDENCE_SCHEMA_VERSION
    )
    assert _normalized_sqlite_objects(migrated) == _normalized_sqlite_objects(genesis)


def test_a_migrated_schema_ledger_rejects_update_and_delete(tmp_path: Path) -> None:
    """The append-only guarantee, asserted on the MIGRATED file too.

    ``test_schema_ledger_table_rejects_update_and_delete`` above pins this for a genesis file
    only. Without this one, the ledger was append-only exactly where it was already tested and
    silently mutable everywhere ``migrate`` had created it.
    """
    path = tmp_path / "evidence.sqlite3"
    _build_pre_ledger_evidence_file(path)
    apply_migrations(path, "evidence")

    conn = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE schema_ledger SET applied_by = 'TAMPERED'")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM schema_ledger")
    finally:
        conn.close()


def test_migrate_rebuilds_dropped_schema_ledger_triggers_and_says_so(
    tmp_path: Path,
) -> None:
    """A ledger whose triggers were dropped is repaired, and the repair is REPORTED.

    Reported, not silent: this is the same discipline the dropped-index repair follows, and for
    the same reason — an operator who is not told cannot know the file was running unprotected.
    The version is already current here, so nothing is applied and nothing is re-ledgered.
    """
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)
    conn = sqlite3.connect(str(path))
    try:
        for name in SCHEMA_LEDGER_TRIGGER_NAMES:
            conn.execute(f"DROP TRIGGER {name}")
        conn.commit()
        # The damage really is invisible to the boot check — the reason a repair is needed.
        assert (
            conn.execute("PRAGMA user_version").fetchone()[0] == EVIDENCE_SCHEMA_VERSION
        )
    finally:
        conn.close()
    SqliteEvidenceStore(path, key_provider=FixedKeyProvider()).close()

    outcome = apply_migrations(path, "evidence")

    assert outcome.applied == ()
    assert outcome.ledgered == ()
    assert sorted(outcome.repaired) == sorted(SCHEMA_LEDGER_TRIGGER_NAMES)
    assert outcome.changed is True
    conn = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM schema_ledger")
        # A repair invents no ledger row — it is not a migration.
        assert conn.execute("SELECT COUNT(*) FROM schema_ledger").fetchone()[0] == 1
    finally:
        conn.close()


# -- Claude-lane review (2026-10-02): creating a ledger is not repairing one ------------------


def test_creating_a_ledger_is_not_reported_as_a_repair(tmp_path: Path) -> None:
    """A file that had NO ``schema_ledger`` reports ``repaired == ()``.

    Claude-lane review MEDIUM-1. ``repaired`` is the operator's one signal that a ledger was
    running unprotected, and plan §7.1.17 points at it by name. Deciding freshness AFTER the
    ``CREATE TABLE`` made that signal fire on every first ``migrate`` of every store — the CLI
    printed ``rebuilt schema_ledger_no_update, schema_ledger_no_delete`` over a file it had
    just created. A warning that also fires on healthy genesis is worth nothing.
    """
    # (a) a truly empty file — the fresh-deploy path
    empty = tmp_path / "evidence.sqlite3"
    empty.touch()
    assert apply_migrations(empty, "evidence").repaired == ()

    # (b) a real pre-ledger file with rows in it — the documented upgrade path
    pre = tmp_path / "pre.sqlite3"
    _build_pre_ledger_evidence_file(pre)
    outcome = apply_migrations(pre, "evidence")
    assert outcome.applied == (1, 2)
    assert outcome.repaired == ()

    # Both are nonetheless protected — "not reported" must not become "not created".
    for path in (empty, pre):
        conn = sqlite3.connect(str(path))
        try:
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                conn.execute("DELETE FROM schema_ledger")
        finally:
            conn.close()


def _table_columns(path: Path) -> dict[str, list[tuple[str, str]]]:
    """``{table: [(column, declared type), ...]}`` in declaration order."""
    conn = sqlite3.connect(str(path))
    try:
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: [
                (str(row[1]), str(row[2]))
                for row in conn.execute(f"PRAGMA table_info({table})")
            ]
            for table in tables
        }
    finally:
        conn.close()


def _non_table_objects(path: Path) -> list[tuple[str, str, str, str]]:
    return [row for row in _normalized_sqlite_objects(path) if row[0] != "table"]


@pytest.mark.parametrize("store", ["evidence", "inbox", "marketfeed", "rcl"])
def test_every_store_converges_from_a_truly_empty_file(
    store: str, tmp_path: Path
) -> None:
    """Genesis and ``migrate``-from-empty agree, for ALL FOUR stores.

    Two gaps this closes (adversarial review (a), Claude-lane LOW-3). First,
    :func:`_build_pre_ledger_evidence_file` keeps the store's own ``entries``/``outbox``, so
    both sides of :func:`test_a_migrated_file_converges_on_the_genesis_schema` take their
    TABLE sql from genesis — drift between ``_EVIDENCE_BASELINE_STATEMENTS`` and the store's
    own ``CREATE TABLE`` literals is invisible to it. Starting from an EMPTY file makes
    ``apply_migrations`` produce every object itself, so the baseline statements really are
    compared against the store's. Second, nothing pinned convergence for the other three
    stores at all.

    ``rcl`` is compared by ``PRAGMA table_info`` instead of ``sqlite_master.sql``: its v2 is an
    ``ALTER TABLE ... ADD COLUMN``, and sqlite stores the post-ALTER text with different
    internal spacing than the genesis ``CREATE TABLE`` while columns, declared types and order
    stay identical. Pinning the text there would pin a sqlite artefact, not the schema.
    """
    genesis_dir = tmp_path / "genesis"
    genesis_dir.mkdir()
    genesis = _build_fresh_store(store, genesis_dir)

    migrated_dir = tmp_path / "migrated"
    migrated_dir.mkdir()
    migrated = migrated_dir / f"{store}.sqlite3"
    migrated.touch()

    apply_migrations(migrated, store)

    assert schema_version(migrated) == schema_version(genesis)
    assert _table_columns(migrated) == _table_columns(genesis)
    if store == "rcl":
        # Index/trigger objects must still match exactly; only the table text differs.
        assert _non_table_objects(migrated) == _non_table_objects(genesis)
    else:
        assert _normalized_sqlite_objects(migrated) == _normalized_sqlite_objects(
            genesis
        )


# -- Codex review (2026-10-02): three ways the fix above still admitted what it names ---------


def test_migrate_refuses_an_ahead_file_without_writing_to_it(tmp_path: Path) -> None:
    """A file from a FUTURE release comes back BYTE-IDENTICAL from a refused ``migrate``.

    Codex review MEDIUM-1. The ledger DDL used to run before the AHEAD check, so an older tool
    told the operator it refused to touch the file and then left new objects in it. "Refused"
    has to mean nothing was written, or the word is doing no work.
    """
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)
    conn = sqlite3.connect(str(path))
    try:
        for name in SCHEMA_LEDGER_TRIGGER_NAMES:
            conn.execute(f"DROP TRIGGER {name}")
        conn.execute("PRAGMA user_version = 999")
        conn.commit()
    finally:
        conn.close()
    before_bytes = path.read_bytes()
    before_objects = _normalized_sqlite_objects(path)

    with pytest.raises(SchemaMigrationRefused, match="AHEAD"):
        apply_migrations(path, "evidence")

    assert path.read_bytes() == before_bytes
    assert _normalized_sqlite_objects(path) == before_objects


def test_a_reserved_trigger_name_owned_by_another_table_is_refused(
    tmp_path: Path,
) -> None:
    """Sqlite trigger names are per-DATABASE, so presence is not protection.

    Codex review MEDIUM-3. With ``schema_ledger_no_update`` already attached to some other
    table, ``CREATE TRIGGER IF NOT EXISTS`` is a no-op and the helper would have returned ``()``
    — "nothing needed repair" — over a ledger that is still freely writable. Exactly the defect
    class this helper exists to close, so it fails closed instead.
    """
    path = tmp_path / "evidence.sqlite3"
    _seed_evidence(path)
    conn = sqlite3.connect(str(path))
    try:
        for name in SCHEMA_LEDGER_TRIGGER_NAMES:
            conn.execute(f"DROP TRIGGER {name}")
        conn.execute("CREATE TABLE decoy (x INTEGER)")
        conn.execute(
            "CREATE TRIGGER schema_ledger_no_update BEFORE UPDATE ON decoy "
            "BEGIN SELECT RAISE(ABORT, 'not the ledger'); END"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SchemaLedgerUnprotected, match="schema_ledger_no_update"):
        create_schema_ledger_objects(sqlite3.connect(str(path)))


def test_the_ledger_objects_land_atomically(tmp_path: Path) -> None:
    """Table and both triggers commit together, or not at all.

    Codex review MEDIUM-2. The three statements used to autocommit one at a time outside the
    genesis transaction, so a failure between them left a table with one or neither trigger —
    the unprotected state — which the boot fast path then waves through. The SAVEPOINT makes
    the partial state unreachable: here the second trigger's creation is made to fail, and the
    whole thing must roll back rather than leave a bare table behind.
    """
    path = tmp_path / "fresh.sqlite3"

    class _FailsOnSecondTrigger(sqlite3.Connection):
        """Real connection; the second ``CREATE TRIGGER`` raises as a disk error would.

        A subclass via ``factory`` rather than monkeypatching, because
        ``sqlite3.Connection.execute`` is read-only — and because the rollback under test is
        sqlite's own, so it must be a genuine connection doing genuine work.
        """

        def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
            if sql.lstrip().upper().startswith("CREATE") and (
                "schema_ledger_no_delete" in sql
            ):
                raise sqlite3.OperationalError("disk I/O error (injected)")
            return super().execute(sql, parameters)

    conn = sqlite3.connect(str(path), factory=_FailsOnSecondTrigger)
    try:
        with pytest.raises(sqlite3.OperationalError, match="injected"):
            create_schema_ledger_objects(conn)
    finally:
        conn.close()

    # Nothing survived: no half-built, unprotected ledger for the fast path to wave through.
    verify = sqlite3.connect(str(path))
    try:
        assert "schema_ledger" not in user_tables(verify)
    finally:
        verify.close()


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


# -- SchemaVersionRefused carries its direction across a process boundary -----


@pytest.mark.parametrize("direction", get_args(SchemaVersionDirection))
def test_a_version_refusal_survives_pickle_and_copy(
    direction: SchemaVersionDirection,
) -> None:
    """The refusal rebuilds with BOTH halves intact — message and ``direction``.

    ``direction`` is a REQUIRED keyword-only argument, and ``BaseException.__reduce__``
    rebuilds as ``cls(*self.args)`` with ``args`` holding only the message. Without the
    ``__reduce__`` override this raises ``TypeError: missing 1 required keyword-only
    argument: 'direction'`` on all three of ``pickle``, ``copy`` and ``deepcopy``
    (measured). That is the shape that bites when an exception crosses a process boundary,
    which this package already does elsewhere
    (``test_schema_genesis_concurrency`` runs N processes against one file; it happens to
    stringify before queueing, so nothing is broken today — this keeps it that way by
    construction rather than by luck).

    The round trip must preserve ``direction``, not merely succeed: the cold-backup
    dispatch chooses ``migrate refused`` vs ``schema refused`` from that attribute, so an
    exception that survives serialization with the attribute dropped would route a verdict
    to the wrong runbook row — worse than failing to serialize at all.

    The cases are derived from :data:`SchemaVersionDirection` itself rather than copied,
    so a third direction added to that Literal is covered here without anyone remembering
    to extend a list — the hand-synced-table shape this PR exists to close.
    """
    original = SchemaVersionRefused(
        f"evidence: {direction} something", direction=direction
    )

    for rebuilt in (
        pickle.loads(pickle.dumps(original)),
        copy.copy(original),
        copy.deepcopy(original),
    ):
        assert type(rebuilt) is SchemaVersionRefused
        assert str(rebuilt) == str(original)
        assert rebuilt.direction == direction


def test_no_store_has_a_migration_newer_than_its_own_schema_version() -> None:
    """``newest migration version <= SCHEMA_VERSION``, per store.

    This is what makes the runbook's ``schema refused`` row true. That row tells the
    operator that ``migrate`` is NOT the fix for an AHEAD store, and ``apply_migrations``
    delivers that by refusing when ``current_version > migrations[-1].version``. If some
    store ever shipped a migration NEWER than the constant its own boot check compares
    against, a file at ``SCHEMA_VERSION + 1`` would be AHEAD for the boot check and yet
    within range for ``apply_migrations`` — the advice would be wrong for that store, and
    nothing else would notice.
    """
    expected = {
        "evidence": EVIDENCE_SCHEMA_VERSION,
        "rcl": RCL_SCHEMA_VERSION,
        "inbox": INBOX_SCHEMA_VERSION,
        "marketfeed": MARKETFEED_SCHEMA_VERSION,
    }

    assert set(expected) == set(
        STORE_MIGRATIONS
    ), "a store joined without a version here"
    for store_name, migrations in STORE_MIGRATIONS.items():
        newest = migrations[-1].version
        assert newest <= expected[store_name], (
            f"{store_name}: newest migration v{newest} is ahead of SCHEMA_VERSION "
            f"{expected[store_name]} — the `schema refused` runbook row would be wrong"
        )
