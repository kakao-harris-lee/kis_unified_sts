"""포지션 사이징 전략 구현

고정 수량 및 리스크 기반 포지션 사이징.

Usage:
    # 고정 수량
    sizer = FixedSizer(FixedSizerConfig(fixed_quantity=100))
    qty = sizer.calculate(signal, balance, positions)

    # 리스크 기반
    sizer = RiskBasedSizer(RiskBasedSizerConfig(risk_per_trade_pct=1.0))
    qty = sizer.calculate(signal, balance, positions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shared.strategy.base import PositionSizer

if TYPE_CHECKING:
    from shared.models.position import Position
    from shared.models.signal import Signal

logger = logging.getLogger(__name__)


# =============================================================================
# Fixed Sizer
# =============================================================================


@dataclass
class FixedSizerConfig:
    """고정 수량 사이저 설정

    Attributes:
        fixed_quantity: 고정 수량 (주식 수 또는 계약 수)
        fixed_amount: 고정 금액 (원)
        max_position_pct: 최대 포지션 비율 (계좌 대비 %)
        max_positions: 최대 동시 보유 종목 수
    """

    fixed_quantity: int = 0
    fixed_amount: float = 1_000_000  # 100만원
    max_position_pct: float = 10.0  # 10%
    max_positions: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixedSizerConfig:
        """딕셔너리에서 생성"""
        return cls(
            fixed_quantity=data.get("fixed_quantity", data.get("contracts", 0)),
            fixed_amount=data.get(
                "fixed_amount", data.get("order_amount_per_stock", 1_000_000)
            ),
            max_position_pct=data.get("max_position_pct", 10.0),
            max_positions=data.get("max_positions", 5),
        )


class FixedSizer(PositionSizer[FixedSizerConfig]):
    """고정 수량 포지션 사이저

    설정된 고정 수량 또는 금액으로 포지션 크기 결정.
    """

    CONFIG_CLASS = FixedSizerConfig

    def calculate(
        self,
        signal: "Signal",
        account_balance: float,
        current_positions: list["Position"],
    ) -> int:
        """포지션 크기 계산

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션

        Returns:
            매매 수량
        """
        c = self.config

        # 최대 포지션 수 체크
        if len(current_positions) >= c.max_positions:
            logger.debug(f"Max positions reached: {len(current_positions)}")
            return 0

        # 고정 수량이 설정된 경우
        if c.fixed_quantity > 0:
            return c.fixed_quantity

        # 고정 금액으로 계산
        price = signal.price
        if price <= 0:
            return 0

        # 최대 포지션 비율 체크
        max_amount = account_balance * (c.max_position_pct / 100)
        amount = min(c.fixed_amount, max_amount)

        quantity = int(amount / price)

        logger.debug(
            f"FixedSizer: amount={amount:,.0f}, price={price:,.0f}, qty={quantity}"
        )
        return quantity


# =============================================================================
# Risk Based Sizer
# =============================================================================


@dataclass
class RiskBasedSizerConfig:
    """리스크 기반 사이저 설정

    Attributes:
        risk_per_trade_pct: 거래당 리스크 (계좌 대비 %)
        stop_loss_pct: 손절 비율 (진입가 대비 %)
        max_position_pct: 최대 포지션 비율
        max_positions: 최대 동시 보유 종목 수
        min_quantity: 최소 수량
        max_quantity: 최대 수량
    """

    risk_per_trade_pct: float = 1.0  # 1%
    stop_loss_pct: float = 2.0  # 2%
    max_position_pct: float = 10.0  # 10%
    max_positions: int = 5
    min_quantity: int = 1
    max_quantity: int = 10000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskBasedSizerConfig:
        """딕셔너리에서 생성"""
        return cls(
            risk_per_trade_pct=data.get("risk_per_trade_pct", 1.0),
            stop_loss_pct=abs(data.get("stop_loss_pct", 2.0)),  # 양수로 변환
            max_position_pct=data.get("max_position_pct", 10.0),
            max_positions=data.get("max_positions", 5),
            min_quantity=data.get("min_quantity", 1),
            max_quantity=data.get("max_quantity", 10000),
        )


class RiskBasedSizer(PositionSizer[RiskBasedSizerConfig]):
    """리스크 기반 포지션 사이저

    손절 폭과 리스크 허용치로 포지션 크기 결정.

    Formula:
        risk_amount = account_balance * (risk_per_trade_pct / 100)
        loss_per_share = price * (stop_loss_pct / 100)
        quantity = risk_amount / loss_per_share
    """

    CONFIG_CLASS = RiskBasedSizerConfig

    def calculate(
        self,
        signal: "Signal",
        account_balance: float,
        current_positions: list["Position"],
    ) -> int:
        """포지션 크기 계산

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션

        Returns:
            매매 수량
        """
        c = self.config

        # 최대 포지션 수 체크
        if len(current_positions) >= c.max_positions:
            logger.debug(f"Max positions reached: {len(current_positions)}")
            return 0

        price = signal.price
        if price <= 0:
            return 0

        # 리스크 금액 계산
        risk_amount = account_balance * (c.risk_per_trade_pct / 100)

        # 시그널에서 손절 비율 가져오기 (없으면 기본값 사용)
        stop_loss_pct = signal.metadata.get("stop_loss_pct", c.stop_loss_pct)
        if stop_loss_pct <= 0:
            stop_loss_pct = c.stop_loss_pct

        # 주당 손실 금액
        loss_per_share = price * (stop_loss_pct / 100)
        if loss_per_share <= 0:
            return 0

        # 수량 계산
        quantity = int(risk_amount / loss_per_share)

        # 최대 포지션 비율 체크
        max_amount = account_balance * (c.max_position_pct / 100)
        max_qty_by_position = int(max_amount / price)
        quantity = min(quantity, max_qty_by_position)

        # 최소/최대 수량 제한
        quantity = max(c.min_quantity, min(quantity, c.max_quantity))

        logger.debug(
            f"RiskBasedSizer: risk={risk_amount:,.0f}, "
            f"stop={stop_loss_pct:.1f}%, qty={quantity}"
        )
        return quantity
