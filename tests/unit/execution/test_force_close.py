"""Tests for shared/execution/force_close.py — Phase 4 Task 8."""

from datetime import datetime, time
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from shared.execution.force_close import ForceCloseExecutor, OpenPosition
from shared.execution.order_result import OrderState

KST = ZoneInfo("Asia/Seoul")


def _position(direction: str = "long") -> OpenPosition:
    return OpenPosition(
        signal_id="sig-1",
        symbol="A05603",
        direction=direction,
        quantity=1,
        entry_price=331.20,
        tick_size_points=0.02,
    )


@pytest.fixture
def kis():
    client = AsyncMock()
    client.place_futures_order.return_value = "MKT-1"
    client.await_fill.return_value = type(
        "F",
        (),
        {"order_id": "MKT-1", "price": 331.10, "quantity": 1, "filled_at_ms": 5000},
    )()
    return client


@pytest.fixture
def fill_logger():
    return AsyncMock()


@pytest.fixture
def executor(kis, fill_logger):
    return ForceCloseExecutor(kis_client=kis, fill_logger=fill_logger)


class TestValidUntilExpiry:
    @pytest.mark.asyncio
    async def test_long_position_closes_via_market_short(
        self, executor, kis, fill_logger
    ):
        result = await executor.close_for_valid_until_expiry(
            position=_position("long"), now_ms=10_000
        )
        assert result.is_filled
        assert result.state is OrderState.FILLED

        kwargs = kis.place_futures_order.call_args.kwargs
        assert kwargs["side"] == "short"  # closing direction
        assert kwargs["order_type"] == "market"
        assert kwargs["symbol"] == "A05603"
        assert kwargs["quantity"] == 1

        log = fill_logger.log_fill.call_args.kwargs
        assert log["trade_role"] == "force_close"
        assert log["order_type"] == "market"

    @pytest.mark.asyncio
    async def test_short_position_closes_via_market_long(self, executor, kis):
        await executor.close_for_valid_until_expiry(
            position=_position("short"), now_ms=10_000
        )
        kwargs = kis.place_futures_order.call_args.kwargs
        assert kwargs["side"] == "long"


class TestEODClose:
    @pytest.mark.asyncio
    async def test_close_for_eod(self, executor, kis, fill_logger):
        result = await executor.close_for_eod(position=_position("long"), now_ms=20_000)
        assert result.is_filled
        kwargs = kis.place_futures_order.call_args.kwargs
        assert kwargs["order_type"] == "market"
        assert fill_logger.log_fill.call_args.kwargs["trade_role"] == "force_close"


class TestKillSwitchClose:
    @pytest.mark.asyncio
    async def test_close_for_kill_switch(self, executor, kis, fill_logger):
        result = await executor.close_for_kill_switch(
            position=_position("long"),
            reason="daily_loss_breach",
            now_ms=30_000,
        )
        assert result.is_filled
        kwargs = kis.place_futures_order.call_args.kwargs
        assert kwargs["order_type"] == "market"
        log = fill_logger.log_fill.call_args.kwargs
        assert log["trade_role"] == "force_close"


class TestIsEOD:
    def test_before_eod_returns_false(self, executor):
        now = datetime(2026, 4, 27, 14, 59, tzinfo=KST)
        assert executor.is_eod(now) is False

    def test_at_eod_returns_true(self, executor):
        now = datetime(2026, 4, 27, 15, 10, tzinfo=KST)
        assert executor.is_eod(now) is True

    def test_after_eod_returns_true(self, executor):
        now = datetime(2026, 4, 27, 15, 30, tzinfo=KST)
        assert executor.is_eod(now) is True

    def test_eod_uses_kst_not_local(self, executor):
        # 06:10 UTC == 15:10 KST → True
        now_utc = datetime(2026, 4, 27, 6, 10, tzinfo=ZoneInfo("UTC"))
        assert executor.is_eod(now_utc) is True

    def test_naive_datetime_assumed_kst(self, executor):
        # Defensive: naive datetime should be treated as KST per project default.
        now = datetime(2026, 4, 27, 15, 11)
        assert executor.is_eod(now) is True

    def test_custom_eod_time(self, kis, fill_logger):
        e = ForceCloseExecutor(
            kis_client=kis, fill_logger=fill_logger, eod_time=time(14, 30)
        )
        now = datetime(2026, 4, 27, 14, 31, tzinfo=KST)
        assert e.is_eod(now) is True
        now2 = datetime(2026, 4, 27, 14, 29, tzinfo=KST)
        assert e.is_eod(now2) is False


class TestSlippageLogging:
    @pytest.mark.asyncio
    async def test_slippage_recorded_against_entry_price(self, executor, fill_logger):
        # Position entered at 331.20; market SELL closes long at 331.10.
        # The trader is selling 5 ticks below entry — that is adverse, so
        # slippage_ticks must be POSITIVE (per tick_math sign convention).
        await executor.close_for_eod(position=_position("long"), now_ms=10_000)
        log = fill_logger.log_fill.call_args.kwargs
        assert log["filled_price"] == 331.10
        assert log["requested_price"] == 331.20
        # long entry, closing SELL fills below entry → +5 ticks adverse
        assert log["slippage_ticks"] == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_slippage_short_entry_close_below_entry(self, kis, fill_logger):
        # Short entered at 331.20; market BUY closes at 331.10 (5 ticks favorable).
        # Closing BUY filling below entry is favorable → -5 ticks (improvement).
        kis.await_fill.return_value = type(
            "F",
            (),
            {
                "order_id": "MKT-1",
                "price": 331.10,
                "quantity": 1,
                "filled_at_ms": 5000,
            },
        )()
        executor = ForceCloseExecutor(kis_client=kis, fill_logger=fill_logger)
        await executor.close_for_eod(position=_position("short"), now_ms=10_000)
        log = fill_logger.log_fill.call_args.kwargs
        assert log["slippage_ticks"] == pytest.approx(-5.0)
