"""S-1 — the durable per-dimension composite marker store (design #39 §5.1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState
from tos.staterestore._wal import enable_wal_journal

DIMENSION_COMMIT_ORDER: tuple[StateDimension, ...] = (
    StateDimension.INTENT,
    StateDimension.CAPACITY,
    StateDimension.TRANSMISSION_ATTEMPT,
    StateDimension.BROKER_ORDER,
    StateDimension.KNOWLEDGE,
)

_DIMENSION_FIELD: dict[StateDimension, str] = {
    StateDimension.INTENT: "intent_state",
    StateDimension.TRANSMISSION_ATTEMPT: "transmission_attempt_state",
    StateDimension.BROKER_ORDER: "broker_order_state",
    StateDimension.KNOWLEDGE: "knowledge_state",
    StateDimension.CAPACITY: "capacity_state",
}

_DIMENSION_ENUM: dict[StateDimension, type] = {
    StateDimension.INTENT: IntentState,
    StateDimension.TRANSMISSION_ATTEMPT: TransmissionAttemptState,
    StateDimension.BROKER_ORDER: BrokerOrderState,
    StateDimension.KNOWLEDGE: KnowledgeState,
    StateDimension.CAPACITY: CapacityState,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dimension_marker (
    intent_identity TEXT NOT NULL,
    dimension       TEXT NOT NULL,
    state_value     TEXT NOT NULL,
    PRIMARY KEY (intent_identity, dimension)
)
"""


class StoreIntegrityError(RuntimeError):
    """A stored marker cannot be read back as a member of its own dimension."""


class CompositeStateStore:
    """A durable, per-dimension marker store for :class:`CompositeState` (S-1)."""

    def __init__(self, path: Path) -> None:
        """Open (creating if needed) the store at ``path`` in WAL / synchronous=FULL."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        try:
            enable_wal_journal(self._conn)
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute(_SCHEMA)
        except BaseException:
            self._conn.close()
            raise

    def __enter__(self) -> CompositeStateStore:
        """Return self (the store is already open)."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the connection."""
        self.close()

    def close(self) -> None:
        """Close the sqlite connection. Committed rows are already durable."""
        self._conn.close()

    def commit_dimension(
        self,
        intent_identity: str,
        dimension: StateDimension,
        state_value: str,
    ) -> None:
        """Commit one dimension marker in its own transaction."""
        self._conn.execute("BEGIN")
        self._conn.execute(
            "INSERT INTO dimension_marker (intent_identity, dimension, state_value) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(intent_identity, dimension) DO UPDATE SET state_value=excluded.state_value",
            (intent_identity, str(dimension), str(state_value)),
        )
        self._conn.execute("COMMIT")

    def commit_composite(
        self,
        composite: CompositeState,
        *,
        stop_after: int | None = None,
    ) -> tuple[StateDimension, ...]:
        """Commit the composite's five dimensions, one transaction each."""
        identity = composite.intent_identity
        if not identity:
            raise StoreIntegrityError(
                "CompositeState.intent_identity is required to persist a composite: "
                "an unidentified durable record cannot be reconstructed after restart"
            )
        limit = len(DIMENSION_COMMIT_ORDER) if stop_after is None else stop_after
        committed: list[StateDimension] = []
        for dimension in DIMENSION_COMMIT_ORDER[:limit]:
            value = getattr(composite, _DIMENSION_FIELD[dimension])
            self.commit_dimension(identity, dimension, str(value))
            committed.append(dimension)
        return tuple(committed)

    def read_markers(self, intent_identity: str) -> dict[StateDimension, object]:
        """Re-read the durable markers for ``intent_identity`` from the file."""
        rows = self._conn.execute(
            "SELECT dimension, state_value FROM dimension_marker "
            "WHERE intent_identity = ?",
            (intent_identity,),
        ).fetchall()
        markers: dict[StateDimension, object] = {}
        for raw_dimension, raw_value in rows:
            try:
                dimension = StateDimension(raw_dimension)
            except ValueError as exc:
                raise StoreIntegrityError(
                    f"stored row names an unknown dimension {raw_dimension!r}"
                ) from exc
            enum_type = _DIMENSION_ENUM[dimension]
            try:
                markers[dimension] = enum_type(raw_value)
            except ValueError as exc:
                raise StoreIntegrityError(
                    f"stored {dimension} marker {raw_value!r} is not a member of "
                    f"{enum_type.__name__} — a marker that cannot be read back is a "
                    "corrupt record, not an absent one"
                ) from exc
        return markers
