from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from services.macro_overnight_collector.main import (
    collect_fx_session,
    collect_us_session,
)
from shared.macro.base import MacroSnapshot


@pytest.mark.asyncio
async def test_collect_us_session_publishes():
    redis = fakeredis.aioredis.FakeRedis()
    archive_client = AsyncMock()
    yahoo = MagicMock()
    yahoo.fetch_us_close_snapshot = AsyncMock(
        return_value=MacroSnapshot(
            ts_ms=1_700_000_000_000,
            session="overnight_us_close",
            sp500_close=5100.0,
            sp500_change_pct=1.0,
            nasdaq_close=17000.0,
            nasdaq_change_pct=0.9,
            collected_from=["yahoo"],
        )
    )
    rc = await collect_us_session(
        redis=redis,
        archive_client=archive_client,
        yahoo_source=yahoo,
        stream="stream:macro.overnight",
        maxlen=1000,
    )
    assert rc == 0
    entries = await redis.xrange("stream:macro.overnight")
    assert len(entries) == 1
    assert entries[0][1][b"session"] == b"overnight_us_close"
    archive_client.execute.assert_not_awaited()
    ttl = await redis.ttl("stream:macro.overnight")
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_collect_fx_session_publishes():
    redis = fakeredis.aioredis.FakeRedis()
    archive_client = AsyncMock()
    ecos = MagicMock()
    ecos.fetch_fx_snapshot = AsyncMock(
        return_value=MacroSnapshot(
            ts_ms=1_700_000_100_000,
            session="overnight_fx",
            usdkrw=1355.8,
            usdkrw_change_pct=0.4,
            collected_from=["ecos"],
        )
    )
    rc = await collect_fx_session(
        redis=redis,
        archive_client=archive_client,
        ecos_source=ecos,
        stream="stream:macro.overnight",
        maxlen=1000,
    )
    assert rc == 0
    entries = await redis.xrange("stream:macro.overnight")
    assert len(entries) == 1
    assert entries[0][1][b"session"] == b"overnight_fx"
    archive_client.execute.assert_not_awaited()
