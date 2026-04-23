"""News collector daemon — polls sources, dedups, publishes to Redis + CH."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from typing import Any

from services.monitoring.metrics import (
    record_news_collected,
    record_news_duplicate,
    record_news_error,
)
from shared.news.base import NewsSource
from shared.news.dedupe import NewsDedupe
from shared.news.publisher import ClickHouseNewsWriter, NewsStreamPublisher

logger = logging.getLogger(__name__)


class NewsCollectorDaemon:
    """Orchestrates N sources. Each source runs in its own isolated loop."""

    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        sources: list[NewsSource],
        stream: str,
        stream_maxlen: int,
        dedupe_memory: int,
        dedupe_ttl_days: int,
        ch_batch_size: int,
        ch_flush_interval: int,
        body_truncate_chars: int,
    ):
        self.redis = redis
        self.sources = sources
        self.publisher = NewsStreamPublisher(redis, stream=stream, maxlen=stream_maxlen)
        self.dedupe = NewsDedupe(
            redis, memory_size=dedupe_memory, ttl_days=dedupe_ttl_days
        )
        self.ch_writer = ClickHouseNewsWriter(
            ch_client,
            batch_size=ch_batch_size,
            flush_interval_seconds=ch_flush_interval,
        )
        self.body_truncate_chars = body_truncate_chars
        self._stop = asyncio.Event()

    async def run(self) -> None:
        flush_task = asyncio.create_task(self.ch_writer.run_periodic_flush(self._stop))
        source_tasks = [asyncio.create_task(self._loop(s)) for s in self.sources]
        try:
            await self._stop.wait()
        finally:
            for t in source_tasks:
                t.cancel()
            await asyncio.gather(*source_tasks, return_exceptions=True)
            await flush_task  # triggers final flush

    async def stop(self) -> None:
        self._stop.set()

    async def _loop(self, source: NewsSource) -> None:
        while not self._stop.is_set():
            try:
                async for item in source.fetch():
                    if await self.dedupe.is_duplicate(item.news_id):
                        record_news_duplicate(source.name)
                        continue
                    await self.dedupe.mark_seen(item.news_id)
                    await self.publisher.publish(
                        item, max_body_chars=self.body_truncate_chars
                    )
                    record_news_collected(source.name)
                    await self.ch_writer.enqueue(item)
            except asyncio.CancelledError:
                raise
            except Exception:
                record_news_error(source.name, "fetch_cycle")
                logger.exception("source=%s fetch cycle failed", source.name)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop.wait(), timeout=source.poll_interval_seconds
                )


async def _build_and_run_from_config() -> int:
    """Production entry point. Resolves sources from YAML config.

    CONCERN: ClickHouseClient.get_instance().async_client does not exist in this
    codebase. The actual pattern is AsyncClickHouseClient from shared.db.client.
    We instantiate AsyncClickHouseClient directly and connect it here.
    # WIP: real CH client wiring — integration test does not hit CH
    """
    import os

    import aiohttp
    import redis.asyncio as aioredis

    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
    from shared.news.config import NewsCollectorConfig
    from shared.news.sources.reuters import ReutersRSSSource
    from shared.news.sources.yonhap import YonhapRSSSource

    cfg = NewsCollectorConfig.from_yaml()
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    # Real CH client wiring — AsyncClickHouseClient, not a non-existent get_instance()
    ch = AsyncClickHouseClient(ClickHouseConfig.from_env(database="kospi"))
    await ch.connect()

    session = aiohttp.ClientSession()
    sources: list[NewsSource] = []
    if cfg.sources.yonhap.enabled:
        sources.append(
            YonhapRSSSource(session=session, rss_url=cfg.sources.yonhap.rss_url)
        )
    if cfg.sources.reuters.enabled:
        sources.append(
            ReutersRSSSource(session=session, rss_url=cfg.sources.reuters.rss_url)
        )
    if cfg.sources.dart.enabled:
        try:
            from shared.llm.collectors import DARTDataCollector  # reuse existing
            from shared.news.sources.dart import DARTNewsSource

            sources.append(DARTNewsSource(collector=DARTDataCollector()))
        except ImportError:
            logger.warning("DARTDataCollector unavailable — skipping DART source")
    if cfg.sources.mk.enabled:
        try:
            from shared.llm.collectors import MKStockNewsCollector
            from shared.news.sources.mk_adapter import MKNewsSourceAdapter

            sources.append(MKNewsSourceAdapter(underlying=MKStockNewsCollector()))
        except ImportError:
            logger.warning("MKStockNewsCollector unavailable — skipping MK source")

    daemon = NewsCollectorDaemon(
        redis=redis_client,
        ch_client=ch,
        sources=sources,
        stream=cfg.redis_stream,
        stream_maxlen=cfg.redis_maxlen,
        dedupe_memory=cfg.dedupe.memory_size,
        dedupe_ttl_days=cfg.dedupe.redis_ttl_days,
        ch_batch_size=cfg.clickhouse_batch_size,
        ch_flush_interval=cfg.clickhouse_flush_interval_seconds,
        body_truncate_chars=cfg.body_truncate_chars,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await session.close()
        await redis_client.aclose()
        await ch.close()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(_build_and_run_from_config())


if __name__ == "__main__":
    import sys

    sys.exit(main())
