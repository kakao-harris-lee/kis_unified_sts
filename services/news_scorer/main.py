"""News scoring consumer-group daemon.

Reads from ``stream:news.raw`` using a Redis consumer-group (XREADGROUP /
XACK), scores each item via an injected :class:`~shared.scoring.base.Scorer`,
and fan-outs the result to ``stream:news.scored`` + ClickHouse via
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
import contextlib
import json
import logging
import signal
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


class NewsScorerDaemon:
    """Consumer-group daemon that scores news items from a Redis stream.

    Args:
        redis: Async Redis client (``redis.asyncio`` or ``fakeredis.aioredis``).
        ch_client: ClickHouse async client for batched inserts.
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
        self.redis = redis
        self.scorer = scorer
        self.fallback = fallback
        self.input_stream = input_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.batch_size = batch_size
        self.xread_block_ms = xread_block_ms
        self.publisher = ScoredPublisher(
            redis=redis,
            ch_client=ch_client,
            stream=output_stream,
            maxlen=output_maxlen,
            ch_batch_size=ch_batch_size,
        )
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Main consumer loop. Blocks until :meth:`stop` is called."""
        # Create the consumer group; ignore error if it already exists (BUSYGROUP).
        with contextlib.suppress(Exception):
            await self.redis.xgroup_create(
                self.input_stream,
                self.consumer_group,
                id="0",
                mkstream=True,
            )

        try:
            while not self._stop.is_set():
                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.input_stream: ">"},
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception:
                    logger.exception("xreadgroup error; sleeping 1s before retry")
                    await asyncio.sleep(1.0)
                    continue

                # Update backlog gauge on every poll cycle (even when idle).
                await self._update_backlog_metric()

                if not messages:
                    # Yield to the event loop so other coroutines (e.g. stop signal,
                    # asyncio.sleep in tests) can run even when the stream is idle.
                    await asyncio.sleep(0)
                    continue

                for _stream, msgs in messages:
                    for msg_id, data in msgs:
                        await self._process(msg_id, data)
        finally:
            await self.publisher.flush()

    async def stop(self) -> None:
        """Signal the run loop to exit after the current batch."""
        self._stop.set()

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]) -> None:
        """Score one stream message and publish the result.

        Handles the full error taxonomy documented in the module docstring:
        parse errors are dropped+ACKed; known scorer failures use fallback+ACK;
        unknown failures leave the message pending for retry.
        """
        # --- parse ---
        try:
            news = _news_from_stream_fields(fields)
        except Exception:
            record_news_scoring_error("parse_error")
            logger.exception(
                "Unparseable stream message; ACKing to avoid poison-pill loop"
            )
            await self.redis.xack(self.input_stream, self.consumer_group, msg_id)
            return

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
            # Do NOT ACK — leave pending so the message can be retried.
            return

        record_news_scoring_duration(
            self.scorer.version, asyncio.get_event_loop().time() - start
        )

        if used_fallback:
            logger.debug(
                "Fallback scorer used reason=%s news_id=%s",
                fallback_reason,
                news.news_id,
            )

        # --- publish ---
        try:
            await self.publisher.publish(item)
        except Exception:
            record_news_scoring_error("publish_error")
            logger.exception(
                "Publisher failed news_id=%s; leaving message pending", news.news_id
            )
            # Do NOT ACK — leave pending so the message can be retried.
            return

        # --- ACK ---
        await self.redis.xack(self.input_stream, self.consumer_group, msg_id)

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


async def _build_and_run() -> int:
    """Instantiate all dependencies from environment/config and run the daemon.

    Called by :func:`main`. Not exercised by integration tests (they inject
    a pre-built daemon directly).
    """
    import os
    import socket

    import redis.asyncio as aioredis
    from openai import AsyncOpenAI

    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
    from shared.scoring.budget import DailyBudget
    from shared.scoring.config import NewsScorerConfig
    from shared.scoring.fallback import FallbackScorer
    from shared.scoring.llm_scorer import LLMScorer

    cfg = NewsScorerConfig.from_yaml()

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    ch_config = ClickHouseConfig.from_env(database="kospi")
    ch_client = AsyncClickHouseClient(ch_config)
    await ch_client.connect()

    openai_client = AsyncOpenAI(api_key=os.environ[cfg.scorer.api_key_env])
    budget = DailyBudget(redis_client, daily_usd_limit=cfg.budget.daily_usd_limit)
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
