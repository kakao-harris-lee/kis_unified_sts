"""Indicator Cache Engine (WS-A2) — dedup for both cache shapes.

Two complementary cache classes live here; know which one is actually wired:

* :class:`CachingIndicatorEngine` — **production-wired** (P2-b). Memoizes full
  ``compute(spec, window)`` results (whole series) by (spec identity, window
  content token). The builder_v1 entry/exit bridges share the
  :func:`cached_default_engine` process singleton, so N builder strategies
  requesting the same spec on the same symbol/bar compute it once.
* :class:`IndicatorCacheEngine` + :class:`PanelStore` — the flat *scalar*
  panel half ("latest values per symbol"). Structurally complete but **not
  yet wired into any runtime**; it is the drop-in for scalar consumers
  (runtime cache writer, dashboards) and for a Redis-backed cross-process
  store (TTL-managed, DB 1) as a P3+ follow-up.

Shared idea: the requested spec set is deduplicated by ``IndicatorSpec``
identity, so ten strategies asking for ``rsi(14)`` cost one computation per
symbol. Incremental (``talib.stream``) and parallel (Polars / process pool)
execution are refinements of :meth:`IndicatorCacheEngine.refresh_many` tracked
as follow-ups; the interfaces here do not change when they land.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable, Mapping

from shared.indicators.engine.base import IndicatorBackend, IndicatorResult
from shared.indicators.engine.registry import IndicatorEngine, default_engine
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow

# Default LRU bound for the series-panel memo (CachingIndicatorEngine).
# Sized so one full evaluation cycle (symbols x unique specs) fits: entries
# from past bars never recur (the key is the window content), so LRU evicts
# them naturally. Memory bound: 2048 entries x a few float64 series of a few
# hundred bars each is on the order of tens of MB worst case, and only while
# fresher entries have not yet displaced them. Tunable per instance.
DEFAULT_SERIES_CACHE_MAXSIZE = 2048


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


class CachingIndicatorEngine(IndicatorEngine):
    """An :class:`IndicatorEngine` that memoizes ``compute`` per (spec, window).

    This is the builder-path half of the cache engine (WS-A2): the flat
    :class:`IndicatorCacheEngine`/:class:`PanelStore` pair above serves scalar
    consumers, while the no-code builder evaluator needs the FULL series (its
    cross/percentile operators require prior values). Memoizing
    ``compute(spec, window)`` by (spec identity,
    :meth:`OHLCVWindow.content_token`) means N builder strategies sharing
    ``rsi(14)`` on the same symbol/bar compute it once — and entry + exit
    evaluations of the same bar share results too. The token is cached on the
    window object, so one evaluation cycle hashes each window once, not once
    per indicator.

    Purity contract: backends are pure functions of (spec, window), pinned by
    the golden backend tests, so a cache hit is value-identical by
    construction. Cached :class:`IndicatorResult` objects are shared with
    callers and must be treated as immutable — the same aliasing rule
    ``compute_many`` already establishes for duplicate specs.

    Process-local and single-threaded by design (builder daemons evaluate on
    one asyncio loop). A Redis-backed cross-process variant is a P3+ follow-up
    and would slot in behind the same interface.
    """

    def __init__(
        self,
        backends: Iterable[IndicatorBackend] = (),
        *,
        maxsize: int = DEFAULT_SERIES_CACHE_MAXSIZE,
    ) -> None:
        super().__init__(backends)
        if maxsize <= 0:
            raise ValueError(f"maxsize must be positive, got {maxsize}")
        self._maxsize = maxsize
        self._memo: OrderedDict[tuple[IndicatorSpec, bytes], IndicatorResult] = (
            OrderedDict()
        )
        self.hits = 0
        self.misses = 0

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        """Compute one spec, returning the memoized result on a content hit."""
        key = (spec, window.content_token())
        cached = self._memo.get(key)
        if cached is not None:
            self._memo.move_to_end(key)
            self.hits += 1
            return cached
        result = super().compute(spec, window)
        self.misses += 1
        self._memo[key] = result
        while len(self._memo) > self._maxsize:
            self._memo.popitem(last=False)
        return result


_SHARED_CACHED_ENGINE: CachingIndicatorEngine | None = None


def cached_default_engine() -> CachingIndicatorEngine:
    """The process-wide caching wrapper around :func:`default_engine`.

    A module singleton so every builder strategy instance (entry AND exit)
    shares one memo — that sharing is what deduplicates identical specs across
    strategies within a bar. Values are identical to :func:`default_engine`
    by the purity contract above.
    """
    global _SHARED_CACHED_ENGINE
    if _SHARED_CACHED_ENGINE is None:
        _SHARED_CACHED_ENGINE = CachingIndicatorEngine(default_engine().backends)
    return _SHARED_CACHED_ENGINE
