"""Anomaly detection for data quality."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np

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
        """Detect outliers using rolling z-score.

        Args:
            values: List of values to check
            window: Rolling window size

        Returns:
            List of detected anomalies with index and value
        """
        if len(values) < self.config.min_samples:
            return []

        arr = np.array(values)
        anomalies = []

        # Calculate rolling mean and std
        for i in range(window, len(arr)):
            window_data = arr[i - window:i]
            mean = np.mean(window_data)
            std = np.std(window_data)

            if std == 0:
                continue

            z_score = abs(arr[i] - mean) / std

            if z_score > self.config.outlier_std_threshold:
                anomalies.append({
                    "index": i,
                    "value": arr[i],
                    "z_score": z_score,
                    "expected_range": (
                        mean - self.config.outlier_std_threshold * std,
                        mean + self.config.outlier_std_threshold * std,
                    ),
                })
                logger.warning(f"Outlier detected at index {i}: {arr[i]} (z={z_score:.2f})")

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
