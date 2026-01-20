"""Test order executor."""
import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.asyncio
async def test_executor_paper_mode():
    """Test paper trading mode simulates orders."""
    from shared.execution.executor import OrderExecutor
    from shared.execution.config import ExecutionConfig
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
    from shared.execution.executor import OrderExecutor
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    await executor.initialize()
    assert executor._initialized is True

    await executor.cleanup()
    assert executor.session is None
