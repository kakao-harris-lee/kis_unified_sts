"""Position.profit_pct / profit_rate — close 이후 안정성 회귀 테스트."""
from datetime import datetime

import pytest

from shared.models.position import Position, PositionSide


def _make_position(
    entry_price: float, current_price: float, side: PositionSide = PositionSide.LONG
) -> Position:
    pos = Position(
        id="p1",
        code="TEST",
        name="TEST",
        strategy="test",
        side=side,
        entry_price=entry_price,
        quantity=10,
        entry_time=datetime(2026, 4, 10, 9, 0),
    )
    pos.current_price = current_price
    return pos


class TestProfitPctBeforeClose:
    def test_long_profit(self):
        pos = _make_position(100.0, 105.0, PositionSide.LONG)
        assert pos.profit_pct == pytest.approx(5.0)

    def test_long_loss(self):
        pos = _make_position(100.0, 95.0, PositionSide.LONG)
        assert pos.profit_pct == pytest.approx(-5.0)

    def test_short_profit(self):
        pos = _make_position(100.0, 95.0, PositionSide.SHORT)
        assert pos.profit_pct == pytest.approx(5.0)


class TestProfitPctAfterClose:
    """exit_price가 설정되면 current_price와 무관하게 exit_price 기준으로 계산."""

    def test_uses_exit_price_when_available(self):
        pos = _make_position(100.0, 50.0, PositionSide.LONG)  # stale current_price
        pos.exit_price = 98.0
        pos.exit_time = datetime(2026, 4, 10, 15, 30)
        assert pos.profit_pct == pytest.approx(-2.0)

    def test_uses_current_price_when_exit_price_none(self):
        pos = _make_position(100.0, 95.0, PositionSide.LONG)
        assert pos.exit_price is None
        assert pos.profit_pct == pytest.approx(-5.0)

    def test_short_uses_exit_price(self):
        pos = _make_position(100.0, 200.0, PositionSide.SHORT)  # stale current_price
        pos.exit_price = 97.0
        pos.exit_time = datetime(2026, 4, 10, 15, 30)
        # SHORT profit: (entry - exit)/entry = (100-97)/100 = 3%
        assert pos.profit_pct == pytest.approx(3.0)


class TestProfitPctEdgeCases:
    def test_entry_price_zero_returns_zero(self):
        pos = _make_position(0.0, 100.0)
        assert pos.profit_pct == 0.0

    def test_entry_price_negative_returns_zero(self):
        pos = _make_position(-5.0, 100.0)
        assert pos.profit_pct == 0.0
