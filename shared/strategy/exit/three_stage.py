"""
3-Stage Dynamic Exit Strategy (통합)

quant_moment_sts의 ThreeStageExitStrategy를 통합 프로젝트용으로 마이그레이션.
모든 하드코딩된 값을 설정에서 받도록 리팩토링.

3-Stage State Machine:
    Stage 1 (SURVIVAL): 수익 < breakeven_threshold_pct
        - Hard Stop: 손실 stop_loss_pct 도달 시 즉시 청산

    Stage 2 (BREAKEVEN): 수익 >= breakeven_threshold_pct
        - Stop Price → 진입가 + 수수료 (본전 확보)

    Stage 3 (MAXIMIZE): 수익 >= maximize_threshold_pct
        - Trailing Stop: 최고가 대비 trailing_stop_pct 하락 시 청산
        - Overshooting: overshoot_threshold_pct 이상 급등 시 gap 축소

추가 청산 조건:
    - Time Cut: time_cut_minutes 경과 + 수익 없음
    - EOD Close: eod_close_time 강제 청산
    - BEAR Exit: 시장 하락 전환 시 전량 청산 (MarketState 연동)

Usage:
    # YAML에서 설정 로드
    config = ThreeStageExitConfig.from_yaml("config/exit/three_stage.yaml")
    exit_strategy = ThreeStageExit(config)

    # 청산 시그널 스캔
    signals = await exit_strategy.scan_positions(positions, market_data)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import TYPE_CHECKING, Any, Optional

from shared.models.position import Position, PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration (설정 기반 - 하드코딩 금지)
# =============================================================================


@dataclass
class ThreeStageExitConfig:
    """3-Stage Exit 설정

    모든 임계값은 이 설정에서 정의됨.
    YAML 설정 파일에서 로드하여 사용.

    Attributes:
        # Stage 1: Survival
        stop_loss_pct: 손절 임계값 (음수, 예: -0.015 = -1.5%)

        # Stage 2: Breakeven
        breakeven_threshold_pct: 본전 전환 임계값 (양수, 예: 0.015 = +1.5%)

        # Stage 3: Maximize
        maximize_threshold_pct: 수익 극대화 전환 임계값 (예: 0.03 = +3%)
        trailing_stop_pct: 트레일링 스탑 갭 (음수, 예: -0.03 = -3%)
        overshoot_threshold_pct: 급등 감지 임계값 (예: 0.07 = +7%)
        overshoot_trailing_pct: 급등 시 축소된 트레일링 갭 (예: -0.015 = -1.5%)

        # Time-based
        time_cut_minutes: 시간 손절 (분)
        eod_close_hour: 장 마감 시각 (시)
        eod_close_minute: 장 마감 시각 (분)

        # Fee
        fee_rate: 거래 수수료율 (예: 0.003 = 0.3%)

        # BEAR 시장 청산
        enable_bear_exit: BEAR 시장 시 청산 활성화
    """

    # Stage 1: Survival
    stop_loss_pct: float = -0.015  # -1.5%

    # Stage 2: Breakeven
    breakeven_threshold_pct: float = 0.015  # +1.5%

    # Stage 3: Maximize
    maximize_threshold_pct: float = 0.03  # +3%
    trailing_stop_pct: float = -0.03  # -3% from high
    overshoot_threshold_pct: float = 0.07  # +7%
    overshoot_trailing_pct: float = -0.015  # -1.5%

    # Time-based
    time_cut_minutes: int = 20
    eod_close_hour: int = 15
    eod_close_minute: int = 15

    # Fee
    fee_rate: float = 0.003  # 0.3%

    # BEAR 시장 청산
    enable_bear_exit: bool = True

    @property
    def eod_close_time(self) -> time:
        """장 마감 시각"""
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self):
        """설정 유효성 검증"""
        # Stage 1
        if self.stop_loss_pct >= 0:
            raise ValueError("stop_loss_pct must be negative")

        # Stage 2
        if self.breakeven_threshold_pct <= 0:
            raise ValueError("breakeven_threshold_pct must be positive")

        # Stage 3
        if self.maximize_threshold_pct <= self.breakeven_threshold_pct:
            raise ValueError(
                "maximize_threshold_pct must be greater than breakeven_threshold_pct"
            )
        if self.trailing_stop_pct >= 0:
            raise ValueError("trailing_stop_pct must be negative")
        if self.overshoot_trailing_pct >= 0:
            raise ValueError("overshoot_trailing_pct must be negative")
        if abs(self.overshoot_trailing_pct) >= abs(self.trailing_stop_pct):
            raise ValueError(
                "overshoot_trailing_pct should be tighter (smaller absolute value) "
                "than trailing_stop_pct"
            )

        # Time-based
        if self.time_cut_minutes <= 0:
            raise ValueError("time_cut_minutes must be positive")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThreeStageExitConfig:
        """딕셔너리에서 생성"""
        # 중첩된 구조 지원 (YAML에서 params 아래에 있을 수 있음)
        if "params" in data:
            data = data["params"]

        return cls(
            stop_loss_pct=data.get("stop_loss_pct", -0.015),
            breakeven_threshold_pct=data.get("breakeven_threshold_pct", 0.015),
            maximize_threshold_pct=data.get("maximize_threshold_pct", 0.03),
            trailing_stop_pct=data.get("trailing_stop_pct", -0.03),
            overshoot_threshold_pct=data.get("overshoot_threshold_pct", 0.07),
            overshoot_trailing_pct=data.get("overshoot_trailing_pct", -0.015),
            time_cut_minutes=data.get("time_cut_minutes", 20),
            eod_close_hour=data.get("eod_close_hour", 15),
            eod_close_minute=data.get("eod_close_minute", 15),
            fee_rate=data.get("fee_rate", 0.003),
            enable_bear_exit=data.get("enable_bear_exit", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "stop_loss_pct": self.stop_loss_pct,
            "breakeven_threshold_pct": self.breakeven_threshold_pct,
            "maximize_threshold_pct": self.maximize_threshold_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "overshoot_threshold_pct": self.overshoot_threshold_pct,
            "overshoot_trailing_pct": self.overshoot_trailing_pct,
            "time_cut_minutes": self.time_cut_minutes,
            "eod_close_hour": self.eod_close_hour,
            "eod_close_minute": self.eod_close_minute,
            "fee_rate": self.fee_rate,
            "enable_bear_exit": self.enable_bear_exit,
        }


# =============================================================================
# Three-Stage Exit Strategy
# =============================================================================


class ThreeStageExit(ExitSignalGenerator[ThreeStageExitConfig]):
    """3-Stage Dynamic Exit Strategy

    설정 기반의 3단계 동적 청산 전략.

    모든 임계값은 ThreeStageExitConfig에서 로드.
    하드코딩된 값 없이 완전히 설정 기반으로 동작.

    Usage:
        config = ThreeStageExitConfig(
            stop_loss_pct=-0.02,
            breakeven_threshold_pct=0.02,
            maximize_threshold_pct=0.05,
        )
        strategy = ThreeStageExit(config)

        # 단일 포지션 청산 체크
        should_exit, signal = await strategy.should_exit(context)

        # 여러 포지션 스캔
        signals = await strategy.scan_positions(positions, market_data)
    """

    NAME = "THREE_STAGE_EXIT"
    VERSION = "E1"
    DESCRIPTION = "3단계 동적 청산 전략 (Survival → Breakeven → Maximize)"
    CONFIG_CLASS = ThreeStageExitConfig  # For registry auto-conversion

    def __init__(self, config: ThreeStageExitConfig):
        super().__init__(config)

        # Concurrency protection: per-position locks
        self._position_locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

        logger.info(
            f"{self.name} ({self.version}) initialized: "
            f"stop_loss={config.stop_loss_pct:.1%}, "
            f"breakeven={config.breakeven_threshold_pct:.1%}, "
            f"maximize={config.maximize_threshold_pct:.1%}, "
            f"trailing={config.trailing_stop_pct:.1%}"
        )

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def version(self) -> str:
        return self.VERSION

    def _validate_config(self):
        """설정 유효성 검증"""
        self.config.validate()

    # -------------------------------------------------------------------------
    # Main Interface
    # -------------------------------------------------------------------------

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        """단일 포지션 청산 여부 판단

        Args:
            context: 청산 판단 컨텍스트

        Returns:
            (should_exit, signal): 청산 여부와 청산 시그널
        """
        signal = await self._check_position(
            position=context.position,
            market_data=context.market_data,
            market_state=context.market_state,
            now=context.timestamp,
        )

        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 청산 시그널 스캔

        Args:
            positions: 현재 보유 포지션 리스트
            market_data: 시장 데이터 (code -> price 매핑)
            market_state: 현재 시장 상태 (MarketClassifier 결과)

        Returns:
            ExitSignal 리스트 (청산 대상 포지션들)
        """
        if not positions:
            return []

        signals = []
        now = datetime.now()

        for position in positions:
            signal = await self._check_position(
                position=position,
                market_data=market_data,
                market_state=market_state,
                now=now,
            )
            if signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit signals"
            )

        return signals

    # -------------------------------------------------------------------------
    # Position Check Logic
    # -------------------------------------------------------------------------

    async def _check_position(
        self,
        position: Position,
        market_data: dict[str, Any],
        market_state: Optional[Any],
        now: datetime,
    ) -> Optional[ExitSignal]:
        """개별 포지션 청산 조건 체크

        우선순위:
            1. EOD Close
            2. BEAR 시장 청산
            3. Stage별 청산 조건 (Hard Stop, Breakeven, Trailing)
            4. Time Cut
        """
        # 현재가 조회
        current_price = self._get_current_price(position, market_data)
        if current_price is None:
            return None

        # 손익 계산
        profit_pct = (current_price - position.entry_price) / position.entry_price
        profit_amount = (current_price - position.entry_price) * position.quantity

        # 최고가
        high_since_entry = max(
            position.highest_price or position.entry_price, current_price
        )

        # 보유 시간 (분)
        holding_minutes = int((now - position.entry_time).total_seconds() / 60)

        # 현재 Stage 결정
        stage = self._determine_stage(position, profit_pct)

        # 1. EOD 체크 (최우선)
        if now.time() >= self.config.eod_close_time:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.EOD_CLOSE,
                priority=1,
                stage=stage,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        # 2. BEAR 시장 체크
        if self.config.enable_bear_exit and self._is_bear_market(market_state):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.BEAR_EXIT,
                priority=1,
                stage=stage,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        # 3. Stage별 청산 조건
        stage_exit = self._check_stage_exit(
            position=position,
            current_price=current_price,
            profit_pct=profit_pct,
            profit_amount=profit_amount,
            stage=stage,
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
        )
        if stage_exit:
            return stage_exit

        # 4. Time Cut (수익 없이 시간 초과)
        if (
            holding_minutes >= self.config.time_cut_minutes
            and profit_pct <= 0
        ):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TIME_CUT,
                priority=3,
                stage=stage,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        return None

    def _get_current_price(
        self, position: Position, market_data: dict[str, Any]
    ) -> Optional[float]:
        """현재가 조회"""
        # market_data에서 조회
        if market_data:
            # code -> price 매핑
            price = market_data.get(position.code)
            if price and price > 0:
                return price

            # 중첩 구조 (code -> {close: price})
            data = market_data.get(position.code, {})
            if isinstance(data, dict):
                price = data.get("close") or data.get("price")
                if price and price > 0:
                    return price

        # Position의 current_price 사용 (fallback)
        if position.current_price > 0:
            return position.current_price

        return None

    def _determine_stage(
        self, position: Position, profit_pct: float
    ) -> PositionState:
        """현재 수익률에 따른 Stage 결정"""
        # Position의 state 사용 (이미 관리되고 있다면)
        if position.state != PositionState.SURVIVAL:
            return position.state

        # profit_pct 기반 결정
        if profit_pct >= self.config.maximize_threshold_pct:
            return PositionState.MAXIMIZE
        elif profit_pct >= self.config.breakeven_threshold_pct:
            return PositionState.BREAKEVEN
        else:
            return PositionState.SURVIVAL

    def _is_bear_market(self, market_state: Any) -> bool:
        """BEAR 시장 여부 체크"""
        if market_state is None:
            return False

        if hasattr(market_state, "regime"):
            return market_state.regime in (
                "BEAR",
                "BEAR_STRONG",
                "BEAR_MODERATE",
            )
        if hasattr(market_state, "name"):
            return "BEAR" in market_state.name.upper()
        if hasattr(market_state, "value"):
            return "BEAR" in str(market_state.value).upper()

        return False

    # -------------------------------------------------------------------------
    # Stage-based Exit Logic
    # -------------------------------------------------------------------------

    def _check_stage_exit(
        self,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        stage: PositionState,
        high_since_entry: float,
        holding_minutes: int,
    ) -> Optional[ExitSignal]:
        """Stage별 청산 조건 체크

        Stage 1 (SURVIVAL): Hard Stop
        Stage 2 (BREAKEVEN): Breakeven Stop
        Stage 3 (MAXIMIZE): Trailing Stop
        """
        c = self.config  # 설정 참조 단축

        # Stage 1: SURVIVAL - Hard Stop
        if stage == PositionState.SURVIVAL:
            if profit_pct <= c.stop_loss_pct:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.STOP_LOSS,
                    priority=1,
                    stage=stage,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                )

        # Stage 2: BREAKEVEN - 본전 Stop
        elif stage == PositionState.BREAKEVEN:
            breakeven_price = position.entry_price * (1 + c.fee_rate)
            if current_price <= breakeven_price:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.BREAKEVEN_STOP,
                    priority=2,
                    stage=stage,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                )

        # Stage 3: MAXIMIZE - Trailing Stop
        elif stage == PositionState.MAXIMIZE:
            trailing_stop_price = self._calculate_trailing_stop(
                position=position,
                high_since_entry=high_since_entry,
            )
            if current_price <= trailing_stop_price:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.TRAILING_STOP,
                    priority=2,
                    stage=stage,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                )

        return None

    def _calculate_trailing_stop(
        self, position: Position, high_since_entry: float
    ) -> float:
        """Trailing Stop 가격 계산

        Overshooting 감지: 급등 시 gap 축소
        """
        c = self.config

        # 현재 수익률 (최고가 기준)
        gain_from_entry = (
            high_since_entry - position.entry_price
        ) / position.entry_price

        # Overshooting 체크: 급등 시 gap 축소
        if gain_from_entry >= c.overshoot_threshold_pct:
            gap = abs(c.overshoot_trailing_pct)
            logger.debug(
                f"[{position.code}] Overshooting detected ({gain_from_entry:.1%}), "
                f"trailing gap tightened to {gap:.1%}"
            )
        else:
            gap = abs(c.trailing_stop_pct)

        trailing_stop_price = high_since_entry * (1 - gap)

        # Position의 stop_price와 비교 (더 높은 값 유지)
        if position.stop_price > 0:
            trailing_stop_price = max(trailing_stop_price, position.stop_price)

        return trailing_stop_price

    # -------------------------------------------------------------------------
    # Signal Creation
    # -------------------------------------------------------------------------

    def _create_exit_signal(
        self,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        reason: ExitReason,
        priority: int,
        stage: PositionState,
        high_since_entry: float,
        holding_minutes: int,
    ) -> ExitSignal:
        """ExitSignal 생성"""
        confidence = self._calculate_confidence(reason, profit_pct, stage)

        logger.info(
            f"[{self.name}] Exit signal: {position.code} | "
            f"Reason: {reason.value} | "
            f"Stage: {stage.value} | "
            f"P/L: {profit_pct:+.2%}"
        )

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
            confidence=confidence,
            priority=priority,
            timestamp=datetime.now(),
            stage=stage.value,
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
        )

    def _calculate_confidence(
        self, reason: ExitReason, profit_pct: float, stage: PositionState
    ) -> float:
        """청산 확신도 계산

        Returns:
            0.0 ~ 1.0 사이의 확신도
        """
        # 손절/EOD/BEAR는 높은 확신도
        if reason in (
            ExitReason.STOP_LOSS,
            ExitReason.EOD_CLOSE,
            ExitReason.BEAR_EXIT,
        ):
            return 1.0

        # Trailing Stop은 수익률에 따라
        if reason == ExitReason.TRAILING_STOP:
            if profit_pct >= 0.05:  # 5% 이상 수익
                return 0.95
            elif profit_pct >= 0.03:  # 3% 이상 수익
                return 0.90
            return 0.85

        # Breakeven Stop
        if reason == ExitReason.BREAKEVEN_STOP:
            return 0.90

        # Time Cut
        if reason == ExitReason.TIME_CUT:
            return 0.70

        return 0.50

    # -------------------------------------------------------------------------
    # State Management (Thread-Safe)
    # -------------------------------------------------------------------------

    async def _get_position_lock(self, position_id: str) -> asyncio.Lock:
        """Position별 Lock 획득 (lazy initialization with double-checked locking)

        Args:
            position_id: 포지션 ID

        Returns:
            해당 포지션의 Lock
        """
        # Fast path: lock already exists
        if position_id in self._position_locks:
            return self._position_locks[position_id]

        # Slow path: create new lock (with double-checked locking)
        async with self._locks_lock:
            if position_id not in self._position_locks:
                self._position_locks[position_id] = asyncio.Lock()
            return self._position_locks[position_id]

    async def update_position_state(
        self, position: Position, current_price: float
    ) -> Optional[PositionState]:
        """Thread-safe 포지션 상태 업데이트 (State Transition)

        외부에서 호출하여 Position의 state를 업데이트.
        상태 전이가 발생하면 새로운 상태를 반환.

        동시에 여러 코루틴이 같은 포지션을 업데이트해도
        race condition이 발생하지 않도록 per-position lock 사용.

        Returns:
            새로운 상태 (전이 발생 시) 또는 None (전이 없음)
        """
        lock = await self._get_position_lock(position.id)
        async with lock:
            return self._update_position_state_internal(position, current_price)

    def _update_position_state_internal(
        self, position: Position, current_price: float
    ) -> Optional[PositionState]:
        """실제 상태 업데이트 로직 (lock 내에서 호출)

        Args:
            position: 업데이트할 포지션
            current_price: 현재 가격

        Returns:
            새로운 상태 (전이 발생 시) 또는 None (전이 없음)
        """
        c = self.config
        profit_pct = (current_price - position.entry_price) / position.entry_price
        old_state = position.state
        new_state = None

        # SURVIVAL → BREAKEVEN
        if (
            position.state == PositionState.SURVIVAL
            and profit_pct >= c.breakeven_threshold_pct
        ):
            position.state = PositionState.BREAKEVEN
            position.stop_price = position.entry_price * (1 + c.fee_rate)
            new_state = PositionState.BREAKEVEN

        # BREAKEVEN → MAXIMIZE
        elif (
            position.state == PositionState.BREAKEVEN
            and profit_pct >= c.maximize_threshold_pct
        ):
            position.state = PositionState.MAXIMIZE
            new_state = PositionState.MAXIMIZE

        if new_state:
            logger.info(
                f"[{self.name}] State transition: {position.code} "
                f"{old_state.value} → {new_state.value}"
            )

        return new_state

    def cleanup_position(self, position_id: str) -> None:
        """포지션 종료 시 lock 정리 (메모리 누수 방지)

        Args:
            position_id: 정리할 포지션 ID
        """
        self._position_locks.pop(position_id, None)

    def get_config(self) -> dict[str, Any]:
        """설정 반환"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.DESCRIPTION,
            **self.config.to_dict(),
        }
