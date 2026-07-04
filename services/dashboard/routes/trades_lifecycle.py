"""Trades lifecycle evidence loading and timeline assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.dashboard.routes.trades_data import _parse_optional_tz_aware
from services.dashboard.routes.trades_lifecycle_data import (
    _clean_text,
    _empty_lifecycle_rows,
    _row_text,
    _row_value,
)
from services.dashboard.routes.trades_lifecycle_data import (
    _load_lifecycle_ledger_rows as _load_lifecycle_ledger_rows,
)
from services.dashboard.routes.trades_lifecycle_data import (
    _load_lifecycle_redis_rows as _load_lifecycle_redis_rows,
)
from services.dashboard.routes.trades_models import (
    LifecycleStep,
    TradeLifecycleResponse,
)


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
