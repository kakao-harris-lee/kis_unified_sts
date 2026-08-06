"""S-1 — the durable per-dimension composite marker store (design #39 §5.1).

ADR-002-005 §13 line 197 verbatim: "All five dimensions SHALL be durable and
reconstructable after crash, restart, or failover." This module realizes the *durable*
half on a real on-disk substrate; :mod:`tos.staterestore.reload` realizes the
*reconstructable* half.

Substrate
---------
stdlib ``sqlite3``, ``journal_mode=WAL``, ``synchronous=FULL`` (design #39 §3.2 A). Two
properties are load-bearing and both are falsifiable (§3.4):

* **durable commit** — a committed row survives an ``os._exit`` crash and is read back
  by a *fresh process*. Falsified by: a post-commit crash losing a committed row.
* **incomplete-store rollback** — writes that were still inside a transaction when the
  process died roll back on reopen, so a reader observes the last committed state and
  never a half-written row. Falsified by: a reopened store exposing a torn record.

Per-dimension transactions
--------------------------
The five dimensions are committed in :data:`DIMENSION_COMMIT_ORDER`, **one transaction
per dimension**. That is what makes the STATE-EV-004 line 1045 injection points
realizable: a crash *between* two of those transactions is a legitimate "incomplete
store", not a corruption. The order follows the ADR's own write-ahead ordering —
identity and capacity are durable before the send boundary, the attempt marker
(``SEND_STARTED``) is durable **before** the external call (§6 line 96), broker evidence
can only follow the call (§7 line 104), and knowledge/evidence is persisted last (line
1045 "before evidence persistence").

This module is non-transmitting: it opens a local file and nothing else. No socket, no
route, no credential, no ambient env (``tos/__init__.py`` line 6; TOS-FW-B / TOS-FW-C).
"""

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

#: The fixed per-dimension commit order (see the module docstring). A crash after the
#: *k*-th entry leaves exactly the first *k* dimensions durable — that is the whole
#: mechanism behind the design #39 §4 "incomplete store" cell.
DIMENSION_COMMIT_ORDER: tuple[StateDimension, ...] = (
    StateDimension.INTENT,
    StateDimension.CAPACITY,
    StateDimension.TRANSMISSION_ATTEMPT,
    StateDimension.BROKER_ORDER,
    StateDimension.KNOWLEDGE,
)

#: The composite attribute each dimension marker carries.
_DIMENSION_FIELD: dict[StateDimension, str] = {
    StateDimension.INTENT: "intent_state",
    StateDimension.TRANSMISSION_ATTEMPT: "transmission_attempt_state",
    StateDimension.BROKER_ORDER: "broker_order_state",
    StateDimension.KNOWLEDGE: "knowledge_state",
    StateDimension.CAPACITY: "capacity_state",
}

#: The enum each dimension's stored string is coerced back through on reload. A value
#: that is not a member of its own dimension's enum is a :class:`StoreIntegrityError`,
#: never a silently-accepted string: global string-value distinctness across the five
#: dimension enums (design #8 §2.2) is what makes a dimension swap detectable, and
#: skipping the coercion would discard exactly that canary.
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
    """A stored marker cannot be read back as a member of its own dimension.

    Fail-closed: an unreadable store is never summarised as an empty one. "The store
    holds nothing" and "the store holds something this code cannot interpret" are
    different findings, and collapsing them would let a corrupted marker be re-derived
    as an *absent* one — which the conservative fill would then quietly repair
    (design #39 §0.5 O-1: the fail-open lives in the wiring, not in the predicate).
    """


class CompositeStateStore:
    """A durable, per-dimension marker store for :class:`CompositeState` (S-1).

    Usage is deliberately explicit rather than magical: the caller commits dimensions
    one at a time (or all five through :meth:`commit_composite`), and each call is its
    own transaction that has returned only after sqlite reports the commit. There is no
    write buffer, no autocommit-deferred queue, and no in-process cache of what was
    written — :meth:`read_markers` always re-reads the file.

    Attributes:
        path: The on-disk store file. It is a real filesystem path: an in-memory sqlite
            database would make ``persistence_real`` unfalsifiable, which is the exact
            EV-L2-pilot C1 defect ("in-memory redefinition") this stage exists to avoid.
    """

    def __init__(self, path: Path) -> None:
        """Open (creating if needed) the store at ``path`` in WAL / synchronous=FULL."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(_SCHEMA)

    # -- context manager ----------------------------------------------------

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

    # -- write path ---------------------------------------------------------

    def commit_dimension(
        self,
        intent_identity: str,
        dimension: StateDimension,
        state_value: str,
    ) -> None:
        """Commit one dimension marker in its own transaction.

        The explicit ``BEGIN`` / ``COMMIT`` pair (``isolation_level=None`` disables
        pysqlite's implicit transaction management) is what makes the transaction
        boundary the *observable* crash boundary: a crash before ``COMMIT`` returns
        leaves the marker absent, and a crash after it leaves the marker durable. There
        is no third outcome for a reader to see.

        Args:
            intent_identity: The immutable intent identity the marker belongs to
                (ADR-002-005 §5 line 76 SAFE-020).
            dimension: Which of the five orthogonal dimensions this marker carries.
            state_value: The dimension's state as its spec string.
        """
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
        """Commit the composite's five dimensions, one transaction each.

        Args:
            composite: The observation whose dimensions become durable. Its
                ``intent_identity`` is required — an unidentified record cannot be
                re-associated after a restart, and storing it under a synthesised key
                would fabricate the identity the reload path is supposed to re-derive.
            stop_after: Commit only the first ``stop_after`` dimensions of
                :data:`DIMENSION_COMMIT_ORDER` (``None`` = all five). This is how an
                *incomplete store* is produced deliberately; it is not a crash by
                itself.

        Returns:
            The dimensions actually committed, in commit order.

        Raises:
            StoreIntegrityError: If the composite carries no ``intent_identity``.
        """
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

    # -- read path ----------------------------------------------------------

    def read_markers(self, intent_identity: str) -> dict[StateDimension, object]:
        """Re-read the durable markers for ``intent_identity`` from the file.

        Returns:
            A mapping of the dimensions actually present to their coerced enum values.
            An absent dimension is simply **not a key** — the caller decides what an
            absence means (:mod:`tos.staterestore.reload` fills it conservatively), and
            this method never invents a default of its own.

        Raises:
            StoreIntegrityError: If a stored string is not a member of its dimension's
                enum, or the row names a dimension outside the five.
        """
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
