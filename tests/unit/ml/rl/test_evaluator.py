"""Test RL model evaluator and evaluation metrics.

Covers average return, profit ratio (RR), win rate calculations,
Sharpe ratio, max drawdown, and slippage analysis.
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, Mock, patch

from shared.ml.rl.evaluator import RLEvaluator


@pytest.fixture
def evaluator():
    """Create RLEvaluator instance with mocked config."""
    with patch("shared.config.loader.ConfigLoader.load") as mock_load:
        mock_load.return_value = {
            "slippage_test_values": [0.00, 0.05, 0.10, 0.15, 0.20],
            "continuous_action": {
                "entry_threshold": 0.3,
                "exit_threshold": 0.1,
            },
        }
        with patch("shared.ml.rl.env.RLEnvConfig.from_yaml") as mock_env_config:
            mock_env_config.return_value = create_mock_env_config()
            return RLEvaluator()


@pytest.fixture
def mock_model():
    """Create mock RL model."""
    model = MagicMock()
    model.predict = MagicMock(return_value=(0, None))  # (action, state)
    return model


@pytest.fixture
def sample_test_data():
    """Generate sample test data (features and prices)."""
    n_steps = 100
    n_features = 25
    n_days = 3

    np.random.seed(42)
    test_days = [
        np.random.randn(n_steps, n_features).astype(np.float32) for _ in range(n_days)
    ]

    # Generate realistic price data
    test_prices = []
    for _ in range(n_days):
        prices = np.zeros((n_steps, 4), dtype=np.float32)
        base_price = 350.0
        for i in range(n_steps):
            price = base_price + np.random.normal(0, 0.5)
            prices[i] = [
                price - 0.1,  # open
                price + 0.3,  # high
                price - 0.3,  # low
                price,  # close
            ]
            base_price = price
        test_prices.append(prices)

    return test_days, test_prices


def create_mock_env_config():
    """Create mock environment config."""
    config = MagicMock()
    config.initial_balance = 100_000_000
    config.commission_rate = 0.00003
    config.tick_size = 0.05
    config.tick_value = 250_000
    config.contract_multiplier = 250_000
    config.max_contracts = 1
    config.slippage = 0.0
    config.margin_rate = 0.15
    config.n_market_features = 25
    config.n_aux_features = 0
    config.n_position_features = 6
    config.market_open = "09:00"
    config.market_close = "15:45"
    config.w_profit = 5.0
    config.w_cost = 2.0
    config.w_risk = 0.3
    config.w_mtm = 0.0
    config.inaction_penalty = 0.0
    config.reward_scale = 100.0
    config.max_loss = -5_000_000
    config.loss_penalty_coeff = 2.0
    return config


class TestEvaluationMetrics:
    """Test core evaluation metric calculations."""

    def test_calc_max_drawdown_no_losses(self, evaluator):
        """Test max drawdown with all positive returns."""
        daily_returns = [0.01, 0.02, 0.01, 0.03, 0.02]
        mdd = evaluator._calc_max_drawdown(daily_returns)

        # With all positive returns, drawdown should be minimal
        assert mdd <= 0
        assert mdd >= -0.1

    def test_calc_max_drawdown_with_losses(self, evaluator):
        """Test max drawdown with losses."""
        # Simulate drawdown: gain, gain, loss, loss, recovery
        daily_returns = [0.05, 0.03, -0.04, -0.06, 0.02]
        mdd = evaluator._calc_max_drawdown(daily_returns)

        # Should capture the drawdown from peak to trough
        assert mdd < 0
        # Peak is after 2nd day, trough is after 4th day
        # Cumulative: 1.05, 1.0815, 1.0382, 0.9759
        # MDD ≈ (0.9759 - 1.0815) / 1.0815 ≈ -0.0976
        assert mdd == pytest.approx(-0.0976, abs=0.01)

    def test_calc_max_drawdown_empty_returns(self, evaluator):
        """Test max drawdown with empty returns."""
        mdd = evaluator._calc_max_drawdown([])
        assert mdd == 0.0

    def test_calc_max_drawdown_flat_returns(self, evaluator):
        """Test max drawdown with zero returns."""
        daily_returns = [0.0, 0.0, 0.0, 0.0]
        mdd = evaluator._calc_max_drawdown(daily_returns)
        assert mdd == 0.0

    def test_calc_sharpe_ratio_positive_returns(self, evaluator):
        """Test Sharpe ratio with positive returns."""
        # Consistent positive returns above risk-free rate
        daily_returns = [0.002] * 252  # 0.2% daily for a year

        sharpe = evaluator._calc_sharpe(daily_returns, risk_free_rate=0.035)

        # Should be positive with consistent positive returns
        assert sharpe > 0
        # Sharpe should be high for consistent returns
        assert sharpe > 2.0

    def test_calc_sharpe_ratio_volatile_returns(self, evaluator):
        """Test Sharpe ratio with volatile returns."""
        np.random.seed(42)
        # Volatile returns with positive mean
        daily_returns = np.random.normal(0.001, 0.01, 252).tolist()

        sharpe = evaluator._calc_sharpe(daily_returns, risk_free_rate=0.035)

        # Sharpe will be lower due to volatility
        assert isinstance(sharpe, float)
        assert np.isfinite(sharpe)

    def test_calc_sharpe_ratio_zero_std(self, evaluator):
        """Test Sharpe ratio with zero standard deviation."""
        # All returns identical (zero volatility)
        daily_returns = [0.001] * 100

        sharpe = evaluator._calc_sharpe(daily_returns, risk_free_rate=0.035)

        # Should return 0 when std is zero
        assert sharpe == 0.0

    def test_calc_sharpe_ratio_insufficient_data(self, evaluator):
        """Test Sharpe ratio with insufficient data."""
        # Less than 2 data points
        sharpe = evaluator._calc_sharpe([0.01], risk_free_rate=0.035)
        assert sharpe == 0.0

        sharpe_empty = evaluator._calc_sharpe([], risk_free_rate=0.035)
        assert sharpe_empty == 0.0

    def test_calc_sharpe_ratio_annualization(self, evaluator):
        """Test Sharpe ratio is annualized (sqrt(252))."""
        # Create returns with known properties
        daily_mean = 0.001  # 0.1% daily
        daily_std = 0.01  # 1% daily volatility
        np.random.seed(42)
        daily_returns = np.random.normal(daily_mean, daily_std, 252).tolist()

        sharpe = evaluator._calc_sharpe(daily_returns, risk_free_rate=0.035)

        # Sharpe should be annualized (multiplied by sqrt(252))
        # Manual calculation for verification
        returns = np.array(daily_returns)
        daily_rf = (1 + 0.035) ** (1 / 252) - 1
        excess = returns - daily_rf
        expected_sharpe = np.mean(excess) / np.std(excess) * np.sqrt(252)

        assert sharpe == pytest.approx(expected_sharpe, rel=0.01)


class TestEvaluateModelMetrics:
    """Test evaluate_model metric calculations with mocked environment."""

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_evaluate_model_returns_correct_structure(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test evaluate_model returns all required metrics."""
        test_days, test_prices = sample_test_data

        # Mock environment to simulate successful episode
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (
            np.zeros(31, dtype=np.float32),
            {"balance": 100_000_000, "n_trades": 0},
        )
        mock_env_instance.step.return_value = (
            np.zeros(31, dtype=np.float32),
            0.0,
            True,  # terminated
            False,  # truncated
            {"balance": 100_500_000, "n_trades": 2},
        )
        mock_env_instance.wins = 1
        mock_env_instance.losses = 1
        mock_env_instance.trade_history = [
            {"pnl": 300_000},  # Win
            {"pnl": -200_000},  # Loss
        ]
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, test_days, test_prices, slippage=0.0
        )

        # Verify all required metrics are present
        assert "avg_return_pct" in metrics
        assert "total_return_pct" in metrics
        assert "rr_ratio" in metrics
        assert "win_rate_pct" in metrics
        assert "total_trades" in metrics
        assert "max_drawdown_pct" in metrics
        assert "sharpe_ratio" in metrics
        assert "daily_returns" in metrics
        assert "slippage" in metrics

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_average_return_calculation(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test average return is calculated correctly from daily returns."""
        test_days, test_prices = sample_test_data

        # Mock environment with known returns
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {"balance": 100_000_000})

        # Simulate 3 days with different returns
        returns_config = [
            {"balance": 102_000_000},  # +2% return
            {"balance": 101_000_000},  # +1% return
            {"balance": 103_000_000},  # +3% return
        ]

        call_count = [0]

        def step_side_effect(*args, **kwargs):
            result_balance = returns_config[call_count[0]]["balance"]
            call_count[0] += 1
            return (
                np.zeros(31),
                0.0,
                True,
                False,
                {"balance": result_balance, "n_trades": 0},
            )

        mock_env_instance.step.side_effect = step_side_effect
        mock_env_instance.wins = 0
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = []
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, test_days, test_prices, slippage=0.0
        )

        # Average return should be (2 + 1 + 3) / 3 = 2.0%
        assert metrics["avg_return_pct"] == pytest.approx(2.0, abs=0.01)

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_profit_ratio_calculation(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test profit ratio (RR ratio) is calculated correctly."""
        test_days, test_prices = sample_test_data

        # Mock environment with specific trade history
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (
            np.zeros(31),
            {"balance": 100_000_000, "n_trades": 0},
        )
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_000_000, "n_trades": 4},
        )

        # Trade history: 2 wins, 2 losses
        # Gross profit: 500K + 300K = 800K
        # Gross loss: 200K + 100K = 300K
        # RR ratio: 800K / 300K = 2.67
        mock_env_instance.wins = 2
        mock_env_instance.losses = 2
        mock_env_instance.trade_history = [
            {"pnl": 500_000},  # Win
            {"pnl": -200_000},  # Loss
            {"pnl": 300_000},  # Win
            {"pnl": -100_000},  # Loss
        ]
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=0.0
        )

        # RR ratio should be 800000 / 300000 = 2.67
        assert metrics["rr_ratio"] == pytest.approx(2.67, abs=0.01)

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_profit_ratio_no_losses(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test profit ratio when there are no losses (should be inf)."""
        test_days, test_prices = sample_test_data

        # Mock environment with only winning trades
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {})
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_000_000, "n_trades": 2},
        )
        mock_env_instance.wins = 2
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = [
            {"pnl": 500_000},  # Win
            {"pnl": 300_000},  # Win
        ]
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=0.0
        )

        # RR ratio should be infinity when no losses
        assert metrics["rr_ratio"] == float("inf")

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_win_rate_calculation(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test win rate is calculated correctly."""
        test_days, test_prices = sample_test_data

        # Mock environment with known win/loss counts
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {})
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_000_000, "n_trades": 10},
        )

        # 7 wins out of 10 trades = 70% win rate
        mock_env_instance.wins = 7
        mock_env_instance.losses = 3
        mock_env_instance.trade_history = [
            {"pnl": 100_000},
            {"pnl": 200_000},
            {"pnl": -50_000},
            {"pnl": 150_000},
            {"pnl": 100_000},
            {"pnl": -30_000},
            {"pnl": 80_000},
            {"pnl": 120_000},
            {"pnl": -40_000},
            {"pnl": 90_000},
        ]
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=0.0
        )

        # Win rate should be 7/10 = 70%
        assert metrics["win_rate_pct"] == pytest.approx(70.0, abs=0.1)

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_win_rate_no_trades(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test win rate when there are no trades."""
        test_days, test_prices = sample_test_data

        # Mock environment with no trades
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {})
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_000_000, "n_trades": 0},
        )
        mock_env_instance.wins = 0
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = []
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=0.0
        )

        # Win rate should be 0% when no trades
        assert metrics["win_rate_pct"] == 0.0
        assert metrics["total_trades"] == 0

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_win_rate_all_wins(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test win rate with 100% winning trades."""
        test_days, test_prices = sample_test_data

        # Mock environment with all winning trades
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {})
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_000_000, "n_trades": 5},
        )
        mock_env_instance.wins = 5
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = [
            {"pnl": 100_000},
            {"pnl": 200_000},
            {"pnl": 150_000},
            {"pnl": 80_000},
            {"pnl": 120_000},
        ]
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=0.0
        )

        # Win rate should be 100%
        assert metrics["win_rate_pct"] == 100.0

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_total_return_accumulation(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test total return is sum of daily returns."""
        test_days, test_prices = sample_test_data

        # Mock environment with known daily returns
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {"balance": 100_000_000})

        returns_config = [
            {"balance": 101_000_000},  # +1%
            {"balance": 102_000_000},  # +2%
            {"balance": 101_500_000},  # +1.5%
        ]

        call_count = [0]

        def step_side_effect(*args, **kwargs):
            result_balance = returns_config[call_count[0]]["balance"]
            call_count[0] += 1
            return (
                np.zeros(31),
                0.0,
                True,
                False,
                {"balance": result_balance, "n_trades": 0},
            )

        mock_env_instance.step.side_effect = step_side_effect
        mock_env_instance.wins = 0
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = []
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, test_days, test_prices, slippage=0.0
        )

        # Total return should be 1 + 2 + 1.5 = 4.5%
        assert metrics["total_return_pct"] == pytest.approx(4.5, abs=0.01)


class TestEvaluatorInitialization:
    """Test RLEvaluator initialization and configuration."""

    def test_evaluator_initialization_default_config(self):
        """Test evaluator initializes with default config path."""
        with patch("shared.config.loader.ConfigLoader.load") as mock_load:
            mock_load.return_value = {
                "slippage_test_values": [0.00, 0.05, 0.10],
                "continuous_action": {},
            }
            with patch("shared.ml.rl.env.RLEnvConfig.from_yaml") as mock_env:
                mock_env.return_value = create_mock_env_config()
                evaluator = RLEvaluator()

                assert evaluator.config is not None
                assert evaluator.env_config is not None
                assert evaluator.slippage_values == [0.00, 0.05, 0.10]

    def test_evaluator_custom_config_path(self):
        """Test evaluator with custom config path."""
        with patch("shared.config.loader.ConfigLoader.load") as mock_load:
            mock_load.return_value = {
                "slippage_test_values": [0.0, 0.1, 0.2],
                "continuous_action": {},
            }
            with patch("shared.ml.rl.env.RLEnvConfig.from_yaml") as mock_env:
                mock_env.return_value = create_mock_env_config()
                evaluator = RLEvaluator(config_path="custom/path.yaml")

                mock_load.assert_called_once_with("custom/path.yaml")
                assert evaluator.slippage_values == [0.0, 0.1, 0.2]

    def test_slippage_values_loaded_from_config(self, evaluator):
        """Test slippage test values are loaded from config."""
        assert evaluator.slippage_values == [0.00, 0.05, 0.10, 0.15, 0.20]


class TestMetricRounding:
    """Test that metrics are rounded to appropriate precision."""

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_metrics_rounded_correctly(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test all metrics are rounded to correct decimal places."""
        test_days, test_prices = sample_test_data

        # Mock environment
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {})
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_123_456, "n_trades": 7},
        )
        mock_env_instance.wins = 4
        mock_env_instance.losses = 3
        mock_env_instance.trade_history = [
            {"pnl": 123_456.789},
            {"pnl": -87_654.321},
            {"pnl": 234_567.891},
            {"pnl": -123_456.789},
            {"pnl": 345_678.912},
            {"pnl": -234_567.891},
            {"pnl": 456_789.123},
        ]
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=0.0
        )

        # Verify rounding precision
        # avg_return_pct and total_return_pct: 2 decimal places
        assert len(str(metrics["avg_return_pct"]).split(".")[-1]) <= 2
        assert len(str(metrics["total_return_pct"]).split(".")[-1]) <= 2

        # rr_ratio: 2 decimal places
        if metrics["rr_ratio"] != float("inf"):
            assert len(str(metrics["rr_ratio"]).split(".")[-1]) <= 2

        # win_rate_pct: 1 decimal place
        assert len(str(metrics["win_rate_pct"]).split(".")[-1]) <= 1

        # max_drawdown_pct: 2 decimal places
        assert len(str(metrics["max_drawdown_pct"]).split(".")[-1]) <= 2

        # sharpe_ratio: 2 decimal places
        assert len(str(metrics["sharpe_ratio"]).split(".")[-1]) <= 2


class TestSlippageHandling:
    """Test slippage parameter handling in evaluation."""

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_slippage_applied_to_config(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test slippage is applied to environment config."""
        test_days, test_prices = sample_test_data

        # Mock environment
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {})
        mock_env_instance.step.return_value = (
            np.zeros(31),
            0.0,
            True,
            False,
            {"balance": 100_000_000, "n_trades": 0},
        )
        mock_env_instance.wins = 0
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = []
        mock_env_class.return_value = mock_env_instance

        slippage_value = 0.15
        metrics = evaluator.evaluate_model(
            mock_model, [test_days[0]], [test_prices[0]], slippage=slippage_value
        )

        # Verify slippage is recorded in metrics
        assert metrics["slippage"] == slippage_value

        # Verify environment was created with slippage config
        call_args = mock_env_class.call_args
        config_used = call_args[1]["config"]
        assert config_used.slippage == slippage_value


class TestDailyReturnsTracking:
    """Test daily returns are tracked correctly."""

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_daily_returns_list_populated(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test daily returns list contains all episode returns."""
        test_days, test_prices = sample_test_data

        # Mock environment with specific returns for each day
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {"balance": 100_000_000})

        expected_daily_returns = [0.02, 0.01, 0.03]  # 2%, 1%, 3%
        call_count = [0]

        def step_side_effect(*args, **kwargs):
            balance = 100_000_000 * (1 + expected_daily_returns[call_count[0]])
            call_count[0] += 1
            return (
                np.zeros(31),
                0.0,
                True,
                False,
                {"balance": balance, "n_trades": 0},
            )

        mock_env_instance.step.side_effect = step_side_effect
        mock_env_instance.wins = 0
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = []
        mock_env_class.return_value = mock_env_instance

        metrics = evaluator.evaluate_model(
            mock_model, test_days, test_prices, slippage=0.0
        )

        # Verify daily returns list
        assert len(metrics["daily_returns"]) == 3
        for i, ret in enumerate(metrics["daily_returns"]):
            assert ret == pytest.approx(expected_daily_returns[i], abs=0.0001)

    @patch("shared.ml.rl.evaluator.FuturesTradingEnv")
    def test_daily_returns_used_for_sharpe_and_mdd(
        self, mock_env_class, evaluator, mock_model, sample_test_data
    ):
        """Test daily returns are used to calculate Sharpe and max drawdown."""
        test_days, test_prices = sample_test_data

        # Mock environment with known returns
        mock_env_instance = MagicMock()
        mock_env_instance.reset.return_value = (np.zeros(31), {"balance": 100_000_000})

        # Specific pattern: up, up, down, down, up
        daily_returns = [0.05, 0.03, -0.04, -0.06, 0.02]
        call_count = [0]

        def step_side_effect(*args, **kwargs):
            balance = 100_000_000 * (1 + daily_returns[call_count[0]])
            call_count[0] += 1
            return (
                np.zeros(31),
                0.0,
                True,
                False,
                {"balance": balance, "n_trades": 0},
            )

        mock_env_instance.step.side_effect = step_side_effect
        mock_env_instance.wins = 0
        mock_env_instance.losses = 0
        mock_env_instance.trade_history = []
        mock_env_class.return_value = mock_env_instance

        # Create 5-day test data
        test_days_5 = [sample_test_data[0][0]] * 5
        test_prices_5 = [sample_test_data[1][0]] * 5

        metrics = evaluator.evaluate_model(
            mock_model, test_days_5, test_prices_5, slippage=0.0
        )

        # Sharpe and MDD should be calculated from these returns
        assert isinstance(metrics["sharpe_ratio"], float)
        assert isinstance(metrics["max_drawdown_pct"], float)

        # MDD should be negative (there were losses)
        assert metrics["max_drawdown_pct"] < 0
