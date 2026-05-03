"""Test order executor."""
from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_executor_paper_mode():
    """Test paper trading mode simulates orders."""
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )

    response = await executor.execute_order(order)

    assert response.success is True
    assert response.order_no is not None


@pytest.mark.asyncio
async def test_executor_initialize_cleanup():
    """Test session lifecycle."""
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    await executor.initialize()
    assert executor._initialized is True

    await executor.cleanup()
    assert executor.session is None


@pytest.mark.asyncio
async def test_send_order_routes_futures_orders():
    """Futures orders should use futures execution path."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="REAL", rate_limit_key="futures")
    executor = OrderExecutor(config=config)
    executor._send_kis_futures_order = AsyncMock(return_value=type("R", (), {"success": True})())

    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=330.5,
    )
    await executor._send_order(order)

    executor._send_kis_futures_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_futures_fill_timeout_triggers_cancel():
    """On fill timeout, cancel API should be called."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor, _FuturesFillStatus
    from shared.execution.models import (
        OrderRequest,
        OrderResponse,
        OrderSide,
        OrderType,
    )

    config = ExecutionConfig(
        trading_mode="REAL",
        rate_limit_key="futures",
        futures_fill_check_poll_interval_seconds=0.05,
        futures_fill_check_timeout_seconds=0.1,
        futures_auto_cancel_unfilled=True,
    )
    executor = OrderExecutor(config=config)
    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=330.5,
    )

    pending = _FuturesFillStatus(found=True, order_no="0000001234", order_qty=1, filled_qty=0, remaining_qty=1)
    after_cancel = _FuturesFillStatus(found=True, order_no="0000001234", order_qty=1, filled_qty=0, remaining_qty=0)
    executor._inquire_futures_fill_status = AsyncMock(side_effect=[pending, pending, after_cancel])
    executor._cancel_futures_order = AsyncMock(
        return_value=OrderResponse(success=True, message="cancel_ok")
    )

    resp = await executor._await_futures_fill_or_cancel(
        order=order,
        order_no="0000001234",
        is_mock=False,
        is_night=False,
    )

    assert resp.success is False
    executor._cancel_futures_order.assert_awaited_once()
    assert "cancelled" in resp.message.lower()


@pytest.mark.asyncio
async def test_execute_order_does_not_retry_when_order_no_exists():
    """Failure with order number should not be retried (duplicate-order guard)."""
    from unittest.mock import AsyncMock

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import (
        OrderRequest,
        OrderResponse,
        OrderSide,
        OrderType,
    )

    config = ExecutionConfig(trading_mode="REAL", max_retries=3, retry_delay=0.01)
    executor = OrderExecutor(config=config)
    executor._send_order = AsyncMock(
        side_effect=[
            OrderResponse(
                success=False,
                order_no="0000001234",
                message="Futures unfilled order cancelled",
            ),
            OrderResponse(success=True, order_no="0000009999", message="should_not_reach"),
        ]
    )

    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=330.5,
    )

    resp = await executor.execute_order(order)

    assert resp.success is False
    assert resp.order_no == "0000001234"
    assert executor._send_order.await_count == 1


def test_resolve_futures_inquire_tr_id_and_path_by_session():
    """체결조회 TR 연동: 모의/주간/야간 경로가 정확히 분기된다."""
    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor

    config = ExecutionConfig(trading_mode="REAL", rate_limit_key="futures")
    executor = OrderExecutor(config=config)

    tr_id, path = executor._resolve_futures_inquire_tr_id_and_path(is_mock=True, is_night=False)
    assert tr_id == config.futures_tr_code_inquire_day_mock
    assert path.endswith("/trading/inquire-ccnl")

    tr_id, path = executor._resolve_futures_inquire_tr_id_and_path(is_mock=False, is_night=False)
    assert tr_id == config.futures_tr_code_inquire_day_real
    assert path.endswith("/trading/inquire-ccnl")

    tr_id, path = executor._resolve_futures_inquire_tr_id_and_path(is_mock=False, is_night=True)
    assert tr_id == config.futures_tr_code_inquire_night_real
    assert path.endswith("/trading/inquire-ngt-ccnl")


def test_is_night_session_boundary():
    """야간 세션 경계(18:00~06:00) 판단 검증."""
    from shared.execution.executor import KST, OrderExecutor

    assert OrderExecutor._is_night_session(datetime(2026, 2, 25, 17, 59, tzinfo=KST)) is False
    assert OrderExecutor._is_night_session(datetime(2026, 2, 25, 18, 0, tzinfo=KST)) is True
    assert OrderExecutor._is_night_session(datetime(2026, 2, 26, 5, 59, tzinfo=KST)) is True
    assert OrderExecutor._is_night_session(datetime(2026, 2, 26, 6, 0, tzinfo=KST)) is False


@pytest.mark.asyncio
async def test_futures_night_order_refused_when_disabled(monkeypatch):
    """Phase 5 legal-review §4: 야간세션이 disabled면 fail-closed로 주문 거부."""
    from unittest.mock import patch

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="LIVE", rate_limit_key="futures")
    executor = OrderExecutor(config)
    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=350.0,
    )
    with (
        patch.object(OrderExecutor, "_is_night_session", return_value=True),
        patch(
            "shared.strategy.market_time.is_futures_night_session_enabled",
            return_value=False,
        ),
    ):
        resp = await executor._send_kis_futures_order(order, is_mock=False)

    assert resp.success is False
    assert "Night session disabled" in resp.message


@pytest.mark.asyncio
async def test_futures_day_order_not_blocked_by_night_guard(monkeypatch):
    """주간 세션이면 야간 가드를 건드리지 않고 정상 경로로 진입(이후 단계는 mock 부재로 실패해도 OK).

    핵심 검증은 응답 메시지가 'Night session disabled'가 아님.
    """
    from unittest.mock import patch

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="LIVE", rate_limit_key="futures")
    executor = OrderExecutor(config)
    order = OrderRequest(
        code="A05603",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=350.0,
    )
    with patch.object(OrderExecutor, "_is_night_session", return_value=False):
        resp = await executor._send_kis_futures_order(order, is_mock=False)

    assert "Night session disabled" not in (resp.message or "")


def test_is_futures_night_session_enabled_reads_yaml(tmp_path, monkeypatch):
    """market_schedule.yaml의 enabled 플래그를 읽어 반환."""
    from shared.config.loader import ConfigLoader
    from shared.strategy.market_time import is_futures_night_session_enabled

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "market_schedule.yaml").write_text(
        "market_schedule:\n"
        "  futures:\n"
        "    night:\n"
        "      enabled: true\n"
        "      open: '18:00'\n"
        "      close: '05:00'\n"
    )
    monkeypatch.setenv("KIS_CONFIG_DIR", str(cfg_dir))
    ConfigLoader.clear_cache()
    try:
        assert is_futures_night_session_enabled() is True
    finally:
        ConfigLoader.clear_cache()


def test_is_futures_night_session_enabled_default_false(tmp_path, monkeypatch):
    """enabled 키 누락 / 파일 없음 → fail-closed로 False."""
    from shared.config.loader import ConfigLoader
    from shared.strategy.market_time import is_futures_night_session_enabled

    cfg_dir = tmp_path / "config_empty"
    cfg_dir.mkdir()
    monkeypatch.setenv("KIS_CONFIG_DIR", str(cfg_dir))
    ConfigLoader.clear_cache()
    try:
        assert is_futures_night_session_enabled() is False
    finally:
        ConfigLoader.clear_cache()
