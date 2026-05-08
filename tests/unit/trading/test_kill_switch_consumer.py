"""Tests for TradingOrchestrator kill-switch consumer loop (Phase 0.2-c).

Covers:
  - Sentinel absent → no flatten
  - Sentinel set + new event id → flatten called once + sentinel DEL'd
  - Sentinel set + old event id (pre-startup) → flatten NOT called
  - Multiple ticks within TTL window → only first call submits orders (idempotency)
  - Redis error → logged, no crash, retry on next tick
  - Telegram alert sent on flatten
  - KillSwitchConsumerConfig defaults and YAML loading
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — minimal stand-ins for the orchestrator components needed by tests.
# ---------------------------------------------------------------------------


def _make_position(
    position_id: str = "pos-1",
    code: str = "A05603",
    side: str = "long",
    quantity: int = 1,
    current_price: float = 360.0,
    strategy: str = "rl_mppo",
) -> MagicMock:
    """Build a minimal Position mock."""
    from shared.models.position import PositionSide

    pos = MagicMock()
    pos.id = position_id
    pos.code = code
    pos.side = PositionSide.LONG if side == "long" else PositionSide.SHORT
    pos.quantity = quantity
    pos.current_price = current_price
    pos.strategy = strategy
    pos.unrealized_pnl = 0.0
    return pos


class _FakeOrchestrator:
    """Minimal orchestrator stand-in exercising the kill-switch consumer logic.

    Copies only the attributes and methods touched by
    :meth:`_start_kill_switch_consumer` and
    :meth:`_kill_switch_consumer_loop`.
    """

    def __init__(
        self,
        positions: list[Any] | None = None,
    ) -> None:
        from services.trading.orchestrator import TradingConfig

        self.config = TradingConfig.stock(
            strategy_name="rl_mppo",
            symbols=["A05603"],
            initial_capital=10_000_000,
        )
        self.config.asset_class = "futures"

        self._market_data_running = False  # controlled per-test
        self._market_data_lock = asyncio.Lock()
        self._market_data_snapshot: dict[str, Any] = {
            "A05603": {"close": 360.0}
        }

        # Position tracker stub
        self._position_tracker = MagicMock()
        self._position_tracker.positions = positions or []
        # close_position returns a mock "closed" position with sane defaults.
        self._position_tracker.close_position = MagicMock(
            side_effect=lambda position_id, exit_price, reason, quantity=None: _make_closed_pos(  # noqa: ARG005
                position_id, exit_price, reason
            )
        )

        self._state_publisher = None
        self.total_pnl = 0.0
        self.total_trades = 0

        # Kill-switch consumer state (same as orchestrator __init__)
        self._kill_switch_consumer_task: asyncio.Task | None = None
        self._ks_last_seen_event_id: str | None = None

        # Broker stub
        self._paper_broker = AsyncMock()
        _order_mock = MagicMock()
        _order_mock.filled = True
        _order_mock.fill_price = 360.0
        self._paper_broker.submit_order = AsyncMock(return_value=_order_mock)
        # Unused in tests but referenced by _kill_switch_flatten_all
        self._order_executor = None
        self._venue_router = None

        # Notification stub (captured for assertions)
        self._notify = AsyncMock()

    # Delegated methods that the consumer loop calls on the orchestrator.

    def _sync_open_positions_metric(self) -> None:
        pass

    def _record_running_totals(self, closed) -> None:
        pass

    async def _persist_closed_position(self, closed, strategy: str) -> None:
        pass

    async def _submit_exit_order(
        self, code: str, is_buy: bool, quantity: int, price: float
    ) -> tuple[bool, float]:
        """Delegate to paper broker."""
        from shared.paper import OrderSide as PaperOrderSide

        order = await self._paper_broker.submit_order(
            symbol=code,
            side=PaperOrderSide.BUY if is_buy else PaperOrderSide.SELL,
            quantity=quantity,
            price=price,
            price_source_time=None,
        )
        is_filled = bool(getattr(order, "filled", True))
        fill_price = float(getattr(order, "fill_price", price) or price)
        return is_filled, fill_price

    async def _kill_switch_flatten_all(self) -> int:
        """Import the real implementation from orchestrator and call it."""
        # Import the real method bound to this fake orchestrator so tests
        # exercise the actual business logic without instantiating the full
        # TradingOrchestrator (which requires KIS credentials etc.).
        import types

        from services.trading.orchestrator import TradingOrchestrator

        real_fn = TradingOrchestrator._kill_switch_flatten_all
        # Bind as method of self.
        bound = types.MethodType(real_fn, self)
        return await bound()


def _make_closed_pos(position_id: str, exit_price: float, reason: str) -> MagicMock:  # noqa: ARG001
    closed = MagicMock()
    closed.id = position_id
    closed.unrealized_pnl = 0.0
    closed.strategy = "rl_mppo"
    return closed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_orch():
    """Orchestrator fake with one open LONG position."""
    pos = _make_position(position_id="pos-long", side="long")
    return _FakeOrchestrator(positions=[pos])


@pytest.fixture
def fake_orch_short():
    """Orchestrator fake with one open SHORT position."""
    pos = _make_position(position_id="pos-short", side="short")
    return _FakeOrchestrator(positions=[pos])


@pytest.fixture
def fake_orch_empty():
    """Orchestrator fake with no open positions."""
    return _FakeOrchestrator()


# ---------------------------------------------------------------------------
# KillSwitchConsumerConfig tests
# ---------------------------------------------------------------------------


class TestKillSwitchConsumerConfig:
    def test_defaults(self):
        from services.kill_switch.config import KillSwitchConsumerConfig

        cfg = KillSwitchConsumerConfig()
        assert cfg.poll_interval_seconds == 5.0
        assert cfg.sentinel_key == "kill_switch:force_flatten:requested"
        assert cfg.events_stream == "kill_switch:events"
        assert cfg.ignore_pre_startup_events is True

    def test_custom_values(self):
        from services.kill_switch.config import KillSwitchConsumerConfig

        cfg = KillSwitchConsumerConfig(
            poll_interval_seconds=2.0,
            sentinel_key="custom:key",
            events_stream="custom:stream",
            ignore_pre_startup_events=False,
        )
        assert cfg.poll_interval_seconds == 2.0
        assert cfg.sentinel_key == "custom:key"
        assert cfg.events_stream == "custom:stream"
        assert cfg.ignore_pre_startup_events is False


# ---------------------------------------------------------------------------
# _kill_switch_flatten_all tests (unit — no async task, no Redis)
# ---------------------------------------------------------------------------


class TestFlattenAll:
    """Unit tests for _kill_switch_flatten_all targeting both long and short."""

    @pytest.mark.asyncio
    async def test_flatten_long_submits_sell(self, fake_orch):
        """Long position exit should call paper broker with SELL."""
        from shared.paper import OrderSide as PaperOrderSide

        count = await fake_orch._kill_switch_flatten_all()
        assert count == 1
        fake_orch._paper_broker.submit_order.assert_called_once()
        call_kwargs = fake_orch._paper_broker.submit_order.call_args[1]
        assert call_kwargs["side"] == PaperOrderSide.SELL

    @pytest.mark.asyncio
    async def test_flatten_short_submits_buy(self, fake_orch_short):
        """Short position exit should call paper broker with BUY (cover)."""
        from shared.paper import OrderSide as PaperOrderSide

        count = await fake_orch_short._kill_switch_flatten_all()
        assert count == 1
        fake_orch_short._paper_broker.submit_order.assert_called_once()
        call_kwargs = fake_orch_short._paper_broker.submit_order.call_args[1]
        assert call_kwargs["side"] == PaperOrderSide.BUY

    @pytest.mark.asyncio
    async def test_flatten_empty_returns_zero(self, fake_orch_empty):
        count = await fake_orch_empty._kill_switch_flatten_all()
        assert count == 0
        fake_orch_empty._paper_broker.submit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_flatten_updates_totals(self, fake_orch):
        """After flatten, total_trades should be incremented."""
        await fake_orch._kill_switch_flatten_all()
        assert fake_orch.total_trades == 1

    @pytest.mark.asyncio
    async def test_broker_error_still_closes_tracking(self, fake_orch):
        """If broker call raises, tracker.close_position still called (fallback)."""
        fake_orch._paper_broker.submit_order.side_effect = RuntimeError("broker down")

        count = await fake_orch._kill_switch_flatten_all()
        # Position still marked closed (fallback behaviour)
        assert count == 1
        fake_orch._position_tracker.close_position.assert_called_once()


# ---------------------------------------------------------------------------
# _kill_switch_consumer_loop integration tests (async, no real Redis)
# ---------------------------------------------------------------------------


def _make_ks_cfg(
    poll_interval: float = 0.01,
    sentinel_key: str = "kill_switch:force_flatten:requested",
    events_stream: str = "kill_switch:events",
    ignore_pre_startup: bool = True,
) -> Any:
    from services.kill_switch.config import KillSwitchConsumerConfig

    return KillSwitchConsumerConfig(
        poll_interval_seconds=poll_interval,
        sentinel_key=sentinel_key,
        events_stream=events_stream,
        ignore_pre_startup_events=ignore_pre_startup,
    )


async def _run_loop_for_ticks(
    orch: _FakeOrchestrator,
    redis_mock: MagicMock,
    ks_cfg: Any,
    ticks: int = 3,
    sleep_between: float = 0.02,
) -> None:
    """Run the consumer loop for a fixed number of sleeps then cancel."""
    import types

    from services.trading.orchestrator import TradingOrchestrator

    real_loop = TradingOrchestrator._kill_switch_consumer_loop
    bound = types.MethodType(real_loop, orch)

    orch._market_data_running = True

    with patch("shared.streaming.client.RedisClient.get_client", return_value=redis_mock):
        task = asyncio.create_task(bound(ks_cfg))
        await asyncio.sleep(sleep_between * ticks)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    orch._market_data_running = False


class TestConsumerLoopNoSentinel:
    """Sentinel absent — flatten must NOT be called."""

    @pytest.mark.asyncio
    async def test_no_sentinel_no_flatten(self, fake_orch):
        redis_mock = MagicMock()
        redis_mock.get.return_value = None  # no sentinel
        redis_mock.xrevrange.return_value = []

        ks_cfg = _make_ks_cfg()
        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=3)

        fake_orch._paper_broker.submit_order.assert_not_called()
        fake_orch._notify.assert_not_called()


class TestConsumerLoopNewEvent:
    """Sentinel set + new event id → flatten once + sentinel DEL'd."""

    @pytest.mark.asyncio
    async def test_new_event_triggers_flatten(self, fake_orch):
        sentinel_key = "kill_switch:force_flatten:requested"
        event_id = "1746300000000-0"

        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=daily_loss"
        redis_mock.xrevrange.return_value = [(event_id, {"event": "force_flatten_requested"})]
        redis_mock.delete = MagicMock(return_value=1)

        # No pre-startup last-seen; consumer will see the event as new.
        fake_orch._ks_last_seen_event_id = None
        ks_cfg = _make_ks_cfg(ignore_pre_startup=False, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=2)

        fake_orch._paper_broker.submit_order.assert_called()
        redis_mock.delete.assert_called_with(sentinel_key)

    @pytest.mark.asyncio
    async def test_new_event_sends_telegram(self, fake_orch):
        event_id = "1746300000000-0"

        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=consecutive_losses"
        redis_mock.xrevrange.return_value = [(event_id, {})]
        redis_mock.delete = MagicMock()

        fake_orch._ks_last_seen_event_id = None
        ks_cfg = _make_ks_cfg(ignore_pre_startup=False, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=2)

        fake_orch._notify.assert_called_once()
        call_args = fake_orch._notify.call_args[0][0]
        assert "KILL-SWITCH" in call_args
        assert "futures" in call_args

    @pytest.mark.asyncio
    async def test_sentinel_deleted_after_flatten(self, fake_orch):
        event_id = "1746300000000-0"
        sentinel_key = "kill_switch:force_flatten:requested"

        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=test"
        redis_mock.xrevrange.return_value = [(event_id, {})]
        redis_mock.delete = MagicMock()

        fake_orch._ks_last_seen_event_id = None
        ks_cfg = _make_ks_cfg(ignore_pre_startup=False, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=2)

        redis_mock.delete.assert_called_with(sentinel_key)


class TestConsumerLoopPreStartupGuard:
    """Pre-startup event id present → flatten NOT called with ignore_pre_startup=True."""

    @pytest.mark.asyncio
    async def test_old_event_id_not_triggered(self, fake_orch):
        event_id = "1746300000000-0"

        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=daily_loss"
        redis_mock.xrevrange.return_value = [(event_id, {})]

        # last-seen is already set to the same event id (simulates startup init)
        fake_orch._ks_last_seen_event_id = event_id
        ks_cfg = _make_ks_cfg(ignore_pre_startup=True, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=3)

        # Flatten must NOT have been submitted
        fake_orch._paper_broker.submit_order.assert_not_called()
        fake_orch._notify.assert_not_called()


class TestConsumerLoopIdempotency:
    """Multiple ticks within TTL window → only first trigger flattens."""

    @pytest.mark.asyncio
    async def test_second_tick_does_not_reflaten(self, fake_orch):
        event_id = "1746300000000-0"

        call_count = 0
        original_get = [True]

        def get_side_effect(key):  # noqa: ARG001
            # Sentinel present first two ticks; after first handling it's DEL'd.
            nonlocal call_count
            call_count += 1
            # After delete is called the sentinel would be gone.  Simulate by
            # returning None once delete has been called.
            if not original_get[0]:
                return None
            return "reason=weekly_loss"

        redis_mock = MagicMock()
        redis_mock.get.side_effect = get_side_effect
        redis_mock.xrevrange.return_value = [(event_id, {})]

        def delete_side_effect(key):  # noqa: ARG001
            original_get[0] = False  # mark sentinel as deleted

        redis_mock.delete = MagicMock(side_effect=delete_side_effect)

        fake_orch._ks_last_seen_event_id = None
        ks_cfg = _make_ks_cfg(ignore_pre_startup=False, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=5)

        # Only called once (first detection)
        assert fake_orch._paper_broker.submit_order.call_count == 1
        # Notify also only once
        assert fake_orch._notify.call_count == 1


class TestConsumerLoopRedisError:
    """Redis error → logged, no crash, retry on next tick."""

    @pytest.mark.asyncio
    async def test_redis_error_no_crash(self, fake_orch):
        import redis

        redis_mock = MagicMock()
        redis_mock.get.side_effect = redis.ConnectionError("connection refused")

        ks_cfg = _make_ks_cfg(poll_interval=0.01)
        # Should NOT raise — loop just logs and retries
        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=3)

        # No flatten attempted after Redis error
        fake_orch._paper_broker.submit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_del_error_no_crash(self, fake_orch):
        """DEL failure after successful flatten must not crash the loop."""
        import redis

        event_id = "1746300000001-0"

        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=test"
        redis_mock.xrevrange.return_value = [(event_id, {})]
        redis_mock.delete.side_effect = redis.ConnectionError("conn error on DEL")

        fake_orch._ks_last_seen_event_id = None
        ks_cfg = _make_ks_cfg(ignore_pre_startup=False, poll_interval=0.01)

        # Must not raise
        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=2)

        # flatten still executed
        fake_orch._paper_broker.submit_order.assert_called()


class TestConsumerLoopEmptyStream:
    """Sentinel present but events stream empty — handled safely."""

    @pytest.mark.asyncio
    async def test_empty_stream_with_last_seen_set_skips(self, fake_orch):
        """If stream empty AND last-seen is set → skip (pre-startup guard)."""
        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=test"
        redis_mock.xrevrange.return_value = []  # empty stream

        fake_orch._ks_last_seen_event_id = "some-prior-event-id"
        ks_cfg = _make_ks_cfg(ignore_pre_startup=True, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=3)

        fake_orch._paper_broker.submit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_stream_no_last_seen_triggers(self, fake_orch):
        """If stream empty AND last-seen is None → trigger flatten."""
        redis_mock = MagicMock()
        redis_mock.get.return_value = "reason=test"
        redis_mock.xrevrange.return_value = []  # empty stream
        redis_mock.delete = MagicMock()

        fake_orch._ks_last_seen_event_id = None
        ks_cfg = _make_ks_cfg(ignore_pre_startup=False, poll_interval=0.01)

        await _run_loop_for_ticks(fake_orch, redis_mock, ks_cfg, ticks=2)

        fake_orch._paper_broker.submit_order.assert_called()
