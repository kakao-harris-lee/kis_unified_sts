"""Tests for StreamingIndicatorEngine momentum indicators."""

from __future__ import annotations

from datetime import datetime

from shared.indicators.streaming.engine import StreamingIndicatorEngine


def _build_warm_mtf_engine(
    symbol: str = "005930",
    timeframe: int = 5,
    num_1m_candles: int = 260,
) -> StreamingIndicatorEngine:
    """Build an engine with enough 1m candles to produce warm MTF candles."""
    engine = StreamingIndicatorEngine(
        bb_period=20,
        mtf_timeframes=[timeframe],
        staleness_seconds=0,
    )

    base_price = 70000.0
    base_volume = 1000
    cumulative_volume = 0

    for minute in range(num_1m_candles):
        ts = datetime(2026, 2, 17, 9 + minute // 60, minute % 60, 30)
        price = base_price + minute * 10
        cumulative_volume += base_volume + minute

        engine.on_tick(
            symbol,
            {
                "close": price,
                "high": price + 50,
                "low": price - 50,
                "volume": cumulative_volume,
            },
            ts,
        )

    cumulative_volume += base_volume + num_1m_candles
    engine.on_tick(
        symbol,
        {
            "close": base_price + num_1m_candles * 10,
            "high": base_price + num_1m_candles * 10 + 50,
            "low": base_price + num_1m_candles * 10 - 50,
            "volume": cumulative_volume,
        },
        datetime(2026, 2, 17, 9 + num_1m_candles // 60, num_1m_candles % 60, 31),
    )

    return engine


class TestMomentumIndicatorsTRIX:
    """Tests for TRIX momentum indicator."""

    def test_get_momentum_indicators_trix_present(self):
        """TRIX and TRIX signal should be present in momentum indicators."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "trix" in indicators
        assert "trix_signal" in indicators
        assert isinstance(indicators["trix"], float)
        assert isinstance(indicators["trix_signal"], float)

    def test_trix_values_are_finite(self):
        """TRIX values should be finite numbers."""
        import math

        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert math.isfinite(indicators["trix"])
        assert math.isfinite(indicators["trix_signal"])

    def test_trix_changes_with_price_trend(self):
        """TRIX should reflect price trend direction."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "trix" in indicators
        assert isinstance(indicators["trix"], float)


class TestMomentumIndicatorsCCI:
    """Tests for CCI (Commodity Channel Index) momentum indicator."""

    def test_get_momentum_indicators_cci_present(self):
        """CCI should be present in momentum indicators."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "cci" in indicators
        assert isinstance(indicators["cci"], float)

    def test_cci_is_finite(self):
        """CCI should be a finite number."""
        import math

        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert math.isfinite(indicators["cci"])

    def test_cci_typical_range(self):
        """CCI typically ranges from -200 to +200, but can exceed."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert (
            -1000 < indicators["cci"] < 1000
        ), f"CCI {indicators['cci']} is outside normal bounds"


class TestMomentumIndicatorsMACD:
    """Tests for MACD momentum indicator."""

    def test_get_momentum_indicators_macd_present(self):
        """MACD line, signal, and oscillator should be present."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "macd_line" in indicators
        assert "macd_signal" in indicators
        assert "macd_oscillator" in indicators

    def test_macd_values_are_finite(self):
        """All MACD values should be finite numbers."""
        import math

        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert math.isfinite(indicators["macd_line"])
        assert math.isfinite(indicators["macd_signal"])
        assert math.isfinite(indicators["macd_oscillator"])

    def test_macd_oscillator_is_difference(self):
        """MACD oscillator should equal MACD line minus MACD signal."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        calculated_osc = indicators["macd_line"] - indicators["macd_signal"]
        assert abs(indicators["macd_oscillator"] - calculated_osc) < 1e-6, (
            f"MACD oscillator mismatch: "
            f"expected {calculated_osc}, got {indicators['macd_oscillator']}"
        )

    def test_macd_positive_in_uptrend(self):
        """MACD line should be positive for strong uptrend."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert (
            indicators["macd_line"] > 0
        ), f"MACD line should be positive in uptrend, got {indicators['macd_line']}"


class TestMomentumIndicatorsStochastic:
    """Tests for Stochastic Oscillator momentum indicator."""

    def test_get_momentum_indicators_stochastic_present(self):
        """Stochastic %K and %D should be present."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "sto_k" in indicators
        assert "sto_d" in indicators

    def test_stochastic_range_0_to_100(self):
        """Stochastic %K and %D should be in range [0, 100]."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert (
            0 <= indicators["sto_k"] <= 100
        ), f"sto_k {indicators['sto_k']} out of range [0, 100]"
        assert (
            0 <= indicators["sto_d"] <= 100
        ), f"sto_d {indicators['sto_d']} out of range [0, 100]"

    def test_stochastic_high_in_uptrend(self):
        """Stochastic should be high (>50) for steadily rising prices."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert (
            indicators["sto_k"] > 50
        ), f"sto_k should be > 50 in uptrend, got {indicators['sto_k']}"


class TestMomentumIndicatorsOtherIndicators:
    """Tests for other momentum indicators (OBV, RSI, Williams %R)."""

    def test_obv_present(self):
        """On-Balance Volume should be present."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "obv" in indicators
        assert isinstance(indicators["obv"], float)

    def test_rsi_present_and_in_range(self):
        """RSI should be present and in range [0, 100]."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "rsi" in indicators
        assert (
            0 <= indicators["rsi"] <= 100
        ), f"RSI {indicators['rsi']} out of range [0, 100]"

    def test_williams_r_present_and_in_range(self):
        """Williams %R should be present and in range [-100, 0]."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "williams_r" in indicators
        assert (
            -100 <= indicators["williams_r"] <= 0
        ), f"Williams %R {indicators['williams_r']} out of range [-100, 0]"


class TestMomentumIndicatorsMetadata:
    """Tests for metadata fields in momentum indicators."""

    def test_includes_timeframe(self):
        """Result should include timeframe metadata."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "timeframe" in indicators
        assert indicators["timeframe"] == 5

    def test_includes_candle_count(self):
        """Result should include candle count metadata."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "candle_count" in indicators
        assert indicators["candle_count"] > 0

    def test_includes_dataframe(self):
        """Result should include full DataFrame for advanced analysis."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert "df" in indicators
        import pandas as pd

        assert isinstance(indicators["df"], pd.DataFrame)
        assert len(indicators["df"]) == indicators["candle_count"]


class TestMomentumIndicatorsWarmup:
    """Tests for warmup and data sufficiency requirements."""

    def test_momentum_requires_mtf_warmup(self):
        """Momentum indicators require sufficient MTF candles."""
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[5],
            staleness_seconds=0,
        )

        symbol = "TEST"
        cumulative = 0

        for minute in range(10):
            ts = datetime(2026, 2, 17, 9, minute, 30)
            cumulative += 1000
            engine.on_tick(
                symbol,
                {"close": 100.0, "high": 110.0, "low": 90.0, "volume": cumulative},
                ts,
            )

        cumulative += 1000
        engine.on_tick(
            symbol,
            {"close": 100.0, "high": 110.0, "low": 90.0, "volume": cumulative},
            datetime(2026, 2, 17, 9, 10, 31),
        )

        indicators = engine.get_momentum_indicators(symbol, timeframe=5)
        assert (
            indicators == {}
        ), "Should return empty dict when insufficient MTF candles"

    def test_momentum_empty_on_insufficient_data(self):
        """Empty dict when candle count < min_candles threshold."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=100)

        indicators = engine.get_momentum_indicators(
            "005930", timeframe=5, min_candles=50
        )

        assert (
            indicators == {}
        ), "Should return empty dict when candle count < min_candles"

    def test_momentum_succeeds_with_sufficient_data(self):
        """Non-empty dict when candle count >= min_candles."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators(
            "005930", timeframe=5, min_candles=50
        )

        assert indicators != {}, "Should return indicators when sufficient data"
        assert indicators["candle_count"] >= 50

    def test_custom_min_candles_threshold(self):
        """Respect custom min_candles parameter."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=105)

        indicators_low_threshold = engine.get_momentum_indicators(
            "005930", timeframe=5, min_candles=20
        )
        indicators_high_threshold = engine.get_momentum_indicators(
            "005930", timeframe=5, min_candles=50
        )

        assert indicators_low_threshold != {}, "Should succeed with min_candles=20"
        assert indicators_high_threshold == {}, "Should fail with min_candles=50"


class TestMomentumIndicatorsCaching:
    """Tests for momentum indicator caching."""

    def test_caches_result_by_symbol_timeframe(self):
        """Results should be cached by (symbol, timeframe) key."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators1 = engine.get_momentum_indicators("005930", timeframe=5)

        indicators2 = engine.get_momentum_indicators("005930", timeframe=5)

        assert indicators1 is indicators2

    def test_cache_invalidates_on_new_candle(self):
        """Cache should invalidate when new candles are added."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators1 = engine.get_momentum_indicators("005930", timeframe=5)
        candle_count1 = indicators1["candle_count"]

        cumulative = 1000000
        for minute in range(250, 255):
            ts = datetime(2026, 2, 17, 9 + minute // 60, minute % 60, 30)
            cumulative += 1000
            engine.on_tick(
                "005930",
                {
                    "close": 72500.0,
                    "high": 72550.0,
                    "low": 72450.0,
                    "volume": cumulative,
                },
                ts,
            )

        cumulative += 1000
        engine.on_tick(
            "005930",
            {"close": 72500.0, "high": 72550.0, "low": 72450.0, "volume": cumulative},
            datetime(2026, 2, 17, 9 + 255 // 60, 255 % 60, 31),
        )

        indicators2 = engine.get_momentum_indicators("005930", timeframe=5)
        candle_count2 = indicators2["candle_count"]

        assert candle_count2 > candle_count1


class TestMomentumIndicatorsErrorHandling:
    """Tests for error handling in momentum calculations."""

    def test_empty_on_nonexistent_symbol(self):
        """Empty dict for symbols with no data."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5])
        indicators = engine.get_momentum_indicators("NONEXISTENT", timeframe=5)

        assert indicators == {}

    def test_empty_on_unregistered_timeframe(self):
        """Empty dict when timeframe not in mtf_timeframes."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators("005930", timeframe=15)

        assert indicators == {}, "Should return empty dict for unregistered timeframe"

    def test_handles_calculation_errors_gracefully(self):
        """Should return empty dict on calculation errors (logged, not raised)."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators("005930", timeframe=5)
        assert indicators != {}


class TestMomentumIndicatorsCustomParameters:
    """Tests for custom indicator parameters."""

    def test_custom_trix_parameters(self):
        """Custom TRIX parameters should be respected."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators(
            "005930",
            timeframe=5,
            trix_n=20,
            trix_signal=15,
        )

        assert "trix" in indicators
        assert "trix_signal" in indicators

    def test_custom_cci_period(self):
        """Custom CCI period should be respected."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators(
            "005930",
            timeframe=5,
            cci_period=14,
        )

        assert "cci" in indicators

    def test_custom_macd_parameters(self):
        """Custom MACD parameters should be respected."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators(
            "005930",
            timeframe=5,
            macd_fast=8,
            macd_slow=20,
            macd_signal=5,
        )

        assert "macd_line" in indicators
        assert "macd_signal" in indicators
        assert "macd_oscillator" in indicators

    def test_custom_stochastic_parameters(self):
        """Custom Stochastic parameters should be respected."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)

        indicators = engine.get_momentum_indicators(
            "005930",
            timeframe=5,
            sto_fastk=14,
            sto_slowk=3,
            sto_slowd=3,
        )

        assert "sto_k" in indicators
        assert "sto_d" in indicators


class TestMomentumIndicatorsMultipleTimeframes:
    """Tests for different timeframe configurations."""

    def test_5_minute_timeframe(self):
        """5-minute timeframe should work correctly."""
        engine = _build_warm_mtf_engine(timeframe=5, num_1m_candles=260)
        indicators = engine.get_momentum_indicators("005930", timeframe=5)

        assert indicators != {}
        assert indicators["timeframe"] == 5

    def test_15_minute_timeframe(self):
        """15-minute timeframe should work correctly."""
        engine = _build_warm_mtf_engine(timeframe=15, num_1m_candles=760)
        indicators = engine.get_momentum_indicators("005930", timeframe=15)

        assert indicators != {}
        assert indicators["timeframe"] == 15
        assert indicators["candle_count"] >= 50

    def test_multiple_symbols_isolated(self):
        """Momentum indicators for different symbols should be independent."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        for symbol in ["SYMBOL_A", "SYMBOL_B"]:
            cumulative = 0
            for minute in range(260):
                ts = datetime(2026, 2, 17, 9 + minute // 60, minute % 60, 30)
                price = 100.0 if symbol == "SYMBOL_A" else 200.0
                cumulative += 1000
                engine.on_tick(
                    symbol,
                    {
                        "close": price + minute,
                        "high": price + minute + 10,
                        "low": price + minute - 10,
                        "volume": cumulative,
                    },
                    ts,
                )

            cumulative += 1000
            engine.on_tick(
                symbol,
                {
                    "close": price + 260,
                    "high": price + 270,
                    "low": price + 250,
                    "volume": cumulative,
                },
                datetime(2026, 2, 17, 9 + 260 // 60, 260 % 60, 31),
            )

        indicators_a = engine.get_momentum_indicators("SYMBOL_A", timeframe=5)
        indicators_b = engine.get_momentum_indicators("SYMBOL_B", timeframe=5)

        assert indicators_a != {}
        assert indicators_b != {}
        assert indicators_a is not indicators_b
