from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.llm.collectors import DARTDataCollector
from shared.news.sources.dart import DARTNewsSource


@pytest.mark.asyncio
async def test_dart_adapter_converts_filings_to_news_items():
    collector = MagicMock()
    collector.fetch_recent_filings = AsyncMock(
        return_value=[
            {
                "rcept_no": "20260420000001",
                "corp_name": "삼성전자",
                "report_nm": "주요사항보고서(합병)",
                "rcept_dt": "20260420",
                "url": "https://dart.fss.or.kr/...",
            },
        ]
    )
    src = DARTNewsSource(collector=collector)
    items = [it async for it in src.fetch()]
    assert len(items) == 1
    item = items[0]
    assert item.source == "dart"
    assert item.news_id == "dart_20260420000001"
    assert item.lang == "ko"
    assert "삼성전자" in item.title


@pytest.mark.asyncio
async def test_dart_adapter_accepts_real_collector_contract():
    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "000",
                "list": [
                    {
                        "rcept_no": "20260514000962",
                        "corp_name": "엘앤에프",
                        "report_nm": "임원ㆍ주요주주특정증권등소유상황보고서",
                        "rcept_dt": "20260514",
                    }
                ],
            }

    calls = []
    collector = DARTDataCollector(api_key="test-key")
    collector.session.get = MagicMock(
        side_effect=lambda url, params, timeout: calls.append((url, params, timeout))
        or _Response()
    )
    src = DARTNewsSource(
        collector=collector,
        lookback_days=1,
        page_count=20,
        poll_interval_seconds=5,
    )

    items = [it async for it in src.fetch()]

    assert len(items) == 1
    assert calls[0][0].endswith("/list.json")
    assert calls[0][1]["page_count"] == 20
    assert items[0].news_id == "dart_20260514000962"
    assert items[0].url.endswith("rcpNo=20260514000962")
    assert src.poll_interval_seconds == 5


@pytest.mark.asyncio
async def test_dart_adapter_skips_filings_without_rcept_no():
    collector = MagicMock()
    collector.fetch_recent_filings = AsyncMock(return_value=[{"corp_name": "x"}])
    src = DARTNewsSource(collector=collector)
    items = [it async for it in src.fetch()]
    assert items == []
