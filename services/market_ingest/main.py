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
from shared.exceptions import APIError, NetworkError, WebSocketDisconnectError
from shared.stock_universe import (
    build_effective_universe_snapshot,
    parse_effective_universe_codes,
    select_stock_universe,
)

logger = logging.getLogger(__name__)

# Cold-start feed failures we degrade from fatal to non-fatal. An intentional
# superset of the tuple caught by
# ``services/trading/orchestrator._start_market_data_loop``: it adds
# ``TimeoutError`` and ``ValueError`` on top of that pattern. A KIS
# ``/oauth2/Approval`` connect-timeout surfaces as ``ConnectionError`` (from
# ``requests``); a throttled/malformed approval response surfaces as
# ``ValueError`` (e.g. EGW00201). Both are exactly the crash-loop vectors this
# daemon must absorb, so ``feed.start()`` failing on any of these keeps the
# process alive and retries with backoff instead of dying (which restarts the
# container and re-hammers the approval endpoint).
_FEED_START_FAILURES = (
    NetworkError,
    WebSocketDisconnectError,
    APIError,
    OSError,
    ConnectionError,
    TimeoutError,
    ValueError,
)

SymbolProvider = Callable[[], Awaitable[list[str]]]


def _load_trade_target_codes(raw: str | None) -> list[str]:
    """Parse a trade-target payload into an uncapped code list."""

    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    return [str(c).strip() for c in payload.get("codes", []) if str(c).strip()]


def _parse_trade_targets(raw: str | None, max_symbols: int) -> list[str]:
    """Parse a ``system:trade_targets:latest`` payload into a capped code list.

    Payload shape: ``{"codes": [...], "names": {...}, "metadata": {...}}``.
    Returns ``[]`` on missing/invalid input so the daemon keeps its current
    subscription rather than crashing.
    """
    return select_stock_universe(
        trade_targets=_load_trade_target_codes(raw),
        watchlist=[],
        max_symbols=max_symbols,
    )


def _select_stock_symbols_from_payloads(
    trade_targets_raw: str | None,
    watchlist_raw: str | None,
    *,
    max_symbols: int,
    existing: list[str] | None = None,
    effective_raw: str | None = None,
    overrides_raw: str | None = None,
) -> list[str]:
    """Select the stock ingest universe using the shared cap order."""

    from services.stock_strategy.universe import parse_watchlist_codes

    effective_codes = parse_effective_universe_codes(
        effective_raw,
        field="market_data_codes",
        max_symbols=max_symbols,
    )
    if effective_codes:
        return effective_codes

    effective = build_effective_universe_snapshot(
        trade_targets_raw=trade_targets_raw,
        daily_watchlist_raw=watchlist_raw,
        overrides_raw=overrides_raw,
        existing_symbols=existing,
        max_symbols=max_symbols,
    )
    market_data_codes = effective.get("market_data_codes")
    if isinstance(market_data_codes, list) and market_data_codes:
        return [str(code) for code in market_data_codes[:max_symbols]]

    return select_stock_universe(
        trade_targets=_load_trade_target_codes(trade_targets_raw),
        watchlist=parse_watchlist_codes(watchlist_raw, max_symbols=max_symbols),
        existing=existing,
        max_symbols=max_symbols,
    )


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
        feed_start_retry_initial_seconds: float = 5.0,
        feed_start_retry_max_seconds: float = 60.0,
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
        # Cold-start feed retry backoff (exponential, capped). A KIS approval/
        # connect failure at start() is non-fatal: the daemon stays up, REST
        # fallback covers the session, and start() is retried on this schedule
        # instead of crash-looping the container. Mirrors the streaming.yaml
        # reconnect_initial_delay/reconnect_max_delay convention.
        self.feed_start_retry_initial_seconds = feed_start_retry_initial_seconds
        self.feed_start_retry_max_seconds = feed_start_retry_max_seconds
        self._symbols: list[str] = []
        self._stop = asyncio.Event()
        self._rest_active = False
        self._feed_started = False
        # The in-flight backoff feed-start retry task. One at a time: cold start
        # spawns it, and a futures rollover restart replaces it (see
        # _spawn_feed_start) so a rollover approval failure retries with the same
        # backoff instead of leaving the feed dark until the next refresh.
        self._start_task: asyncio.Task[None] | None = None

    def _on_tick(
        self, symbol: str, data: dict[str, Any], ts: datetime  # noqa: ARG002
    ) -> None:
        # Hot path: republish only. (ts is part of the feed callback contract
        # but the tick stream carries its own timestamp in `data`.)
        self.publisher.publish(self.asset, symbol, data)

    async def _apply_symbols(self, symbols: list[str]) -> None:
        if self.restart_on_symbol_change:
            # Futures feed requires update_symbols BEFORE start(); restart on change.
            # Re-run start through the SAME backoff retry task as cold start so a
            # KIS approval/connect failure during a rollover restart retries in
            # the background instead of crashing the refresh loop or leaving the
            # feed dark (futures has no REST fallback) until the next refresh.
            await self.feed.stop()
            self._feed_started = False
            self.feed.update_symbols(symbols)
            await self._spawn_feed_start()
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

    async def _start_feed(self) -> bool:
        """Start the WS feed; a cold-start KIS approval/connect failure is non-fatal.

        Returns True on success (sets ``_feed_started``), False on a caught
        transient failure. Downgrading the failure keeps the daemon process
        alive so it can retry with backoff and let REST fallback cover the
        session — instead of propagating to ``asyncio.run`` and crash-looping
        the container (the RestartCount=1268 root cause). Mirrors
        ``services/trading/orchestrator._start_market_data_loop``.
        """
        try:
            await self.feed.start()
        except _FEED_START_FAILURES as exc:
            logger.warning(
                "market-ingest feed start failed asset=%s: %r "
                "(daemon stays up; REST fallback covers the session, retrying)",
                self.asset,
                exc,
            )
            self._feed_started = False
            return False
        self._feed_started = True
        logger.info("market-ingest feed started asset=%s", self.asset)
        return True

    async def _start_feed_with_backoff(self) -> None:
        """Retry ``_start_feed`` with exponential backoff until it succeeds.

        Runs concurrently with the REST-fallback and refresh loops so a KIS
        ``/oauth2/Approval`` outage neither crashes the daemon nor blocks data
        (REST covers the session). Once the feed starts, its own reconnect
        machinery owns subsequent drops, so this loop exits after first success.
        """
        delay = self.feed_start_retry_initial_seconds
        while not self._stop.is_set():
            if await self._start_feed():
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            delay = min(delay * 2, self.feed_start_retry_max_seconds)

    async def _spawn_feed_start(self) -> None:
        """(Re)start the backoff feed-start retry task, at most one at a time.

        Awaits cancellation of any in-flight task first so a futures rollover
        restart can never race two ``feed.start()`` loops. Used by both cold
        start and the rollover restart branch so both get identical backoff.
        """
        if self._start_task is not None and not self._start_task.done():
            self._start_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._start_task
        task = asyncio.create_task(self._start_feed_with_backoff())
        task.add_done_callback(self._on_start_task_done)
        self._start_task = task

    def _on_start_task_done(self, task: asyncio.Task) -> None:
        """Surface an uncaught crash in the feed-start retry loop.

        asyncio task exceptions are silent unless retrieved; without this an
        unexpected error in the retry loop would silently disable feed startup
        for the session. The daemon still survives (REST fallback covers data).
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "market-ingest feed-start retry loop crashed asset=%s: %r",
                self.asset,
                exc,
                exc_info=exc,
            )

    async def run(self) -> None:
        self.feed.set_tick_callback(self._on_tick)
        symbols = await self.symbol_provider()
        self._symbols = symbols
        self.feed.update_symbols(symbols)
        # Wire REST fallback BEFORE starting the feed so a cold-start KIS
        # approval/connect failure still gets market data during the session
        # (is_healthy() is False while the feed is not running, so the fallback
        # loop polls REST once its grace window elapses).
        fallback_task = asyncio.create_task(self._rest_fallback_loop())
        fallback_task.add_done_callback(self._on_fallback_done)
        # Start the feed via a backoff retry task INSTEAD of a bare await: a bare
        # await propagates a KIS approval ConnectionError through asyncio.run and
        # crash-loops the container. The retry task keeps the daemon alive and
        # re-attempts on the configured backoff.
        await self._spawn_feed_start()
        logger.info(
            "market-ingest running asset=%s symbols=%d", self.asset, len(symbols)
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
                    self._enqueue_new_symbol_coverage(new_symbols)
                    await self._apply_symbols(new_symbols)
                elif not new_symbols:
                    logger.debug(
                        "symbol_provider returned empty list; keeping current symbols"
                    )
        finally:
            # Suppress BOTH the expected CancelledError AND any exception a task
            # already died with (already logged by its done-callback) so feed/
            # publisher cleanup below always runs and the original error isn't
            # masked.
            if self._start_task is not None:
                self._start_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._start_task
            fallback_task.cancel()
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

        target_key = os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
        )
        watchlist_key = os.environ.get(
            "STOCK_WATCHLIST_KEY", "system:daily_watchlist:latest"
        )
        effective_universe_key = os.environ.get(
            "STOCK_EFFECTIVE_UNIVERSE_KEY", "stock:universe:effective:latest"
        )
        overrides_key = os.environ.get(
            "STOCK_UNIVERSE_OVERRIDES_KEY", "stock:universe:overrides"
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
            return _select_stock_symbols_from_payloads(
                await _get_text(target_key),
                await _get_text(watchlist_key),
                max_symbols=max_symbols,
                effective_raw=await _get_text(effective_universe_key),
                overrides_raw=await _get_text(overrides_key),
            )

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
        feed_start_retry_initial_seconds=float(
            os.environ.get("INGEST_FEED_START_RETRY_INITIAL_SECONDS", "5")
        ),
        feed_start_retry_max_seconds=float(
            os.environ.get("INGEST_FEED_START_RETRY_MAX_SECONDS", "60")
        ),
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
