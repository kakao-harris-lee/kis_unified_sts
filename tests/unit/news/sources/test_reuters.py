import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.reuters import ReutersRSSSource


@pytest.mark.asyncio
async def test_reuters_parses_rss_and_tags_lang_en():
    with open("tests/fixtures/reuters_sample.xml", "rb") as f:
        body = f.read()
    with aioresponses() as m:
        m.get("https://kr.reuters.com/rss/businessNews", body=body)
        async with aiohttp.ClientSession() as session:
            src = ReutersRSSSource(
                session=session, rss_url="https://kr.reuters.com/rss/businessNews"
            )
            items = [it async for it in src.fetch()]
    assert len(items) == 1
    assert items[0].source == "reuters"
    assert items[0].lang == "en"
    assert items[0].news_id.startswith("reuters_")
