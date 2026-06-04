"""News scoring consumer-group daemon.

Reads from ``stream:news.raw`` using a Redis consumer-group (XREADGROUP /
XACK), scores each item via an injected :class:`~shared.scoring.base.Scorer`,
and fan-outs the result to ``stream:news.scored`` plus optional ClickHouse via
:class:`~shared.scoring.publisher.ScoredPublisher`.

Error taxonomy
--------------
- Parse error on stream fields  → XACK (broken message, drop rather than loop)
- ``BudgetExceeded``            → fallback score + XACK
- ``ScoringValidationError``    → fallback score + XACK
- ``TimeoutError``              → fallback score + XACK
- Unknown exception             → NO XACK (leave pending for retry)
- Publisher failure             → NO XACK (leave pending)
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from dataclasses import replace
from typing import Any

try:
    from services.monitoring.metrics import (
        record_news_scored,
        record_news_scorer_backlog,
        record_news_scoring_duration,
        record_news_scoring_error,
        record_news_scoring_fallback,
    )
except ImportError:  # pragma: no cover — metrics module unavailable in minimal envs

    def record_news_scored(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_news_scoring_duration(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_news_scoring_error(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_news_scoring_fallback(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_news_scorer_backlog(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass


from shared.news.base import NewsItem
from shared.scoring.base import Scorer
from shared.scoring.budget import BudgetExceeded
from shared.scoring.publisher import ScoredPublisher
from shared.scoring.validators import ScoringValidationError
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)


def _news_from_stream_fields(fields: dict[bytes, bytes]) -> NewsItem:
    """Parse Redis stream field dict into a :class:`NewsItem`.

    All values arrive as ``bytes``; missing optional fields fall back to
    safe defaults so that a single malformed field does not silently corrupt
    all items in the batch.

    Raises:
        Any exception from ``NewsItem.__init__`` (e.g. ValueError on bad int).
    """

    def _s(key: str, default: str = "") -> str:
        raw = fields.get(key.encode(), b"")
        return (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw or default)
        )

    return NewsItem(
        news_id=_s("news_id"),
        source=_s("source"),
        published_at_ms=int(_s("published_at_ms", "0") or 0),
        received_at_ms=int(_s("received_at_ms", "0") or 0),
        title=_s("title"),
        body=_s("body"),
        url=_s("url"),
        source_version=_s("source_version"),
        lang=_s("lang"),
        keywords=json.loads(_s("keywords_json", "[]") or "[]"),
    )


class NewsScorerDaemon(StreamStage):
    """Consumer-group daemon that scores news items from a Redis stream.

    Args:
        redis: Async Redis client (``redis.asyncio`` or ``fakeredis.aioredis``).
        ch_client: Optional ClickHouse async client for mirror inserts.
        scorer: Primary :class:`~shared.scoring.base.Scorer` (LLM-backed).
        fallback: Fallback scorer used when the primary fails gracefully.
        input_stream: Redis stream key to consume from.
        output_stream: Redis stream key to publish scored items to.
        consumer_group: Redis consumer-group name.
        worker_id: Unique consumer name within the group (typically hostname+pid).
        output_maxlen: ``MAXLEN ~`` cap for the output stream.
        ch_batch_size: Rows to buffer before flushing to ClickHouse.
        xread_block_ms: Milliseconds to block on ``XREADGROUP`` when idle.
        batch_size: Maximum number of messages to fetch per ``XREADGROUP`` call.
    """

    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        scorer: Scorer,
        fallback: Scorer,
        input_stream: str,
        output_stream: str,
        consumer_group: str,
        worker_id: str,
        output_maxlen: int,
        ch_batch_size: int,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=input_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=1.0,
        )
        self.scorer = scorer
        self.fallback = fallback
        self.publisher = ScoredPublisher(
            redis=redis,
            ch_client=ch_client,
            stream=output_stream,
            maxlen=output_maxlen,
            ch_batch_size=ch_batch_size,
        )

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]
    ) -> bool:
        """Score one stream message and publish the result.

        Returns True ⇒ framework XACKs (parse poison-pill, fallback, success);
        False ⇒ leave pending for retry (unknown scorer error, publish error).
        """
        # --- parse ---
        try:
            news = _news_from_stream_fields(fields)
        except Exception:
            record_news_scoring_error("parse_error")
            logger.exception(
                "Unparseable stream message; ACKing to avoid poison-pill loop"
            )
            return True  # poison-pill: consume (base XACKs)

        # --- score ---
        start = asyncio.get_event_loop().time()
        used_fallback = False
        fallback_reason: str | None = None

        try:
            item = await self.scorer.score(news)
            record_news_scored(self.scorer.version, item.category)
        except BudgetExceeded:
            item = await self.fallback.score(news)
            used_fallback = True
            fallback_reason = "budget"
            record_news_scoring_fallback("budget")
        except ScoringValidationError:
            item = await self.fallback.score(news)
            used_fallback = True
            fallback_reason = "json_error"
            record_news_scoring_fallback("json_error")
        except TimeoutError:
            item = await self.fallback.score(news)
            used_fallback = True
            fallback_reason = "timeout"
            record_news_scoring_fallback("timeout")
        except Exception:
            record_news_scoring_error("scorer_unknown")
            logger.exception(
                "Unhandled scorer error news_id=%s; leaving message pending",
                news.news_id,
            )
            return False  # leave pending for retry (base does NOT XACK)

        record_news_scoring_duration(
            self.scorer.version, asyncio.get_event_loop().time() - start
        )

        if used_fallback:
            logger.debug(
                "Fallback scorer used reason=%s news_id=%s",
                fallback_reason,
                news.news_id,
            )
        item = _attach_raw_news_context(item, news, msg_id)

        # --- publish ---
        try:
            await self.publisher.publish(item)
        except Exception:
            record_news_scoring_error("publish_error")
            logger.exception(
                "Publisher failed news_id=%s; leaving message pending", news.news_id
            )
            return False  # leave pending for retry (base does NOT XACK)

        return True  # success: framework XACKs

    async def post_poll(self, message_count: int) -> None:
        await self._update_backlog_metric()

    async def on_shutdown(self) -> None:
        await self.publisher.flush()

    async def _update_backlog_metric(self) -> None:
        """Query XPENDING and update the backlog gauge. Errors are non-fatal."""
        try:
            info = await self.redis.xpending(self.input_stream, self.consumer_group)
            # redis-py returns a dict; fakeredis may return a list/tuple.
            if isinstance(info, dict):
                count = int(info.get("pending", 0))
            elif info:
                count = int(info[0])
            else:
                count = 0
            record_news_scorer_backlog(count)
        except Exception:
            logger.debug("Backlog metric query failed", exc_info=True)


def _attach_raw_news_context(
    item: Any,
    news: NewsItem,
    msg_id: bytes | str,
) -> Any:
    """Return a scored item enriched with source metadata for downstream joins."""
    raw_ref = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
    return replace(
        item,
        raw_ref=raw_ref,
        raw_source=news.source,
        raw_title=news.title,
        raw_url=news.url,
        raw_published_at_ms=news.published_at_ms,
        raw_keywords=list(news.keywords),
    )


async def _build_and_run() -> int:
    """Instantiate all dependencies from environment/config and run the daemon.

    Called by :func:`main`. Not exercised by integration tests (they inject
    a pre-built daemon directly).
    """
    import os
    import socket

    import redis.asyncio as aioredis
    from openai import AsyncOpenAI

    from shared.scoring.budget import DailyBudget
    from shared.scoring.config import NewsScorerConfig
    from shared.scoring.fallback import FallbackScorer
    from shared.scoring.llm_scorer import LLMScorer
    from shared.storage import create_async_clickhouse_client
    from shared.storage.config import StorageConfig

    cfg = NewsScorerConfig.from_yaml()

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    ch_client = None
    storage_config = StorageConfig.load_or_default()
    if storage_config.runtime_storage.clickhouse_mirror.enabled:
        ch_client = await create_async_clickhouse_client(database="kospi")

    openai_client = AsyncOpenAI(api_key=os.environ[cfg.scorer.api_key_env])
    budget = DailyBudget(
        redis_client,
        daily_usd_limit=cfg.budget.daily_usd_limit,
        key_prefix=cfg.budget.key_prefix,
    )
    llm = LLMScorer(
        client=openai_client,
        budget=budget,
        model=cfg.scorer.model,
        version=cfg.scorer.version,
        temperature=cfg.scorer.temperature,
        max_tokens=cfg.scorer.max_tokens,
        timeout_seconds=cfg.scorer.timeout_seconds,
        retries=cfg.scorer.retries,
        body_max_chars=cfg.body_truncate_chars,
    )
    fallback = FallbackScorer()

    worker_id = f"{cfg.worker_id_prefix}-{socket.gethostname()}-{os.getpid()}"
    daemon = NewsScorerDaemon(
        redis=redis_client,
        ch_client=ch_client,
        scorer=llm,
        fallback=fallback,
        input_stream=cfg.input_stream,
        output_stream=cfg.output_stream,
        consumer_group=cfg.consumer_group,
        worker_id=worker_id,
        output_maxlen=cfg.output_stream_maxlen,
        ch_batch_size=cfg.ch_batch_size,
        xread_block_ms=cfg.xread_block_ms,
        batch_size=cfg.batch_size,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await openai_client.close()
        await redis_client.aclose()
        if ch_client is not None:
            await ch_client.close()

    return 0


def main() -> int:
    """Synchronous entry-point for the news scorer service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
