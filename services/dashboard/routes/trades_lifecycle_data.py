"""Trades lifecycle row loading helpers."""

from __future__ import annotations

import json
from typing import Any

from services.dashboard.domain.assets import target_assets
from services.dashboard.routes.trades_data import _get_reader, _get_runtime_ledger
from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger

_LIFECYCLE_TABLE_ORDER = {
    "trades": "exit_time DESC, id DESC",
    "fills": "filled_at DESC, id DESC",
    "orders": "updated_at DESC, created_at DESC, id DESC",
    "signal_decisions": "created_at DESC, id DESC",
    "position_snapshots": "row_id DESC",
}

_LIFECYCLE_FILTER_COLUMNS = {
    "trades": {"id", "asset_class", "symbol", "strategy", "side"},
    "fills": {"id", "order_id", "asset_class", "symbol", "side", "broker_fill_id"},
    "orders": {
        "id",
        "asset_class",
        "symbol",
        "side",
        "strategy",
        "broker_order_id",
        "client_order_id",
    },
    "signal_decisions": {"id", "signal_id", "asset_class", "symbol", "strategy"},
    "position_snapshots": {"position_id", "asset_class", "symbol", "strategy"},
}

_LIFECYCLE_ROW_ID_KEYS = {
    "trades": ("id", "trade_id"),
    "fills": ("id", "fill_id", "broker_fill_id"),
    "orders": ("id", "order_id", "client_order_id", "broker_order_id"),
    "signals": ("id", "signal_id"),
    "positions": ("row_id", "position_id", "id"),
}


def _empty_lifecycle_rows() -> dict[str, list[dict]]:
    return {
        "trades": [],
        "fills": [],
        "orders": [],
        "signals": [],
        "positions": [],
    }


def _with_source(row: dict, source: str) -> dict:
    data = dict(row)
    data["__source"] = source
    return data


def _row_payload(row: dict | None) -> dict:
    if not row:
        return {}
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else {}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_value(row: dict | None, *keys: str) -> Any:
    if not row:
        return None
    payload = _row_payload(row)
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return None


def _row_text(row: dict | None, *keys: str) -> str | None:
    return _clean_text(_row_value(row, *keys))


def _lifecycle_row_identity(kind: str, row: dict) -> str:
    for key in _LIFECYCLE_ROW_ID_KEYS[kind]:
        value = _row_value(row, key)
        if value is not None and value != "":
            return f"{kind}:{key}:{value}"
    return f"{kind}:raw:{json.dumps(row, sort_keys=True, default=str)}"


def _append_lifecycle_rows(
    rows: dict[str, list[dict]],
    kind: str,
    new_rows: list[dict],
) -> bool:
    existing = {_lifecycle_row_identity(kind, row) for row in rows[kind]}
    added = False
    for row in new_rows:
        enriched = _with_source(row, "runtime_ledger")
        identity = _lifecycle_row_identity(kind, enriched)
        if identity in existing:
            continue
        rows[kind].append(enriched)
        existing.add(identity)
        added = True
    return added


def _maybe_set_lookup(lookup: dict[str, str | None], key: str, value: Any) -> None:
    if lookup.get(key) is None:
        lookup[key] = _clean_text(value)


def _derive_lifecycle_lookup(
    rows: dict[str, list[dict]],
    *,
    signal_id: str | None,
    order_id: str | None,
    fill_id: str | None,
    trade_id: str | None,
    position_id: str | None = None,
    symbol: str | None = None,
) -> dict[str, str | None]:
    lookup: dict[str, str | None] = {
        "signal_id": _clean_text(signal_id),
        "order_id": _clean_text(order_id),
        "fill_id": _clean_text(fill_id),
        "trade_id": _clean_text(trade_id),
        "position_id": _clean_text(position_id),
        "symbol": _clean_text(symbol),
    }
    for trade in rows["trades"]:
        _maybe_set_lookup(lookup, "trade_id", _row_value(trade, "id", "trade_id"))
        _maybe_set_lookup(lookup, "position_id", _row_value(trade, "position_id"))
        _maybe_set_lookup(lookup, "signal_id", _row_value(trade, "signal_id"))
        _maybe_set_lookup(
            lookup, "order_id", _row_value(trade, "order_id", "entry_order_id")
        )
        _maybe_set_lookup(
            lookup, "fill_id", _row_value(trade, "fill_id", "entry_fill_id")
        )
        _maybe_set_lookup(lookup, "symbol", _row_value(trade, "symbol", "code"))
    for fill in rows["fills"]:
        _maybe_set_lookup(
            lookup, "fill_id", _row_value(fill, "id", "fill_id", "broker_fill_id")
        )
        _maybe_set_lookup(lookup, "order_id", _row_value(fill, "order_id"))
        _maybe_set_lookup(lookup, "signal_id", _row_value(fill, "signal_id"))
        _maybe_set_lookup(lookup, "symbol", _row_value(fill, "symbol", "code"))
    for order in rows["orders"]:
        _maybe_set_lookup(
            lookup,
            "order_id",
            _row_value(order, "id", "order_id", "client_order_id", "broker_order_id"),
        )
        _maybe_set_lookup(lookup, "signal_id", _row_value(order, "signal_id"))
        _maybe_set_lookup(lookup, "symbol", _row_value(order, "symbol", "code"))
    for signal in rows["signals"]:
        _maybe_set_lookup(lookup, "signal_id", _row_value(signal, "signal_id", "id"))
        _maybe_set_lookup(lookup, "symbol", _row_value(signal, "symbol", "code"))
    for position in rows["positions"]:
        _maybe_set_lookup(
            lookup, "position_id", _row_value(position, "position_id", "id")
        )
        _maybe_set_lookup(lookup, "trade_id", _row_value(position, "trade_id"))
        _maybe_set_lookup(lookup, "symbol", _row_value(position, "symbol", "code"))
    return lookup


def _has_lifecycle_lookup(lookup: dict[str, str | None]) -> bool:
    return any(_clean_text(value) for value in lookup.values())


def _sqlite_row_to_dict(row: Any) -> dict:
    data = dict(row)
    payload_json = data.get("payload_json")
    if isinstance(payload_json, str):
        try:
            data["payload"] = json.loads(payload_json)
        except json.JSONDecodeError:
            data["payload"] = {}
    return data


def _query_lifecycle_table(
    ledger: SQLiteRuntimeLedger,
    table: str,
    *,
    asset_class: str,
    symbol: str | None = None,
    exact_filters: tuple[tuple[str, str | None], ...] = (),
    payload_filters: tuple[str | None, ...] = (),
    limit: int,
) -> list[dict]:
    """Query a whitelisted RuntimeLedger table for lifecycle evidence."""
    order_by = _LIFECYCLE_TABLE_ORDER.get(table)
    if order_by is None:
        return []
    allowed_columns = _LIFECYCLE_FILTER_COLUMNS.get(table, set())

    sql = f"SELECT * FROM {table} WHERE 1=1"
    params: list[Any] = []
    targets = target_assets(asset_class)
    if targets:
        placeholders = ", ".join("?" for _ in targets)
        sql += f" AND asset_class IN ({placeholders})"
        params.extend(targets)
    if symbol:
        sql += " AND symbol = ?"
        params.append(symbol)
    match_clauses: list[str] = []
    match_params: list[Any] = []
    for column, value in exact_filters:
        text = _clean_text(value)
        if not text or column not in allowed_columns:
            continue
        match_clauses.append(f"{column} = ?")
        match_params.append(text)
    for value in payload_filters:
        text = _clean_text(value)
        if not text:
            continue
        match_clauses.append("payload_json LIKE ?")
        match_params.append(f"%{text}%")
    if match_clauses:
        sql += f" AND ({' OR '.join(match_clauses)})"
        params.extend(match_params)
    sql += f" ORDER BY {order_by} LIMIT ?"
    params.append(limit)

    rows = ledger._require_conn().execute(sql, params).fetchall()  # noqa: SLF001
    return [_sqlite_row_to_dict(row) for row in rows]


def _query_lifecycle_batch(
    ledger: SQLiteRuntimeLedger,
    rows: dict[str, list[dict]],
    *,
    asset_class: str,
    lookup: dict[str, str | None],
    broad: bool = False,
    allow_symbol_lookup: bool = True,
    limit: int,
) -> bool:
    table_map = (
        ("trades", "trades"),
        ("fills", "fills"),
        ("orders", "orders"),
        ("signal_decisions", "signals"),
        ("position_snapshots", "positions"),
    )
    exact_by_table: dict[str, tuple[tuple[str, str | None], ...]] = {
        "trades": (("id", lookup.get("trade_id")),),
        "fills": (
            ("id", lookup.get("fill_id")),
            ("broker_fill_id", lookup.get("fill_id")),
            ("order_id", lookup.get("order_id")),
        ),
        "orders": (
            ("id", lookup.get("order_id")),
            ("client_order_id", lookup.get("order_id")),
            ("broker_order_id", lookup.get("order_id")),
        ),
        "signal_decisions": (
            ("id", lookup.get("signal_id")),
            ("signal_id", lookup.get("signal_id")),
        ),
        "position_snapshots": (("position_id", lookup.get("position_id")),),
    }
    payload_by_table: dict[str, tuple[str | None, ...]] = {
        "trades": (
            lookup.get("signal_id"),
            lookup.get("order_id"),
            lookup.get("fill_id"),
            lookup.get("position_id"),
        ),
        "fills": (lookup.get("signal_id"),),
        "orders": (lookup.get("signal_id"),),
        "signal_decisions": (lookup.get("order_id"),),
        "position_snapshots": (
            lookup.get("trade_id"),
            lookup.get("signal_id"),
            lookup.get("order_id"),
            lookup.get("fill_id"),
        ),
    }

    added = False
    for table, kind in table_map:
        if broad:
            added |= _append_lifecycle_rows(
                rows,
                kind,
                _query_lifecycle_table(
                    ledger,
                    table,
                    asset_class=asset_class,
                    limit=limit,
                ),
            )
            continue

        exact_filters = exact_by_table.get(table, ())
        payload_filters = payload_by_table.get(table, ())
        if any(_clean_text(value) for _, value in exact_filters) or any(
            _clean_text(value) for value in payload_filters
        ):
            added |= _append_lifecycle_rows(
                rows,
                kind,
                _query_lifecycle_table(
                    ledger,
                    table,
                    asset_class=asset_class,
                    exact_filters=exact_filters,
                    payload_filters=payload_filters,
                    limit=limit,
                ),
            )

        if allow_symbol_lookup and lookup.get("symbol"):
            added |= _append_lifecycle_rows(
                rows,
                kind,
                _query_lifecycle_table(
                    ledger,
                    table,
                    asset_class=asset_class,
                    symbol=lookup["symbol"],
                    limit=limit,
                ),
            )
    return added


def _load_lifecycle_ledger_rows(
    asset_class: str,
    *,
    symbol: str | None = None,
    signal_id: str | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
    trade_id: str | None = None,
    position_id: str | None = None,
    allow_symbol_lookup: bool = True,
    limit: int = 500,
    ledger: SQLiteRuntimeLedger | None = None,
) -> tuple[dict[str, list[dict]], bool]:
    owns_ledger = ledger is None
    if ledger is None:
        ledger = _get_runtime_ledger()
    if ledger is None:
        return _empty_lifecycle_rows(), False

    rows = _empty_lifecycle_rows()
    try:
        lookup = _derive_lifecycle_lookup(
            rows,
            signal_id=signal_id,
            order_id=order_id,
            fill_id=fill_id,
            trade_id=trade_id,
            position_id=position_id,
            symbol=symbol,
        )
        if not _has_lifecycle_lookup(lookup):
            _query_lifecycle_batch(
                ledger,
                rows,
                asset_class=asset_class,
                lookup=lookup,
                broad=True,
                limit=limit,
            )
        else:
            for _ in range(3):
                lookup = _derive_lifecycle_lookup(
                    rows,
                    signal_id=signal_id,
                    order_id=order_id,
                    fill_id=fill_id,
                    trade_id=trade_id,
                    position_id=position_id,
                    symbol=symbol,
                )
                if not _query_lifecycle_batch(
                    ledger,
                    rows,
                    asset_class=asset_class,
                    lookup=lookup,
                    allow_symbol_lookup=allow_symbol_lookup,
                    limit=limit,
                ):
                    break
        return rows, True
    except RuntimeLedgerError:
        return _empty_lifecycle_rows(), False
    except Exception:
        return rows, True
    finally:
        if owns_ledger:
            ledger.close()


def _load_lifecycle_redis_rows(
    asset_class: str,
    *,
    symbol: str | None = None,
) -> dict[str, list[dict]]:
    rows = _empty_lifecycle_rows()
    for target in target_assets(asset_class):
        try:
            reader = _get_reader(target)
            trades = reader.get_trades(start=0, count=500)
            signals = reader.get_signals(start=0, count=200)
            positions = reader.get_positions()
        except Exception:
            continue

        for key, values in (
            ("trades", trades),
            ("signals", signals),
            ("positions", positions),
        ):
            for value in values:
                if not isinstance(value, dict):
                    continue
                if symbol and _row_text(value, "symbol", "code") != symbol:
                    continue
                enriched = dict(value)
                enriched.setdefault("asset_class", target)
                rows[key].append(_with_source(enriched, "redis"))
    return rows
