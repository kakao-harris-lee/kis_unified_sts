"""E3: Time Decay Exit Strategy

시간 기반 포지션 청산 전략.
오래 보유한 포지션에 대해 수익이 미달하면 청산합니다.

핵심 아이디어:
- 단타 전략은 빠른 수익 실현이 목표
- 오래 보유 = 예상대로 움직이지 않음 = 청산 고려
- 시간이 지날수록 기대 수익 threshold를 낮춤 (decay)

시간대별 기대 수익:
- 0~10분: 아무 조건 없음 (충분한 시간 제공)
- 10~20분: 손실이면 청산 (profit < 0)
- 20~30분: 수익 0.5% 미달 시 청산
- 30분+: 무조건 청산 (시간 초과)

Usage:
    exit_strategy = TimeDecayExit(config)
    should_exit, signal = await exit_strategy.should_exit(context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from shared.models.position import PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import now_kst, to_kst
from shared.strategy.registry import ExitRegistry

if TYPE_CHECKING:
    from shared.models.position import Position

logger = logging.getLogger(__name__)


@dataclass
class TimeDecayConfig:
    """E3 Time Decay 설정

    Attributes:
        decay_tiers: 시간대별 수익 threshold (minutes_start, required_profit_pct)
        max_hold_minutes: 최대 보유 시간 (분) - 이후 무조건 청산
        skip_maximize_state: MAXIMIZE 상태는 예외 처리 (수익 중)
        market_warmup_minutes: 장 시작 후 N분간 미적용
    """

    decay_tiers: list[tuple[int, float]] = field(
        default_factory=lambda: [
            (10, 0.0),  # 10분 이후: 손실이면 청산 (profit < 0)
            (20, 0.005),  # 20분 이후: +0.5% 미달 시 청산
        ]
    )
    max_hold_minutes: int = 30
    skip_maximize_state: bool = True
    market_warmup_minutes: int = 10

    @classmethod
    def from_dict(cls, data: dict) -> "TimeDecayConfig":
        """dict에서 설정 생성."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@ExitRegistry.register("time_decay")
class TimeDecayExit(ExitSignalGenerator[TimeDecayConfig]):
    """E3: 시간 기반 청산 전략

    포지션 보유 시간에 따라 기대 수익 threshold를 조정합니다.
    시간이 지날수록 더 빠르게 청산을 결정합니다.

    핵심 원리:
    - 모멘텀 전략은 빠른 수익이 목표
    - 예상대로 움직이지 않으면 → 빨리 손절하고 다음 기회
    - "시간은 비용"이라는 철학

    우선순위:
    - E1 HARD_STOP (priority=1) > E3 TIME_DECAY (priority=2) > E2 TRAILING (priority=2)
    """

    NAME = "TIME_DECAY_EXIT"
    VERSION = "E3"
    CONFIG_CLASS = TimeDecayConfig

    def __init__(self, config: TimeDecayConfig | dict):
        if isinstance(config, dict):
            config = TimeDecayConfig.from_dict(config)
        super().__init__(config)
        # decay_tiers를 정렬 (분 오름차순)
        self._decay_tiers = sorted(self.config.decay_tiers, key=lambda x: x[0])

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def version(self) -> str:
        return self.VERSION

    def _validate_config(self) -> None:
        """설정 유효성 검증."""
        c = self.config
        assert c.max_hold_minutes > 0, "max_hold_minutes must be positive"

    @property
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록."""
        return []  # 시간 기반이므로 지표 불필요

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
        snapshot = get_symbol_snapshot(context.market_data, position.code)
        current_price = get_price_from_snapshot(snapshot) or position.current_price

        # MAXIMIZE 상태 스킵 (수익 중이므로 E1/E2에 맡김)
        if self.config.skip_maximize_state and position.state == PositionState.MAXIMIZE:
            return False, None

        # 보유 시간 계산 (분)
        hold_duration = to_kst(context.timestamp) - to_kst(position.entry_time)
        hold_minutes = hold_duration.total_seconds() / 60

        # 현재가 확인
        if current_price <= 0:
            logger.warning(f"[{self.name}] {position.code}: No current price, skipping")
            return False, None

        # 손익 계산
        profit_pct = position.profit_rate

        # 1. 최대 보유 시간 초과 체크
        if hold_minutes >= self.config.max_hold_minutes:
            signal = self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                hold_minutes=hold_minutes,
                reason=f"MAX_HOLD exceeded: {hold_minutes:.1f}min",
            )
            return True, signal

        # 2. Decay tier 체크
        required_profit = self._get_required_profit(hold_minutes)

        if profit_pct < required_profit:
            signal = self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                hold_minutes=hold_minutes,
                reason=f"Time decay: profit={profit_pct:.2%} < required={required_profit:.2%}",
            )
            return True, signal

        return False, None

    async def scan_positions(
        self,
        positions: list["Position"],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 청산 시그널 스캔.

        Args:
            positions: 현재 보유 포지션 리스트
            market_data: 시장 데이터
            market_state: 시장 상태 (사용 안 함)

        Returns:
            ExitSignal 리스트
        """
        if not positions:
            return []

        signals = []
        now = now_kst()

        for position in positions:
            snapshot = get_symbol_snapshot(market_data, position.code)
            context = ExitContext(
                position=position,
                market_data={position.code: snapshot},
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
                f"triggered time decay exit"
            )

        return signals

    def _get_required_profit(self, hold_minutes: float) -> float:
        """보유 시간에 따른 필요 수익률 반환

        Args:
            hold_minutes: 보유 시간 (분)

        Returns:
            해당 시간대의 required_profit_pct (이 값 미달 시 청산)
        """
        required = -999.0  # 기본: 조건 없음

        for tier_minutes, tier_profit in self._decay_tiers:
            if hold_minutes >= tier_minutes:
                required = tier_profit
            else:
                break  # 정렬된 리스트이므로 이후 tier는 볼 필요 없음

        return required

    def _create_exit_signal(
        self,
        position: "Position",
        current_price: float,
        profit_pct: float,
        hold_minutes: float,
        reason: str,
    ) -> ExitSignal:
        """청산 시그널 생성."""
        profit_amount = (current_price - position.entry_price) * position.quantity

        logger.info(f"[{self.name}] {position.code}: {reason}")

        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=ExitReason.TIME_CUT,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=position.entry_price,
            profit_amount=profit_amount,
            profit_pct=profit_pct,
            confidence=0.7,
            priority=2,  # 중간 우선순위
            timestamp=now_kst(),
            stage=position.state.value if position.state else "",
            high_since_entry=position.highest_price or position.entry_price,
            holding_minutes=int(hold_minutes),
            quantity=position.quantity,
        )

    def get_config(self) -> dict[str, Any]:
        """전략 설정 반환"""
        return {
            "name": self.name,
            "version": self.version,
            "max_hold_minutes": self.config.max_hold_minutes,
            "decay_tiers": self._decay_tiers,
            "skip_maximize_state": self.config.skip_maximize_state,
            "market_warmup_minutes": self.config.market_warmup_minutes,
        }

    def get_decay_status(self, hold_minutes: float) -> dict[str, Any]:
        """디버깅용: 현재 보유 시간에 대한 decay 상태 반환"""
        required = self._get_required_profit(hold_minutes)

        current_tier = None
        next_tier = None

        for i, (tier_minutes, tier_profit) in enumerate(self._decay_tiers):
            if hold_minutes < tier_minutes:
                next_tier = (tier_minutes, tier_profit)
                break
            current_tier = (tier_minutes, tier_profit)

        time_to_next = None
        if next_tier:
            time_to_next = next_tier[0] - hold_minutes

        return {
            "hold_minutes": hold_minutes,
            "required_profit_pct": required,
            "current_tier": current_tier,
            "next_tier": next_tier,
            "time_to_next": time_to_next,
            "max_hold_remaining": max(0, self.config.max_hold_minutes - hold_minutes),
        }
