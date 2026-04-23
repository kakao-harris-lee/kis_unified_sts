from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.news.sources.mk_adapter import MKNewsSourceAdapter


@pytest.mark.asyncio
async def test_mk_adapter_yields_raw_items_without_sentiment():
    underlying = MagicMock()
    underlying.fetch_market_news = AsyncMock(
        return_value=[
            {
                "id": "mk_001",
                "title": "코스피 2% 상승",
                "content": "장중 2% 상승...",
                "url": "https://mk.co.kr/...1",
                "published_at_ms": 1_700_000_000_000,
                # should ignore these:
                "sentiment": "긍정",
                "sentiment_score": 0.7,
            },
            {
                "title": "no-id filtered",
                "content": "x",
                "url": "https://mk.co.kr/...2",
                "published_at_ms": 1_700_000_001_000,
            },
        ]
    )
    src = MKNewsSourceAdapter(underlying=underlying)
    items = [it async for it in src.fetch()]
    assert len(items) == 2
    assert items[0].source == "mk"
    assert items[0].news_id == "mk_mk_001"
    # URL-hashed fallback for no-id entry
    assert items[1].news_id.startswith("mk_")
    assert all("sentiment" not in i.keywords for i in items)
