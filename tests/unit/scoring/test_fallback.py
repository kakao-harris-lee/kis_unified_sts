"""Tests for FallbackScorer neutral defaults."""

import pytest

from shared.news.base import NewsItem
from shared.scoring.fallback import FallbackScorer


def _news(news_id: str = "n1") -> NewsItem:
    return NewsItem(
        news_id=news_id,
        source="yonhap",
        published_at_ms=1_700_000_000_000,
        received_at_ms=1_700_000_000_500,
        title="t",
        body="b",
        url="u",
        source_version="yonhap-v1",
        lang="ko",
        keywords=[],
    )


@pytest.mark.asyncio
async def test_fallback_produces_neutral():
    fb = FallbackScorer(version="fallback-neutral-v1")
    item = await fb.score(_news("n1"))
    assert item.category == "other"
    assert item.sentiment == 0.0
    assert item.impact_score == 0.0
    assert item.direction_bias == "neutral"
    assert item.confidence == 0.0
    assert item.scorer_version == "fallback-neutral-v1"
    assert item.news_id == "n1"


@pytest.mark.asyncio
async def test_fallback_preserves_raw_ref():
    fb = FallbackScorer(version="fallback-neutral-v1")
    item = await fb.score(_news("n1"))
    assert item.reasoning.startswith("fallback:")
