"""Regression: futures daemon must not tight-restart after market close.

When the orchestrator daemon (``run()``) is (re)started *after* the market has
already closed for the trading day, ``run_session()`` must return early WITHOUT
calling ``start()``/``stop()``. Otherwise ``stop()`` sets ``_running=False``,
the daemon ``while self._running`` loop breaks and the process exits 0 — under
compose ``restart: unless-stopped`` that becomes a ~14s tight restart loop that
re-runs KIS REST/WS prewarm + startup LLM analysis on every cycle.

Surfaced during the 2026-06-09 cron→compose cutover: ``trader-futures`` showed
``RestartCount 257`` with ``ExitCode 0`` after the 15:45 KST futures close.
"""

from datetime import date, datetime
from datetime import time as dt_time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trading import orchestrator as orch_mod
from services.trading.orchestrator import TradingOrchestrator, TradingState

# Tuesday — a weekday/trading day. Futures close is 15:45.
_TRADING_DAY = date(2026, 6, 9)


def _make_orchestrator(asset_class: str = "futures") -> TradingOrchestrator:
    """Build a bare orchestrator with only what ``run_session()`` touches."""
    o = TradingOrchestrator.__new__(TradingOrchestrator)
    schedule = SimpleNamespace(
        get_open_time=lambda ac: dt_time(9, 0),
        get_close_time=lambda ac: dt_time(15, 45),
    )
    o.config = SimpleNamespace(asset_class=asset_class, schedule=schedule)
    o._holiday_cache = SimpleNamespace(get=lambda: set())
    o._publish_status_snapshot = MagicMock()
    o._notify = AsyncMock()
    o.start = AsyncMock()
    o.stop = AsyncMock()
    o._sleep_unless_stop_requested = AsyncMock()
    o._running = True
    o._stop_requested = False
    o.session_count = 0
    o.state = TradingState.IDLE
    return o


def _patch_clock(monkeypatch, now: datetime) -> None:
    class _FakeDate:
        @staticmethod
        def today() -> date:
            return now.date()

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return now

    monkeypatch.setattr(orch_mod, "date", _FakeDate)
    monkeypatch.setattr(orch_mod, "datetime", _FakeDateTime)


@pytest.mark.asyncio
async def test_run_session_after_close_returns_without_starting(monkeypatch):
    """After-close start → early return, no start()/stop(), _running preserved."""
    o = _make_orchestrator()
    _patch_clock(monkeypatch, datetime(2026, 6, 9, 16, 44, 0))  # 16:44 > 15:45 close

    await o.run_session()

    o.start.assert_not_awaited()
    o.stop.assert_not_awaited()
    # _running stays True so the daemon loop sleeps until tomorrow (no exit/restart).
    assert o._running is True
    assert o._stop_requested is False
    assert o.state == TradingState.IDLE


@pytest.mark.asyncio
async def test_run_session_during_session_runs_and_stops(monkeypatch):
    """Contrast: started during the session, it DOES start() then stop()."""
    o = _make_orchestrator()
    _patch_clock(monkeypatch, datetime(2026, 6, 9, 10, 0, 0))  # 10:00 < 15:45 close

    await o.run_session()

    o.start.assert_awaited_once()
    o.stop.assert_awaited_once()
    assert o.session_count == 1
