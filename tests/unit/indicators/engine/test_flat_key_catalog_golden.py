"""Zero-drift pins for the ``flat_key`` catalog (P2-b alignment tripwire)."""

from __future__ import annotations

import pytest

from shared.indicators.engine.spec import flat_key

_SHARED_VOCABULARY_PINS: dict[tuple[str, str], str] = {
    ("bollinger", "upper"): "bb_upper",
    ("bollinger", "middle"): "bb_middle",
    ("bollinger", "lower"): "bb_lower",
    ("stochastic", "k"): "stoch_k",
    ("stochastic", "d"): "stoch_d",
    ("stochrsi", "k"): "stochrsi_k",
    ("stochrsi", "d"): "stochrsi_d",
    ("macd", "value"): "macd",
    ("macd", "signal"): "macd_signal",
    ("macd", "histogram"): "macd_hist",
    ("trix", "value"): "trix",
    ("trix", "signal"): "trix_signal",
    ("rsi", "value"): "rsi",
    ("mfi", "value"): "mfi",
    ("adx", "value"): "adx",
    ("atr", "value"): "atr",
    ("vwap", "value"): "vwap",
    ("rvol", "value"): "rvol",
    ("volume_ma", "value"): "volume_ma",
    ("williams_r", "value"): "williams_r",
}


@pytest.mark.parametrize(
    ("indicator_id", "output", "expected"),
    [(iid, out, key) for (iid, out), key in _SHARED_VOCABULARY_PINS.items()],
)
def test_shared_vocabulary_flat_keys_are_pinned(
    indicator_id: str, output: str, expected: str
) -> None:
    assert flat_key(indicator_id, output) == expected


@pytest.mark.parametrize("period", [5, 20, 60])
def test_period_keyed_ema_sma_flat_keys_are_pinned(period: int) -> None:
    assert flat_key("ema", "value", {"period": period}) == f"ema_{period}"
    assert flat_key("sma", "value", {"period": period}) == f"sma_{period}"
