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
from shared.indicators.engine.registry import IndicatorEngine, default_engine
from shared.indicators.engine.spec import (
    IndicatorSpec,
    OHLCVWindow,
    flat_key,
)
from shared.indicators.engine.talib_backend import TALibBackend

__all__ = [
    "IndicatorBackend",
    "IndicatorCacheEngine",
    "IndicatorComputationError",
    "IndicatorEngine",
    "IndicatorError",
    "IndicatorResult",
    "IndicatorSpec",
    "InMemoryPanelStore",
    "OHLCVWindow",
    "PanelStore",
    "TALibBackend",
    "UnsupportedIndicatorError",
    "default_engine",
    "flat_key",
]
