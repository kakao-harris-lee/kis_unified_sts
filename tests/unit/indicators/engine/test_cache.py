"""Unit tests for the Indicator Cache Engine (dedup + panel store).

Backend-agnostic: a counting fake backend proves the "compute each unique spec
once per symbol" guarantee without TA-Lib.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.indicators.engine.base import IndicatorBackend, IndicatorResult
from shared.indicators.engine.cache import (
    CachingIndicatorEngine,
    IndicatorCacheEngine,
    InMemoryPanelStore,
    cached_default_engine,
)
from shared.indicators.engine.registry import IndicatorEngine
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


class CountingBackend(IndicatorBackend):
    """Fake backend recording every compute call as (indicator_id, key)."""

    def __init__(self, ids: set[str]) -> None:
        self._ids = frozenset(ids)
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "counting"

    def supported_ids(self) -> frozenset[str]:
        return self._ids

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        self.calls.append(spec.key)
        return IndicatorResult(
            spec=spec,
            series={"value": np.array([1.0], dtype=np.float64)},
            latest={"value": 1.0},
        )


def _window(value: float = 1.0) -> OHLCVWindow:
    return OHLCVWindow.from_sequences(
        open=[value], high=[value], low=[value], close=[value], volume=[value]
    )


def _cache(ids: set[str], specs) -> tuple[IndicatorCacheEngine, CountingBackend]:
    backend = CountingBackend(ids)
    engine = IndicatorEngine([backend])
    return (
        IndicatorCacheEngine(engine, InMemoryPanelStore(), specs),
        backend,
    )


class TestInMemoryPanelStore:
    def test_write_read_roundtrip(self) -> None:
        store = InMemoryPanelStore()
        store.write("005930", {"rsi": 47.1})
        assert store.read("005930") == {"rsi": 47.1}

    def test_read_missing_returns_empty(self) -> None:
        assert InMemoryPanelStore().read("nope") == {}

    def test_read_returns_a_copy(self) -> None:
        store = InMemoryPanelStore()
        store.write("005930", {"rsi": 47.1})
        got = store.read("005930")
        got["rsi"] = 0.0
        assert store.read("005930") == {"rsi": 47.1}  # not mutated


class TestIndicatorCacheEngine:
    def test_specs_are_deduplicated_at_construction(self) -> None:
        cache, _ = _cache(
            {"rsi"},
            [
                IndicatorSpec.create("rsi", {"period": 14}),
                IndicatorSpec.create("rsi", {"period": 14}),  # dup
            ],
        )
        assert len(cache.specs) == 1

    def test_refresh_computes_and_caches(self) -> None:
        cache, _ = _cache({"rsi"}, [IndicatorSpec.create("rsi", {"period": 14})])
        panel = cache.refresh("005930", _window())
        assert panel == {"rsi": 1.0}
        assert cache.get("005930") == {"rsi": 1.0}

    def test_get_before_refresh_is_empty(self) -> None:
        cache, _ = _cache({"rsi"}, [IndicatorSpec.create("rsi", {"period": 14})])
        assert cache.get("005930") == {}

    def test_duplicate_specs_compute_once_per_symbol(self) -> None:
        cache, backend = _cache(
            {"rsi"},
            [
                IndicatorSpec.create("rsi", {"period": 14}),
                IndicatorSpec.create("rsi", {"period": 14}),
                IndicatorSpec.create("rsi", {"period": 14}),
            ],
        )
        cache.refresh("005930", _window())
        assert len(backend.calls) == 1

    def test_refresh_many_covers_all_symbols(self) -> None:
        cache, backend = _cache(
            {"rsi", "atr"},
            [
                IndicatorSpec.create("rsi", {"period": 14}),
                IndicatorSpec.create("atr", {"period": 14}),
            ],
        )
        panels = cache.refresh_many({"005930": _window(), "000660": _window()})
        assert set(panels) == {"005930", "000660"}
        assert panels["005930"] == {"rsi": 1.0, "atr": 1.0}
        # 2 unique specs x 2 symbols = 4 computations.
        assert len(backend.calls) == 4


def _multi_window(*closes: float) -> OHLCVWindow:
    values = list(closes)
    return OHLCVWindow.from_sequences(
        open=values, high=values, low=values, close=values, volume=values
    )


class TestCachingIndicatorEngine:
    """Series-level memoization for the builder evaluation path (P2-b)."""

    def _engine(self, ids: set[str]) -> tuple[CachingIndicatorEngine, CountingBackend]:
        backend = CountingBackend(ids)
        return CachingIndicatorEngine([backend]), backend

    def test_same_spec_and_window_computes_once(self) -> None:
        engine, backend = self._engine({"rsi"})
        spec = IndicatorSpec.create("rsi", {"period": 14})
        window = _multi_window(1.0, 2.0, 3.0)
        first = engine.compute(spec, window)
        second = engine.compute(spec, window)
        assert len(backend.calls) == 1
        assert second is first  # memo hit returns the identical result object
        assert engine.hits == 1 and engine.misses == 1

    def test_equal_window_content_hits_across_instances(self) -> None:
        # Content-addressed: a NEW but byte-identical window (e.g. the same
        # bar seen by another strategy) is a hit, never a recompute.
        engine, backend = self._engine({"rsi"})
        spec = IndicatorSpec.create("rsi", {"period": 14})
        engine.compute(spec, _multi_window(1.0, 2.0, 3.0))
        engine.compute(spec, _multi_window(1.0, 2.0, 3.0))
        assert len(backend.calls) == 1

    def test_new_bar_recomputes(self) -> None:
        engine, backend = self._engine({"rsi"})
        spec = IndicatorSpec.create("rsi", {"period": 14})
        engine.compute(spec, _multi_window(1.0, 2.0, 3.0))
        engine.compute(spec, _multi_window(2.0, 3.0, 4.0))  # window advanced
        assert len(backend.calls) == 2

    def test_different_params_are_distinct_entries(self) -> None:
        engine, backend = self._engine({"rsi"})
        window = _multi_window(1.0, 2.0, 3.0)
        engine.compute(IndicatorSpec.create("rsi", {"period": 14}), window)
        engine.compute(IndicatorSpec.create("rsi", {"period": 7}), window)
        assert len(backend.calls) == 2

    def test_lru_evicts_oldest(self) -> None:
        backend = CountingBackend({"rsi"})
        engine = CachingIndicatorEngine([backend], maxsize=1)
        spec = IndicatorSpec.create("rsi", {"period": 14})
        first, second = _multi_window(1.0), _multi_window(2.0)
        engine.compute(spec, first)
        engine.compute(spec, second)  # evicts `first`
        engine.compute(spec, first)  # recompute after eviction
        assert len(backend.calls) == 3

    def test_flat_panel_and_compute_many_go_through_memo(self) -> None:
        engine, backend = self._engine({"rsi"})
        spec = IndicatorSpec.create("rsi", {"period": 14})
        window = _multi_window(1.0, 2.0, 3.0)
        engine.compute(spec, window)
        engine.flat_panel([spec], window)
        engine.compute_many([spec], window)
        assert len(backend.calls) == 1

    def test_cache_clear_resets(self) -> None:
        engine, backend = self._engine({"rsi"})
        spec = IndicatorSpec.create("rsi", {"period": 14})
        window = _multi_window(1.0, 2.0, 3.0)
        engine.compute(spec, window)
        engine.cache_clear()
        engine.compute(spec, window)
        assert len(backend.calls) == 2
        assert engine.hits == 0 and engine.misses == 1

    def test_rejects_non_positive_maxsize(self) -> None:
        with pytest.raises(ValueError):
            CachingIndicatorEngine([], maxsize=0)

    def test_cached_default_engine_is_a_shared_singleton(self) -> None:
        assert cached_default_engine() is cached_default_engine()
        assert isinstance(cached_default_engine(), CachingIndicatorEngine)
