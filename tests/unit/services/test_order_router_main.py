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
