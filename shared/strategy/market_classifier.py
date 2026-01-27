"""MarketClassifier: 시장 상태 분류기

MFI + ADX를 활용한 시장 상태 분류.
E4 MarketRegimeExit 전략에서 사용.

시장 상태:
- BULL_STRONG: 강한 상승장 (MFI > 49)
- BULL_MODERATE: 온건한 상승장 (MFI > 48)
- SIDEWAYS_UP: 횡보 상승 (MFI > 45)
- SIDEWAYS_FLAT: 횡보 (MFI 41-45)
- SIDEWAYS_DOWN: 횡보 하락 (MFI 34-41)
- BEAR_MODERATE: 온건한 하락장 (MFI < 41)
- BEAR_STRONG: 강한 하락장 (MFI < 34)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MarketState(Enum):
    """시장 상태"""

    BULL_STRONG = "BULL_STRONG"
    BULL_MODERATE = "BULL_MODERATE"
    SIDEWAYS_UP = "SIDEWAYS_UP"
    SIDEWAYS_FLAT = "SIDEWAYS_FLAT"
    SIDEWAYS_DOWN = "SIDEWAYS_DOWN"
    BEAR_MODERATE = "BEAR_MODERATE"
    BEAR_STRONG = "BEAR_STRONG"
    UNKNOWN = "UNKNOWN"


class MarketClassifier:
    """시장 상태 분류기

    MFI (Money Flow Index)와 ADX (Average Directional Index)를 활용하여
    현재 시장 상태를 분류합니다.

    Usage:
        classifier = MarketClassifier()
        state = classifier.classify(mfi=52.0, adx=25.0)
        if classifier.is_bearish(state):
            # 하락장 대응
    """

    DEFAULT_CONFIG = {
        "mfi_bull_strong": 49,
        "mfi_bull_moderate": 48,
        "mfi_sideways_up": 45,
        "mfi_bear_moderate": 41,
        "mfi_bear_strong": 34,
        "adx_strong_trend": 20,
        "adx_moderate_trend": 18,
    }

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Args:
            config: MFI/ADX 임계값 설정
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        logger.debug(f"MarketClassifier initialized with config: {self.config}")

    def classify(
        self,
        mfi: float,
        adx: float,
        rsi: Optional[float] = None,
        macd: Optional[float] = None,
        macd_signal: Optional[float] = None,
    ) -> MarketState:
        """시장 상태 분류

        Args:
            mfi: Money Flow Index (0-100)
            adx: Average Directional Index (0-100)
            rsi: Relative Strength Index (optional)
            macd: MACD value (optional)
            macd_signal: MACD Signal (optional)

        Returns:
            MarketState enum
        """
        # MFI 기반 1차 분류
        if mfi >= self.config["mfi_bull_strong"]:
            return MarketState.BULL_STRONG
        elif mfi >= self.config["mfi_bull_moderate"]:
            return MarketState.BULL_MODERATE
        elif mfi >= self.config["mfi_sideways_up"]:
            return MarketState.SIDEWAYS_UP
        elif mfi >= self.config["mfi_bear_moderate"]:
            # SIDEWAYS_FLAT vs SIDEWAYS_DOWN 구분
            midpoint = (
                self.config["mfi_sideways_up"] + self.config["mfi_bear_moderate"]
            ) / 2
            if mfi >= midpoint:
                return MarketState.SIDEWAYS_FLAT
            else:
                return MarketState.SIDEWAYS_DOWN
        elif mfi >= self.config["mfi_bear_strong"]:
            return MarketState.BEAR_MODERATE
        else:
            return MarketState.BEAR_STRONG

    def is_bullish(self, state: MarketState) -> bool:
        """상승 시장 여부"""
        return state in [MarketState.BULL_STRONG, MarketState.BULL_MODERATE]

    def is_bearish(self, state: MarketState) -> bool:
        """하락 시장 여부"""
        return state in [MarketState.BEAR_STRONG, MarketState.BEAR_MODERATE]

    def is_sideways(self, state: MarketState) -> bool:
        """횡보 시장 여부"""
        return state in [
            MarketState.SIDEWAYS_UP,
            MarketState.SIDEWAYS_FLAT,
            MarketState.SIDEWAYS_DOWN,
        ]

    def should_trade(self, state: MarketState) -> bool:
        """거래 가능 상태 여부 (BEAR 제외)"""
        return not self.is_bearish(state)

    def get_position_size_multiplier(self, state: MarketState) -> float:
        """시장 상태별 포지션 크기 배수

        Returns:
            BULL_STRONG: 1.0 (기본)
            BULL_MODERATE: 0.8
            SIDEWAYS_UP: 0.6
            SIDEWAYS_FLAT: 0.5
            SIDEWAYS_DOWN: 0.25
            BEAR: 0.0 (거래 금지)
        """
        multipliers = {
            MarketState.BULL_STRONG: 1.0,
            MarketState.BULL_MODERATE: 0.8,
            MarketState.SIDEWAYS_UP: 0.6,
            MarketState.SIDEWAYS_FLAT: 0.5,
            MarketState.SIDEWAYS_DOWN: 0.25,
            MarketState.BEAR_MODERATE: 0.0,
            MarketState.BEAR_STRONG: 0.0,
            MarketState.UNKNOWN: 0.0,
        }
        return multipliers.get(state, 0.0)
