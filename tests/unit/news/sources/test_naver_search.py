import re

import aiohttp
import pytest
from aioresponses import aioresponses

from shared.news.sources.naver_search import NaverNewsSearchSource

_ENDPOINT = "https://openapi.naver.com/v1/search/news.json"


@pytest.mark.asyncio
async def test_naver_search_parses_json_news_response():
    payload = {
        "items": [
            {
                "title": "<b>삼성전자</b> &amp; 반도체 장전 이슈",
                "originallink": "https://example.com/original",
                "link": "https://n.news.naver.com/article/1",
                "description": "개장전 <b>주요이슈</b> 점검",
                "pubDate": "Mon, 26 Sep 2016 07:50:00 +0900",
            }
        ]
    }
    with aioresponses() as mocked:
        mocked.get(
            re.compile(r"^https://openapi\.naver\.com/v1/search/news\.json.*"),
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = NaverNewsSearchSource(
                session=session,
                client_id="client-id",
                client_secret="client-secret",
                queries=["인포스탁 개장전 주요이슈 점검"],
                display=5,
                sort="date",
            )
            items = [item async for item in src.fetch()]

    assert len(items) == 1
    assert items[0].source == "naver_search"
    assert items[0].news_id.startswith("naver_search_")
    assert items[0].title == "삼성전자 & 반도체 장전 이슈"
    assert items[0].body == "개장전 주요이슈 점검"
    assert items[0].url == "https://example.com/original"
    assert items[0].keywords == ["인포스탁 개장전 주요이슈 점검"]
    assert items[0].published_at_ms > 0

    request = next(iter(mocked.requests.values()))[0]
    assert request.kwargs["params"]["query"] == "인포스탁 개장전 주요이슈 점검"
    assert request.kwargs["params"]["display"] == "5"
    assert request.kwargs["params"]["sort"] == "date"
    assert request.kwargs["headers"]["X-Naver-Client-Id"] == "client-id"
    assert request.kwargs["headers"]["X-Naver-Client-Secret"] == "client-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_naver_search_swallows_http_errors(status):
    with aioresponses() as mocked:
        mocked.get(
            re.compile(r"^https://openapi\.naver\.com/v1/search/news\.json.*"),
            status=status,
        )
        async with aiohttp.ClientSession() as session:
            src = NaverNewsSearchSource(
                session=session,
                client_id="client-id",
                client_secret="client-secret",
                queries=["테마별 등락율 순위"],
            )
            items = [item async for item in src.fetch()]

    assert items == []


@pytest.mark.asyncio
async def test_naver_search_swallows_invalid_json():
    with aioresponses() as mocked:
        mocked.get(
            re.compile(r"^https://openapi\.naver\.com/v1/search/news\.json.*"),
            body="{bad",
        )
        async with aiohttp.ClientSession() as session:
            src = NaverNewsSearchSource(
                session=session,
                client_id="client-id",
                client_secret="client-secret",
                queries=["테마별 등락율 순위"],
            )
            items = [item async for item in src.fetch()]

    assert items == []
