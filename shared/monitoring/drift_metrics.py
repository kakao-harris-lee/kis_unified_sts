"""Data drift metrics for RL model monitoring.

Unified dataclass for representing all drift-related metrics including
KL divergence, PSI, confidence distribution shifts, and rolling performance metrics.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DriftMetrics:
    """Unified drift metrics for RL model monitoring.

    Combines feature drift (KL divergence, PSI), confidence distribution tracking,
    and rolling performance metrics (Sharpe ratio, win rate) into a single
    representation for storage and alerting.

    Attributes:
        timestamp: When the metrics were computed
        code: Trading symbol/code (e.g., 'A05xxx' for KOSPI200 mini)
        strategy: Strategy name (e.g., 'rl_mppo')
        kl_divergence: KL divergence between current and reference feature distribution
        psi_score: Population Stability Index (PSI) score
        confidence_mean: Mean of model prediction confidence distribution
        confidence_std: Standard deviation of confidence distribution
        sharpe_5d: 5-day rolling Sharpe ratio (nullable until enough data)
        sharpe_20d: 20-day rolling Sharpe ratio (nullable until enough data)
        win_rate_5d: 5-day rolling win rate percentage (nullable until enough data)
        win_rate_20d: 20-day rolling win rate percentage (nullable until enough data)
    """

    timestamp: datetime
    code: str
    strategy: str
    kl_divergence: float
    psi_score: float
    confidence_mean: float
    confidence_std: float
    sharpe_5d: float | None = None
    sharpe_20d: float | None = None
    win_rate_5d: float | None = None
    win_rate_20d: float | None = None

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for serialization.

        Returns:
            Dictionary representation of all metrics
        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "code": self.code,
            "strategy": self.strategy,
            "kl_divergence": self.kl_divergence,
            "psi_score": self.psi_score,
            "confidence_mean": self.confidence_mean,
            "confidence_std": self.confidence_std,
            "sharpe_5d": self.sharpe_5d,
            "sharpe_20d": self.sharpe_20d,
            "win_rate_5d": self.win_rate_5d,
            "win_rate_20d": self.win_rate_20d,
        }
