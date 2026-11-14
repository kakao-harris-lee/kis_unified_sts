"""The synthetic venue ledger: the append-only record the synthetic venue never kept (§3.1)."""

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

VENUE_LEDGER_FILE_NAME = "venue_ledger.sqlite3"

VENUE_LEDGER_SCHEMA_VERSION = 1

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

_EXECUTION_FACT_COLUMNS: tuple[str, ...] = tuple(
    column for column in _ROW_COLUMNS if column != "trading_date"
)

_SELECT_ROWS_SQL = f"SELECT {', '.join(_ROW_COLUMNS)}, written_seq FROM {_TABLE} ORDER BY written_seq ASC"

_DATE_SHAPE = re.compile(r"\d{8}")

_FILE_MODE = 0o600


def valid_trading_date(value: object) -> bool:
    """Whether ``value`` is a real ``YYYYMMDD`` KST trading date token."""
    if not isinstance(value, str) or _DATE_SHAPE.fullmatch(value) is None:
        return False
    try:
        return datetime.strptime(value, "%Y%m%d").strftime("%Y%m%d") == value
    except ValueError:
        return False


class VenueLedgerWriteFailed(Exception):
    """The venue produced a result, but this process could not record it durably."""


@dataclass(frozen=True)
class VenueLedgerFill:
    """One recorded venue result, as read back (module docstring "Identity")."""

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
    """This store's own DDL, run inside ``open_or_create_schema``'s genesis transaction."""
    del fresh
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute(_NO_UPDATE_TRIGGER_SQL)
    conn.execute(_NO_DELETE_TRIGGER_SQL)


def _decimal_text(value: Decimal | None) -> str | None:
    """A magnitude as the exact text the row stores, or ``None`` when there is none."""
    return None if value is None else str(value)


def _decimal_or_raise(value: object, *, column: str, seq: object) -> Decimal | None:
    """Decode a stored magnitude, or refuse the whole read (fail-closed)."""
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
    """The append-only synthetic venue ledger — one sqlite file, written at the send boundary."""

    def __init__(
        self,
        path: Path,
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        """Open (or create) the venue ledger at ``path``."""
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
        """Bring the file into existence with mode exactly ``0600`` before sqlite opens it."""
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
        """Append one venue result, or recognize it as already recorded."""
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
        """The row tuple in :data:`_ROW_COLUMNS` order, or a typed refusal."""
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
        """Whether the colliding row reports the SAME execution as ``values`` (module docstring)."""
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
    """Read-only access to a venue ledger file — the witness's only source (§3.2)."""

    def __init__(self, path: Path) -> None:
        """Bind this reader to the venue ledger file at ``path`` (opened per :meth:`fills`)."""
        self.path = path

    def fills(self) -> tuple[VenueLedgerFill, ...]:
        """Every recorded venue result, in append (``written_seq``) order."""
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
    assert isinstance(value, str)
    return value


class RecordingSyntheticTransport:
    """The kernel synthetic transport, with the venue's own record written before it answers."""

    def __init__(
        self,
        inner: SyntheticPaperTransport,
        ledger: SyntheticVenueLedger,
        *,
        trading_date_now: Callable[[], str | None],
    ) -> None:
        """Bind the kernel transport, the venue ledger, and the trusted trading-date source."""
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
        """Transmit exactly once, record the venue row, then return the kernel's result."""
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
        """The injected KST trading date, or a write refusal (constructor docstring)."""
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
        assert isinstance(trading_date, str)
        return trading_date
