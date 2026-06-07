"""F-7: orchestrator futures live-mode guard on the real-order entry branch."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.trading.orchestrator import TradingOrchestrator
from shared.execution.live_mode_guard import LiveModeGuard


def _guard(enabled: bool) -> LiveModeGuard:
    return LiveModeGuard(enabled=enabled)


def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.mark.asyncio
async def test_blocked_futures_when_disabled() -> None:
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(False),
        _guard_redis=_redis(),
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is True


@pytest.mark.asyncio
async def test_allowed_futures_when_enabled_and_not_suspended() -> None:
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(True),
        _guard_redis=_redis(),
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is False


@pytest.mark.asyncio
async def test_blocked_futures_when_redis_suspend_set() -> None:
    r = _redis()
    await r.set("futures:live:suspended", "1")
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(True),
        _guard_redis=r,
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is True


@pytest.mark.asyncio
async def test_blocked_futures_fail_closed_when_guard_or_redis_none() -> None:
    f1 = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=None,
        _guard_redis=_redis(),
    )
    f2 = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(True),
        _guard_redis=None,
    )
    assert await TradingOrchestrator._real_entry_blocked(f1) is True
    assert await TradingOrchestrator._real_entry_blocked(f2) is True


@pytest.mark.asyncio
async def test_not_blocked_for_stock_regardless_of_guard() -> None:
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="stock"),
        _live_mode_guard=_guard(False),
        _guard_redis=_redis(),
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is False


@pytest.mark.asyncio
async def test_entry_real_branch_blocked_for_futures_when_suspended() -> None:
    executor = AsyncMock()
    notes: list[str] = []
    fake = SimpleNamespace(
        config=SimpleNamespace(paper_trading=False, asset_class="futures"),
        _paper_broker=None,
        _order_executor=executor,
        _live_mode_guard=_guard(False),
        _guard_redis=_redis(),
        _live_guard_warned=False,
        _schedule_notify=lambda msg: notes.append(msg),
    )
    fake._real_entry_blocked = TradingOrchestrator._real_entry_blocked.__get__(fake)

    result = await TradingOrchestrator._place_entry_order(
        fake,
        code="101W09",
        is_short=False,
        quantity=1,
        order_type="market",
        limit_price=None,
        market_price=100.0,
    )

    assert result == (False, 0.0, 0, "KRX")
    executor.execute_order.assert_not_awaited()
    assert notes and "101W09" in notes[0]
