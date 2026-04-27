"""OrderResult dataclass — Phase 4 Task 2."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from shared.execution.order_result import OrderResult, OrderState


class TestOrderState:
    def test_enum_members(self):
        assert OrderState.FILLED.value == "filled"
        assert OrderState.MISSED.value == "missed"
        assert OrderState.CANCELLED.value == "cancelled"
        assert OrderState.ERROR.value == "error"

    def test_enum_membership(self):
        assert {s.name for s in OrderState} == {
            "FILLED",
            "MISSED",
            "CANCELLED",
            "ERROR",
        }


class TestOrderResultFilled:
    def test_filled_factory_sets_state_and_fields(self):
        fill = SimpleNamespace(price=331.25, order_id="ORD123")
        result = OrderResult.filled(fill, slippage_ticks=0.5)

        assert result.state is OrderState.FILLED
        assert result.filled_price == 331.25
        assert result.slippage_ticks == 0.5
        assert result.order_id == "ORD123"
        assert result.reason is None

    def test_filled_without_order_id(self):
        fill = SimpleNamespace(price=100.0)
        result = OrderResult.filled(fill, slippage_ticks=0.0)

        assert result.state is OrderState.FILLED
        assert result.filled_price == 100.0
        assert result.order_id is None


class TestOrderResultMissed:
    def test_missed_factory_sets_reason(self):
        result = OrderResult.missed(reason="passive_not_filled")

        assert result.state is OrderState.MISSED
        assert result.reason == "passive_not_filled"
        assert result.filled_price is None
        assert result.slippage_ticks is None
        assert result.order_id is None

    def test_missed_with_order_id(self):
        result = OrderResult.missed(reason="cancelled_after_timeout", order_id="ORD999")

        assert result.state is OrderState.MISSED
        assert result.reason == "cancelled_after_timeout"
        assert result.order_id == "ORD999"


class TestOrderResultCancelled:
    def test_cancelled_factory(self):
        result = OrderResult.cancelled(reason="kill_switch", order_id="ORD42")

        assert result.state is OrderState.CANCELLED
        assert result.reason == "kill_switch"
        assert result.order_id == "ORD42"


class TestOrderResultError:
    def test_error_factory(self):
        result = OrderResult.error(reason="kis_egw00201", order_id=None)

        assert result.state is OrderState.ERROR
        assert result.reason == "kis_egw00201"


class TestOrderResultImmutability:
    def test_is_frozen(self):
        result = OrderResult.missed(reason="x")
        with pytest.raises(FrozenInstanceError):
            result.state = OrderState.FILLED  # type: ignore[misc]

    def test_predicates(self):
        fill = SimpleNamespace(price=1.0)
        assert OrderResult.filled(fill, slippage_ticks=0.0).is_filled
        assert OrderResult.missed(reason="x").is_missed
        assert OrderResult.cancelled(reason="x").is_cancelled
        assert OrderResult.error(reason="x").is_error
