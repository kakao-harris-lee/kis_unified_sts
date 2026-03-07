"""Data drift detection for ML models.

Implements KL divergence and PSI (Population Stability Index) metrics to detect
distribution shifts between reference and current data distributions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class DriftConfig:
    """Drift detection configuration."""

    num_bins: int = 10
    min_samples: int = 30
    epsilon: float = 1e-10  # Small constant to avoid log(0) and division by zero


class DriftDetector:
    """Detect data drift using KL divergence and PSI metrics.

    Tracks reference distributions and computes drift scores by comparing
    current distributions against the reference baseline.

    Metrics:
        - KL Divergence: Measures the difference between two probability distributions
        - PSI (Population Stability Index): Industry-standard metric for distribution shift

    Example:
        >>> detector = DriftDetector()
        >>> detector.set_reference(reference_data)
        >>> kl_div = detector.compute_kl_divergence(current_data)
        >>> psi = detector.compute_psi(current_data)
    """

    def __init__(self, config: DriftConfig | None = None):
        """Initialize drift detector.

        Args:
            config: Drift detection configuration. Uses defaults if None.
        """
        self.config = config or DriftConfig()
        self._reference_dist: NDArray[np.float64] | None = None
        self._reference_bins: NDArray[np.float64] | None = None

    def set_reference(self, data: NDArray[np.float64] | list[float]) -> None:
        """Set reference distribution from data.

        Computes histogram bins and probabilities that will be used as the
        baseline for drift detection.

        Args:
            data: Reference data array

        Raises:
            ValueError: If data has insufficient samples
        """
        arr = np.asarray(data, dtype=np.float64)

        if len(arr) < self.config.min_samples:
            raise ValueError(
                f"Insufficient samples for reference distribution: "
                f"{len(arr)} < {self.config.min_samples}"
            )

        # Create histogram bins from reference data
        counts, bin_edges = np.histogram(arr, bins=self.config.num_bins)

        # Convert counts to probabilities, add epsilon to avoid zero probabilities
        self._reference_dist = (counts + self.config.epsilon) / (
            counts.sum() + self.config.epsilon * self.config.num_bins
        )
        self._reference_bins = bin_edges

        logger.info(
            f"Reference distribution set: {len(arr)} samples, "
            f"{self.config.num_bins} bins"
        )

    def compute_kl_divergence(
        self, data: NDArray[np.float64] | list[float]
    ) -> float:
        """Compute KL divergence between current data and reference distribution.

        KL(P||Q) = Σ P(i) * log(P(i) / Q(i))
        where P is the current distribution and Q is the reference.

        Args:
            data: Current data array

        Returns:
            KL divergence score (non-negative, 0 = identical distributions)

        Raises:
            RuntimeError: If reference distribution not set
            ValueError: If data has insufficient samples
        """
        if self._reference_dist is None or self._reference_bins is None:
            raise RuntimeError(
                "Reference distribution not set. Call set_reference() first."
            )

        arr = np.asarray(data, dtype=np.float64)

        if len(arr) < self.config.min_samples:
            raise ValueError(
                f"Insufficient samples: {len(arr)} < {self.config.min_samples}"
            )

        # Compute current distribution using same bins as reference
        counts, _ = np.histogram(arr, bins=self._reference_bins)

        # Convert to probabilities with epsilon smoothing
        current_dist = (counts + self.config.epsilon) / (
            counts.sum() + self.config.epsilon * self.config.num_bins
        )

        # Compute KL divergence: KL(current || reference)
        kl_div = np.sum(current_dist * np.log(current_dist / self._reference_dist))

        return float(kl_div)

    def compute_psi(self, data: NDArray[np.float64] | list[float]) -> float:
        """Compute Population Stability Index (PSI).

        PSI = Σ (current% - reference%) * ln(current% / reference%)

        PSI Interpretation:
            < 0.1: No significant change
            0.1 - 0.25: Moderate change, investigate
            > 0.25: Significant change, model likely needs retraining

        Args:
            data: Current data array

        Returns:
            PSI score (non-negative)

        Raises:
            RuntimeError: If reference distribution not set
            ValueError: If data has insufficient samples
        """
        if self._reference_dist is None or self._reference_bins is None:
            raise RuntimeError(
                "Reference distribution not set. Call set_reference() first."
            )

        arr = np.asarray(data, dtype=np.float64)

        if len(arr) < self.config.min_samples:
            raise ValueError(
                f"Insufficient samples: {len(arr)} < {self.config.min_samples}"
            )

        # Compute current distribution using same bins as reference
        counts, _ = np.histogram(arr, bins=self._reference_bins)

        # Convert to probabilities with epsilon smoothing
        current_dist = (counts + self.config.epsilon) / (
            counts.sum() + self.config.epsilon * self.config.num_bins
        )

        # PSI formula: sum of (current% - reference%) * ln(current% / reference%)
        psi = np.sum(
            (current_dist - self._reference_dist)
            * np.log(current_dist / self._reference_dist)
        )

        return float(psi)

    def compute_drift_scores(
        self, data: NDArray[np.float64] | list[float]
    ) -> dict[str, float]:
        """Compute both KL divergence and PSI in a single call.

        Args:
            data: Current data array

        Returns:
            Dictionary with 'kl_divergence' and 'psi' keys

        Raises:
            RuntimeError: If reference distribution not set
            ValueError: If data has insufficient samples
        """
        return {
            "kl_divergence": self.compute_kl_divergence(data),
            "psi": self.compute_psi(data),
        }

    def reset_reference(self) -> None:
        """Clear the reference distribution.

        Useful when you need to set a new baseline for drift detection.
        """
        self._reference_dist = None
        self._reference_bins = None
        logger.info("Reference distribution reset")

    @property
    def has_reference(self) -> bool:
        """Check if reference distribution is set.

        Returns:
            True if reference distribution is available
        """
        return self._reference_dist is not None and self._reference_bins is not None
