"""Backend registry and the engine facade consumers call.

:class:`IndicatorEngine` composes one or more :class:`IndicatorBackend` in
priority order and is the single entry point the rest of the platform uses:
runtime cache writer, backtest feature build, and the builder evaluator all go
through it. It already implements the deduplication that the full Indicator
Cache Engine (WS-A2) builds on — :meth:`compute_many` collapses identical
:class:`IndicatorSpec` requests so a panel with ten strategies asking for
``rsi(14)`` computes it once.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorResult,
    UnsupportedIndicatorError,
)
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


class IndicatorEngine:
    """Resolve indicator specs to backends and compute them (with dedup)."""

    def __init__(self, backends: Iterable[IndicatorBackend] = ()) -> None:
        self._backends: list[IndicatorBackend] = list(backends)

    def register(self, backend: IndicatorBackend) -> IndicatorEngine:
        """Append a backend (lower priority than those already registered)."""
        self._backends.append(backend)
        return self

    @property
    def backends(self) -> tuple[IndicatorBackend, ...]:
        return tuple(self._backends)

    def resolve(self, indicator_id: str) -> IndicatorBackend:
        """Return the first registered backend that supports ``indicator_id``.

        Raises:
            UnsupportedIndicatorError: if no backend supports it.
        """
        for backend in self._backends:
            if backend.supports(indicator_id):
                return backend
        raise UnsupportedIndicatorError(
            f"no registered backend supports '{indicator_id}'"
        )

    def supported_ids(self) -> frozenset[str]:
        """Union of ids supported across all registered backends."""
        ids: set[str] = set()
        for backend in self._backends:
            ids |= backend.supported_ids()
        return frozenset(ids)

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        """Compute one spec via its resolved backend."""
        return self.resolve(spec.indicator_id).compute(spec, window)

    def compute_many(
        self, specs: Iterable[IndicatorSpec], window: OHLCVWindow
    ) -> dict[IndicatorSpec, IndicatorResult]:
        """Compute a set of specs over one window, computing each unique spec once.

        Deduplicates by spec identity (frozen/hashable). This is the core of the
        cache engine's "no duplicate calculation" guarantee.
        """
        results: dict[IndicatorSpec, IndicatorResult] = {}
        for spec in specs:
            if spec in results:
                continue
            results[spec] = self.compute(spec, window)
        return results

    def flat_panel(
        self, specs: Iterable[IndicatorSpec], window: OHLCVWindow
    ) -> dict[str, float]:
        """Compute a deduplicated panel and flatten to canonical latest keys.

        The returned mapping is exactly what the runtime cache publishes and the
        builder evaluator reads: flat ``{canonical_key: scalar}`` with warmup
        NaNs dropped. On key collisions the last spec wins (callers should not
        request the same flat key under conflicting params).
        """
        panel: dict[str, float] = {}
        for result in self.compute_many(specs, window).values():
            panel.update(result.flat_latest())
        return panel


_DAILY_ENGINE: IndicatorEngine | None = None
_MOMENTUM_ENGINE: IndicatorEngine | None = None
_STREAMING_ENGINE: IndicatorEngine | None = None
_RUNTIME_TALIB_ENGINE: IndicatorEngine | None = None


def momentum_indicator_engine() -> IndicatorEngine:
    """Momentum-convention engine hosting the exact ``shared.indicators.momentum``
    math (TRIX/CCI/MACD/slow-Stochastic/Williams %R/OBV/RSI, HTS-compatible column
    names, full-series output). Distinct from the other engines; cached singleton."""
    global _MOMENTUM_ENGINE
    if _MOMENTUM_ENGINE is None:
        from shared.indicators.engine.momentum_backend import MomentumCompatBackend

        _MOMENTUM_ENGINE = IndicatorEngine([MomentumCompatBackend()])
    return _MOMENTUM_ENGINE


def daily_indicator_engine() -> IndicatorEngine:
    """Daily-convention engine hosting the exact ``calculate_daily_indicators`` math
    (pandas ``min_periods`` SMA, ``adjust=False`` EMA, ewm-seeded RSI). Distinct
    from the intraday streaming/standard engines. Cached module singleton."""
    global _DAILY_ENGINE
    if _DAILY_ENGINE is None:
        from shared.indicators.engine.daily_backend import DailyCompatBackend

        _DAILY_ENGINE = IndicatorEngine([DailyCompatBackend()])
    return _DAILY_ENGINE


def streaming_indicator_engine() -> IndicatorEngine:
    """Runtime-convention engine hosting the exact streaming ``_calc_*`` math.

    Distinct from :func:`default_engine` (TA-Lib standard conventions, used by the
    no-code builder): the runtime must preserve its historical values (first-delta
    RSI seed, ddof=1 Bollinger, lenient ADX warmup, fast %K), which TA-Lib does not
    reproduce on the short early-session windows the runtime uses. Cached as a
    module singleton — the streaming hot path calls it per symbol per bar and the
    backend is stateless.
    """
    global _STREAMING_ENGINE
    if _STREAMING_ENGINE is None:
        from shared.indicators.engine.streaming_backend import StreamingCompatBackend

        _STREAMING_ENGINE = IndicatorEngine([StreamingCompatBackend()])
    return _STREAMING_ENGINE


def default_engine() -> IndicatorEngine:
    """Build the standard engine: TA-Lib for standard indicators, NumPy for custom.

    TA-Lib is registered first so it wins for the ids it covers; the pure-NumPy
    backend covers what TA-Lib lacks (``vwap`` / ``rvol`` / ...). Dependency
    tolerant on purpose — if the TA-Lib wheel is absent only the NumPy backend
    registers rather than failing at import, so wiring/tests degrade gracefully.
    """
    from shared.indicators.engine.numpy_backend import NumpyBackend
    from shared.indicators.engine.talib_backend import TALibBackend

    engine = IndicatorEngine()
    if TALibBackend.available():
        engine.register(TALibBackend())
    engine.register(NumpyBackend())
    return engine


# Runtime indicator convention gate (Phase C). Selects which engine the runtime
# ``_calc_*`` delegates use. Default ``streaming`` preserves the historical live
# values bit-for-bit (zero live impact); flip to ``talib`` — only after the
# data-server A/B backtest gate in
# ``docs/runbooks/streaming-talib-convergence-gate.md`` passes — to converge the
# runtime onto the same TA-Lib standard the no-code builder already uses.
# Mirrors the StochRSI default-off precedent (config-gated, additive).
_RUNTIME_CONVENTION_ENV = "STS_INDICATOR_CONVENTION"


def runtime_indicator_convention() -> str:
    """Return the active runtime indicator convention (``streaming`` | ``talib``).

    Read from the ``STS_INDICATOR_CONVENTION`` env var; defaults to ``streaming``
    (historical live behavior). Any unrecognized value falls back to ``streaming``
    so a typo can never silently change live signal values.
    """
    value = os.environ.get(_RUNTIME_CONVENTION_ENV, "streaming").strip().lower()
    return "talib" if value == "talib" else "streaming"


def runtime_indicator_engine() -> IndicatorEngine:
    """Return the engine the runtime ``_calc_*`` delegates should use.

    ``streaming`` (default) → :func:`streaming_indicator_engine` (historical
    values). ``talib`` → a cached TA-Lib standard engine (converged with the
    builder). The convention is process-wide and read per call so a restart with
    the env flag set is all that is needed to switch; both branches return a
    cached module singleton, so this is cheap on the per-symbol-per-bar hot path.
    """
    if runtime_indicator_convention() == "talib":
        global _RUNTIME_TALIB_ENGINE
        if _RUNTIME_TALIB_ENGINE is None:
            _RUNTIME_TALIB_ENGINE = default_engine()
        return _RUNTIME_TALIB_ENGINE
    return streaming_indicator_engine()
