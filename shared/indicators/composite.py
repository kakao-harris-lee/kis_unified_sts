"""복합 스코어 계산기

여러 지표를 통합하여 복합 스코어 계산.

quant_moment_sts의 CompositeScoreCalculator를 마이그레이션.

Usage:
    calc = CompositeScoreCalculator()

    score = calc.calculate(
        volume_velocity=0.3,
        imbalance=0.4,
        price_vs_vwap=1.5,
        program_net_buy=500_000_000,
    )

    if score.is_signal:
        print(f"SIGNAL! Total: {score.total_score}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from shared.indicators.orderbook import OrderBookAnalyzer, OrderBookConfig
from shared.indicators.volume import (
    VolumeAccelerationCalculator,
    VolumeConfig,
    VWAPCalculator,
    VWAPConfig,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ProgramScoreConfig:
    """프로그램 순매수 스코어 설정"""

    max_score: float = 20.0
    full_score_amount: float = 1_000_000_000  # 만점 기준 금액 (10억)


@dataclass
class IndicatorConfig:
    """지표 계산 통합 설정

    모든 매직 넘버를 중앙 집중화하여 관리.

    스코어 구성 (100점 만점):
    - Volume Acceleration: 0-40점
    - Orderbook Imbalance: 0-30점
    - Program Net Buy: 0-20점
    - VWAP Position: 0-10점
    """

    # 시그널 임계값
    signal_threshold: float = 70.0

    # 개별 지표 설정
    orderbook: OrderBookConfig = field(default_factory=OrderBookConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    vwap: VWAPConfig = field(default_factory=VWAPConfig)
    program: ProgramScoreConfig = field(default_factory=ProgramScoreConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndicatorConfig:
        """딕셔너리에서 생성"""
        return cls(
            signal_threshold=data.get("signal_threshold", 70.0),
            orderbook=OrderBookConfig.from_dict(data.get("orderbook", {})),
            volume=VolumeConfig.from_dict(data.get("volume", {})),
            vwap=VWAPConfig.from_dict(data.get("vwap", {})),
            program=ProgramScoreConfig(
                max_score=data.get("program", {}).get("max_score", 20.0),
                full_score_amount=data.get("program", {}).get(
                    "full_score_amount", 1_000_000_000
                ),
            ),
        )


# =============================================================================
# Score Result
# =============================================================================


@dataclass
class ScoreResult:
    """복합 스코어 결과

    Attributes:
        total_score: 총점 (0-100)
        volume_score: 거래량 가속도 점수 (0-40)
        imbalance_score: 호가 불균형 점수 (0-30)
        program_score: 프로그램 순매수 점수 (0-20)
        vwap_score: VWAP 위치 점수 (0-10)
        is_signal: 시그널 발생 여부 (score >= threshold)
    """

    total_score: float
    volume_score: float
    imbalance_score: float
    program_score: float
    vwap_score: float
    is_signal: bool


# 하위호환성 별칭
CompositeScore = ScoreResult


# =============================================================================
# Composite Score Calculator
# =============================================================================


class CompositeScoreCalculator:
    """복합 스코어 계산기

    스코어 구성 (100점 만점):
    - Volume Acceleration: 0-40점
    - Orderbook Imbalance: 0-30점
    - Program Net Buy: 0-20점
    - VWAP Position: 0-10점

    SIGNAL_LONG 조건: score >= signal_threshold (default: 70)

    Usage:
        calc = CompositeScoreCalculator()

        score = calc.calculate(
            volume_velocity=0.3,
            imbalance=0.4,
            price_vs_vwap=1.5,
        )

        if score.is_signal:
            print("BUY SIGNAL!")
    """

    def __init__(self, config: IndicatorConfig | None = None):
        """
        Args:
            config: 설정 (기본값 사용 시 None)
        """
        self.config = config or IndicatorConfig()
        self.orderbook_analyzer = OrderBookAnalyzer(config=self.config.orderbook)
        self.volume_calculator = VolumeAccelerationCalculator(
            config=self.config.volume
        )
        self.vwap_calculator = VWAPCalculator(config=self.config.vwap)

    @property
    def signal_threshold(self) -> float:
        """시그널 발생 임계값"""
        return self.config.signal_threshold

    def calculate(
        self,
        volume_velocity: float,
        imbalance: float,
        price_vs_vwap: float,
        program_net_buy: float = 0.0,
        *,
        timestamps: list = None,
        context_timestamp = None,
        lookahead_guard = None,
        context_info: str = None,
    ) -> ScoreResult:
        """복합 스코어 계산

        Args:
            volume_velocity: 거래량 변화율
            imbalance: 호가 불균형 (-1.0 ~ +1.0)
            price_vs_vwap: VWAP 대비 가격 (%)
            program_net_buy: 프로그램 순매수 금액

        Returns:
            ScoreResult
        """
        # LookaheadGuard: 시계열 입력이 배열이면 검사
        if lookahead_guard and timestamps is not None and context_timestamp is not None:
            lookahead_guard.check([volume_velocity], timestamps, context_timestamp, context_info or "composite:volume_velocity")
            lookahead_guard.check([imbalance], timestamps, context_timestamp, context_info or "composite:imbalance")
            lookahead_guard.check([price_vs_vwap], timestamps, context_timestamp, context_info or "composite:price_vs_vwap")
        vol_score = self.volume_calculator.get_velocity_score(volume_velocity)
        imb_score = self.orderbook_analyzer.get_imbalance_score(imbalance)
        vwap_score = self.vwap_calculator.get_vwap_score(price_vs_vwap)

        # 프로그램 순매수 스코어
        program_cfg = self.config.program
        program_score = 0.0
        if program_net_buy > 0:
            program_score = min(
                program_cfg.max_score,
                program_net_buy
                / program_cfg.full_score_amount
                * program_cfg.max_score,
            )

        total = vol_score + imb_score + program_score + vwap_score

        return ScoreResult(
            total_score=total,
            volume_score=vol_score,
            imbalance_score=imb_score,
            program_score=program_score,
            vwap_score=vwap_score,
            is_signal=total >= self.signal_threshold,
        )

    def calculate_from_raw(
        self,
        current_volume: int,
        prev_volume: int,
        bid_total: int,
        ask_total: int,
        current_price: float,
        vwap: float,
        program_net_buy: float = 0.0,
        *,
        timestamps: list = None,
        context_timestamp = None,
        lookahead_guard = None,
        context_info: str = None,
    ) -> ScoreResult:
        """원시 데이터로 복합 스코어 계산

        Args:
            current_volume: 현재 윈도우 거래량
            prev_volume: 이전 윈도우 거래량
            bid_total: 매수 잔량 합계
            ask_total: 매도 잔량 합계
            current_price: 현재가
            vwap: VWAP 값
            program_net_buy: 프로그램 순매수 금액

        Returns:
            ScoreResult
        """
        # 거래량 변화율
        if prev_volume > 0:
            volume_velocity = (current_volume - prev_volume) / prev_volume
        else:
            volume_velocity = 0.0

        # 호가 불균형
        total_qty = bid_total + ask_total
        if total_qty > 0:
            imbalance = (bid_total - ask_total) / total_qty
        else:
            imbalance = 0.0

        # VWAP 대비 가격
        if vwap > 0:
            price_vs_vwap = (current_price - vwap) / vwap * 100
        else:
            price_vs_vwap = 0.0

        return self.calculate(
            volume_velocity=volume_velocity,
            imbalance=imbalance,
            price_vs_vwap=price_vs_vwap,
            program_net_buy=program_net_buy,
            timestamps=timestamps,
            context_timestamp=context_timestamp,
            lookahead_guard=lookahead_guard,
            context_info=context_info,
        )
