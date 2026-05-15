import re
from urllib.parse import parse_qs, urlparse

import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.marketaux import MarketauxNewsSource


@pytest.mark.asyncio
async def test_marketaux_parses_financial_news_response():
    payload = {
        "data": [
            {
                "uuid": "70cb577e-c2dd-4dde-b501-f713823a4939",
                "title": "Chip stocks rise after market close",
                "description": "Semiconductor shares moved higher.",
                "snippet": "Investors bought AI-linked semiconductor names.",
                "url": "https://example.com/markets/chips",
                "language": "en",
                "published_at": "2026-05-15T01:24:00.000000Z",
                "source": "example.com",
                "keywords": "semiconductors,stocks",
                "entities": [
                    {
                        "symbol": "NVDA",
                        "name": "NVIDIA Corporation",
                        "country": "us",
                        "type": "equity",
                        "sentiment_score": 0.31,
                    }
                ],
            }
        ]
    }
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.marketaux\.com/v1/news/all.*"),
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = MarketauxNewsSource(
                session=session,
                api_token="test-token",
                limit=20,
                language="en",
                countries="us,kr",
                symbols="NVDA",
                published_after_minutes=0,
                poll_interval_seconds=300,
            )
            items = [it async for it in src.fetch()]

        request_url = next(iter(m.requests))[1]
        query = parse_qs(urlparse(str(request_url)).query)

    assert len(items) == 1
    assert items[0].source == "marketaux"
    assert items[0].news_id == "marketaux_70cb577e-c2dd-4dde-b501-f713823a4939"
    assert items[0].published_at_ms == 1_778_808_240_000
    assert items[0].lang == "en"
    assert "source=example.com" in items[0].body
    assert "symbols=NVDA" in items[0].body
    assert items[0].keywords == ["semiconductors", "stocks", "NVDA", "example.com"]
    assert src.poll_interval_seconds == 300
    assert query["api_token"] == ["test-token"]
    assert query["symbols"] == ["NVDA"]
    assert query["filter_entities"] == ["true"]


@pytest.mark.asyncio
async def test_marketaux_missing_token_returns_empty():
    async with aiohttp.ClientSession() as session:
        src = MarketauxNewsSource(session=session, api_token="")
        items = [it async for it in src.fetch()]

    assert items == []


@pytest.mark.asyncio
async def test_marketaux_rate_limit_returns_empty():
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.marketaux\.com/v1/news/all.*"),
            status=429,
        )
        async with aiohttp.ClientSession() as session:
            src = MarketauxNewsSource(session=session, api_token="test-token")
            items = [it async for it in src.fetch()]

    assert items == []
