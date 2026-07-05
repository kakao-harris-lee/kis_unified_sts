"""Unit tests for the IndicatorEngine registry (resolution + dedup).

Backend-agnostic: uses a counting fake backend so these run without TA-Lib.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorResult,
    UnsupportedIndicatorError,
)
from shared.indicators.engine.registry import IndicatorEngine
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


class CountingBackend(IndicatorBackend):
    """Fake backend that records how many times each spec was computed."""

    def __init__(self, name: str, ids: set[str], value: float = 1.0) -> None:
        self._name = name
        self._ids = frozenset(ids)
        self._value = value
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def supported_ids(self) -> frozenset[str]:
        return self._ids

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        self.calls.append(spec.key)
        series = np.array([self._value], dtype=np.float64)
        return IndicatorResult(
            spec=spec, series={"value": series}, latest={"value": self._value}
        )


@pytest.fixture
def window() -> OHLCVWindow:
    return OHLCVWindow.from_sequences(
        open=[1.0], high=[1.0], low=[1.0], close=[1.0], volume=[1.0]
    )


def test_resolve_and_supported_ids_union() -> None:
    a = CountingBackend("a", {"rsi", "atr"})
    b = CountingBackend("b", {"adx"})
    engine = IndicatorEngine([a, b])
    assert engine.resolve("rsi") is a
    assert engine.resolve("adx") is b
    assert engine.supported_ids() == frozenset({"rsi", "atr", "adx"})


def test_resolve_prefers_first_registered_backend() -> None:
    first = CountingBackend("first", {"rsi"}, value=1.0)
    second = CountingBackend("second", {"rsi"}, value=2.0)
    engine = IndicatorEngine([first, second])
    assert engine.resolve("rsi") is first


def test_unsupported_indicator_raises() -> None:
    engine = IndicatorEngine([CountingBackend("a", {"rsi"})])
    with pytest.raises(UnsupportedIndicatorError, match="vwap"):
        engine.resolve("vwap")


def test_compute_many_dedups_identical_specs(window: OHLCVWindow) -> None:
    backend = CountingBackend("a", {"rsi"})
    engine = IndicatorEngine([backend])
    specs = [
        IndicatorSpec.create("rsi", {"period": 14}),
        IndicatorSpec.create("rsi", {"period": 14}),  # duplicate
        IndicatorSpec.create("rsi", {"period": 14}),  # duplicate
    ]
    results = engine.compute_many(specs, window)
    assert len(results) == 1
    assert len(backend.calls) == 1  # computed once despite 3 requests


def test_compute_many_keeps_distinct_params(window: OHLCVWindow) -> None:
    backend = CountingBackend("a", {"rsi"})
    engine = IndicatorEngine([backend])
    specs = [
        IndicatorSpec.create("rsi", {"period": 14}),
        IndicatorSpec.create("rsi", {"period": 21}),
    ]
    results = engine.compute_many(specs, window)
    assert len(results) == 2
    assert len(backend.calls) == 2


def test_flat_panel_merges_canonical_keys(window: OHLCVWindow) -> None:
    backend = CountingBackend("a", {"rsi", "atr"}, value=5.0)
    engine = IndicatorEngine([backend])
    specs = [
        IndicatorSpec.create("rsi", {"period": 14}),
        IndicatorSpec.create("atr", {"period": 14}),
    ]
    panel = engine.flat_panel(specs, window)
    assert panel == {"rsi": 5.0, "atr": 5.0}


class _PeriodEchoBackend(IndicatorBackend):
    """Backend whose latest value IS the requested period (observes collisions)."""

    @property
    def name(self) -> str:
        return "period-echo"

    def supported_ids(self) -> frozenset[str]:
        return frozenset({"rsi"})

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        period = spec.param_map.get("period", 0.0)
        return IndicatorResult(
            spec=spec,
            series={"value": np.array([period], dtype=np.float64)},
            latest={"value": period},
        )


def test_flat_panel_last_wins_on_flatkey_collision(window: OHLCVWindow) -> None:
    # rsi is NOT period-keyed, so rsi(14) and rsi(21) both flatten to "rsi".
    # compute_many keeps them distinct (2 computations) but flat_panel is
    # last-wins on the shared key — this pins that documented foot-gun.
    engine = IndicatorEngine([_PeriodEchoBackend()])
    specs = [
        IndicatorSpec.create("rsi", {"period": 14}),
        IndicatorSpec.create("rsi", {"period": 21}),
    ]
    assert len(engine.compute_many(specs, window)) == 2
    assert engine.flat_panel(specs, window) == {"rsi": 21.0}
