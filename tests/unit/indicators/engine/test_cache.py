"""Unit tests for the Indicator Cache Engine (dedup + panel store).

Backend-agnostic: a counting fake backend proves the "compute each unique spec
once per symbol" guarantee without TA-Lib.
"""

from __future__ import annotations

import numpy as np

from shared.indicators.engine.base import IndicatorBackend, IndicatorResult
from shared.indicators.engine.cache import (
    IndicatorCacheEngine,
    InMemoryPanelStore,
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
