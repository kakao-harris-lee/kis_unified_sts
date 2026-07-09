"""Trades route data access and conversion helpers."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.dashboard.domain.assets import target_assets
from services.dashboard.routes.trades_models import TradeResponse
from shared.exceptions import InfrastructureError
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger

_LEDGER_NAME_LOOKUP_LIMIT = 2_000


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


def _slippage_bps(
    requested_price: float | None, filled_price: float | None, side: str
) -> float | None:
    """Signed execution slippage in bps vs requested (arrival) price.

    Positive = adverse (paid more on a buy / received less on a sell).
    None when the requested price is missing/zero.
    """
    if not requested_price or filled_price is None:
        return None
    raw = (filled_price - requested_price) / requested_price
    # Sell fills are adverse when filled BELOW requested → flip sign so positive
    # is always "worse for us" regardless of side.
    signed = -raw if side.upper() in {"SELL", "SHORT"} else raw
    return round(signed * 10_000, 2)


def _ledger_fill_to_dict(fill: dict) -> dict:
    payload = fill.get("payload") if isinstance(fill.get("payload"), dict) else {}
    role = payload.get("trade_role", "")
    filled_at = fill.get("filled_at") or payload.get("filled_at")
    if isinstance(filled_at, datetime):
        filled_at = filled_at.isoformat()
    symbol = fill.get("symbol") or payload.get("symbol") or payload.get("code", "")
    side = fill.get("side") or payload.get("side", "")
    filled_price = fill.get("price") or payload.get("filled_price", 0.0)
    requested_price = payload.get("requested_price")
    return {
        "signal_id": payload.get("signal_id", ""),
        "symbol": symbol,
        "code": symbol,
        "name": _name_from_payload(fill, payload),
        "side": side,
        "filled_price": filled_price,
        "quantity": fill.get("quantity") or payload.get("quantity", 0),
        "filled_at": filled_at,
        "trade_role": "entry" if role == "entry" else "exit",
        "asset_class": fill.get("asset_class")
        or payload.get("asset_class")
        or "unknown",
        "order_id": fill.get("order_id") or payload.get("order_id", ""),
        # Execution-quality fields (TCA). Present when the fill logger recorded a
        # requested/arrival price; older rows may omit them (→ null).
        "requested_price": requested_price,
        "tick_size_points": payload.get("tick_size_points"),
        "slippage_ticks": payload.get("slippage_ticks"),
        "slippage_bps": _slippage_bps(requested_price, filled_price, side),
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
