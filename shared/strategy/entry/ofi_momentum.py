"""OFI Momentum 진입 전략

OFI (Order Flow Imbalance) 기반 단기 모멘텀 전략.
연속적인 매수/매도 압력 감지 시 진입.

kospi_mini_sts의 OFIMomentumStrategy를 통합 프로젝트용으로 마이그레이션.

핵심 로직:
    - OFI Z-Score > ±threshold (연속 N분) → 진입
    - 스프레드 필터: 좁을 때만 진입
    - 호가 불균형 확인: 방향 일치 시 진입

Usage:
    config = OFIMomentumConfig(
        ofi_zscore_threshold=2.0,
        consecutive_bars=3,
    )
    strategy = OFIMomentumEntry(config)

    signal = await strategy.generate(context)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Deque, Optional

import numpy as np

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class OFIMomentumConfig(ConfigMixin):
    """OFI Momentum 진입 전략 설정

    Attributes:
        # OFI 시그널 설정
        ofi_zscore_threshold: Z-Score 임계값 (기본: ±2σ)
        consecutive_bars: 연속 확인 바 수
        ofi_lookback: OFI 히스토리 기간

        # 스프레드 필터
        require_tight_spread: 스프레드 필터 활성화
        max_spread_points: 최대 허용 스프레드 (포인트)
        tick_size: 1틱 크기

        # 호가 불균형
        imbalance_confirm: 호가 불균형 확인 활성화
        imbalance_threshold: 불균형 임계값

        # 진입 조건
        min_history: 최소 히스토리 바 수
        cooldown_bars: 진입 후 쿨다운 바 수
    """

    # OFI 시그널 설정
    ofi_zscore_threshold: float = 2.0
    consecutive_bars: int = 3
    ofi_lookback: int = 60

    # 스프레드 필터
    require_tight_spread: bool = True
    max_spread_points: float = 0.04  # 2틱 (0.02 * 2)
    tick_size: float = 0.02

    # 호가 불균형
    imbalance_confirm: bool = True
    imbalance_threshold: float = 0.2

    # 진입 조건
    min_history: int = 20
    cooldown_bars: int = 5

    def validate(self):
        """설정 유효성 검증"""
        if self.ofi_zscore_threshold <= 0:
            raise ValueError("ofi_zscore_threshold must be positive")

        if self.consecutive_bars < 1:
            raise ValueError("consecutive_bars must be at least 1")

        if not (0 < self.imbalance_threshold <= 1):
            raise ValueError("imbalance_threshold must be between 0 and 1")


# =============================================================================
# OFI Momentum Entry Strategy
# =============================================================================


class OFIMomentumEntry(EntrySignalGenerator[OFIMomentumConfig]):
    """OFI Momentum 진입 전략

    OFI가 ±Nσ를 연속 M분 이상 유지하면 진입:
    - OFI Z-Score > +threshold (연속) + 스프레드 좁음 + 매수 불균형 → 매수
    - OFI Z-Score < -threshold (연속) + 스프레드 좁음 + 매도 불균형 → 매도

    Microstructure 전략과의 차이점:
    - OFI 시그널에만 집중 (단순화)
    - 연속 바 확인 필수
    - 복합 스코어링 없음

    Usage:
        config = OFIMomentumConfig(ofi_zscore_threshold=2.0)
        strategy = OFIMomentumEntry(config)

        signal = await strategy.generate(context)
    """

    NAME = "OFI_MOMENTUM"
    CONFIG_CLASS = OFIMomentumConfig
    REQUIRED_INDICATORS = ["ofi", "ofi_zscore", "spread", "bid_ask_imbalance"]

    def __init__(self, config: OFIMomentumConfig):
        super().__init__(config)

        # OFI 히스토리
        self.ofi_values: Deque[float] = deque(maxlen=config.ofi_lookback)
        self.ofi_zscore_history: Deque[float] = deque(maxlen=10)

        # 상태 관리
        self.history_count: int = 0
        self.bars_since_last_signal: int = 0

        logger.info(
            f"{self.name} initialized: "
            f"zscore_threshold={config.ofi_zscore_threshold}, "
            f"consecutive_bars={config.consecutive_bars}"
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
        self.history_count += 1
        self.bars_since_last_signal += 1

        market_data = context.market_data
        indicators = context.indicators

        # OFI 업데이트
        ofi = indicators.get("ofi", market_data.get("ofi", 0))
        self.ofi_values.append(ofi)

        # 최소 히스토리 체크
        if self.history_count < self.config.min_history:
            return None

        # 쿨다운 체크
        if self.bars_since_last_signal < self.config.cooldown_bars:
            return None

        # OFI Z-Score 계산 및 저장
        ofi_zscore = self._calculate_ofi_zscore(ofi, indicators)
        self.ofi_zscore_history.append(ofi_zscore)

        # 스프레드 필터
        if self.config.require_tight_spread:
            spread = indicators.get("spread", market_data.get("spread", 0))
            if spread > self.config.max_spread_points:
                logger.debug(f"Spread too wide: {spread:.4f}")
                return None

        # 호가 불균형
        imbalance = indicators.get(
            "bid_ask_imbalance", market_data.get("imbalance", 0)
        )

        # 매수 시그널 체크
        if self._check_consecutive_ofi("positive"):
            if self.config.imbalance_confirm:
                if imbalance < self.config.imbalance_threshold:
                    logger.debug(
                        f"OFI positive but imbalance weak ({imbalance:.2f})"
                    )
                    return None

            self.bars_since_last_signal = 0
            logger.info(
                f"[OFIMomentum] BUY signal: ofi_z={ofi_zscore:.2f}, "
                f"imbalance={imbalance:.2f}"
            )
            return self._create_signal(context, "BUY", ofi_zscore, imbalance)

        # 매도 시그널 체크
        if self._check_consecutive_ofi("negative"):
            if self.config.imbalance_confirm:
                if imbalance > -self.config.imbalance_threshold:
                    logger.debug(
                        f"OFI negative but imbalance weak ({imbalance:.2f})"
                    )
                    return None

            self.bars_since_last_signal = 0
            logger.info(
                f"[OFIMomentum] SELL signal: ofi_z={ofi_zscore:.2f}, "
                f"imbalance={imbalance:.2f}"
            )
            return self._create_signal(context, "SELL", ofi_zscore, imbalance)

        return None

    # -------------------------------------------------------------------------
    # OFI Calculation
    # -------------------------------------------------------------------------

    def _calculate_ofi_zscore(
        self, current_ofi: float, indicators: dict[str, Any]
    ) -> float:
        """OFI Z-Score 계산

        indicators에 이미 계산된 값이 있으면 사용, 없으면 직접 계산.
        """
        # 이미 계산된 값이 있으면 사용
        if "ofi_zscore" in indicators:
            return indicators["ofi_zscore"]

        # 직접 계산
        if len(self.ofi_values) < 20:
            return 0.0

        values = list(self.ofi_values)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))

        if std == 0:
            return 0.0

        return (current_ofi - mean) / std

    def _check_consecutive_ofi(self, direction: str) -> bool:
        """연속 OFI Z-Score 체크

        Args:
            direction: "positive" or "negative"

        Returns:
            연속 조건 만족 여부
        """
        c = self.config

        if len(self.ofi_zscore_history) < c.consecutive_bars:
            return False

        recent = list(self.ofi_zscore_history)[-c.consecutive_bars:]

        if direction == "positive":
            return all(z > c.ofi_zscore_threshold for z in recent)
        else:
            return all(z < -c.ofi_zscore_threshold for z in recent)

    # -------------------------------------------------------------------------
    # Signal Creation
    # -------------------------------------------------------------------------

    def _create_signal(
        self,
        context: EntryContext,
        direction: str,
        ofi_zscore: float,
        imbalance: float,
    ) -> Signal:
        """Signal 객체 생성"""
        market_data = context.market_data
        price = market_data.get("close", market_data.get("price", 0))

        # 신뢰도 계산 (Z-Score 크기 기반)
        confidence = min(abs(ofi_zscore) / 4.0, 1.0)  # 4σ에서 100%

        return Signal(
            code=market_data.get("code", ""),
            name=market_data.get("name", ""),
            signal_type=SignalType.ENTRY,
            strategy=self.name,
            price=price,
            confidence=confidence,
            timestamp=context.timestamp,
            metadata={
                "direction": direction,
                "ofi_zscore": ofi_zscore,
                "imbalance": imbalance,
                "consecutive_bars": self.config.consecutive_bars,
            },
        )

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_current_zscore(self) -> float:
        """현재 OFI Z-Score 조회"""
        return self.ofi_zscore_history[-1] if self.ofi_zscore_history else 0.0

    def reset(self):
        """상태 초기화"""
        self.ofi_values.clear()
        self.ofi_zscore_history.clear()
        self.history_count = 0
        self.bars_since_last_signal = 0

    def get_config(self) -> dict[str, Any]:
        """설정 반환"""
        return {
            "name": self.name,
            "required_indicators": self.required_indicators,
            **self.config.to_dict(),
        }
