"""Basis calculator for statistical arbitrage."""
import logging
import time
from collections import deque
from typing import Deque, Optional, Tuple

import numpy as np

from .config import ArbitrageConfig
from .models import BasisData

logger = logging.getLogger(__name__)


class BasisCalculator:
    """Calculate basis and z-score for statistical arbitrage.

    Fair Value Formula:
        fair_value = spot * (1 + r * T/365)

    Where:
        spot = KOSPI200 index value
        r = risk-free rate (annual)
        T = days to expiry
    """

    def __init__(self, config: ArbitrageConfig):
        self.config = config
        self.basis_history: Deque[float] = deque(maxlen=config.rolling_window)
        self._last_data: Optional[BasisData] = None

    def calculate_fair_value(self, spot_index: float, days_to_expiry: int) -> float:
        """Calculate theoretical fair value of futures."""
        time_factor = days_to_expiry / 365.0
        return spot_index * (1 + self.config.risk_free_rate * time_factor)

    def update(
        self,
        spot_index: float,
        futures_price: float,
        days_to_expiry: int,
        timestamp: Optional[float] = None
    ) -> BasisData:
        """Update basis calculation with new prices."""
        timestamp = timestamp or time.time()

        # Calculate fair value and basis
        fair_value = self.calculate_fair_value(spot_index, days_to_expiry)
        basis = futures_price - fair_value

        # Update rolling history
        self.basis_history.append(basis)

        # Calculate rolling statistics
        rolling_mean, rolling_std = self._get_rolling_stats()

        # Calculate z-score
        if rolling_std > 0 and len(self.basis_history) >= self.config.min_samples:
            basis_zscore = (basis - rolling_mean) / rolling_std
        else:
            basis_zscore = 0.0

        self._last_data = BasisData(
            timestamp=timestamp,
            spot_index=spot_index,
            futures_price=futures_price,
            fair_value=fair_value,
            basis=basis,
            basis_zscore=basis_zscore,
            days_to_expiry=days_to_expiry,
            rolling_mean=rolling_mean,
            rolling_std=rolling_std
        )

        return self._last_data

    def _get_rolling_stats(self) -> Tuple[float, float]:
        """Calculate rolling mean and std of basis."""
        if len(self.basis_history) < 2:
            return 0.0, 0.0

        arr = np.array(self.basis_history)
        return float(np.mean(arr)), float(np.std(arr, ddof=1))

    def is_ready(self) -> bool:
        """Check if calculator has enough samples."""
        return len(self.basis_history) >= self.config.min_samples

    def is_signal(self, threshold: float = None) -> Tuple[bool, Optional[str]]:
        """Check if current basis is a trading signal.

        Returns:
            (has_signal, direction): direction is "BUY" or "SELL" or None
        """
        if not self._last_data or not self.is_ready():
            return False, None

        threshold = threshold or self.config.basis_threshold
        z = self._last_data.basis_zscore

        if z > threshold:
            return True, "SELL"  # Basis too high, sell futures
        elif z < -threshold:
            return True, "BUY"   # Basis too low, buy futures

        return False, None

    def reset(self) -> None:
        """Reset calculator state."""
        self.basis_history.clear()
        self._last_data = None
