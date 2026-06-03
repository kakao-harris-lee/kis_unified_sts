"""Runtime ledger interface and SQLite implementation.

The ledger stores durable operational records that must survive process
restart: orders, fills, trades, position snapshots, risk events, signal
decisions, and market context history. SQLite is the default runtime backend;
ClickHouse mirror/backends can be added behind this interface without keeping
ClickHouse on the hot path.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from shared.storage.config import SQLiteStorageConfig


class RuntimeLedgerError(RuntimeError):
    """Raised when runtime ledger operations fail."""


class RuntimeLedger(Protocol):
    """Durable runtime ledger contract."""

    def record_order(self, order: Mapping[str, Any] | Any) -> str:
        """Record an order submission/router decision and return record id."""
        ...

    def record_fill(self, fill: Mapping[str, Any] | Any) -> str:
        """Record a broker/mock fill and return record id."""
        ...

    def record_trade(self, trade: Mapping[str, Any] | Any) -> str:
        """Record a closed trade summary and return record id."""
        ...

    def record_position_snapshot(self, snapshot: Mapping[str, Any] | Any) -> int:
        """Record an open/closed position state snapshot and return row id."""
        ...

    def record_risk_event(self, event: Mapping[str, Any] | Any) -> str:
        """Record an operational risk/audit event and return record id."""
        ...

    def record_signal_decision(self, decision: Mapping[str, Any] | Any) -> str:
        """Record generated/filtered/vetoed signal history and return record id."""
        ...

    def record_market_context(self, context: Mapping[str, Any] | Any) -> str:
        """Record an LLM/market context snapshot and return record id."""
        ...

    def load_open_positions(
        self, asset_class: str | None = None
    ) -> list[dict[str, Any]]:
        """Load latest open position snapshots."""
        ...

    def query_trades(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Query closed trades by common filters."""
        ...

    def flush(self) -> None:
        """Flush pending writes."""
        ...

    def close(self) -> None:
        """Close the ledger backend."""
        ...


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _value(value: Any) -> Any:
    """Convert common runtime values to SQLite/JSON-friendly values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return _value(value)


def _as_mapping(record: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        data = dict(record)
    elif is_dataclass(record) and not isinstance(record, type):
        data = asdict(record)
    elif hasattr(record, "model_dump"):
        data = record.model_dump()
    else:
        data = {
            key: getattr(record, key)
            for key in dir(record)
            if not key.startswith("_") and not callable(getattr(record, key))
        }

    safe_data = _json_safe(data)
    if not isinstance(safe_data, dict):
        return {}
    data = safe_data

    # Preserve common computed properties from Position-like objects.
    for attr in ("profit_pct", "profit_rate", "unrealized_pnl"):
        if attr not in data and hasattr(record, attr):
            with suppress(Exception):
                data[attr] = _json_safe(getattr(record, attr))
    return data


def _coalesce(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return default


def _record_id(data: Mapping[str, Any], prefix: str, *keys: str) -> str:
    value = _coalesce(data, "id", *keys)
    if value is not None:
        return str(value)
    return f"{prefix}_{uuid.uuid4().hex}"


def _json_payload(data: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe(data), ensure_ascii=False, sort_keys=True)


def _pnl(data: Mapping[str, Any]) -> float | None:
    value = _coalesce(data, "pnl", "realized_pnl", "unrealized_pnl")
    if value is not None:
        return float(value)

    entry_price = _coalesce(data, "entry_price")
    exit_price = _coalesce(data, "exit_price")
    quantity = _coalesce(data, "quantity")
    if entry_price is None or exit_price is None or quantity is None:
        return None

    side = str(_coalesce(data, "side", default="long")).lower()
    if side == "short":
        return (float(entry_price) - float(exit_price)) * int(quantity)
    return (float(exit_price) - float(entry_price)) * int(quantity)


def _pnl_pct(data: Mapping[str, Any], pnl: float | None) -> float | None:
    value = _coalesce(data, "pnl_pct", "profit_pct")
    if value is not None:
        return float(value)
    if pnl is None:
        return None
    entry_price = _coalesce(data, "entry_price")
    quantity = _coalesce(data, "quantity")
    if entry_price is None or quantity is None:
        return None
    notional = max(float(entry_price) * int(quantity), 1e-9)
    return (pnl / notional) * 100.0


def _hold_seconds(data: Mapping[str, Any]) -> int | None:
    value = _coalesce(data, "hold_seconds", "hold_duration_seconds")
    if value is not None:
        return int(float(value))

    entry_time = _coalesce(data, "entry_time", "entry_date")
    exit_time = _coalesce(data, "exit_time", "exit_date")
    if not isinstance(entry_time, str) or not isinstance(exit_time, str):
        return None
    try:
        entry = datetime.fromisoformat(entry_time)
        exit_ = datetime.fromisoformat(exit_time)
    except ValueError:
        return None
    return max(int((exit_ - entry).total_seconds()), 0)


class SQLiteRuntimeLedger:
    """SQLite WAL runtime ledger implementation."""

    SCHEMA_VERSION = "1"

    def __init__(self, path: str | Path | SQLiteStorageConfig):
        if isinstance(path, SQLiteStorageConfig):
            self.config = path
            self.path = Path(path.path)
        else:
            self.path = Path(path)
            self.config = SQLiteStorageConfig(path=str(self.path))

        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._connect()

    def _connect(self) -> None:
        try:
            if self.path.exists() and self.path.is_dir():
                raise RuntimeLedgerError(
                    f"SQLite ledger path is a directory: {self.path}"
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            self._initialize_connection()
            self._migrate()
        except RuntimeLedgerError:
            raise
        except Exception as exc:
            raise RuntimeLedgerError(
                f"Failed to open SQLite runtime ledger at {self.path}: {exc}"
            ) from exc

    def _initialize_connection(self) -> None:
        conn = self._require_conn()
        conn.execute(f"PRAGMA busy_timeout={self.config.busy_timeout_ms}")
        conn.execute("PRAGMA foreign_keys=ON")
        if self.config.wal:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA synchronous={self.config.synchronous}")

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeLedgerError("SQLite runtime ledger is closed")
        return self._conn

    def _migrate(self) -> None:
        with self._lock:
            conn = self._require_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ledger_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    asset_class TEXT,
                    symbol TEXT,
                    side TEXT,
                    order_type TEXT,
                    quantity INTEGER,
                    price REAL,
                    status TEXT,
                    strategy TEXT,
                    broker_order_id TEXT,
                    client_order_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    order_id TEXT,
                    asset_class TEXT,
                    symbol TEXT,
                    side TEXT,
                    quantity INTEGER,
                    price REAL,
                    filled_at TEXT NOT NULL,
                    broker_fill_id TEXT,
                    venue TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    asset_class TEXT,
                    symbol TEXT,
                    name TEXT,
                    side TEXT,
                    strategy TEXT,
                    entry_time TEXT,
                    entry_price REAL,
                    exit_time TEXT,
                    exit_price REAL,
                    quantity INTEGER,
                    pnl REAL,
                    pnl_pct REAL,
                    hold_seconds INTEGER,
                    exit_reason TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS position_snapshots (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT UNIQUE,
                    position_id TEXT NOT NULL,
                    asset_class TEXT,
                    symbol TEXT,
                    name TEXT,
                    side TEXT,
                    strategy TEXT,
                    quantity INTEGER,
                    entry_time TEXT,
                    entry_price REAL,
                    current_price REAL,
                    high_since_entry REAL,
                    low_since_entry REAL,
                    stop_price REAL,
                    state TEXT,
                    is_open INTEGER NOT NULL,
                    exit_time TEXT,
                    exit_price REAL,
                    exit_reason TEXT,
                    pnl REAL,
                    snapshot_time TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_position_snapshots_latest
                    ON position_snapshots(position_id, row_id);
                CREATE INDEX IF NOT EXISTS idx_position_snapshots_asset_open
                    ON position_snapshots(asset_class, is_open);
                CREATE INDEX IF NOT EXISTS idx_trades_query
                    ON trades(asset_class, symbol, strategy, exit_time);

                CREATE TABLE IF NOT EXISTS risk_events (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    event_type TEXT,
                    asset_class TEXT,
                    severity TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS signal_decisions (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    signal_id TEXT,
                    asset_class TEXT,
                    symbol TEXT,
                    strategy TEXT,
                    decision TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_context_history (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    asset_class TEXT,
                    symbol TEXT,
                    context_type TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """)
            self._upsert_metadata("schema_version", self.SCHEMA_VERSION)
            self._upsert_metadata("ledger_path", str(self.path))

    def _upsert_metadata(self, key: str, value: str) -> None:
        self._require_conn().execute(
            """
            INSERT INTO ledger_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, _utc_now_iso()),
        )

    def record_order(self, order: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(order)
        record_id = _record_id(data, "order", "order_id", "client_order_id")
        now = _utc_now_iso()
        params = (
            record_id,
            _coalesce(data, "idempotency_key", "client_order_id", default=record_id),
            _coalesce(data, "asset_class"),
            _coalesce(data, "symbol", "code"),
            _coalesce(data, "side"),
            _coalesce(data, "order_type", "type"),
            _coalesce(data, "quantity"),
            _coalesce(data, "price"),
            _coalesce(data, "status", default="submitted"),
            _coalesce(data, "strategy"),
            _coalesce(data, "broker_order_id", "order_no"),
            _coalesce(data, "client_order_id"),
            _coalesce(data, "created_at", "timestamp", default=now),
            now,
            _json_payload(data),
        )
        with self._lock:
            self._require_conn().execute(
                """
                INSERT INTO orders (
                    id, idempotency_key, asset_class, symbol, side, order_type,
                    quantity, price, status, strategy, broker_order_id,
                    client_order_id, created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    status = excluded.status,
                    broker_order_id = excluded.broker_order_id,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return record_id

    def record_fill(self, fill: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(fill)
        record_id = _record_id(data, "fill", "fill_id", "broker_fill_id")
        params = (
            record_id,
            _coalesce(
                data, "idempotency_key", "fill_id", "broker_fill_id", default=record_id
            ),
            _coalesce(data, "order_id", "order_no", "broker_order_id"),
            _coalesce(data, "asset_class"),
            _coalesce(data, "symbol", "code"),
            _coalesce(data, "side"),
            _coalesce(data, "quantity", "filled_qty"),
            _coalesce(data, "price", "filled_price"),
            _coalesce(data, "filled_at", "timestamp", default=_utc_now_iso()),
            _coalesce(data, "broker_fill_id", "fill_id"),
            _coalesce(data, "venue", "execution_venue"),
            _json_payload(data),
        )
        with self._lock:
            self._require_conn().execute(
                """
                INSERT INTO fills (
                    id, idempotency_key, order_id, asset_class, symbol, side,
                    quantity, price, filled_at, broker_fill_id, venue, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    quantity = excluded.quantity,
                    price = excluded.price,
                    filled_at = excluded.filled_at,
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return record_id

    def record_trade(self, trade: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(trade)
        record_id = _record_id(data, "trade", "trade_id", "position_id")
        pnl = _pnl(data)
        params = (
            record_id,
            _coalesce(
                data, "idempotency_key", "trade_id", "position_id", default=record_id
            ),
            _coalesce(data, "asset_class"),
            _coalesce(data, "symbol", "code"),
            _coalesce(data, "name"),
            _coalesce(data, "side"),
            _coalesce(data, "strategy"),
            _coalesce(data, "entry_time", "entry_date"),
            _coalesce(data, "entry_price"),
            _coalesce(data, "exit_time", "exit_date"),
            _coalesce(data, "exit_price"),
            _coalesce(data, "quantity"),
            pnl,
            _pnl_pct(data, pnl),
            _hold_seconds(data),
            _coalesce(data, "exit_reason", "reason"),
            _json_payload(data),
        )
        with self._lock:
            self._require_conn().execute(
                """
                INSERT INTO trades (
                    id, idempotency_key, asset_class, symbol, name, side,
                    strategy, entry_time, entry_price, exit_time, exit_price,
                    quantity, pnl, pnl_pct, hold_seconds, exit_reason, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    exit_time = excluded.exit_time,
                    exit_price = excluded.exit_price,
                    pnl = excluded.pnl,
                    pnl_pct = excluded.pnl_pct,
                    hold_seconds = excluded.hold_seconds,
                    exit_reason = excluded.exit_reason,
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return record_id

    def record_position_snapshot(self, snapshot: Mapping[str, Any] | Any) -> int:
        data = _as_mapping(snapshot)
        position_id = str(_coalesce(data, "position_id", "id"))
        if not position_id or position_id == "None":
            raise RuntimeLedgerError("position snapshot requires position_id or id")

        is_open = _coalesce(data, "is_open")
        if is_open is None:
            is_open = 0 if _coalesce(data, "exit_time", "exit_date") else 1
        pnl = _pnl(data)
        snapshot_time = _coalesce(
            data, "snapshot_time", "updated_at", default=_utc_now_iso()
        )
        params = (
            _coalesce(data, "idempotency_key"),
            position_id,
            _coalesce(data, "asset_class"),
            _coalesce(data, "symbol", "code"),
            _coalesce(data, "name"),
            _coalesce(data, "side"),
            _coalesce(data, "strategy"),
            _coalesce(data, "quantity"),
            _coalesce(data, "entry_time", "entry_date"),
            _coalesce(data, "entry_price"),
            _coalesce(data, "current_price"),
            _coalesce(data, "high_since_entry", "highest_price"),
            _coalesce(data, "low_since_entry", "lowest_price"),
            _coalesce(data, "stop_price", "stop_loss_price"),
            _coalesce(data, "state", "current_state"),
            int(bool(is_open)),
            _coalesce(data, "exit_time", "exit_date"),
            _coalesce(data, "exit_price"),
            _coalesce(data, "exit_reason"),
            pnl,
            snapshot_time,
            _json_payload(data),
        )
        with self._lock:
            cur = self._require_conn().execute(
                """
                INSERT INTO position_snapshots (
                    idempotency_key, position_id, asset_class, symbol, name,
                    side, strategy, quantity, entry_time, entry_price,
                    current_price, high_since_entry, low_since_entry, stop_price,
                    state, is_open, exit_time, exit_price, exit_reason, pnl,
                    snapshot_time, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    current_price = excluded.current_price,
                    high_since_entry = excluded.high_since_entry,
                    low_since_entry = excluded.low_since_entry,
                    stop_price = excluded.stop_price,
                    state = excluded.state,
                    is_open = excluded.is_open,
                    exit_time = excluded.exit_time,
                    exit_price = excluded.exit_price,
                    exit_reason = excluded.exit_reason,
                    pnl = excluded.pnl,
                    snapshot_time = excluded.snapshot_time,
                    payload_json = excluded.payload_json
                """,
                params,
            )
            return int(cur.lastrowid or 0)

    def record_risk_event(self, event: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(event)
        return self._record_event_table(
            table="risk_events",
            record_id=_record_id(data, "risk", "event_id"),
            idempotency_key=_coalesce(data, "idempotency_key", "event_id"),
            columns=("event_type", "asset_class", "severity", "created_at"),
            values=(
                _coalesce(data, "event_type", "type"),
                _coalesce(data, "asset_class"),
                _coalesce(data, "severity", default="info"),
                _coalesce(data, "created_at", "timestamp", default=_utc_now_iso()),
            ),
            data=data,
        )

    def record_signal_decision(self, decision: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(decision)
        return self._record_event_table(
            table="signal_decisions",
            record_id=_record_id(data, "signal_decision", "decision_id", "signal_id"),
            idempotency_key=_coalesce(data, "idempotency_key", "decision_id"),
            columns=(
                "signal_id",
                "asset_class",
                "symbol",
                "strategy",
                "decision",
                "created_at",
            ),
            values=(
                _coalesce(data, "signal_id"),
                _coalesce(data, "asset_class"),
                _coalesce(data, "symbol", "code"),
                _coalesce(data, "strategy"),
                _coalesce(data, "decision", "status"),
                _coalesce(data, "created_at", "timestamp", default=_utc_now_iso()),
            ),
            data=data,
        )

    def record_market_context(self, context: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(context)
        return self._record_event_table(
            table="market_context_history",
            record_id=_record_id(data, "market_context", "context_id"),
            idempotency_key=_coalesce(data, "idempotency_key", "context_id"),
            columns=("asset_class", "symbol", "context_type", "created_at"),
            values=(
                _coalesce(data, "asset_class"),
                _coalesce(data, "symbol", "code"),
                _coalesce(data, "context_type", "type"),
                _coalesce(data, "created_at", "timestamp", default=_utc_now_iso()),
            ),
            data=data,
        )

    def _record_event_table(
        self,
        *,
        table: str,
        record_id: str,
        idempotency_key: Any,
        columns: tuple[str, ...],
        values: tuple[Any, ...],
        data: Mapping[str, Any],
    ) -> str:
        all_columns = ("id", "idempotency_key", *columns, "payload_json")
        placeholders = ", ".join("?" for _ in all_columns)
        updates = ", ".join(
            f"{column} = excluded.{column}" for column in (*columns, "payload_json")
        )
        with self._lock:
            self._require_conn().execute(
                f"""
                INSERT INTO {table} ({", ".join(all_columns)})
                VALUES ({placeholders})
                ON CONFLICT(idempotency_key) DO UPDATE SET {updates}
                """,
                (record_id, idempotency_key or record_id, *values, _json_payload(data)),
            )
        return record_id

    def load_open_positions(
        self, asset_class: str | None = None
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT ps.*
            FROM position_snapshots ps
            JOIN (
                SELECT position_id, MAX(row_id) AS row_id
                FROM position_snapshots
                GROUP BY position_id
            ) latest
              ON ps.position_id = latest.position_id
             AND ps.row_id = latest.row_id
            WHERE ps.is_open = 1
        """
        params: list[Any] = []
        if asset_class:
            sql += " AND ps.asset_class = ?"
            params.append(asset_class)
        sql += " ORDER BY ps.entry_time ASC, ps.position_id ASC"
        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def query_trades(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        sql = "SELECT * FROM trades WHERE 1=1"
        params: list[Any] = []

        for field, keys in (
            ("asset_class", ("asset_class",)),
            ("symbol", ("symbol", "code")),
            ("strategy", ("strategy",)),
            ("side", ("side",)),
        ):
            value = _coalesce(filters, *keys)
            if value is not None:
                sql += f" AND {field} = ?"
                params.append(value)

        if start := _coalesce(filters, "start", "start_time", "from"):
            sql += " AND exit_time >= ?"
            params.append(start)
        if end := _coalesce(filters, "end", "end_time", "to"):
            sql += " AND exit_time <= ?"
            params.append(end)

        sql += " ORDER BY exit_time DESC, id DESC"
        limit = int(_coalesce(filters, "limit", default=500))
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def flush(self) -> None:
        with self._lock:
            self._require_conn().commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.commit()
                self._conn.close()
                self._conn = None

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        payload = data.get("payload_json")
        if isinstance(payload, str):
            try:
                data["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                data["payload"] = {}
        return data

    def __enter__(self) -> SQLiteRuntimeLedger:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
