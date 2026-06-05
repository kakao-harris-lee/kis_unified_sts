"""End-to-end integration tests for NewsScorerDaemon.

Uses ``fakeredis.aioredis`` for Redis isolation. The primary scorer and fallback are replaced with
``_FakeScorer`` — a lightweight in-process stub that avoids any real I/O.

Test coverage
-------------
- Happy path: score succeeds → item published to stream:news.scored + XACK
- ScoringValidationError → fallback scorer invoked → stream entry is the
  fallback version + XACK
- Unknown exception → NO XACK (message stays pending)
- Parse error on stream fields → XACK (drop poison-pill)
- BudgetExceeded → fallback + XACK
- TimeoutError → fallback + XACK
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.news_scorer.main import NewsScorerDaemon
from shared.news.base import NewsItem
from shared.scoring.base import ScoredItem, Scorer
from shared.scoring.budget import BudgetExceeded
from shared.scoring.validators import ScoringValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeScorer(Scorer):
    """Deterministic scorer stub that cycles through a pre-configured list of outcomes."""

    version = "fake-v1"

    def __init__(self, outcomes: list | None = None) -> None:
        self._outcomes: list = outcomes if outcomes is not None else ["ok"]
        self._idx = 0

    async def score(self, news: NewsItem) -> ScoredItem:
        outcome = self._outcomes[min(self._idx, len(self._outcomes) - 1)]
        self._idx += 1
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, type) and issubclass(outcome, Exception):
            raise outcome()
        return ScoredItem(
            news_id=news.news_id,
            scorer_version=self.version,  # use instance version so overrides work
            scored_at_ms=1_700_000_000_000,
            category="macro_us",
            sentiment=0.4,
            impact_score=0.8,
            direction_bias="long",
            confidence=0.85,
            keywords=["k"],
            reasoning="r",
            raw_ref="",
        )


async def _seed_raw(redis: fakeredis.aioredis.FakeRedis, news_id: str = "n1") -> None:
    """Push one raw news message onto stream:news.raw."""
    await redis.xadd(
        "stream:news.raw",
        {
            "news_id": news_id,
            "source": "yonhap",
            "published_at_ms": "1700000000000",
            "received_at_ms": "1700000000500",
            "title": "t",
            "body": "b",
            "url": "u",
            "source_version": "yonhap-v1",
            "lang": "ko",
            "keywords_json": json.dumps([]),
        },
    )


def _make_daemon(
    redis: fakeredis.aioredis.FakeRedis,
    scorer: Scorer,
    fallback: Scorer,
    archive_client: AsyncMock | None = None,
) -> NewsScorerDaemon:
    if archive_client is None:
        archive_client = AsyncMock()
    return NewsScorerDaemon(
        redis=redis,
        archive_client=archive_client,
        scorer=scorer,
        fallback=fallback,
        input_stream="stream:news.raw",
        output_stream="stream:news.scored",
        consumer_group="news_scorer-v1",
        worker_id="worker-test",
        output_maxlen=100,
        archive_batch_size=1,
        xread_block_ms=100,
        batch_size=10,
    )


async def _run_daemon_briefly(daemon: NewsScorerDaemon, seconds: float = 0.6) -> None:
    """Start the daemon, let it run briefly, then stop and await completion."""
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(seconds)
    await daemon.stop()
    await task


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daemon_scores_and_acks() -> None:
    """Happy path: primary scorer succeeds → stream entry published + ACKed."""
    redis = fakeredis.aioredis.FakeRedis()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=["ok"])
    fallback = _FakeScorer(outcomes=["ok"])
    fallback.version = "fallback-neutral-v1"

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon)

    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1, "Expected one entry in scored stream"
    assert entries[0][1][b"news_id"] == b"n1"
    assert entries[0][1][b"raw_source"] == b"yonhap"
    assert entries[0][1][b"raw_title"] == b"t"

    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0, "Message should have been ACKed"


@pytest.mark.asyncio
async def test_daemon_falls_back_on_scoring_validation_error() -> None:
    """ScoringValidationError → fallback scorer used, scored entry has fallback version."""
    redis = fakeredis.aioredis.FakeRedis()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=[ScoringValidationError("bad json")])
    fallback = _FakeScorer(outcomes=["ok"])
    fallback.version = "fallback-neutral-v1"

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon)

    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1
    assert entries[0][1][b"scorer_version"] == b"fallback-neutral-v1"

    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_daemon_falls_back_on_budget_exceeded() -> None:
    """BudgetExceeded → fallback scorer used + message ACKed."""
    redis = fakeredis.aioredis.FakeRedis()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=[BudgetExceeded("cap hit")])
    fallback = _FakeScorer(outcomes=["ok"])
    fallback.version = "fallback-neutral-v1"

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon)

    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1
    assert entries[0][1][b"scorer_version"] == b"fallback-neutral-v1"

    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_daemon_falls_back_on_timeout() -> None:
    """TimeoutError → fallback scorer used + message ACKed."""
    redis = fakeredis.aioredis.FakeRedis()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=[TimeoutError("slow")])
    fallback = _FakeScorer(outcomes=["ok"])
    fallback.version = "fallback-neutral-v1"

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon)

    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1
    assert entries[0][1][b"scorer_version"] == b"fallback-neutral-v1"

    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_daemon_does_not_ack_on_unknown_exception() -> None:
    """Unknown scorer exception → NO XACK (message remains pending for retry)."""
    redis = fakeredis.aioredis.FakeRedis()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=[RuntimeError("mystery failure")])
    fallback = _FakeScorer(outcomes=["ok"])

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon)

    # Scored stream should be empty (no publish without ACK).
    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 0

    # The message must still be pending.
    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 1


@pytest.mark.asyncio
async def test_daemon_acks_on_parse_error() -> None:
    """A structurally broken stream message (missing fields) is ACKed to avoid retry loops.

    We push a message with no fields at all; _news_from_stream_fields should
    produce a NewsItem with empty/zero values.  To trigger an actual parse
    error we rely on the fact that int("") raises ValueError — achieved by
    sending an explicitly bad int field.
    """
    redis = fakeredis.aioredis.FakeRedis()
    # Push a message with a non-integer published_at_ms to trigger parse error.
    await redis.xadd(
        "stream:news.raw",
        {
            "news_id": "bad",
            "source": "test",
            "published_at_ms": "NOT_AN_INT",
            "received_at_ms": "1700000000500",
            "title": "t",
            "body": "b",
            "url": "u",
            "source_version": "v1",
            "lang": "ko",
            "keywords_json": "[]",
        },
    )

    scorer = _FakeScorer(outcomes=["ok"])
    fallback = _FakeScorer(outcomes=["ok"])

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon)

    # Message should have been ACKed (dropped).
    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_daemon_processes_multiple_messages() -> None:
    """Multiple seeded messages are all scored and ACKed."""
    redis = fakeredis.aioredis.FakeRedis()
    for i in range(3):
        await _seed_raw(redis, f"n{i}")

    scorer = _FakeScorer(outcomes=["ok", "ok", "ok"])
    fallback = _FakeScorer(outcomes=["ok"])

    daemon = _make_daemon(redis, scorer, fallback)
    await _run_daemon_briefly(daemon, seconds=0.8)

    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 3

    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_daemon_does_not_ack_on_publish_failure() -> None:
    """Publisher failure → NO XACK (message stays pending)."""
    redis = fakeredis.aioredis.FakeRedis()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=["ok"])
    fallback = _FakeScorer(outcomes=["ok"])

    daemon = _make_daemon(redis, scorer, fallback)
    daemon.publisher.publish = AsyncMock(side_effect=RuntimeError("publish down"))
    await _run_daemon_briefly(daemon)

    # The message must remain pending for redelivery.
    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 1
