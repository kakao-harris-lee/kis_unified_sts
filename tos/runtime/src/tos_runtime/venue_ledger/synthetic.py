"""The synthetic venue ledger: the append-only record the synthetic venue never kept (§3.1).

**What this closes (#1011 §1).** ``tos.brokeradapter.synthetic.SyntheticPaperTransport`` is a pure
function and keeps no durable record of what it accepted (F1), so the synthetic tree's only
``BrokerWitness`` re-reads the **evidence store** (F2), declares
``independent_of_evidence_store=False`` (F3), and the release consumer leaves every reservation
``CAPACITY_RELEASE_HELD`` (F4) — the scope seals after its first entry (F5). The rule is right;
what was missing is a venue-side record. This module writes one.

**Where it lives.** Its own file (:data:`VENUE_LEDGER_FILE_NAME`) inside the data leaf, in
``journal_mode=WAL`` with mode ``0600`` — a DIFFERENT file and a DIFFERENT connection from
``evidence.sqlite3`` and ``rcl.sqlite3``. That separation is the whole independence claim:
:class:`~tos_runtime.recon.witness_synthetic_venue.SyntheticVenueLedgerWitness` reads only this
file, and nothing it reports is derived from an evidence row. It is not the independence of a
real broker (the same process writes both files, as plan §6 decision 2 states outright), which is
why that witness stamps ``provenance="synthetic-venue-ledger"`` rather than claiming a broker
read.

**When it is written.** :class:`RecordingSyntheticTransport` wraps the kernel transport and
writes the row **after** ``send_once`` returns and **before** the result reaches its caller. A
write that fails raises :class:`VenueLedgerWriteFailed` instead of returning the result, so
"the venue accepted it and nothing recorded it" is unrepresentable. The caller is the egress
gateway, which already has the honest disposition for exactly this shape: any exception out of
``send_once`` becomes ``SendHaltReason.TRANSPORT_RAISED`` — "a missing acknowledgement is NOT a
non-acceptance (RFC-005 §11:322-323). The reservation stays POTENTIALLY_LIVE, the attempt stays
consumed, and nothing is resubmitted" (``tos/src/tos/egressgw/gateway.py``). This module invents
no new halt reason, no new disposition, and no new recovery path; it raises into that one.

**Identity, and what a re-send does.** A row's identity is ``broker_execution_id`` ALONE —
UNIQUE, with no date in the key. The kernel stamps a deterministic
``syn-exec:{attempt_id}:{kind}``, which already carries the attempt and the kind and is therefore
globally unique on its own; a KIS ODNO needs its date because it is a *per-day sequence*, and
this id is not one. Keying on ``(trading_date, broker_execution_id)`` looked like the same
discipline and was measurably weaker (review-1017 L1): re-sending the same attempt across a
midnight boundary produced a SECOND row for one execution, and the witness netted the fill twice.

So re-sending the same attempt after a restart (§2-3 drill) reproduces the same key on ANY day
and :meth:`SyntheticVenueLedger.record` leaves ONE row: the venue holds one execution, so the
witness's net position counts one fill. ``trading_date`` stays a column — it is the date the
venue executed (the FIRST recorded one, since the table is append-only) and the
``(broker_execution_id, order_date)`` half of
``tos_runtime.recon.service._join_orders_by_execution_id``'s C-1 cross-reference — but it is not
part of the identity. A later re-send therefore never rewrites it. The result itself is returned
unchanged, which is the
only answer consistent with the kernel ``Transport`` contract ("transmit exactly once and return
the typed result"; a fate that is unknown is ``UNKNOWN``/``TIMEOUT``, never a rejection) AND with
the engine's own duplicate handling: ``tos.engine.state.ProvisionalReservationLedger
.apply_egress_result`` keys DUPLICATE detection on ``(attempt_id, kind, filled_quantity,
remaining_quantity, broker_execution_id, resolution_generation)``, so a byte-identical re-send is
recorded as ``DUPLICATE`` and never applied twice. Returning anything else here — an ``UNKNOWN``,
say — would carry a DIFFERENT signature, escape that guard, and be applied as a second, new
result. The honest and the safe answer are the same one.

Firewall: stdlib (``datetime``, ``decimal``, ``os``, ``re``, ``sqlite3``) + ``tos.*`` +
``tos_runtime.operations.schema_ledger`` + ``tos_runtime.recon.ports`` (``WitnessUnavailable``
only — the shared read-failure exception type, the same reuse
:mod:`tos_runtime.riskstate.position` already documents). No ``shared.*``, no network, no
``os.environ``, no wall clock of its own (the trading date is injected).
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tos.brokeradapter.synthetic import SyntheticPaperTransport
from tos.canonical import CanonicalDecimal
from tos.engine import AttemptRequest, EgressResultPayload, InstrumentKey
from tos.ordering import OrderingEvent

from tos_runtime.operations.schema_ledger import (
    closing_on_failure,
    enable_wal_journal,
    open_or_create_schema,
)
from tos_runtime.recon.ports import WitnessUnavailable

__all__ = [
    "VENUE_LEDGER_FILE_NAME",
    "VENUE_LEDGER_SCHEMA_VERSION",
    "RecordingSyntheticTransport",
    "SyntheticVenueLedger",
    "VenueLedgerFill",
    "VenueLedgerReader",
    "VenueLedgerWriteFailed",
    "valid_trading_date",
]

#: The venue ledger's own file inside the data leaf — deliberately NOT
#: ``evidence.sqlite3``/``rcl.sqlite3`` (module docstring "Where it lives"). Not a backup-set
#: member yet: adding it to the cold backup is P3's own step, with its runbook row.
VENUE_LEDGER_FILE_NAME = "venue_ledger.sqlite3"

#: This store's schema version, in the shared ``schema_ledger`` discipline every other
#: runtime-owned sqlite store uses (``tos_runtime.operations.schema_ledger``). Deliberately NOT
#: registered in ``STORE_MIGRATIONS``/``MIGRATE_PATH_BY_STORE`` yet: those two are pinned equal
#: to each other (``tos/runtime/tests/compose/test_cli.py``) and the second lives under
#: ``compose/``, so registering the pair belongs with the P2 compose wiring that first gives this
#: store a real data-leaf path. A v1 store with no migrations needs no ``migrate`` run.
VENUE_LEDGER_SCHEMA_VERSION = 1

#: The one table. Rows cover every result the venue produced, not only fills — an ACK or a
#: REJECT is equally a thing the venue did, and leaving it out would make the ledger's silence
#: ambiguous.
_TABLE = "venue_results"

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    written_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_date TEXT NOT NULL,
    broker_execution_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    account TEXT NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT,
    quantity TEXT,
    filled_quantity TEXT,
    remaining_quantity TEXT,
    result_kind TEXT NOT NULL,
    UNIQUE (broker_execution_id)
)
"""

#: Append-only, mechanically — the same trigger discipline ``tos_runtime.evidence.store``'s own
#: ``entries`` table and ``schema_ledger`` itself already use. A venue's record of what it
#: executed is not editable after the fact.
_NO_UPDATE_TRIGGER_SQL = f"""
CREATE TRIGGER IF NOT EXISTS {_TABLE}_no_update
BEFORE UPDATE ON {_TABLE}
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime venue ledger: {_TABLE} is append-only — UPDATE forbidden');
END
"""

_NO_DELETE_TRIGGER_SQL = f"""
CREATE TRIGGER IF NOT EXISTS {_TABLE}_no_delete
BEFORE DELETE ON {_TABLE}
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime venue ledger: {_TABLE} is append-only — DELETE forbidden');
END
"""

#: The business columns, in the order every read and the conflict comparison below use them.
#: ``written_seq`` is excluded on purpose: it is this file's append order, not a fact about the
#: execution, so two byte-identical executions must not be told apart by it.
_ROW_COLUMNS: tuple[str, ...] = (
    "attempt_id",
    "broker_execution_id",
    "account",
    "instrument",
    "side",
    "quantity",
    "filled_quantity",
    "remaining_quantity",
    "result_kind",
    "trading_date",
)

#: The columns that say WHAT the venue executed, compared on a UNIQUE conflict to tell a
#: re-send of one execution from a different result claiming an identity the venue already used.
#: ``trading_date`` is excluded (review-1017 L1): it records WHEN this process observed the
#: execution, and the same attempt re-sent after a midnight boundary carries a later date while
#: being the same single execution. Treating that as a mismatch would refuse the very re-send
#: the single-shot contract requires to be answered with the unchanged result.
_EXECUTION_FACT_COLUMNS: tuple[str, ...] = tuple(
    column for column in _ROW_COLUMNS if column != "trading_date"
)

_SELECT_ROWS_SQL = f"SELECT {', '.join(_ROW_COLUMNS)}, written_seq FROM {_TABLE} ORDER BY written_seq ASC"

_DATE_SHAPE = re.compile(r"\d{8}")

#: Exactly ``0600`` — the venue ledger records what this deployment executed, and the custody
#: package already holds this repo's "exactly 0600, not merely no-more-permissive" convention
#: (``tos_runtime.custody.file_custody._REQUIRED_MODE``).
_FILE_MODE = 0o600


def valid_trading_date(value: object) -> bool:
    """Whether ``value`` is a real ``YYYYMMDD`` KST trading date token.

    Shape **and** calendar: ``"20261131"`` matches the shape and is not a date, so the
    ``strptime`` round trip is what actually decides. Mirrors
    ``tos_runtime.riskstate.held_position``'s own private check; this is the venue-ledger
    package's single copy, used by the writer and by the witness alike.

    Args:
        value: The candidate token.

    Returns:
        ``True`` iff ``value`` is an eight-digit string naming a real calendar date.
    """
    if not isinstance(value, str) or _DATE_SHAPE.fullmatch(value) is None:
        return False
    try:
        return datetime.strptime(value, "%Y%m%d").strftime("%Y%m%d") == value
    except ValueError:
        return False


class VenueLedgerWriteFailed(Exception):
    """The venue produced a result, but this process could not record it durably.

    Raised out of :meth:`RecordingSyntheticTransport.send_once` **instead of** returning the
    result. There is no new disposition behind it: the egress gateway catches every exception a
    transport raises and records ``SendHaltReason.TRANSPORT_RAISED``, whose own documented
    meaning is exactly this shape — the send may well have happened, the reservation stays
    POTENTIALLY_LIVE, the attempt stays consumed, nothing is resubmitted (module docstring).

    Deliberately NOT ``tos_runtime.transport.kis_mock.adapter.SendRefused``: that one means
    "refused BEFORE the wire, zero network". Here the venue already acted.
    """


@dataclass(frozen=True)
class VenueLedgerFill:
    """One recorded venue result, as read back (module docstring "Identity").

    ``quantity``/``filled_quantity``/``remaining_quantity`` are ``None`` when the recorded
    result carried none (an ACK, a REJECT, an UNKNOWN) — never a fabricated zero.
    """

    attempt_id: str
    broker_execution_id: str
    account: str
    instrument: str
    side: str | None
    quantity: Decimal | None
    filled_quantity: Decimal | None
    remaining_quantity: Decimal | None
    result_kind: str
    trading_date: str
    written_seq: int


def _create_venue_ledger_schema(conn: sqlite3.Connection, fresh: bool) -> None:
    """This store's own DDL, run inside ``open_or_create_schema``'s genesis transaction.

    ``fresh`` is unused: every statement is ``IF NOT EXISTS`` and none is genesis-only (unlike
    the evidence store's ``entries_kind_seq`` index).
    """
    del fresh
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute(_NO_UPDATE_TRIGGER_SQL)
    conn.execute(_NO_DELETE_TRIGGER_SQL)


def _decimal_text(value: Decimal | None) -> str | None:
    """A magnitude as the exact text the row stores, or ``None`` when there is none."""
    return None if value is None else str(value)


def _decimal_or_raise(value: object, *, column: str, seq: object) -> Decimal | None:
    """Decode a stored magnitude, or refuse the whole read (fail-closed).

    Raises:
        WitnessUnavailable: ``value`` is neither ``NULL`` nor a parseable decimal text — a row
            this reader cannot read is never silently dropped, because a dropped fill reads as a
            smaller net position than the venue actually holds.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise WitnessUnavailable(
            f"venue ledger row written_seq={seq!r}: {column} is {type(value).__name__}, "
            "not decimal text"
        )
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise WitnessUnavailable(
            f"venue ledger row written_seq={seq!r}: {column}={value!r} is not a decimal"
        ) from exc


def _required_text(value: object, *, column: str, seq: object) -> str:
    """A ``NOT NULL`` text column's value, or refuse the whole read (fail-closed)."""
    if not isinstance(value, str) or not value.strip():
        raise WitnessUnavailable(
            f"venue ledger row written_seq={seq!r}: {column}={value!r} is not a concrete token"
        )
    return value


class SyntheticVenueLedger:
    """The append-only synthetic venue ledger — one sqlite file, written at the send boundary.

    ``journal_mode=WAL``, ``synchronous=FULL``, mode ``0600``, mirroring every other
    runtime-owned durable store's transaction discipline
    (:class:`~tos_runtime.evidence.store.SqliteEvidenceStore`). Every write happens inside
    ``BEGIN IMMEDIATE`` ... ``COMMIT``.
    """

    def __init__(
        self,
        path: Path,
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        """Open (or create) the venue ledger at ``path``.

        Args:
            path: The sqlite file path. The parent directory must already exist (this module
                never creates directories — matches every other runtime-owned sqlite store).
            monotonic_ns: Injected monotonic-clock callable, for the schema-ledger genesis
                stamp only — never read directly.

        Raises:
            VenueLedgerWriteFailed: The file could not be created with mode ``0600`` (including
                a ``path`` that is a symlink — ``O_NOFOLLOW``), or sqlite refused to open it.
        """
        self.path = path
        self._create_file_0600(path)
        try:
            self._conn = sqlite3.connect(str(path), isolation_level=None)
        except (
            sqlite3.Error
        ) as exc:  # pragma: no cover - defensive, needs a broken file
            raise VenueLedgerWriteFailed(
                f"SyntheticVenueLedger: cannot open {path}: {exc}"
            ) from exc
        with closing_on_failure(self._conn):
            enable_wal_journal(self._conn)
            self._conn.execute("PRAGMA synchronous=FULL")
            open_or_create_schema(
                self._conn,
                store_name="venue_ledger",
                schema_version=VENUE_LEDGER_SCHEMA_VERSION,
                create_ddl=_create_venue_ledger_schema,
                shape_tables=(_TABLE,),
                monotonic_ns=monotonic_ns,
            )

    @staticmethod
    def _create_file_0600(path: Path) -> None:
        """Bring the file into existence with mode exactly ``0600`` before sqlite opens it.

        sqlite would create it at ``0644 & ~umask``, and its ``-wal``/``-shm`` siblings inherit
        the database file's permissions, so the mode has to be settled first. ``O_NOFOLLOW``
        refuses a symlink in place of the ledger; the explicit ``chmod`` makes the mode exact
        rather than umask-dependent, and also repairs a pre-existing file left more permissive.
        """
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, _FILE_MODE)
            os.close(fd)
            os.chmod(path, _FILE_MODE)
        except OSError as exc:
            raise VenueLedgerWriteFailed(
                f"SyntheticVenueLedger: cannot create {path} with mode 0600: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the underlying sqlite3 connection."""
        self._conn.close()

    def record(
        self,
        *,
        attempt_id: str,
        broker_execution_id: str | None,
        account: str,
        instrument: str,
        side: str | None,
        quantity: Decimal | None,
        filled_quantity: Decimal | None,
        remaining_quantity: Decimal | None,
        result_kind: str,
        trading_date: str,
    ) -> bool:
        """Append one venue result, or recognize it as already recorded.

        Args:
            attempt_id: The result's own attempt identity.
            broker_execution_id: The venue's execution identity — required. The kernel's
                synthetic transport stamps one on every result it produces, so ``None`` here
                means something other than that transport produced it, and a row without an
                identity could neither be deduplicated nor joined.
            account: The dispatch scope's account.
            instrument: The dispatch scope's instrument.
            side: The sealed outbound side token, recorded verbatim (never interpreted here —
                long/short symmetry; side is a policy-carried token).
            quantity: The authorized order quantity, if any.
            filled_quantity: The result's filled magnitude, if any.
            remaining_quantity: The result's remaining magnitude, if any.
            result_kind: The ``EgressResultKind`` token.
            trading_date: The KST trading date (``YYYYMMDD``) from trusted time. Recorded, and
                NOT part of the row's identity — a re-send across a midnight boundary is still
                the same single execution (review-1017 L1, module docstring).

        Returns:
            ``True`` when this call wrote the row; ``False`` when the same execution was already
            recorded, on this trading date or an earlier one (a re-send of the same
            deterministic attempt — module docstring).

        Raises:
            VenueLedgerWriteFailed: A field is not recordable, the execution identity is already
                held by a DIFFERENT recorded result, or sqlite refused the write.
        """
        values = self._validated_row(
            attempt_id=attempt_id,
            broker_execution_id=broker_execution_id,
            account=account,
            instrument=instrument,
            side=side,
            quantity=quantity,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            result_kind=result_kind,
            trading_date=trading_date,
        )
        placeholders = ", ".join("?" for _ in _ROW_COLUMNS)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    f"INSERT INTO {_TABLE} ({', '.join(_ROW_COLUMNS)}) "
                    f"VALUES ({placeholders})",
                    values,
                )
            except sqlite3.IntegrityError:
                self._conn.execute("ROLLBACK")
                return self._already_recorded(values)
            self._conn.execute("COMMIT")
        except sqlite3.Error as exc:
            raise VenueLedgerWriteFailed(
                f"SyntheticVenueLedger.record: {self.path} refused the write for "
                f"attempt {attempt_id!r}: {exc}"
            ) from exc
        return True

    @staticmethod
    def _validated_row(
        *,
        attempt_id: str,
        broker_execution_id: str | None,
        account: str,
        instrument: str,
        side: str | None,
        quantity: Decimal | None,
        filled_quantity: Decimal | None,
        remaining_quantity: Decimal | None,
        result_kind: str,
        trading_date: str,
    ) -> tuple[object, ...]:
        """The row tuple in :data:`_ROW_COLUMNS` order, or a typed refusal.

        Checked here rather than left to sqlite's own ``NOT NULL`` so a refusal names the field,
        and so the only ``IntegrityError`` :meth:`record` can see is the UNIQUE identity one.
        """
        required = {
            "attempt_id": attempt_id,
            "broker_execution_id": broker_execution_id,
            "account": account,
            "instrument": instrument,
            "result_kind": result_kind,
        }
        for name, value in required.items():
            if not isinstance(value, str) or not value.strip():
                raise VenueLedgerWriteFailed(
                    f"SyntheticVenueLedger.record: {name}={value!r} is not a concrete token — "
                    "a venue row without it could be neither deduplicated nor joined"
                )
        if not valid_trading_date(trading_date):
            raise VenueLedgerWriteFailed(
                f"SyntheticVenueLedger.record: trading_date={trading_date!r} is not a "
                "YYYYMMDD KST trading date — it is half of the witness's "
                "(broker_execution_id, order_date) cross-reference join key"
            )
        return (
            attempt_id,
            broker_execution_id,
            account,
            instrument,
            side,
            _decimal_text(quantity),
            _decimal_text(filled_quantity),
            _decimal_text(remaining_quantity),
            result_kind,
            trading_date,
        )

    def _already_recorded(self, values: tuple[object, ...]) -> bool:
        """Whether the colliding row reports the SAME execution as ``values`` (module docstring).

        Compared on :data:`_EXECUTION_FACT_COLUMNS` — every column except ``trading_date``. A row
        agreeing on all of them is the deterministic re-send, on this day or a later one: the
        venue holds ONE execution, so this reports "already there" and no second fill is created.
        A row that differs is not a re-send — it is a different result claiming an identity the
        venue has already used, which is the fail-closed refusal.

        Raises:
            VenueLedgerWriteFailed: The stored row reports a different execution, or it vanished
                between the conflict and this read.
        """
        execution_id = values[_ROW_COLUMNS.index("broker_execution_id")]
        facts = tuple(
            values[_ROW_COLUMNS.index(column)] for column in _EXECUTION_FACT_COLUMNS
        )
        row = self._conn.execute(
            f"SELECT {', '.join(_EXECUTION_FACT_COLUMNS)} FROM {_TABLE} "
            "WHERE broker_execution_id = ?",
            (execution_id,),
        ).fetchone()
        if row is None:  # pragma: no cover - UNIQUE fired, so the row exists
            raise VenueLedgerWriteFailed(
                "SyntheticVenueLedger.record: execution identity "
                f"{execution_id!r} collided but no row is readable"
            )
        if tuple(row) != facts:
            raise VenueLedgerWriteFailed(
                "SyntheticVenueLedger.record: execution identity "
                f"{execution_id!r} is already held by a DIFFERENT recorded "
                f"result {tuple(row)!r} — not a re-send of {facts!r}"
            )
        return False


class VenueLedgerReader:
    """Read-only access to a venue ledger file — the witness's only source (§3.2).

    Opens the file through sqlite's ``mode=ro`` URI, so this class is incapable of writing even
    if asked. It takes a path, never a :class:`SyntheticVenueLedger` and never an evidence
    store: the constructor signature is where the witness's independence claim is enforced.
    """

    def __init__(self, path: Path) -> None:
        """Bind this reader to the venue ledger file at ``path`` (opened per :meth:`fills`)."""
        self.path = path

    def fills(self) -> tuple[VenueLedgerFill, ...]:
        """Every recorded venue result, in append (``written_seq``) order.

        Returns:
            The decoded rows.

        Raises:
            WitnessUnavailable: The file is missing, locked, corrupt, or carries a row this
                reader cannot decode. Never an empty result standing in for a failed read —
                the shared fail-closed contract :class:`~tos_runtime.recon.ports.BrokerWitness`
                states for its own ``observe``.
        """
        try:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise WitnessUnavailable(
                f"venue ledger {self.path} cannot be opened read-only: {exc}"
            ) from exc
        try:
            raw_rows = conn.execute(_SELECT_ROWS_SQL).fetchall()
        except sqlite3.Error as exc:
            raise WitnessUnavailable(
                f"venue ledger {self.path} query failed: {exc}"
            ) from exc
        finally:
            conn.close()
        return tuple(_decode_row(row) for row in raw_rows)


def _decode_row(row: tuple[object, ...]) -> VenueLedgerFill:
    """Decode one ``_SELECT_ROWS_SQL`` row, refusing the whole read on anything malformed."""
    fields = dict(zip(_ROW_COLUMNS, row, strict=False))
    seq = row[-1]
    return VenueLedgerFill(
        attempt_id=_required_text(fields["attempt_id"], column="attempt_id", seq=seq),
        broker_execution_id=_required_text(
            fields["broker_execution_id"], column="broker_execution_id", seq=seq
        ),
        account=_required_text(fields["account"], column="account", seq=seq),
        instrument=_required_text(fields["instrument"], column="instrument", seq=seq),
        side=fields["side"] if isinstance(fields["side"], str) else None,
        quantity=_decimal_or_raise(fields["quantity"], column="quantity", seq=seq),
        filled_quantity=_decimal_or_raise(
            fields["filled_quantity"], column="filled_quantity", seq=seq
        ),
        remaining_quantity=_decimal_or_raise(
            fields["remaining_quantity"], column="remaining_quantity", seq=seq
        ),
        result_kind=_required_text(
            fields["result_kind"], column="result_kind", seq=seq
        ),
        trading_date=_trading_date_or_raise(fields["trading_date"], seq=seq),
        written_seq=seq if isinstance(seq, int) else -1,
    )


def _trading_date_or_raise(value: object, *, seq: object) -> str:
    """A row's trading date, or refuse the read — an undated row can never join (C-1)."""
    if not valid_trading_date(value):
        raise WitnessUnavailable(
            f"venue ledger row written_seq={seq!r}: trading_date={value!r} is not a "
            "YYYYMMDD trading date"
        )
    assert isinstance(value, str)  # narrowed by valid_trading_date
    return value


class RecordingSyntheticTransport:
    """The kernel synthetic transport, with the venue's own record written before it answers.

    Satisfies :class:`tos.brokeradapter.Transport` structurally, with the SAME single-shot
    signature: no retry count, no idempotency key, no second method — wrapping the kernel
    transport adds a durable write, never a resend.

    The wrapped transport is typed as the concrete
    :class:`~tos.brokeradapter.synthetic.SyntheticPaperTransport` rather than the ``Transport``
    Protocol on purpose: this ledger is the SYNTHETIC venue's record, and the witness over it
    declares ``independent_of_evidence_store=True``. Wrapping a transport that actually reaches
    a broker would make that record a fabrication of someone else's venue.
    """

    def __init__(
        self,
        inner: SyntheticPaperTransport,
        ledger: SyntheticVenueLedger,
        *,
        trading_date_now: Callable[[], str | None],
    ) -> None:
        """Bind the kernel transport, the venue ledger, and the trusted trading-date source.

        Args:
            inner: The kernel's synthetic paper transport — the thing that actually produces
                the result.
            ledger: The venue ledger every produced result is recorded into.
            trading_date_now: Returns the KST trading date (``YYYYMMDD``) at this instant, or
                ``None`` when it cannot be established. Required, never defaulted: the SAME
                injected reading the egress receipt's own ``trading_date`` comes from
                (``tos_runtime.compose.root``'s one ``trading_date_reader``), so the venue row
                and the receipt can never disagree about which day it is.

                ⚠ Unlike ``KisMockTransport._stamp_trading_date``, which degrades an
                unavailable date to ``None`` so the ACK still reaches the inbox, an unavailable
                date here is a write failure. There the BROKER is the independent record and an
                undated receipt merely cannot join; here the row IS the record, and an undated
                one carries no ``order_date`` for the witness's cross-reference join at all.
        """
        self._inner = inner
        self._ledger = ledger
        self._trading_date_now = trading_date_now

    @property
    def inner(self) -> SyntheticPaperTransport:
        """The wrapped kernel transport (its ``requests`` tuple is the send-count evidence)."""
        return self._inner

    def send_once(
        self,
        attempt: AttemptRequest,
        *,
        instrument_key: InstrumentKey,
        coordinates: tuple[tuple[str, str | None], ...],
        quantity: CanonicalDecimal | None = None,
        price: CanonicalDecimal | None = None,
        side: str | None = None,
        reference: OrderingEvent = OrderingEvent(),
        seal_digest: str | None = None,
    ) -> EgressResultPayload:
        """Transmit exactly once, record the venue row, then return the kernel's result.

        Args:
            attempt: The Coordinator's bound attempt request.
            instrument_key: The send's dispatch scope.
            coordinates: The opaque ordered egress coordinates.
            quantity: The authorized order quantity.
            price: The authorized order price.
            side: The authorized side token.
            reference: The event's causal-ordering coordinates.
            seal_digest: The sealed ``SendSeal.seal_digest``.

        Returns:
            The kernel transport's own :class:`~tos.engine.EgressResultPayload`, unchanged —
            including for a re-send the ledger recognized as already recorded (module
            docstring "Identity, and what a re-send does").

        Raises:
            VenueLedgerWriteFailed: The result could not be recorded. The result is NOT
                returned; the gateway's ``TRANSPORT_RAISED`` halt is the disposition.
        """
        result = self._inner.send_once(
            attempt,
            instrument_key=instrument_key,
            coordinates=coordinates,
            quantity=quantity,
            price=price,
            side=side,
            reference=reference,
            seal_digest=seal_digest,
        )
        self._ledger.record(
            attempt_id=result.attempt_id,
            broker_execution_id=result.broker_execution_id,
            account=instrument_key.account,
            instrument=instrument_key.instrument,
            side=side,
            quantity=quantity,
            filled_quantity=result.filled_quantity,
            remaining_quantity=result.remaining_quantity,
            result_kind=result.kind.value,
            trading_date=self._trading_date(),
        )
        return result

    def _trading_date(self) -> str:
        """The injected KST trading date, or a write refusal (constructor docstring).

        Raises:
            VenueLedgerWriteFailed: The source raised, or could not establish a date.
        """
        try:
            trading_date = self._trading_date_now()
        except Exception as exc:  # noqa: BLE001 - any failure is "no date", fail-closed
            raise VenueLedgerWriteFailed(
                f"RecordingSyntheticTransport: the trading-date source raised "
                f"{type(exc).__name__}: {exc} — the venue result cannot be recorded"
            ) from exc
        if not valid_trading_date(trading_date):
            raise VenueLedgerWriteFailed(
                f"RecordingSyntheticTransport: trading_date={trading_date!r} is not a "
                "YYYYMMDD KST trading date — the venue result cannot be recorded"
            )
        assert isinstance(trading_date, str)  # narrowed by valid_trading_date
        return trading_date
