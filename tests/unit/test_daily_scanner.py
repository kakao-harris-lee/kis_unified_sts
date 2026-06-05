"""Unit tests for services/daily_scanner.py."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

import pytest

from services.daily_scanner import (
    DailyBar,
    DailyScanner,
    DailyScannerConfig,
    _atr,
    _rsi,
    _sma,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bars(
    closes: list[float],
    volumes: list[int] | None = None,
    *,
    high_delta: float = 1.0,
    low_delta: float = 1.0,
) -> list[DailyBar]:
    """Build a list of DailyBar from close prices and optional volumes.

    Args:
        closes: Close prices (oldest → newest).
        volumes: Matching volumes. Defaults to 1_000_000 per bar.
        high_delta: Each bar's high = close + high_delta.
        low_delta: Each bar's low = close - low_delta.

    Returns:
        List of DailyBar objects.
    """
    if volumes is None:
        volumes = [1_000_000] * len(closes)

    assert len(closes) == len(volumes), "closes and volumes must have the same length"

    return [
        DailyBar(
            code="TEST",
            date=date(2026, 1, i + 1),
            open=c,
            high=c + high_delta,
            low=max(c - low_delta, 0.01),
            close=c,
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestSmaHelper:
    def test_basic(self):
        assert _sma([1.0, 2.0, 3.0, 4.0, 5.0], 3) == pytest.approx(4.0)

    def test_insufficient_data_returns_none(self):
        assert _sma([1.0, 2.0], 5) is None

    def test_exact_period(self):
        assert _sma([10.0, 20.0], 2) == pytest.approx(15.0)


class TestRsiHelper:
    def test_all_gains_returns_100(self):
        # Steadily rising prices → all gains, no losses → RSI = 100
        closes = [float(i) for i in range(1, 17)]  # 16 values → period=14, needs 15
        result = _rsi(closes, 14)
        assert result == pytest.approx(100.0)

    def test_insufficient_data_returns_none(self):
        assert _rsi([1.0] * 5, 14) is None

    def test_neutral_range(self):
        # Alternating +1 / -1 → RS = 1 → RSI = 50
        closes = []
        v = 100.0
        closes.append(v)
        for i in range(15):
            v = v + 1.0 if i % 2 == 0 else v - 1.0
            closes.append(v)
        result = _rsi(closes, 14)
        assert result is not None
        assert 0.0 <= result <= 100.0


class TestAtrHelper:
    def test_constant_bars_returns_range(self):
        # All bars with high=close+2, low=close-2 → TR=4 always
        bars = _make_bars([100.0] * 16, high_delta=2.0, low_delta=2.0)
        result = _atr(bars, 14)
        assert result == pytest.approx(4.0)

    def test_insufficient_data_returns_none(self):
        bars = _make_bars([100.0] * 5)
        assert _atr(bars, 14) is None


# ---------------------------------------------------------------------------
# TrendPullback filter tests
# ---------------------------------------------------------------------------


class TestTrendPullbackFilter:
    def _scanner(self) -> DailyScanner:
        cfg = DailyScannerConfig(
            tp_sma_period=5,
            tp_rsi_period=5,
            tp_rsi_max=45.0,
            tp_trend_deviation_pct=5.0,
            tp_min_volume_20d=100_000,
        )
        return DailyScanner(cfg)

    def test_passes_uptrend_pullback(self):
        """Close above SMA but RSI below max — should pass.

        Series: sharp rise then pullback then partial recovery.
        RSI(5) ≈ 33 (pullback), SMA(5) ≈ 105.2, close = 106 > SMA.
        """
        scanner = self._scanner()
        # Rising phase builds up SMA, then a pullback lowers RSI below 45,
        # and the last bar recovers enough to stay above SMA(5).
        closes = [90.0, 95.0, 100.0, 105.0, 110.0, 108.0, 106.0, 104.0, 102.0, 106.0]
        bars = _make_bars(closes, [500_000] * len(closes))
        result = scanner.filter_trend_pullback("TEST", bars)
        assert result is True

    def test_rejects_downtrend(self):
        """Close below SMA — should reject."""
        scanner = self._scanner()
        # Steadily falling prices: close will be below SMA(5)
        closes = [110.0, 108.0, 106.0, 104.0, 102.0, 100.0, 98.0]
        bars = _make_bars(closes, [500_000] * len(closes))
        result = scanner.filter_trend_pullback("TEST", bars)
        assert result is False

    def test_rejects_overbought(self):
        """RSI above tp_rsi_max — should reject."""
        scanner = self._scanner()
        # Steadily rising prices → RSI near 100
        closes = [float(100 + i * 2) for i in range(10)]
        bars = _make_bars(closes, [500_000] * len(closes))
        result = scanner.filter_trend_pullback("TEST", bars)
        assert result is False

    def test_insufficient_data(self):
        """Fewer bars than required — should reject."""
        scanner = self._scanner()
        bars = _make_bars([100.0, 101.0], [500_000, 500_000])
        result = scanner.filter_trend_pullback("TEST", bars)
        assert result is False

    def test_rejects_low_volume(self):
        """Average volume below minimum — should reject."""
        scanner = self._scanner()
        closes = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 108.5]
        bars = _make_bars(closes, [10_000] * len(closes))  # far below 100_000 min
        result = scanner.filter_trend_pullback("TEST", bars)
        assert result is False


# ---------------------------------------------------------------------------
# MomentumBreakout filter tests
# ---------------------------------------------------------------------------


class TestMomentumBreakoutFilter:
    def _scanner(self) -> DailyScanner:
        cfg = DailyScannerConfig(
            mb_high_period=5,
            mb_proximity_pct=5.0,
            mb_volume_trend_ratio=1.2,
            mb_max_extension_pct=15.0,
        )
        return DailyScanner(cfg)

    def test_passes_near_high_volume_increasing(self):
        """Close near N-day high and short-term vol > long-term vol×ratio."""
        scanner = self._scanner()
        # 20 bars of base then 5 bars near the high
        base_closes = [100.0] * 20
        near_high_closes = [
            100.0,
            100.5,
            101.0,
            101.5,
            102.0,
        ]  # high_n = 103 (from high=close+1)
        closes = base_closes + near_high_closes
        # Last 5 bars have higher volume than base
        base_vols = [500_000] * 20
        surge_vols = [1_200_000] * 5
        volumes = base_vols + surge_vols
        bars = _make_bars(closes, volumes)
        result = scanner.filter_momentum_breakout("TEST", bars)
        assert result is True

    def test_rejects_far_from_high(self):
        """Close far below N-day high — should reject."""
        scanner = self._scanner()
        # high_n will be around 120, current close = 100 → ~17% below
        closes = [100.0] * 15 + [120.0, 100.0, 100.0, 100.0, 100.0]
        volumes = [1_200_000] * len(closes)
        bars = _make_bars(closes, volumes)
        result = scanner.filter_momentum_breakout("TEST", bars)
        assert result is False

    def test_rejects_overextended(self):
        """Close significantly above N-day high — overextended, should reject."""
        scanner = self._scanner()
        # All bars at 100, last close = 120 (20% above high_n=101 with delta=1)
        closes = [100.0] * 19 + [120.0]
        volumes = [1_500_000] * len(closes)
        bars = _make_bars(closes, volumes, high_delta=1.0, low_delta=1.0)
        result = scanner.filter_momentum_breakout("TEST", bars)
        assert result is False

    def test_rejects_low_volume_trend(self):
        """Short-term volume not above threshold × long-term volume."""
        scanner = self._scanner()
        # Uniform volume across all bars → vol_ma5 == vol_ma20 → ratio=1.0 < 1.2
        closes = [98.0, 99.0, 100.0, 101.0, 102.0] * 4 + [
            101.5,
            101.6,
            101.7,
            101.8,
            102.0,
        ]
        volumes = [600_000] * len(closes)
        bars = _make_bars(closes, volumes)
        result = scanner.filter_momentum_breakout("TEST", bars)
        assert result is False

    def test_insufficient_data(self):
        """Fewer bars than mb_high_period — should reject."""
        scanner = self._scanner()
        bars = _make_bars([100.0] * 3, [500_000] * 3)
        result = scanner.filter_momentum_breakout("TEST", bars)
        assert result is False


# ---------------------------------------------------------------------------
# MinimumEdge filter tests
# ---------------------------------------------------------------------------


class TestMinimumEdge:
    def _scanner(self) -> DailyScanner:
        cfg = DailyScannerConfig(
            me_atr_period=5,
            me_round_trip_cost=0.005,
            me_min_atr_cost_ratio=2.0,
            max_stale_trading_days=9999,
        )
        return DailyScanner(cfg)

    def test_passes_high_atr(self):
        """ATR well above threshold — should pass."""
        scanner = self._scanner()
        # close=100, high=105, low=95 → TR≈10 → ATR=10 → atr_pct=10%
        # required = 2.0 × 0.5% = 1.0%
        bars = _make_bars([100.0] * 8, high_delta=5.0, low_delta=5.0)
        result = scanner.check_minimum_edge("TEST", bars)
        assert result is True

    def test_rejects_low_atr(self):
        """ATR below threshold — should reject."""
        scanner = self._scanner()
        # close=100, high=100.1, low=99.9 → TR≈0.2 → atr_pct=0.2%
        # required = 2.0 × 0.5% = 1.0%
        bars = _make_bars([100.0] * 8, high_delta=0.1, low_delta=0.1)
        result = scanner.check_minimum_edge("TEST", bars)
        assert result is False

    def test_insufficient_data(self):
        """Fewer bars than period+1 — should reject."""
        scanner = self._scanner()
        bars = _make_bars([100.0] * 3)
        result = scanner.check_minimum_edge("TEST", bars)
        assert result is False


# ---------------------------------------------------------------------------
# Daily freshness guard tests
# ---------------------------------------------------------------------------


class TestDailyFreshness:
    def test_accepts_latest_expected_trading_day(self):
        scanner = DailyScanner(DailyScannerConfig(max_stale_trading_days=0))
        bars = _make_bars([100.0, 101.0])
        bars[-1].date = date(2026, 5, 15)

        assert scanner.check_daily_freshness(
            "TEST",
            bars,
            expected_latest=date(2026, 5, 15),
        )

    def test_rejects_stale_trading_day_lag(self):
        scanner = DailyScanner(DailyScannerConfig(max_stale_trading_days=1))
        bars = _make_bars([100.0, 101.0])
        bars[-1].date = date(2026, 5, 13)

        assert not scanner.check_daily_freshness(
            "TEST",
            bars,
            expected_latest=date(2026, 5, 15),
        )


# ---------------------------------------------------------------------------
# scan_universe integration test (mocked _load_daily_bars)
# ---------------------------------------------------------------------------


class TestScanAll:
    class FakeTradeTrendRanker:
        def summary(self):
            return {"enabled": True, "status": "loaded"}

        def rank_watchlists(self, watchlists):
            ranked = {name: list(reversed(codes)) for name, codes in watchlists.items()}
            return (
                ranked,
                {
                    "TP002": {
                        "trade_trend_priority": {
                            "score": 1.0,
                            "matched_sector": "semiconductor",
                        }
                    }
                },
                {"enabled": True, "status": "loaded"},
            )

    def test_scan_returns_watchlist(self):
        """scan_universe routes codes into the correct lists."""
        # Use relaxed config so our synthetic bars pass filters
        cfg = DailyScannerConfig(
            tp_sma_period=5,
            tp_rsi_period=5,
            tp_rsi_max=45.0,
            tp_trend_deviation_pct=5.0,
            tp_min_volume_20d=100_000,
            mb_high_period=5,
            mb_proximity_pct=5.0,
            mb_volume_trend_ratio=1.2,
            mb_max_extension_pct=15.0,
            me_atr_period=5,
            me_round_trip_cost=0.005,
            me_min_atr_cost_ratio=2.0,
        )
        scanner = DailyScanner(cfg)

        # Trend-pullback bars: rising then small dip, high volume, decent ATR
        tp_closes = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 108.5]
        tp_bars = _make_bars(
            tp_closes, [500_000] * len(tp_closes), high_delta=5.0, low_delta=5.0
        )

        # Momentum-breakout bars: near N-day high, volume surge on last 5 bars
        mb_base = [100.0] * 10
        mb_near = [100.0, 100.5, 101.0, 101.5, 102.0]
        mb_closes = mb_base + mb_near
        mb_vols = [500_000] * 10 + [1_200_000] * 5
        mb_bars = _make_bars(mb_closes, mb_vols, high_delta=5.0, low_delta=5.0)

        # Code that should fail minimum edge (tiny ATR)
        bad_bars = _make_bars(
            [100.0] * 10, [500_000] * 10, high_delta=0.05, low_delta=0.05
        )

        side_effect_map = {
            "TP001": tp_bars,
            "MB001": mb_bars,
            "BAD001": bad_bars,
            "EMPTY001": [],
        }

        with patch.object(
            scanner,
            "_load_daily_bars",
            side_effect=lambda code, **_: side_effect_map.get(code, []),
        ):
            result = scanner.scan_universe(["TP001", "MB001", "BAD001", "EMPTY001"])

        assert "trend_pullback" in result
        assert "momentum_breakout" in result

        # BAD001 and EMPTY001 should be filtered out
        assert "BAD001" not in result["trend_pullback"]
        assert "BAD001" not in result["momentum_breakout"]
        assert "EMPTY001" not in result["trend_pullback"]
        assert "EMPTY001" not in result["momentum_breakout"]

    def test_scan_orders_watchlist_with_trade_trend_priority_metadata(self):
        cfg = DailyScannerConfig(
            tp_sma_period=5,
            tp_rsi_period=5,
            tp_rsi_max=45.0,
            tp_trend_deviation_pct=5.0,
            tp_min_volume_20d=100_000,
            me_atr_period=5,
            me_round_trip_cost=0.005,
            me_min_atr_cost_ratio=2.0,
            max_stale_trading_days=9999,
        )
        scanner = DailyScanner(cfg)
        scanner._trade_trend_ranker = self.FakeTradeTrendRanker()
        tp_bars = _make_bars(
            [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 108.5],
            [500_000] * 7,
            high_delta=5.0,
            low_delta=5.0,
        )

        with (
            patch.object(scanner, "_load_daily_bars", return_value=tp_bars),
            patch.object(scanner, "check_daily_freshness", return_value=True),
            patch.object(scanner, "check_minimum_edge", return_value=True),
            patch.object(scanner, "filter_trend_pullback", return_value=True),
            patch.object(scanner, "filter_momentum_breakout", return_value=False),
        ):
            result = scanner.scan_universe(["TP001", "TP002"])

        assert result["trend_pullback"][:2] == ["TP002", "TP001"]
        assert (
            scanner._last_watchlist_metadata["TP002"]["trade_trend_priority"][
                "matched_sector"
            ]
            == "semiconductor"
        )

    def test_scan_respects_max_watchlist_size(self):
        """Results are capped at max_watchlist_size."""
        cfg = DailyScannerConfig(
            tp_sma_period=5,
            tp_rsi_period=5,
            tp_rsi_max=45.0,
            tp_trend_deviation_pct=5.0,
            tp_min_volume_20d=100_000,
            me_atr_period=5,
            me_round_trip_cost=0.005,
            me_min_atr_cost_ratio=2.0,
            max_stale_trading_days=9999,
            max_watchlist_size=2,
        )
        scanner = DailyScanner(cfg)

        tp_closes = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 108.5]
        tp_bars = _make_bars(
            tp_closes, [500_000] * len(tp_closes), high_delta=5.0, low_delta=5.0
        )

        codes = [f"CODE{i:03d}" for i in range(10)]

        with patch.object(scanner, "_load_daily_bars", return_value=tp_bars):
            result = scanner.scan_universe(codes)

        assert len(result["trend_pullback"]) <= 2

    def test_scan_and_publish_calls_redis(self):
        """scan_and_publish writes to Redis without error."""
        cfg = DailyScannerConfig(
            tp_sma_period=5,
            tp_rsi_period=5,
            tp_rsi_max=45.0,
            tp_trend_deviation_pct=5.0,
            tp_min_volume_20d=100_000,
            me_atr_period=5,
            me_round_trip_cost=0.005,
            me_min_atr_cost_ratio=2.0,
            max_stale_trading_days=9999,
        )
        scanner = DailyScanner(cfg)
        tp_bars = _make_bars(
            [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 108.5],
            [500_000] * 7,
            high_delta=5.0,
            low_delta=5.0,
        )

        with (
            patch.object(scanner, "_load_daily_bars", return_value=tp_bars),
            patch("services.daily_scanner.RedisClient") as mock_redis_cls,
        ):
            mock_redis = mock_redis_cls.get_client.return_value
            result = scanner.scan_and_publish(["CODE001"])

        assert isinstance(result, dict)
        assert "trend_pullback" in result
        assert "momentum_breakout" in result
        mock_redis.set.assert_called_once()
        payload = json.loads(mock_redis.set.call_args.args[1])
        assert "sources" in payload
        assert "trade_trend_priority" in payload["sources"]
