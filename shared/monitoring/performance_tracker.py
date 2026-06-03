"""Performance tracking for RL model monitoring.

Tracks rolling Sharpe ratio and win rate over configurable windows (5-day and 20-day)
to detect model performance degradation in production.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    """Individual trade outcome record.

    Attributes:
        timestamp: When the trade was closed
        pnl: Profit/loss in currency units
        pnl_pct: Profit/loss percentage
        is_win: Whether the trade was profitable
    """

    timestamp: datetime
    pnl: float
    pnl_pct: float
    is_win: bool


@dataclass
class PerformanceConfig:
    """Performance tracker configuration.

    Attributes:
        window_5d_bars: Number of bars for 5-day window (e.g., 5 for daily, 1200 for 1-min)
        window_20d_bars: Number of bars for 20-day window (e.g., 20 for daily, 4800 for 1-min)
        risk_free_rate: Annual risk-free rate for Sharpe calculation
        min_trades: Minimum trades required for metrics calculation
    """

    window_5d_bars: int = 5  # Default for daily data
    window_20d_bars: int = 20  # Default for daily data
    risk_free_rate: float = 0.03  # 3% annual
    min_trades: int = 2  # Minimum trades to compute Sharpe


@dataclass
class BenchmarkMetrics:
    """Training benchmark metrics for comparison.

    Attributes:
        sharpe_ratio: Benchmark Sharpe ratio from training/validation
        win_rate: Benchmark win rate from training/validation (0-100)
        avg_pnl_pct: Benchmark average PnL percentage
    """

    sharpe_ratio: float
    win_rate: float  # 0-100
    avg_pnl_pct: float


@dataclass
class PerformanceMetrics:
    """Current performance metrics.

    Attributes:
        sharpe_5d: 5-day rolling Sharpe ratio (annualized)
        sharpe_20d: 20-day rolling Sharpe ratio (annualized)
        win_rate_5d: 5-day rolling win rate (0-100)
        win_rate_20d: 20-day rolling win rate (0-100)
        avg_pnl_pct_5d: 5-day average PnL percentage
        avg_pnl_pct_20d: 20-day average PnL percentage
        total_trades_5d: Number of trades in 5-day window
        total_trades_20d: Number of trades in 20-day window
        sharpe_degradation_5d: Degradation vs benchmark (negative if worse)
        sharpe_degradation_20d: Degradation vs benchmark (negative if worse)
        win_rate_degradation_5d: Degradation vs benchmark (negative if worse)
        win_rate_degradation_20d: Degradation vs benchmark (negative if worse)
        timestamp: When metrics were computed
    """

    sharpe_5d: float | None
    sharpe_20d: float | None
    win_rate_5d: float | None
    win_rate_20d: float | None
    avg_pnl_pct_5d: float | None
    avg_pnl_pct_20d: float | None
    total_trades_5d: int
    total_trades_20d: int
    sharpe_degradation_5d: float | None = None
    sharpe_degradation_20d: float | None = None
    win_rate_degradation_5d: float | None = None
    win_rate_degradation_20d: float | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert metrics to dictionary."""
        return {
            "sharpe_5d": self.sharpe_5d,
            "sharpe_20d": self.sharpe_20d,
            "win_rate_5d": self.win_rate_5d,
            "win_rate_20d": self.win_rate_20d,
            "avg_pnl_pct_5d": self.avg_pnl_pct_5d,
            "avg_pnl_pct_20d": self.avg_pnl_pct_20d,
            "total_trades_5d": self.total_trades_5d,
            "total_trades_20d": self.total_trades_20d,
            "sharpe_degradation_5d": self.sharpe_degradation_5d,
            "sharpe_degradation_20d": self.sharpe_degradation_20d,
            "win_rate_degradation_5d": self.win_rate_degradation_5d,
            "win_rate_degradation_20d": self.win_rate_degradation_20d,
            "timestamp": self.timestamp.isoformat(),
        }


class PerformanceTracker:
    """Track rolling performance metrics for RL model monitoring.

    Maintains rolling windows of trade outcomes and computes Sharpe ratio and
    win rate over 5-day and 20-day periods. Compares against training benchmarks
    to detect performance degradation.

    Example:
        >>> tracker = PerformanceTracker()
        >>> tracker.set_benchmark(sharpe_ratio=1.5, win_rate=65.0, avg_pnl_pct=2.0)
        >>> tracker.record_trade(pnl=1000, pnl_pct=2.5)
        >>> metrics = tracker.get_metrics()
        >>> print(f"5d Sharpe: {metrics.sharpe_5d}")
    """

    def __init__(
        self,
        config: PerformanceConfig | None = None,
        benchmark: BenchmarkMetrics | None = None,
    ):
        """Initialize performance tracker.

        Args:
            config: Performance tracking configuration. Uses defaults if None.
            benchmark: Training benchmark metrics for comparison. Optional.
        """
        self.config = config or PerformanceConfig()
        self.benchmark = benchmark

        # Rolling windows for trade outcomes
        self._trades_5d: Deque[TradeOutcome] = deque(
            maxlen=self.config.window_5d_bars
        )
        self._trades_20d: Deque[TradeOutcome] = deque(
            maxlen=self.config.window_20d_bars
        )

        logger.info(
            f"PerformanceTracker initialized: "
            f"5d_window={self.config.window_5d_bars}, "
            f"20d_window={self.config.window_20d_bars}, "
            f"risk_free_rate={self.config.risk_free_rate}"
        )

    def set_benchmark(
        self,
        sharpe_ratio: float,
        win_rate: float,
        avg_pnl_pct: float,
    ) -> None:
        """Set benchmark metrics from training/validation period.

        Args:
            sharpe_ratio: Benchmark Sharpe ratio
            win_rate: Benchmark win rate (0-100)
            avg_pnl_pct: Benchmark average PnL percentage
        """
        self.benchmark = BenchmarkMetrics(
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl_pct,
        )
        logger.info(
            f"Benchmark set: Sharpe={sharpe_ratio:.3f}, "
            f"WinRate={win_rate:.1f}%, AvgPnL={avg_pnl_pct:.2f}%"
        )

    def record_trade(
        self,
        pnl: float,
        pnl_pct: float,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a closed trade outcome.

        Args:
            pnl: Profit/loss in currency units
            pnl_pct: Profit/loss percentage
            timestamp: Trade close time. Uses current time if None.
        """
        ts = timestamp or datetime.now()
        outcome = TradeOutcome(
            timestamp=ts,
            pnl=pnl,
            pnl_pct=pnl_pct,
            is_win=(pnl > 0),
        )

        # Add to both windows (deque handles maxlen automatically)
        self._trades_5d.append(outcome)
        self._trades_20d.append(outcome)

        logger.debug(
            f"Trade recorded: PnL={pnl:.2f} ({pnl_pct:+.2f}%), "
            f"5d_count={len(self._trades_5d)}, 20d_count={len(self._trades_20d)}"
        )

    def _calculate_sharpe(
        self, trades: list[TradeOutcome], annualization_factor: int = 252
    ) -> float | None:
        """Calculate Sharpe ratio from trade outcomes.

        Args:
            trades: List of trade outcomes
            annualization_factor: Factor to annualize Sharpe (252 for daily, 252*390 for 1-min)

        Returns:
            Annualized Sharpe ratio, or None if insufficient data
        """
        if len(trades) < self.config.min_trades:
            return None

        # Extract PnL percentages
        returns = np.array([t.pnl_pct / 100.0 for t in trades])

        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 0.0

        # Daily risk-free rate
        daily_rf = self.config.risk_free_rate / 252

        # Sharpe ratio
        sharpe = (mean_return - daily_rf) / std_return

        # Annualize
        return float(sharpe * np.sqrt(annualization_factor))

    def _calculate_win_rate(self, trades: list[TradeOutcome]) -> float | None:
        """Calculate win rate from trade outcomes.

        Args:
            trades: List of trade outcomes

        Returns:
            Win rate percentage (0-100), or None if no trades
        """
        if len(trades) == 0:
            return None

        winning_trades = sum(1 for t in trades if t.is_win)
        return (winning_trades / len(trades)) * 100.0

    def _calculate_avg_pnl_pct(self, trades: list[TradeOutcome]) -> float | None:
        """Calculate average PnL percentage from trade outcomes.

        Args:
            trades: List of trade outcomes

        Returns:
            Average PnL percentage, or None if no trades
        """
        if len(trades) == 0:
            return None

        return np.mean([t.pnl_pct for t in trades])

    def get_metrics(self) -> PerformanceMetrics:
        """Compute current performance metrics.

        Calculates rolling Sharpe ratio, win rate, and average PnL for both
        5-day and 20-day windows. If benchmark is set, also computes degradation.

        Returns:
            PerformanceMetrics with current values and benchmark comparison
        """
        # Convert deques to lists for calculations
        trades_5d = list(self._trades_5d)
        trades_20d = list(self._trades_20d)

        # Calculate metrics for both windows
        sharpe_5d = self._calculate_sharpe(trades_5d)
        sharpe_20d = self._calculate_sharpe(trades_20d)

        win_rate_5d = self._calculate_win_rate(trades_5d)
        win_rate_20d = self._calculate_win_rate(trades_20d)

        avg_pnl_pct_5d = self._calculate_avg_pnl_pct(trades_5d)
        avg_pnl_pct_20d = self._calculate_avg_pnl_pct(trades_20d)

        # Calculate degradation if benchmark is set
        sharpe_deg_5d = None
        sharpe_deg_20d = None
        win_rate_deg_5d = None
        win_rate_deg_20d = None

        if self.benchmark is not None:
            if sharpe_5d is not None:
                sharpe_deg_5d = sharpe_5d - self.benchmark.sharpe_ratio
            if sharpe_20d is not None:
                sharpe_deg_20d = sharpe_20d - self.benchmark.sharpe_ratio
            if win_rate_5d is not None:
                win_rate_deg_5d = win_rate_5d - self.benchmark.win_rate
            if win_rate_20d is not None:
                win_rate_deg_20d = win_rate_20d - self.benchmark.win_rate

        return PerformanceMetrics(
            sharpe_5d=sharpe_5d,
            sharpe_20d=sharpe_20d,
            win_rate_5d=win_rate_5d,
            win_rate_20d=win_rate_20d,
            avg_pnl_pct_5d=avg_pnl_pct_5d,
            avg_pnl_pct_20d=avg_pnl_pct_20d,
            total_trades_5d=len(trades_5d),
            total_trades_20d=len(trades_20d),
            sharpe_degradation_5d=sharpe_deg_5d,
            sharpe_degradation_20d=sharpe_deg_20d,
            win_rate_degradation_5d=win_rate_deg_5d,
            win_rate_degradation_20d=win_rate_deg_20d,
            timestamp=datetime.now(),
        )

    def reset(self) -> None:
        """Clear all trade history.

        Useful when starting a new monitoring period or after model retraining.
        """
        self._trades_5d.clear()
        self._trades_20d.clear()
        logger.info("Performance tracker reset")

    @property
    def total_trades(self) -> int:
        """Get total number of trades in 20-day window.

        Returns:
            Number of trades in the longer window
        """
        return len(self._trades_20d)

    @property
    def has_benchmark(self) -> bool:
        """Check if benchmark is set.

        Returns:
            True if benchmark metrics are available
        """
        return self.benchmark is not None
