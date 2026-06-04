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
    AdaptiveRegimeDetector,
    AdaptiveRegimeState,
    AdaptiveRegimeConfig,
)
from .performance_tracker import (
    RegimePerformanceTracker,
    RegimePerformanceConfig,
    TradeRecord,
    RegimeStats,
)

# Base models and types
from .models import (
    RegimeState,
    RegimeSignal,
    RegimeConfig,
)

# Traditional detectors
from .detector import StockRegimeDetector

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
