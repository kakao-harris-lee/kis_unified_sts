"""Order/fill/trade/event methods for RuntimeLedger."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .runtime_ledger_errors import RuntimeLedgerError
from .runtime_ledger_helpers import (
    _as_mapping,
    _coalesce,
    _hold_seconds,
    _json_payload,
    _pnl,
    _pnl_pct,
    _record_id,
    _resolve_track_id,
    _utc_now_iso,
)


class RuntimeLedgerRecordMixin:
    def record_order(
        self, order: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
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
            _resolve_track_id(data, track_id),
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
                    client_order_id, track_id, created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    status = excluded.status,
                    broker_order_id = excluded.broker_order_id,
                    track_id = COALESCE(excluded.track_id, track_id),
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return record_id

    def record_fill(
        self, fill: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
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
            _resolve_track_id(data, track_id),
            _json_payload(data),
        )
        with self._lock:
            self._require_conn().execute(
                """
                INSERT INTO fills (
                    id, idempotency_key, order_id, asset_class, symbol, side,
                    quantity, price, filled_at, broker_fill_id, venue, track_id,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    quantity = excluded.quantity,
                    price = excluded.price,
                    filled_at = excluded.filled_at,
                    track_id = COALESCE(excluded.track_id, track_id),
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return record_id

    def record_trade(
        self, trade: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
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
            _resolve_track_id(data, track_id),
            _json_payload(data),
        )
        with self._lock:
            self._require_conn().execute(
                """
                INSERT INTO trades (
                    id, idempotency_key, asset_class, symbol, name, side,
                    strategy, entry_time, entry_price, exit_time, exit_price,
                    quantity, pnl, pnl_pct, hold_seconds, exit_reason, track_id,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    exit_time = excluded.exit_time,
                    exit_price = excluded.exit_price,
                    pnl = excluded.pnl,
                    pnl_pct = excluded.pnl_pct,
                    hold_seconds = excluded.hold_seconds,
                    exit_reason = excluded.exit_reason,
                    track_id = COALESCE(excluded.track_id, track_id),
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

    def record_signal_decision(
        self, decision: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
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
                "track_id",
                "created_at",
            ),
            values=(
                _coalesce(data, "signal_id"),
                _coalesce(data, "asset_class"),
                _coalesce(data, "symbol", "code"),
                _coalesce(data, "strategy"),
                _coalesce(data, "decision", "status"),
                _resolve_track_id(data, track_id),
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
            # track_id must survive an untagged upsert retry (NULL never
            # overwrites an existing tag).
            (
                f"{column} = COALESCE(excluded.{column}, {column})"
                if column == "track_id"
                else f"{column} = excluded.{column}"
            )
            for column in (*columns, "payload_json")
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

    def query_position_snapshots_daily(
        self,
        asset_class: str | None = None,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Latest snapshot per (position_id, day) for exposure-over-time charts.

        Groups by position_id AND snapshot day, taking the max row_id in each
        day (so a position contributes one row per day it was live). Read-only.
        """
        sql = """
            SELECT ps.*
            FROM position_snapshots ps
            JOIN (
                SELECT position_id, substr(snapshot_time, 1, 10) AS day,
                       MAX(row_id) AS row_id
                FROM position_snapshots
                GROUP BY position_id, substr(snapshot_time, 1, 10)
            ) latest
              ON ps.position_id = latest.position_id
             AND ps.row_id = latest.row_id
            WHERE 1=1
        """
        params: list[Any] = []
        if asset_class:
            sql += " AND ps.asset_class = ?"
            params.append(asset_class)
        if start:
            sql += " AND substr(ps.snapshot_time, 1, 10) >= ?"
            params.append(start)
        if end:
            sql += " AND substr(ps.snapshot_time, 1, 10) <= ?"
            params.append(end)
        sql += " ORDER BY ps.snapshot_time ASC, ps.position_id ASC"
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
            ("track_id", ("track_id", "track")),
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

    def query_fills(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        sql = "SELECT * FROM fills WHERE 1=1"
        params: list[Any] = []

        for field, keys in (
            ("asset_class", ("asset_class",)),
            ("symbol", ("symbol", "code")),
            ("side", ("side",)),
            ("order_id", ("order_id",)),
            ("track_id", ("track_id", "track")),
        ):
            value = _coalesce(filters, *keys)
            if value is not None:
                sql += f" AND {field} = ?"
                params.append(value)

        if start := _coalesce(filters, "start", "start_time", "from"):
            sql += " AND filled_at >= ?"
            params.append(start)
        if end := _coalesce(filters, "end", "end_time", "to"):
            sql += " AND filled_at <= ?"
            params.append(end)

        sql += " ORDER BY filled_at DESC, id DESC"
        limit = int(_coalesce(filters, "limit", default=100))
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]
