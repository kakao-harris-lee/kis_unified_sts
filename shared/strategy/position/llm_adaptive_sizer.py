"""LLM-Aware Adaptive Position Sizer

포지션 사이즈를 LLM 시장 분석 컨텍스트(risk_score, confidence, risk_mode)에 따라 동적으로 조정.

Usage:
    # LLM 적응형 사이징 (단일-임계값 모드, 주식)
    sizer = LLMAdaptiveSizer(LLMAdaptiveSizerConfig(
        risk_per_trade_pct=1.0,
        confidence_boost_high=1.2,
        confidence_penalty_low=0.7,
        risk_mode_scaling={'RISK_ON': 1.2, 'NEUTRAL': 1.0, 'RISK_OFF': 0.5}
    ))
    qty = sizer.calculate(signal, balance, positions, market_context)

    # 멀티-티어 스케일링 모드 (선물, Phase 1.3)
    sizer = LLMAdaptiveSizer(LLMAdaptiveSizerConfig(
        base_quantity=1,
        max_quantity_cap=1,
        tiers=[(30, 1.0), (60, 0.7), (80, 0.4), (100, 0.0)],
    ))
    qty = sizer.calculate(signal, balance, positions, market_context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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

    단일-임계값 모드 (주식, 기존 동작 유지):
        tiers가 비어 있을 때 활성화됨.
        risk_score_threshold_high / risk_score_penalty_high 파라미터를 사용.

    멀티-티어 스케일링 모드 (선물, Phase 1.3):
        tiers가 비어 있지 않을 때 활성화됨.
        단일-임계값 경로를 우회하고 티어별 스케일을 직접 적용.
        티어는 (risk_score_upper_bound, scale_multiplier) 쌍의 리스트로 구성하며,
        순서대로 평가하여 첫 번째 일치 티어를 사용한다.
        scale=0.0이면 진입 스킵(수량=0)을 의미한다.

    Attributes:
        # RiskBasedSizerConfig 상속 속성
        risk_per_trade_pct: 거래당 리스크 (계좌 대비 %)
        stop_loss_pct: 손절 비율 (진입가 대비 %)
        max_position_pct: 최대 포지션 비율
        max_positions: 최대 동시 보유 종목 수
        min_quantity: 최소 수량
        max_quantity: 최대 수량

        # LLM 적응형 파라미터 (단일-임계값 모드)
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

        # 멀티-티어 스케일링 파라미터 (Phase 1.3 — 선물)
        base_quantity: 티어 스케일링 전 기본 계약 수
        tiers: (risk_score_upper_bound, scale_multiplier) 쌍 리스트.
            비어 있으면 단일-임계값 모드(주식 호환)로 폴백.
            예: [(30, 1.0), (60, 0.7), (80, 0.4), (100, 0.0)]
            - risk_score <= 30  → ×1.0 (풀 사이즈)
            - 30 < risk_score <= 60 → ×0.7
            - 60 < risk_score <= 80 → ×0.4
            - risk_score > 80       → ×0.0 (진입 스킵)
        max_quantity_cap: 최종 수량의 상한 (계약 수). None이면 적용 안 함.
            선물 운용 시 futures_live.max_position_size_contracts와 동일한 값으로
            설정하여 order_router 캡과 함께 이중 방어선을 구성한다.
    """

    # Confidence 기반 스케일링
    confidence_threshold_high: float = 0.7
    confidence_threshold_low: float = 0.4
    confidence_boost_high: float = 1.2
    confidence_penalty_low: float = 0.7

    # Risk Score 기반 스케일링 (단일-임계값 모드)
    risk_score_threshold_high: float = 70.0  # 0-100 scale
    risk_score_penalty_high: float = 0.6

    # RiskMode 기반 스케일링
    risk_mode_scaling: dict[str, float] = field(
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

    # 멀티-티어 스케일링 (Phase 1.3 — 선물)
    base_quantity: int = 0
    """티어 스케일링 전 기본 계약 수. 0이면 RiskBasedSizer의 계산 결과를 사용."""

    tiers: list[tuple[float, float]] = field(default_factory=list)
    """(risk_score_upper_bound, scale_multiplier) 쌍 리스트.
    비어 있으면 단일-임계값 모드(주식 호환)로 폴백.
    YAML에서는 [[30, 1.0], [60, 0.7], [80, 0.4], [100, 0.0]] 형태로 작성.
    """

    max_quantity_cap: int | None = None
    """최종 수량 상한 (계약 수).
    선물 운용 시 futures_live.max_position_size_contracts 기본값(1)과 동일하게 설정하여
    order_router의 기존 캡 로직과 함께 이중 방어선을 구성한다.
    """

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMAdaptiveSizerConfig:
        """딕셔너리에서 생성

        Args:
            data: YAML params 딕셔너리

        Returns:
            LLMAdaptiveSizerConfig 인스턴스
        """
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

        # 멀티-티어 파라미터 (Phase 1.3)
        raw_tiers = data.get("tiers", [])
        tiers: list[tuple[float, float]] = [
            (float(pair[0]), float(pair[1])) for pair in raw_tiers
        ]

        raw_cap = data.get("max_quantity_cap")
        max_quantity_cap: int | None = int(raw_cap) if raw_cap is not None else None

        tier_params = {
            "base_quantity": int(data.get("base_quantity", 0)),
            "tiers": tiers,
            "max_quantity_cap": max_quantity_cap,
        }

        return cls(**base_params, **llm_params, **tier_params)


# =============================================================================
# LLM Adaptive Sizer
# =============================================================================


class LLMAdaptiveSizer(RiskBasedSizer):
    """LLM 적응형 포지션 사이저

    RiskBasedSizer를 확장하여 MarketContext 기반 동적 포지션 사이즈 조정.

    두 가지 운용 모드:

    1. 단일-임계값 모드 (tiers=[] — 주식 기존 동작):
        a. RiskBasedSizer로 기본 수량 계산
        b. MarketContext.confidence 기반 스케일링
           - High confidence (>= 0.7) → 1.2x boost
           - Low confidence (< 0.4) → 0.7x penalty
        c. MarketContext.risk_score 기반 스케일링
           - High risk (>= 70) → 0.6x penalty
        d. MarketContext.risk_mode 기반 스케일링
           - RISK_ON → 1.2x, NEUTRAL → 1.0x, RISK_OFF → 0.5x
        e. Final = base × confidence_mult × risk_mult × mode_mult

    2. 멀티-티어 스케일링 모드 (tiers 비어 있지 않음 — 선물 Phase 1.3):
        a. base_quantity(>0)가 있으면 그 값을 기본 수량으로 사용.
           없으면 RiskBasedSizer 계산 결과 사용.
        b. tiers에서 risk_score에 해당하는 scale_multiplier 조회
           (scale=0.0 → 진입 스킵, 수량=0)
        c. confidence / risk_mode 스케일링을 그 위에 추가로 적용
        d. max_quantity_cap으로 최종 수량 클램핑 (방어선 #1)
           order_router가 시그널 처리 전 동일 캡을 재적용 (방어선 #2)

    Graceful Degradation:
        - market_context가 None이면 RiskBasedSizer와 동일하게 동작
          (또는 base_quantity를 그대로 반환)
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
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],
        market_context: MarketContext | None = None,
    ) -> int:
        """포지션 크기 계산 (LLM 컨텍스트 기반 적응형)

        tiers가 설정되어 있으면 멀티-티어 스케일링 모드(선물)로 동작하고,
        그렇지 않으면 기존 단일-임계값 모드(주식)로 동작한다.

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션
            market_context: LLM 시장 분석 컨텍스트 (선택적)

        Returns:
            매매 수량 (0이면 진입 스킵)
        """
        c = self.config

        # 멀티-티어 모드 (Phase 1.3 — 선물)
        if c.tiers:
            return self._calculate_tier_mode(
                signal, account_balance, current_positions, market_context
            )

        # 단일-임계값 모드 (기존 주식 동작 — 하위 호환)
        return self._calculate_legacy_mode(
            signal, account_balance, current_positions, market_context
        )

    # ------------------------------------------------------------------
    # 멀티-티어 스케일링 (Phase 1.3 — 선물)
    # ------------------------------------------------------------------

    def _calculate_tier_mode(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],
        market_context: MarketContext | None,
    ) -> int:
        """멀티-티어 모드 계산

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션
            market_context: LLM 시장 분석 컨텍스트

        Returns:
            매매 수량 (0이면 진입 스킵)
        """
        c = self.config

        # 1. 기본 수량 결정
        if c.base_quantity > 0:
            base_quantity = c.base_quantity
        else:
            base_quantity = super().calculate(
                signal, account_balance, current_positions, market_context
            )

        if base_quantity == 0:
            return 0

        # 2. MarketContext 없으면 기본 수량 반환 (graceful degradation)
        if market_context is None:
            logger.debug(
                "LLMAdaptiveSizer[tier]: No market_context, "
                f"using base_quantity={base_quantity}"
            )
            final = self._apply_cap(base_quantity)
            return final

        # 3. 티어 스케일 조회 (risk_score 기반)
        tier_scale = self._lookup_tier_scale(market_context.risk_score)

        # scale=0.0 → 진입 스킵 (exit/stop은 정상 유지)
        if tier_scale == 0.0:
            logger.debug(
                f"LLMAdaptiveSizer[tier]: risk_score={market_context.risk_score:.1f} "
                f"→ scale=0.0, entry skip"
            )
            return 0

        # 4. tier_scale 적용 후 confidence/risk_mode 추가 스케일링
        #    티어가 이미 레짐 리스크를 반영하므로 risk_score 단일-임계값은 적용 안 함.
        #
        # 주의 (Gate-3 ladder 상호작용):
        #    base_quantity=1, max_quantity_cap=1 (현재 paper rollout 구성)에서는
        #    confidence/risk_mode가 부스트 방향이면 cap이 흡수, 페널티 방향이면
        #    int(0.x) → 0이 되어 진입 스킵된다. 두 경로 모두 안전.
        #
        #    Gate-3 ladder가 base_quantity를 2 이상으로 끌어올리면, RISK_OFF +
        #    낮은 confidence 조합이 `tier_scale * conf * mode` 누적으로
        #    예기치 않게 0으로 수렴할 수 있다. 운영자는 ladder 상승 시점에
        #    enable_confidence_scaling / enable_risk_mode_scaling 플래그를 끄거나
        #    base_quantity와 cap을 동기화해 의도된 사이즈가 보장되는지
        #    재검증해야 한다.
        confidence_mult = self._calculate_confidence_multiplier(market_context)
        risk_mode_mult = self._calculate_risk_mode_multiplier(market_context)

        total_multiplier = tier_scale * confidence_mult * risk_mode_mult
        adjusted_quantity = int(base_quantity * total_multiplier)

        # 5. int 절단으로 0이 된 경우는 수량 부족으로 그대로 진입 스킵.
        #    (별도 보강 로직은 두지 않는다 — base_quantity 또는 cap이 너무
        #    낮다는 신호이므로 운영자가 YAML을 조정해야 한다.)

        # 6. max_quantity_cap 적용 (방어선 #1)
        adjusted_quantity = self._apply_cap(adjusted_quantity)

        logger.debug(
            f"LLMAdaptiveSizer[tier]: base={base_quantity}, "
            f"risk_score={market_context.risk_score:.1f}, tier_scale={tier_scale:.2f}, "
            f"conf={confidence_mult:.2f}, mode={risk_mode_mult:.2f}, "
            f"total_mult={total_multiplier:.2f}, adjusted={adjusted_quantity}"
        )

        return adjusted_quantity

    def _lookup_tier_scale(self, risk_score: float) -> float:
        """risk_score에 해당하는 티어 scale_multiplier를 반환한다.

        티어를 순서대로 평가하여 risk_score <= upper_bound인 첫 번째 티어를 선택한다.
        **어떤 티어에도 해당하지 않으면 0.0을 반환**한다 — fail-safe로 진입을
        스킵한다. 이는 운영자가 ``[[30, 1.0], [60, 0.7], [80, 0.4], [100, 0.0]]``처럼
        100까지 명시적으로 정의했을 때 risk_score > 100 이라는 비정상 입력에
        대해 안전하게 대응하기 위함이다. 만약 운영자가 의도적으로 "최상위
        구간을 풀-사이즈"로 두고 싶다면 마지막 티어의 upper_bound를
        ``float("inf")``로 설정하거나, ``[[..., 1.0]]``처럼 catch-all을 끝에 추가해야 한다.

        Args:
            risk_score: 현재 LLM risk_score (0-100)

        Returns:
            해당 티어의 scale_multiplier (매칭 없을 시 0.0 fail-safe)
        """
        for upper_bound, scale in self.config.tiers:
            if risk_score <= upper_bound:
                return scale
        # 마지막 티어보다 높은 risk_score → 0.0 (진입 스킵 폴백, fail-safe)
        logger.debug(
            f"LLMAdaptiveSizer: risk_score={risk_score:.1f} exceeds all tier "
            f"upper_bounds; falling back to 0.0 (entry skip)"
        )
        return 0.0

    def _apply_cap(self, quantity: int) -> int:
        """max_quantity_cap이 설정된 경우 수량을 클램핑한다.

        Args:
            quantity: 캡 적용 전 수량

        Returns:
            캡 적용 후 수량
        """
        cap = self.config.max_quantity_cap
        if cap is not None and quantity > cap:
            logger.debug(
                f"LLMAdaptiveSizer: quantity={quantity} clamped to "
                f"max_quantity_cap={cap}"
            )
            return cap
        return quantity

    # ------------------------------------------------------------------
    # 단일-임계값 모드 (기존 주식 동작 — 하위 호환)
    # ------------------------------------------------------------------

    def _calculate_legacy_mode(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],
        market_context: MarketContext | None,
    ) -> int:
        """단일-임계값 모드 계산 (주식 기존 동작)

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션
            market_context: LLM 시장 분석 컨텍스트

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
        self, market_context: MarketContext
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
        self, market_context: MarketContext
    ) -> float:
        """Risk Score 기반 곱셈 계수 계산 (단일-임계값 모드 전용)

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
        self, market_context: MarketContext
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
