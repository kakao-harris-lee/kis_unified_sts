"""E4: Market Regime Exit Strategy

시장 상태 기반 청산 전략.
MarketClassifier의 시장 상태에 따라 청산 조건을 동적으로 조정합니다.

핵심 아이디어:
- BEAR 시장: 즉시 청산 (수익/손실 무관)
- SIDEWAYS_DOWN: 손실 시 즉시 청산, 수익도 빠른 청산
- SIDEWAYS_FLAT: 보수적 청산 (낮은 수익 목표)
- BULL: 관대한 청산 (높은 수익 목표, E1/E2에 맡김)

시장 상태별 행동:
- BEAR_STRONG:     즉시 청산 (시장 급락)
- BEAR_MODERATE:   즉시 청산 (하락 추세)
- SIDEWAYS_DOWN:   손실 시 청산, 수익 +0.5% 목표
- SIDEWAYS_FLAT:   손실 시 청산, 수익 +1% 목표
- SIDEWAYS_UP:     스킵 (E1/E2에 맡김)
- BULL_*:          스킵 (E1/E2에 맡김)

Usage:
    classifier = MarketClassifier()
    exit_strategy = MarketRegimeExit(config, market_classifier=classifier)
    should_exit, signal = await exit_strategy.should_exit(context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from shared.models.position import PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator
from shared.strategy.market_classifier import MarketClassifier, MarketState
from shared.strategy.registry import ExitRegistry

if TYPE_CHECKING:
    from shared.models.position import Position

logger = logging.getLogger(__name__)


@dataclass
class MarketRegimeConfig:
    """E4 Market Regime 설정

    Attributes:
        regime_thresholds: 시장 상태별 필요 수익률
            -999.0 = 조건 없음 (스킵)
            0.0 = 손실 시 청산
            양수 = 해당 수익 미달 시 청산
        immediate_exit_states: 즉시 청산 상태 (조건 무시)
        exit_maximize_in_bear: MAXIMIZE 상태에서도 BEAR 청산 적용 여부
    """

    regime_thresholds: dict[MarketState, float] = field(
        default_factory=lambda: {
            MarketState.BEAR_STRONG: 999.0,  # 무조건 청산
            MarketState.BEAR_MODERATE: 999.0,  # 무조건 청산
            MarketState.SIDEWAYS_DOWN: 0.005,  # +0.5% 미달 시 청산
            MarketState.SIDEWAYS_FLAT: 0.0,  # 손실 시 청산
            MarketState.SIDEWAYS_UP: -999.0,  # 스킵 (E1/E2에 맡김)
            MarketState.BULL_MODERATE: -999.0,  # 스킵
            MarketState.BULL_STRONG: -999.0,  # 스킵
            MarketState.UNKNOWN: -999.0,  # 스킵
        }
    )
    immediate_exit_states: list[MarketState] = field(
        default_factory=lambda: [
            MarketState.BEAR_STRONG,
            MarketState.BEAR_MODERATE,
        ]
    )
    exit_maximize_in_bear: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "MarketRegimeConfig":
        """dict에서 설정 생성."""
        # regime_thresholds 변환 (str -> MarketState)
        if "regime_thresholds" in data:
            thresholds = {}
            for key, value in data["regime_thresholds"].items():
                if isinstance(key, str):
                    thresholds[MarketState(key)] = value
                else:
                    thresholds[key] = value
            data = {**data, "regime_thresholds": thresholds}

        # immediate_exit_states 변환
        if "immediate_exit_states" in data:
            states = []
            for s in data["immediate_exit_states"]:
                if isinstance(s, str):
                    states.append(MarketState(s))
                else:
                    states.append(s)
            data = {**data, "immediate_exit_states": states}

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@ExitRegistry.register("market_regime")
class MarketRegimeExit(ExitSignalGenerator[MarketRegimeConfig]):
    """E4: 시장 상태 기반 청산 전략

    MarketClassifier가 감지한 시장 상태에 따라 청산 조건을 조정합니다.
    BEAR 시장에서는 즉시 청산하여 손실을 최소화합니다.

    우선순위:
    - E4 BEAR_EXIT (priority=1) = E1 HARD_STOP (긴급)
    - E4 VOLATILITY_EXIT (priority=2) = E2/E3 (일반)

    사용 시나리오:
    1. 장 중 KOSPI 급락 → BEAR_STRONG 감지 → 모든 포지션 즉시 청산
    2. 횡보 하락장 → 수익 없으면 빠르게 정리
    3. 상승장 → 전략적 청산은 E1/E2에 맡김
    """

    NAME = "MARKET_REGIME_EXIT"
    VERSION = "E4"
    CONFIG_CLASS = MarketRegimeConfig

    def __init__(
        self,
        config: MarketRegimeConfig | dict,
        market_classifier: Optional[MarketClassifier] = None,
    ):
        if isinstance(config, dict):
            config = MarketRegimeConfig.from_dict(config)
        super().__init__(config)
        self._classifier = market_classifier or MarketClassifier()

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def version(self) -> str:
        return self.VERSION

    def _validate_config(self) -> None:
        """설정 유효성 검증."""
        pass  # 기본 설정으로도 동작 가능

    @property
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록."""
        return ["mfi", "adx"]

    def set_market_classifier(self, classifier: MarketClassifier) -> None:
        """MarketClassifier 설정 (지연 주입)"""
        self._classifier = classifier
        logger.info(f"[{self.name}] MarketClassifier set")

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        """청산 여부 판단.

        Args:
            context: 청산 판단 컨텍스트

        Returns:
            (should_exit, signal) 튜플
        """
        position = context.position
        market_state = context.market_state
        current_price = context.market_data.get("close", position.current_price)

        # 시장 상태가 없으면 스킵
        if market_state is None:
            logger.debug(f"[{self.name}] No market_state provided, skipping")
            return False, None

        # MarketState로 변환 (필요시)
        if isinstance(market_state, str):
            try:
                market_state = MarketState(market_state)
            except ValueError:
                logger.warning(
                    f"[{self.name}] Unknown market_state: {market_state}, skipping"
                )
                return False, None

        # 1. 즉시 청산 상태 체크 (BEAR)
        if market_state in self.config.immediate_exit_states:
            # MAXIMIZE 상태 체크
            if position.state == PositionState.MAXIMIZE:
                if not self.config.exit_maximize_in_bear:
                    logger.debug(
                        f"[{self.name}] {position.code}: MAXIMIZE state, "
                        f"skipping bear exit (config)"
                    )
                    return False, None

            signal = self._create_exit_signal(
                position=position,
                current_price=current_price,
                market_state=market_state,
                reason=ExitReason.BEAR_EXIT,
                priority=1,  # 긴급 우선순위
                message=f"BEAR market detected: {market_state.value}",
            )
            return True, signal

        # 2. Regime 기반 수익 threshold 체크
        required_profit = self.config.regime_thresholds.get(market_state, -999.0)

        # -999.0 = 스킵 (E1/E2에 맡김)
        if required_profit <= -999.0:
            return False, None

        # 현재가 확인
        if current_price <= 0:
            logger.warning(f"[{self.name}] {position.code}: No current price, skipping")
            return False, None

        # 손익 계산
        profit_pct = position.profit_rate

        # Threshold 체크
        if profit_pct < required_profit:
            signal = self._create_exit_signal(
                position=position,
                current_price=current_price,
                market_state=market_state,
                reason=ExitReason.BEAR_EXIT,
                priority=2,  # 일반 우선순위
                message=(
                    f"Regime exit: {market_state.value}, "
                    f"profit={profit_pct:.2%} < required={required_profit:.2%}"
                ),
            )
            return True, signal

        return False, None

    async def scan_positions(
        self,
        positions: list["Position"],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 시장 상태 기반 청산 시그널 스캔.

        Args:
            positions: 현재 보유 포지션 리스트
            market_data: 시장 데이터
            market_state: 현재 시장 상태 (필수!)

        Returns:
            ExitSignal 리스트
        """
        if not positions:
            return []

        # 시장 상태가 없으면 스킵
        if market_state is None:
            logger.debug(f"[{self.name}] No market_state provided, skipping")
            return []

        signals = []
        now = datetime.now()

        for position in positions:
            context = ExitContext(
                position=position,
                market_data=market_data,
                indicators={},
                timestamp=now,
                market_state=market_state,
            )
            should_exit, signal = await self.should_exit(context)
            if should_exit and signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit (market={market_state})"
            )

        return signals

    def _create_exit_signal(
        self,
        position: "Position",
        current_price: float,
        market_state: MarketState,
        reason: ExitReason,
        priority: int,
        message: str,
    ) -> ExitSignal:
        """청산 시그널 생성."""
        profit_pct = position.profit_rate
        profit_amount = (current_price - position.entry_price) * position.quantity
        hold_duration = datetime.now() - position.entry_time
        holding_minutes = int(hold_duration.total_seconds() / 60)

        logger.info(f"[{self.name}] {position.code}: {message}")

        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=reason,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=position.entry_price,
            profit_amount=profit_amount,
            profit_pct=profit_pct,
            confidence=0.8 if reason == ExitReason.BEAR_EXIT else 0.6,
            priority=priority,
            timestamp=datetime.now(),
            stage=position.state.value if position.state else "",
            high_since_entry=position.highest_price or position.entry_price,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
        )

    def get_config(self) -> dict[str, Any]:
        """전략 설정 반환"""
        return {
            "name": self.name,
            "version": self.version,
            "immediate_exit_states": [s.value for s in self.config.immediate_exit_states],
            "exit_maximize_in_bear": self.config.exit_maximize_in_bear,
            "regime_thresholds": {
                s.value: v for s, v in self.config.regime_thresholds.items()
            },
        }

    def get_regime_action(self, market_state: MarketState) -> dict[str, Any]:
        """디버깅용: 시장 상태에 대한 전략 행동 반환"""
        if market_state in self.config.immediate_exit_states:
            return {
                "market_state": market_state.value,
                "action": "immediate_exit",
                "required_profit_pct": None,
                "exit_reason": ExitReason.BEAR_EXIT.value,
                "priority": 1,
            }

        required = self.config.regime_thresholds.get(market_state, -999.0)

        if required <= -999.0:
            return {
                "market_state": market_state.value,
                "action": "skip",
                "required_profit_pct": None,
                "exit_reason": None,
                "priority": None,
            }

        return {
            "market_state": market_state.value,
            "action": "conditional_exit",
            "required_profit_pct": required,
            "exit_reason": ExitReason.BEAR_EXIT.value,
            "priority": 2,
        }
