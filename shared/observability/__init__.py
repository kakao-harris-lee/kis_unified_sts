"""Shared observability utilities.

Exposes the rolling-rate-tracker base class used by KIS API error-rate
tracking and ClickHouse insert failure tracking.
"""

from shared.observability.rate_tracker import RollingRateTracker

__all__ = ["RollingRateTracker"]
