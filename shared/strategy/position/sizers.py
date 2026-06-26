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
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.config.mixins import ConfigMixin
from shared.strategy.base import PositionSizer
from shared.strategy.registry import SizerRegistry

if TYPE_CHECKING:
    from shared.execution.contract_spec import ContractSpec
    from shared.llm.market_context import MarketContext
    from shared.models.position import Position
    from shared.models.signal import Signal
    from shared.risk.state import RiskStateSnapshot

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
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],
        market_context: MarketContext | None = None,
    ) -> int:
        """포지션 크기 계산

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션
            market_context: LLM 시장 분석 컨텍스트 (선택적)

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
        try:
            multiplier = float(
                signal.metadata.get("position_size_multiplier", 1.0) or 1.0
            )
        except (TypeError, ValueError):
            multiplier = 1.0
        amount *= max(0.0, min(1.0, multiplier))

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
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],
        market_context: MarketContext | None = None,
    ) -> int:
        """포지션 크기 계산

        Args:
            signal: 진입 시그널
            account_balance: 계좌 잔고
            current_positions: 현재 보유 포지션
            market_context: LLM 시장 분석 컨텍스트 (선택적)

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


# =============================================================================
# Fixed Fractional Futures Sizer
# =============================================================================


class FixedFractionalFuturesConfig(ServiceConfigBase):
    """선물 고정 비율 사이저 설정

    Attributes:
        max_position_risk_pct: 계좌 대비 최대 리스크 비율 (예: 0.015 = 1.5%)
        max_position_size: 최대 계약 수 (계좌 크기 무관 상한)
        soft_reduce_threshold: 연속 손실 횟수 도달 시 포지션 절반으로 축소

    Loaded from ``config/risk.yaml`` under the ``fixed_fractional_futures``
    section when using ``from_yaml()``. Field defaults match the values
    previously hardcoded in the Phase 3 spec §7.
    """

    _default_config_file: ClassVar[str] = "risk.yaml"
    _default_section: ClassVar[str] = "fixed_fractional_futures"

    max_position_risk_pct: float = Field(
        default=0.015, description="Maximum risk as fraction of equity per trade"
    )
    max_position_size: int = Field(
        default=2, description="Hard cap on contracts regardless of equity"
    )
    soft_reduce_threshold: int = Field(
        default=4, description="Consecutive losses that trigger 50% position reduction"
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixedFractionalFuturesConfig:
        """딕셔너리에서 생성 — 기존 코드 호환용 shim.

        Prefer :meth:`from_yaml` for new callers.
        """
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


@SizerRegistry.register("fixed_fractional_futures")
class FixedFractionalFuturesSizer(PositionSizer["FixedFractionalFuturesConfig"]):
    """선물 계약용 고정 비율 포지션 사이저

    진입가와 손절가 간 거리를 기반으로 계약당 리스크(KRW)를 계산하고,
    계좌 자산 대비 최대 리스크 비율에 맞게 계약 수를 결정한다.

    Args:
        config: FixedFractionalFuturesConfig 설정 객체
        contract_spec: 선물 계약 스펙 (승수, 틱 크기 등)
        state_snapshot: 리스크 상태 스냅샷 (연속 손실 감지용, 선택적)

    Formula:
        stop_distance_points = |entry_price - stop_loss|
        krw_per_contract = stop_distance_points × multiplier_krw_per_point
        target_risk_krw = account_equity_krw × max_position_risk_pct
        raw_size = target_risk_krw / max(krw_per_contract, 1.0)
        size = clamp(int(raw_size), 1, max_position_size)
        if consecutive_losses >= soft_reduce_threshold:
            size = max(1, size // 2)
    """

    CONFIG_CLASS = FixedFractionalFuturesConfig

    def __init__(
        self,
        config: FixedFractionalFuturesConfig,
        contract_spec: ContractSpec | None = None,
        state_snapshot: RiskStateSnapshot | None = None,
    ) -> None:
        super().__init__(config)
        self.spec = contract_spec
        self.state = state_snapshot

    def calculate(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],  # noqa: ARG002
        market_context: MarketContext | None = None,  # noqa: ARG002
    ) -> int:
        """선물 포지션 계약 수 계산

        Args:
            signal: 진입 시그널 (entry_price, stop_loss 필드 사용)
            account_balance: 계좌 자산 총액 (KRW)
            current_positions: 현재 보유 포지션 (미사용, 인터페이스 호환용)
            market_context: LLM 시장 분석 컨텍스트 (미사용, 인터페이스 호환용)

        Returns:
            계약 수 (최소 1, 최대 max_position_size)
        """
        c = self.config

        # 손절 거리 계산 (포인트 단위)
        stop_distance_points = abs(signal.entry_price - signal.stop_loss)

        # 계약당 리스크 (KRW)
        multiplier = self.spec.multiplier_krw_per_point if self.spec is not None else 1
        krw_per_contract = stop_distance_points * multiplier

        # 목표 리스크 금액 (KRW)
        target_risk_krw = account_balance * c.max_position_risk_pct

        # 계약 수 계산 (0 나눗셈 방지를 위해 1.0 하한)
        raw_size = target_risk_krw / max(krw_per_contract, 1.0)
        size = max(1, min(int(raw_size), c.max_position_size))

        # 연속 손실 감지 시 절반으로 축소
        if (
            self.state is not None
            and self.state.consecutive_losses >= c.soft_reduce_threshold
        ):
            size = max(1, size // 2)

        logger.debug(
            f"FixedFractionalFuturesSizer: stop_dist={stop_distance_points:.4f}pts, "
            f"krw/contract={krw_per_contract:,.0f}, target_risk={target_risk_krw:,.0f}, "
            f"raw={raw_size:.2f} → size={size}"
        )
        return size


# =============================================================================
# Volatility-Target Futures Sizer (CTA)
# =============================================================================


@dataclass
class VolatilityTargetFuturesConfig(ConfigMixin):
    """Volatility-targeted futures sizer settings (CTA / managed-futures).

    Sizes contracts so the position's *ex-ante* annualised volatility matches a
    target, the canonical CTA risk-normalisation. A trending instrument with low
    vol gets more contracts; a choppy high-vol instrument gets fewer — equalising
    risk per position across regimes.

    Attributes:
        target_annual_vol: Target annualised volatility as a fraction of equity
            (0.15 = 15%). The notional is scaled so realised vol ≈ this.
        point_value_krw: Futures multiplier (KRW per index point). KOSPI200
            futures = 50,000. Overridable so other contracts can reuse the sizer.
        max_contracts: Hard cap on contracts regardless of equity (paper safety).
        min_contracts: Floor; 0 means "no trade" is allowed when vol too high.
        trading_days_per_year: Annualisation factor for daily vol → annual.
        vol_floor: Minimum daily-return vol to divide by (0-vol guard).
    """

    target_annual_vol: float = 0.15
    point_value_krw: float = 50_000.0
    max_contracts: int = 5
    min_contracts: int = 0
    trading_days_per_year: int = 252
    vol_floor: float = 1e-6

    def validate(self) -> None:
        if self.target_annual_vol <= 0:
            raise ValueError("target_annual_vol must be positive")
        if self.point_value_krw <= 0:
            raise ValueError("point_value_krw must be positive")
        if self.max_contracts < 1:
            raise ValueError("max_contracts must be >= 1")
        if self.min_contracts < 0 or self.min_contracts > self.max_contracts:
            raise ValueError("require 0 <= min_contracts <= max_contracts")
        if self.trading_days_per_year <= 0:
            raise ValueError("trading_days_per_year must be positive")
        if self.vol_floor <= 0:
            raise ValueError("vol_floor must be positive")


@SizerRegistry.register("volatility_target_futures")
class VolatilityTargetFuturesSizer(PositionSizer["VolatilityTargetFuturesConfig"]):
    """Volatility-targeted contract sizing for daily CTA futures strategies.

    Reads the instrument's daily-return volatility from ``signal.metadata``
    (``daily_return_vol`` annualised, or ``daily_return_vol_daily`` per-day which
    is annualised here). Falls back to an ATR-implied vol
    (``entry_atr`` / price × sqrt(trading_days_per_year)) when no explicit vol is
    present, so the sizer degrades gracefully.

    Formula::

        ann_vol      = max(daily_return_vol, vol_floor)        # annualised
        target_krw   = equity × target_annual_vol               # risk budget
        notional/ct  = price × point_value_krw
        raw          = target_krw / (ann_vol × notional_per_contract)
        size         = clamp(round(raw), min_contracts, max_contracts)

    Direction is carried by the signal (``signal_direction``); the sizer returns a
    non-negative contract count and is fully long/short symmetric.
    """

    CONFIG_CLASS = VolatilityTargetFuturesConfig

    def calculate(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],  # noqa: ARG002
        market_context: MarketContext | None = None,  # noqa: ARG002
    ) -> int:
        c = self.config
        meta = signal.metadata or {}
        price = float(signal.price or meta.get("entry_price", 0.0) or 0.0)
        if price <= 0 or account_balance <= 0:
            return 0

        ann_vol = self._annualised_vol(meta, price)
        if ann_vol <= 0:
            return 0

        notional_per_contract = price * c.point_value_krw
        if notional_per_contract <= 0:
            return 0

        target_risk_krw = account_balance * c.target_annual_vol
        raw = target_risk_krw / (ann_vol * notional_per_contract)
        size = int(round(raw))
        size = max(c.min_contracts, min(size, c.max_contracts))

        logger.debug(
            "VolatilityTargetFuturesSizer: ann_vol=%.4f price=%.2f "
            "notional/ct=%.0f target_risk=%.0f raw=%.2f → size=%d",
            ann_vol,
            price,
            notional_per_contract,
            target_risk_krw,
            raw,
            size,
        )
        return size

    def _annualised_vol(self, meta: dict[str, Any], price: float) -> float:
        """Resolve annualised return vol from metadata, ATR-implied as fallback."""
        c = self.config
        ann = _coerce_float(meta.get("daily_return_vol"))
        if ann is not None and ann > 0:
            return max(ann, c.vol_floor)

        daily = _coerce_float(meta.get("daily_return_vol_daily"))
        if daily is not None and daily > 0:
            return max(daily * math.sqrt(c.trading_days_per_year), c.vol_floor)

        atr = _coerce_float(meta.get("entry_atr"))
        if atr is not None and atr > 0 and price > 0:
            daily_implied = atr / price
            return max(daily_implied * math.sqrt(c.trading_days_per_year), c.vol_floor)

        return 0.0


def _coerce_float(value: Any) -> float | None:
    """Best-effort float coercion; None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
