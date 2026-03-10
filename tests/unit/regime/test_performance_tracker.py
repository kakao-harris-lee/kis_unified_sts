"""Test RegimePerformanceTracker."""
import pytest
from datetime import datetime

from shared.regime.performance_tracker import (
    RegimePerformanceTracker,
    RegimePerformanceConfig,
    TradeRecord,
    RegimeStats,
)
from shared.exceptions import ValidationError


class TestTradeRecord:
    """Test TradeRecord dataclass."""

    def test_is_closed_true(self):
        """Trade with exit price and PnL is closed"""
        record = TradeRecord(
            regime="TRENDING_BULL",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=datetime.now(),
            exit_price=105.0,
            pnl=500.0
        )
        assert record.is_closed is True

    def test_is_closed_false(self):
        """Trade without exit is not closed"""
        record = TradeRecord(
            regime="TRENDING_BULL",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=datetime.now()
        )
        assert record.is_closed is False

    def test_is_winner(self):
        """Positive PnL → winner"""
        record = TradeRecord(
            regime="TRENDING_BULL",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=datetime.now(),
            exit_price=105.0,
            pnl=500.0
        )
        assert record.is_winner is True

    def test_is_loser(self):
        """Negative PnL → loser"""
        record = TradeRecord(
            regime="TRENDING_BEAR",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=datetime.now(),
            exit_price=95.0,
            pnl=-500.0
        )
        assert record.is_winner is False

    def test_return_pct(self):
        """Calculate return percentage correctly"""
        record = TradeRecord(
            regime="TRENDING_BULL",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=datetime.now(),
            exit_price=105.0,
            pnl=500.0
        )
        assert abs(record.return_pct - 0.05) < 0.001  # 5%

    def test_return_pct_open_trade(self):
        """Return pct is 0 for open trade"""
        record = TradeRecord(
            regime="TRENDING_BULL",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=datetime.now()
        )
        assert record.return_pct == 0.0

    def test_to_dict(self):
        """Convert to dictionary for serialization"""
        now = datetime.now()
        record = TradeRecord(
            regime="TRENDING_BULL",
            code="TEST",
            entry_price=100.0,
            entry_timestamp=now,
            exit_price=105.0,
            exit_timestamp=now,
            pnl=500.0,
            model_name="test_model",
            metadata={"signal_confidence": 0.9}
        )
        d = record.to_dict()

        assert d["regime"] == "TRENDING_BULL"
        assert d["code"] == "TEST"
        assert d["entry_price"] == 100.0
        assert d["exit_price"] == 105.0
        assert d["pnl"] == 500.0
        assert d["model_name"] == "test_model"
        assert d["metadata"]["signal_confidence"] == 0.9

    def test_from_dict(self):
        """Create from dictionary"""
        now = datetime.now()
        data = {
            "regime": "TRENDING_BULL",
            "code": "TEST",
            "entry_price": 100.0,
            "entry_timestamp": now.isoformat(),
            "exit_price": 105.0,
            "exit_timestamp": now.isoformat(),
            "pnl": 500.0,
            "model_name": "test_model",
            "metadata": {}
        }
        record = TradeRecord.from_dict(data)

        assert record.regime == "TRENDING_BULL"
        assert record.code == "TEST"
        assert record.entry_price == 100.0
        assert record.exit_price == 105.0
        assert record.pnl == 500.0


class TestRegimePerformanceTracker:
    """Test suite for RegimePerformanceTracker."""

    @pytest.fixture
    def tracker(self):
        """Create tracker with test configuration."""
        config = RegimePerformanceConfig(
            max_trades_per_regime=10,
            redis_enabled=False,
            min_trades_for_stats=1,
        )
        return RegimePerformanceTracker(config)

    # 1. Test entry/exit recording

    def test_record_entry(self, tracker):
        """Record entry creates open position"""
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST",
            price=100.0,
            timestamp=datetime.now(),
            model_name="test_model"
        )
        assert tracker.get_open_positions_count() == 1

    def test_record_exit(self, tracker):
        """Record exit closes position"""
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST",
            price=100.0,
            timestamp=datetime.now(),
            model_name="test_model"
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST",
            price=105.0,
            timestamp=datetime.now(),
            pnl=500.0,
            model_name="test_model"
        )
        assert tracker.get_open_positions_count() == 0
        assert tracker.get_closed_trades_count() == 1

    def test_record_entry_validation(self, tracker):
        """Entry validation raises errors"""
        # Empty regime
        with pytest.raises(ValidationError, match="regime cannot be empty"):
            tracker.record_entry("", "TEST", 100.0, datetime.now())

        # Empty code
        with pytest.raises(ValidationError, match="code cannot be empty"):
            tracker.record_entry("BULL", "", 100.0, datetime.now())

        # Invalid price
        with pytest.raises(ValidationError, match="price must be > 0"):
            tracker.record_entry("BULL", "TEST", 0.0, datetime.now())

    def test_record_exit_validation(self, tracker):
        """Exit validation raises errors"""
        # Empty regime
        with pytest.raises(ValidationError, match="regime cannot be empty"):
            tracker.record_exit("", "TEST", 100.0, datetime.now(), 50.0)

        # Empty code
        with pytest.raises(ValidationError, match="code cannot be empty"):
            tracker.record_exit("BULL", "", 100.0, datetime.now(), 50.0)

        # Invalid price
        with pytest.raises(ValidationError, match="price must be > 0"):
            tracker.record_exit("BULL", "TEST", 0.0, datetime.now(), 50.0)

    # 2. Test metric calculations

    def test_calculate_win_rate(self, tracker):
        """Win rate = winners / total"""
        # 3 winners, 2 losers
        for i in range(5):
            tracker.record_entry(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            pnl = 100.0 if i < 3 else -50.0
            exit_price = 105.0 if i < 3 else 95.0
            tracker.record_exit(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=exit_price,
                timestamp=datetime.now(),
                pnl=pnl,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        assert abs(stats["win_rate"] - 0.6) < 0.001  # 3/5

    def test_calculate_sharpe_ratio(self, tracker):
        """Sharpe ratio = (mean - rf) / std"""
        # Add trades with known PnL distribution
        for pnl in [100, 200, -50, 150, -30]:
            tracker.record_entry(
                regime="TRENDING_BULL",
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BULL",
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                pnl=pnl,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        assert "sharpe_ratio" in stats
        # Verify Sharpe is calculated (should be positive for profitable trades)
        assert stats["sharpe_ratio"] > 0

    def test_calculate_max_drawdown(self, tracker):
        """Max drawdown from peak"""
        # Simulate drawdown pattern
        pnls = [100, 200, -150, -100, 250]  # Peak at 300, trough at 50
        for i, pnl in enumerate(pnls):
            tracker.record_entry(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=100.0,
                timestamp=datetime.now(),
                pnl=pnl,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        # Expected drawdown: (300 - 50) / 300 = 0.833
        assert stats["max_drawdown"] > 0.5  # Should be significant

    def test_calculate_profit_factor(self, tracker):
        """Profit factor = total_wins / abs(total_losses)"""
        # Winners: 100 + 200 = 300
        # Losers: -50 - 30 = -80
        # Profit factor = 300 / 80 = 3.75
        for pnl in [100, 200, -50, -30]:
            tracker.record_entry(
                regime="TRENDING_BULL",
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BULL",
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                pnl=pnl,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        assert abs(stats["profit_factor"] - 3.75) < 0.01

    def test_calculate_avg_pnl(self, tracker):
        """Average PnL calculation"""
        pnls = [100, -50, 200, -30, 150]
        for pnl in pnls:
            tracker.record_entry(
                regime="TRENDING_BULL",
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BULL",
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                pnl=pnl,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        expected_avg = sum(pnls) / len(pnls)
        assert abs(stats["avg_pnl"] - expected_avg) < 0.01

    # 3. Test bounded memory

    def test_bounded_memory_enforcement(self, tracker):
        """Max trades per regime enforced"""
        # Add 15 trades (max is 10)
        for i in range(15):
            tracker.record_entry(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=105.0,
                timestamp=datetime.now(),
                pnl=50.0,
                model_name="test"
            )

        # Should only keep most recent 10
        assert tracker.get_closed_trades_count() <= 10

    # 4. Test edge cases

    def test_edge_case_zero_trades(self, tracker):
        """Regime with no trades returns empty stats"""
        stats = tracker.get_regime_stats("NONEXISTENT")
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0

    def test_edge_case_all_winners(self, tracker):
        """100% win rate, no losers"""
        for i in range(3):
            tracker.record_entry(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BULL",
                code=f"TEST{i}",
                price=105.0,
                timestamp=datetime.now(),
                pnl=50.0,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        assert stats["win_rate"] == 1.0
        assert stats["profit_factor"] == 0.0  # No losses: returns 0.0 per implementation

    def test_edge_case_all_losers(self, tracker):
        """0% win rate, no winners"""
        for i in range(3):
            tracker.record_entry(
                regime="TRENDING_BEAR",
                code=f"TEST{i}",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime="TRENDING_BEAR",
                code=f"TEST{i}",
                price=95.0,
                timestamp=datetime.now(),
                pnl=-50.0,
                model_name="test"
            )

        stats = tracker.get_regime_stats("TRENDING_BEAR")
        assert stats["win_rate"] == 0.0
        assert stats["profit_factor"] == 0.0  # No wins

    # 5. Test model distribution

    def test_model_distribution_tracking(self, tracker):
        """Track which models used per regime"""
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST1",
            price=100.0,
            timestamp=datetime.now(),
            model_name="model_a"
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST1",
            price=105.0,
            timestamp=datetime.now(),
            pnl=50.0,
            model_name="model_a"
        )

        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST2",
            price=100.0,
            timestamp=datetime.now(),
            model_name="model_b"
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST2",
            price=105.0,
            timestamp=datetime.now(),
            pnl=50.0,
            model_name="model_b"
        )

        stats = tracker.get_regime_stats("TRENDING_BULL")
        assert stats["model_distribution"]["model_a"] == 1
        assert stats["model_distribution"]["model_b"] == 1

    # 6. Test configuration validation

    def test_config_validation_max_trades(self):
        """Invalid max_trades_per_regime raises error"""
        with pytest.raises(ValueError, match="max_trades_per_regime"):
            RegimePerformanceConfig(max_trades_per_regime=5)  # Below MIN_MAX_TRADES

    def test_config_validation_max_open(self):
        """Invalid max_open_positions raises error"""
        with pytest.raises(ValueError, match="max_open_positions"):
            RegimePerformanceConfig(max_open_positions=5)  # Below MIN_MAX_TRADES

    def test_config_validation_min_trades(self):
        """Invalid min_trades_for_stats raises error"""
        with pytest.raises(ValueError, match="min_trades_for_stats"):
            RegimePerformanceConfig(min_trades_for_stats=0)

    def test_config_validation_risk_free_rate(self):
        """Invalid risk_free_rate raises error"""
        with pytest.raises(ValueError, match="risk_free_rate"):
            RegimePerformanceConfig(risk_free_rate=1.5)  # Above 1.0

    def test_config_validation_redis_db(self):
        """Invalid redis_db raises error"""
        with pytest.raises(ValueError, match="redis_db"):
            RegimePerformanceConfig(redis_db=-1)

    def test_config_from_dict(self):
        """Create config from dict with validation"""
        data = {
            "max_trades_per_regime": 500,
            "max_open_positions": 50,
            "min_trades_for_stats": 5,
            "risk_free_rate": 0.03,
            "redis_enabled": True,
            "redis_key_prefix": "test_prefix",
            "redis_db": 2
        }
        config = RegimePerformanceConfig.from_dict(data)

        assert config.max_trades_per_regime == 500
        assert config.max_open_positions == 50
        assert config.min_trades_for_stats == 5
        assert config.risk_free_rate == 0.03
        assert config.redis_enabled is True
        assert config.redis_key_prefix == "test_prefix"
        assert config.redis_db == 2

    def test_config_from_dict_type_validation(self):
        """from_dict validates types"""
        with pytest.raises(TypeError, match="max_trades_per_regime must be int"):
            RegimePerformanceConfig.from_dict({"max_trades_per_regime": "invalid"})

    # 7. Test get_all_stats

    def test_get_all_stats(self, tracker):
        """Get all stats returns dict for all regimes"""
        # Add trades for multiple regimes
        for regime in ["TRENDING_BULL", "TRENDING_BEAR"]:
            tracker.record_entry(
                regime=regime,
                code="TEST",
                price=100.0,
                timestamp=datetime.now(),
                model_name="test"
            )
            tracker.record_exit(
                regime=regime,
                code="TEST",
                price=105.0,
                timestamp=datetime.now(),
                pnl=50.0,
                model_name="test"
            )

        all_stats = tracker.get_all_stats()
        assert "TRENDING_BULL" in all_stats
        assert "TRENDING_BEAR" in all_stats
        assert all_stats["TRENDING_BULL"]["total_trades"] == 1
        assert all_stats["TRENDING_BEAR"]["total_trades"] == 1

    # 8. Test exit without entry

    def test_exit_without_entry(self, tracker):
        """Exit without matching entry creates standalone record"""
        result = tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST",
            price=105.0,
            timestamp=datetime.now(),
            pnl=50.0,
            model_name="test"
        )

        # Should create a record even without matching entry
        assert result is not None
        assert tracker.get_closed_trades_count() == 1

    # 9. Test overwrite existing open position

    def test_overwrite_open_position(self, tracker):
        """Recording entry for same regime/code overwrites"""
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST",
            price=100.0,
            timestamp=datetime.now(),
            model_name="test1"
        )

        # Record another entry for same regime/code
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST",
            price=102.0,
            timestamp=datetime.now(),
            model_name="test2"
        )

        # Should still have only 1 open position
        assert tracker.get_open_positions_count() == 1

    # 10. Test stats cache

    def test_stats_cache(self, tracker):
        """Stats are cached and reused"""
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST",
            price=100.0,
            timestamp=datetime.now(),
            model_name="test"
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST",
            price=105.0,
            timestamp=datetime.now(),
            pnl=50.0,
            model_name="test"
        )

        # First call calculates stats
        stats1 = tracker.get_regime_stats("TRENDING_BULL")

        # Second call should use cache
        stats2 = tracker.get_regime_stats("TRENDING_BULL")

        assert stats1 == stats2

    def test_stats_cache_invalidation(self, tracker):
        """Cache is invalidated when new trade is added"""
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST1",
            price=100.0,
            timestamp=datetime.now(),
            model_name="test"
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST1",
            price=105.0,
            timestamp=datetime.now(),
            pnl=50.0,
            model_name="test"
        )

        stats1 = tracker.get_regime_stats("TRENDING_BULL")
        assert stats1["total_trades"] == 1

        # Add another trade
        tracker.record_entry(
            regime="TRENDING_BULL",
            code="TEST2",
            price=100.0,
            timestamp=datetime.now(),
            model_name="test"
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="TEST2",
            price=105.0,
            timestamp=datetime.now(),
            pnl=50.0,
            model_name="test"
        )

        stats2 = tracker.get_regime_stats("TRENDING_BULL")
        assert stats2["total_trades"] == 2
