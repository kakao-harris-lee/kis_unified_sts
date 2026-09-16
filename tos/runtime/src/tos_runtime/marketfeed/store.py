"""``SqliteSnapshotStore`` — the durable half of the admitted-snapshot injection port (design #38;
plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 3).

One sqlite3 file, two tables: ``snapshots`` (one row per issued :class:`~tos.capsule
.CriticalInputSnapshot`, content-addressed by its own ``snapshot_id``/``canonical_digest``) and
``preimages`` (one row per ``(snapshot_id, raw_event_id)`` pair — the durable
:class:`~tos.marketfeed.RawPayloadPreimage` bodies a snapshot's covered observations' digests
address). Implements :class:`~tos_runtime.marketfeed.ports.DurableSnapshotStore` — the SAME object
plays both kernel-injected roles (:class:`~tos.marketfeed.SnapshotStore` via :meth:`__call__`,
:class:`~tos.marketfeed.ValueCandidateSource` via :meth:`candidates`) because both read the same
durable rows; see that Protocol's own docstring for why splitting them would let the two halves
disagree.

**Digest re-check, not id lookup (mutation M3).** :meth:`__call__` compares the STORED
``canonical_digest`` column against the REQUESTED ``canonical_digest`` argument before returning a
body — a live ``snapshot_id`` whose stored digest disagrees with what the caller asked for returns
``None``, never the body (ADR-002-018 §15:386 — a more-permissive substitute is refused here, not
merely caught downstream by ``publish_context_value_view``'s own binding gate). A missing row is
``None`` too — never a nearest match, never a substitute.

**Durability, restart-proven (mutation M4).** ``preimages`` are on disk, not held in the producer
process's memory — a fresh :class:`SqliteSnapshotStore` opened over the same file after a restart
resolves the exact same body and the exact same candidates a pre-restart instance would have. See
``tos/runtime/tests/marketfeed/test_store.py``'s restart test, which proves this by publishing a
view through the REAL kernel :func:`~tos.marketfeed.value.publish_context_value_view` /
:class:`~tos.marketfeed.MarketFeedContextResolver` against a second, freshly-opened store instance.

**Single-instrument-scoped, by construction of this store's own schema (plan §2 decision 3 — the
store decision, not the scheduler's).** :meth:`put` derives the ``snapshots.instrument`` column
from ``snapshot.scope.instruments`` and REFUSES a snapshot whose scope does not name exactly one
instrument — :meth:`latest_as_of` is keyed by a single ``instrument TEXT`` column, and a snapshot
claiming more than one (or zero) would make that key ambiguous. This refusal is a necessity of THIS
schema, not an inherited policy: the scheduler's own single-instrument rule (plan §2 decision 8) is
a SEPARATE discipline this store neither implements nor depends on — a future multi-instrument
schema (a composite key, or one row per instrument) could drop this refusal without the scheduler
changing at all. The two happen to agree today because FORWARD-OBLIGATION-MS1's multi-symbol
ingest-ordering obligation is unratified (``ports.py``'s own
:class:`~tos_runtime.marketfeed.ports.TickOutcome` docstring), not because one derives from the
other.

**Candidates are claims, not pre-filtered admissions.** :meth:`candidates` returns one
:class:`~tos.marketfeed.AdmittedValue` per preimage entry per covered observation — every payload
key this snapshot durably recorded, unfiltered by what this module thinks is admissible. The
kernel's own publication gate (``tos.marketfeed.value._admit_one``) is the sole authority on
admission; a store that pre-filtered would just be a second, informal gate that could disagree with
the real one. The one exception is dispatch scope: a request whose ``instrument_key`` names an
account/instrument outside ``snapshot.scope`` gets ``()`` — mirroring
``tos/tests/slice/_slice_fixtures.py``'s ``BandBarBook.candidate_source`` — because that is routing,
not admission.

**Atomicity.** :meth:`put` writes the snapshot row and every preimage row inside one
``BEGIN IMMEDIATE`` ... ``COMMIT`` transaction, with ``ROLLBACK`` on any failure — the same
discipline :mod:`tos_runtime.evidence.store` and :mod:`tos_runtime.engine.inbox` already use. A
snapshot row without its preimages is exactly the state that makes a later ``candidates()`` read
silently starve every value operand, so a partial write must never be observable. ``INSERT OR
IGNORE`` makes a retried ``put`` of the SAME (content-addressed) snapshot a safe no-op rather than a
``UNIQUE`` constraint error — the same duplicate-safe idiom :class:`~tos_runtime.engine.inbox
.SqliteEventInbox.enqueue` uses for its own content-addressed ``event_id``.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``sqlite3``, ``time``) +
``tos.*`` (``tos.capsule``, ``tos.engine``, ``tos.marketfeed``) + ``tos_runtime.operations`` (the
schema-ledger boot check, mirroring every other runtime-owned sqlite store) only. No ``shared.*``,
no network, no clock read beyond the injected ``monotonic_ns`` the schema ledger's genesis stamp
uses.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from tos.capsule import CriticalInputSnapshot
from tos.capsule.observation import Observation
from tos.engine import InstrumentKey
from tos.marketfeed import AdmittedValue, RawPayloadPreimage

from tos_runtime.operations.schema_ledger import (
    compute_schema_shape_digest,
    ensure_schema_current,
    file_is_fresh,
)

__all__ = [
    "MARKETFEED_FILE_NAME",
    "MARKETFEED_SCHEMA_VERSION",
    "InjectedCrash",
    "SqliteSnapshotStore",
]

#: This store's own ``PRAGMA user_version`` / ``schema_ledger`` baseline (mirrors
#: ``tos_runtime.evidence.store.EVIDENCE_SCHEMA_VERSION``'s own docstring convention). Bumped only
#: when ``snapshots``/``preimages`` actually change shape; see
#: ``tos_runtime.operations.schema_migrations.MARKETFEED_MIGRATIONS`` for the registered migration
#: this version corresponds to.
MARKETFEED_SCHEMA_VERSION = 1

#: This store's own file name for a ``data_dir`` layout. The four sibling constants
#: (``EVIDENCE_FILE_NAME``/``RCL_FILE_NAME``/``INBOX_FILE_NAME``/``COMPOSITE_STATE_FILE_NAME``)
#: live in :mod:`tos_runtime.operations.backup_set` instead, because they name the members of the
#: *backup set* — this store is deliberately NOT a backup-set member yet; that membership is a
#: separate decision with its own restore semantics, owned by the tick-source wave's lane D. This
#: constant exists on its own, here, only because ``tos_runtime.compose.cli``'s ``migrate``
#: subcommand needs a path for this store the moment ``"marketfeed"`` joins
#: :data:`~tos_runtime.operations.schema_migrations.STORE_MIGRATIONS`.
MARKETFEED_FILE_NAME = "marketfeed.sqlite3"

_CREATE_SNAPSHOTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    canonical_digest TEXT NOT NULL,
    instrument TEXT NOT NULL,
    as_of_ms INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL
)
"""

_CREATE_SNAPSHOTS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS snapshots_instrument_as_of
ON snapshots (instrument, as_of_ms)
"""

_CREATE_PREIMAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS preimages (
    snapshot_id TEXT NOT NULL,
    raw_event_id TEXT NOT NULL,
    preimage_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, raw_event_id)
)
"""


class InjectedCrash(RuntimeError):
    """Raised by a test-supplied ``crash_hook`` to simulate a process death mid-:meth:`put`.

    Mirrors :class:`tos_runtime.evidence.store.InjectedCrash` — never raised by production code
    paths; this module only *calls* the injected hook, which decides whether to raise.
    """


def _single_instrument(instruments: tuple[str, ...]) -> str:
    """The one instrument ``snapshot.scope.instruments`` must name (module docstring).

    Raises:
        ValueError: ``instruments`` does not carry exactly one name.
    """
    if len(instruments) != 1:
        raise ValueError(
            "SqliteSnapshotStore.put: this store's schema keys latest_as_of by a single "
            "instrument column (module docstring) — snapshot.scope.instruments must name "
            f"exactly one instrument, got {instruments!r}"
        )
    return instruments[0]


def _latest_observation_as_of(observations: Sequence[Observation]) -> int:
    """The newest ``time.source_event_time`` among ``snapshot.observations``.

    Args:
        observations: ``snapshot.observations``.

    Raises:
        ValueError: no observation carries a concrete ``source_event_time`` — a snapshot with no
            dateable observation gives this store nothing to index ``latest_as_of`` by, and
            substituting a fabricated bound (0, "now") would be exactly the kind of invented
            freshness fact this wave's governance discipline refuses.
    """
    as_of_values: tuple[int, ...] = tuple(
        observation.time.source_event_time
        for observation in observations
        if observation.time.source_event_time is not None
    )
    if not as_of_values:
        raise ValueError(
            "SqliteSnapshotStore.put: snapshot carries no observation with a concrete "
            "time.source_event_time — cannot durably index it for latest_as_of"
        )
    return max(as_of_values)


class SqliteSnapshotStore:
    """The durable, content-addressed snapshot + preimage store (module docstring).

    One sqlite3 file (``journal_mode=WAL``, ``synchronous=FULL``), mirroring
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s own transaction discipline.
    """

    def __init__(
        self,
        path: Path,
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        crash_hook: Callable[[str], None] | None = None,
    ) -> None:
        """Open (or create) the snapshot store at ``path``.

        Args:
            path: The sqlite file path. Parent directory must already exist (this module never
                creates directories — matches every other runtime-owned sqlite store).
            monotonic_ns: Injected monotonic-clock callable for the schema-ledger genesis stamp
                only — never read directly (matches ``SqliteEvidenceStore``'s own constructor
                discipline).
            crash_hook: Test-only fault-injection callable, called as ``crash_hook("before_commit")``
                immediately before :meth:`put`'s own ``COMMIT`` — mirrors
                :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s own ``crash_hook``
                idiom, used here to prove :meth:`put`'s atomicity (a hook that raises leaves the
                transaction rolled back, so neither table gains a row). ``None`` in production;
                this module never calls it itself except from that one point.
        """
        self.path = path
        self._monotonic_ns = monotonic_ns
        self._crash_hook = crash_hook
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        # Captured BEFORE any CREATE TABLE below runs — schema_ledger.file_is_fresh's own
        # docstring: a fresh file looks identical to an already-populated one otherwise.
        was_fresh = file_is_fresh(self._conn)
        self._conn.execute(_CREATE_SNAPSHOTS_TABLE_SQL)
        self._conn.execute(_CREATE_SNAPSHOTS_INDEX_SQL)
        self._conn.execute(_CREATE_PREIMAGES_TABLE_SQL)
        ensure_schema_current(
            self._conn,
            store_name="marketfeed",
            schema_version=MARKETFEED_SCHEMA_VERSION,
            was_fresh=was_fresh,
            migration_digest=compute_schema_shape_digest(
                self._conn, ("snapshots", "preimages")
            ),
            monotonic_ns=monotonic_ns,
        )

    def close(self) -> None:
        """Close the underlying sqlite3 connection."""
        self._conn.close()

    def put(
        self,
        snapshot: CriticalInputSnapshot,
        preimages: Mapping[str, RawPayloadPreimage],
    ) -> None:
        """Durably record ``snapshot`` and every preimage its observations address.

        Args:
            snapshot: The issued snapshot — ``snapshot_id``/``canonical_digest`` must both be
                concrete (an unissued/``DRAFT`` snapshot has neither) and ``scope.instruments``
                must name exactly one instrument (module docstring).
            preimages: ``raw_event_id -> preimage`` for every observation ``snapshot`` covers.

        Raises:
            ValueError: ``snapshot`` is not issued (missing id/digest), does not name exactly one
                scope instrument, or has no observation with a concrete as-of.
        """
        if snapshot.snapshot_id is None or snapshot.canonical_digest is None:
            raise ValueError(
                "SqliteSnapshotStore.put: snapshot must be issued (concrete snapshot_id and "
                f"canonical_digest), got snapshot_id={snapshot.snapshot_id!r} "
                f"canonical_digest={snapshot.canonical_digest!r}"
            )
        instrument = _single_instrument(snapshot.scope.instruments)
        as_of_ms = _latest_observation_as_of(snapshot.observations)
        snapshot_json = snapshot.model_dump_json()
        serialized_preimages = tuple(
            (raw_event_id, preimage.model_dump_json())
            for raw_event_id, preimage in preimages.items()
        )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO snapshots "
                "(snapshot_id, canonical_digest, instrument, as_of_ms, snapshot_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.canonical_digest,
                    instrument,
                    as_of_ms,
                    snapshot_json,
                ),
            )
            for raw_event_id, preimage_json in serialized_preimages:
                self._conn.execute(
                    "INSERT OR IGNORE INTO preimages "
                    "(snapshot_id, raw_event_id, preimage_json) VALUES (?, ?, ?)",
                    (snapshot.snapshot_id, raw_event_id, preimage_json),
                )
            if self._crash_hook is not None:
                self._crash_hook("before_commit")
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """Resolve ``snapshot_id`` to its body iff the stored digest matches ``canonical_digest``.

        Never returns a body under a mismatched digest (mutation M3) and never returns a body for
        an unknown id — both cases answer ``None``, the store's own "no such snapshot" / "not the
        snapshot you asked for" first-class absence.
        """
        if snapshot_id is None:
            return None
        row = self._conn.execute(
            "SELECT canonical_digest, snapshot_json FROM snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        stored_digest, snapshot_json = row
        if stored_digest != canonical_digest:
            return None
        return CriticalInputSnapshot.model_validate_json(snapshot_json)

    def candidates(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> tuple[AdmittedValue, ...]:
        """One :class:`~tos.marketfeed.AdmittedValue` per preimage key per covered observation.

        Returns ``()`` when ``instrument_key`` names an account/instrument outside
        ``snapshot.scope`` (module docstring's dispatch-scope note) — otherwise every stored
        preimage entry is emitted as an unfiltered claim; the kernel's own publication gate is the
        admission authority, not this store.
        """
        if (
            instrument_key.account not in snapshot.scope.accounts
            or instrument_key.instrument not in snapshot.scope.instruments
        ):
            return ()
        rows = self._conn.execute(
            "SELECT raw_event_id, preimage_json FROM preimages WHERE snapshot_id = ?",
            (snapshot.snapshot_id,),
        ).fetchall()
        candidates: list[AdmittedValue] = []
        for raw_event_id, preimage_json in rows:
            preimage = RawPayloadPreimage.model_validate_json(preimage_json)
            for entry in preimage.entries:
                candidates.append(
                    AdmittedValue(
                        field_key=entry.key,
                        observation_ref=raw_event_id,
                        preimage=preimage,
                    )
                )
        return tuple(candidates)

    def latest_as_of(self, *, instrument: str) -> int | None:
        """The newest ``as_of_ms`` durably stored for ``instrument``, or ``None`` if none.

        Reads committed rows only (the store has no other view of "already issued") — the tick
        source's own distinctness obligation (``ports.py``'s ``DurableSnapshotStore.latest_as_of``
        docstring) relies on this being the durable truth, not an in-memory cache.
        """
        row = self._conn.execute(
            "SELECT MAX(as_of_ms) FROM snapshots WHERE instrument = ?", (instrument,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])
