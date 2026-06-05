"""FuturesContextProvider — the live MarketContext builder (replaces the stub).

Mirrors the field sources of shared/strategy/entry/setup_adapters._build_market_context
but pulls from a daemon-local indicator engine + parquet daily reference + Redis
macro + scheduled-events YAML (the inputs the Task-17 stub never supplied).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.decision.context import MarketContext, ScheduledEvent

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


class FuturesContextProvider:
    """Async callable returning a MarketContext (or None until warm)."""

    def __init__(
        self,
        *,
        engine: Any,
        daily_ref: Any,
        symbol: str,
        macro_reader: Callable[[], Any | None],
        events_provider: Callable[[], list[ScheduledEvent]],
        now_fn: Callable[[], datetime],
    ) -> None:
        self._engine = engine
        self._daily_ref = daily_ref
        self._symbol = symbol
        self._macro_reader = macro_reader
        self._events_provider = events_provider
        self._now_fn = now_fn

    async def __call__(self) -> MarketContext | None:
        symbol = self._symbol
        if not self._engine.is_warm(symbol):
            return None

        price = self._engine.get_last_price(symbol)
        current_price = float(price) if price is not None else 0.0
        if current_price <= 0.0:
            return None
        atr_14 = float(
            (self._engine.get_indicators(symbol) or {}).get("atr", 0.0) or 0.0
        )
        if atr_14 <= 0.0:
            # Engine is warm (enough candles) but indicators are absent or
            # stale (>180 s no tick).  Without a valid ATR, Setup A/C would
            # compute zero-width stops — suppress the context until ATR recovers.
            return None

        now = self._now_fn()
        now_kst = now.astimezone(_KST) if now.tzinfo else now.replace(tzinfo=_KST)

        self._daily_ref.observe(price=current_price, now=now_kst)
        prev_close = float(self._daily_ref.prev_close())
        today_open = float(self._daily_ref.today_open())

        rng = self._engine.get_recent_range(symbol, 15)
        last_15min_high, last_15min_low = rng if rng else (current_price, current_price)

        try:
            macro = self._macro_reader()
        except Exception:
            logger.exception("macro_reader failed; treating as no macro")
            macro = None
        try:
            events = self._events_provider()
        except Exception:
            logger.exception("events_provider failed; treating as no events")
            events = []

        return MarketContext(
            now=now_kst,
            symbol=symbol,
            current_price=current_price,
            prev_close=prev_close,
            today_open=today_open,
            vwap=0.0,  # unused by Setup A/C
            atr_14=atr_14,
            atr_90th_percentile=0.0,  # unused
            last_15min_high=float(last_15min_high),
            last_15min_low=float(last_15min_low),
            current_spread_ticks=0.0,  # unused; no orderbook in raw_data
            macro_overnight=macro,
            scheduled_events=list(events),
        )
