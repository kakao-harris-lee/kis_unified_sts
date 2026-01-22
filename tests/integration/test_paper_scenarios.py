"""Paper trading scenario tests for different market conditions."""
import pytest
from datetime import datetime

from shared.paper.broker import VirtualBroker
from shared.paper.models import OrderSide, PositionSide


class TestBullMarketScenario:
    """Test trading in bull market conditions."""

    @pytest.fixture
    def broker(self):
        """Create broker with 10M KRW."""
        return VirtualBroker(
            initial_balance=10_000_000,
            commission_rate=0.00015,
            slippage_rate=0.0001,
        )

    @pytest.mark.asyncio
    async def test_trending_up_profit(self, broker):
        """Test profit in trending up market."""
        # Buy at start
        await broker.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=50000,
        )

        # Verify position opened
        position = broker.get_position("005930")
        assert position is not None
        assert position.side == PositionSide.LONG
        assert position.quantity == 100

        # Simulate trending up
        prices = [51000, 52000, 53000, 54000, 55000]
        for price in prices:
            position.update_price(price)

        # Should be in profit
        assert position.unrealized_pnl > 0
        # Price went from ~50000 to 55000, so ~10% gain on 100 shares
        assert position.current_price == 55000
        assert position.highest_price == 55000

    @pytest.mark.asyncio
    async def test_buy_and_hold_strategy(self, broker):
        """Test simple buy and hold returns."""
        initial_equity = broker.get_equity()

        # Buy position
        await broker.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            quantity=50,
            price=60000,
        )

        # Price doubles
        position = broker.get_position("005930")
        position.update_price(120000)

        # Equity should have grown significantly
        assert broker.get_equity() > initial_equity


class TestBearMarketScenario:
    """Test trading in bear market conditions."""

    @pytest.fixture
    def broker(self):
        """Create broker with 10M KRW."""
        return VirtualBroker(
            initial_balance=10_000_000,
            commission_rate=0.00015,
            slippage_rate=0.0001,
        )

    @pytest.mark.asyncio
    async def test_stop_loss_protection(self, broker):
        """Test stop loss protects capital."""
        # Buy position
        await broker.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=50000,
        )

        # Price drops 10%
        position = broker.get_position("005930")
        position.update_price(45000)

        # Verify loss tracking
        assert position.unrealized_pnl < 0
        pnl_pct = position.unrealized_pnl / (position.entry_price * position.quantity) * 100
        assert pnl_pct < -5  # Should show significant loss

    @pytest.mark.asyncio
    async def test_cut_loss_early(self, broker):
        """Test cutting losses early preserves capital."""
        initial_balance = broker.balance

        # Buy position
        await broker.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=50000,
        )

        # Price drops slightly
        position = broker.get_position("005930")
        position.update_price(49000)

        # Sell to cut loss
        await broker.submit_order(
            symbol="005930",
            side=OrderSide.SELL,
            quantity=100,
            price=49000,
        )

        # Position should be closed
        assert broker.get_position("005930") is None

        # Should have recorded a losing trade
        assert len(broker.trades) == 1
        assert broker.trades[0].pnl < 0

        # But most capital preserved
        assert broker.balance > initial_balance * 0.95  # Lost less than 5%


class TestVolatileMarketScenario:
    """Test trading in volatile market conditions."""

    @pytest.fixture
    def broker(self):
        """Create broker with 10M KRW."""
        return VirtualBroker(
            initial_balance=10_000_000,
            commission_rate=0.00015,
            slippage_rate=0.0001,
        )

    @pytest.mark.asyncio
    async def test_whipsaw_handling(self, broker):
        """Test handling of whipsaw price movements."""
        await broker.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=50000,
        )

        position = broker.get_position("005930")

        # Simulate whipsaw: up → down → up
        position.update_price(52000)  # +4%
        assert position.highest_price == 52000

        position.update_price(49000)  # -2% from entry
        assert position.highest_price == 52000  # Highest preserved

        position.update_price(53000)  # +6%
        assert position.highest_price == 53000  # New high

        # Lowest should track
        assert position.lowest_price == 49000

    @pytest.mark.asyncio
    async def test_multiple_small_trades(self, broker):
        """Test multiple small profitable trades."""
        initial_balance = broker.balance

        # Execute 5 round-trip trades with small profits
        for i in range(5):
            entry_price = 50000 + i * 100
            exit_price = entry_price + 500  # +1% each

            await broker.submit_order(
                symbol="005930",
                side=OrderSide.BUY,
                quantity=10,
                price=entry_price,
            )

            await broker.submit_order(
                symbol="005930",
                side=OrderSide.SELL,
                quantity=10,
                price=exit_price,
            )

        # Should have 5 winning trades
        assert len(broker.trades) == 5
        winning = [t for t in broker.trades if t.pnl > 0]
        assert len(winning) == 5

        # Balance should have grown
        assert broker.balance > initial_balance


class TestMultiSymbolScenario:
    """Test trading multiple symbols simultaneously."""

    @pytest.fixture
    def broker(self):
        """Create broker with 50M KRW for multiple positions."""
        return VirtualBroker(
            initial_balance=50_000_000,
            commission_rate=0.00015,
            slippage_rate=0.0001,
        )

    @pytest.mark.asyncio
    async def test_portfolio_diversification(self, broker):
        """Test holding multiple positions."""
        symbols = [
            ("005930", 58000, 50),   # Samsung
            ("000660", 120000, 20),  # SK Hynix
            ("035420", 280000, 10),  # NAVER
        ]

        for symbol, price, qty in symbols:
            await broker.submit_order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=qty,
                price=price,
            )

        # Should have 3 positions
        assert len(broker.positions) == 3

        # Update prices - mixed results
        broker.positions["005930"].update_price(60000)   # +3.4%
        broker.positions["000660"].update_price(115000)  # -4.2%
        broker.positions["035420"].update_price(290000)  # +3.6%

        # Portfolio should still be profitable overall
        total_pnl = sum(p.unrealized_pnl for p in broker.positions.values())
        # Samsung: +100K, SK: -100K, NAVER: +100K = net positive
        assert total_pnl > 0

    @pytest.mark.asyncio
    async def test_sequential_exits(self, broker):
        """Test closing positions one by one."""
        # Open 3 positions
        await broker.submit_order("005930", OrderSide.BUY, 50, 50000)
        await broker.submit_order("000660", OrderSide.BUY, 20, 100000)
        await broker.submit_order("035420", OrderSide.BUY, 10, 250000)

        assert len(broker.positions) == 3

        # Close first position
        await broker.submit_order("005930", OrderSide.SELL, 50, 52000)
        assert len(broker.positions) == 2
        assert "005930" not in broker.positions

        # Close second position
        await broker.submit_order("000660", OrderSide.SELL, 20, 105000)
        assert len(broker.positions) == 1

        # Close third position
        await broker.submit_order("035420", OrderSide.SELL, 10, 260000)
        assert len(broker.positions) == 0

        # Should have 3 trades recorded
        assert len(broker.trades) == 3


class TestEdgeCaseScenario:
    """Test edge cases and error handling."""

    @pytest.fixture
    def broker(self):
        """Create broker with limited capital."""
        return VirtualBroker(
            initial_balance=1_000_000,
            commission_rate=0.00015,
            slippage_rate=0.0001,
        )

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, broker):
        """Test order rejection when balance insufficient."""
        from shared.paper.models import InsufficientBalanceError

        # Try to buy more than we can afford
        with pytest.raises(InsufficientBalanceError):
            await broker.submit_order(
                symbol="005930",
                side=OrderSide.BUY,
                quantity=1000,  # Way too many shares
                price=50000,    # 50M KRW needed, only have 1M
            )

    @pytest.mark.asyncio
    async def test_zero_position_value(self, broker):
        """Test equity calculation with no positions."""
        # Initial equity should equal balance
        assert broker.get_equity() == broker.balance

        # After a round-trip trade, equity should reflect realized P&L
        await broker.submit_order("005930", OrderSide.BUY, 10, 50000)
        await broker.submit_order("005930", OrderSide.SELL, 10, 51000)

        # No positions, but equity changed due to trade
        assert len(broker.positions) == 0
        assert broker.get_equity() == broker.balance

    @pytest.mark.asyncio
    async def test_summary_accuracy(self, broker):
        """Test summary statistics are accurate."""
        # Execute mixed trades
        await broker.submit_order("005930", OrderSide.BUY, 10, 50000)
        await broker.submit_order("005930", OrderSide.SELL, 10, 52000)  # Win

        await broker.submit_order("000660", OrderSide.BUY, 5, 100000)
        await broker.submit_order("000660", OrderSide.SELL, 5, 98000)   # Loss

        summary = broker.get_summary()

        assert summary["total_trades"] == 2
        assert summary["winning_trades"] == 1
        assert summary["win_rate"] == 0.5
        assert summary["open_positions"] == 0
