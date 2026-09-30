"""order_router exits for a compose restart when its contract expires.

Entrypoint wiring for review F4 on PR #689 (light): the real paper-mode
``_build_and_run`` must lock, subscribe and watch the resolved contract and
return the roll exit status the day after expiry. The feed and the daemon are
stubbed; config, fill logger, paper adapter and PseudoOCO are the real ones on
fakeredis. The clock is pinned through the shared module's ``datetime``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

import shared.execution.futures_instrument as fi
from shared.execution.futures_instrument import (
    FRONT_MONTH_ROLL_EXIT_CODE,
    KST,
    FrontMonthRolloverSchedule,
)


@pytest.mark.asyncio
async def test_order_router_paper_exits_with_roll_code_day_after_expiry(
    monkeypatch, caplog
):
    import redis.asyncio as aioredis

    import services.order_router.main as orm
    import shared.storage as storage

    monkeypatch.setenv("FUTURES_ORDER_ROUTER", "paper")
    monkeypatch.delenv("FUTURES_ORDER_ROUTER_FEED", raising=False)
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "kospi200")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)
    monkeypatch.setenv("ORDER_ROUTER_PUBLISH_KIS_ERROR_RATE", "false")

    clock = {"now": datetime(2026, 9, 10, 16, 0, tzinfo=KST)}  # expiry day, closed

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return clock["now"].astimezone(tz)

    monkeypatch.setattr(fi, "datetime", _Clock)
    monkeypatch.setattr(
        FrontMonthRolloverSchedule,
        "from_yaml",
        classmethod(lambda cls: cls(check_time=time(8, 30), poll_interval_seconds=0.0)),
    )
    monkeypatch.setattr(
        aioredis, "from_url", lambda *_a, **_k: fakeredis.aioredis.FakeRedis()
    )
    monkeypatch.setattr(storage, "SQLiteRuntimeLedger", MagicMock())

    feed = MagicMock(start=AsyncMock(), stop=AsyncMock())
    feed_symbols: list[str] = []

    def _fake_build_price_feed(*, symbol: str, **_kwargs: Any) -> MagicMock:
        feed_symbols.append(symbol)
        return feed

    monkeypatch.setattr(orm, "_build_price_feed", _fake_build_price_feed)

    daemon_kwargs: dict[str, Any] = {}

    class _Daemon:
        def __init__(self, **kwargs: Any) -> None:
            daemon_kwargs.update(kwargs)
            self._stop = asyncio.Event()

        async def run(self) -> None:
            clock["now"] = datetime(2026, 9, 11, 8, 31, tzinfo=KST)
            await self._stop.wait()

        async def stop(self) -> None:
            self._stop.set()

    monkeypatch.setattr(orm, "OrderRouterDaemon", _Daemon)

    with caplog.at_level(logging.INFO, logger=fi.__name__):
        code = await asyncio.wait_for(orm._build_and_run(), timeout=5)

    assert code == FRONT_MONTH_ROLL_EXIT_CODE
    assert feed_symbols == ["A01609"]
    assert daemon_kwargs["locked_symbol"] == "A01609"
    feed.stop.assert_awaited_once()  # the finally cleanup still runs on a roll
    assert "order-router: front-month rollover check active" in caplog.text
    assert "futures front-month rolled: A01609 -> A01612" in caplog.text
