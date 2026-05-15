import re

import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.gdelt import GDELTNewsSource


@pytest.mark.asyncio
async def test_gdelt_parses_limited_doc_api_response():
    payload = {
        "articles": [
            {
                "url": "https://example.com/markets/1",
                "title": "Global yields move equity markets",
                "seendate": "20260515T010203Z",
                "domain": "example.com",
                "sourcecountry": "US",
                "language": "English",
            }
        ]
    }
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.gdeltproject\.org/api/v2/doc/doc.*"),
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(
                session=session,
                query='"stock market"',
                max_records=20,
                timespan="6h",
                poll_interval_seconds=300,
            )
            items = [it async for it in src.fetch()]

    assert len(items) == 1
    assert items[0].source == "gdelt"
    assert items[0].news_id.startswith("gdelt_")
    assert items[0].published_at_ms == 1_778_806_923_000
    assert "domain=example.com" in items[0].body
    assert items[0].keywords == ["gdelt", "example.com"]
    assert src.poll_interval_seconds == 300


@pytest.mark.asyncio
async def test_gdelt_rate_limit_returns_empty():
    with aioresponses() as m:
        m.get(
            re.compile(r"^https://api\.gdeltproject\.org/api/v2/doc/doc.*"),
            status=429,
        )
        async with aiohttp.ClientSession() as session:
            src = GDELTNewsSource(session=session, query='"stock market"')
            items = [it async for it in src.fetch()]

    assert items == []
