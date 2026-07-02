"""Trades endpoints."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.dashboard.domain.assets import normalize_asset_class, target_assets
from shared.exceptions import InfrastructureError
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger


def _parse_tz_aware(value: str | None) -> datetime:
    """Parse an ISO timestamp into tz-aware UTC, or fall back to now(UTC).

    Same convention as services/dashboard/routes/signals.py — the dashboard
    emits tz-aware UTC throughout so downstream comparisons (statistics,
    history, etc.) never hit "can't compare offset-naive and offset-aware".
    """
    if value is None:
        return datetime.now(UTC)
    try:
        ts = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(UTC)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _parse_optional_tz_aware(value: Any) -> datetime | None:
    """Parse an optional ISO timestamp into tz-aware UTC."""
    if isinstance(value, datetime):
        ts = value
    elif isinstance(value, str) and value:
        try:
            ts = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


router = APIRouter(prefix="/api/trades", tags=["trades"])

_LEDGER_NAME_LOOKUP_LIMIT = 2_000


class TradeResponse(BaseModel):
    """Trade response model."""

    id: str
    asset_class: str
    symbol: str
    name: str = ""
    side: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    strategy: str
    entry_time: datetime
    exit_time: datetime


class TradeListResponse(BaseModel):
    """Trade list response."""

    trades: list[TradeResponse]
    total: int
    page: int
    limit: int


class TradeStatistics(BaseModel):
    """Trade statistics."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_win: float
    max_loss: float
    profit_factor: float


class StrategyPerformance(BaseModel):
    """Per-strategy performance."""

    strategy: str
    trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float


class LifecycleStep(BaseModel):
    """One step in a signal/order/fill/trade lifecycle timeline."""

    stage: str
    label: str
    status: str
    id: str | None = None
    timestamp: datetime | None = None
    source: str
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TradeLifecycleResponse(BaseModel):
    """Read-only lifecycle timeline for dashboard inspection."""

    asset_class: str
    as_of: datetime
    filters: dict[str, str] = Field(default_factory=dict)
    lineage: dict[str, str | None] = Field(default_factory=dict)
    steps: list[LifecycleStep]
    warnings: list[str] = Field(default_factory=list)


def _get_reader(asset_class: str | None = None):
    from shared.streaming.trading_state import TradingStateReader

    asset = asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_trades(asset_class: str) -> list[dict]:
    """Load all trades from Redis."""
    try:
        reader = _get_reader(asset_class)
        return reader.get_trades(start=0, count=500)
    except InfrastructureError:
        # Redis unavailable - return empty list
        return []


def _get_runtime_ledger() -> SQLiteRuntimeLedger | None:
    """Return dashboard runtime ledger reader when an existing SQLite DB is configured."""
    try:
        config = StorageConfig.load_or_default()
        if config.dashboard.trade_stats_source != "runtime_ledger":
            return None
        if config.runtime_storage.backend != "sqlite":
            return None
        path = Path(config.runtime_storage.sqlite.path)
        if not path.exists() or path.is_dir():
            return None
        return SQLiteRuntimeLedger(config.runtime_storage.sqlite)
    except Exception:
        return None


def _ledger_row_to_trade_dict(row: dict) -> dict:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    asset_class = row.get("asset_class") or payload.get("asset_class") or "unknown"
    symbol = row.get("symbol") or payload.get("code") or payload.get("symbol") or ""
    return {
        "id": row.get("id") or payload.get("id") or payload.get("trade_id") or "",
        "asset_class": asset_class,
        "symbol": symbol,
        "code": symbol,
        "name": row.get("name") or payload.get("name") or "",
        "side": row.get("side") or payload.get("side") or "long",
        "quantity": row.get("quantity") or payload.get("quantity") or 0,
        "entry_price": row.get("entry_price") or payload.get("entry_price") or 0.0,
        "exit_price": row.get("exit_price") or payload.get("exit_price") or 0.0,
        "pnl": row.get("pnl") or payload.get("pnl") or 0.0,
        "pnl_pct": row.get("pnl_pct") or payload.get("pnl_pct") or 0.0,
        "strategy": row.get("strategy") or payload.get("strategy") or "",
        "entry_time": row.get("entry_time") or payload.get("entry_time"),
        "exit_time": row.get("exit_time") or payload.get("exit_time"),
        "hold_seconds": row.get("hold_seconds") or payload.get("hold_seconds") or 0,
        "exit_reason": row.get("exit_reason") or payload.get("exit_reason") or "",
    }


def _load_runtime_ledger_trades(
    asset_class: str,
    *,
    strategy: str | None = None,
    symbol: str | None = None,
    limit: int = 500,
) -> tuple[list[dict], bool]:
    """Load trades from RuntimeLedger.

    Returns (rows, available). ``available`` is true only when an existing
    RuntimeLedger DB was opened, so callers can distinguish "empty ledger" from
    "ledger not configured yet".
    """
    ledger = _get_runtime_ledger()
    if ledger is None:
        return [], False

    try:
        rows: list[dict] = []
        for target in target_assets(asset_class):
            filters: dict = {"asset_class": target, "limit": limit}
            if strategy:
                filters["strategy"] = strategy
            if symbol:
                filters["symbol"] = symbol
            rows.extend(ledger.query_trades(filters))
        trades = [_ledger_row_to_trade_dict(row) for row in rows]
        trades.sort(key=lambda t: _parse_tz_aware(t.get("exit_time")), reverse=True)
        return (trades[:limit] if limit > 0 else trades), True
    except RuntimeLedgerError:
        return [], False
    finally:
        ledger.close()


def _to_trade_response(t: dict, asset_class: str) -> TradeResponse | None:
    try:
        return TradeResponse(
            id=t.get("id", ""),
            asset_class=t.get("asset_class", asset_class),
            symbol=t.get("symbol") or t.get("code", ""),
            name=_clean_display_name(
                t.get("name") or t.get("stock_name") or t.get("prdt_name")
            ),
            side=t.get("side", "long"),
            quantity=int(t.get("quantity", 0)),
            entry_price=float(t.get("entry_price", 0)),
            exit_price=float(t.get("exit_price", 0)),
            pnl=float(t.get("pnl", 0)),
            pnl_pct=float(t.get("pnl_pct", 0)),
            strategy=t.get("strategy", ""),
            entry_time=_parse_tz_aware(t.get("entry_time")),
            exit_time=_parse_tz_aware(t.get("exit_time")),
        )
    except (ValueError, TypeError, KeyError):
        # Invalid trade data - skip this record
        return None


@router.get("", response_model=TradeListResponse)
async def get_trades(
    strategy: str | None = Query(None, description="Filter by strategy"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=100, description="Number of trades"),
    page: int = Query(1, ge=1, description="Page number"),
    asset_class: str = Query(default="futures"),
):
    """Get list of trades with optional filters."""
    asset = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset,
        strategy=strategy,
        symbol=symbol,
        limit=max(limit * page, limit),
    )
    using_ledger = ledger_available
    if using_ledger:
        raw_by_asset = [
            (str(trade.get("asset_class") or asset), trade) for trade in ledger_rows
        ]
    else:
        raw_by_asset = [
            (target, trade)
            for target in target_assets(asset)
            for trade in _load_trades(target)
        ]
    trades = [_to_trade_response(t, target) for target, t in raw_by_asset]
    trades = [t for t in trades if t is not None]
    trades.sort(key=lambda t: t.exit_time, reverse=True)

    if strategy and not using_ledger:
        trades = [t for t in trades if t.strategy == strategy]
    if symbol and not using_ledger:
        trades = [t for t in trades if t.symbol == symbol]

    total = len(trades)
    start = (page - 1) * limit
    end = start + limit
    paginated = trades[start:end]

    return TradeListResponse(trades=paginated, total=total, page=page, limit=limit)


@router.get("/statistics", response_model=TradeStatistics)
async def get_trade_statistics():
    """Get overall trade statistics."""
    asset = normalize_asset_class(os.environ.get("TRADING_ASSET_CLASS", "stock"))
    ledger_rows, ledger_available = _load_runtime_ledger_trades(asset)
    raw = ledger_rows if ledger_available else _load_trades(asset)
    trades = [
        _to_trade_response(
            t, t.get("asset_class", asset) if isinstance(t, dict) else asset
        )
        for t in raw
    ]
    trades = [t for t in trades if t is not None]

    if not trades:
        return TradeStatistics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl=0.0,
            max_win=0.0,
            max_loss=0.0,
            profit_factor=0.0,
        )

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl < 0]
    total_pnl = sum(t.pnl for t in trades)
    gross_profit = sum(t.pnl for t in winning) if winning else 0
    gross_loss = abs(sum(t.pnl for t in losing)) if losing else 0

    return TradeStatistics(
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=len(winning) / len(trades) * 100 if trades else 0,
        total_pnl=total_pnl,
        avg_pnl=total_pnl / len(trades) if trades else 0,
        max_win=max((t.pnl for t in trades), default=0),
        max_loss=min((t.pnl for t in trades), default=0),
        profit_factor=gross_profit / gross_loss if gross_loss > 0 else 0,
    )


@router.get("/by-strategy", response_model=list[StrategyPerformance])
async def get_trades_by_strategy(
    asset_class: str | None = Query(default=None, description="stock, futures, or all"),
):
    """Get trade performance grouped by strategy."""
    asset = normalize_asset_class(
        asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    )
    ledger_rows, ledger_available = _load_runtime_ledger_trades(asset)
    if ledger_available:
        raw = ledger_rows
    else:
        raw = []
        for target in target_assets(asset):
            raw.extend(_load_trades(target))
    trades = [
        _to_trade_response(
            t, t.get("asset_class", asset) if isinstance(t, dict) else asset
        )
        for t in raw
    ]
    trades = [t for t in trades if t is not None]

    strategy_trades: dict[str, list[TradeResponse]] = {}
    for trade in trades:
        if trade.strategy not in strategy_trades:
            strategy_trades[trade.strategy] = []
        strategy_trades[trade.strategy].append(trade)

    results = []
    for strat, strades in strategy_trades.items():
        winning = len([t for t in strades if t.pnl > 0])
        total_pnl = sum(t.pnl for t in strades)
        results.append(
            StrategyPerformance(
                strategy=strat,
                trades=len(strades),
                win_rate=winning / len(strades) * 100 if strades else 0,
                total_pnl=total_pnl,
                avg_pnl=total_pnl / len(strades) if strades else 0,
            )
        )

    return results


def _empty_db_stats() -> dict[str, float]:
    return {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "avg_pnl": 0.0,
        "max_win": 0.0,
        "max_loss": 0.0,
    }


def _statistics_from_trade_dicts(trades: list[dict]) -> dict[str, float]:
    if not trades:
        return _empty_db_stats()

    pnls = [float(t.get("pnl", 0) or 0) for t in trades]
    winning = [pnl for pnl in pnls if pnl > 0]
    losing = [pnl for pnl in pnls if pnl <= 0]
    total_pnl = sum(pnls)
    return {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(len(winning) / len(trades) * 100, 2),
        "total_pnl": total_pnl,
        "avg_pnl": round(total_pnl / len(trades), 2),
        "max_win": max(pnls, default=0.0),
        "max_loss": min(pnls, default=0.0),
    }


def _ledger_trade_to_closed_dict(trade: dict) -> dict:
    return {
        "id": trade.get("id", ""),
        "asset_class": trade.get("asset_class", "unknown"),
        "code": trade.get("code") or trade.get("symbol", ""),
        "name": trade.get("name", ""),
        "strategy": trade.get("strategy", ""),
        "side": trade.get("side", "long"),
        "entry_date": trade.get("entry_time"),
        "entry_price": trade.get("entry_price", 0.0),
        "exit_date": trade.get("exit_time"),
        "exit_price": trade.get("exit_price", 0.0),
        "quantity": trade.get("quantity", 0),
        "pnl": trade.get("pnl", 0.0),
        "pnl_pct": trade.get("pnl_pct", 0.0),
        "hold_seconds": trade.get("hold_seconds", 0),
        "exit_reason": trade.get("exit_reason", ""),
    }


def _clean_display_name(value: Any) -> str:
    if value is None:
        return ""
    name = str(value).strip()
    if not name or name.lower() in {"none", "null"}:
        return ""
    return name


def _symbol_from_payload(row: dict, payload: dict) -> str:
    return str(row.get("symbol") or payload.get("symbol") or payload.get("code") or "")


def _name_from_payload(row: dict, payload: dict) -> str:
    return _clean_display_name(
        row.get("name")
        or payload.get("name")
        or payload.get("stock_name")
        or payload.get("prdt_name")
    )


def _ledger_symbol_names(
    ledger: SQLiteRuntimeLedger,
    asset_class: str,
) -> dict[str, str]:
    names: dict[str, str] = {}
    for target in target_assets(asset_class):
        try:
            trades = ledger.query_trades(
                {"asset_class": target, "limit": _LEDGER_NAME_LOOKUP_LIMIT}
            )
        except RuntimeLedgerError:
            trades = []
        for trade in trades:
            payload = (
                trade.get("payload") if isinstance(trade.get("payload"), dict) else {}
            )
            symbol = _symbol_from_payload(trade, payload)
            name = _name_from_payload(trade, payload)
            if symbol and name:
                names.setdefault(symbol, name)

        try:
            positions = ledger.load_open_positions(target)
        except RuntimeLedgerError:
            positions = []
        for position in positions:
            payload = (
                position.get("payload")
                if isinstance(position.get("payload"), dict)
                else {}
            )
            symbol = _symbol_from_payload(position, payload)
            name = _name_from_payload(position, payload)
            if symbol and name:
                names.setdefault(symbol, name)
    return names


def _ledger_fill_to_dict(fill: dict) -> dict:
    payload = fill.get("payload") if isinstance(fill.get("payload"), dict) else {}
    role = payload.get("trade_role", "")
    filled_at = fill.get("filled_at") or payload.get("filled_at")
    if isinstance(filled_at, datetime):
        filled_at = filled_at.isoformat()
    symbol = fill.get("symbol") or payload.get("symbol") or payload.get("code", "")
    return {
        "signal_id": payload.get("signal_id", ""),
        "symbol": symbol,
        "code": symbol,
        "name": _name_from_payload(fill, payload),
        "side": fill.get("side") or payload.get("side", ""),
        "filled_price": fill.get("price") or payload.get("filled_price", 0.0),
        "quantity": fill.get("quantity") or payload.get("quantity", 0),
        "filled_at": filled_at,
        "trade_role": "entry" if role == "entry" else "exit",
        "asset_class": fill.get("asset_class")
        or payload.get("asset_class")
        or "unknown",
        "order_id": fill.get("order_id") or payload.get("order_id", ""),
    }


def _load_runtime_ledger_fills(
    asset_class: str,
    *,
    limit: int = 100,
) -> tuple[list[dict], bool]:
    ledger = _get_runtime_ledger()
    if ledger is None:
        return [], False
    try:
        rows: list[dict] = []
        for target in target_assets(asset_class):
            rows.extend(ledger.query_fills({"asset_class": target, "limit": limit}))
        symbol_names = _ledger_symbol_names(ledger, asset_class)
        fills = [_ledger_fill_to_dict(row) for row in rows]
        for fill in fills:
            if not fill.get("name"):
                fill["name"] = symbol_names.get(str(fill.get("symbol") or ""), "")
        fills.sort(key=lambda f: _parse_tz_aware(f.get("filled_at")), reverse=True)
        return fills[:limit], True
    except RuntimeLedgerError:
        return [], False
    finally:
        ledger.close()


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


def _row_matches(row: dict, expected: str | None, *keys: str) -> bool:
    expected_text = _clean_text(expected)
    if expected_text is None:
        return False
    return any(_row_text(row, key) == expected_text for key in keys)


def _pick_row(
    rows: list[dict],
    selectors: list[tuple[str | None, tuple[str, ...]]],
    *,
    allow_fallback: bool,
) -> dict | None:
    for expected, keys in selectors:
        if not _clean_text(expected):
            continue
        for row in rows:
            if _row_matches(row, expected, *keys):
                return row
    if allow_fallback and rows:
        return rows[0]
    return None


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
    # When a caller passes an already-open ledger we reuse it (and leave closing
    # to the owner) instead of opening — and migrating — a second connection.
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


def _status_from_bool_or_text(row: dict | None, *keys: str) -> str:
    value = _row_value(row, *keys)
    if isinstance(value, bool):
        return "executed" if value else "generated"
    text = _clean_text(value)
    return text.lower() if text else "unknown"


def _compact_details(row: dict | None, keys: tuple[str, ...]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if not row:
        return details
    for key in keys:
        value = _row_value(row, key)
        if value is not None and value != "":
            details[key] = value
    return details


def _missing_lifecycle_step(
    *,
    stage: str,
    label: str,
    expected_id: str | None,
) -> LifecycleStep:
    status = "unknown" if expected_id else "not_available"
    summary = "Lineage id is present, but no evidence row was found."
    if status == "not_available":
        summary = "No evidence is available for this lifecycle step."
    return LifecycleStep(
        stage=stage,
        label=label,
        status=status,
        id=expected_id,
        source="not_available",
        summary=summary,
    )


def _source(row: dict | None) -> str:
    return str(row.get("__source") or "runtime_ledger") if row else "not_available"


def _signal_step(row: dict | None, signal_id: str | None) -> LifecycleStep:
    if row is None:
        return _missing_lifecycle_step(
            stage="signal",
            label="Signal",
            expected_id=signal_id,
        )
    symbol = _row_text(row, "symbol", "code")
    strategy = _row_text(row, "strategy")
    side = _row_text(row, "side", "signal_type")
    summary = "Generated"
    if symbol or side:
        summary = " ".join(part for part in (side, symbol) if part)
    return LifecycleStep(
        stage="signal",
        label="Signal",
        status=_status_from_bool_or_text(row, "decision", "status", "executed"),
        id=signal_id or _row_text(row, "signal_id", "id"),
        timestamp=_parse_optional_tz_aware(
            _row_value(row, "created_at", "timestamp", "signal_time")
        ),
        source=_source(row),
        summary=summary,
        details=_compact_details(
            row,
            (
                "asset_class",
                "symbol",
                "strategy",
                "side",
                "signal_type",
                "confidence",
                "price",
                "reason",
                "stage",
            ),
        )
        | ({"strategy": strategy} if strategy else {}),
    )


def _order_step(row: dict | None, order_id: str | None) -> LifecycleStep:
    if row is None:
        return _missing_lifecycle_step(
            stage="ticket_order",
            label="Ticket / Order",
            expected_id=order_id,
        )
    symbol = _row_text(row, "symbol", "code")
    side = _row_text(row, "side")
    quantity = _row_value(row, "quantity", "qty")
    return LifecycleStep(
        stage="ticket_order",
        label="Ticket / Order",
        status=_status_from_bool_or_text(row, "status", "decision"),
        id=order_id
        or _row_text(row, "id", "order_id", "client_order_id", "broker_order_id"),
        timestamp=_parse_optional_tz_aware(
            _row_value(row, "created_at", "timestamp", "updated_at")
        ),
        source=_source(row),
        summary=" ".join(str(part) for part in (side, quantity, symbol) if part),
        details=_compact_details(
            row,
            (
                "asset_class",
                "symbol",
                "strategy",
                "side",
                "order_type",
                "quantity",
                "price",
                "client_order_id",
                "broker_order_id",
                "signal_id",
            ),
        ),
    )


def _fill_step(row: dict | None, fill_id: str | None) -> LifecycleStep:
    if row is None:
        return _missing_lifecycle_step(
            stage="fill",
            label="Fill",
            expected_id=fill_id,
        )
    symbol = _row_text(row, "symbol", "code")
    side = _row_text(row, "side")
    quantity = _row_value(row, "quantity", "filled_qty")
    price = _row_value(row, "price", "filled_price")
    return LifecycleStep(
        stage="fill",
        label="Fill",
        status="filled",
        id=fill_id or _row_text(row, "id", "fill_id", "broker_fill_id"),
        timestamp=_parse_optional_tz_aware(_row_value(row, "filled_at", "timestamp")),
        source=_source(row),
        summary=" ".join(str(part) for part in (side, quantity, symbol, price) if part),
        details=_compact_details(
            row,
            (
                "asset_class",
                "symbol",
                "side",
                "quantity",
                "filled_qty",
                "price",
                "filled_price",
                "order_id",
                "signal_id",
                "trade_role",
                "venue",
            ),
        ),
    )


def _position_step(row: dict | None, position_id: str | None) -> LifecycleStep:
    if row is None:
        return _missing_lifecycle_step(
            stage="position",
            label="Position",
            expected_id=position_id,
        )
    is_open = _row_value(row, "is_open")
    if is_open is None:
        status = _status_from_bool_or_text(row, "state", "current_state")
    else:
        status = "open" if bool(is_open) else "closed"
    symbol = _row_text(row, "symbol", "code")
    side = _row_text(row, "side")
    quantity = _row_value(row, "quantity")
    return LifecycleStep(
        stage="position",
        label="Position",
        status=status,
        id=position_id or _row_text(row, "position_id", "id"),
        timestamp=_parse_optional_tz_aware(
            _row_value(row, "snapshot_time", "updated_at", "entry_time")
        ),
        source=_source(row),
        summary=" ".join(str(part) for part in (side, quantity, symbol) if part),
        details=_compact_details(
            row,
            (
                "asset_class",
                "symbol",
                "strategy",
                "side",
                "quantity",
                "entry_price",
                "current_price",
                "state",
                "is_open",
                "exit_reason",
            ),
        ),
    )


def _closed_trade_step(row: dict | None, trade_id: str | None) -> LifecycleStep:
    if row is None:
        return _missing_lifecycle_step(
            stage="closed_trade",
            label="Closed Trade",
            expected_id=trade_id,
        )
    symbol = _row_text(row, "symbol", "code")
    pnl = _row_value(row, "pnl")
    return LifecycleStep(
        stage="closed_trade",
        label="Closed Trade",
        status="closed",
        id=trade_id or _row_text(row, "id", "trade_id"),
        timestamp=_parse_optional_tz_aware(_row_value(row, "exit_time", "exit_date")),
        source=_source(row),
        summary=" ".join(str(part) for part in (symbol, "pnl", pnl) if part),
        details=_compact_details(
            row,
            (
                "asset_class",
                "symbol",
                "strategy",
                "side",
                "quantity",
                "entry_price",
                "exit_price",
                "pnl",
                "pnl_pct",
                "exit_reason",
            ),
        ),
    )


def _maybe_set_lineage(lineage: dict[str, str | None], key: str, value: Any) -> None:
    if lineage.get(key) is None:
        lineage[key] = _clean_text(value)


def _build_lifecycle_response(
    *,
    asset_class: str,
    signal_id: str | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
    trade_id: str | None = None,
    position_id: str | None = None,
    symbol: str | None = None,
    ledger_rows: dict[str, list[dict]] | None = None,
    redis_rows: dict[str, list[dict]] | None = None,
    ledger_available: bool = True,
    allow_symbol_fallback: bool = True,
) -> TradeLifecycleResponse:
    ledger_rows = ledger_rows or _empty_lifecycle_rows()
    redis_rows = redis_rows or _empty_lifecycle_rows()
    filters = {
        key: value
        for key, value in {
            "signal_id": signal_id,
            "order_id": order_id,
            "fill_id": fill_id,
            "trade_id": trade_id,
            "position_id": position_id,
            "symbol": symbol,
        }.items()
        if _clean_text(value)
    }
    has_request_filters = bool(filters)
    symbol_selector = symbol if allow_symbol_fallback else None

    all_trades = ledger_rows["trades"] + redis_rows["trades"]
    all_fills = ledger_rows["fills"] + redis_rows["fills"]
    all_orders = ledger_rows["orders"] + redis_rows["orders"]
    all_signals = ledger_rows["signals"] + redis_rows["signals"]
    all_positions = ledger_rows["positions"] + redis_rows["positions"]

    trade = _pick_row(
        all_trades,
        [
            (trade_id, ("id", "trade_id")),
            (fill_id, ("fill_id", "entry_fill_id", "exit_fill_id")),
            (order_id, ("order_id", "entry_order_id", "exit_order_id")),
            (signal_id, ("signal_id",)),
            (symbol_selector, ("symbol", "code")),
        ],
        allow_fallback=not has_request_filters,
    )

    lineage: dict[str, str | None] = {
        "signal_id": _clean_text(signal_id),
        "order_id": _clean_text(order_id),
        "fill_id": _clean_text(fill_id),
        "trade_id": _clean_text(trade_id),
        "position_id": _clean_text(position_id),
    }
    _maybe_set_lineage(lineage, "trade_id", _row_value(trade, "id", "trade_id"))
    _maybe_set_lineage(lineage, "position_id", _row_value(trade, "position_id"))
    _maybe_set_lineage(lineage, "signal_id", _row_value(trade, "signal_id"))
    _maybe_set_lineage(
        lineage, "order_id", _row_value(trade, "order_id", "entry_order_id")
    )
    _maybe_set_lineage(
        lineage, "fill_id", _row_value(trade, "fill_id", "entry_fill_id")
    )

    fill = _pick_row(
        all_fills,
        [
            (lineage["fill_id"], ("id", "fill_id", "broker_fill_id")),
            (lineage["order_id"], ("order_id",)),
            (lineage["signal_id"], ("signal_id",)),
            (
                symbol_selector
                or (
                    _row_text(trade, "symbol", "code")
                    if allow_symbol_fallback
                    else None
                ),
                ("symbol", "code"),
            ),
        ],
        allow_fallback=not any(
            (lineage["fill_id"], lineage["order_id"], lineage["signal_id"])
        )
        and not has_request_filters,
    )
    _maybe_set_lineage(lineage, "fill_id", _row_value(fill, "id", "fill_id"))
    _maybe_set_lineage(lineage, "order_id", _row_value(fill, "order_id"))
    _maybe_set_lineage(lineage, "signal_id", _row_value(fill, "signal_id"))

    order = _pick_row(
        all_orders,
        [
            (
                lineage["order_id"],
                ("id", "order_id", "client_order_id", "broker_order_id"),
            ),
            (lineage["signal_id"], ("signal_id",)),
            (
                symbol_selector
                or (
                    _row_text(fill, "symbol", "code") if allow_symbol_fallback else None
                ),
                ("symbol", "code"),
            ),
        ],
        allow_fallback=not any((lineage["order_id"], lineage["signal_id"]))
        and not has_request_filters,
    )
    _maybe_set_lineage(
        lineage,
        "order_id",
        _row_value(order, "id", "order_id", "client_order_id", "broker_order_id"),
    )
    _maybe_set_lineage(lineage, "signal_id", _row_value(order, "signal_id"))

    signal = _pick_row(
        all_signals,
        [
            (lineage["signal_id"], ("signal_id", "id")),
            (lineage["order_id"], ("order_id", "client_order_id", "broker_order_id")),
            (
                symbol_selector
                or (
                    _row_text(order, "symbol", "code")
                    if allow_symbol_fallback
                    else None
                ),
                ("symbol", "code"),
            ),
        ],
        allow_fallback=not any((lineage["signal_id"], lineage["order_id"]))
        and not has_request_filters,
    )
    _maybe_set_lineage(lineage, "signal_id", _row_value(signal, "signal_id", "id"))
    _maybe_set_lineage(lineage, "order_id", _row_value(signal, "order_id"))

    if order is None and lineage["signal_id"]:
        order = _pick_row(
            all_orders,
            [(lineage["signal_id"], ("signal_id",))],
            allow_fallback=False,
        )
        _maybe_set_lineage(
            lineage,
            "order_id",
            _row_value(order, "id", "order_id", "client_order_id", "broker_order_id"),
        )
    if fill is None and lineage["order_id"]:
        fill = _pick_row(
            all_fills,
            [(lineage["order_id"], ("order_id",))],
            allow_fallback=False,
        )
        _maybe_set_lineage(lineage, "fill_id", _row_value(fill, "id", "fill_id"))

    position = _pick_row(
        all_positions,
        [
            (lineage["position_id"], ("position_id", "id")),
            (lineage["trade_id"], ("trade_id",)),
            (
                symbol_selector
                or (
                    _row_text(trade, "symbol", "code")
                    or _row_text(fill, "symbol", "code")
                    if allow_symbol_fallback
                    else None
                ),
                ("symbol", "code"),
            ),
        ],
        allow_fallback=not lineage["position_id"] and not has_request_filters,
    )
    _maybe_set_lineage(
        lineage, "position_id", _row_value(position, "position_id", "id")
    )

    steps = [
        _signal_step(signal, lineage["signal_id"]),
        _order_step(order, lineage["order_id"]),
        _fill_step(fill, lineage["fill_id"]),
        _position_step(position, lineage["position_id"]),
        _closed_trade_step(trade, lineage["trade_id"]),
    ]

    warnings: list[str] = []
    if not ledger_available:
        warnings.append("runtime_ledger_not_available")
    if trade is not None and any(
        step.status in {"unknown", "not_available"}
        for step in steps
        if step.stage in {"signal", "ticket_order", "fill"}
    ):
        warnings.append("partial_legacy_lineage")
    if not any(step.source != "not_available" for step in steps):
        warnings.append("no_lifecycle_evidence")

    return TradeLifecycleResponse(
        asset_class=asset_class,
        as_of=datetime.now(UTC),
        filters=filters,
        lineage=lineage,
        steps=steps,
        warnings=warnings,
    )


@router.get("/lifecycle", response_model=TradeLifecycleResponse)
async def get_trade_lifecycle(
    signal_id: str | None = Query(None, description="Filter by signal id"),
    order_id: str | None = Query(None, description="Filter by order id"),
    fill_id: str | None = Query(None, description="Filter by fill id"),
    trade_id: str | None = Query(None, description="Filter by closed trade id"),
    symbol: str | None = Query(None, description="Filter by symbol/code"),
    asset_class: str = Query(default="futures"),
) -> TradeLifecycleResponse:
    """Return a read-only signal/order/fill/trade lifecycle timeline."""
    asset = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_lifecycle_ledger_rows(
        asset,
        symbol=symbol,
        signal_id=signal_id,
        order_id=order_id,
        fill_id=fill_id,
        trade_id=trade_id,
    )
    redis_rows = _load_lifecycle_redis_rows(asset, symbol=symbol)
    return _build_lifecycle_response(
        asset_class=asset,
        signal_id=signal_id,
        order_id=order_id,
        fill_id=fill_id,
        trade_id=trade_id,
        symbol=symbol,
        ledger_rows=ledger_rows,
        redis_rows=redis_rows,
        ledger_available=ledger_available,
    )


@router.get("/closed/statistics")
async def get_db_closed_statistics(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
):
    """Aggregate statistics from RuntimeLedger."""
    asset_class = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset_class,
        strategy=strategy,
        limit=10_000,
    )
    if ledger_available:
        return _statistics_from_trade_dicts(ledger_rows)
    return _empty_db_stats()


@router.get("/fills")
async def get_recent_fills(
    asset_class: str = Query(default="futures"),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    """Recent order fills from RuntimeLedger."""
    asset = normalize_asset_class(asset_class)
    ledger_fills, ledger_available = _load_runtime_ledger_fills(asset, limit=limit)
    if ledger_available:
        return {"fills": ledger_fills}
    return {"fills": []}


@router.get("/closed")
async def get_db_closed_trades(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
    code: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Recent closed trades from RuntimeLedger."""
    asset_class = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset_class,
        strategy=strategy,
        symbol=code,
        limit=limit,
    )
    if ledger_available:
        return [_ledger_trade_to_closed_dict(row) for row in ledger_rows]
    return []
