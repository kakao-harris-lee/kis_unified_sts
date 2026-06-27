"""Probability calibrator for z-score normalization."""
import logging
from collections import deque

import numpy as np
from scipy import stats

from .config import EnsembleConfig

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """Calibrate DL model probabilities using z-score normalization.

    The calibrator maintains a rolling window of historical probabilities
    and uses z-score to normalize new predictions, converting them to
    calibrated confidence scores.
    """

    def __init__(self, config: EnsembleConfig):
        self.config = config
        self._history: deque[float] = deque(maxlen=config.calibration_lookback)
        self._mean: float | None = None
        self._std: float | None = None

    def update(self, probability: float) -> None:
        """Update calibrator with new probability observation.

        Args:
            probability: Raw probability from DL model (0.0 to 1.0)
        """
        self._history.append(probability)

        # Update rolling statistics
        if len(self._history) >= 2:
            arr = np.array(self._history)
            self._mean = float(np.mean(arr))
            self._std = float(np.std(arr, ddof=1))

    def get_zscore(self, probability: float) -> float:
        """Calculate z-score of a probability.

        Args:
            probability: Raw probability to score

        Returns:
            Z-score (number of standard deviations from mean)
        """
        if self._mean is None or self._std is None or self._std == 0:
            return 0.0

        return (probability - self._mean) / self._std

    def calibrate(self, probability: float) -> float:
        """Convert raw probability to calibrated confidence.

        Uses the CDF of the standard normal distribution to convert
        z-scores to calibrated probabilities.

        Args:
            probability: Raw probability from DL model

        Returns:
            Calibrated probability (0.0 to 1.0)
        """
        if not self.is_ready():
            return probability  # Return raw if not ready

        z_score = self.get_zscore(probability)

        # Use normal CDF to convert z-score to probability
        calibrated = stats.norm.cdf(z_score)

        return float(calibrated)

    def is_ready(self) -> bool:
        """Check if calibrator has enough data."""
        return len(self._history) >= self.config.calibration_lookback

    def get_stats(self) -> dict:
        """Get current calibration statistics."""
        return {
            "samples": len(self._history),
            "mean": self._mean,
            "std": self._std,
            "ready": self.is_ready(),
        }

    def reset(self) -> None:
        """Reset calibrator state."""
        self._history.clear()
        self._mean = None
        self._std = None
