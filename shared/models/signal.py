"""시그널 모델

진입/청산 시그널 데이터 모델.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SignalType(Enum):
    """시그널 유형"""

    ENTRY = "entry"
    EXIT = "exit"


class ExitReason(Enum):
    """청산 사유

    각 청산 사유는 우선순위와 함께 정의됨.
    """

    # Stage 1: Survival
    STOP_LOSS = "stop_loss"  # 손절

    # Stage 2: Breakeven
    BREAKEVEN_STOP = "breakeven_stop"  # 본전 스탑

    # Stage 3: Maximize
    TRAILING_STOP = "trailing_stop"  # 트레일링 스탑

    # Time-based
    TIME_CUT = "time_cut"  # 시간 손절
    EOD_CLOSE = "eod_close"  # 장 마감

    # Market-based
    BEAR_EXIT = "bear_exit"  # 하락장 청산

    # Indicator-based
    INDICATOR_EXIT = "indicator_exit"  # 지표 기반 청산 (예: StochRSI)
    MOMENTUM_DECAY = "momentum_decay"  # 모멘텀 소진 청산
    VWAP_BREAKDOWN = "vwap_breakdown"  # VWAP 이탈 청산

    # RL model-based
    RL_EXIT = "rl_exit"  # RL 모델 청산 시그널

    # Manual
    MANUAL_CLOSE = "manual_close"  # 수동 청산
    FORCE_CLOSE = "force_close"  # 강제 청산


@dataclass
class Signal:
    """진입 시그널

    Attributes:
        code: 종목 코드
        name: 종목명
        signal_type: 시그널 유형
        strategy: 전략명
        price: 시그널 발생 가격
        quantity: 수량 (계산된 포지션 크기)
        confidence: 확신도 (0.0 ~ 1.0)
        timestamp: 시그널 발생 시간
        metadata: 추가 메타데이터
    """

    code: str
    name: str = ""
    signal_type: SignalType = SignalType.ENTRY
    strategy: str = ""
    price: float = 0.0
    quantity: int = 0
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExitSignal:
    """청산 시그널

    Attributes:
        code: 종목 코드
        name: 종목명
        position_id: 포지션 ID
        reason: 청산 사유
        strategy: 청산 전략명
        current_price: 현재가
        exit_price: 청산 예상 가격
        entry_price: 진입가 (수익률 계산용)
        profit_amount: 예상 손익 금액
        profit_pct: 예상 손익률 (비율)
        confidence: 청산 확신도 (0.0 ~ 1.0)
        priority: 우선순위 (1: 최우선)
        timestamp: 시그널 발생 시간
        stage: 포지션 상태 (survival/breakeven/maximize)
        high_since_entry: 진입 후 최고가
        holding_minutes: 보유 시간 (분)
        quantity: 청산 수량
        metadata: 추가 메타데이터
    """

    code: str
    name: str = ""
    position_id: str = ""
    reason: ExitReason = ExitReason.MANUAL_CLOSE
    strategy: str = ""
    current_price: float = 0.0
    exit_price: float = 0.0
    entry_price: float = 0.0
    profit_amount: float = 0.0
    profit_pct: float = 0.0
    confidence: float = 0.5
    priority: int = 3
    timestamp: datetime = field(default_factory=datetime.now)
    stage: str = ""
    high_since_entry: float = 0.0
    holding_minutes: int = 0
    quantity: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def profit_pct_display(self) -> str:
        """표시용 수익률 문자열"""
        return f"{self.profit_pct:+.2%}"

    @property
    def is_profitable(self) -> bool:
        """수익 여부"""
        return self.profit_pct > 0
