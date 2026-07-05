"""Declarative Indicator Context for the no-code Strategy Builder.

The ``Indicator Context`` stage of the declarative pipeline:

    YAML -> IndicatorSpec -> TA-Lib Registry -> TA-Lib Adapter
    -> Indicator Context (DataFrame) -> Condition Evaluator -> Strategy Engine.

Each ``BuilderIndicator`` (an ``indicator_id`` + params + output alias declared
in the builder YAML) becomes an :class:`IndicatorSpec` computed by the indicator
engine (``shared/indicators/engine``). Every output series is materialized as an
``alias.output`` column in a single DataFrame. The builder itself computes no
indicator math; all calculation is delegated to the engine (TA-Lib for standard
indicators, NumPy for the rest). Adding a new indicator is a registry change —
this module and the evaluator never change.

Because the context carries the *full* series (not a single scalar), the
crossover operators (``cross_above`` / ``cross_below``) have a genuine previous
value and finally work in the streaming/backtest runtimes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from shared.indicators.engine import (
    IndicatorEngine,
    IndicatorError,
    IndicatorSpec,
    OHLCVWindow,
    default_engine,
)
from shared.strategy_builder.schema import BuilderState, SymbolSeries

_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def _numeric_params(params: Mapping[str, int | float | str]) -> dict[str, float]:
    """Keep only numeric params (the engine's specs are numeric-only)."""
    numeric: dict[str, float] = {}
    for key, value in params.items():
        try:
            numeric[key] = float(value)
        except (TypeError, ValueError):
            continue
    return numeric


@dataclass(frozen=True, eq=False)
class IndicatorContext:
    """A computed indicator panel: a DataFrame of OHLCV + ``alias.output`` columns."""

    frame: pd.DataFrame

    def to_symbol_series(self, symbol: str, name: str | None = None) -> SymbolSeries:
        """Adapt the DataFrame to the SymbolSeries the evaluator consumes."""
        fields = {
            column: self.frame[column].tolist()
            for column in _OHLCV_COLUMNS
            if column in self.frame.columns
        }
        indicators = {
            column: self.frame[column].tolist()
            for column in self.frame.columns
            if column not in _OHLCV_COLUMNS
        }
        return SymbolSeries(
            symbol=symbol,
            name=name,
            timestamps=[],
            fields=fields,
            indicators=indicators,
        )


def build_indicator_context(
    state: BuilderState,
    window: OHLCVWindow,
    engine: IndicatorEngine | None = None,
) -> IndicatorContext:
    """Compute every builder indicator via the engine into one DataFrame.

    Each output series is exposed as an ``alias.output`` column (full series, so
    cross operators have prior values). Unsupported or failed indicators are
    omitted — the evaluator then reports them as ``missing`` and the condition
    group fails safe (no signal).

    Args:
        state: Parsed builder state (its ``indicators`` drive computation).
        window: OHLCV history window to compute over.
        engine: Indicator engine; defaults to :func:`default_engine`.

    Returns:
        The computed :class:`IndicatorContext`.
    """
    engine = engine or default_engine()
    columns: dict[str, np.ndarray] = {
        "open": window.open,
        "high": window.high,
        "low": window.low,
        "close": window.close,
        "volume": window.volume,
    }
    for indicator in state.indicators:
        spec = IndicatorSpec.create(
            indicator.indicator_id, _numeric_params(indicator.params)
        )
        try:
            result = engine.compute(spec, window)
        except IndicatorError:
            continue
        for output, series in result.series.items():
            columns[f"{indicator.alias}.{output}"] = np.asarray(series, dtype=float)
    return IndicatorContext(frame=pd.DataFrame(columns))
