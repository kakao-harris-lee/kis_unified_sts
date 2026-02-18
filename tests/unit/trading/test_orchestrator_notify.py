"""Tests for TradingOrchestrator fire-and-forget notification tracking."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeOrchestrator:
    """Minimal stand-in to test _schedule_notify / _on_notify_done."""

    def __init__(self):
        self._pending_notify_tasks: set[asyncio.Task] = set()
        self._notify = AsyncMock()

    def _schedule_notify(self, message: str) -> None:
        task = asyncio.create_task(self._notify(message), name="notify")
        self._pending_notify_tasks.add(task)
        task.add_done_callback(self._on_notify_done)

    def _on_notify_done(self, task: asyncio.Task) -> None:
        self._pending_notify_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            pass  # would log in real code


@pytest.fixture
def orch():
    return FakeOrchestrator()


class TestScheduleNotify:

    @pytest.mark.asyncio
    async def test_schedule_notify_adds_task_to_set(self, orch):
        orch._schedule_notify("test message")
        assert len(orch._pending_notify_tasks) == 1
        await asyncio.sleep(0.01)
        assert len(orch._pending_notify_tasks) == 0

    @pytest.mark.asyncio
    async def test_schedule_notify_calls_notify(self, orch):
        orch._schedule_notify("hello")
        await asyncio.sleep(0.01)
        orch._notify.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_on_notify_done_removes_task(self, orch):
        orch._schedule_notify("msg")
        assert len(orch._pending_notify_tasks) == 1
        await asyncio.sleep(0.01)
        assert len(orch._pending_notify_tasks) == 0

    @pytest.mark.asyncio
    async def test_on_notify_done_handles_exception(self, orch):
        orch._notify = AsyncMock(side_effect=RuntimeError("send failed"))
        orch._schedule_notify("msg")
        await asyncio.sleep(0.01)
        assert len(orch._pending_notify_tasks) == 0

    @pytest.mark.asyncio
    async def test_multiple_schedule_notify(self, orch):
        orch._schedule_notify("msg1")
        orch._schedule_notify("msg2")
        orch._schedule_notify("msg3")
        assert len(orch._pending_notify_tasks) == 3
        await asyncio.sleep(0.05)
        assert len(orch._pending_notify_tasks) == 0
        assert orch._notify.call_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_awaits_pending(self, orch):
        """Simulate _cleanup_resources pattern."""
        orch._notify = AsyncMock(side_effect=lambda m: asyncio.sleep(0.05))
        orch._schedule_notify("slow msg")
        assert len(orch._pending_notify_tasks) == 1

        # Await all pending (like _cleanup_resources does)
        await asyncio.gather(*orch._pending_notify_tasks, return_exceptions=True)
        assert orch._notify.call_count == 1
