"""Market ingest daemon — owns a KIS price feed and republishes every tick to the
Redis tick stream (``market:ticks`` / ``raw_data``) and NOTHING else.

Isolating the WebSocket reader in its own process keeps tick→stream latency
independent of downstream indicator/strategy/order compute (M1 of the
stream-pipeline-decoupling design). Per-asset: ``INGEST_ASSET=stock|futures``
selects the feed + symbol source in ``_build_and_run``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

SymbolProvider = Callable[[], Awaitable[list[str]]]


def _parse_trade_targets(raw: str | None, max_symbols: int) -> list[str]:
    """Parse a ``system:trade_targets:latest`` payload into a capped code list.

    Payload shape: ``{"codes": [...], "names": {...}, "metadata": {...}}``.
    Returns ``[]`` on missing/invalid input so the daemon keeps its current
    subscription rather than crashing.
    """
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    codes = [str(c).strip() for c in payload.get("codes", []) if str(c).strip()]
    return codes[:max_symbols]


class MarketIngestDaemon:
    """Own a KIS price feed; republish each tick to the Redis tick stream.

    The tick callback does ONLY ``publisher.publish`` — no indicators, strategy,
    or orders — so the feed's frame-processing thread is never blocked by
    downstream compute.
    """

    def __init__(
        self,
        *,
        asset: str,
        feed: Any,
        publisher: Any,
        symbol_provider: SymbolProvider,
        refresh_interval_seconds: float,
        restart_on_symbol_change: bool = False,
    ) -> None:
        self.asset = asset
        self.feed = feed
        self.publisher = publisher
        self.symbol_provider = symbol_provider
        self.refresh_interval_seconds = refresh_interval_seconds
        self.restart_on_symbol_change = restart_on_symbol_change
        self._symbols: list[str] = []
        self._stop = asyncio.Event()

    def _on_tick(
        self, symbol: str, data: dict[str, Any], ts: datetime  # noqa: ARG002
    ) -> None:
        # Hot path: republish only. (ts is part of the feed callback contract
        # but the tick stream carries its own timestamp in `data`.)
        self.publisher.publish(self.asset, symbol, data)

    async def _apply_symbols(self, symbols: list[str]) -> None:
        if self.restart_on_symbol_change:
            # Futures feed requires update_symbols BEFORE start(); restart on change.
            await self.feed.stop()
            self.feed.update_symbols(symbols)
            await self.feed.start()
        else:
            # Stock feed accepts live update_symbols (diffs sub/unsub internally).
            self.feed.update_symbols(symbols)
        self._symbols = symbols

    async def run(self) -> None:
        self.feed.set_tick_callback(self._on_tick)
        symbols = await self.symbol_provider()
        self._symbols = symbols
        self.feed.update_symbols(symbols)
        await self.feed.start()
        logger.info(
            "market-ingest started asset=%s symbols=%d", self.asset, len(symbols)
        )
        try:
            while not self._stop.is_set():
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.refresh_interval_seconds
                    )
                if self._stop.is_set():
                    break
                try:
                    new_symbols = await self.symbol_provider()
                except Exception:
                    logger.exception("symbol_provider failed; keeping current symbols")
                    continue
                if new_symbols and new_symbols != self._symbols:
                    logger.info(
                        "universe change asset=%s %d→%d",
                        self.asset,
                        len(self._symbols),
                        len(new_symbols),
                    )
                    await self._apply_symbols(new_symbols)
                elif not new_symbols:
                    logger.debug(
                        "symbol_provider returned empty list; keeping current symbols"
                    )
        finally:
            await self.feed.stop()
            self.publisher.close()
            logger.info("market-ingest stopped asset=%s", self.asset)

    async def stop(self) -> None:
        self._stop.set()


async def _build_and_run() -> int:
    """Production entrypoint. INGEST_ASSET=stock|futures selects feed + universe."""
    import os
    import signal as signal_mod

    import redis.asyncio as aioredis

    from services.monitoring.tick_stream_publisher import (
        TickStreamPublisher,
        TickStreamPublisherConfig,
    )
    from shared.kis.auth import KISAuthConfig

    asset = os.environ.get("INGEST_ASSET", "").strip().lower()
    if asset not in ("stock", "futures"):
        logger.error("INGEST_ASSET must be 'stock' or 'futures' (got %r)", asset)
        return 64

    publisher = TickStreamPublisher(TickStreamPublisherConfig.from_env())

    cleanup_redis: Any | None = None
    if asset == "stock":
        from shared.kis.stock_feed import KISStockPriceFeed

        auth = KISAuthConfig(
            app_key=os.environ.get("KIS_STOCK_APP_KEY", ""),
            app_secret=os.environ.get("KIS_STOCK_APP_SECRET", ""),
            is_real=os.environ.get("KIS_STOCK_MARKET", "mock").lower() == "real",
        )
        feed: Any = KISStockPriceFeed(config=auth)
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        redis_client = aioredis.from_url(redis_url)
        cleanup_redis = redis_client
        target_key = os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
        )
        max_symbols = int(os.environ.get("INGEST_MAX_SYMBOLS", "40"))

        async def symbol_provider() -> list[str]:
            raw = await redis_client.get(target_key)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            return _parse_trade_targets(raw, max_symbols)

        refresh_interval = float(os.environ.get("INGEST_REFRESH_SECONDS", "30"))
        restart_on_change = False
    else:
        from shared.collector.historical.futures import get_front_month_code
        from shared.kis.futures_feed import KISFuturesPriceFeed

        auth = KISAuthConfig(
            app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
            app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
            is_real=os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real",
        )
        feed = KISFuturesPriceFeed(config=auth)

        async def symbol_provider() -> list[str]:
            return [get_front_month_code(product="mini")]

        # Re-resolve hourly so a quarterly rollover triggers a restart-on-change.
        refresh_interval = float(os.environ.get("INGEST_REFRESH_SECONDS", "3600"))
        restart_on_change = True

    daemon = MarketIngestDaemon(
        asset=asset,
        feed=feed,
        publisher=publisher,
        symbol_provider=symbol_provider,
        refresh_interval_seconds=refresh_interval,
        restart_on_symbol_change=restart_on_change,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        if cleanup_redis is not None:
            await cleanup_redis.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
