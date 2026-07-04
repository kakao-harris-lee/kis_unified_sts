"""VR (Volume Ratio) 지표 계산 단위 테스트.

테스트 대상:
  - VolumeRatioCalculator.calculate() - VR 계산
  - self.calc.get_zone() - VR 구간 판별
  - VolumeRatioCalculator.get_ma_trend() - MA 추세 판별
  - VolumeRatioCalculator.calculate_sma() - SMA 계산
  - VolumeRatioCalculator.calculate_rsi() - RSI 계산
  - VolumeRatioCalculator.check_volume_warning() - 거래량 급감 경고
"""


import math

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import RSICalculator
from shared.indicators.volume_ratio import (
    MATrend,
    VolumeRatioCalculator,
    VRSignal,
    VRZone,
)


class TestVolumeRatioCalculator:
    """VR 계산 테스트"""

    def setup_method(self):
        self.calc = VolumeRatioCalculator(period=20)

    def test_vr_basic_equal(self):
        """상승 10일, 하락 10일, 동일 거래량 → VR ≈ 100%"""
        # 교대로 상승/하락: 100, 102, 101, 103, 100, ...
        closes = [100.0]
        for i in range(20):
            if i % 2 == 0:
                closes.append(closes[-1] + 2)
            else:
                closes.append(closes[-1] - 1)
        volumes = [1000] * len(closes)

        result = self.calc.calculate(closes, volumes)

        # 초기 period 구간은 None
        for i in range(20):
            assert result[i] is None

        # 마지막 값은 계산 가능해야 함
        assert result[-1] is not None
        assert result[-1] > 0

    def test_vr_all_up_returns_none(self):
        """모든 날이 상승 → 하락 거래량 0 → VR = None (division by zero 방지)"""
        closes = list(range(100, 122))  # 22개: continuously rising
        volumes = [1000] * 22

        result = self.calc.calculate(closes, volumes)
        # 20번째 인덱스부터 계산 가능하지만 하락일이 없으므로 None
        assert result[20] is None
        assert result[21] is None

    def test_vr_all_down(self):
        """모든 날이 하락 → 상승 거래량 0 → VR = 0%"""
        closes = list(range(200, 178, -1))  # 22개: continuously falling
        volumes = [1000] * 22

        result = self.calc.calculate(closes, volumes)
        # 하락 거래량만 있으므로 numerator = 0, VR = 0%
        assert result[20] is not None
        assert result[20] == pytest.approx(0.0, abs=0.01)

    def test_vr_depression_zone(self):
        """하락 우세 → VR < 75% (침체권)"""
        # 5일 상승(vol=500), 15일 하락(vol=1500)
        closes = [100.0]
        for i in range(20):
            if i < 5:
                closes.append(closes[-1] + 1)  # 상승
            else:
                closes.append(closes[-1] - 1)  # 하락
        volumes = [0] + [500 if i < 5 else 1500 for i in range(20)]

        result = self.calc.calculate(closes, volumes)
        vr = result[-1]

        assert vr is not None
        # 상승 거래량 합 = 500 × 5 = 2500
        # 하락 거래량 합 = 1500 × 15 = 22500
        # VR = 2500 / 22500 × 100 ≈ 11.1%
        assert vr < 75.0

    def test_vr_overheat_zone(self):
        """상승 우세 → VR > 300% (과열권)"""
        # 18일 상승(vol=2000), 2일 하락(vol=200)
        closes = [100.0]
        for i in range(20):
            if i < 18:
                closes.append(closes[-1] + 1)  # 상승
            else:
                closes.append(closes[-1] - 1)  # 하락
        volumes = [0] + [2000 if i < 18 else 200 for i in range(20)]

        result = self.calc.calculate(closes, volumes)
        vr = result[-1]

        assert vr is not None
        # 상승 거래량 합 = 2000 × 18 = 36000
        # 하락 거래량 합 = 200 × 2 = 400
        # VR = 36000 / 400 × 100 = 9000%
        assert vr > 300.0

    def test_vr_with_unchanged_days(self):
        """보합일 거래량은 상승/하락 양쪽에 절반씩 배분"""
        # 10 상승, 5 하락, 5 보합
        closes = [100.0]
        for i in range(20):
            if i < 10:
                closes.append(closes[-1] + 1)
            elif i < 15:
                closes.append(closes[-1] - 1)
            else:
                closes.append(closes[-1])  # 보합
        volumes = [0] + [1000] * 20

        result = self.calc.calculate(closes, volumes)
        vr = result[-1]

        assert vr is not None
        # 상승 vol = 10000, 하락 vol = 5000, 보합 vol = 5000
        # VR = (10000 + 2500) / (5000 + 2500) × 100 = 12500/7500 × 100 ≈ 166.7%
        assert vr == pytest.approx(166.67, rel=0.01)

    def test_vr_insufficient_data(self):
        """데이터 부족 → 모두 None"""
        closes = [100.0, 101.0, 99.0]
        volumes = [1000, 1000, 1000]

        result = self.calc.calculate(closes, volumes)
        assert all(v is None for v in result)

    def test_vr_mismatched_lengths(self):
        """closes와 volumes 길이 불일치 → ValueError"""
        with pytest.raises(ValueError, match="same length"):
            self.calc.calculate([100, 101], [1000])

    def test_vr_period_validation(self):
        """period < 2 → ValueError"""
        with pytest.raises(ValueError, match="period must be >= 2"):
            VolumeRatioCalculator(period=1)


class TestVRZone:
    """VR 구간 판별 테스트"""

    def setup_method(self):
        self.calc = VolumeRatioCalculator(period=20)

    def test_extreme_bottom(self):
        zone = self.calc.get_zone(30.0)
        assert zone is not None
        assert zone.zone == VRZone.EXTREME_BOTTOM
        assert zone.signal == VRSignal.STRONG_BUY

    def test_bottom(self):
        zone = self.calc.get_zone(50.0)
        assert zone is not None
        assert zone.zone == VRZone.BOTTOM
        assert zone.signal == VRSignal.STRONG_BUY

    def test_depression(self):
        zone = self.calc.get_zone(70.0)
        assert zone is not None
        assert zone.zone == VRZone.DEPRESSION
        assert zone.signal == VRSignal.BUY

    def test_normal(self):
        zone = self.calc.get_zone(120.0)
        assert zone is not None
        assert zone.zone == VRZone.NORMAL
        assert zone.signal == VRSignal.NEUTRAL

    def test_overheat(self):
        zone = self.calc.get_zone(350.0)
        assert zone is not None
        assert zone.zone == VRZone.OVERHEAT
        assert zone.signal == VRSignal.SELL

    def test_extreme_overheat(self):
        zone = self.calc.get_zone(500.0)
        assert zone is not None
        assert zone.zone == VRZone.EXTREME_OVERHEAT
        assert zone.signal == VRSignal.STRONG_SELL

    def test_none_input(self):
        assert self.calc.get_zone(None) is None

    def test_zero(self):
        zone = self.calc.get_zone(0.0)
        assert zone is not None
        assert zone.zone == VRZone.EXTREME_BOTTOM


class TestMATrend:
    """MA 추세 판별 테스트"""

    def test_strong_uptrend(self):
        """정배열: close > ma5 > ma20 > ma60"""
        trend = VolumeRatioCalculator.get_ma_trend(
            close=110, ma5=108, ma20=105, ma60=100
        )
        assert trend == MATrend.STRONG_UPTREND

    def test_uptrend(self):
        """close > ma20 > ma60 (ma5 무관)"""
        trend = VolumeRatioCalculator.get_ma_trend(
            close=106, ma5=109, ma20=105, ma60=100
        )
        assert trend == MATrend.UPTREND

    def test_strong_downtrend(self):
        """역배열: close < ma5 < ma20 < ma60"""
        trend = VolumeRatioCalculator.get_ma_trend(
            close=90, ma5=92, ma20=95, ma60=100
        )
        assert trend == MATrend.STRONG_DOWNTREND

    def test_downtrend(self):
        """close < ma20 < ma60"""
        trend = VolumeRatioCalculator.get_ma_trend(
            close=93, ma5=91, ma20=95, ma60=100
        )
        assert trend == MATrend.DOWNTREND

    def test_sideways(self):
        """어느 조건에도 해당 안됨"""
        trend = VolumeRatioCalculator.get_ma_trend(
            close=100, ma5=99, ma20=101, ma60=98
        )
        assert trend == MATrend.SIDEWAYS


class TestSMA:
    """SMA 계산 테스트"""

    def test_sma_basic(self):
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = VolumeRatioCalculator.calculate_sma(closes, period=3)

        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(20.0)  # (10+20+30)/3
        assert result[3] == pytest.approx(30.0)  # (20+30+40)/3
        assert result[4] == pytest.approx(40.0)  # (30+40+50)/3

    def test_sma_insufficient_data(self):
        result = VolumeRatioCalculator.calculate_sma([10.0, 20.0], period=5)
        assert all(v is None for v in result)


class TestRSI:
    """RSI 계산 테스트"""

    def test_rsi_all_gains(self):
        """연속 상승 → RSI = 100"""
        closes = list(range(100, 120))
        result = VolumeRatioCalculator.calculate_rsi(closes, period=14)
        # 마지막 RSI
        rsi = result[-1]
        assert rsi is not None
        assert rsi == pytest.approx(100.0)

    def test_rsi_all_losses(self):
        """연속 하락 → RSI = 0"""
        closes = list(range(200, 180, -1))
        result = VolumeRatioCalculator.calculate_rsi(closes, period=14)
        rsi = result[-1]
        assert rsi is not None
        assert rsi == pytest.approx(0.0, abs=0.1)

    def test_rsi_range(self):
        """RSI는 0~100 범위"""
        np.random.seed(42)
        closes = list(np.cumsum(np.random.randn(100)) + 100)
        result = VolumeRatioCalculator.calculate_rsi(closes, period=14)

        for v in result:
            if v is not None:
                assert 0.0 <= v <= 100.0

    def test_rsi_insufficient_data(self):
        result = VolumeRatioCalculator.calculate_rsi([100, 101, 102], period=14)
        assert all(v is None for v in result)

    def test_rsi_no_duplicate_seed_stutter(self):
        """First two RSI outputs must be distinct Wilder steps, not a duplicated seed.

        Regression for the off-by-one: the loop emitted the SMA seed for both
        result[period] and result[period+1] (making them identical) and never
        folded gains[period] into the Wilder recursion.
        """
        closes = [100.0 + 3.0 * math.sin(i / 2.0) + 0.3 * i for i in range(20)]
        result = VolumeRatioCalculator.calculate_rsi(closes, period=14)

        assert result[14] is not None and result[15] is not None
        assert result[14] != pytest.approx(
            result[15], abs=1e-9
        ), "result[period] and result[period+1] must not be the duplicated seed"

    def test_rsi_matches_canonical_wilder(self):
        """calculate_rsi must equal the canonical Wilder RSI (shared SoT) everywhere.

        Cross-checks against ``momentum.RSICalculator`` (a separate implementation
        of the repo's converged Wilder convention). The off-by-one both duplicated
        the seed and dropped gains[period], so every value from index ``period`` on
        diverged from canonical.
        """
        closes = [100.0 + 3.0 * math.sin(i / 2.0) + 0.3 * i for i in range(40)]
        result = VolumeRatioCalculator.calculate_rsi(closes, period=14)
        canonical = (
            RSICalculator(period=14)
            .calculate(pd.DataFrame({"close": closes}))["rsi"]
            .tolist()
        )

        for i, value in enumerate(result):
            if value is not None:
                assert value == pytest.approx(
                    canonical[i], abs=1e-6
                ), f"RSI diverges from canonical Wilder at index {i}"


class TestVolumeWarning:
    """거래량 급감 경고 테스트"""

    def test_no_warning_normal_volume(self):
        volumes = [1000] * 20
        assert VolumeRatioCalculator.check_volume_warning(volumes) is False

    def test_warning_volume_drop(self):
        # 마지막 5일 거래량이 급감
        volumes = [1000] * 15 + [100] * 5
        assert VolumeRatioCalculator.check_volume_warning(volumes) is True

    def test_insufficient_data(self):
        volumes = [1000] * 5  # < long_window(20)
        assert VolumeRatioCalculator.check_volume_warning(volumes) is False
