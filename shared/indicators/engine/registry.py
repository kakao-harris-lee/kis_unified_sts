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


def default_engine() -> IndicatorEngine:
    """Build the standard engine: TA-Lib backend when available.

    Kept dependency-tolerant on purpose — if the TA-Lib wheel is absent the
    engine is returned empty (every ``resolve`` raises) rather than failing at
    import, so wiring/tests degrade gracefully. Custom (NumPy/Numba) backends
    for ``vwap`` / ``rvol`` / ``ichimoku`` register here in WS-A5.
    """
    engine = IndicatorEngine()
    from shared.indicators.engine.talib_backend import TALibBackend

    if TALibBackend.available():
        engine.register(TALibBackend())
    return engine
