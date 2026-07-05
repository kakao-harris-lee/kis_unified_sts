"""Value objects and canonical key normalization for the indicator engine.

This is the input/identity layer of the Track A single-source-of-truth
calculation engine (see
``docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md``). It is
deliberately free of any dependency on TA-Lib, pandas, or the existing runtime
calculators so the abstraction can be imported and unit-tested in isolation and
so no backend choice leaks into the interface.

Two responsibilities live here:

* ``IndicatorSpec`` / ``OHLCVWindow`` — the immutable request + input a backend
  consumes. ``IndicatorSpec`` is frozen and hashable so it doubles as the
  deduplication key ("compute RSI(14) once even if ten strategies ask for it").
* ``flat_key`` — the one place that maps a builder-catalog ``id.output`` onto
  the flat runtime cache key. This resolves the builder plumbing "name
  mismatch" gap (catalog exposes ``bollinger.upper`` / ``stochastic.k`` while
  the runtime historically emitted ``bb_upper`` / ``stoch_k``) in a single
  shared table instead of scattered per-consumer knowledge.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np

# Builder-catalog (indicator_id, output_id) -> canonical flat runtime key.
# Single-output indicators (rsi, atr, adx, vwap, ...) are omitted and default
# to their bare id via ``flat_key`` below.
_OUTPUT_KEY_OVERRIDES: Final[dict[tuple[str, str], str]] = {
    ("bollinger", "upper"): "bb_upper",
    ("bollinger", "middle"): "bb_middle",
    ("bollinger", "lower"): "bb_lower",
    ("stochastic", "k"): "stoch_k",
    ("stochastic", "d"): "stoch_d",
    ("macd", "value"): "macd",
    ("macd", "signal"): "macd_signal",
    ("macd", "histogram"): "macd_hist",
    ("trix", "signal"): "trix_signal",
}

# Indicators whose flat key encodes the period (the runtime exposes several
# periods side by side, e.g. ``ema_5`` / ``ema_20`` / ``ema_60``).
_PERIOD_KEYED: Final[frozenset[str]] = frozenset({"sma", "ema"})


def flat_key(
    indicator_id: str,
    output: str = "value",
    params: Mapping[str, float] | None = None,
) -> str:
    """Return the canonical flat cache key for one indicator output.

    Args:
        indicator_id: Builder-catalog indicator id (e.g. ``bollinger``).
        output: Output id within that indicator (e.g. ``upper``). Defaults to
            ``value`` for single-output indicators.
        params: Resolved parameters, used only for period-keyed indicators
            (``sma`` / ``ema``) to embed the period in the key.

    Returns:
        The flat key a consumer (builder evaluator, cache writer) should read,
        e.g. ``bb_upper``, ``stoch_k``, ``ema_20``, or ``rsi``.
    """
    override = _OUTPUT_KEY_OVERRIDES.get((indicator_id, output))
    if override is not None:
        return override
    if indicator_id in _PERIOD_KEYED:
        period = int((params or {}).get("period", 0) or 0)
        if period > 0:
            return f"{indicator_id}_{period}"
    return indicator_id


@dataclass(frozen=True)
class IndicatorSpec:
    """An immutable, hashable request to compute one indicator.

    Frozen so it can be used directly as a dict key for deduplication. Build via
    :meth:`create` so ``params`` is canonicalized (sorted float pairs) — two
    logically-equal requests then compare and hash equal regardless of dict
    ordering.
    """

    indicator_id: str
    params: tuple[tuple[str, float], ...] = ()
    timeframe: str = "5m"

    @classmethod
    def create(
        cls,
        indicator_id: str,
        params: Mapping[str, float] | None = None,
        timeframe: str = "5m",
    ) -> IndicatorSpec:
        """Create a spec with canonicalized (sorted, float-coerced) params."""
        items = tuple(sorted((str(k), float(v)) for k, v in (params or {}).items()))
        return cls(indicator_id=indicator_id, params=items, timeframe=timeframe)

    @property
    def param_map(self) -> dict[str, float]:
        """Params as a plain mapping."""
        return dict(self.params)

    @property
    def key(self) -> str:
        """Stable human-readable identity, e.g. ``5m:bollinger(period=20,std=2)``."""
        rendered = ",".join(f"{key}={value:g}" for key, value in self.params)
        return f"{self.timeframe}:{self.indicator_id}({rendered})"


@dataclass(frozen=True, eq=False)
class OHLCVWindow:
    """A bounded OHLCV window fed to a backend.

    Arrays are float64 and C-contiguous (TA-Lib requires this). ``eq=False``
    avoids ambiguous element-wise ``__eq__`` on the ndarray fields — windows are
    never compared or hashed.
    """

    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    @classmethod
    def from_sequences(
        cls,
        *,
        open: object,
        high: object,
        low: object,
        close: object,
        volume: object,
    ) -> OHLCVWindow:
        """Build a window from any array-likes, coercing to float64 arrays.

        Raises:
            ValueError: if the columns have differing lengths.
        """
        arrays = {
            "open": np.ascontiguousarray(open, dtype=np.float64),
            "high": np.ascontiguousarray(high, dtype=np.float64),
            "low": np.ascontiguousarray(low, dtype=np.float64),
            "close": np.ascontiguousarray(close, dtype=np.float64),
            "volume": np.ascontiguousarray(volume, dtype=np.float64),
        }
        lengths = {name: arr.shape[0] for name, arr in arrays.items()}
        if len(set(lengths.values())) > 1:
            raise ValueError(f"OHLCV columns have differing lengths: {lengths}")
        return cls(**arrays)

    def __len__(self) -> int:
        return int(self.close.shape[0])
