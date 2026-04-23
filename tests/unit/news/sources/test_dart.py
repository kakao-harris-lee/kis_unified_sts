from unittest.mock import AsyncMock, MagicMock

import pytest

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
async def test_dart_adapter_skips_filings_without_rcept_no():
    collector = MagicMock()
    collector.fetch_recent_filings = AsyncMock(return_value=[{"corp_name": "x"}])
    src = DARTNewsSource(collector=collector)
    items = [it async for it in src.fetch()]
    assert items == []
