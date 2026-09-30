"""decision_engine exits for a compose restart when its contract expires.

Entrypoint wiring for review F4 on PR #689: the real ``_build_and_run`` in a
producing mode must hand ``daemon.run`` to the shared front-month watch, watch
the same contract its context provider consumes, and return the roll exit
status. Started on the 2026-09-10 expiry day (A01609); the 08:30 KST check on
09-11 must roll it. The clock is pinned through the shared module's
``datetime``; nothing reads the wall clock.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from unittest.mock import MagicMock

import fakeredis
import fakeredis.aioredis
import pytest

import shared.execution.futures_instrument as fi
from shared.execution.futures_instrument import (
    FRONT_MONTH_ROLL_EXIT_CODE,
    KST,
    FrontMonthRolloverSchedule,
)


@pytest.mark.asyncio
async def test_decision_engine_shadow_exits_with_roll_code_day_after_expiry(
    monkeypatch, caplog
):
    import redis
    import redis.asyncio as aioredis

    import services.decision_engine.main as dem
    import shared.storage as storage

    monkeypatch.setenv("FUTURES_STRATEGY_DAEMON", "shadow")
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "kospi200")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

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
    monkeypatch.setattr(
        redis.Redis,
        "from_url",
        classmethod(lambda cls, *_a, **_k: fakeredis.FakeRedis()),
    )
    monkeypatch.setattr(storage, "SQLiteRuntimeLedger", MagicMock())
    monkeypatch.setattr(dem, "_build_setups", lambda: [])

    provider_contracts: list[str] = []

    async def _fake_context_provider_builder(redis_client, instrument=None):
        provider_contracts.append(instrument.symbol)

        async def _provider() -> None:
            return None

        return _provider, None, None, None

    monkeypatch.setattr(dem, "_build_context_provider", _fake_context_provider_builder)

    class _Daemon:
        def __init__(self) -> None:
            self._stop = asyncio.Event()

        async def run(self) -> None:
            # Started on the expiry day; the process outlives the night.
            clock["now"] = datetime(2026, 9, 11, 8, 31, tzinfo=KST)
            await self._stop.wait()

        async def stop(self) -> None:
            self._stop.set()

    monkeypatch.setattr(dem, "_build_daemon", lambda **_kwargs: _Daemon())

    with caplog.at_level(logging.INFO, logger=fi.__name__):
        code = await asyncio.wait_for(dem._build_and_run(), timeout=5)

    assert code == FRONT_MONTH_ROLL_EXIT_CODE
    assert provider_contracts == ["A01609"]  # the watched contract is the consumed one
    assert "decision-engine: front-month rollover check active" in caplog.text
    assert (
        "futures front-month rolled: A01609 -> A01612 (expiry 2026-12-10)"
        in caplog.text
    )
