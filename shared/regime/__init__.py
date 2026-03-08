"""Regime detection module.

This module provides adaptive regime detection, model selection, and performance tracking
for trading strategies. It supports multiple detection methods (basic, HMM, adaptive) and
enables regime-aware strategy routing.

Key Components:
    - Adaptive Regime Detection: Multi-metric regime classification with dynamic switching
    - Model Selection: Automatic model switching based on regime performance
    - Performance Tracking: Regime-specific performance monitoring and model evaluation
    - Basic Detectors: Traditional regime detection methods
    - Strategy Routing: Regime-aware strategy selection

Example:
    >>> from shared.regime import (
    ...     AdaptiveRegimeDetector,
    ...     AdaptiveModelSelector,
    ...     RegimePerformanceTracker
    ... )
    >>> detector = AdaptiveRegimeDetector()
    >>> selector = AdaptiveModelSelector()
    >>> tracker = RegimePerformanceTracker()
"""

# Core adaptive components (main exports)
from .adaptive_detector import (
    AdaptiveRegimeDetector,
    AdaptiveRegimeState,
    AdaptiveRegimeConfig,
)
from .model_selector import (
    AdaptiveModelSelector,
    ModelSwitchingConfig,
    ModelMapping,
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
from .hmm_detector import (
    HMMRegimeDetector,
    HMMConfig,
    HMMRegimeState,
)

# Strategy routing
from .router import StrategyRouter

__all__ = [
    # Main adaptive components
    "AdaptiveRegimeDetector",
    "AdaptiveModelSelector",
    "RegimePerformanceTracker",
    # Adaptive configuration
    "AdaptiveRegimeState",
    "AdaptiveRegimeConfig",
    "ModelSwitchingConfig",
    "ModelMapping",
    "RegimePerformanceConfig",
    "TradeRecord",
    "RegimeStats",
    # Base models
    "RegimeState",
    "RegimeSignal",
    "RegimeConfig",
    # Traditional detectors
    "StockRegimeDetector",
    "HMMRegimeDetector",
    "HMMConfig",
    "HMMRegimeState",
    # Routing
    "StrategyRouter",
]
