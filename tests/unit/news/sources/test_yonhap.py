import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.yonhap import YonhapRSSSource

SAMPLE_XML_PATH = "tests/fixtures/yonhap_sample.xml"


@pytest.mark.asyncio
async def test_yonhap_parses_rss():
    with open(SAMPLE_XML_PATH, "rb") as f:
        body = f.read()

    with aioresponses() as m:
        m.get("https://www.yna.co.kr/rss/economy.xml", body=body)
        async with aiohttp.ClientSession() as session:
            src = YonhapRSSSource(
                session=session,
                rss_url="https://www.yna.co.kr/rss/economy.xml",
            )
            items = [it async for it in src.fetch()]

    assert len(items) == 2
    assert items[0].source == "yonhap"
    assert items[0].title.startswith("FOMC")
    # news_id is deterministic sha256[:16]
    assert items[0].news_id.startswith("yonhap_")
    assert items[0].lang == "ko"


@pytest.mark.asyncio
async def test_yonhap_swallows_http_errors():
    with aioresponses() as m:
        m.get("https://www.yna.co.kr/rss/economy.xml", status=500)
        async with aiohttp.ClientSession() as session:
            src = YonhapRSSSource(
                session=session,
                rss_url="https://www.yna.co.kr/rss/economy.xml",
            )
            items = [it async for it in src.fetch()]
    assert items == []


@pytest.mark.asyncio
async def test_yonhap_deterministic_news_id():
    with open(SAMPLE_XML_PATH, "rb") as f:
        body = f.read()

    with aioresponses() as m:
        m.get("https://www.yna.co.kr/rss/economy.xml", body=body, repeat=True)
        async with aiohttp.ClientSession() as session:
            src = YonhapRSSSource(
                session=session,
                rss_url="https://www.yna.co.kr/rss/economy.xml",
            )
            first = [it async for it in src.fetch()]
            second = [it async for it in src.fetch()]

    assert first[0].news_id == second[0].news_id
