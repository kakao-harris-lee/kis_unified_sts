"""Unit tests for engine value objects + canonical key normalization."""

from __future__ import annotations

import numpy as np
import pytest

from shared.indicators.engine.spec import (
    IndicatorSpec,
    OHLCVWindow,
    flat_key,
)


class TestFlatKey:
    def test_single_output_defaults_to_id(self) -> None:
        assert flat_key("rsi") == "rsi"
        assert flat_key("atr", "value") == "atr"
        assert flat_key("williams_r", "value") == "williams_r"

    def test_bollinger_outputs_map_to_bb_keys(self) -> None:
        assert flat_key("bollinger", "upper") == "bb_upper"
        assert flat_key("bollinger", "middle") == "bb_middle"
        assert flat_key("bollinger", "lower") == "bb_lower"

    def test_stochastic_and_macd_output_overrides(self) -> None:
        assert flat_key("stochastic", "k") == "stoch_k"
        assert flat_key("stochastic", "d") == "stoch_d"
        assert flat_key("macd", "value") == "macd"
        assert flat_key("macd", "signal") == "macd_signal"
        assert flat_key("macd", "histogram") == "macd_hist"

    def test_period_keyed_indicators_embed_period(self) -> None:
        assert flat_key("ema", "value", {"period": 20}) == "ema_20"
        assert flat_key("sma", "value", {"period": 50}) == "sma_50"

    def test_period_keyed_without_period_falls_back_to_id(self) -> None:
        assert flat_key("ema", "value") == "ema"
        assert flat_key("ema", "value", {"period": 0}) == "ema"


class TestIndicatorSpec:
    def test_create_canonicalizes_params_order(self) -> None:
        a = IndicatorSpec.create("macd", {"fast": 12, "slow": 26, "signal": 9})
        b = IndicatorSpec.create("macd", {"signal": 9, "slow": 26, "fast": 12})
        assert a == b
        assert hash(a) == hash(b)

    def test_spec_is_hashable_dedup_key(self) -> None:
        a = IndicatorSpec.create("rsi", {"period": 14})
        b = IndicatorSpec.create("rsi", {"period": 14})
        c = IndicatorSpec.create("rsi", {"period": 21})
        seen = {a: 1}
        assert b in seen  # equal spec dedups
        assert c not in seen

    def test_timeframe_participates_in_identity(self) -> None:
        a = IndicatorSpec.create("rsi", {"period": 14}, timeframe="5m")
        b = IndicatorSpec.create("rsi", {"period": 14}, timeframe="1m")
        assert a != b

    def test_param_map_roundtrip(self) -> None:
        spec = IndicatorSpec.create("bollinger", {"period": 20, "std": 2})
        assert spec.param_map == {"period": 20.0, "std": 2.0}

    def test_key_is_stable_and_readable(self) -> None:
        spec = IndicatorSpec.create("bollinger", {"period": 20, "std": 2})
        assert spec.key == "5m:bollinger(period=20,std=2)"


class TestOHLCVWindow:
    def test_from_sequences_coerces_float64_contiguous(self) -> None:
        window = OHLCVWindow.from_sequences(
            open=[1, 2, 3],
            high=[2, 3, 4],
            low=[0, 1, 2],
            close=[1, 2, 3],
            volume=[10, 20, 30],
        )
        assert len(window) == 3
        assert window.close.dtype == np.float64
        assert window.close.flags["C_CONTIGUOUS"]

    def test_from_sequences_rejects_ragged_columns(self) -> None:
        with pytest.raises(ValueError, match="differing lengths"):
            OHLCVWindow.from_sequences(
                open=[1, 2],
                high=[2, 3],
                low=[0, 1],
                close=[1, 2, 3],  # longer
                volume=[10, 20],
            )


class TestWindowContentToken:
    """OHLCVWindow.content_token — the cache engine's window identity."""

    def _window(self, values: list[float]) -> OHLCVWindow:
        return OHLCVWindow.from_sequences(
            open=values, high=values, low=values, close=values, volume=values
        )

    def test_equal_content_yields_equal_token(self) -> None:
        assert (
            self._window([1.0, 2.0]).content_token()
            == self._window([1.0, 2.0]).content_token()
        )

    def test_different_content_yields_different_token(self) -> None:
        assert (
            self._window([1.0, 2.0]).content_token()
            != self._window([1.0, 3.0]).content_token()
        )

    def test_token_is_cached_on_the_window(self) -> None:
        window = self._window([1.0, 2.0, 3.0])
        assert window.content_token() is window.content_token()  # computed once

    def test_column_boundary_is_unambiguous(self) -> None:
        # Same flattened bytes, different column split -> different token.
        a = OHLCVWindow.from_sequences(
            open=[1.0, 2.0],
            high=[3.0, 4.0],
            low=[1.0, 2.0],
            close=[3.0, 4.0],
            volume=[0.0, 0.0],
        )
        b = OHLCVWindow.from_sequences(
            open=[1.0, 2.0],
            high=[3.0, 4.0],
            low=[3.0, 4.0],
            close=[1.0, 2.0],
            volume=[0.0, 0.0],
        )
        assert a.content_token() != b.content_token()
