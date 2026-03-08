"""포지션 모델

포지션 상태 및 데이터 모델.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class PositionState(Enum):
    """포지션 상태 (3-Stage State Machine)

    Stage 1 (SURVIVAL): 진입 직후, 손절 대기
    Stage 2 (BREAKEVEN): 본전 확보, 본전 스탑
    Stage 3 (MAXIMIZE): 수익 극대화, 트레일링 스탑
    """

    SURVIVAL = "survival"
    BREAKEVEN = "breakeven"
    MAXIMIZE = "maximize"


class PositionSide(Enum):
    """포지션 방향"""

    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """포지션 데이터 모델

    Attributes:
        id: 포지션 고유 ID
        code: 종목 코드
        name: 종목명
        side: 포지션 방향 (long/short)
        quantity: 보유 수량
        entry_price: 진입 가격
        entry_time: 진입 시간
        current_price: 현재가
        highest_price: 진입 후 최고가
        lowest_price: 진입 후 최저가
        stop_price: 손절/스탑 가격
        state: 포지션 상태 (3-Stage)
        strategy: 진입 전략명
        fee_rate: 거래 수수료율
        execution_venue: 실행 거래소 (KRX/ATS)
    """

    id: str
    code: str
    name: str
    side: PositionSide
    quantity: int
    entry_price: float
    entry_time: datetime = field(default_factory=datetime.now)

    # 가격 추적
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float("inf")
    stop_price: float = 0.0

    # 상태
    state: PositionState = PositionState.SURVIVAL
    strategy: str = ""

    # 수수료 (설정에서 로드)
    fee_rate: float = 0.003  # 기본 0.3% (편도 0.15% * 2)
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_venue: str = "KRX"  # 실행 거래소 (KRX/ATS)

    # 청산 관련
    exit_triggered: bool = False
    exit_reason: Optional[str] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None

    def __post_init__(self):
        # 초기 최고/최저가 설정
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == float("inf"):
            self.lowest_price = self.entry_price
        if self.current_price == 0.0:
            self.current_price = self.entry_price

    def update_price(self, price: float):
        """가격 업데이트 및 최고/최저가 갱신"""
        self.current_price = price
        if price > self.highest_price:
            self.highest_price = price
        if price < self.lowest_price:
            self.lowest_price = price

    @property
    def profit_rate(self) -> float:
        """현재 수익률 (비율, 예: 0.05 = 5%)"""
        if self.entry_price <= 0:
            return 0.0

        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) / self.entry_price
        else:  # SHORT
            return (self.entry_price - self.current_price) / self.entry_price

    @property
    def profit_pct(self) -> float:
        """현재 수익률 (퍼센트, 예: 5.0 = 5%)"""
        return self.profit_rate * 100

    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익 (금액)"""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - self.current_price) * self.quantity

    def get_hold_duration(self) -> float:
        """보유 시간 (분)"""
        return (datetime.now() - self.entry_time).total_seconds() / 60

    def get_hold_duration_seconds(self) -> float:
        """보유 시간 (초)"""
        return (datetime.now() - self.entry_time).total_seconds()
