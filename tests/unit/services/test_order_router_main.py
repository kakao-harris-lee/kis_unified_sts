"""Tests for services/order_router/main.py — Phase 4 Task 12."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.order_router.main import (
    OrderRouterDaemon,
    _fill_stream_for,
    _final_stream_for,
    _resolve_mode,
)
from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.fill_logger import FillLogger
from shared.execution.order_result import OrderState
from shared.execution.passive_maker import Fill
from shared.execution.pseudo_oco import PseudoOCO

FINAL_STREAM = "stream:signal.final"
GROUP = "order_router"


def _spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50_000,
        tick_size_points=0.02,
        tick_value_krw=1_000,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


def _signal(direction: str = "long") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 4, 28, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 28, 5, 0, tzinfo=UTC),
    )


async def _publish_final(redis, signal: Signal, *, signal_id: str = "sig-1") -> None:
    fields = signal.to_stream_dict()
    fields["signal_id"] = signal_id
    fields["size_multiplier"] = "1.0"
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def kis():
    client = AsyncMock()
    client.get_futures_orderbook.return_value = SimpleNamespace(
        bid=[SimpleNamespace(price=331.20)],
        ask=[SimpleNamespace(price=331.22)],
    )
    client.place_futures_order.return_value = "ORD-1"
    client.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.20, quantity=1, filled_at_ms=2000
    )
    return client


@pytest.fixture
def fill_logger():
    return AsyncMock()


@pytest.fixture
def pseudo_oco(fill_logger):
    return PseudoOCO(fill_logger=fill_logger)


def _make_daemon(
    *,
    redis,
    kis,
    fill_logger,
    pseudo_oco,
    sentinel_path=None,
    live_mode_guard=None,
    locked_symbol=None,
):
    from shared.execution.passive_maker import PassiveMaker

    passive = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    return OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
        kill_switch_sentinel_path=sentinel_path,
        live_mode_guard=live_mode_guard,
        locked_symbol=locked_symbol,
    )


async def _run_one_batch(daemon):
    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())


@pytest.mark.asyncio
async def test_signal_routes_to_passive_maker(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    # Passive limit was placed
    kis.place_futures_order.assert_awaited_once()
    kwargs = kis.place_futures_order.call_args.kwargs
    assert kwargs["order_type"] == "limit"
    assert kwargs["side"] == "long"
    # Fill was logged
    fill_logger.log_fill.assert_awaited_once()


@pytest.mark.asyncio
async def test_signal_registers_oco_on_fill(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    # PseudoOCO has one active handle
    assert len(pseudo_oco.active_handles) == 1
    handle = pseudo_oco.active_handles[0]
    assert handle.symbol == "A05603"
    assert handle.stop_price == 330.50
    assert handle.target_price == 332.50


@pytest.mark.asyncio
async def test_missed_passive_fill_does_not_register_oco(
    redis, kis, fill_logger, pseudo_oco
):
    kis.await_fill.return_value = None  # passive timed out
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    # Cancel was called, OCO not registered
    kis.cancel_order.assert_awaited_once()
    assert pseudo_oco.active_handles == []


@pytest.mark.asyncio
async def test_xack_after_successful_route(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    pending = await redis.xpending(FINAL_STREAM, GROUP)
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 0
    elif pending:
        assert int(pending[0]) == 0


@pytest.mark.asyncio
async def test_sentinel_present_at_startup_refuses_to_run(
    tmp_path, redis, kis, fill_logger, pseudo_oco
):
    sentinel = tmp_path / "tripped"
    sentinel.write_text("kill_switch tripped")

    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        sentinel_path=str(sentinel),
    )
    await _publish_final(redis, _signal("long"))

    # run() should return immediately without consuming
    await daemon.run()

    assert daemon.refused_due_to_sentinel is True
    kis.place_futures_order.assert_not_awaited()
    fill_logger.log_fill.assert_not_awaited()


@pytest.mark.asyncio
async def test_sentinel_appearing_mid_run_stops_consumption(
    tmp_path, redis, kis, fill_logger, pseudo_oco
):
    sentinel = tmp_path / "tripped"

    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        sentinel_path=str(sentinel),
    )

    async def _trip_after_a_moment():
        # Let the loop iterate once with no messages, then trip
        await asyncio.sleep(0.03)
        sentinel.write_text("trip")

    await asyncio.gather(daemon.run(), _trip_after_a_moment())
    assert daemon.refused_due_to_sentinel is True


@pytest.mark.asyncio
async def test_no_sentinel_path_runs_normally(redis, kis, fill_logger, pseudo_oco):
    """sentinel_path=None disables the guard — back-compat for tests/other callers."""
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        sentinel_path=None,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_awaited_once()
    assert daemon.refused_due_to_sentinel is False


@pytest.mark.asyncio
async def test_size_multiplier_scales_quantity(redis, kis, fill_logger, pseudo_oco):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    fields = _signal("long").to_stream_dict()
    fields["signal_id"] = "sig-x"
    fields["size_multiplier"] = "0.5"  # halve the base size
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    await _run_one_batch(daemon)

    # base_quantity (default 1) × 0.5 → 0; floors to at least 1 contract
    kwargs = kis.place_futures_order.call_args.kwargs
    assert kwargs["quantity"] >= 1


# -----------------------------------------------------------------------------
# Phase 5 Task 5 — LiveModeGuard wiring
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_mode_disabled_skips_order_and_xacks(
    redis, kis, fill_logger, pseudo_oco
):
    """enabled=False → every signal is xack-skipped, no order placed."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=False)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_not_awaited()
    fill_logger.log_fill.assert_not_awaited()
    assert daemon.live_suspended_count == 1
    # Suspended signals are XACK'd (consumed, no retry)
    pending = await redis.xpending(FINAL_STREAM, GROUP)
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 0
    elif pending:
        assert int(pending[0]) == 0


@pytest.mark.asyncio
async def test_live_mode_redis_flag_skips_order(redis, kis, fill_logger, pseudo_oco):
    """enabled=True + Redis suspend flag set → signal skipped."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, suspend_key="futures:live:suspended")
    await redis.set("futures:live:suspended", "1")
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_not_awaited()
    assert daemon.live_suspended_count == 1


@pytest.mark.asyncio
async def test_live_mode_enabled_no_flag_routes_normally(
    redis, kis, fill_logger, pseudo_oco
):
    """enabled=True, no Redis flag → behaves like no guard at all."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_awaited_once()
    assert daemon.live_suspended_count == 0


@pytest.mark.asyncio
async def test_live_mode_guard_none_back_compat(redis, kis, fill_logger, pseudo_oco):
    """live_mode_guard=None preserves Phase-4 behaviour (no suspend check)."""
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=None,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_awaited_once()
    assert daemon.live_suspended_count == 0


# -----------------------------------------------------------------------------
# Phase 5 Gate-3 hard caps (symbol_lock / max_position_size / max_daily_trades)
# -----------------------------------------------------------------------------


def _signal_with_symbol(symbol: str, direction: str = "long") -> Signal:
    """_signal() with a custom symbol (Signal is frozen, so build fresh)."""
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol=symbol,
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 4, 28, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 28, 5, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_symbol_lock_blocks_non_locked_symbol(
    redis, kis, fill_logger, pseudo_oco
):
    """symbol_lock_enabled + signal.symbol mismatch → XACK skip."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, symbol_lock_enabled=True)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
        locked_symbol="A05603",  # front-month mini
    )
    # Signal for a different (e.g. expired) contract code
    await _publish_final(redis, _signal_with_symbol("A05604"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_not_awaited()
    assert daemon.symbol_lock_blocked_count == 1


@pytest.mark.asyncio
async def test_symbol_lock_disabled_allows_other_symbols(
    redis, kis, fill_logger, pseudo_oco
):
    """symbol_lock_enabled=False → mismatched symbol still routes."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, symbol_lock_enabled=False)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
        locked_symbol="A05603",
    )
    await _publish_final(redis, _signal_with_symbol("A05604"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_awaited_once()
    assert daemon.symbol_lock_blocked_count == 0


@pytest.mark.asyncio
async def test_symbol_lock_no_locked_symbol_is_noop(
    redis, kis, fill_logger, pseudo_oco
):
    """locked_symbol=None disables the gate even with symbol_lock_enabled=True."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, symbol_lock_enabled=True)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
        locked_symbol=None,  # not configured → can't enforce
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kis.place_futures_order.assert_awaited_once()
    assert daemon.symbol_lock_blocked_count == 0


@pytest.mark.asyncio
async def test_position_size_cap_clamps_quantity(redis, kis, fill_logger, pseudo_oco):
    """max_position_size_contracts=1 caps a 2-contract signal to 1."""
    from shared.execution.live_mode_guard import LiveModeGuard
    from shared.execution.passive_maker import PassiveMaker

    guard = LiveModeGuard(enabled=True, max_position_size_contracts=1)
    # Build daemon with base_quantity=2 so the un-capped quantity exceeds the cap.
    passive = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
        base_quantity=2,
        live_mode_guard=guard,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    kwargs = kis.place_futures_order.call_args.kwargs
    assert kwargs["quantity"] == 1
    assert daemon.position_size_capped_count == 1


@pytest.mark.asyncio
async def test_daily_trade_cap_blocks_after_max_reached(
    redis, kis, fill_logger, pseudo_oco
):
    """max_daily_trades=2 → 3rd signal of the day is XACK-skipped."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, max_daily_trades=2)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    # Publish 3 signals
    for i in range(3):
        await _publish_final(redis, _signal("long"), signal_id=f"sig-{i}")

    await _run_one_batch(daemon)

    # First 2 placed, 3rd blocked
    assert kis.place_futures_order.await_count == 2
    assert daemon.daily_trade_blocked_count == 1


@pytest.mark.asyncio
async def test_daily_trade_counter_sets_ttl_on_first_incr(
    redis, kis, fill_logger, pseudo_oco
):
    """First INCR of the day → TTL set so the counter expires at next KST midnight."""
    from services.order_router.main import _DAILY_TRADE_KEY_PREFIX, _kst_date_key
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, max_daily_trades=10)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    counter_key = f"{_DAILY_TRADE_KEY_PREFIX}{_kst_date_key()}"
    ttl = await redis.ttl(counter_key)
    # TTL must be set (>0) and ≤ 24h
    assert 0 < ttl <= 86_400


@pytest.mark.asyncio
async def test_daily_trade_redis_failure_fails_open(
    redis, kis, fill_logger, pseudo_oco
):
    """Redis INCR failure → log + allow (kill_switch is the primary safety net)."""
    from unittest.mock import patch

    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, max_daily_trades=2)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    await _publish_final(redis, _signal("long"))

    # Patch the INCR call to raise; xadd / xreadgroup / xack still work.
    original_incr = redis.incr

    async def _broken_incr(*a, **kw):
        raise Exception("simulated redis outage")

    with patch.object(redis, "incr", side_effect=_broken_incr):
        await _run_one_batch(daemon)

    # Fail-open: order still placed
    kis.place_futures_order.assert_awaited_once()
    assert daemon.daily_trade_blocked_count == 0
    # Restore for any later tests using the same fixture
    redis.incr = original_incr


def test_kst_date_key_format():
    """KST-date helper returns ISO YYYY-MM-DD."""
    from datetime import datetime

    from services.order_router.main import _kst_date_key

    # 2026-04-30 23:00 UTC = 2026-05-01 08:00 KST
    utc_ts = datetime(2026, 4, 30, 23, 0, tzinfo=UTC)
    assert _kst_date_key(utc_ts) == "2026-05-01"


def test_seconds_until_next_kst_midnight_floors_at_60():
    """At 23:59:59 KST, TTL still ≥ 60s (no zero-second TTL)."""
    from datetime import datetime

    from services.order_router.main import _seconds_until_next_kst_midnight

    # 2026-05-01 14:59:59 UTC = 2026-05-01 23:59:59 KST
    utc_ts = datetime(2026, 5, 1, 14, 59, 59, tzinfo=UTC)
    assert _seconds_until_next_kst_midnight(utc_ts) >= 60


def test_seconds_until_next_kst_midnight_caps_at_24h():
    """TTL is bounded to ≤ 86400s even on weird clock skew."""
    from datetime import datetime

    from services.order_router.main import _seconds_until_next_kst_midnight

    utc_ts = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
    assert _seconds_until_next_kst_midnight(utc_ts) <= 86_400


def test_final_stream_for_paper_and_live(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_FINAL_STREAM", raising=False)
    assert _final_stream_for("paper") == "signal.final.futures.shadow"
    assert _final_stream_for("live") == "signal.final.futures"


def test_fill_stream_for_paper_and_live(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_FILL_STREAM", raising=False)
    assert _fill_stream_for("paper") == "order.fill.futures.shadow"
    assert _fill_stream_for("live") == "order.fill.futures"


def test_stream_helpers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_FINAL_STREAM", "custom.final")
    monkeypatch.setenv("FUTURES_FILL_STREAM", "custom.fill")
    assert _final_stream_for("paper") == "custom.final"
    assert _fill_stream_for("live") == "custom.fill"


def test_resolve_mode_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_ORDER_ROUTER", raising=False)
    assert _resolve_mode() == "off"


def test_resolve_mode_paper_and_live(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_ORDER_ROUTER", "paper")
    assert _resolve_mode() == "paper"
    monkeypatch.setenv("FUTURES_ORDER_ROUTER", "live")
    assert _resolve_mode() == "live"


def test_resolve_mode_normalizes_case_and_whitespace(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_ORDER_ROUTER", "  PAPER ")
    assert _resolve_mode() == "paper"


def test_resolve_mode_empty_falls_through_to_off(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_ORDER_ROUTER", "")
    assert _resolve_mode() == "off"


# -----------------------------------------------------------------------------
# F-6 Task 2 — exit-monitor poll task + paper wiring
# -----------------------------------------------------------------------------


class _FakeFeed:
    def __init__(self, close: float) -> None:
        self._close = close

    async def get_current_price(self, symbol: str) -> dict:  # noqa: ARG002
        return {"close": self._close}


@pytest.mark.asyncio
async def test_exit_monitor_closes_bracket_and_records_pnl(redis):
    fill_logger = FillLogger(
        redis=redis, stream="order.fill.futures.shadow", batch_size=1
    )
    runtime_state = AsyncMock()
    pseudo_oco = PseudoOCO(
        fill_logger=fill_logger,
        runtime_state=runtime_state,
        multiplier_krw_per_point=50_000,
    )
    # register a long bracket: entry 331.20, stop 330.00
    await pseudo_oco.register_bracket(
        signal=_signal("long"),
        signal_id="s1",
        fill=Fill(order_id="E1", price=331.20, quantity=1, filled_at_ms=1000),
    )
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=AsyncMock(),
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream="signal.final.futures.shadow",
        consumer_group="order_router",
        worker_id="w1",
        xread_block_ms=100,
        batch_size=1,
        passive_timeout_seconds=1,
        locked_symbol="A05603",
        futures_price_feed=_FakeFeed(close=329.0),  # below the stop → fires
        exit_poll_interval=0.01,
    )
    await daemon.on_startup()
    await asyncio.sleep(0.05)  # let the monitor poll at least once
    await daemon.on_shutdown()
    assert pseudo_oco.active_handles == []  # bracket closed
    runtime_state.record_trade.assert_awaited()  # PnL recorded


@pytest.mark.asyncio
async def test_no_feed_starts_no_monitor(redis):
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=AsyncMock(),
        pseudo_oco=AsyncMock(),
        contract_spec=_spec(),
        final_stream="signal.final.futures",
        consumer_group="order_router",
        worker_id="w1",
        xread_block_ms=100,
        batch_size=1,
        passive_timeout_seconds=1,
        locked_symbol="A05603",
    )
    await daemon.on_startup()
    assert daemon._exit_task is None
    await daemon.on_shutdown()  # no-op, must not raise


# -----------------------------------------------------------------------------
# Telegram interactive-alerts — intent=close branch
# -----------------------------------------------------------------------------

POSITIONS_KEY = "futures:monitor:positions"


def _position_record(
    *,
    symbol: str = "A05603",
    side: str = "long",
    quantity: int = 1,
    entry_price: float = 331.20,
    signal_id: str = "sig-open-1",
) -> str:
    import json

    return json.dumps(
        {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "quantity": quantity,
            "opened_at_ms": 1000,
            "setup_type": "A_gap_reversion",
            "signal_id": signal_id,
            "high_water": entry_price,
            "low_water": entry_price,
        }
    )


async def _publish_close(redis, *, symbol: str = "A05603") -> None:
    await redis.xadd(
        FINAL_STREAM,
        {"intent": "close", "symbol": symbol, "signal_id": "close-req-1"},
    )


@pytest.mark.asyncio
async def test_close_paper_mode_flattens_and_logs_force_close(
    redis, kis, fill_logger, pseudo_oco
):
    """close_executor=None (paper) synthesizes the fill and logs force_close."""
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await redis.hset(POSITIONS_KEY, "A05603", _position_record(quantity=2))
    await _publish_close(redis)

    await _run_one_batch(daemon)

    fill_logger.log_fill.assert_awaited_once()
    kwargs = fill_logger.log_fill.call_args.kwargs
    assert kwargs["symbol"] == "A05603"
    assert kwargs["side"] == "short"  # opposite of the held "long" side
    assert kwargs["quantity"] == 2
    assert kwargs["trade_role"] == "force_close"
    assert daemon.close_count == 1
    # No entry-side order was placed via the passive path.
    kis.place_futures_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_short_position_flattens_with_long_side(
    redis, kis, fill_logger, pseudo_oco
):
    """Held short -> closing side is long (long/short symmetry preserved)."""
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await redis.hset(
        POSITIONS_KEY, "A05603", _position_record(side="short", quantity=1)
    )
    await _publish_close(redis)

    await _run_one_batch(daemon)

    kwargs = fill_logger.log_fill.call_args.kwargs
    assert kwargs["side"] == "long"


@pytest.mark.asyncio
async def test_close_no_open_position_is_noop_consumed(
    redis, kis, fill_logger, pseudo_oco
):
    """No record in the positions hash -> consumed, no fill logged."""
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_close(redis)

    await _run_one_batch(daemon)

    fill_logger.log_fill.assert_not_awaited()
    assert daemon.close_count == 0
    pending = await redis.xpending(FINAL_STREAM, GROUP)
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 0
    elif pending:
        assert int(pending[0]) == 0


@pytest.mark.asyncio
async def test_close_skips_entry_only_guards(redis, kis, fill_logger, pseudo_oco):
    """position_size_cap / daily_trade_cap must NOT block a close."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(
        enabled=True, max_position_size_contracts=1, max_daily_trades=1
    )
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    # Exhaust the daily-trade cap (max=1) with an entry signal first, so a
    # would-be entry at this point is blocked — then prove a close still
    # goes through despite both the exhausted cap and the oversized quantity.
    await _publish_final(redis, _signal("long"), signal_id="sig-entry-1")
    await redis.hset(POSITIONS_KEY, "A05603", _position_record(quantity=5))
    await _publish_close(redis)

    await _run_one_batch(daemon)

    assert daemon.daily_trade_blocked_count == 0  # the close never touches this counter
    kwargs = fill_logger.log_fill.call_args_list[-1].kwargs
    assert kwargs["quantity"] == 5  # not clamped by the position-size cap
    assert kwargs["trade_role"] == "force_close"
    assert daemon.position_size_capped_count == 0
    assert daemon.close_count == 1


@pytest.mark.asyncio
async def test_close_live_suspended_skips_and_xacks(
    redis, kis, fill_logger, pseudo_oco
):
    """live_mode_guard suspension still blocks a close (still a live order)."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=False)  # Gate 2 not complete -> suspended
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
    )
    await redis.hset(POSITIONS_KEY, "A05603", _position_record())
    await _publish_close(redis)

    await _run_one_batch(daemon)

    fill_logger.log_fill.assert_not_awaited()
    assert daemon.live_suspended_count == 1


@pytest.mark.asyncio
async def test_close_symbol_lock_blocks_foreign_symbol(
    redis, kis, fill_logger, pseudo_oco
):
    """symbol_lock still applies to a close on a non-locked symbol."""
    from shared.execution.live_mode_guard import LiveModeGuard

    guard = LiveModeGuard(enabled=True, symbol_lock_enabled=True)
    daemon = _make_daemon(
        redis=redis,
        kis=kis,
        fill_logger=fill_logger,
        pseudo_oco=pseudo_oco,
        live_mode_guard=guard,
        locked_symbol="A05603",
    )
    await redis.hset(POSITIONS_KEY, "A05604", _position_record(symbol="A05604"))
    await _publish_close(redis, symbol="A05604")

    await _run_one_batch(daemon)

    fill_logger.log_fill.assert_not_awaited()
    assert daemon.symbol_lock_blocked_count == 1


@pytest.mark.asyncio
async def test_close_live_mode_uses_close_executor(redis, fill_logger, pseudo_oco):
    """live close_executor set -> flatten() drives the placed order + fill."""
    from shared.execution.passive_maker import Fill

    close_executor = AsyncMock()
    close_executor.flatten.return_value = Fill(
        order_id="LIVE-CLOSE-1", price=330.90, quantity=1, filled_at_ms=5000
    )
    kis = AsyncMock()
    passive = AsyncMock()
    passive.fill_logger = fill_logger
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
        close_executor=close_executor,
    )
    await redis.hset(POSITIONS_KEY, "A05603", _position_record(quantity=1))
    await _publish_close(redis)

    await _run_one_batch(daemon)

    close_executor.flatten.assert_awaited_once()
    flatten_kwargs = close_executor.flatten.call_args.kwargs
    assert flatten_kwargs["symbol"] == "A05603"
    assert flatten_kwargs["side"] == "short"
    assert flatten_kwargs["quantity"] == 1
    kwargs = fill_logger.log_fill.call_args.kwargs
    assert kwargs["filled_price"] == 330.90
    assert daemon.close_count == 1
    _ = kis  # unused placeholder kept for readability of the setup above


@pytest.mark.asyncio
async def test_close_live_mode_executor_blocked_leaves_pending(
    redis, fill_logger, pseudo_oco
):
    """close_executor.flatten() returning None (guard-blocked) -> NO XACK, retried."""
    close_executor = AsyncMock()
    close_executor.flatten.return_value = None
    passive = AsyncMock()
    passive.fill_logger = fill_logger
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
        close_executor=close_executor,
    )
    await redis.hset(POSITIONS_KEY, "A05603", _position_record(quantity=1))
    await _publish_close(redis)

    await _run_one_batch(daemon)

    fill_logger.log_fill.assert_not_awaited()
    pending = await redis.xpending(FINAL_STREAM, GROUP)
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 1
    elif pending:
        assert int(pending[0]) == 1


@pytest.mark.asyncio
async def test_close_missing_symbol_field_is_poison_pill(
    redis, kis, fill_logger, pseudo_oco
):
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await redis.xadd(FINAL_STREAM, {"intent": "close"})

    await _run_one_batch(daemon)

    pending = await redis.xpending(FINAL_STREAM, GROUP)
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 0
    elif pending:
        assert int(pending[0]) == 0


# ---------------------------------------------------------------------------
# Review attempt-1 #2 — an UNRESOLVED fill state must not be consumed quietly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unresolved_fill_state_is_logged_at_error_and_brackets_nothing(
    redis, kis, fill_logger, pseudo_oco, caplog
):
    """`fill_state_unknown` reaching the daemon is not an ordinary non-fill.

    The broker may hold an unbracketed position. Logging it at info alongside
    genuine "didn't fill" signals is how the D-2 harm stays invisible.
    """
    import logging

    kis.await_fill.return_value = None
    kis.fill_state_unknown = lambda order_id: True

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    with caplog.at_level(logging.ERROR, logger="services.order_router.main"):
        await _run_one_batch(daemon)

    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("UNRESOLVED" in m for m in messages), messages
    assert any("fill_state_unknown" in m for m in messages), messages


@pytest.mark.asyncio
async def test_ordinary_non_fill_stays_at_info(
    redis, kis, fill_logger, pseudo_oco, caplog
):
    """Negative control: a resolved miss must not be escalated to ERROR."""
    import logging

    kis.await_fill.return_value = None
    kis.fill_state_unknown = lambda order_id: False

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    with caplog.at_level(logging.INFO, logger="services.order_router.main"):
        await _run_one_batch(daemon)

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("not filled" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Review attempt-2 #1 — the bracket must be sized from the FILL, not the request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_fill_arms_a_bracket_sized_from_the_fill(
    redis, kis, fill_logger, pseudo_oco
):
    """A 2-of-3 partial must arm a 2-lot bracket, not a 3-lot one.

    Futures accounts are net-position: a 3-lot protective exit against a long 2
    does not clamp at flat, it FLIPS to a short 1 — an unbounded-risk position
    created by the very order meant to bound risk.
    """
    kis.await_fill.return_value = Fill(
        order_id="ORD-PARTIAL", price=331.20, quantity=2, filled_at_ms=2000
    )
    registered = []
    pseudo_oco.register_bracket = AsyncMock(
        side_effect=lambda **kw: registered.append(kw)
    )

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    # base_quantity=1 x size_multiplier=3.0 -> requested 3
    signal = _signal("long")
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-partial"
    fields["size_multiplier"] = "3.0"
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    await _run_one_batch(daemon)

    assert registered, "bracket was never registered"
    assert registered[0]["fill"].quantity == 2


@pytest.mark.asyncio
async def test_full_fill_still_brackets_the_whole_position(
    redis, kis, fill_logger, pseudo_oco
):
    """Negative control: a complete fill brackets the full size."""
    kis.await_fill.return_value = Fill(
        order_id="ORD-FULL", price=331.20, quantity=3, filled_at_ms=2000
    )
    registered = []
    pseudo_oco.register_bracket = AsyncMock(
        side_effect=lambda **kw: registered.append(kw)
    )

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    signal = _signal("long")
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-full"
    fields["size_multiplier"] = "3.0"
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    await _run_one_batch(daemon)

    assert registered[0]["fill"].quantity == 3


@pytest.mark.asyncio
async def test_client_reporting_no_quantity_falls_back_to_the_request(
    redis, kis, fill_logger, pseudo_oco
):
    """All-or-nothing clients (paper adapter) report no per-fill quantity."""
    from shared.execution.order_result import OrderResult

    registered = []
    pseudo_oco.register_bracket = AsyncMock(
        side_effect=lambda **kw: registered.append(kw)
    )
    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    daemon.passive_maker.place_passive_limit_futures = AsyncMock(
        return_value=OrderResult(
            state=OrderState.FILLED,
            order_id="ORD-LEGACY",
            filled_price=331.20,
            slippage_ticks=0.0,
            filled_quantity=None,
        )
    )
    await _publish_final(redis, _signal("long"))

    await _run_one_batch(daemon)

    assert registered[0]["fill"].quantity == 1  # base_quantity


@pytest.mark.asyncio
async def test_unresolved_but_filled_is_bracketed_and_escalated(
    redis, kis, fill_logger, pseudo_oco, caplog
):
    """Review attempt-2 #3: a Fill whose TOTAL is unknown still arms a bracket.

    The measured quantity is a lower bound, so the bracket is armed (better
    than none) but the operator must be told the broker may hold more.
    """
    import logging

    kis.await_fill.return_value = Fill(
        order_id="ORD-U", price=331.20, quantity=2, filled_at_ms=2000
    )
    kis.fill_state_unknown = lambda order_id: True
    registered = []
    pseudo_oco.register_bracket = AsyncMock(
        side_effect=lambda **kw: registered.append(kw)
    )

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    with caplog.at_level(logging.ERROR, logger="services.order_router.main"):
        await _run_one_batch(daemon)

    assert registered, "an unresolved total must NOT suppress the bracket"
    assert registered[0]["fill"].quantity == 2
    assert any("UNRESOLVED executed total" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_resolved_fill_is_not_escalated(
    redis, kis, fill_logger, pseudo_oco, caplog
):
    """Negative control: a resolved fill brackets silently."""
    import logging

    kis.await_fill.return_value = Fill(
        order_id="ORD-OK", price=331.20, quantity=1, filled_at_ms=2000
    )
    kis.fill_state_unknown = lambda order_id: False

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=fill_logger, pseudo_oco=pseudo_oco
    )
    await _publish_final(redis, _signal("long"))

    with caplog.at_level(logging.ERROR, logger="services.order_router.main"):
        await _run_one_batch(daemon)

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


# ---------------------------------------------------------------------------
# Review attempt-3 #11 — the fill STREAM carries the executed quantity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_fill_writes_the_executed_quantity_to_the_fill_stream(
    redis, kis, pseudo_oco
):
    """A 2-of-3 partial must publish quantity=2, not the requested 3.

    This row is not audit-only. `futures_monitor` copies it into
    `futures:monitor:positions`, and the router's `_handle_close` reads it back
    as the size for `close_executor.flatten(...)` — a real broker order. A
    logged 3 against a held 2 makes the force-close over-sell by one contract,
    which on a net-position futures account flips to a short 1.
    """
    from shared.execution.fill_logger import FillLogger

    fill_stream = "stream:order.fill.test"
    real_logger = FillLogger(
        redis=redis, archive_client=None, stream=fill_stream, asset_class="futures"
    )
    kis.await_fill.return_value = Fill(
        order_id="ORD-PARTIAL", price=331.20, quantity=2, filled_at_ms=2000
    )

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=real_logger, pseudo_oco=pseudo_oco
    )
    signal = _signal("long")
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-stream-partial"
    fields["size_multiplier"] = "3.0"  # base 1 x 3 -> requested 3
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    await _run_one_batch(daemon)

    rows = await redis.xrange(fill_stream)
    entries = [
        {k.decode(): v.decode() for k, v in payload.items()} for _, payload in rows
    ]
    entry_rows = [r for r in entries if r["trade_role"] == "entry"]
    assert entry_rows, "no entry fill row was published"
    assert entry_rows[0]["quantity"] == "2"


@pytest.mark.asyncio
async def test_full_fill_writes_the_full_quantity_to_the_fill_stream(
    redis, kis, pseudo_oco
):
    """Negative control: a complete fill publishes the whole size."""
    from shared.execution.fill_logger import FillLogger

    fill_stream = "stream:order.fill.test.full"
    real_logger = FillLogger(
        redis=redis, archive_client=None, stream=fill_stream, asset_class="futures"
    )
    kis.await_fill.return_value = Fill(
        order_id="ORD-FULL", price=331.20, quantity=3, filled_at_ms=2000
    )

    daemon = _make_daemon(
        redis=redis, kis=kis, fill_logger=real_logger, pseudo_oco=pseudo_oco
    )
    signal = _signal("long")
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-stream-full"
    fields["size_multiplier"] = "3.0"
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    await _run_one_batch(daemon)

    rows = await redis.xrange(fill_stream)
    entries = [
        {k.decode(): v.decode() for k, v in payload.items()} for _, payload in rows
    ]
    entry_rows = [r for r in entries if r["trade_role"] == "entry"]
    assert entry_rows[0]["quantity"] == "3"
