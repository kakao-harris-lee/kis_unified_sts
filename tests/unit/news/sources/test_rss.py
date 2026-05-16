import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.rss import GenericRSSSource


@pytest.mark.asyncio
async def test_generic_rss_parses_official_feed():
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Market headline</title>
      <link>https://example.com/news/1</link>
      <description>Summary text</description>
      <pubDate>Fri, 15 May 2026 01:02:03 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    with aioresponses() as m:
        m.get("https://example.com/rss.xml", body=body)
        async with aiohttp.ClientSession() as session:
            src = GenericRSSSource(
                session=session,
                name="example_rss",
                rss_url="https://example.com/rss.xml",
                lang="en",
                poll_interval_seconds=240,
            )
            items = [it async for it in src.fetch()]

    assert len(items) == 1
    assert items[0].source == "example_rss"
    assert items[0].news_id.startswith("example_rss_")
    assert items[0].title == "Market headline"
    assert items[0].body == "Summary text"
    assert items[0].lang == "en"
    assert src.poll_interval_seconds == 240


@pytest.mark.asyncio
async def test_generic_rss_swallows_http_errors():
    with aioresponses() as m:
        m.get("https://example.com/rss.xml", status=503)
        async with aiohttp.ClientSession() as session:
            src = GenericRSSSource(
                session=session,
                name="example_rss",
                rss_url="https://example.com/rss.xml",
                lang="en",
            )
            items = [it async for it in src.fetch()]

    assert items == []
