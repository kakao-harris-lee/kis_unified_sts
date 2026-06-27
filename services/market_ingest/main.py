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

from shared.config.runtime_defaults import redis_url_from_env

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
        rest_price_fetcher: (
            Callable[[str], Awaitable[dict[str, Any] | None]] | None
        ) = None,
        rest_poll_interval_seconds: float = 15.0,
        ws_unhealthy_grace_seconds: float = 120.0,
        session_gate: Callable[[], bool] | None = None,
        rest_rate_limited: Callable[[], bool] | None = None,
    ) -> None:
        self.asset = asset
        self.feed = feed
        self.publisher = publisher
        self.symbol_provider = symbol_provider
        self.refresh_interval_seconds = refresh_interval_seconds
        self.restart_on_symbol_change = restart_on_symbol_change
        # REST fallback: when the WS feed goes stale (KIS resets the connection),
        # poll KIS REST for current prices and republish via the SAME publish path
        # so downstream (M4-P) sees no difference. Disabled when no fetcher is
        # injected (unit tests, or a feed with no REST equivalent).
        self.rest_price_fetcher = rest_price_fetcher
        self.rest_poll_interval_seconds = rest_poll_interval_seconds
        # Grace defaults to 120s to match the futures MarketDataProvider's
        # startup_grace: KIS WS often delivers first ticks per-symbol staggered
        # right after open, and a shorter window caused REST-fallback storms.
        self.ws_unhealthy_grace_seconds = ws_unhealthy_grace_seconds
        self.session_gate = session_gate
        # When the KIS client is rate-limited (EGW00201 penalty/cooldown) — the
        # likely state during the very outage that triggers fallback — skip the
        # poll instead of blocking minutes inside acquire(). Mirrors the futures
        # _rest_poll_loop is_rate_limited short-circuit.
        self.rest_rate_limited = rest_rate_limited
        self._symbols: list[str] = []
        self._stop = asyncio.Event()
        self._rest_active = False

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

    def _enqueue_new_symbol_coverage(self, new_symbols: list[str]) -> None:
        """Queue newly-admitted stock symbols for on-entry deep daily backfill.

        Best-effort: a freshly-admitted universe symbol needs >= 200 daily bars
        for SMA(200)/pattern_pullback, but KIS serves only ~100 bars/call so it
        starts shallow. We enqueue the *added* codes to Redis; a scheduler worker
        (``sts stock-backfill ensure-coverage``) drains the queue and deepens
        them. This container's data mount is read-only, so detection (here) is
        decoupled from execution (scheduler). Never breaks the ingest loop.
        """
        if self.asset != "stock":
            return
        added = [s for s in new_symbols if s not in set(self._symbols)]
        if not added:
            return
        try:
            from shared.collector.historical.coverage import enqueue_symbols

            enqueue_symbols(added)
        except Exception as exc:  # noqa: BLE001 - never break ingest on coverage hook
            logger.warning("coverage enqueue hook failed: %s", exc)

    def _feed_is_healthy(self) -> bool:
        """True if the WS feed is delivering fresh ticks.

        Feeds without ``is_healthy`` introspection (e.g. test doubles) are
        treated as healthy so the REST fallback stays dormant for them.
        """
        is_healthy = getattr(self.feed, "is_healthy", None)
        if not callable(is_healthy):
            return True
        try:
            return bool(is_healthy())
        except Exception:
            return False

    async def _poll_rest_once(self) -> None:
        """Fetch each subscribed symbol's price via REST and republish it."""
        symbols = list(self._symbols)
        if not symbols or self.rest_price_fetcher is None:
            return
        if self.rest_rate_limited is not None and self.rest_rate_limited():
            logger.warning(
                "REST fallback: KIS client rate-limited, skipping poll asset=%s",
                self.asset,
            )
            return
        published = 0
        for symbol in symbols:
            if self._stop.is_set():
                break
            try:
                data = await self.rest_price_fetcher(symbol)
                if data:
                    self.publisher.publish(self.asset, symbol, data)
                    published += 1
            except Exception:
                logger.warning(
                    "REST fallback fetch/publish failed asset=%s symbol=%s",
                    self.asset,
                    symbol,
                    exc_info=True,
                )
                continue
        if published:
            logger.warning(
                "REST fallback active: WS feed stale, republished %d/%d %s prices",
                published,
                len(symbols),
                self.asset,
            )

    async def _rest_fallback_loop(self) -> None:
        """Poll KIS REST while the WS feed is stale (KIS reset / outage).

        Only runs during the regular session — off-hours and on holidays KIS
        REST returns a stale last-close that would be stamped ``now`` and could
        mislead the strategy, so polling is gated by ``session_gate``.
        """
        if self.rest_price_fetcher is None:
            return  # fallback disabled
        unhealthy_for = 0.0
        while not self._stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.rest_poll_interval_seconds
                )
            if self._stop.is_set():
                break
            if self.session_gate is not None and not self.session_gate():
                unhealthy_for = 0.0
                self._rest_active = False
                continue
            if self._feed_is_healthy():
                if self._rest_active:
                    logger.info(
                        "REST fallback: WS feed recovered asset=%s, stopping REST poll",
                        self.asset,
                    )
                unhealthy_for = 0.0
                self._rest_active = False
                continue
            # WS unhealthy — give it a grace window to self-recover before polling.
            unhealthy_for += self.rest_poll_interval_seconds
            if unhealthy_for < self.ws_unhealthy_grace_seconds:
                continue
            self._rest_active = True
            await self._poll_rest_once()

    def _on_fallback_done(self, task: asyncio.Task) -> None:
        """Surface a fallback-loop crash immediately.

        asyncio task exceptions are silent unless retrieved; without this a crash
        in the fallback loop would silently disable REST failover for the rest of
        the session (the exact scenario the feature exists to cover).
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "REST fallback loop crashed asset=%s: %r", self.asset, exc, exc_info=exc
            )

    async def run(self) -> None:
        self.feed.set_tick_callback(self._on_tick)
        symbols = await self.symbol_provider()
        self._symbols = symbols
        self.feed.update_symbols(symbols)
        await self.feed.start()
        logger.info(
            "market-ingest started asset=%s symbols=%d", self.asset, len(symbols)
        )
        fallback_task = asyncio.create_task(self._rest_fallback_loop())
        fallback_task.add_done_callback(self._on_fallback_done)
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
                    self._enqueue_new_symbol_coverage(new_symbols)
                    await self._apply_symbols(new_symbols)
                elif not new_symbols:
                    logger.debug(
                        "symbol_provider returned empty list; keeping current symbols"
                    )
        finally:
            fallback_task.cancel()
            # Suppress BOTH the expected CancelledError AND any exception the task
            # already died with (already logged by _on_fallback_done) so feed/
            # publisher cleanup below always runs and the original error isn't
            # masked.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await fallback_task
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
    cleanup_kis: Any | None = None
    rest_price_fetcher: Callable[[str], Awaitable[dict[str, Any] | None]] | None = None
    session_gate: Callable[[], bool] | None = None
    rest_rate_limited: Callable[[], bool] | None = None
    if asset == "stock":
        from shared.kis.stock_feed import KISStockPriceFeed

        auth = KISAuthConfig(
            app_key=os.environ.get("KIS_STOCK_APP_KEY", ""),
            app_secret=os.environ.get("KIS_STOCK_APP_SECRET", ""),
            is_real=os.environ.get("KIS_STOCK_MARKET", "mock").lower() == "real",
        )
        feed: Any = KISStockPriceFeed(config=auth)
        # REST fallback so a KIS WS reset doesn't blind the decoupled stock
        # pipeline (the futures orchestrator already fails over to REST). Gated
        # to the regular session so off-hours/holiday last-closes aren't
        # republished as live ticks.
        if os.environ.get("INGEST_REST_FALLBACK_ENABLED", "true").lower() == "true":
            from shared.kis.client import KISClient
            from shared.strategy.market_time import is_regular_session_open

            kis_client = KISClient(auth)
            cleanup_kis = kis_client
            rest_price_fetcher = kis_client.get_current_price
            session_gate = is_regular_session_open
            rest_rate_limited = lambda: kis_client.is_rate_limited  # noqa: E731
        redis_url = redis_url_from_env()
        redis_client = aioredis.from_url(redis_url)
        cleanup_redis = redis_client
        from services.stock_strategy.universe import parse_watchlist_codes

        target_key = os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
        )
        watchlist_key = os.environ.get(
            "STOCK_WATCHLIST_KEY", "system:daily_watchlist:latest"
        )
        max_symbols = int(os.environ.get("INGEST_MAX_SYMBOLS", "40"))

        async def _get_text(key: str) -> str | None:
            raw = await redis_client.get(key)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            return raw

        async def symbol_provider() -> list[str]:
            # Tick the UNION of fusion trade_targets and the stock-strategy's
            # daily-watchlist universe. The two sources read different keys and
            # can diverge intraday; ticking only trade_targets starves the
            # strategy of data for watchlist-only symbols (no signals).
            merged: dict[str, None] = {}
            for code in _parse_trade_targets(await _get_text(target_key), max_symbols):
                merged.setdefault(code, None)
            for code in parse_watchlist_codes(
                await _get_text(watchlist_key), max_symbols=max_symbols
            ):
                merged.setdefault(code, None)
            return list(merged)[:max_symbols]

        refresh_interval = float(os.environ.get("INGEST_REFRESH_SECONDS", "30"))
        restart_on_change = False
    else:
        from shared.execution.futures_instrument import (
            resolve_futures_instrument_from_env,
        )
        from shared.kis.futures_feed import KISFuturesPriceFeed

        auth = KISAuthConfig(
            app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
            app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
            is_real=os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real",
        )
        feed = KISFuturesPriceFeed(config=auth)

        async def symbol_provider() -> list[str]:
            return [resolve_futures_instrument_from_env().symbol]

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
        rest_price_fetcher=rest_price_fetcher,
        rest_poll_interval_seconds=float(
            os.environ.get("INGEST_REST_POLL_SECONDS", "15")
        ),
        ws_unhealthy_grace_seconds=float(
            os.environ.get("INGEST_REST_GRACE_SECONDS", "120")
        ),
        session_gate=session_gate,
        rest_rate_limited=rest_rate_limited,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        if cleanup_redis is not None:
            await cleanup_redis.aclose()
        if cleanup_kis is not None:
            await cleanup_kis.close()
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
