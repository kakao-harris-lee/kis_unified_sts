"""Decision-engine daemon — Setup A/C → signal.candidate.futures.

Phase 4 Task 10. Polls a context provider on a fixed cadence (default
~1 minute), runs each registered :class:`Setup` (A_gap_reversion,
C_event_reaction) against the snapshot, and publishes any emitted
:class:`Signal` to ``signal.candidate.futures`` (live) /
``signal.candidate.futures.shadow`` (shadow) for the risk_filter daemon
(Task 11) to consume.

The ``context_provider`` is an injected async callable returning either a
:class:`MarketContext` or None. The production wiring (live KIS feed +
overnight macro + scheduled events) is heavier than this PR's scope and
will be supplied by the parent runtime: this module just runs the
"context → setup → publish" loop. Tests inject a stub provider that
yields pre-built contexts.

Error taxonomy:
- Setup raises          → log + skip that setup (other setups still run)
- context_provider None → tick produces no signal; sleep until next tick
- redis xadd failure    → propagated; the supervisor restarts the daemon
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from shared.config.runtime_defaults import redis_url_from_env
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup
from shared.streaming.parquet_warmup import (
    warmup_engine_from_parquet as _warmup_engine_from_parquet,
)

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class DecisionEngineDaemon:
    def __init__(
        self,
        *,
        redis: Any,
        setups: list[Setup],
        context_provider: Callable[[], Awaitable[MarketContext | None]],
        candidate_stream: str,
        candidate_maxlen: int,
        tick_interval_seconds: float,
    ) -> None:
        self.redis = redis
        self.setups = setups
        self.context_provider = context_provider
        self.candidate_stream = candidate_stream
        self.candidate_maxlen = candidate_maxlen
        self.tick_interval_seconds = tick_interval_seconds
        self._stop = asyncio.Event()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                ctx = await self.context_provider()
            except Exception:
                logger.exception("context_provider raised; sleeping and retrying")
                await asyncio.sleep(self.tick_interval_seconds)
                continue

            if ctx is None:
                await asyncio.sleep(self.tick_interval_seconds)
                continue

            for setup in self.setups:
                try:
                    signal = setup.check(ctx)
                except Exception:
                    logger.exception(
                        "setup %s raised; skipping this tick",
                        setup.__class__.__name__,
                    )
                    continue
                if signal is None:
                    continue

                try:
                    await self._publish(signal)
                except Exception:
                    logger.exception(
                        "publish to %s failed; signal dropped (%s)",
                        self.candidate_stream,
                        signal.setup_type,
                    )

            await asyncio.sleep(self.tick_interval_seconds)

    async def stop(self) -> None:
        self._stop.set()

    async def _publish(self, signal) -> None:
        fields = signal.to_stream_dict()
        # Issue a fresh signal_id per emission so downstream consumers can
        # de-dupe and trace through risk_filter / order_router / order_fills.
        fields["signal_id"] = uuid.uuid4().hex
        await self.redis.xadd(
            self.candidate_stream,
            fields,
            maxlen=self.candidate_maxlen,
            approximate=True,
        )
        await self.redis.expire(self.candidate_stream, _STREAM_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Flag helpers — module-level so tests can import them directly
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    import os

    return os.getenv("FUTURES_STRATEGY_DAEMON", "off").strip().lower()


def _candidate_stream_for(mode: str) -> str:
    """Map a mode string to the Redis stream name for signal candidates.

    shadow → isolated shadow stream; any other value (off / live) → the live
    candidate stream. Bases mirror the stock chain (F-1): asset-infixed, with a
    `.shadow` suffix for the shadow form.
    """
    return (
        "signal.candidate.futures.shadow"
        if mode == "shadow"
        else "signal.candidate.futures"
    )


def _is_producing_mode(mode: str) -> bool:
    """True when the daemon builds a REAL context provider (shadow|live).

    off / unset / unknown → False → inert stub (no candidates emitted). The
    candidate stream is mode-correct via _candidate_stream_for regardless.
    """
    return mode in ("shadow", "live")


# ---------------------------------------------------------------------------
# Context-provider builder (shadow|live)
# ---------------------------------------------------------------------------


async def _build_context_provider(
    redis_client: Any,
) -> tuple[Any, Any, Any]:
    """Wire indicator engine + StreamConsumerFeed(raw_data) + FuturesContextProvider.

    Mode-agnostic: used for both shadow and live producing modes. Returns
    ``(context_provider, feed, sync_redis)``.  The caller is responsible for
    calling ``await feed.stop()`` and ``sync_redis.close()`` on shutdown.
    """
    import os
    from datetime import UTC, datetime

    redis_url = redis_url_from_env()

    from services.decision_engine.context_provider import FuturesContextProvider
    from services.decision_engine.daily_reference import FuturesDailyReference
    from services.trading.indicator_engine import StreamingIndicatorEngine
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.decision.context import load_scheduled_events
    from shared.execution.futures_instrument import resolve_futures_instrument_from_env
    from shared.macro.base import read_latest_macro_snapshot
    from shared.storage.config import StorageConfig
    from shared.storage.market_data_store import ParquetMarketDataStore

    instrument = resolve_futures_instrument_from_env()
    symbol = instrument.symbol

    engine = StreamingIndicatorEngine()

    # Cold-start warmup: seed 1-min bars from parquet (best-effort).
    store = ParquetMarketDataStore(
        StorageConfig.load_or_default().market_data.parquet.root,
        asset_class="futures",
    )
    _warmup_engine_from_parquet(engine, store, symbol)

    feed = StreamConsumerFeed(
        redis=redis_client,
        stream=os.environ.get("FUTURES_TICK_STREAM", "raw_data"),
        indicator_engine=engine,
    )
    feed.update_symbols([symbol])
    await feed.start()

    daily_ref = FuturesDailyReference(store=store, symbol=symbol)
    macro_stream = os.environ.get("MACRO_OVERNIGHT_STREAM", "stream:macro.overnight")
    events_path = os.environ.get(
        "SCHEDULED_EVENTS_PATH", "config/scheduled_events.yaml"
    )

    # read_latest_macro_snapshot uses a SYNC redis client (xrevrange + string
    # key access).  Build a dedicated sync client with decode_responses=True
    # alongside the async client used for XADD.
    import redis as _redis_sync

    sync_redis = _redis_sync.Redis.from_url(redis_url, decode_responses=True)

    def _macro_reader() -> Any:
        return read_latest_macro_snapshot(sync_redis, macro_stream)

    def _events_provider() -> list:
        try:
            return load_scheduled_events(events_path)
        except Exception:
            return []

    provider = FuturesContextProvider(
        engine=engine,
        daily_ref=daily_ref,
        symbol=symbol,
        macro_reader=_macro_reader,
        events_provider=_events_provider,
        now_fn=lambda: datetime.now(UTC),
    )
    return provider, feed, sync_redis


async def _resolve_context_provider(
    mode: str, redis_client: Any
) -> tuple[Any, Any, Any]:
    """Return (context_provider, feed, sync_redis) for the mode.

    Producing modes (shadow|live) → real FuturesContextProvider (+ feed +
    sync_redis to close on shutdown). Otherwise an inert stub returning None,
    with feed=sync_redis=None.
    """
    if _is_producing_mode(mode):
        return await _build_context_provider(redis_client)

    async def _stub_context_provider() -> None:
        return None

    return _stub_context_provider, None, None


# ---------------------------------------------------------------------------
# Production entrypoint
# ---------------------------------------------------------------------------


async def _build_and_run() -> int:
    """Production entrypoint — flag-gated (FUTURES_STRATEGY_DAEMON=off|shadow|live).

    off / unset: inert stub (context_provider returns None, no signals emitted).
    shadow:      real context_provider → signal.candidate.futures.shadow.
    live:        real context_provider → signal.candidate.futures.
    The producer is ungated (emits candidates, not orders — order_router is the
    gated, wallet-authority stage).
    """
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)

    from shared.decision.setups.event_reaction import SetupCEventReaction
    from shared.decision.setups.gap_reversion import SetupAGapReversion

    setups = [SetupAGapReversion(), SetupCEventReaction()]
    mode = _resolve_mode()
    candidate_stream = _candidate_stream_for(mode)

    context_provider, feed, sync_redis = await _resolve_context_provider(
        mode, redis_client
    )

    daemon = DecisionEngineDaemon(
        redis=redis_client,
        setups=setups,
        context_provider=context_provider,
        candidate_stream=candidate_stream,
        candidate_maxlen=10_000,
        tick_interval_seconds=60.0,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        if feed is not None:
            await feed.stop()
        if sync_redis is not None:
            sync_redis.close()
        await redis_client.aclose()
    return 0


def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
