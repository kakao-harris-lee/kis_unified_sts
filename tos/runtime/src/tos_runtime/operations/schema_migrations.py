"""Per-store baseline ``SchemaMigration`` definitions + the operator-facing ``apply_migrations``
(TOS Phase 5 W4 plan §2 decision 3; ``marketfeed`` entry added by the tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 3).

**Baseline v1, per store.** Each runtime-owned durable store (evidence, RCL, inbox, marketfeed)
gets exactly one registered migration: version 1, "baseline — current DDL as of the store's own
introduction". A future wave that actually changes a table's shape adds a SECOND
``SchemaMigration`` per affected store; this module does not invent placeholder future versions.

**First v2 (kernel round #4 K-4).** ``RCL_MIGRATIONS`` now carries a genuine second entry —
``reservations`` gains ``committed_vector_json`` — the first store in this module to move past
baseline. It is the worked example for the pattern above: a NEW ``SchemaMigration`` appended,
never an edit to the v1 entry's own statements/expected shape.
``EVIDENCE_MIGRATIONS`` follows it (evidence growth plan §2 A2).

**Rollback, per migration.** A migration's rollback is stated where the migration is, because
it is not uniform. ``RCL`` v2 added a nullable column: sqlite has no ``DROP COLUMN`` on that
shape, so rolling it back means restoring the durable set from a backup taken before the
migration (``operations.backup_set``) — the reason that migration is one-way in practice.

``EVIDENCE`` v2 is the easy case: it adds only an INDEX, an auxiliary structure that stores no
row content, so rolling it back leaves every row's bytes, ``entry_digest`` and ``chain_digest``
exactly as they were, and ``SqliteEvidenceStore.verify()`` unchanged either way. No backup
restore is needed. There is exactly ONE supported procedure, and both halves are required::

    DROP INDEX IF EXISTS entries_kind_seq;
    PRAGMA user_version = 1;

Dropping the index while LEAVING ``user_version`` at 2 is not a rollback: v2 code boots happily
and silently runs every by-kind read as a full scan again, and nothing detects it —
``compute_schema_shape_digest`` reads ``PRAGMA table_info``, which does not see indexes at all.
Rolling forward again is always ``apply_migrations`` (the ``migrate`` CLI), never a hand-written
``CREATE INDEX``; it re-applies the step from either half-state and, at an already-current
version, rebuilds a dropped index through the repair pass
(:attr:`SchemaMigration.repair_statements`).

**A re-applied step is not re-recorded.** ``schema_ledger.version`` is a PRIMARY KEY on an
append-only table, so the v2 row survives the rollback above and a second ``migrate`` cannot
insert it again. :func:`apply_migrations` therefore skips the INSERT when the row already
exists, while still running the DDL and stamping ``user_version``. The ledger is a record of
"this version was first applied here", not a count of how many times it ran. Before this
(review HIGH-1), the duplicate INSERT raised ``IntegrityError``, rolled the whole transaction
back, and left the file stuck at v1 with no index — unbootable by v2 code and unreachable by
``migrate``.

**Rollout order (round #4 review LOW — first genuine v1->v2 bump, so this module carried no
prior worked example of the deploy-time ordering it requires).**
:func:`~tos_runtime.operations.schema_ledger.open_or_create_schema` refuses BOTH directions on
open (that module's docstring points 3/4: behind OR ahead of the running code's expected version), so
a `RCL_SCHEMA_VERSION` bump is not safe to roll out in an arbitrary order against a running store.
The required sequence: (1) fully stop every process still running the OLD (v1-expecting) code
against this store file — a still-live v1 process would itself get refused the instant
``apply_migrations`` stamps the file at v2 out from under it; (2) run
``apply_migrations(path, "rcl")`` to bring the file to v2; (3) start the NEW (v2-expecting) code.
Running ``apply_migrations`` first, while a v1 process is still up, does not corrupt anything —
the v1 process simply gets ``SchemaVersionRefused`` on its next open/reopen — but it does turn a
planned migration into an unplanned outage of that still-live process.

**Deliberately self-contained (duplicated DDL, not imported).** The literal ``CREATE
TABLE``/trigger strings below mirror — and must be kept in sync with — each store's own DDL
(:mod:`tos_runtime.evidence.store`, :mod:`tos_runtime.rcl.schema`, :mod:`tos_runtime.engine.inbox`,
:mod:`tos_runtime.marketfeed.store`, including the inbox's own ``_ADDED_COLUMNS`` idiom, folded
into ``events`` directly here since baseline v1 IS "the current DDL, added columns included" per
the plan). This is intentional, not an oversight: :func:`apply_migrations` must be able to bring a
PRE-EXISTING file (real tables, ``user_version == 0``, never ledgered) up to baseline WITHOUT
constructing the real store class first — that class's own constructor now calls
:func:`~tos_runtime.operations.schema_ledger.open_or_create_schema`, which would immediately
refuse a non-fresh, sub-baseline file with :class:`~tos_runtime.operations.schema_ledger
.SchemaVersionRefused` — precisely the refusal this function exists to resolve. Importing the
store classes here to reuse their DDL would recreate that exact bootstrapping problem.

**Shape verification before stamping (plan §2 decision 3: "PRAGMA table_info 로 현 형상 일치 검증
후 스탬프(불일치 = 거부)").** For a pre-existing file (``user_version == 0``, tables already
present), :func:`apply_migrations` compares each table's REAL, on-disk column set against this
module's own expected column set before running anything — a mismatch refuses
(:class:`SchemaMigrationRefused`) rather than silently running ``CREATE TABLE IF NOT EXISTS``
over a table whose shape this code does not actually recognize.

Firewall: stdlib (``sqlite3``, ``hashlib``, ``time``) only.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tos_runtime.operations.schema_ledger import (
    MIGRATE_APPLIED_BY,
    SCHEMA_LEDGER_TABLE_SQL,
    read_schema_version,
)

__all__ = [
    "EVIDENCE_MIGRATIONS",
    "INBOX_MIGRATIONS",
    "MigrationOutcome",
    "MARKETFEED_MIGRATIONS",
    "RCL_MIGRATIONS",
    "STORE_MIGRATIONS",
    "SchemaMigration",
    "SchemaMigrationRefused",
    "apply_migrations",
    "schema_version",
]


class SchemaMigrationRefused(RuntimeError):
    """Raised by :func:`apply_migrations` — a pre-existing file's real shape disagrees with the
    migration's expected shape, or the file is already ahead of every known migration.
    """


@dataclass(frozen=True)
class MigrationOutcome:
    """What one :func:`apply_migrations` call actually did — the operator-facing report.

    ``migrate`` used to print "is current" for three materially different outcomes: nothing to
    do, versions applied, and an auxiliary structure rebuilt. Returning this lets the CLI say
    which (review L3).

    Args:
        store_name: The store this ran against.
        from_version: ``PRAGMA user_version`` on entry.
        to_version: ``PRAGMA user_version`` on exit.
        applied: Versions whose statements ran, in order.
        ledgered: The subset of :attr:`applied` that also wrote a ``schema_ledger`` row. A
            version can be applied WITHOUT being ledgered when its row already survived from an
            earlier run (the ledger is append-only, so a re-applied step is never re-recorded).
        repaired: Names of auxiliary structures rebuilt at an already-current version.
    """

    store_name: str
    from_version: int
    to_version: int
    applied: tuple[int, ...]
    ledgered: tuple[int, ...]
    repaired: tuple[str, ...]

    @property
    def changed(self) -> bool:
        """Whether this call altered the file at all."""
        return bool(self.applied or self.repaired)


@dataclass(frozen=True)
class SchemaMigration:
    """One registered schema migration for one store.

    Args:
        version: The ``PRAGMA user_version`` this migration brings a store TO — migrations for a
            store are applied strictly in ascending, gapless order starting from
            ``current_version + 1``.
        description: Free-text, operator-facing.
        statements: The DDL statements applied, in order, inside one transaction.
        expected_tables: ``{table_name: (column_name, ...)}`` — the shape this migration
            produces (or, for a pre-existing file already holding these tables under
            ``user_version == 0``, the shape :func:`apply_migrations` verifies BEFORE stamping).
            Column order matters (matches ``PRAGMA table_info`` order); empty for a migration
            that adds no new table shape to verify (none in this wave).
        repair_statements: The subset of :attr:`statements` that is safe to re-run against a
            file ALREADY stamped at :attr:`version`, to rebuild an auxiliary structure that was
            dropped out from under it (:func:`apply_migrations`'s repair pass). Only genuinely
            idempotent DDL belongs here: ``CREATE INDEX IF NOT EXISTS`` qualifies, ``ALTER TABLE
            ... ADD COLUMN`` does NOT (it raises "duplicate column name" on the second run), so
            this is stated per migration rather than inferred. Empty means "this version has
            nothing repairable" — the default, and the honest answer for every migration that
            changes column shape.
    """

    version: int
    description: str
    statements: tuple[str, ...]
    expected_tables: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    repair_statements: tuple[str, ...] = ()

    @property
    def statements_digest(self) -> str:
        """sha256 over the canonical join of :attr:`statements` — the ledger's own
        ``migration_digest`` value for this migration."""
        canonical = "\n".join(self.statements)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -- evidence store baseline (mirrors tos_runtime.evidence.store + .outbox) -------------------

_EVIDENCE_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS entries (
        seq INTEGER PRIMARY KEY,
        segment_id TEXT,
        kind TEXT NOT NULL,
        record_class TEXT NOT NULL,
        runtime_identity_json TEXT,
        payload_json TEXT NOT NULL,
        entry_digest TEXT NOT NULL,
        chain_digest TEXT NOT NULL,
        key_generation INTEGER NOT NULL,
        appended_at_monotonic_ns INTEGER NOT NULL
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_update
    BEFORE UPDATE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_delete
    BEFORE DELETE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TABLE IF NOT EXISTS outbox (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_seq INTEGER NOT NULL,
        target TEXT NOT NULL,
        delivered_at_monotonic_ns INTEGER
    )
    """,
)

_EVIDENCE_V2_STATEMENTS: tuple[str, ...] = (
    """
    CREATE INDEX IF NOT EXISTS entries_kind_seq ON entries (kind, seq)
    """,
)

EVIDENCE_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description="baseline — entries (append-only) + outbox",
        statements=_EVIDENCE_BASELINE_STATEMENTS,
        expected_tables={
            "entries": (
                "seq",
                "segment_id",
                "kind",
                "record_class",
                "runtime_identity_json",
                "payload_json",
                "entry_digest",
                "chain_digest",
                "key_generation",
                "appended_at_monotonic_ns",
            ),
            "outbox": (
                "seq",
                "entry_seq",
                "target",
                "delivered_at_monotonic_ns",
            ),
        },
    ),
    # Evidence growth plan §2 A2 (docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md):
    # `entries` gains the `entries_kind_seq` covering index, mirroring
    # `tos_runtime.evidence.store`'s own `_CREATE_KIND_SEQ_INDEX_SQL` (which a FRESH file gets
    # at genesis — this migration is the pre-existing-file half). Like RCL's v2 above it only
    # ever runs against an already-v1-ledgered store, so `expected_tables` is empty; and unlike
    # every other migration in this module it changes NO column shape at all, which is exactly
    # why it is safe: an index is an auxiliary structure, so no row's bytes, `entry_digest` or
    # `chain_digest` move and `SqliteEvidenceStore.verify()` is unaffected.
    SchemaMigration(
        version=2,
        description=(
            "entries gains the entries_kind_seq (kind, seq) covering index — the 14 "
            "boot/recovery readers' WHERE kind = ?/IN (...) ORDER BY seq shape, of the 19 "
            "modules that read this store at all (evidence growth plan §2 A2)"
        ),
        statements=_EVIDENCE_V2_STATEMENTS,
        # The whole migration is one `CREATE INDEX IF NOT EXISTS`, so re-running it against an
        # already-v2 file is a no-op when the index is there and a rebuild when it is not —
        # which is exactly the repair `migrate` needs to be able to perform (review HIGH-1: a
        # dropped index is otherwise invisible to every check and unreachable by every tool).
        repair_statements=_EVIDENCE_V2_STATEMENTS,
    ),
)

# -- RCL commit log baseline (mirrors tos_runtime.rcl.schema) ---------------------------------

_RCL_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS epochs (
        epoch INTEGER PRIMARY KEY,
        issued_at_monotonic_ns INTEGER NOT NULL,
        runtime_generation INTEGER,
        runtime_identity_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entries (
        seq INTEGER PRIMARY KEY,
        writer_epoch INTEGER NOT NULL,
        command_id TEXT NOT NULL UNIQUE,
        command_digest TEXT,
        kind TEXT,
        payload_digest TEXT,
        payload_json TEXT,
        is_reservation_transition INTEGER NOT NULL DEFAULT 0
            CHECK (is_reservation_transition IN (0, 1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reservations (
        reservation_id TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        last_seq INTEGER NOT NULL,
        scope_account TEXT NOT NULL,
        scope_instrument TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS epochs_no_update
    BEFORE UPDATE ON epochs
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: epochs is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS epochs_no_delete
    BEFORE DELETE ON epochs
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: epochs is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_update
    BEFORE UPDATE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: entries is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_delete
    BEFORE DELETE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: entries is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS reservations_no_delete
    BEFORE DELETE ON reservations
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: reservations rows are never deleted');
    END
    """,
)

_RCL_V2_STATEMENTS: tuple[str, ...] = (
    """
    ALTER TABLE reservations ADD COLUMN committed_vector_json TEXT
    """,
)

RCL_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description="baseline — epochs + entries (append-only) + reservations (UPDATE-only projection)",
        statements=_RCL_BASELINE_STATEMENTS,
        expected_tables={
            "epochs": (
                "epoch",
                "issued_at_monotonic_ns",
                "runtime_generation",
                "runtime_identity_json",
            ),
            "entries": (
                "seq",
                "writer_epoch",
                "command_id",
                "command_digest",
                "kind",
                "payload_digest",
                "payload_json",
                "is_reservation_transition",
            ),
            "reservations": (
                "reservation_id",
                "state",
                "last_seq",
                "scope_account",
                "scope_instrument",
            ),
        },
    ),
    # Kernel round #4 K-4: `reservations` gains `committed_vector_json` (the durable form of
    # `CapacityReservationTransition.committed_vector`, tos/src/tos/rcl/commitlog.py). This
    # migration only ever runs against an already-v1-ledgered store (current_version == 1 by
    # the time apply_migrations reaches it), so `expected_tables` is empty — the pre-shape
    # verification in `_verify_expected_shape_or_refuse` only fires for `current_version == 0`,
    # which v1's own entry above already claimed for a totally fresh/untracked file.
    SchemaMigration(
        version=2,
        description=(
            "reservations gains committed_vector_json (kernel round #4 K-4 "
            "CapacityReservationTransition.committed_vector)"
        ),
        statements=_RCL_V2_STATEMENTS,
    ),
)

# -- event inbox baseline (mirrors tos_runtime.engine.inbox, _ADDED_COLUMNS folded in) --------

_INBOX_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS events (
        seq INTEGER PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL,
        account TEXT NOT NULL,
        instrument TEXT NOT NULL,
        reference_json TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        payload_digest TEXT NOT NULL,
        consumed_evidence_seq INTEGER,
        consumed_generation INTEGER,
        handling_started_evidence_seq INTEGER,
        handling_started_generation INTEGER
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS events_unconsumed
    ON events (seq) WHERE consumed_evidence_seq IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS attempt_composites (
        attempt_id TEXT PRIMARY KEY,
        composite_json TEXT NOT NULL,
        observation_revision INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attempt_finality_witness (
        attempt_id TEXT PRIMARY KEY,
        witness INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS new_risk_halt (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        reason TEXT NOT NULL,
        event_id TEXT,
        evidence_seq INTEGER
    )
    """,
)

INBOX_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description=(
            "baseline — events (incl. the pre-ledger _ADDED_COLUMNS handling_started_* "
            "columns) + attempt_composites + attempt_finality_witness + new_risk_halt"
        ),
        statements=_INBOX_BASELINE_STATEMENTS,
        expected_tables={
            "events": (
                "seq",
                "event_id",
                "kind",
                "account",
                "instrument",
                "reference_json",
                "payload_json",
                "payload_digest",
                "consumed_evidence_seq",
                "consumed_generation",
                "handling_started_evidence_seq",
                "handling_started_generation",
            ),
            "attempt_composites": (
                "attempt_id",
                "composite_json",
                "observation_revision",
            ),
            "attempt_finality_witness": ("attempt_id", "witness"),
            "new_risk_halt": ("id", "reason", "event_id", "evidence_seq"),
        },
    ),
)

# -- marketfeed snapshot store baseline (mirrors tos_runtime.marketfeed.store) ----------------

_MARKETFEED_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id TEXT PRIMARY KEY,
        canonical_digest TEXT NOT NULL,
        instrument TEXT NOT NULL,
        as_of_ms INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS snapshots_instrument_as_of
    ON snapshots (instrument, as_of_ms)
    """,
    """
    CREATE TABLE IF NOT EXISTS preimages (
        snapshot_id TEXT NOT NULL,
        raw_event_id TEXT NOT NULL,
        preimage_json TEXT NOT NULL,
        PRIMARY KEY (snapshot_id, raw_event_id)
    )
    """,
)

MARKETFEED_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description=(
            "baseline — snapshots (content-addressed, one row per issued "
            "CriticalInputSnapshot) + preimages (durable, keyed by (snapshot_id, raw_event_id))"
        ),
        statements=_MARKETFEED_BASELINE_STATEMENTS,
        expected_tables={
            "snapshots": (
                "snapshot_id",
                "canonical_digest",
                "instrument",
                "as_of_ms",
                "snapshot_json",
            ),
            "preimages": (
                "snapshot_id",
                "raw_event_id",
                "preimage_json",
            ),
        },
    ),
)

STORE_MIGRATIONS: Mapping[str, tuple[SchemaMigration, ...]] = {
    "evidence": EVIDENCE_MIGRATIONS,
    "rcl": RCL_MIGRATIONS,
    "inbox": INBOX_MIGRATIONS,
    "marketfeed": MARKETFEED_MIGRATIONS,
}


def schema_version(path: Path) -> int:
    """Read-only: the ``PRAGMA user_version`` currently stamped on the sqlite file at ``path``.

    Opens and closes its own connection — never assumes the store at ``path`` is open or closed
    elsewhere in this process (a read-only ``PRAGMA`` is safe against a concurrently open WAL
    file either way).
    """
    conn = sqlite3.connect(str(path))
    try:
        return read_schema_version(conn)
    finally:
        conn.close()


def _ledger_has_version(conn: sqlite3.Connection, version: int) -> bool:
    """Whether ``schema_ledger`` already carries a row for ``version``.

    ``schema_ledger.version`` is a PRIMARY KEY on an append-only table, so a re-applied step
    cannot insert a second row and cannot delete the first — it can only skip the insert
    (review HIGH-1: before this check, a step whose ledger row survived a rollback aborted the
    whole transaction with ``IntegrityError`` and stranded the file).
    """
    row = conn.execute(
        "SELECT 1 FROM schema_ledger WHERE version = ?", (version,)
    ).fetchone()
    return row is not None


def _repair_at_current_version(
    conn: sqlite3.Connection, head: SchemaMigration
) -> tuple[str, ...]:
    """Re-run ``head``'s :attr:`~SchemaMigration.repair_statements` against an already-current
    file, and report which auxiliary structures were actually rebuilt.

    Exists because an auxiliary structure — an index — can be dropped out from under a stamped
    version and leave NOTHING that notices: ``PRAGMA user_version`` still reads latest, the
    schema-ledger boot check passes, and ``compute_schema_shape_digest`` reads
    ``PRAGMA table_info``, which is blind to indexes. Before this pass the only tool that could
    have rebuilt it (``migrate``) no-op'd, because its loop skips every version ``<=
    current_version``.

    The statements are idempotent by declaration (see :attr:`SchemaMigration.repair_statements`),
    so this is a no-op on a healthy file. The return value names what was missing, which is what
    lets the CLI say "repaired" instead of the misleading "is current".
    """
    if not head.repair_statements:
        return ()
    before = _index_names(conn)
    for statement in head.repair_statements:
        conn.execute(statement)
    conn.commit()
    return tuple(sorted(_index_names(conn) - before))


def _index_names(conn: sqlite3.Connection) -> frozenset[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name IS NOT NULL"
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


def _verify_expected_shape_or_refuse(
    conn: sqlite3.Connection, *, store_name: str, migration: SchemaMigration
) -> None:
    """Refuse if any of ``migration.expected_tables`` ALREADY EXISTS with a different column set.

    A table that does not exist yet is not a mismatch (the migration's own ``CREATE TABLE IF NOT
    EXISTS`` will create it) — only an EXISTING table with the WRONG shape refuses.
    """
    for table_name, expected_columns in migration.expected_tables.items():
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not rows:
            continue
        actual_columns = tuple(row[1] for row in rows)
        if actual_columns != tuple(expected_columns):
            raise SchemaMigrationRefused(
                f"{store_name}: pre-existing table {table_name!r} has columns "
                f"{actual_columns!r}, expected {tuple(expected_columns)!r} for migration "
                f"version {migration.version} — refusing to stamp a shape this code does not "
                "recognize (migrate refuses, never silently reshapes)"
            )


def apply_migrations(
    path: Path,
    store_name: str,
    *,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> MigrationOutcome:
    """Bring the CLOSED store file at ``path`` up to ``store_name``'s latest known migration.

    Operates on its own, fresh ``sqlite3.connect`` — the caller is responsible for the store
    being closed everywhere else in this process first (this function does not itself detect a
    concurrently open handle; matches :mod:`tos_runtime.operations.backup_set`'s own documented
    precondition).

    Args:
        path: The sqlite file to migrate in place.
        store_name: One of :data:`STORE_MIGRATIONS`'s keys (``"evidence"`` / ``"rcl"`` /
            ``"inbox"``).
        monotonic_ns: Injected monotonic-clock callable for the ledger row's
            ``applied_at_monotonic_ns``.

    Returns:
        A :class:`MigrationOutcome` naming what ran — versions applied, ledger rows written,
        and auxiliary structures repaired at an already-current version.

    Raises:
        ValueError: ``store_name`` is not registered.
        SchemaMigrationRefused: The file is already ahead of every known migration for this
            store, or a pre-existing table's real shape disagrees with what a migration expects.
    """
    migrations = STORE_MIGRATIONS.get(store_name)
    if migrations is None:
        raise ValueError(f"apply_migrations: unknown store_name {store_name!r}")

    conn = sqlite3.connect(str(path))
    try:
        conn.execute(SCHEMA_LEDGER_TABLE_SQL)
        current_version = read_schema_version(conn)
        target_version = migrations[-1].version
        if current_version > target_version:
            raise SchemaMigrationRefused(
                f"{store_name}: on-disk user_version={current_version} is already AHEAD of "
                f"the newest known migration ({target_version}) — refusing"
            )
        from_version = current_version
        applied: list[int] = []
        ledgered: list[int] = []
        for migration in migrations:
            if migration.version <= current_version:
                continue
            if current_version == 0:
                _verify_expected_shape_or_refuse(
                    conn, store_name=store_name, migration=migration
                )
            already_ledgered = _ledger_has_version(conn, migration.version)
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in migration.statements:
                    conn.execute(statement)
                if not already_ledgered:
                    conn.execute(
                        "INSERT INTO schema_ledger "
                        "(version, applied_at_monotonic_ns, migration_digest, applied_by) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            migration.version,
                            monotonic_ns(),
                            migration.statements_digest,
                            MIGRATE_APPLIED_BY,
                        ),
                    )
                conn.execute(f"PRAGMA user_version = {int(migration.version)}")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            applied.append(migration.version)
            if not already_ledgered:
                ledgered.append(migration.version)
            current_version = migration.version

        repaired: tuple[str, ...] = ()
        if not applied and current_version == target_version:
            repaired = _repair_at_current_version(conn, migrations[-1])
        return MigrationOutcome(
            store_name=store_name,
            from_version=from_version,
            to_version=current_version,
            applied=tuple(applied),
            ledgered=tuple(ledgered),
            repaired=repaired,
        )
    finally:
        conn.close()
