"""Anomaly detection for data quality."""
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnomalyConfig:
    """Anomaly detection configuration."""
    outlier_std_threshold: float = 3.0
    gap_tolerance_factor: float = 2.0
    min_samples: int = 10


class AnomalyDetector:
    """Detect data quality anomalies.

    Features:
    - Price outlier detection (z-score)
    - Data gap detection
    - Volume anomaly detection
    """

    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or AnomalyConfig()

    def detect_outliers(
        self,
        values: List[float],
        window: int = 20,
    ) -> List[Dict]:
        """Detect outliers using vectorized rolling z-score.

        Uses pandas rolling operations for O(n) complexity instead of
        O(n×window) with manual loops.

        Args:
            values: List of values to check
            window: Rolling window size

        Returns:
            List of detected anomalies with index and value
        """
        if len(values) < self.config.min_samples:
            return []

        # Convert to pandas Series for vectorized operations
        series = pd.Series(values)

        # Vectorized rolling calculations - O(n) complexity
        rolling_mean = series.rolling(window).mean()
        rolling_std = series.rolling(window).std()

        # Vectorized z-score calculation (avoid division by zero)
        # Use shift to compare current value against previous window's stats
        z_scores = np.abs(series - rolling_mean.shift(1)) / rolling_std.shift(1)

        # Find outliers where z-score exceeds threshold
        outlier_mask = z_scores > self.config.outlier_std_threshold

        # Build results only for outliers (avoid iterating all values)
        anomalies = []
        outlier_indices = np.where(outlier_mask)[0]

        for i in outlier_indices:
            if i >= window and pd.notna(z_scores.iloc[i]):
                mean = rolling_mean.iloc[i - 1] if i > 0 else rolling_mean.iloc[i]
                std = rolling_std.iloc[i - 1] if i > 0 else rolling_std.iloc[i]

                if pd.notna(mean) and pd.notna(std) and std > 0:
                    anomalies.append({
                        "index": int(i),
                        "value": float(values[i]),
                        "z_score": float(z_scores.iloc[i]),
                        "expected_range": (
                            float(mean - self.config.outlier_std_threshold * std),
                            float(mean + self.config.outlier_std_threshold * std),
                        ),
                    })
                    logger.warning(
                        f"Outlier detected at index {i}: {values[i]} "
                        f"(z={z_scores.iloc[i]:.2f})"
                    )

        return anomalies

    def detect_gaps(
        self,
        timestamps: List[datetime],
        expected_interval_seconds: int = 60,
    ) -> List[Dict]:
        """Detect gaps in time series data.

        Args:
            timestamps: List of timestamps
            expected_interval_seconds: Expected interval between data points

        Returns:
            List of detected gaps
        """
        if len(timestamps) < 2:
            return []

        gaps = []
        tolerance = expected_interval_seconds * self.config.gap_tolerance_factor

        sorted_ts = sorted(timestamps)

        for i in range(1, len(sorted_ts)):
            delta = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()

            if delta > tolerance:
                gaps.append({
                    "start": sorted_ts[i - 1],
                    "end": sorted_ts[i],
                    "gap_seconds": delta,
                    "expected_seconds": expected_interval_seconds,
                })
                logger.warning(
                    f"Data gap detected: {sorted_ts[i-1]} to {sorted_ts[i]} "
                    f"({delta:.0f}s, expected {expected_interval_seconds}s)"
                )

        return gaps

    def detect_volume_anomaly(
        self,
        volumes: List[float],
        threshold_factor: float = 5.0,
    ) -> List[Dict]:
        """Detect abnormal trading volumes.

        Args:
            volumes: List of volume values
            threshold_factor: Multiple of average to flag as anomaly

        Returns:
            List of volume anomalies
        """
        if len(volumes) < self.config.min_samples:
            return []

        arr = np.array(volumes)
        avg_volume = np.mean(arr)
        threshold = avg_volume * threshold_factor

        anomalies = []
        for i, vol in enumerate(arr):
            if vol > threshold:
                anomalies.append({
                    "index": i,
                    "volume": vol,
                    "average": avg_volume,
                    "ratio": vol / avg_volume,
                })

        return anomalies
