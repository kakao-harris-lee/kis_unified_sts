"""Indicator Cache Engine (WS-A2) — dedup + pluggable panel store.

Computes a deduplicated flat indicator panel per symbol through an
:class:`IndicatorEngine` and publishes it to a :class:`PanelStore`. This is the
structural core of the roadmap's cache engine: the requested spec set is unified
once, so ten strategies asking for ``rsi(14)`` cost one computation per symbol,
and every consumer (builder evaluator, strategies, backtest) reads the same flat
panel — collapsing the historic runtime/backtest dual path.

Incremental (``talib.stream``) and parallel (Polars / process pool) execution
are refinements of :meth:`IndicatorCacheEngine.refresh_many` tracked as
follow-ups; the interfaces here do not change when they land. The Redis-backed
:class:`PanelStore` (TTL-managed, DB 1) likewise drops in without touching the
engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping

from shared.indicators.engine.registry import IndicatorEngine
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


class PanelStore(ABC):
    """Sink/source for per-symbol flat indicator panels.

    Deliberately minimal (write/read of a flat ``{key: scalar}`` map) so a
    Redis-backed implementation can manage TTLs and key namespacing on its own
    without leaking that concern into the engine.
    """

    @abstractmethod
    def write(self, symbol: str, panel: Mapping[str, float]) -> None:
        """Persist ``panel`` as the latest indicators for ``symbol``."""

    @abstractmethod
    def read(self, symbol: str) -> dict[str, float]:
        """Return the latest panel for ``symbol`` (empty if none cached)."""


class InMemoryPanelStore(PanelStore):
    """Process-local :class:`PanelStore` for tests and single-process use.

    Returns copies so callers can't mutate cached state through the reference.
    """

    def __init__(self) -> None:
        self._panels: dict[str, dict[str, float]] = {}

    def write(self, symbol: str, panel: Mapping[str, float]) -> None:
        self._panels[symbol] = dict(panel)

    def read(self, symbol: str) -> dict[str, float]:
        return dict(self._panels.get(symbol, {}))


class IndicatorCacheEngine:
    """Compute a deduplicated flat panel per symbol and cache it.

    The spec set is deduplicated once at construction, so the same indicator
    requested by many strategies is computed at most once per symbol.
    """

    def __init__(
        self,
        engine: IndicatorEngine,
        store: PanelStore,
        specs: Iterable[IndicatorSpec],
    ) -> None:
        self._engine = engine
        self._store = store
        # dict.fromkeys keeps insertion order while dropping duplicate specs
        # (IndicatorSpec is frozen/hashable).
        self._specs: tuple[IndicatorSpec, ...] = tuple(dict.fromkeys(specs))

    @property
    def specs(self) -> tuple[IndicatorSpec, ...]:
        """The unique specs this engine computes."""
        return self._specs

    def refresh(self, symbol: str, window: OHLCVWindow) -> dict[str, float]:
        """Compute the flat panel for ``symbol`` over ``window`` and cache it."""
        panel = self._engine.flat_panel(self._specs, window)
        self._store.write(symbol, panel)
        return panel

    def refresh_many(
        self, sources: Mapping[str, OHLCVWindow]
    ) -> dict[str, dict[str, float]]:
        """Refresh several symbols at once.

        Serial today; this is the single method that becomes Polars/pool-parallel
        (WS-A2) without changing its signature or any caller.
        """
        return {
            symbol: self.refresh(symbol, window) for symbol, window in sources.items()
        }

    def get(self, symbol: str) -> dict[str, float]:
        """Read the cached panel for ``symbol`` (empty if not yet refreshed)."""
        return self._store.read(symbol)
