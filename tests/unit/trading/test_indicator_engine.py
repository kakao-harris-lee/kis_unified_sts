"""Tests for StreamingIndicatorEngine helpers."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import patch

from services.trading.indicator_engine import StreamingIndicatorEngine


def test_get_recent_candles_returns_ohlcv_dicts():
    engine = StreamingIndicatorEngine()
    symbol = "A01603"

    engine.on_tick(symbol, {"close": 100.0, "high": 101.0, "low": 99.5, "volume": 10}, datetime(2026, 2, 12, 9, 0, 10))
    engine.on_tick(symbol, {"close": 101.0, "high": 101.5, "low": 100.2, "volume": 12}, datetime(2026, 2, 12, 9, 1, 5))
    engine.on_tick(symbol, {"close": 102.0, "high": 102.4, "low": 101.7, "volume": 8}, datetime(2026, 2, 12, 9, 2, 5))

    candles = engine.get_recent_candles(symbol, limit=5)
    assert len(candles) == 2  # completed candles only
    assert set(candles[0].keys()) == {"open", "high", "low", "close", "volume"}


def _build_warm_engine(symbol: str = "005930") -> StreamingIndicatorEngine:
    """Build an engine with 25 candles (warm for bb_period=20).

    Volumes increase linearly (1000, 1010, ..., 1240) so RVOL short > long.
    """
    engine = StreamingIndicatorEngine(bb_period=20, high_period=5, rvol_short=5, rvol_long=20)

    # Generate 25 candles by ticking across minute boundaries
    base_price = 70000.0
    base_volume = 1000
    for minute in range(25):
        ts = datetime(2026, 2, 17, 9, minute, 30)
        price = base_price + minute * 100
        engine.on_tick(
            symbol,
            {
                "close": price,
                "high": price + 50,
                "low": price - 50,
                "volume": base_volume + minute * 10,
            },
            ts,
        )
    # One more tick in minute 25 to finalize candle 24
    engine.on_tick(
        symbol,
        {"close": base_price + 2500, "high": base_price + 2550, "low": base_price + 2450, "volume": 1300},
        datetime(2026, 2, 17, 9, 25, 30),
    )

    assert engine.is_warm(symbol), "Engine should be warm with 25 candles"
    return engine


class TestVolumeIndicators:
    """Tests for VWAP, RVOL, volume_velocity, volume_acceleration, high_N."""

    def test_get_indicators_includes_volume_keys(self):
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        assert "vwap" in indicators
        assert "rvol" in indicators
        assert "volume_velocity" in indicators
        assert "volume_acceleration" in indicators
        assert "high_5" in indicators

    def test_vwap_is_positive(self):
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        assert indicators["vwap"] > 0, "VWAP should be positive when data exists"

    def test_rvol_reflects_rising_volume(self):
        """RVOL > 1.0 when recent volumes are higher than long-term average."""
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        # Volumes increase linearly (1000..1240), so short-window avg > long-window avg
        assert indicators["rvol"] > 1.0, (
            f"RVOL should be > 1.0 for increasing volumes, got {indicators['rvol']:.4f}"
        )

    def test_volume_velocity_is_numeric(self):
        """Volume velocity should be a finite number (not just existence check)."""
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        import math
        assert math.isfinite(indicators["volume_velocity"]), (
            f"volume_velocity should be finite, got {indicators['volume_velocity']}"
        )

    def test_volume_acceleration_is_numeric(self):
        """Volume acceleration should be a finite number."""
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        import math
        assert math.isfinite(indicators["volume_acceleration"]), (
            f"volume_acceleration should be finite, got {indicators['volume_acceleration']}"
        )

    def test_high_n_tracks_recent_highs(self):
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        # high_5 should be the max high of last 5 candles
        candles = engine.get_recent_candles("005930", limit=5)
        expected_high = max(c["high"] for c in candles)
        assert indicators["high_5"] == expected_high

    def test_custom_high_period_value(self):
        """Verify custom high_period produces correct key AND value."""
        engine = StreamingIndicatorEngine(bb_period=20, high_period=3)

        # Build 25 candles with increasing prices
        for minute in range(25):
            ts = datetime(2026, 2, 17, 9, minute, 30)
            engine.on_tick(
                "TEST",
                {"close": 100 + minute, "high": 110 + minute, "low": 90 + minute, "volume": 500},
                ts,
            )
        engine.on_tick(
            "TEST",
            {"close": 125, "high": 135, "low": 115, "volume": 500},
            datetime(2026, 2, 17, 9, 25, 30),
        )

        indicators = engine.get_indicators("TEST")
        assert "high_3" in indicators

        # Verify the actual value matches last 3 candles' max high
        candles = engine.get_recent_candles("TEST", limit=3)
        expected_high = max(c["high"] for c in candles)
        assert indicators["high_3"] == expected_high, (
            f"high_3 should be {expected_high}, got {indicators['high_3']}"
        )

    def test_empty_symbol_returns_empty_dict(self):
        engine = StreamingIndicatorEngine()
        assert engine.get_indicators("NONEXISTENT") == {}

    def test_bb_rsi_still_present(self):
        """Ensure original indicators are not broken."""
        engine = _build_warm_engine()
        indicators = engine.get_indicators("005930")

        assert "bb_lower" in indicators
        assert "bb_middle" in indicators
        assert "bb_upper" in indicators
        assert "rsi" in indicators
        assert indicators["bb_lower"] < indicators["bb_middle"] < indicators["bb_upper"]

    def test_seed_candles_produces_indicators(self):
        """seed_candles() should allow get_indicators() to work (BB/RSI/RVOL/high_N)."""
        engine = StreamingIndicatorEngine(bb_period=20, high_period=5, rvol_short=5, rvol_long=20)
        symbol = "SEED_TEST"

        # Seed 25 historical candles
        candles = []
        for i in range(25):
            candles.append({
                "open": 100.0 + i,
                "high": 110.0 + i,
                "low": 90.0 + i,
                "close": 105.0 + i,
                "volume": 1000 + i * 10,
            })
        engine.seed_candles(symbol, candles)

        assert engine.is_warm(symbol)
        indicators = engine.get_indicators(symbol)

        # BB/RSI should work from seeded candles
        assert "bb_lower" in indicators
        assert "rsi" in indicators
        assert "rvol" in indicators
        assert f"high_5" in indicators

        # VWAP is 0.0 after seeding (no ticks fed to VWAPCalculator)
        assert indicators["vwap"] == 0.0, (
            "VWAP should be 0.0 for seed-only data (no tick-level feed)"
        )

    def test_on_tick_rejects_inf_nan(self):
        """inf/nan close values should be silently dropped."""
        engine = StreamingIndicatorEngine()
        symbol = "BAD"

        engine.on_tick(symbol, {"close": float("inf"), "volume": 100}, datetime(2026, 1, 1, 9, 0, 0))
        engine.on_tick(symbol, {"close": float("nan"), "volume": 100}, datetime(2026, 1, 1, 9, 1, 0))
        engine.on_tick(symbol, {"close": -1.0, "volume": 100}, datetime(2026, 1, 1, 9, 2, 0))

        assert symbol not in engine._accumulators, "Bad ticks should not create accumulators"

    def test_on_tick_clamps_negative_volume(self):
        """Negative volume should be clamped to 0."""
        engine = StreamingIndicatorEngine()
        symbol = "NEGVOL"

        engine.on_tick(symbol, {"close": 100.0, "volume": -50}, datetime(2026, 1, 1, 9, 0, 0))
        engine.on_tick(symbol, {"close": 101.0, "volume": 100}, datetime(2026, 1, 1, 9, 1, 0))

        candles = engine.get_recent_candles(symbol)
        assert len(candles) == 1
        assert candles[0]["volume"] == 0.0, "Negative volume should be clamped to 0"


class TestMomentumDecayEodGuard:
    """Tests for eod_close_enabled config flag."""

    def test_eod_close_enabled_default_true(self):
        from shared.strategy.exit.momentum_decay import MomentumDecayConfig

        config = MomentumDecayConfig()
        assert config.eod_close_enabled is True

    def test_eod_close_disabled(self):
        from shared.strategy.exit.momentum_decay import MomentumDecayConfig

        config = MomentumDecayConfig(eod_close_enabled=False)
        assert config.eod_close_enabled is False

    @patch("shared.strategy.exit.momentum_decay.is_trading_day_kst", return_value=True)
    @patch("shared.strategy.exit.momentum_decay.effective_close_time", return_value=time(15, 15))
    def test_eod_close_triggers_when_enabled(self, _mock_ect, _mock_td):
        """With eod_close_enabled=True on a trading day past EOD time, signal MUST be EOD_CLOSE."""
        from shared.strategy.exit.momentum_decay import MomentumDecayConfig, MomentumDecayExit
        from shared.models.position import Position, PositionSide
        from shared.models.signal import ExitReason

        config = MomentumDecayConfig(
            eod_close_enabled=True,
            stop_loss_pct=-0.05,
            no_profit_days=10,
            max_hold_days=20,
        )
        exit_strategy = MomentumDecayExit(config)

        position = Position(
            id="test-eod-enabled",
            code="005930",
            name="Samsung",
            side=PositionSide.LONG,
            entry_price=70000,
            current_price=70000,
            quantity=10,
            strategy="volume_accumulation",
            entry_time=datetime(2026, 2, 17, 9, 30),
        )

        market_data = {"005930": {"close": 70000}}
        now = datetime(2026, 2, 17, 15, 20)  # After EOD time 15:15

        signal = exit_strategy._check_position(
            position=position,
            market_data=market_data,
            market_state=None,
            now=now,
        )

        assert signal is not None, "EOD close should trigger when enabled on trading day"
        assert signal.reason == ExitReason.EOD_CLOSE

    @patch("shared.strategy.exit.momentum_decay.is_trading_day_kst", return_value=True)
    @patch("shared.strategy.exit.momentum_decay.effective_close_time", return_value=time(15, 15))
    def test_eod_close_skipped_when_disabled(self, _mock_ect, _mock_td):
        """With eod_close_enabled=False, no EOD_CLOSE signal even past EOD time on trading day."""
        from shared.strategy.exit.momentum_decay import MomentumDecayConfig, MomentumDecayExit
        from shared.models.position import Position, PositionSide
        from shared.models.signal import ExitReason

        config = MomentumDecayConfig(
            eod_close_enabled=False,
            stop_loss_pct=-0.05,
            no_profit_days=10,
            max_hold_days=20,
        )
        exit_strategy = MomentumDecayExit(config)

        position = Position(
            id="test-eod-disabled",
            code="005930",
            name="Samsung",
            side=PositionSide.LONG,
            entry_price=70000,
            current_price=70000,
            quantity=10,
            strategy="volume_accumulation",
            entry_time=datetime(2026, 2, 17, 9, 30),
        )

        market_data = {"005930": {"close": 70000}}
        now = datetime(2026, 2, 17, 15, 20)  # After EOD time

        signal = exit_strategy._check_position(
            position=position,
            market_data=market_data,
            market_state=None,
            now=now,
        )

        # Should be None (no exit) or non-EOD reason
        if signal is not None:
            assert signal.reason != ExitReason.EOD_CLOSE, (
                "EOD close should be skipped when eod_close_enabled=False"
            )
