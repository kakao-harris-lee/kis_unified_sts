"""Test order execution models."""
import pytest


def test_order_request_creation():
    """Test OrderRequest model."""
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )

    assert order.code == "005930"
    assert order.side == OrderSide.BUY
    assert order.quantity == 10


def test_order_response_success():
    """Test successful OrderResponse."""
    from shared.execution.models import OrderResponse

    response = OrderResponse(
        success=True,
        order_no="0001234567",
        message="Order accepted"
    )

    assert response.success is True
    assert response.order_no == "0001234567"


def test_order_response_failure():
    """Test failed OrderResponse."""
    from shared.execution.models import OrderResponse

    response = OrderResponse(
        success=False,
        message="Insufficient balance"
    )

    assert response.success is False
    assert response.order_no is None
