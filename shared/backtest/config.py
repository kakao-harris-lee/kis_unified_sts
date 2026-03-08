"""백테스트 설정

모든 백테스트 관련 설정을 중앙 집중화.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from shared.execution.slippage_model import SlippageModel
    from shared.backtest.ats_simulator import ATSSimulator


@dataclass
class CostConfig:
    """비용 설정"""

    commission_rate: float = 0.00015  # 수수료율 0.015%
    slippage_rate: float = 0.0001  # 슬리피지율 0.01%
    tax_rate: float = 0.0  # 거래세 (주식 매도: 0.0023)

    @classmethod
    def stock(cls) -> CostConfig:
        """주식용 비용 설정"""
        return cls(
            commission_rate=0.00015,  # 키움 0.015%
            slippage_rate=0.0001,
            tax_rate=0.0023,  # 매도세 0.23%
        )

    @classmethod
    def futures(cls) -> CostConfig:
        """선물용 비용 설정"""
        return cls(
            commission_rate=0.00003,  # 선물 수수료
            slippage_rate=0.0001,
            tax_rate=0.0,  # 선물 거래세 없음
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostConfig:
        return cls(
            commission_rate=data.get("commission_rate", 0.00015),
            slippage_rate=data.get("slippage_rate", 0.0001),
            tax_rate=data.get("tax_rate", 0.0),
        )


@dataclass
class RiskConfig:
    """리스크 관리 설정"""

    # 손절/익절
    stop_loss_pct: float = 2.0  # 기본 손절 %
    take_profit_pct: float = 5.0  # 기본 익절 %

    # 트레일링 스탑
    trailing_stop_enabled: bool = False
    trailing_stop_trigger_pct: float = 3.0
    trailing_stop_distance_pct: float = 1.5

    # 시간 제한
    max_hold_bars: int = 0  # 0 = 제한 없음
    force_close_time: str | None = None  # "15:15" 형식

    # ATR 기반 동적 손절
    use_atr_stop: bool = False
    atr_stop_multiplier: float = 2.0

    # 일 경계 포지션 처리
    close_on_day_change: bool = False  # 일자 변경 시 포지션 강제 청산 (RL intraday 전략)

    # 일별 리스크 한도
    max_daily_loss: float = 0.0  # 0 = 제한 없음
    max_daily_trades: int = 0  # 0 = 제한 없음

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskConfig:
        return cls(
            stop_loss_pct=data.get("stop_loss_pct", 2.0),
            take_profit_pct=data.get("take_profit_pct", 5.0),
            trailing_stop_enabled=data.get("trailing_stop_enabled", False),
            trailing_stop_trigger_pct=data.get("trailing_stop_trigger_pct", 3.0),
            trailing_stop_distance_pct=data.get("trailing_stop_distance_pct", 1.5),
            max_hold_bars=data.get("max_hold_bars", 0),
            force_close_time=data.get("force_close_time"),
            close_on_day_change=data.get("close_on_day_change", False),
            use_atr_stop=data.get("use_atr_stop", False),
            atr_stop_multiplier=data.get("atr_stop_multiplier", 2.0),
            max_daily_loss=data.get("max_daily_loss", 0.0),
            max_daily_trades=data.get("max_daily_trades", 0),
        )


@dataclass
class BacktestConfig:
    """백테스트 설정

    Attributes:
        initial_capital: 초기 자본
        position_size_pct: 포지션 크기 (자본 대비 %)
        order_amount_per_stock: 종목당 고정 주문 금액 (주식 전용, 우선 적용)
        max_positions: 최대 동시 포지션 수
        point_value: 1포인트 가치 (선물용)
        cost: 비용 설정
        risk: 리스크 설정
        slippage_model: 슬리피지 모델 (선물용, None이면 고정 슬리피지율 사용)
        ats_enabled: ATS 라우팅 시뮬레이션 활성화 (주식 전용)
        ats_simulator: ATS 시뮬레이터 인스턴스
        verbose: 디버그 출력
    """

    initial_capital: float = 10_000_000
    position_size_pct: float = 10.0  # 자본의 10%
    order_amount_per_stock: float | None = None
    max_positions: int = 5
    point_value: float = 1.0  # 주식은 1.0, 선물은 50000 등

    cost: CostConfig = field(default_factory=CostConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    slippage_model: SlippageModel | None = None
    ats_enabled: bool = False
    ats_simulator: ATSSimulator | None = None

    verbose: bool = False

    @classmethod
    def stock(
        cls,
        initial_capital: float = 10_000_000,
        position_size_pct: float = 10.0,
        order_amount_per_stock: float | None = None,
        max_positions: int = 5,
    ) -> BacktestConfig:
        """주식용 설정"""
        return cls(
            initial_capital=initial_capital,
            position_size_pct=position_size_pct,
            order_amount_per_stock=order_amount_per_stock,
            max_positions=max_positions,
            point_value=1.0,
            cost=CostConfig.stock(),
        )

    @classmethod
    def futures(
        cls,
        initial_capital: float = 10_000_000,
        contracts: int = 1,
        point_value: float = 50_000,
    ) -> BacktestConfig:
        """선물용 설정"""
        return cls(
            initial_capital=initial_capital,
            position_size_pct=100.0,  # 선물은 계약 수로 관리
            max_positions=contracts,
            point_value=point_value,
            cost=CostConfig.futures(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BacktestConfig:
        # Import SlippageModel at runtime to avoid circular imports
        slippage_model = None
        if "slippage_model" in data:
            from shared.execution.slippage_model import (
                SlippageModel,
                SlippageModelConfig,
            )

            slippage_config = SlippageModelConfig.from_dict(data["slippage_model"])
            slippage_model = SlippageModel(slippage_config)

        # Import ATSSimulator at runtime to avoid circular imports
        ats_simulator = None
        ats_enabled = data.get("ats_enabled", False)
        if ats_enabled and "ats_simulation" in data:
            from shared.backtest.ats_simulator import (
                ATSSimulator,
                ATSSimulationConfig,
            )

            ats_config = ATSSimulationConfig.from_dict(data["ats_simulation"])
            ats_simulator = ATSSimulator.from_config(ats_config)

        return cls(
            initial_capital=data.get("initial_capital", 10_000_000),
            position_size_pct=data.get("position_size_pct", 10.0),
            order_amount_per_stock=data.get("order_amount_per_stock"),
            max_positions=data.get("max_positions", 5),
            point_value=data.get("point_value", 1.0),
            cost=CostConfig.from_dict(data.get("cost", {})),
            risk=RiskConfig.from_dict(data.get("risk", {})),
            slippage_model=slippage_model,
            ats_enabled=ats_enabled,
            ats_simulator=ats_simulator,
            verbose=data.get("verbose", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """MLflow 로깅용 딕셔너리 변환"""
        return {
            "initial_capital": self.initial_capital,
            "position_size_pct": self.position_size_pct,
            "order_amount_per_stock": self.order_amount_per_stock or 0.0,
            "max_positions": self.max_positions,
            "point_value": self.point_value,
            "commission_rate": self.cost.commission_rate,
            "slippage_rate": self.cost.slippage_rate,
            "tax_rate": self.cost.tax_rate,
            "stop_loss_pct": self.risk.stop_loss_pct,
            "take_profit_pct": self.risk.take_profit_pct,
            "trailing_stop_enabled": self.risk.trailing_stop_enabled,
        }
