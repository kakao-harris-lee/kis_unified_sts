"""``SqliteSnapshotStore`` — the durable half of the admitted-snapshot injection port (design #38;"""

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
    closing_on_failure,
    enable_wal_journal,
    open_or_create_schema,
)

__all__ = [
    "MARKETFEED_FILE_NAME",
    "MARKETFEED_SCHEMA_VERSION",
    "InjectedCrash",
    "SqliteSnapshotStore",
]

#: This store's own ``PRAGMA user_version`` / ``schema_ledger`` baseline (mirrors
MARKETFEED_SCHEMA_VERSION = 1

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
    """Raised by a test-supplied ``crash_hook`` to simulate a process death mid-:meth:`put`."""


def _single_instrument(instruments: tuple[str, ...]) -> str:
    """The one instrument ``snapshot.scope.instruments`` must name (module docstring)."""
    if len(instruments) != 1:
        raise ValueError(
            "SqliteSnapshotStore.put: this store's schema keys latest_as_of by a single "
            "instrument column (module docstring) — snapshot.scope.instruments must name "
            f"exactly one instrument, got {instruments!r}"
        )
    return instruments[0]


def _latest_observation_as_of(observations: Sequence[Observation]) -> int:
    """The newest ``time.source_event_time`` among ``snapshot.observations``."""
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


def _create_marketfeed_schema(conn: sqlite3.Connection, fresh: bool) -> None:
    """This store's own DDL, run by :func:`~tos_runtime.operations.schema_ledger"""
    del fresh
    conn.execute(_CREATE_SNAPSHOTS_TABLE_SQL)
    conn.execute(_CREATE_SNAPSHOTS_INDEX_SQL)
    conn.execute(_CREATE_PREIMAGES_TABLE_SQL)


class SqliteSnapshotStore:
    """The durable, content-addressed snapshot + preimage store (module docstring)."""

    def __init__(
        self,
        path: Path,
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        crash_hook: Callable[[str], None] | None = None,
    ) -> None:
        """Open (or create) the snapshot store at ``path``."""
        self.path = path
        self._monotonic_ns = monotonic_ns
        self._crash_hook = crash_hook
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        with closing_on_failure(self._conn):
            enable_wal_journal(self._conn)
            self._conn.execute("PRAGMA synchronous=FULL")
            open_or_create_schema(
                self._conn,
                store_name="marketfeed",
                schema_version=MARKETFEED_SCHEMA_VERSION,
                create_ddl=_create_marketfeed_schema,
                shape_tables=("snapshots", "preimages"),
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
        """Durably record ``snapshot`` and every preimage its observations address."""
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
        """Resolve ``snapshot_id`` to its body iff the stored digest matches ``canonical_digest``."""
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
        """One :class:`~tos.marketfeed.AdmittedValue` per preimage key per covered observation."""
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
        """The newest ``as_of_ms`` durably stored for ``instrument``, or ``None`` if none."""
        row = self._conn.execute(
            "SELECT MAX(as_of_ms) FROM snapshots WHERE instrument = ?", (instrument,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])
