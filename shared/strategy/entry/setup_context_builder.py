"""Context builders for setup-based entry adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.decision.context import (
    MarketContext,
    ScheduledEvent,
    build_market_context,
)
from shared.strategy.base import EntryContext

KST = ZoneInfo("Asia/Seoul")

__all__ = ["build_setup_market_context"]


def build_setup_market_context(context: EntryContext) -> MarketContext | None:
    """Build a decision-engine ``MarketContext`` from an entry context.

    Returns ``None`` when mandatory price fields are missing or zero, which lets
    setup adapters short-circuit signal generation.
    """
    mc = context.market_context
    if isinstance(mc, MarketContext):
        return mc

    md = context.market_data or {}
    ind = context.indicators or {}

    def _get_float(keys: list[str], default: float = 0.0) -> float:
        for key in keys:
            value = md.get(key) or ind.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return default

    current_price = _get_float(["close", "current_price", "price"])
    if current_price <= 0.0:
        return None

    prev_close = _get_float(["prev_close", "previous_close"])
    today_open = _get_float(["open", "today_open"])
    atr_14 = _get_float(["atr", "atr_14", "atr14"])
    atr_90th = _get_float(["atr_90th_percentile", "atr_90pct"], default=atr_14 * 1.5)
    vwap = _get_float(["vwap"], default=current_price)
    last_15min_high = _get_float(
        ["last_15min_high", "range_high_15m"], default=current_price
    )
    last_15min_low = _get_float(
        ["last_15min_low", "range_low_15m"], default=current_price
    )
    spread_ticks = _get_float(["spread_ticks", "current_spread_ticks"], default=1.0)
    symbol = str(md.get("code", md.get("symbol", "")))

    timestamp = context.timestamp
    if timestamp is None:
        timestamp = datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp_kst = timestamp.astimezone(KST)

    raw_events: list[Any] = (context.metadata or {}).get("scheduled_events", [])
    scheduled_events: list[ScheduledEvent] = []
    for event in raw_events:
        if isinstance(event, ScheduledEvent):
            scheduled_events.append(event)

    if mc is not None and hasattr(mc, "macro_overnight"):
        macro_overnight = mc.macro_overnight  # type: ignore[union-attr]
    else:
        macro_overnight = (context.metadata or {}).get("macro_overnight")

    return build_market_context(
        now=timestamp_kst,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        atr_14=atr_14,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        vwap=vwap,
        atr_90th_percentile=atr_90th,
        current_spread_ticks=spread_ticks,
        macro_overnight=macro_overnight,
        scheduled_events=scheduled_events,
    )
