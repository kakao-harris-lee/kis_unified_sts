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

from shared.decision.context import (
    MarketContext,
    ScheduledEvent,
    build_market_context,
)

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
        # State-change latch for the VWAP availability log below: log the
        # transition, not every 60 s tick (it holds until the first candle).
        self._vwap_unavailable = False

    async def __call__(self) -> MarketContext | None:
        symbol = self._symbol
        if not self._engine.is_warm(symbol):
            return None

        price = self._engine.get_last_price(symbol)
        current_price = float(price) if price is not None else 0.0
        if current_price <= 0.0:
            return None
        indicators = self._engine.get_indicators(symbol) or {}
        atr_14 = float(indicators.get("atr", 0.0) or 0.0)
        if atr_14 <= 0.0:
            # Engine is warm (enough candles) but indicators are absent or
            # stale (>180 s no tick).  Without a valid ATR, Setup A/C would
            # compute zero-width stops — suppress the context until ATR recovers.
            return None

        # Session VWAP from the streaming engine's VWAPCalculator. Setup D reads
        # it as z = (price - vwap) / atr_14, so a MISSING vwap is not a benign
        # default — substituting current_price collapses z to 0 and makes Setup
        # D permanently inert (#533/#537 class). It is therefore passed through
        # as-is (0.0 when absent) and the DAEMON skips only the setups that
        # declare REQUIRES_VWAP; suppressing the whole context here would also
        # darken Setup A/C, which never read vwap.
        #
        # Engine behaviour worth knowing (not fixed here — the engine is out of
        # scope). ``VWAPCalculator`` is keyed on the UTC calendar date
        # (``ts.strftime("%Y%m%d")``, shared/indicators/streaming/engine.py),
        # so the session it accumulates is NOT the KRX session:
        #   * 0.0 happens on a COLD START only — the symbol has no entry and no
        #     volume yet, because parquet warm-up does not seed the calculator
        #     (``seed_candles`` never feeds ``_vwap_calc``). That is the case
        #     this guard reports, and the daemon turns it into a `no_vwap`
        #     evaluation for the vwap-dependent setups.
        #   * At the 00:00 UTC / 09:00 KST boundary ``add_tick`` resets the
        #     accumulator and adds the new tick in the SAME call, so vwap is
        #     immediately non-zero but degenerate: it equals that one candle's
        #     close, i.e. z ≈ 0 for the first candles of the new bucket. That
        #     reads as an ordinary `not_extreme` reject, NOT as `no_vwap` —
        #     it is silent, and no guard here can see it.
        #   * Between 08:45 and 09:00 KST the UTC date is still yesterday's, so
        #     the value carries over the PREVIOUS bucket's accumulation.
        vwap = float(indicators.get("vwap", 0.0) or 0.0)
        if vwap <= 0.0 and not self._vwap_unavailable:
            self._vwap_unavailable = True
            logger.warning(
                "session VWAP unavailable for %s (cold accumulator); "
                "vwap-dependent setups are skipped until the first candle "
                "completes (Setup A/C keep running)",
                symbol,
            )
        elif vwap > 0.0 and self._vwap_unavailable:
            self._vwap_unavailable = False
            logger.info("session VWAP available again for %s", symbol)

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

        return build_market_context(
            now=now_kst,
            symbol=symbol,
            current_price=current_price,
            prev_close=prev_close,
            today_open=today_open,
            atr_14=atr_14,
            vwap=vwap,
            last_15min_high=float(last_15min_high),
            last_15min_low=float(last_15min_low),
            macro_overnight=macro,
            scheduled_events=list(events),
        )
