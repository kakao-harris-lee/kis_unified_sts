"""StockStrategyDaemon — stock entry-candidate producer (shadow-first).

Owns a daemon-local indicator engine fed by market:ticks (StreamConsumerFeed),
a dynamic screener universe, and the existing StrategyManager. On a decision
cadence it builds an EntryContext per warm symbol and publishes the resulting
orchestrator Signals to signal.candidate.stock(.shadow).

As the only decoupled component with an indicator engine, it also computes the
market-wide regime (median MFI over the universe) and publishes it to Redis for
M4-X's bear exit — see ``shared.streaming.stock_regime``. While the regime is
BEAR_* it skips entry evaluation (``block_entries_in_bear``): long-only entries
in a bear market would be liquidated by M4-X immediately (fee churn).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.stock_strategy.candidate import stock_signal_to_stream_dict
from services.stock_strategy.universe import parse_watchlist_codes
from shared.models.signal import Signal
from shared.strategy.base import EntryContext
from shared.strategy.market_time import is_regular_session_open
from shared.streaming.stock_regime import (
    StockRegimeConfig,
    compute_regime_payload,
    indicator_lag_seconds,
    is_bear_regime,
)

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class StockStrategyDaemon:
    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        engine: Any,
        resolver: Any,
        manager: Any,
        candidate_stream: str,
        candidate_maxlen: int,
        now_fn: Callable[[], datetime],
        eval_interval_seconds: float = 60.0,
        universe_refresh_seconds: float = 30.0,
        max_symbols: int = 40,
        watchlist_reader: Callable[[], Any] | None = None,
        regime_config: StockRegimeConfig | None = None,
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.engine = engine
        self.resolver = resolver
        self.manager = manager
        self.candidate_stream = candidate_stream
        self.candidate_maxlen = candidate_maxlen
        self._now_fn = now_fn
        self._eval_interval = eval_interval_seconds
        self._universe_refresh = universe_refresh_seconds
        self._max_symbols = max_symbols
        self._watchlist_reader = watchlist_reader
        self._regime_config = regime_config
        self._universe: list[str] = []
        self._stop = asyncio.Event()

    def _apply_watchlist(self, raw: Any) -> None:
        codes = parse_watchlist_codes(raw, max_symbols=self._max_symbols)
        if not codes:
            return  # keep prior universe
        self._universe = codes
        self.feed.update_symbols(codes)

    async def _publish_regime(self, now: datetime) -> dict[str, Any] | None:
        """Compute + publish the market regime; return the payload (None if off).

        Compute failures log and return None — entry evaluation proceeds
        ungated, and M4-X's staleness gate covers the missed publish. A
        publish (``redis.set``) failure still returns the locally computed
        payload so the bear entry gate keeps working: M4-X may still act on
        the previous fresh payload, and entering long during BEAR in that
        window is exactly the fee churn the gate prevents.
        """
        cfg = self._regime_config
        if cfg is None or not cfg.enabled:
            return None
        get_mfi = getattr(self.engine, "get_market_mfi_values", None)
        if get_mfi is None:
            return None
        try:
            universe = set(self._universe)
            mfi_by_symbol = get_mfi(universe)
            payload = compute_regime_payload(
                mfi_by_symbol,
                config=cfg,
                now_ms=int(now.timestamp() * 1000),
                last_tick_ts_ms=self._latest_tick_ts_ms(universe),
            )
        except Exception:
            logger.exception("stock regime compute failed")
            return None
        self._observe_indicator_lag(payload, now)
        try:
            await self.redis.set(
                cfg.redis_key, json.dumps(payload), ex=cfg.publish_ttl_seconds
            )
        except Exception:
            logger.exception("stock regime publish failed")
        return payload

    def _latest_tick_ts_ms(self, universe: set[str]) -> int | None:
        """Freshest engine tick timestamp as epoch ms (None when unavailable).

        Duck-typed like ``get_market_mfi_values`` — an engine without the
        method (or with no ticks yet) yields None, which publishes a
        null ``last_tick_ts_ms`` (old-schema behavior).
        """
        get_latest = getattr(self.engine, "get_market_latest_tick_ts", None)
        if get_latest is None:
            return None
        ts = get_latest(universe)
        if ts is None:
            return None
        return int(ts.timestamp() * 1000)

    def _observe_indicator_lag(self, payload: dict[str, Any], now: datetime) -> None:
        """Log the candle-freshness lag of the regime payload (issue #460).

        WARNING only when the lag breaches ``warn_indicator_lag_seconds``
        *during the regular session* — off-hours the tick stream is silent by
        design and the lag grows unboundedly (would spam all night). The
        unconditional DEBUG line keeps the lag inspectable at any time.
        """
        cfg = self._regime_config
        lag = indicator_lag_seconds(payload)
        if lag is None or cfg is None:
            return
        logger.debug(
            "stock regime computed: regime=%s mfi_symbols=%s indicator_lag=%.0fs",
            payload.get("regime"),
            payload.get("mfi_symbols"),
            lag,
        )
        if lag > cfg.warn_indicator_lag_seconds and is_regular_session_open(now):
            logger.warning(
                "stock regime indicator lag %.0fs exceeds %.0fs in-session — "
                "regime %s is computed from stale candles (tick stream stall?)",
                lag,
                cfg.warn_indicator_lag_seconds,
                payload.get("regime"),
            )

    async def evaluate_once(self) -> int:
        """Build context + check_entries per warm symbol; publish. Returns #published."""
        published = 0
        now = self._now_fn()
        regime_payload = await self._publish_regime(now)
        if (
            regime_payload is not None
            and self._regime_config is not None
            and self._regime_config.block_entries_in_bear
            and is_bear_regime(regime_payload.get("regime"))
        ):
            logger.info(
                "bear regime %s (mfi=%s, symbols=%s) — skipping entry evaluation",
                regime_payload.get("regime"),
                regime_payload.get("mfi"),
                regime_payload.get("mfi_symbols"),
            )
            return 0
        for symbol in list(self._universe):
            try:
                if not self.engine.is_warm(symbol):
                    continue
                market_data = await self.feed.get_current_price(symbol)
                if not market_data:
                    continue
                indicators = self.resolver.collect_entry_indicators(symbol)
                ctx = EntryContext(
                    market_data=market_data,
                    indicators=indicators,
                    current_positions=[],
                    timestamp=now,
                    metadata={"shadow": True},
                )
                signals = await self.manager.check_entries(ctx)
                for sig in signals or []:
                    await self._publish(sig)
                    published += 1
            except Exception:
                logger.exception("stock entry eval failed symbol=%s", symbol)
        return published

    async def _publish(self, signal: Signal) -> None:
        fields = stock_signal_to_stream_dict(signal, signal_id=uuid.uuid4().hex)
        await self.redis.xadd(
            self.candidate_stream,
            fields,
            maxlen=self.candidate_maxlen,
            approximate=True,
        )
        await self.redis.expire(self.candidate_stream, _STREAM_TTL_SECONDS)

    async def _refresh_loop(self) -> None:
        while not self._stop.is_set():
            if self._watchlist_reader is not None:
                try:
                    self._apply_watchlist(self._watchlist_reader())
                except Exception:
                    logger.exception("watchlist refresh failed; keeping prior universe")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self._universe_refresh
                )

    async def run(self) -> None:
        await self.feed.start()
        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            while not self._stop.is_set():
                await self.evaluate_once()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._eval_interval
                    )
        finally:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()
