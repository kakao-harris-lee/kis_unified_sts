"""Regime detection module.

This module provides adaptive regime detection, performance tracking, and
regime-aware strategy routing for trading strategies.

Key Components:
    - Adaptive Regime Detection: Multi-metric regime classification with dynamic switching
    - Performance Tracking: Regime-specific performance monitoring and model evaluation
    - Basic Detectors: Traditional regime detection methods
    - Strategy Routing: Regime-aware strategy selection

Example:
    >>> from shared.regime import (
    ...     AdaptiveRegimeDetector,
    ...     RegimePerformanceTracker
    ... )
    >>> detector = AdaptiveRegimeDetector()
    >>> tracker = RegimePerformanceTracker()
"""

# Core adaptive components (main exports)
from .adaptive_detector import (
    AdaptiveRegimeConfig,
    AdaptiveRegimeDetector,
    AdaptiveRegimeState,
)

# Traditional detectors
from .detector import StockRegimeDetector

# Base models and types
from .models import (
    RegimeConfig,
    RegimeSignal,
    RegimeState,
)
from .performance_tracker import (
    RegimePerformanceConfig,
    RegimePerformanceTracker,
    RegimeStats,
    TradeRecord,
)

# Strategy routing
from .router import StrategyRouter

__all__ = [
    # Main adaptive components
    "AdaptiveRegimeDetector",
    "RegimePerformanceTracker",
    # Adaptive configuration
    "AdaptiveRegimeState",
    "AdaptiveRegimeConfig",
    "RegimePerformanceConfig",
    "TradeRecord",
    "RegimeStats",
    # Base models
    "RegimeState",
    "RegimeSignal",
    "RegimeConfig",
    # Traditional detectors
    "StockRegimeDetector",
    # Routing
    "StrategyRouter",
]
