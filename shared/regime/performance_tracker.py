"""Regime Performance Tracker

Tracks trading performance per market regime for model attribution and optimization.

Maintains performance metrics for each regime:
- Tracks entries and exits per regime
- Calculates win rate, average PnL, Sharpe ratio, total trades
- Provides regime-specific performance attribution
- Optional Redis backing for persistence

Usage:
    tracker = RegimePerformanceTracker()

    # Record entry
    tracker.record_entry(
        regime="TRENDING_BULL",
        code="101S6000",
        price=350.5,
        timestamp=datetime.now(),
        model_name="setup_a_gap_reversion",
    )

    # Record exit
    tracker.record_exit(
        regime="TRENDING_BULL",
        code="101S6000",
        price=352.0,
        timestamp=datetime.now(),
        pnl=1500.0,
        model_name="setup_a_gap_reversion",
    )

    # Get regime stats
    stats = tracker.get_regime_stats("TRENDING_BULL")
    print(f"Win rate: {stats['win_rate']:.2%}")

    # Get all stats
    all_stats = tracker.get_all_stats()
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np

from shared.exceptions import ValidationError

logger = logging.getLogger(__name__)


# Validation constants
MIN_MAX_TRADES = 10
MAX_MAX_TRADES = 10000
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


@dataclass
class TradeRecord:
    """Record of a single trade for regime performance tracking."""

    regime: str
    code: str
    entry_price: float
    entry_timestamp: datetime
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    pnl: Optional[float] = None
    model_name: Optional[str] = None
    side: str = "LONG"  # "LONG" or "SHORT"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_price is not None and self.pnl is not None

    @property
    def is_winner(self) -> bool:
        """Check if trade is a winner (positive PnL)."""
        if not self.is_closed:
            return False
        return self.pnl > 0

    @property
    def return_pct(self) -> float:
        """Calculate return percentage.

        For LONG positions: (exit - entry) / entry
        For SHORT positions: (entry - exit) / entry (negated)
        """
        if not self.is_closed:
            return 0.0
        if self.entry_price == 0:
            return 0.0
        raw = (self.exit_price - self.entry_price) / self.entry_price
        if self.side == "SHORT":
            return -raw
        return raw

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "regime": self.regime,
            "code": self.code,
            "entry_price": self.entry_price,
            "entry_timestamp": self.entry_timestamp.isoformat(),
            "exit_price": self.exit_price,
            "exit_timestamp": (
                self.exit_timestamp.isoformat() if self.exit_timestamp else None
            ),
            "pnl": self.pnl,
            "model_name": self.model_name,
            "side": self.side,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradeRecord:
        """Create from dictionary."""
        return cls(
            regime=data["regime"],
            code=data["code"],
            entry_price=data["entry_price"],
            entry_timestamp=datetime.fromisoformat(data["entry_timestamp"]),
            exit_price=data.get("exit_price"),
            exit_timestamp=(
                datetime.fromisoformat(data["exit_timestamp"])
                if data.get("exit_timestamp")
                else None
            ),
            pnl=data.get("pnl"),
            model_name=data.get("model_name"),
            side=data.get("side", "LONG"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RegimeStats:
    """Performance statistics for a regime."""

    regime: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    model_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "regime": self.regime,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "avg_pnl": self.avg_pnl,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "model_distribution": self.model_distribution,
        }


@dataclass
class RegimePerformanceConfig:
    """Configuration for regime performance tracker."""

    # Maximum trades to keep in memory per regime
    max_trades_per_regime: int = 1000

    # Maximum open positions to track
    max_open_positions: int = 100

    # Minimum trades required for valid statistics
    min_trades_for_stats: int = 10

    # Risk-free rate for Sharpe ratio calculation (annual)
    risk_free_rate: float = 0.02  # 2%

    # Redis configuration (optional)
    redis_enabled: bool = False
    redis_key_prefix: str = "regime_performance"
    redis_db: int = 1  # DB 1 is standard for this project
    # Per AGENTS.md §2.4: every Redis key MUST define a TTL. Regime stats are
    # running aggregates that span many trading days, so the default matches
    # ``RUNNING_TOTALS_TTL_SECONDS`` in ``shared/streaming/trading_state.py``
    # (30 days). Tune via YAML if a different retention is desired.
    redis_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (MIN_MAX_TRADES <= self.max_trades_per_regime <= MAX_MAX_TRADES):
            raise ValueError(
                f"max_trades_per_regime must be between {MIN_MAX_TRADES} "
                f"and {MAX_MAX_TRADES}, got {self.max_trades_per_regime}"
            )

        if not (MIN_MAX_TRADES <= self.max_open_positions <= MAX_MAX_TRADES):
            raise ValueError(
                f"max_open_positions must be between {MIN_MAX_TRADES} "
                f"and {MAX_MAX_TRADES}, got {self.max_open_positions}"
            )

        if self.min_trades_for_stats < 1:
            raise ValueError(
                f"min_trades_for_stats must be >= 1, got {self.min_trades_for_stats}"
            )

        if not (0 <= self.risk_free_rate <= 1.0):
            raise ValueError(
                f"risk_free_rate must be between 0 and 1.0, got {self.risk_free_rate}"
            )

        if self.redis_db < 0:
            raise ValueError(f"redis_db must be >= 0, got {self.redis_db}")

        if self.redis_ttl_seconds <= 0:
            raise ValueError(
                f"redis_ttl_seconds must be > 0, got {self.redis_ttl_seconds}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegimePerformanceConfig:
        """Create config from dict with validation.

        Args:
            data: Configuration dictionary

        Returns:
            Validated RegimePerformanceConfig

        Raises:
            ValueError: If validation fails
            TypeError: If type validation fails
        """
        max_trades = data.get("max_trades_per_regime", 1000)
        max_open = data.get("max_open_positions", 100)
        min_trades = data.get("min_trades_for_stats", 10)
        risk_free = data.get("risk_free_rate", 0.02)
        redis_enabled = data.get("redis_enabled", False)
        redis_prefix = data.get("redis_key_prefix", "regime_performance")
        redis_db = data.get("redis_db", 1)
        redis_ttl_seconds = data.get("redis_ttl_seconds", 60 * 60 * 24 * 30)

        # Type validation
        if not isinstance(max_trades, int):
            raise TypeError(
                f"max_trades_per_regime must be int, got {type(max_trades)}"
            )
        if not isinstance(max_open, int):
            raise TypeError(f"max_open_positions must be int, got {type(max_open)}")
        if not isinstance(min_trades, int):
            raise TypeError(f"min_trades_for_stats must be int, got {type(min_trades)}")
        if not isinstance(risk_free, (int, float)):
            raise TypeError(f"risk_free_rate must be numeric, got {type(risk_free)}")
        if not isinstance(redis_enabled, bool):
            raise TypeError(f"redis_enabled must be bool, got {type(redis_enabled)}")
        if not isinstance(redis_prefix, str):
            raise TypeError(f"redis_key_prefix must be str, got {type(redis_prefix)}")
        if not isinstance(redis_db, int):
            raise TypeError(f"redis_db must be int, got {type(redis_db)}")
        if not isinstance(redis_ttl_seconds, int) or isinstance(
            redis_ttl_seconds, bool
        ):
            raise TypeError(
                f"redis_ttl_seconds must be int, got {type(redis_ttl_seconds)}"
            )

        return cls(
            max_trades_per_regime=max_trades,
            max_open_positions=max_open,
            min_trades_for_stats=min_trades,
            risk_free_rate=risk_free,
            redis_enabled=redis_enabled,
            redis_key_prefix=redis_prefix,
            redis_db=redis_db,
            redis_ttl_seconds=redis_ttl_seconds,
        )


class RegimePerformanceTracker:
    """Track trading performance per market regime.

    Maintains in-memory performance tracking with optional Redis persistence.
    Calculates regime-specific metrics for model attribution and optimization.

    Thread-safe for single-threaded operation (typical trading scenario).
    For multi-threaded use, external synchronization required.
    """

    def __init__(self, config: Optional[RegimePerformanceConfig] = None):
        """Initialize tracker.

        Args:
            config: Performance tracker configuration. Uses defaults if None.
        """
        self.config = config or RegimePerformanceConfig()

        # In-memory storage: regime -> deque of closed trades
        self._closed_trades: dict[str, deque[TradeRecord]] = defaultdict(
            lambda: deque(maxlen=self.config.max_trades_per_regime)
        )

        # Open positions: (regime, code) -> TradeRecord
        self._open_positions: dict[tuple[str, str], TradeRecord] = {}

        # Cached statistics: regime -> RegimeStats
        self._stats_cache: dict[str, RegimeStats] = {}
        self._cache_dirty: set[str] = set()

        # Redis client (optional, lazy-initialized)
        self._redis_client: Optional[Any] = None

        logger.info(
            f"RegimePerformanceTracker initialized "
            f"(max_trades_per_regime={self.config.max_trades_per_regime}, "
            f"redis_enabled={self.config.redis_enabled})"
        )

    def record_entry(
        self,
        regime: str,
        code: str,
        price: float,
        timestamp: datetime,
        model_name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TradeRecord:
        """Record a trade entry.

        Args:
            regime: Market regime at entry
            code: Symbol/code
            price: Entry price
            timestamp: Entry timestamp
            model_name: Name of model that generated signal (optional)
            metadata: Additional metadata (optional)

        Returns:
            Created TradeRecord

        Raises:
            ValidationError: If validation fails
        """
        # Validation
        if not regime:
            raise ValidationError("regime cannot be empty")
        if not code:
            raise ValidationError("code cannot be empty")
        if price <= 0:
            raise ValidationError(f"price must be > 0, got {price}")

        # Check max open positions
        if len(self._open_positions) >= self.config.max_open_positions:
            logger.warning(
                f"Max open positions ({self.config.max_open_positions}) reached. "
                f"Entry for {code} will still be recorded."
            )

        # Create trade record
        trade = TradeRecord(
            regime=regime,
            code=code,
            entry_price=price,
            entry_timestamp=timestamp,
            model_name=model_name,
            metadata=metadata or {},
        )

        # Store in open positions
        key = (regime, code)
        if key in self._open_positions:
            logger.warning(
                f"Overwriting existing open position for {regime}/{code}. "
                f"Previous entry may not have been closed properly."
            )
        self._open_positions[key] = trade

        logger.debug(
            f"Recorded entry: regime={regime}, code={code}, price={price:.2f}, "
            f"model={model_name}, open_positions={len(self._open_positions)}"
        )

        return trade

    def record_exit(
        self,
        regime: str,
        code: str,
        price: float,
        timestamp: datetime,
        pnl: float,
        model_name: Optional[str] = None,
    ) -> Optional[TradeRecord]:
        """Record a trade exit.

        Args:
            regime: Market regime at exit (should match entry regime)
            code: Symbol/code
            price: Exit price
            timestamp: Exit timestamp
            pnl: Profit/loss in currency units
            model_name: Name of model that generated signal (optional)

        Returns:
            Closed TradeRecord if found, None if no matching open position

        Raises:
            ValidationError: If validation fails
        """
        # Validation
        if not regime:
            raise ValidationError("regime cannot be empty")
        if not code:
            raise ValidationError("code cannot be empty")
        if price <= 0:
            raise ValidationError(f"price must be > 0, got {price}")

        # Find matching open position
        key = (regime, code)
        trade = self._open_positions.pop(key, None)

        if trade is None:
            logger.warning(
                f"No matching open position found for {regime}/{code}. "
                f"Creating standalone exit record."
            )
            # Create a minimal trade record for the exit
            trade = TradeRecord(
                regime=regime,
                code=code,
                entry_price=price,  # Use exit price as entry (no entry data)
                entry_timestamp=timestamp,
                model_name=model_name,
            )

        # Update exit data
        trade.exit_price = price
        trade.exit_timestamp = timestamp
        trade.pnl = pnl
        if model_name:
            trade.model_name = model_name

        # Store in closed trades
        self._closed_trades[regime].append(trade)

        # Mark stats cache as dirty
        self._cache_dirty.add(regime)

        logger.debug(
            f"Recorded exit: regime={regime}, code={code}, price={price:.2f}, "
            f"pnl={pnl:.2f}, model={model_name}, "
            f"closed_trades={len(self._closed_trades[regime])}"
        )

        # Optionally persist to Redis
        if self.config.redis_enabled:
            self._persist_to_redis(regime)

        return trade

    def get_regime_stats(self, regime: str) -> dict[str, Any]:
        """Get performance statistics for a specific regime.

        Args:
            regime: Regime name

        Returns:
            Dictionary with performance metrics:
                - total_trades: Total number of closed trades
                - winning_trades: Number of winning trades
                - losing_trades: Number of losing trades
                - total_pnl: Total profit/loss
                - avg_pnl: Average profit/loss per trade
                - avg_win: Average winning trade
                - avg_loss: Average losing trade
                - win_rate: Percentage of winning trades
                - profit_factor: Ratio of gross profit to gross loss
                - sharpe_ratio: Risk-adjusted return metric
                - max_drawdown: Maximum drawdown from peak
                - model_distribution: Distribution of trades by model
        """
        # Check cache
        if regime not in self._cache_dirty and regime in self._stats_cache:
            return self._stats_cache[regime].to_dict()

        # Calculate fresh stats
        stats = self._calculate_stats(regime)
        self._stats_cache[regime] = stats
        self._cache_dirty.discard(regime)

        return stats.to_dict()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get performance statistics for all regimes.

        Returns:
            Dictionary mapping regime name to stats dictionary
        """
        result = {}
        for regime in self._closed_trades.keys():
            result[regime] = self.get_regime_stats(regime)
        return result

    def get_open_positions_count(self) -> int:
        """Get count of open positions."""
        return len(self._open_positions)

    def get_closed_trades_count(self, regime: Optional[str] = None) -> int:
        """Get count of closed trades.

        Args:
            regime: Specific regime (optional). If None, returns total across all regimes.

        Returns:
            Count of closed trades
        """
        if regime:
            return len(self._closed_trades.get(regime, []))
        return sum(len(trades) for trades in self._closed_trades.values())

    def clear_regime(self, regime: str):
        """Clear all data for a specific regime.

        Args:
            regime: Regime to clear
        """
        if regime in self._closed_trades:
            del self._closed_trades[regime]
        if regime in self._stats_cache:
            del self._stats_cache[regime]
        self._cache_dirty.discard(regime)

        # Remove open positions for this regime
        keys_to_remove = [k for k in self._open_positions if k[0] == regime]
        for key in keys_to_remove:
            del self._open_positions[key]

        logger.info(f"Cleared all data for regime: {regime}")

    def clear_all(self):
        """Clear all tracking data."""
        self._closed_trades.clear()
        self._open_positions.clear()
        self._stats_cache.clear()
        self._cache_dirty.clear()
        logger.info("Cleared all performance tracking data")

    def _calculate_stats(self, regime: str) -> RegimeStats:
        """Calculate performance statistics for a regime.

        Args:
            regime: Regime name

        Returns:
            RegimeStats object
        """
        trades = list(self._closed_trades.get(regime, []))
        closed_trades = [t for t in trades if t.is_closed]

        if len(closed_trades) < self.config.min_trades_for_stats:
            # Insufficient data for valid statistics
            return RegimeStats(regime=regime)

        # Basic counts
        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t.is_winner)
        losing_trades = total_trades - winning_trades

        # PnL calculations
        pnls = [t.pnl for t in closed_trades]
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

        wins = [t.pnl for t in closed_trades if t.is_winner]
        losses = [t.pnl for t in closed_trades if not t.is_winner]

        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        # Win rate
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # Profit factor
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0.0

        # Sharpe ratio (annualized)
        sharpe_ratio = self._calculate_sharpe_ratio(pnls)

        # Max drawdown
        max_drawdown = self._calculate_max_drawdown(pnls)

        # Model distribution
        model_distribution = defaultdict(int)
        for trade in closed_trades:
            if trade.model_name:
                model_distribution[trade.model_name] += 1

        return RegimeStats(
            regime=regime,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            model_distribution=dict(model_distribution),
        )

    def _calculate_sharpe_ratio(self, pnls: list[float]) -> float:
        """Calculate Sharpe ratio.

        Args:
            pnls: List of trade PnLs

        Returns:
            Annualized Sharpe ratio
        """
        if len(pnls) < 2:
            return 0.0

        returns = np.array(pnls)
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 0.0

        # Simple Sharpe: (mean - risk_free) / std
        # Annualization factor: sqrt(252) for daily trades
        # For intraday, we use sqrt(number of trades per year estimate)
        sharpe = (mean_return - self.config.risk_free_rate) / std_return

        return float(sharpe)

    def _calculate_max_drawdown(self, pnls: list[float]) -> float:
        """Calculate maximum drawdown.

        Args:
            pnls: List of trade PnLs

        Returns:
            Maximum drawdown (positive number)
        """
        if not pnls:
            return 0.0

        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

        return float(max_dd)

    def _persist_to_redis(self, regime: str):
        """Persist regime stats to Redis.

        Args:
            regime: Regime name
        """
        if not self.config.redis_enabled:
            return

        try:
            if self._redis_client is None:
                self._init_redis_client()

            stats = self.get_regime_stats(regime)
            key = f"{self.config.redis_key_prefix}:{regime}"

            # AGENTS.md §2.4 — every Redis key MUST define a TTL.
            self._redis_client.set(
                key, json.dumps(stats), ex=self.config.redis_ttl_seconds
            )
            logger.debug(f"Persisted stats to Redis: {key}")

        except Exception as e:
            logger.error(f"Failed to persist to Redis: {e}", exc_info=True)

    def _init_redis_client(self):
        """Initialize Redis client (lazy initialization)."""
        try:
            import redis

            self._redis_client = redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                db=self.config.redis_db,
                decode_responses=True,
            )
            logger.info(f"Redis client initialized (db={self.config.redis_db})")

        except ImportError:
            logger.warning("redis-py not installed. Redis persistence disabled.")
            self.config.redis_enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}", exc_info=True)
            self.config.redis_enabled = False
