"""Shared observability utilities.

Exposes the rolling-rate-tracker base class used by KIS API error-rate
tracking and related operational monitors.
"""

from shared.observability.rate_tracker import RollingRateTracker

__all__ = ["RollingRateTracker"]
