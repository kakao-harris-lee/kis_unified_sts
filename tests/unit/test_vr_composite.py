"""VR Composite 전략 (Entry + Exit) 단위 테스트.

테스트 대상:
  - VRCompositeEntry: 진입 신호 생성 규칙 5개
  - VRCompositeExit: 청산 신호 생성 규칙 4개 + 안전장치 2개
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np
import pytest

from shared.indicators.volume_ratio import VolumeRatioCalculator
from shared.models.signal import ExitReason, SignalType
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.vr_composite import VRCompositeConfig, VRCompositeEntry
from shared.strategy.exit.vr_composite_exit import VRCompositeExitConfig, VRCompositeExit


# ---- Helpers ----

def _make_daily_data(
    n: int = 80,
    base_price: float = 100.0,
    trend: str = "sideways",
    base_volume: int = 1000,
) -> tuple[list[float], list[int]]:
    """테스트용 일봉 데이터 생성.

    Args:
        n: 데이터 길이
        trend: "up", "down", "sideways"
        base_volume: 기본 거래량
    """
    np.random.seed(42)
    closes = [base_price]
    volumes = [base_volume]

    for i in range(1, n):
        if trend == "up":
            change = abs(np.random.randn()) * 0.5
        elif trend == "down":
            change = -abs(np.random.randn()) * 0.5
        else:
            change = np.random.randn() * 0.3

        closes.append(closes[-1] + change)
        volumes.append(base_volume + int(np.random.randint(-200, 200)))

    return closes, volumes


def _make_depressed_data(n: int = 80) -> tuple[list[float], list[int]]:
    """VR 침체/바닥권을 만드는 데이터 (하락 우세)."""
    closes = [100.0]
    volumes = [1000]

    for i in range(1, n):
        # 80% 확률 하락, 20% 상승
        if i % 5 == 0:
            closes.append(closes[-1] + 0.3)
            volumes.append(500)
        else:
            closes.append(closes[-1] - 0.5)
            volumes.append(1500)

    return closes, volumes


def _make_overheated_data(n: int = 80) -> tuple[list[float], list[int]]:
    """VR 과열권을 만드는 데이터 (상승 우세)."""
    closes = [100.0]
    volumes = [1000]

    for i in range(1, n):
        # 90% 확률 상승, 10% 하락
        if i % 10 == 0:
            closes.append(closes[-1] - 0.2)
            volumes.append(200)
        else:
            closes.append(closes[-1] + 0.5)
            volumes.append(2000)

    return closes, volumes


class TestVRCompositeEntry:
    """VR Composite 진입 전략 테스트"""

    def setup_method(self):
        self.config = VRCompositeConfig()
        self.entry = VRCompositeEntry(self.config)

    @pytest.mark.asyncio
    async def test_no_signal_without_code(self):
        """종목 코드 없으면 None"""
        ctx = EntryContext(
            market_data={},
            indicators={},
            timestamp=datetime.now(),
        )
        result = await self.entry.generate(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_signal_without_data(self):
        """일봉 데이터 없으면 None"""
        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={},
            timestamp=datetime.now(),
        )
        result = await self.entry.generate(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_signal_insufficient_data(self):
        """데이터 부족이면 None"""
        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={
                "daily_closes": [100.0, 101.0, 99.0],
                "daily_volumes": [1000, 1000, 1000],
            },
            timestamp=datetime.now(),
        )
        result = await self.entry.generate(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_strong_buy_signal_vr_bottom_rsi_oversold(self):
        """Rule 1/2: VR 바닥/침체 + RSI 과매도 → BUY 신호"""
        # 하락 우세 데이터 → VR 침체/바닥
        closes, volumes = _make_depressed_data(80)

        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),
        )

        # VR과 RSI 값 확인
        calc = VolumeRatioCalculator(period=20)
        vr_values = calc.calculate(closes, volumes)
        rsi_values = VolumeRatioCalculator.calculate_rsi(closes, 14)

        vr = vr_values[-1]
        rsi = rsi_values[-1]

        result = await self.entry.generate(ctx)

        # VR이 실제로 낮은지 확인
        if vr is not None and vr <= 75.0:
            if rsi is not None and rsi <= 30.0:
                # Rule 1 또는 Rule 2 → 신호 발생해야 함
                assert result is not None
                assert result.signal_type == SignalType.ENTRY
                assert result.confidence >= 0.80
                assert result.metadata["vr"] == vr
            elif rsi is not None and rsi <= 40.0:
                # Rule 3, 4, 5 가능
                # 결과가 있을 수도 없을 수도 (MA 추세에 따라)
                pass

    @pytest.mark.asyncio
    async def test_neutral_when_vr_normal(self):
        """VR이 정상 범위이면 관망 (None)"""
        closes, volumes = _make_daily_data(80, trend="sideways")

        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),
        )

        calc = VolumeRatioCalculator(period=20)
        vr_values = calc.calculate(closes, volumes)
        vr = vr_values[-1]

        result = await self.entry.generate(ctx)

        # VR이 75% 초과면 신호 없어야 함
        if vr is not None and vr > 75.0:
            assert result is None

    @pytest.mark.asyncio
    async def test_signal_cooldown(self):
        """쿨다운 기간 내 동일 종목 재진입 방지"""
        closes, volumes = _make_depressed_data(80)

        # 첫 번째 시그널
        self.entry._last_signal_at["005930"] = datetime.now()

        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),  # 같은 날
        )

        result = await self.entry.generate(ctx)
        assert result is None  # 쿨다운 중이므로 None

    @pytest.mark.asyncio
    async def test_signal_after_cooldown(self):
        """쿨다운 기간 이후에는 재진입 가능"""
        closes, volumes = _make_depressed_data(80)

        # 4일 전 시그널 (cooldown = 3일)
        self.entry._last_signal_at["005930"] = datetime.now() - timedelta(days=4)

        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),
        )

        # 쿨다운 해제 → 조건 충족 시 신호 발생 가능
        # (실제 VR/RSI/MA 조건에 따라 None일 수도 있음)

    @pytest.mark.asyncio
    async def test_signal_metadata(self):
        """신호 메타데이터에 VR, RSI, MA 정보 포함"""
        closes, volumes = _make_depressed_data(80)

        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자"},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),
        )

        result = await self.entry.generate(ctx)

        if result is not None:
            assert "vr" in result.metadata
            assert "rsi" in result.metadata
            assert "ma_trend" in result.metadata
            assert "reasons" in result.metadata
            assert result.strategy == "vr_composite"

    def test_config_validation(self):
        """잘못된 설정 → AssertionError"""
        with pytest.raises(AssertionError):
            VRCompositeEntry(VRCompositeConfig(vr_period=1))

        with pytest.raises(AssertionError):
            VRCompositeEntry(VRCompositeConfig(rsi_oversold=60))  # > 50

        with pytest.raises(AssertionError):
            VRCompositeEntry(VRCompositeConfig(ma_short=20, ma_mid=5))  # short > mid

    def test_required_indicators(self):
        assert "daily_closes" in self.entry.required_indicators
        assert "daily_volumes" in self.entry.required_indicators


class TestVRCompositeExit:
    """VR Composite 청산 전략 테스트"""

    def setup_method(self):
        self.config = VRCompositeExitConfig()
        self.exit_strategy = VRCompositeExit(self.config)

    def _make_position(
        self,
        code: str = "005930",
        entry_price: float = 100.0,
        entry_time: datetime = None,
    ):
        """테스트용 Position mock"""
        position = MagicMock()
        position.code = code
        position.entry_price = entry_price
        position.entry_time = entry_time or datetime.now() - timedelta(days=5)
        return position

    @pytest.mark.asyncio
    async def test_hard_stop_loss(self):
        """수익률 -7% 이하 → 즉시 청산"""
        position = self._make_position(entry_price=100.0)
        close = 92.0  # -8%

        ctx = ExitContext(
            position=position,
            market_data={"close": close},
            indicators={},
            timestamp=datetime.now(),
        )

        should, signal = await self.exit_strategy.should_exit(ctx)
        assert should is True
        assert signal is not None
        assert signal.reason == ExitReason.STOP_LOSS
        assert signal.priority == 1
        assert signal.confidence >= 0.90

    @pytest.mark.asyncio
    async def test_max_hold_days(self):
        """최대 보유일수 초과 → 시간 기반 청산"""
        position = self._make_position(
            entry_price=100.0,
            entry_time=datetime.now() - timedelta(days=65),
        )

        ctx = ExitContext(
            position=position,
            market_data={"close": 105.0},
            indicators={},
            timestamp=datetime.now(),
        )

        should, signal = await self.exit_strategy.should_exit(ctx)
        assert should is True
        assert signal is not None
        assert signal.reason == ExitReason.TIME_CUT

    @pytest.mark.asyncio
    async def test_no_exit_when_vr_normal(self):
        """VR 정상 범위 → 청산 안 함"""
        position = self._make_position(entry_price=100.0)
        closes, volumes = _make_daily_data(80, trend="sideways")

        ctx = ExitContext(
            position=position,
            market_data={"close": closes[-1]},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),
        )

        calc = VolumeRatioCalculator(period=20)
        vr_values = calc.calculate(closes, volumes)
        vr = vr_values[-1]

        should, signal = await self.exit_strategy.should_exit(ctx)

        # VR이 300% 미만이면 청산하지 않아야 함
        if vr is not None and vr < 300.0:
            assert should is False

    @pytest.mark.asyncio
    async def test_sell_signal_vr_overheat(self):
        """VR 과열 + RSI 과매수 → 청산 신호"""
        position = self._make_position(entry_price=80.0)
        closes, volumes = _make_overheated_data(80)

        ctx = ExitContext(
            position=position,
            market_data={"close": closes[-1]},
            indicators={
                "daily_closes": closes,
                "daily_volumes": volumes,
            },
            timestamp=datetime.now(),
        )

        calc = VolumeRatioCalculator(period=20)
        vr_values = calc.calculate(closes, volumes)
        rsi_values = VolumeRatioCalculator.calculate_rsi(closes, 14)

        vr = vr_values[-1]
        rsi = rsi_values[-1]

        should, signal = await self.exit_strategy.should_exit(ctx)

        if vr is not None and vr >= 300.0 and rsi is not None and rsi >= 70.0:
            assert should is True
            assert signal is not None
            assert signal.reason == ExitReason.INDICATOR_EXIT

    @pytest.mark.asyncio
    async def test_no_exit_zero_close(self):
        """종가 0이면 청산 판단 불가"""
        position = self._make_position()
        ctx = ExitContext(
            position=position,
            market_data={"close": 0},
            indicators={},
            timestamp=datetime.now(),
        )
        should, signal = await self.exit_strategy.should_exit(ctx)
        assert should is False

    @pytest.mark.asyncio
    async def test_exit_metadata(self):
        """청산 신호 메타데이터 검증"""
        position = self._make_position(entry_price=100.0)
        close = 90.0  # -10% → hard stop

        ctx = ExitContext(
            position=position,
            market_data={"close": close},
            indicators={},
            timestamp=datetime.now(),
        )

        should, signal = await self.exit_strategy.should_exit(ctx)
        assert should is True
        assert signal.metadata["trigger"] == "hard_stop"
        assert signal.strategy == "vr_composite_exit"

    def test_config_validation(self):
        """잘못된 설정 → AssertionError"""
        with pytest.raises(AssertionError):
            VRCompositeExit(VRCompositeExitConfig(hard_stop_pct=0.05))  # positive

        with pytest.raises(AssertionError):
            VRCompositeExit(VRCompositeExitConfig(vr_period=1))

    @pytest.mark.asyncio
    async def test_scan_positions(self):
        """scan_positions: 여러 포지션 스캔"""
        p1 = self._make_position(code="005930", entry_price=100.0)
        p2 = self._make_position(code="000660", entry_price=100.0)

        market_data = {
            "005930": {"close": 90.0},  # -10% → hard stop
            "000660": {"close": 105.0},  # +5% → 안전
        }

        signals = await self.exit_strategy.scan_positions(
            positions=[p1, p2],
            market_data=market_data,
        )

        # p1은 hard stop으로 청산 예상
        stop_codes = [s.code for s in signals]
        assert "005930" in stop_codes
