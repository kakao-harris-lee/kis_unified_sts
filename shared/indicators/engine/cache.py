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

import hashlib
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable, Mapping

from shared.indicators.engine.base import IndicatorBackend, IndicatorResult
from shared.indicators.engine.registry import IndicatorEngine, default_engine
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow

# Default LRU bound for the series-panel memo (CachingIndicatorEngine).
# Sized so one full evaluation cycle (symbols x unique specs) fits: entries
# from past bars never recur (the key is the window content), so LRU evicts
# them naturally. Tunable per instance via the constructor.
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


def _window_token(window: OHLCVWindow) -> bytes:
    """Content digest of an OHLCV window (the memo key's window half).

    Content-addressed on purpose: two windows with identical bytes yield
    identical indicator series (backends are pure), so sharing a cached result
    across callers — even across symbols — can never change a value. Hashing
    ~5 x N float64 arrays is microseconds versus a TA-Lib/pandas compute.
    """
    digest = hashlib.blake2b(digest_size=16)
    for arr in (window.open, window.high, window.low, window.close, window.volume):
        digest.update(arr.tobytes())
        digest.update(str(arr.shape[0]).encode())
    return digest.digest()


class CachingIndicatorEngine(IndicatorEngine):
    """An :class:`IndicatorEngine` that memoizes ``compute`` per (spec, window).

    This is the builder-path half of the cache engine (WS-A2): the flat
    :class:`IndicatorCacheEngine`/:class:`PanelStore` pair above serves scalar
    consumers, while the no-code builder evaluator needs the FULL series (its
    cross/percentile operators require prior values). Memoizing
    ``compute(spec, window)`` by (spec identity, window content) means N
    builder strategies sharing ``rsi(14)`` on the same symbol/bar compute it
    once — and entry + exit evaluations of the same bar share results too.

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
        key = (spec, _window_token(window))
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

    def cache_clear(self) -> None:
        """Drop all memoized results (test/diagnostic hook)."""
        self._memo.clear()
        self.hits = 0
        self.misses = 0


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
