"""Builder-path panel caching: compute-once semantics (P2-b).

Proves that N builder strategies sharing an indicator spec compute it once per
symbol/bar when they share a :class:`CachingIndicatorEngine` — and that the
runtime bridges (builder_v1 entry + exit) actually share the process singleton
so this holds in the paper runtime, not just in a lab setup.
"""

from __future__ import annotations

import numpy as np

from shared.indicators.engine import (
    CachingIndicatorEngine,
    IndicatorResult,
    IndicatorSpec,
    OHLCVWindow,
)
from shared.indicators.engine.base import IndicatorBackend
from shared.strategy.entry.builder_strategy import (
    BuilderStrategyConfig,
    BuilderStrategyEntry,
)
from shared.strategy.exit.builder_strategy_exit import (
    BuilderStrategyExit,
    BuilderStrategyExitConfig,
)
from shared.strategy_builder.indicator_context import build_indicator_context
from shared.strategy_builder.schema import BuilderState


class CountingSeriesBackend(IndicatorBackend):
    """Fake backend that returns window-length series and counts computes."""

    def __init__(self, ids: set[str]) -> None:
        self._ids = frozenset(ids)
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "counting-series"

    def supported_ids(self) -> frozenset[str]:
        return self._ids

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        self.calls.append(spec.key)
        series = np.linspace(1.0, 2.0, num=len(window))
        return IndicatorResult(
            spec=spec, series={"value": series}, latest={"value": float(series[-1])}
        )


def _window(n: int = 30) -> OHLCVWindow:
    close = np.arange(n, dtype=float) + 100.0
    return OHLCVWindow.from_sequences(
        open=close, high=close + 1, low=close - 1, close=close, volume=close * 10
    )


def _state(name: str, indicators: list[dict]) -> BuilderState:
    return BuilderState.model_validate(
        {
            "metadata": {"name": name},
            "asset_class": "stock",
            "indicators": indicators,
            "entry": {"conditions": []},
            "exit": {"conditions": []},
        }
    )


def test_two_strategies_sharing_a_spec_compute_it_once_per_bar() -> None:
    backend = CountingSeriesBackend({"rsi", "ema"})
    engine = CachingIndicatorEngine([backend])
    window = _window()

    strategy_a = _state(
        "A", [{"indicator_id": "rsi", "alias": "r", "params": {"period": 14}}]
    )
    strategy_b = _state(
        "B",
        [
            {"indicator_id": "rsi", "alias": "my_rsi", "params": {"period": 14}},
            {"indicator_id": "ema", "alias": "e", "params": {"period": 5}},
        ],
    )

    ctx_a = build_indicator_context(strategy_a, window, engine)
    ctx_b = build_indicator_context(strategy_b, window, engine)

    # rsi(14) computed ONCE despite two strategies (different aliases);
    # ema(5) computed once. Total backend computes = unique specs = 2.
    assert backend.calls == ["5m:rsi(period=14)", "5m:ema(period=5)"]
    assert engine.hits == 1

    # Same values land under each strategy's own alias column.
    np.testing.assert_array_equal(
        ctx_a.frame["r.value"].to_numpy(), ctx_b.frame["my_rsi.value"].to_numpy()
    )


def test_duplicate_alias_specs_within_one_strategy_compute_once() -> None:
    backend = CountingSeriesBackend({"rsi"})
    engine = CachingIndicatorEngine([backend])
    state = _state(
        "dup",
        [
            {"indicator_id": "rsi", "alias": "fast", "params": {"period": 14}},
            {"indicator_id": "rsi", "alias": "slow", "params": {"period": 14}},
        ],
    )
    ctx = build_indicator_context(state, _window(), engine)
    assert len(backend.calls) == 1
    assert {"fast.value", "slow.value"} <= set(ctx.frame.columns)


def test_new_bar_recomputes_no_stale_reuse() -> None:
    backend = CountingSeriesBackend({"rsi"})
    engine = CachingIndicatorEngine([backend])
    state = _state(
        "A", [{"indicator_id": "rsi", "alias": "r", "params": {"period": 14}}]
    )
    build_indicator_context(state, _window(30), engine)
    build_indicator_context(state, _window(31), engine)  # new bar arrived
    assert len(backend.calls) == 2


def test_runtime_bridges_share_the_process_singleton_engine() -> None:
    entry_a = BuilderStrategyEntry(BuilderStrategyConfig(builder_state={}))
    entry_b = BuilderStrategyEntry(BuilderStrategyConfig(builder_state={}))
    exit_ = BuilderStrategyExit(BuilderStrategyExitConfig(builder_state={}))
    assert entry_a._engine is entry_b._engine
    assert entry_a._engine is exit_._engine
    assert isinstance(entry_a._engine, CachingIndicatorEngine)
