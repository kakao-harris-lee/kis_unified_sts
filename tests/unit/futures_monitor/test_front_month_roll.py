"""futures_monitor exits for a compose restart when its contract expires.

End-to-end through the real ``_build_and_run`` entrypoint: the process starts on
the 2026-09-10 expiry day (resolves A01609), keeps running overnight, and the
08:30 KST check on 09-11 must stop it with the roll exit status so compose
brings it back on A01612 — instead of sitting on the dead code (2026-09-11
incident). The clock is pinned through the shared module's ``datetime``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time

import fakeredis.aioredis
import pytest

import shared.execution.futures_instrument as fi
from shared.execution.futures_instrument import (
    FRONT_MONTH_ROLL_EXIT_CODE,
    KST,
    FrontMonthRolloverSchedule,
)


@pytest.mark.asyncio
async def test_futures_monitor_exits_with_roll_code_day_after_expiry(
    monkeypatch, caplog
):
    import redis.asyncio as aioredis

    import services.futures_monitor.daemon as daemon_mod
    import services.futures_monitor.main as m
    import shared.streaming.trading_state as trading_state

    monkeypatch.setenv("FUTURES_MONITOR_DAEMON", "shadow")
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
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
    monkeypatch.setattr(trading_state, "TradingStatePublisher", lambda **_k: object())

    built: dict[str, object] = {}

    class _Daemon:
        def __init__(self, **kwargs: object) -> None:
            built.update(kwargs)
            self._stop = asyncio.Event()
            self.stopped = False

        async def run(self) -> None:
            # Started on the expiry day; the process outlives the night.
            clock["now"] = datetime(2026, 9, 11, 8, 31, tzinfo=KST)
            await self._stop.wait()

        async def stop(self) -> None:
            self.stopped = True
            self._stop.set()

    monkeypatch.setattr(daemon_mod, "FuturesMonitorDaemon", _Daemon)

    with caplog.at_level(logging.INFO, logger=fi.__name__):
        code = await asyncio.wait_for(m._build_and_run(), timeout=10)

    assert code == FRONT_MONTH_ROLL_EXIT_CODE
    assert built["feed"]._subscribed == {"A01609"}  # type: ignore[attr-defined]
    assert built["contract_symbol"] == "A01609"  # F5 recovery check sees it too
    assert "futures-monitor: front-month rollover check active" in caplog.text
    assert (
        "futures front-month rolled: A01609 -> A01612 (expiry 2026-12-10)"
        in caplog.text
    )
