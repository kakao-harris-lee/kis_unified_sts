"""LLM-Aware Adaptive Position Sizer

포지션 사이즈를 LLM 시장 분석 컨텍스트(risk_score, confidence, risk_mode)에 따라 동적으로 조정.

Usage:
    # LLM 적응형 사이징
    sizer = LLMAdaptiveSizer(LLMAdaptiveSizerConfig(
        risk_per_trade_pct=1.0,
        confidence_boost_high=1.2,
        confidence_penalty_low=0.7,
        risk_mode_scaling={'RISK_ON': 1.2, 'NEUTRAL': 1.0, 'RISK_OFF': 0.5}
    ))
    qty = sizer.calculate(signal, balance, positions, market_context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

from shared.strategy.position.sizers import RiskBasedSizer, RiskBasedSizerConfig

if TYPE_CHECKING:
    from shared.llm.market_context import MarketContext
    from shared.models.position import Position
    from shared.models.signal import Signal

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Adaptive Sizer Config
# =============================================================================


@dataclass
class LLMAdaptiveSizerConfig(RiskBasedSizerConfig):
    """LLM 적응형 사이저 설정

    RiskBasedSizerConfig를 상속하여 LLM 컨텍스트 기반 스케일링 파라미터 추가.

    Attributes:
        # RiskBasedSizerConfig 상속 속성
        risk_per_trade_pct: 거래당 리스크 (계좌 대비 %)
        stop_loss_pct: 손절 비율 (진입가 대비 %)
        max_position_pct: 최대 포지션 비율
        max_positions: 최대 동시 보유 종목 수
        min_quantity: 최소 수량
        max_quantity: 최대 수량

        # LLM 적응형 파라미터
        confidence_threshold_high: 높은 신뢰도 임계값 (>= 이 값이면 부스트)
        confidence_threshold_low: 낮은 신뢰도 임계값 (< 이 값이면 페널티)
        confidence_boost_high: 높은 신뢰도 시 곱셈 계수 (default: 1.2x)
        confidence_penalty_low: 낮은 신뢰도 시 곱셈 계수 (default: 0.7x)
        risk_score_threshold_high: 높은 리스크 임계값 (>= 이 값이면 축소)
        risk_score_penalty_high: 높은 리스크 시 곱셈 계수 (default: 0.6x)
        risk_mode_scaling: RiskMode별 스케일링 계수 (RISK_ON/NEUTRAL/RISK_OFF)
        enable_risk_score_scaling: risk_score 기반 스케일링 활성화
        enable_confidence_scaling: confidence 기반 스케일링 활성화
        enable_risk_mode_scaling: risk_mode 기반 스케일링 활성화
    """

    # Confidence 기반 스케일링
    confidence_threshold_high: float = 0.7
    confidence_threshold_low: float = 0.4
    confidence_boost_high: float = 1.2
    confidence_penalty_low: float = 0.7

    # Risk Score 기반 스케일링
    risk_score_threshold_high: float = 70.0  # 0-100 scale
    risk_score_penalty_high: float = 0.6

    # RiskMode 기반 스케일링
    risk_mode_scaling: Dict[str, float] = field(
        default_factory=lambda: {
            "RISK_ON": 1.2,
            "NEUTRAL": 1.0,
            "RISK_OFF": 0.5,
        }
    )

    # 기능 토글
    enable_risk_score_scaling: bool = True
    enable_confidence_scaling: bool = True
    enable_risk_mode_scaling: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMAdaptiveSizerConfig:
        """딕셔너리에서 생성"""
        # 부모 클래스 파라미터 먼저 처리
        base_params = {
            "risk_per_trade_pct": data.get("risk_per_trade_pct", 1.0),
            "stop_loss_pct": abs(data.get("stop_loss_pct", 2.0)),
            "max_position_pct": data.get("max_position_pct", 10.0),
            "max_positions": data.get("max_positions", 5),
            "min_quantity": data.get("min_quantity", 1),
            "max_quantity": data.get("max_quantity", 10000),
        }

        # LLM 적응형 파라미터
        llm_params = {
            "confidence_threshold_high": data.get("confidence_threshold_high", 0.7),
            "confidence_threshold_low": data.get("confidence_threshold_low", 0.4),
            "confidence_boost_high": data.get("confidence_boost_high", 1.2),
            "confidence_penalty_low": data.get("confidence_penalty_low", 0.7),
            "risk_score_threshold_high": data.get("risk_score_threshold_high", 70.0),
            "risk_score_penalty_high": data.get("risk_score_penalty_high", 0.6),
            "risk_mode_scaling": data.get(
                "risk_mode_scaling",
                {"RISK_ON": 1.2, "NEUTRAL": 1.0, "RISK_OFF": 0.5},
            ),
            "enable_risk_score_scaling": data.get("enable_risk_score_scaling", True),
            "enable_confidence_scaling": data.get("enable_confidence_scaling", True),
            "enable_risk_mode_scaling": data.get("enable_risk_mode_scaling", True),
        }

        return cls(**base_params, **llm_params)


# =============================================================================
# LLM Adaptive Sizer
# =============================================================================


class LLMAdaptiveSizer(RiskBasedSizer):
    """LLM 적응형 포지션 사이저

    RiskBasedSizer를 확장하여 MarketContext 기반 동적 포지션 사이즈 조정.

    조정 로직:
        1. RiskBasedSizer로 기본 수량 계산
        2. MarketContext.confidence 기반 스케일링
           - High confidence (>= 0.7) → 1.2x boost
           - Low confidence (< 0.4) → 0.7x penalty
        3. MarketContext.risk_score 기반 스케일링
           - High risk (>= 70) → 0.6x penalty
        4. MarketContext.risk_mode 기반 스케일링
           - RISK_ON → 1.2x
           - NEUTRAL → 1.0x
           - RISK_OFF → 0.5x
        5. Final quantity = base_quantity * confidence_mult * risk_mult * mode_mult

    Graceful Degradation:
        - market_context가 None이면 RiskBasedSizer와 동일하게 동작
    """

    CONFIG_CLASS = LLMAdaptiveSizerConfig

    def __init__(self, config: LLMAdaptiveSizerConfig):
        """초기화

        Args:
            config: LLM 적응형 사이저 설정
        """
        super().__init__(config)
        # Type hint for IDE support
        self.config: LLMAdaptiveSizerConfig = config

    def calculate(
        self,
        signal: "Signal",
        account_balance: float,
        current_positions: list["Position"],
        market_context: Optional["MarketContext"] = None,
    ) -> int:
        """포지션 크기 계산 (LLM 컨텍스트 기반 적응형)

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션
            market_context: LLM 시장 분석 컨텍스트 (선택적)

        Returns:
            매매 수량
        """
        c = self.config

        # 1. RiskBasedSizer로 기본 수량 계산
        base_quantity = super().calculate(
            signal, account_balance, current_positions, market_context
        )

        # 기본 수량이 0이면 조기 반환
        if base_quantity == 0:
            return 0

        # 2. MarketContext가 없으면 기본 수량 그대로 반환 (graceful degradation)
        if market_context is None:
            logger.debug(
                f"LLMAdaptiveSizer: No market_context, using base quantity={base_quantity}"
            )
            return base_quantity

        # 3. 스케일링 계수 계산
        confidence_mult = self._calculate_confidence_multiplier(market_context)
        risk_score_mult = self._calculate_risk_score_multiplier(market_context)
        risk_mode_mult = self._calculate_risk_mode_multiplier(market_context)

        # 4. 최종 수량 계산
        total_multiplier = confidence_mult * risk_score_mult * risk_mode_mult
        adjusted_quantity = int(base_quantity * total_multiplier)

        # 5. 최소/최대 제한 재적용
        adjusted_quantity = max(c.min_quantity, min(adjusted_quantity, c.max_quantity))

        logger.debug(
            f"LLMAdaptiveSizer: base={base_quantity}, "
            f"conf={confidence_mult:.2f}, risk={risk_score_mult:.2f}, "
            f"mode={risk_mode_mult:.2f}, total_mult={total_multiplier:.2f}, "
            f"adjusted={adjusted_quantity}"
        )

        return adjusted_quantity

    def _calculate_confidence_multiplier(
        self, market_context: "MarketContext"
    ) -> float:
        """Confidence 기반 곱셈 계수 계산

        Args:
            market_context: 시장 컨텍스트

        Returns:
            곱셈 계수 (0.7 ~ 1.2)
        """
        c = self.config

        if not c.enable_confidence_scaling:
            return 1.0

        confidence = market_context.confidence

        if confidence >= c.confidence_threshold_high:
            # 높은 신뢰도 → 부스트
            multiplier = c.confidence_boost_high
            logger.debug(
                f"High confidence ({confidence:.2f}) → boost {multiplier:.2f}x"
            )
        elif confidence < c.confidence_threshold_low:
            # 낮은 신뢰도 → 페널티
            multiplier = c.confidence_penalty_low
            logger.debug(
                f"Low confidence ({confidence:.2f}) → penalty {multiplier:.2f}x"
            )
        else:
            # 중간 신뢰도 → 중립
            multiplier = 1.0

        return multiplier

    def _calculate_risk_score_multiplier(
        self, market_context: "MarketContext"
    ) -> float:
        """Risk Score 기반 곱셈 계수 계산

        Args:
            market_context: 시장 컨텍스트

        Returns:
            곱셈 계수 (0.6 ~ 1.0)
        """
        c = self.config

        if not c.enable_risk_score_scaling:
            return 1.0

        risk_score = market_context.risk_score

        if risk_score >= c.risk_score_threshold_high:
            # 높은 리스크 → 축소
            multiplier = c.risk_score_penalty_high
            logger.debug(
                f"High risk_score ({risk_score:.1f}) → penalty {multiplier:.2f}x"
            )
        else:
            # 정상 리스크 → 중립
            multiplier = 1.0

        return multiplier

    def _calculate_risk_mode_multiplier(
        self, market_context: "MarketContext"
    ) -> float:
        """RiskMode 기반 곱셈 계수 계산

        Args:
            market_context: 시장 컨텍스트

        Returns:
            곱셈 계수 (RISK_ON=1.2, NEUTRAL=1.0, RISK_OFF=0.5)
        """
        c = self.config

        if not c.enable_risk_mode_scaling:
            return 1.0

        risk_mode = market_context.risk_mode.value  # Enum → string
        multiplier = c.risk_mode_scaling.get(risk_mode, 1.0)

        logger.debug(f"RiskMode {risk_mode} → multiplier {multiplier:.2f}x")
        return multiplier
