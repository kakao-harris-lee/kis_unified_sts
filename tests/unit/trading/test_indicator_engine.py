"""Tests for StreamingIndicatorEngine helpers."""

from __future__ import annotations

from datetime import UTC, datetime, time
from unittest.mock import patch

from services.trading.indicator_engine import StreamingIndicatorEngine


def test_get_recent_candles_returns_ohlcv_dicts():
    engine = StreamingIndicatorEngine()
    symbol = "A01603"

    # Cumulative volumes: 10, 22, 30 → deltas: 10, 12, 8
    engine.on_tick(symbol, {"close": 100.0, "high": 101.0, "low": 99.5, "volume": 10}, datetime(2026, 2, 12, 9, 0, 10))
    engine.on_tick(symbol, {"close": 101.0, "high": 101.5, "low": 100.2, "volume": 22}, datetime(2026, 2, 12, 9, 1, 5))
    engine.on_tick(symbol, {"close": 102.0, "high": 102.4, "low": 101.7, "volume": 30}, datetime(2026, 2, 12, 9, 2, 5))

    candles = engine.get_recent_candles(symbol, limit=5)
    assert len(candles) == 2  # completed candles only
    assert set(candles[0].keys()) == {"open", "high", "low", "close", "volume"}


def _build_warm_engine(symbol: str = "005930") -> StreamingIndicatorEngine:
    """Build an engine with 25 candles (warm for bb_period=20).

    Volumes increase linearly (1000, 1010, ..., 1240) so RVOL short > long.
    staleness_seconds=0 disables the staleness guard (test uses fixed timestamps).

    on_tick() expects cumulative daily volume (like WebSocket feeds), so we
    send running totals that produce the desired per-candle deltas.
    """
    engine = StreamingIndicatorEngine(bb_period=20, high_period=5, rvol_short=5, rvol_long=20, staleness_seconds=0)

    # Generate 25 candles by ticking across minute boundaries
    base_price = 70000.0
    base_volume = 1000
    cumulative = 0
    for minute in range(25):
        ts = datetime(2026, 2, 17, 9, minute, 30)
        price = base_price + minute * 100
        cumulative += base_volume + minute * 10  # delta = 1000, 1010, ..., 1240
        engine.on_tick(
            symbol,
            {
                "close": price,
                "high": price + 50,
                "low": price - 50,
                "volume": cumulative,
            },
            ts,
        )
    # One more tick in minute 25 to finalize candle 24
    cumulative += 1300
    engine.on_tick(
        symbol,
        {"close": base_price + 2500, "high": base_price + 2550, "low": base_price + 2450, "volume": cumulative},
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
        engine = StreamingIndicatorEngine(bb_period=20, high_period=3, staleness_seconds=0)

        # Build 25 candles with increasing prices (cumulative volumes)
        cumulative = 0
        for minute in range(25):
            ts = datetime(2026, 2, 17, 9, minute, 30)
            cumulative += 500
            engine.on_tick(
                "TEST",
                {"close": 100 + minute, "high": 110 + minute, "low": 90 + minute, "volume": cumulative},
                ts,
            )
        cumulative += 500
        engine.on_tick(
            "TEST",
            {"close": 125, "high": 135, "low": 115, "volume": cumulative},
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
        engine = StreamingIndicatorEngine(bb_period=20, high_period=5, rvol_short=5, rvol_long=20, staleness_seconds=0)
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

        # First tick: negative volume clamped to 0 → cumulative baseline = 0, delta = 0
        engine.on_tick(symbol, {"close": 100.0, "volume": -50}, datetime(2026, 1, 1, 9, 0, 0))
        # Second tick: cumulative 100, prev_cum=0 → delta = 100
        engine.on_tick(symbol, {"close": 101.0, "volume": 100}, datetime(2026, 1, 1, 9, 1, 0))

        candles = engine.get_recent_candles(symbol)
        assert len(candles) == 1
        assert candles[0]["volume"] == 0.0, "Negative volume should be clamped to 0"


class TestCumulativeVolumeDelta:
    """Tests for cumulative daily volume → per-tick delta conversion."""

    def test_cumulative_volume_delta_conversion(self):
        """Cumulative daily volume is converted to per-tick delta."""
        engine = StreamingIndicatorEngine(staleness_seconds=0)
        # Simulate 3 ticks within same minute with cumulative volume
        engine.on_tick("005930", {"close": 100, "high": 101, "low": 99, "volume": 1000}, datetime(2026, 2, 20, 9, 30, 0))
        engine.on_tick("005930", {"close": 101, "high": 102, "low": 100, "volume": 1200}, datetime(2026, 2, 20, 9, 30, 2))
        engine.on_tick("005930", {"close": 102, "high": 103, "low": 101, "volume": 1200}, datetime(2026, 2, 20, 9, 30, 4))  # No new trades
        # Cross minute boundary to finalize candle
        engine.on_tick("005930", {"close": 103, "high": 104, "low": 102, "volume": 1500}, datetime(2026, 2, 20, 9, 31, 0))

        acc = engine._accumulators["005930"]
        candle = acc.candles[0]  # Finalized 09:30 candle
        # Delta: 1000 + (1200-1000) + (1200-1200) = 1000 + 200 + 0 = 1200
        assert candle.volume == 1200, f"Expected 1200, got {candle.volume}"

    def test_volume_reset_new_day(self):
        """Volume reset (new day) is handled correctly."""
        engine = StreamingIndicatorEngine()
        engine._last_cumulative_volume["005930"] = 500000  # Yesterday's final
        engine.on_tick("005930", {"close": 100, "volume": 100}, datetime(2026, 2, 21, 9, 0, 0))
        # volume (100) < prev_cum (500000) → treated as new day, delta = 100
        assert engine._last_cumulative_volume["005930"] == 100

    def test_seed_candles_not_affected(self):
        """seed_candles uses per-candle volume, unaffected by delta conversion."""
        engine = StreamingIndicatorEngine(staleness_seconds=0)
        engine.seed_candles("005930", [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 5000},
            {"open": 100, "high": 102, "low": 98, "close": 101, "volume": 6000},
        ])
        candles = engine._accumulators["005930"].candles
        assert candles[0].volume == 5000  # Per-candle, not accumulated
        assert candles[1].volume == 6000

    def test_seed_clears_cumulative_baseline(self):
        """seed_candles should clear the cumulative baseline for the symbol."""
        engine = StreamingIndicatorEngine()
        engine._last_cumulative_volume["005930"] = 999999
        engine.seed_candles("005930", [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 5000},
        ])
        assert "005930" not in engine._last_cumulative_volume

    def test_remove_symbol_clears_cumulative(self):
        """remove_symbol should clean up _last_cumulative_volume."""
        engine = StreamingIndicatorEngine()
        engine.on_tick("005930", {"close": 100, "volume": 1000}, datetime(2026, 2, 20, 9, 0, 0))
        assert "005930" in engine._last_cumulative_volume

        engine.remove_symbol("005930")
        assert "005930" not in engine._last_cumulative_volume

    def test_multiple_symbols_independent(self):
        """Each symbol tracks cumulative volume independently."""
        engine = StreamingIndicatorEngine()
        engine.on_tick("A", {"close": 100, "volume": 1000}, datetime(2026, 2, 20, 9, 0, 0))
        engine.on_tick("B", {"close": 200, "volume": 5000}, datetime(2026, 2, 20, 9, 0, 0))
        engine.on_tick("A", {"close": 101, "volume": 1100}, datetime(2026, 2, 20, 9, 0, 2))
        engine.on_tick("B", {"close": 201, "volume": 5500}, datetime(2026, 2, 20, 9, 0, 2))

        assert engine._last_cumulative_volume["A"] == 1100
        assert engine._last_cumulative_volume["B"] == 5500

    def test_volume_is_cumulative_false_skips_delta(self):
        """When volume_is_cumulative=False, volume is used as-is (per-tick)."""
        engine = StreamingIndicatorEngine()
        # First tick: per-tick volume, no delta conversion
        engine.on_tick("F01", {"close": 350, "volume": 50, "volume_is_cumulative": False},
                       datetime(2026, 2, 20, 9, 0, 0))
        # Second tick: also per-tick
        engine.on_tick("F01", {"close": 351, "volume": 30, "volume_is_cumulative": False},
                       datetime(2026, 2, 20, 9, 0, 2))
        # Cross minute to finalize
        engine.on_tick("F01", {"close": 352, "volume": 20, "volume_is_cumulative": False},
                       datetime(2026, 2, 20, 9, 1, 0))

        candle = engine._accumulators["F01"].candles[0]
        # Per-tick: 50 + 30 = 80 (no delta subtraction)
        assert candle.volume == 80, f"Expected 80, got {candle.volume}"
        # _last_cumulative_volume should NOT be updated for non-cumulative ticks
        assert "F01" not in engine._last_cumulative_volume

    def test_set_volume_baseline_prevents_inflation(self):
        """set_volume_baseline() prevents first-tick cumulative from inflating candle."""
        engine = StreamingIndicatorEngine()
        # Simulate mid-session addition: symbol already has 500K cumulative volume
        engine.set_volume_baseline("005930", 500000)

        # First tick with cumulative 500100 → delta = 100 (not 500100)
        engine.on_tick("005930", {"close": 70000, "volume": 500100}, datetime(2026, 2, 20, 10, 30, 0))
        # Second tick
        engine.on_tick("005930", {"close": 70050, "volume": 500300}, datetime(2026, 2, 20, 10, 30, 2))
        # Cross minute to finalize
        engine.on_tick("005930", {"close": 70100, "volume": 500500}, datetime(2026, 2, 20, 10, 31, 0))

        candle = engine._accumulators["005930"].candles[0]
        # Delta: (500100-500000) + (500300-500100) = 100 + 200 = 300
        assert candle.volume == 300, f"Expected 300 (not ~500K inflation), got {candle.volume}"

    def test_set_volume_baseline_after_seed(self):
        """Baseline set after seed_candles prevents first real tick inflation."""
        engine = StreamingIndicatorEngine()
        engine.seed_candles("005930", [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 5000},
        ])
        # seed_candles clears baseline; now set it from current WebSocket cache
        engine.set_volume_baseline("005930", 200000)

        # First real tick: delta = 200050 - 200000 = 50 (not 200050)
        engine.on_tick("005930", {"close": 101, "volume": 200050}, datetime(2026, 2, 20, 9, 5, 0))
        # Cross minute
        engine.on_tick("005930", {"close": 102, "volume": 200100}, datetime(2026, 2, 20, 9, 6, 0))

        candle = engine._accumulators["005930"].candles[1]  # candle after seeded one
        assert candle.volume == 50, f"Expected 50, got {candle.volume}"


class TestIndicatorStaleness:
    """Verify staleness guard rejects indicators from symbols with no recent ticks."""

    def _build_stale_engine(self, symbol: str = "STALE", staleness: float = 60.0):
        """Build a warm engine with known tick timestamps for staleness testing."""
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=staleness)
        cumulative = 0
        for minute in range(25):
            cumulative += 500
            engine.on_tick(
                symbol,
                {"close": 100 + minute, "high": 110 + minute, "low": 90 + minute, "volume": cumulative},
                datetime(2026, 2, 17, 9, minute, 30),
            )
        cumulative += 500
        engine.on_tick(
            symbol,
            {"close": 125, "high": 135, "low": 115, "volume": cumulative},
            datetime(2026, 2, 17, 9, 25, 30),
        )
        assert engine.is_warm(symbol)
        return engine

    def test_stale_indicators_return_empty(self):
        """get_indicators should return {} when last tick is older than staleness_seconds."""
        engine = self._build_stale_engine(staleness=60.0)

        # 2 minutes after last tick (> 60s threshold)
        now = datetime(2026, 2, 17, 9, 27, 31)
        result = engine.get_indicators("STALE", now=now)
        assert result == {}, f"Expected empty dict for stale data, got {result}"

    def test_fresh_indicators_returned(self):
        """get_indicators should return values when last tick is recent."""
        engine = self._build_stale_engine(staleness=180.0)

        # 10s after last tick (within 180s threshold)
        now = datetime(2026, 2, 17, 9, 25, 40)
        result = engine.get_indicators("STALE", now=now)
        assert "bb_lower" in result
        assert "rsi" in result

    def test_staleness_disabled_when_zero(self):
        """staleness_seconds=0 should disable the check entirely."""
        engine = self._build_stale_engine(staleness=0)

        # 3 hours after last tick — but staleness=0 disables the check
        now = datetime(2026, 2, 17, 12, 0, 0)
        result = engine.get_indicators("STALE", now=now)
        assert "bb_lower" in result

    def test_last_tick_ts_tracked(self):
        """CandleAccumulator should track last_tick_ts."""
        engine = StreamingIndicatorEngine()
        ts = datetime(2026, 2, 17, 9, 5, 30)
        engine.on_tick("TEST", {"close": 100.0, "volume": 100}, ts)  # cumulative=100, delta=100

        acc = engine._accumulators["TEST"]
        assert acc.last_tick_ts == ts


class TestRemoveSymbol:
    """Verify remove_symbol cleans up all state for evicted symbols."""

    def test_remove_symbol_clears_accumulator(self):
        engine = _build_warm_engine("005930")
        assert "005930" in engine._accumulators

        engine.remove_symbol("005930")

        assert "005930" not in engine._accumulators
        assert "005930" not in engine._warm_logged

    def test_remove_symbol_clears_volume_state(self):
        engine = _build_warm_engine("005930")
        # Verify VWAP/VolumeAcceleration have data
        indicators = engine.get_indicators("005930")
        assert "vwap" in indicators

        engine.remove_symbol("005930")

        # After removal, getting indicators should return empty
        assert engine.get_indicators("005930") == {}

    def test_remove_nonexistent_symbol_no_error(self):
        engine = StreamingIndicatorEngine()
        engine.remove_symbol("NOPE")  # should not raise

    def test_remove_then_readd_fresh(self):
        """After removing and re-adding, old stale data should not persist."""
        engine = _build_warm_engine("005930")
        old_indicators = engine.get_indicators("005930")
        assert "bb_lower" in old_indicators

        engine.remove_symbol("005930")

        # Re-add with different prices (staleness=0, so no time issues)
        # Cumulative volumes: 2000, 4000, ..., 50000, 52000
        for minute in range(25):
            engine.on_tick(
                "005930",
                {"close": 50000 + minute * 200, "high": 50100 + minute * 200,
                 "low": 49900 + minute * 200, "volume": 2000 * (minute + 1)},
                datetime(2026, 2, 17, 10, minute, 30),
            )
        engine.on_tick(
            "005930",
            {"close": 55000, "high": 55100, "low": 54900, "volume": 2000 * 26},
            datetime(2026, 2, 17, 10, 25, 30),
        )

        new_indicators = engine.get_indicators("005930")
        assert "bb_lower" in new_indicators
        # New BB middle should be around 50000-55000, very different from old ~70000-72000
        assert new_indicators["bb_middle"] < 56000


class TestMarketMfiActiveSymbols:
    """Verify get_market_mfi respects active_symbols filter."""

    def test_mfi_filters_by_active_symbols(self):
        """Only active symbols should be included in market MFI."""
        engine = _build_warm_engine("005930")

        # Add another warm symbol (cumulative volumes)
        # Note: "000660" is a different symbol from "005930", so its
        # cumulative baseline starts at 0 independently.
        cumulative = 0
        for minute in range(25):
            cumulative += 3000 + minute * 10
            engine.on_tick(
                "000660",
                {"close": 200000 + minute * 100, "high": 200100 + minute * 100,
                 "low": 199900 + minute * 100, "volume": cumulative},
                datetime(2026, 2, 17, 9, minute, 30),
            )
        cumulative += 3300
        engine.on_tick(
            "000660",
            {"close": 202500, "high": 202600, "low": 202400, "volume": cumulative},
            datetime(2026, 2, 17, 9, 25, 30),
        )

        # MFI with all symbols
        mfi_all = engine.get_market_mfi()
        assert mfi_all is not None

        # MFI with only one symbol
        mfi_one = engine.get_market_mfi(active_symbols={"005930"})
        assert mfi_one is not None

        # MFI with no matching symbols
        mfi_none = engine.get_market_mfi(active_symbols={"NONEXIST"})
        assert mfi_none is None

    def test_mfi_none_param_uses_all(self):
        """active_symbols=None should include all symbols (backward compatible)."""
        engine = _build_warm_engine("005930")
        mfi = engine.get_market_mfi(active_symbols=None)
        assert mfi is not None


class TestMarketLatestTickTs:
    """get_market_latest_tick_ts — candle-freshness marker for regime MFI (#460)."""

    def test_returns_max_across_symbols_utc_aware(self):
        engine = _build_warm_engine("005930")
        # second symbol with a strictly newer last tick
        engine.on_tick(
            "000660",
            {"close": 200000, "high": 200100, "low": 199900, "volume": 100},
            datetime(2026, 2, 17, 11, 0, 0),
        )

        ts = engine.get_market_latest_tick_ts()

        assert ts is not None
        assert ts.tzinfo is not None  # naive inputs normalized to UTC-aware
        assert ts == datetime(2026, 2, 17, 11, 0, 0, tzinfo=UTC)

    def test_respects_active_symbols_filter(self):
        engine = _build_warm_engine("005930")
        engine.on_tick(
            "000660",
            {"close": 200000, "high": 200100, "low": 199900, "volume": 100},
            datetime(2026, 2, 17, 11, 0, 0),
        )

        only_old = engine.get_market_latest_tick_ts(active_symbols={"005930"})
        assert only_old is not None
        assert only_old < datetime(2026, 2, 17, 11, 0, 0, tzinfo=UTC)

        assert engine.get_market_latest_tick_ts(active_symbols={"NONEXIST"}) is None

    def test_returns_none_without_ticks(self):
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
        assert engine.get_market_latest_tick_ts() is None


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
