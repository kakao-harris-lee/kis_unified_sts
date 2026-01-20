"""
마이크로스트럭처 기반 진입 전략 (통합)

kospi_mini_sts의 PureMicrostructureStrategy를 통합 프로젝트용으로 마이그레이션.
EntrySignalGenerator 인터페이스 구현.

핵심 시그널:
    - OFI (Order Flow Imbalance): 호가 변화 기반 매수/매도 압력
    - 호가 불균형 (Order Book Imbalance): 매수/매도 잔량 비율
    - 스프레드 분석: 유동성 상태 판단
    - 변동성 레짐: 시장 상태별 전략 조정

복합 스코어링:
    총점 = Σ(시그널 점수 × 가중치) > 진입 임계값

Usage:
    config = MicrostructureEntryConfig(
        ofi_zscore_threshold=2.0,
        imbalance_threshold=0.5,
        entry_score_threshold=0.6,
    )
    entry_strategy = MicrostructureEntry(config)

    signal = await entry_strategy.generate(context)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Deque, Optional

import numpy as np

from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class VolatilityRegime(Enum):
    """변동성 레짐"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SignalDirection(Enum):
    """시그널 방향"""

    BUY = 1
    SELL = -1
    HOLD = 0


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class MicrostructureEntryConfig:
    """마이크로스트럭처 진입 전략 설정

    모든 임계값은 이 설정에서 정의됨.
    YAML 설정 파일에서 로드하여 사용.

    Attributes:
        # 시그널 가중치
        ofi_weight: OFI 시그널 가중치
        imbalance_weight: 호가 불균형 가중치
        spread_weight: 스프레드 가중치
        regime_weight: 레짐 가중치

        # OFI 조건
        ofi_zscore_threshold: OFI Z-Score 임계값 (±2σ)
        ofi_consecutive_bars: 연속 확인 바 수
        ofi_lookback: OFI 계산 기간
        ofi_zscore_period: Z-Score 계산 기간

        # 호가 불균형 조건
        imbalance_threshold: 불균형 임계값 (0.5 = 50%)
        imbalance_lookback: 불균형 계산 기간

        # 스프레드 조건
        max_spread_ticks: 최대 허용 스프레드 (틱)
        spread_percentile_threshold: 스프레드 백분위 임계값
        tick_size: 1틱 크기 (KOSPI Mini: 0.02)

        # 진입 조건
        entry_score_threshold: 복합 점수 진입 임계값
        min_history: 최소 히스토리 바 수
        cooldown_bars: 진입 후 쿨다운 바 수

        # 레짐별 동작
        low_regime_bias: LOW 레짐 바이어스 (mean_reversion/breakout)
        high_regime_bias: HIGH 레짐 바이어스
    """

    # 시그널 가중치 (합계 = 1.0)
    ofi_weight: float = 0.4
    imbalance_weight: float = 0.3
    spread_weight: float = 0.2
    regime_weight: float = 0.1

    # OFI 조건
    ofi_zscore_threshold: float = 2.0
    ofi_consecutive_bars: int = 3
    ofi_lookback: int = 20
    ofi_zscore_period: int = 60

    # 호가 불균형 조건
    imbalance_threshold: float = 0.5
    imbalance_lookback: int = 20

    # 스프레드 조건
    max_spread_ticks: int = 2
    spread_percentile_threshold: float = 0.7
    spread_lookback: int = 60
    tick_size: float = 0.02  # KOSPI Mini 1틱

    # 진입 조건
    entry_score_threshold: float = 0.6
    min_history: int = 20
    cooldown_bars: int = 5

    # 레짐별 동작
    low_regime_bias: str = "mean_reversion"
    high_regime_bias: str = "breakout"

    def validate(self):
        """설정 유효성 검증"""
        weights_sum = (
            self.ofi_weight
            + self.imbalance_weight
            + self.spread_weight
            + self.regime_weight
        )
        if not (0.99 <= weights_sum <= 1.01):
            raise ValueError(
                f"Signal weights must sum to 1.0, got {weights_sum}"
            )

        if self.ofi_zscore_threshold <= 0:
            raise ValueError("ofi_zscore_threshold must be positive")

        if not (0 < self.imbalance_threshold <= 1):
            raise ValueError("imbalance_threshold must be between 0 and 1")

        if not (0 < self.entry_score_threshold <= 1):
            raise ValueError("entry_score_threshold must be between 0 and 1")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MicrostructureEntryConfig:
        """딕셔너리에서 생성"""
        if "params" in data:
            data = data["params"]

        return cls(
            ofi_weight=data.get("ofi_weight", 0.4),
            imbalance_weight=data.get("imbalance_weight", 0.3),
            spread_weight=data.get("spread_weight", 0.2),
            regime_weight=data.get("regime_weight", 0.1),
            ofi_zscore_threshold=data.get("ofi_zscore_threshold", 2.0),
            ofi_consecutive_bars=data.get("ofi_consecutive_bars", 3),
            ofi_lookback=data.get("ofi_lookback", 20),
            ofi_zscore_period=data.get("ofi_zscore_period", 60),
            imbalance_threshold=data.get("imbalance_threshold", 0.5),
            imbalance_lookback=data.get("imbalance_lookback", 20),
            max_spread_ticks=data.get("max_spread_ticks", 2),
            spread_percentile_threshold=data.get(
                "spread_percentile_threshold", 0.7
            ),
            spread_lookback=data.get("spread_lookback", 60),
            tick_size=data.get("tick_size", 0.02),
            entry_score_threshold=data.get("entry_score_threshold", 0.6),
            min_history=data.get("min_history", 20),
            cooldown_bars=data.get("cooldown_bars", 5),
            low_regime_bias=data.get("low_regime_bias", "mean_reversion"),
            high_regime_bias=data.get("high_regime_bias", "breakout"),
        )

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "ofi_weight": self.ofi_weight,
            "imbalance_weight": self.imbalance_weight,
            "spread_weight": self.spread_weight,
            "regime_weight": self.regime_weight,
            "ofi_zscore_threshold": self.ofi_zscore_threshold,
            "ofi_consecutive_bars": self.ofi_consecutive_bars,
            "ofi_lookback": self.ofi_lookback,
            "ofi_zscore_period": self.ofi_zscore_period,
            "imbalance_threshold": self.imbalance_threshold,
            "imbalance_lookback": self.imbalance_lookback,
            "max_spread_ticks": self.max_spread_ticks,
            "spread_percentile_threshold": self.spread_percentile_threshold,
            "spread_lookback": self.spread_lookback,
            "tick_size": self.tick_size,
            "entry_score_threshold": self.entry_score_threshold,
            "min_history": self.min_history,
            "cooldown_bars": self.cooldown_bars,
            "low_regime_bias": self.low_regime_bias,
            "high_regime_bias": self.high_regime_bias,
        }


# =============================================================================
# Signal Score
# =============================================================================


@dataclass
class SignalScore:
    """시그널 점수"""

    ofi_score: float = 0.0
    imbalance_score: float = 0.0
    spread_score: float = 0.0
    regime_score: float = 0.0
    total_score: float = 0.0
    direction: SignalDirection = SignalDirection.HOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "ofi": self.ofi_score,
            "imbalance": self.imbalance_score,
            "spread": self.spread_score,
            "regime": self.regime_score,
            "total": self.total_score,
            "direction": self.direction.value,
        }


# =============================================================================
# OFI Calculator
# =============================================================================


@dataclass
class OrderBookSnapshot:
    """호가창 스냅샷"""

    bid_price: float  # 최우선 매수호가
    ask_price: float  # 최우선 매도호가
    bid_qty: int  # 매수 잔량
    ask_qty: int  # 매도 잔량
    timestamp: float = 0.0

    @property
    def spread(self) -> float:
        """스프레드 (포인트)"""
        return self.ask_price - self.bid_price

    @property
    def mid_price(self) -> float:
        """중간가"""
        return (self.bid_price + self.ask_price) / 2

    @property
    def imbalance(self) -> float:
        """호가 불균형 (-1 ~ 1)"""
        total = self.bid_qty + self.ask_qty
        if total == 0:
            return 0.0
        return (self.bid_qty - self.ask_qty) / total


class OFICalculator:
    """OFI (Order Flow Imbalance) 계산기

    OFI = Σ (bid_change - ask_change)

    - bid_change: 매수호가 상승 시 +bid_qty, 하락 시 -bid_qty
    - ask_change: 매도호가 상승 시 -ask_qty, 하락 시 +ask_qty

    양수 OFI → 매수 압력
    음수 OFI → 매도 압력
    """

    def __init__(self, lookback: int = 20, zscore_period: int = 60):
        self.lookback = lookback
        self.zscore_period = zscore_period

        self.prev_snapshot: Optional[OrderBookSnapshot] = None
        self.ofi_values: Deque[float] = deque(maxlen=zscore_period)
        self.cumulative_ofi: float = 0.0

    def update(self, snapshot: OrderBookSnapshot) -> float:
        """호가 스냅샷 업데이트 및 OFI 계산"""
        if self.prev_snapshot is None:
            self.prev_snapshot = snapshot
            return 0.0

        ofi = self._calculate_ofi(self.prev_snapshot, snapshot)
        self.ofi_values.append(ofi)
        self.cumulative_ofi += ofi

        self.prev_snapshot = snapshot
        return ofi

    def _calculate_ofi(
        self, prev: OrderBookSnapshot, curr: OrderBookSnapshot
    ) -> float:
        """OFI 계산 (단일 틱)"""
        bid_change = 0.0
        ask_change = 0.0

        # Bid side
        if curr.bid_price > prev.bid_price:
            bid_change = curr.bid_qty
        elif curr.bid_price < prev.bid_price:
            bid_change = -prev.bid_qty
        else:
            bid_change = curr.bid_qty - prev.bid_qty

        # Ask side
        if curr.ask_price > prev.ask_price:
            ask_change = -prev.ask_qty
        elif curr.ask_price < prev.ask_price:
            ask_change = curr.ask_qty
        else:
            ask_change = curr.ask_qty - prev.ask_qty

        return bid_change - ask_change

    @property
    def current_ofi(self) -> float:
        """현재 OFI"""
        return self.ofi_values[-1] if self.ofi_values else 0.0

    @property
    def rolling_ofi(self) -> float:
        """롤링 OFI (lookback 기간 합계)"""
        if len(self.ofi_values) < self.lookback:
            return sum(self.ofi_values)
        return sum(list(self.ofi_values)[-self.lookback :])

    @property
    def ofi_zscore(self) -> float:
        """OFI Z-Score"""
        if len(self.ofi_values) < 10:
            return 0.0

        values = list(self.ofi_values)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))

        if std == 0:
            return 0.0

        return (self.current_ofi - mean) / std

    def reset(self):
        """상태 초기화"""
        self.prev_snapshot = None
        self.ofi_values.clear()
        self.cumulative_ofi = 0.0


# =============================================================================
# Order Book Imbalance
# =============================================================================


class OrderBookImbalance:
    """호가 불균형 분석기

    Imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty)

    양수 → 매수 우위
    음수 → 매도 우위
    """

    def __init__(self, lookback: int = 20):
        self.lookback = lookback
        self.imbalances: Deque[float] = deque(maxlen=lookback)

    def update(self, bid_qty: int, ask_qty: int) -> float:
        """호가 잔량 업데이트"""
        total = bid_qty + ask_qty
        if total == 0:
            imbalance = 0.0
        else:
            imbalance = (bid_qty - ask_qty) / total

        self.imbalances.append(imbalance)
        return imbalance

    @property
    def current(self) -> float:
        """현재 불균형"""
        return self.imbalances[-1] if self.imbalances else 0.0

    @property
    def average(self) -> float:
        """평균 불균형"""
        return float(np.mean(self.imbalances)) if self.imbalances else 0.0

    @property
    def trend(self) -> float:
        """불균형 추세 (최근 - 이전 평균)"""
        if len(self.imbalances) < 5:
            return 0.0

        recent = float(np.mean(list(self.imbalances)[-5:]))
        older = float(np.mean(list(self.imbalances)[:-5]))
        return recent - older

    def reset(self):
        """상태 초기화"""
        self.imbalances.clear()


# =============================================================================
# Spread Analyzer
# =============================================================================


class SpreadAnalyzer:
    """스프레드 분석기

    스프레드가 좁을 때 = 유동성 양호 = 진입 유리
    스프레드가 넓을 때 = 유동성 부족 = 진입 불리
    """

    def __init__(self, lookback: int = 60, tick_size: float = 0.02):
        self.lookback = lookback
        self.tick_size = tick_size
        self.spreads: Deque[float] = deque(maxlen=lookback)

    def update(self, bid_price: float, ask_price: float) -> float:
        """스프레드 업데이트"""
        spread = ask_price - bid_price
        self.spreads.append(spread)
        return spread

    @property
    def current(self) -> float:
        """현재 스프레드"""
        return self.spreads[-1] if self.spreads else self.tick_size

    @property
    def average(self) -> float:
        """평균 스프레드"""
        return float(np.mean(self.spreads)) if self.spreads else self.tick_size

    @property
    def spread_ticks(self) -> int:
        """스프레드 (틱 단위)"""
        return int(round(self.current / self.tick_size))

    @property
    def percentile(self) -> float:
        """현재 스프레드의 백분위 (0~1)"""
        if len(self.spreads) < 10:
            return 0.5

        sorted_spreads = sorted(self.spreads)
        rank = sum(1 for s in sorted_spreads if s < self.current)
        return rank / len(sorted_spreads)

    def is_tight(self, threshold_ratio: float = 0.8) -> bool:
        """스프레드가 평균보다 좁은지"""
        return self.current < self.average * threshold_ratio

    def is_wide(self, threshold_ratio: float = 1.5) -> bool:
        """스프레드가 평균보다 넓은지"""
        return self.current > self.average * threshold_ratio

    def reset(self):
        """상태 초기화"""
        self.spreads.clear()


# =============================================================================
# Microstructure Entry Strategy
# =============================================================================


class MicrostructureEntry(EntrySignalGenerator[MicrostructureEntryConfig]):
    """마이크로스트럭처 기반 진입 전략

    LSTM 없이 마이크로스트럭처 시그널만으로 트레이딩.

    진입 조건:
        1. OFI Z-Score > ±threshold (연속 N분)
        2. 호가 불균형 > ±threshold
        3. 스프레드 < 최대 허용 틱
        4. 레짐 방향 일치

    복합 점수 = Σ(시그널 × 가중치) > 임계값

    Usage:
        config = MicrostructureEntryConfig(entry_score_threshold=0.6)
        strategy = MicrostructureEntry(config)

        signal = await strategy.generate(context)
    """

    NAME = "MICROSTRUCTURE"
    REQUIRED_INDICATORS = [
        "ofi",
        "ofi_zscore",
        "bid_ask_imbalance",
        "spread",
        "regime",
    ]

    def __init__(self, config: MicrostructureEntryConfig):
        super().__init__(config)

        # 시그널 계산기 초기화
        self.ofi_calculator = OFICalculator(
            lookback=config.ofi_lookback,
            zscore_period=config.ofi_zscore_period,
        )
        self.imbalance_analyzer = OrderBookImbalance(
            lookback=config.imbalance_lookback
        )
        self.spread_analyzer = SpreadAnalyzer(
            lookback=config.spread_lookback,
            tick_size=config.tick_size,
        )

        # OFI Z-Score 히스토리 (연속 확인용)
        self.ofi_zscore_history: Deque[float] = deque(maxlen=10)

        # 쿨다운 관리
        self.bars_since_last_signal: int = 0
        self.history_count: int = 0

        logger.info(
            f"{self.name} initialized: "
            f"entry_threshold={config.entry_score_threshold}, "
            f"ofi_zscore={config.ofi_zscore_threshold}, "
            f"imbalance={config.imbalance_threshold}"
        )

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def required_indicators(self) -> list[str]:
        return self.REQUIRED_INDICATORS

    def _validate_config(self):
        """설정 유효성 검증"""
        self.config.validate()

    # -------------------------------------------------------------------------
    # Main Interface
    # -------------------------------------------------------------------------

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """진입 시그널 생성

        Args:
            context: 진입 판단 컨텍스트

        Returns:
            Signal if entry condition met, None otherwise
        """
        self.bars_since_last_signal += 1
        self.history_count += 1

        # 최소 히스토리 체크
        if self.history_count < self.config.min_history:
            return None

        # 마켓 데이터 추출
        market_data = context.market_data
        indicators = context.indicators

        # 호가 데이터 업데이트
        self._update_orderbook_data(market_data)

        # OFI Z-Score 히스토리 업데이트
        ofi_zscore = indicators.get("ofi_zscore", 0.0)
        if ofi_zscore == 0 and "ofi" in indicators:
            ofi_zscore = indicators["ofi"] / 1000 if abs(indicators["ofi"]) > 0 else 0
        self.ofi_zscore_history.append(ofi_zscore)

        # 쿨다운 체크
        if self.bars_since_last_signal < self.config.cooldown_bars:
            return None

        # 스프레드 필터 (너무 넓으면 진입 안함)
        spread = indicators.get("spread", 0.0)
        spread_ticks = spread / self.config.tick_size if spread > 0 else 1
        if spread_ticks > self.config.max_spread_ticks:
            logger.debug(f"Spread too wide: {spread_ticks:.1f} ticks")
            return None

        # 레짐 추출
        regime = self._get_regime(indicators)

        # 매수/매도 점수 계산
        buy_score = self._calculate_signal_score(
            indicators, SignalDirection.BUY, regime
        )
        sell_score = self._calculate_signal_score(
            indicators, SignalDirection.SELL, regime
        )

        # 매수 시그널
        if buy_score.total_score >= self.config.entry_score_threshold:
            self.bars_since_last_signal = 0
            logger.info(
                f"[Microstructure] BUY signal: score={buy_score.total_score:.2f}, "
                f"ofi={buy_score.ofi_score:.2f}, imb={buy_score.imbalance_score:.2f}"
            )
            return self._create_signal(context, buy_score)

        # 매도 시그널
        if sell_score.total_score >= self.config.entry_score_threshold:
            self.bars_since_last_signal = 0
            logger.info(
                f"[Microstructure] SELL signal: score={sell_score.total_score:.2f}, "
                f"ofi={sell_score.ofi_score:.2f}, imb={sell_score.imbalance_score:.2f}"
            )
            return self._create_signal(context, sell_score)

        return None

    # -------------------------------------------------------------------------
    # Signal Calculation
    # -------------------------------------------------------------------------

    def _update_orderbook_data(self, market_data: dict[str, Any]):
        """호가 데이터로 계산기 업데이트"""
        bid_price = market_data.get("bid_price", 0)
        ask_price = market_data.get("ask_price", 0)
        bid_qty = market_data.get("bid_qty", 0)
        ask_qty = market_data.get("ask_qty", 0)

        if bid_price > 0 and ask_price > 0:
            snapshot = OrderBookSnapshot(
                bid_price=bid_price,
                ask_price=ask_price,
                bid_qty=bid_qty,
                ask_qty=ask_qty,
            )
            self.ofi_calculator.update(snapshot)
            self.imbalance_analyzer.update(bid_qty, ask_qty)
            self.spread_analyzer.update(bid_price, ask_price)

    def _get_regime(self, indicators: dict[str, Any]) -> VolatilityRegime:
        """레짐 추출"""
        regime_value = indicators.get("regime")
        if regime_value is None:
            return VolatilityRegime.MEDIUM

        if isinstance(regime_value, VolatilityRegime):
            return regime_value

        try:
            return VolatilityRegime(regime_value)
        except ValueError:
            return VolatilityRegime.MEDIUM

    def _calculate_signal_score(
        self,
        indicators: dict[str, Any],
        direction: SignalDirection,
        regime: VolatilityRegime,
    ) -> SignalScore:
        """시그널 점수 계산"""
        score = SignalScore(direction=direction)
        c = self.config

        # 1. OFI 점수 (0~1)
        score.ofi_score = self._calculate_ofi_score(direction)

        # 2. 호가 불균형 점수 (0~1)
        score.imbalance_score = self._calculate_imbalance_score(
            indicators, direction
        )

        # 3. 스프레드 점수 (0~1)
        score.spread_score = self._calculate_spread_score(indicators)

        # 4. 레짐 점수 (0~1)
        score.regime_score = self._calculate_regime_score(regime, direction)

        # 가중 합계
        score.total_score = (
            score.ofi_score * c.ofi_weight
            + score.imbalance_score * c.imbalance_weight
            + score.spread_score * c.spread_weight
            + score.regime_score * c.regime_weight
        )

        return score

    def _calculate_ofi_score(self, direction: SignalDirection) -> float:
        """OFI 점수 계산

        연속 N분 동안 같은 방향 Z-Score > 임계값이면 1.0
        """
        c = self.config

        if len(self.ofi_zscore_history) < c.ofi_consecutive_bars:
            return 0.0

        recent = list(self.ofi_zscore_history)[-c.ofi_consecutive_bars :]
        threshold = c.ofi_zscore_threshold

        if direction == SignalDirection.BUY:
            # 연속 양수 Z-Score
            consecutive = all(z > threshold for z in recent)
            if consecutive:
                return 1.0
            positive_count = sum(1 for z in recent if z > 0)
            return positive_count / len(recent) * 0.7
        else:  # SELL
            # 연속 음수 Z-Score
            consecutive = all(z < -threshold for z in recent)
            if consecutive:
                return 1.0
            negative_count = sum(1 for z in recent if z < 0)
            return negative_count / len(recent) * 0.7

    def _calculate_imbalance_score(
        self, indicators: dict[str, Any], direction: SignalDirection
    ) -> float:
        """호가 불균형 점수 계산"""
        imbalance = indicators.get(
            "bid_ask_imbalance", self.imbalance_analyzer.current
        )
        threshold = self.config.imbalance_threshold

        if direction == SignalDirection.BUY:  # 매수 우위
            if imbalance >= threshold:
                return 1.0
            elif imbalance > 0:
                return imbalance / threshold * 0.8
            else:
                return 0.0
        else:  # SELL (매도 우위)
            if imbalance <= -threshold:
                return 1.0
            elif imbalance < 0:
                return abs(imbalance) / threshold * 0.8
            else:
                return 0.0

    def _calculate_spread_score(self, indicators: dict[str, Any]) -> float:
        """스프레드 점수 계산

        스프레드가 좁을수록 높은 점수
        """
        spread = indicators.get("spread", self.spread_analyzer.current)
        tick_size = self.config.tick_size
        avg_spread = tick_size * 2  # 기본 평균 스프레드 (2틱)

        if spread <= tick_size:  # 1틱
            return 1.0
        elif spread <= avg_spread:
            return 0.8
        elif spread <= avg_spread * 1.5:
            return 0.5
        else:
            return 0.2

    def _calculate_regime_score(
        self, regime: VolatilityRegime, direction: SignalDirection
    ) -> float:
        """레짐 점수 계산

        레짐에 맞는 방향이면 높은 점수
        """
        c = self.config

        # LOW 레짐: 역추세 선호
        if regime == VolatilityRegime.LOW:
            if c.low_regime_bias == "mean_reversion":
                return 0.8
            return 0.5

        # HIGH 레짐: 추세 추종 선호
        elif regime == VolatilityRegime.HIGH:
            if c.high_regime_bias == "breakout":
                return 0.9
            return 0.6

        # MEDIUM 레짐: 중립
        else:
            return 0.5

    # -------------------------------------------------------------------------
    # Signal Creation
    # -------------------------------------------------------------------------

    def _create_signal(
        self, context: EntryContext, score: SignalScore
    ) -> Signal:
        """Signal 객체 생성"""
        market_data = context.market_data
        price = market_data.get("close", market_data.get("price", 0))

        return Signal(
            code=market_data.get("code", ""),
            name=market_data.get("name", ""),
            signal_type=SignalType.ENTRY,
            strategy=self.name,
            price=price,
            confidence=score.total_score,
            timestamp=context.timestamp,
            metadata={
                "direction": "BUY" if score.direction == SignalDirection.BUY else "SELL",
                "ofi_score": score.ofi_score,
                "imbalance_score": score.imbalance_score,
                "spread_score": score.spread_score,
                "regime_score": score.regime_score,
            },
        )

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_current_scores(
        self, indicators: dict[str, Any]
    ) -> dict[str, SignalScore]:
        """현재 시그널 점수 조회 (디버깅용)"""
        regime = self._get_regime(indicators)
        return {
            "buy": self._calculate_signal_score(
                indicators, SignalDirection.BUY, regime
            ),
            "sell": self._calculate_signal_score(
                indicators, SignalDirection.SELL, regime
            ),
        }

    def reset(self):
        """상태 초기화"""
        self.ofi_calculator.reset()
        self.imbalance_analyzer.reset()
        self.spread_analyzer.reset()
        self.ofi_zscore_history.clear()
        self.bars_since_last_signal = 0
        self.history_count = 0

    def get_config(self) -> dict[str, Any]:
        """설정 반환"""
        return {
            "name": self.name,
            "required_indicators": self.required_indicators,
            **self.config.to_dict(),
        }
