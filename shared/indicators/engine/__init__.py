"""Indicator calculation engine (Track A single source of truth).

Public surface for the backend-agnostic indicator engine. Consumers should
depend on :class:`IndicatorEngine` + the value objects here, never on a concrete
backend. See
``docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md``.

Example:
    >>> from shared.indicators.engine import default_engine, IndicatorSpec, OHLCVWindow
    >>> engine = default_engine()
    >>> spec = IndicatorSpec.create("rsi", {"period": 14})
    >>> # window = OHLCVWindow.from_sequences(open=..., high=..., ...)
    >>> # engine.compute(spec, window).flat_latest()  # -> {"rsi": 47.1}
"""

from __future__ import annotations

from shared.indicators.engine.adapters import (
    OHLCVBar,
    window_from_bars,
    window_from_records,
)
from shared.indicators.engine.backtest_backend import BacktestCompatBackend
from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorComputationError,
    IndicatorError,
    IndicatorResult,
    UnsupportedIndicatorError,
)
from shared.indicators.engine.cache import (
    IndicatorCacheEngine,
    InMemoryPanelStore,
    PanelStore,
)
from shared.indicators.engine.daily_backend import DailyCompatBackend
from shared.indicators.engine.momentum_backend import MomentumCompatBackend
from shared.indicators.engine.numpy_backend import NumpyBackend
from shared.indicators.engine.reference_backend import ReferenceBackend
from shared.indicators.engine.registry import (
    IndicatorEngine,
    backtest_indicator_engine,
    daily_indicator_engine,
    default_engine,
    momentum_indicator_engine,
    reference_indicator_engine,
    runtime_indicator_convention,
    runtime_indicator_engine,
    streaming_indicator_engine,
)
from shared.indicators.engine.shadow import ShadowDelta
from shared.indicators.engine.spec import (
    IndicatorSpec,
    OHLCVWindow,
    flat_key,
)
from shared.indicators.engine.stateful import (
    VolumeAcceleration,
    VolumeAccelerationCalculator,
    VolumeConfig,
    VWAPCalculator,
    VWAPConfig,
    VWAPData,
)
from shared.indicators.engine.streaming_backend import StreamingCompatBackend
from shared.indicators.engine.talib_backend import TALibBackend

__all__ = [
    "BacktestCompatBackend",
    "DailyCompatBackend",
    "IndicatorBackend",
    "IndicatorCacheEngine",
    "IndicatorComputationError",
    "IndicatorEngine",
    "IndicatorError",
    "IndicatorResult",
    "IndicatorSpec",
    "InMemoryPanelStore",
    "MomentumCompatBackend",
    "NumpyBackend",
    "OHLCVBar",
    "OHLCVWindow",
    "PanelStore",
    "ReferenceBackend",
    "ShadowDelta",
    "StreamingCompatBackend",
    "TALibBackend",
    "UnsupportedIndicatorError",
    "VWAPCalculator",
    "VWAPConfig",
    "VWAPData",
    "VolumeAcceleration",
    "VolumeAccelerationCalculator",
    "VolumeConfig",
    "backtest_indicator_engine",
    "daily_indicator_engine",
    "default_engine",
    "flat_key",
    "momentum_indicator_engine",
    "reference_indicator_engine",
    "runtime_indicator_convention",
    "runtime_indicator_engine",
    "streaming_indicator_engine",
    "window_from_bars",
    "window_from_records",
]
