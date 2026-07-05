"""Declarative Indicator Context: YAML specs -> engine -> DataFrame -> evaluator.

Proves the builder computes no math itself (all via the engine) and that the
full-series context makes cross operators finally fire.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("talib")

from shared.indicators.engine import OHLCVWindow  # noqa: E402
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator  # noqa: E402
from shared.strategy_builder.indicator_context import (  # noqa: E402
    build_indicator_context,
)
from shared.strategy_builder.schema import BuilderState  # noqa: E402


def _window(close: list[float]) -> OHLCVWindow:
    arr = np.asarray(close, dtype=float)
    return OHLCVWindow.from_sequences(
        open=arr,
        high=arr + 1.0,
        low=arr - 1.0,
        close=arr,
        volume=np.full(arr.shape, 1000.0),
    )


def _cross_state() -> BuilderState:
    return BuilderState.model_validate(
        {
            "metadata": {"name": "golden cross"},
            "asset_class": "stock",
            "indicators": [
                {"indicator_id": "ema", "alias": "ema_fast", "params": {"period": 3}},
                {"indicator_id": "ema", "alias": "ema_slow", "params": {"period": 10}},
            ],
            "entry": {
                "logic": "AND",
                "conditions": [
                    {
                        "left": {"type": "indicator", "indicator_alias": "ema_fast"},
                        "operator": "cross_above",
                        "right": {"type": "indicator", "indicator_alias": "ema_slow"},
                    }
                ],
            },
            "exit": {"conditions": []},
        }
    )


def test_context_columns_come_from_engine() -> None:
    state = _cross_state()
    ctx = build_indicator_context(state, _window([float(i) for i in range(30)]))
    cols = set(ctx.frame.columns)
    assert {"open", "high", "low", "close", "volume"} <= cols
    assert "ema_fast.value" in cols
    assert "ema_slow.value" in cols


def test_to_symbol_series_splits_fields_and_indicators() -> None:
    state = _cross_state()
    ctx = build_indicator_context(state, _window([float(i) for i in range(30)]))
    series = ctx.to_symbol_series("005930", name="Samsung")
    assert set(series.fields) == {"open", "high", "low", "close", "volume"}
    assert set(series.indicators) == {"ema_fast.value", "ema_slow.value"}


def test_cross_above_fires_through_declarative_pipeline() -> None:
    # Downtrend keeps fast EMA below slow; the final spike flips fast above slow
    # on the last bar -> a genuine cross_above. This is impossible with the old
    # scalar-only context (no distinct previous value).
    state = _cross_state()
    close = [100 - 2 * i for i in range(19)] + [200.0]
    ctx = build_indicator_context(state, _window(close))
    series = ctx.to_symbol_series("005930")

    evaluation = StrategyBuilderEvaluator().evaluate_group(
        state.entry.conditions, state.entry.logic, series
    )
    assert evaluation.passed, "cross_above should fire on the crossover bar"
    assert not evaluation.missing


def test_no_cross_when_no_crossover() -> None:
    # Monotonic rise: fast stays above slow the whole time -> no NEW cross_above.
    state = _cross_state()
    ctx = build_indicator_context(state, _window([100.0 + i for i in range(30)]))
    series = ctx.to_symbol_series("005930")
    evaluation = StrategyBuilderEvaluator().evaluate_group(
        state.entry.conditions, state.entry.logic, series
    )
    assert not evaluation.passed


def test_unsupported_indicator_is_missing_not_crash() -> None:
    state = BuilderState.model_validate(
        {
            "metadata": {"name": "unknown"},
            "indicators": [
                {"indicator_id": "definitely_not_real", "alias": "x"},
            ],
            "entry": {
                "conditions": [
                    {
                        "left": {"type": "indicator", "indicator_alias": "x"},
                        "operator": "greater_than",
                        "right": {"type": "value", "value": 0.0},
                    }
                ]
            },
            "exit": {"conditions": []},
        }
    )
    ctx = build_indicator_context(state, _window([float(i) for i in range(20)]))
    assert "x.value" not in ctx.frame.columns  # omitted, no crash
    series = ctx.to_symbol_series("005930")
    evaluation = StrategyBuilderEvaluator().evaluate_group(
        state.entry.conditions, state.entry.logic, series
    )
    assert not evaluation.passed
    assert evaluation.missing  # reported as missing -> fails safe
