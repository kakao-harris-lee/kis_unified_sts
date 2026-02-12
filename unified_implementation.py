"""
KIS Unified Trading Platform - 핵심 구현체
==========================================

이 파일은 CLAUDE.md의 설계를 바탕으로 한 실제 구현 코드입니다.
Claude Code로 작업 시 이 패턴을 따라 구현하세요.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generic, Type, TypeVar
import yaml


# =============================================================================
# 1. 설정 스키마 (Pydantic 기반)
# =============================================================================

from pydantic import BaseModel, Field, validator


class EntryConfig(BaseModel):
    """진입 전략 설정"""
    type: str
    params: dict = Field(default_factory=dict)


class ExitConfig(BaseModel):
    """청산 전략 설정"""
    type: str
    params: dict = Field(default_factory=dict)


class PositionConfig(BaseModel):
    """포지션 사이징 설정"""
    type: str
    params: dict = Field(default_factory=dict)


class StrategyDefinition(BaseModel):
    """전략 정의"""
    name: str
    asset_class: str
    enabled: bool = True
    entry: EntryConfig
    exit: ExitConfig
    position: PositionConfig


class StrategyConfig(BaseModel):
    """전략 설정 파일 루트"""
    strategy: StrategyDefinition


# 구체적인 설정 클래스들

class BBEntryParams(BaseModel):
    """볼린저 밴드 진입 파라미터"""
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    volume_confirm: bool = True
    volume_ma_period: int = 20
    volume_threshold: float = 1.5


class ThreeStageExitParams(BaseModel):
    """3-Stage Exit 파라미터"""
    hard_stop_pct: float = 2.0
    breakeven_threshold_pct: float = 2.0
    breakeven_buffer_pct: float = 0.1
    maximize_threshold_pct: float = 5.0
    trailing_stop_pct: float = 3.0
    tight_trailing_pct: float = 1.5
    tight_trailing_trigger_pct: float = 10.0
    
    @validator('maximize_threshold_pct')
    def maximize_must_be_greater(cls, v, values):
        if 'breakeven_threshold_pct' in values and v <= values['breakeven_threshold_pct']:
            raise ValueError('maximize_threshold_pct must be greater than breakeven_threshold_pct')
        return v


class OFIEntryParams(BaseModel):
    """OFI 기반 진입 파라미터"""
    ofi_threshold: float = 1.5
    ofi_lookback: int = 20
    imbalance_threshold: float = 0.3
    liquidity_min: float = 0.5


class ScalpingExitParams(BaseModel):
    """스캘핑 청산 파라미터"""
    stop_ticks: int = 5
    target_ticks: int = 10
    max_hold_seconds: int = 300
    ofi_reversal_exit: bool = True


class RiskBasedSizerParams(BaseModel):
    """리스크 기반 포지션 사이징 파라미터"""
    max_position_pct: float = 10.0
    max_positions: int = 5
    risk_per_trade_pct: float = 1.0


class FixedSizerParams(BaseModel):
    """고정 수량 포지션 사이징 파라미터"""
    contracts: int = 1
    max_contracts: int = 2


# =============================================================================
# 2. 설정 로더
# =============================================================================

class ConfigLoader:
    """
    YAML 설정 파일 로더
    
    모든 설정은 이 클래스를 통해 로드
    하드코딩된 값 사용 금지!
    """
    
    _instance = None
    _config_dir: Path = Path("config")
    _cache: dict = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def set_config_dir(cls, path: str | Path):
        """설정 디렉토리 변경"""
        cls._config_dir = Path(path)
        cls._cache.clear()
    
    @classmethod
    def load_yaml(cls, path: str) -> dict:
        """YAML 파일 로드 (캐시됨)"""
        if path not in cls._cache:
            full_path = cls._config_dir / path
            if not full_path.exists():
                raise FileNotFoundError(f"Config not found: {full_path}")
            
            with open(full_path, 'r', encoding='utf-8') as f:
                cls._cache[path] = yaml.safe_load(f)
        
        return cls._cache[path]
    
    @classmethod
    def load_strategy(cls, asset_class: str, strategy_name: str) -> StrategyConfig:
        """전략 설정 로드"""
        path = f"strategies/{asset_class}/{strategy_name}.yaml"
        data = cls.load_yaml(path)
        return StrategyConfig(**data)
    
    @classmethod
    def load_all_strategies(cls, asset_class: str = None) -> list[StrategyConfig]:
        """모든 활성화된 전략 로드"""
        strategies = []
        
        asset_classes = [asset_class] if asset_class else ["stock", "futures"]
        
        for ac in asset_classes:
            strategy_dir = cls._config_dir / "strategies" / ac
            if strategy_dir.exists():
                for yaml_file in strategy_dir.glob("*.yaml"):
                    rel_path = f"strategies/{ac}/{yaml_file.name}"
                    data = cls.load_yaml(rel_path)
                    config = StrategyConfig(**data)
                    if config.strategy.enabled:
                        strategies.append(config)
        
        return strategies


# =============================================================================
# 3. 데이터 모델
# =============================================================================

class AssetClass(str, Enum):
    STOCK = "stock"
    FUTURES = "futures"


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ExitState(str, Enum):
    SURVIVAL = "survival"
    BREAKEVEN = "breakeven"
    MAXIMIZE = "maximize"


@dataclass
class Signal:
    """매매 시그널"""
    symbol: str
    direction: SignalDirection
    strength: float  # 0.0 ~ 1.0
    strategy_name: str
    timestamp: datetime
    asset_class: AssetClass
    entry_type: str
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"Signal strength must be 0.0-1.0, got {self.strength}")


@dataclass
class Position:
    """포지션"""
    id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int
    entry_price: float
    entry_time: datetime
    asset_class: AssetClass
    strategy_name: str
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    exit_state: ExitState = ExitState.SURVIVAL
    metadata: dict = field(default_factory=dict)
    
    @property
    def pnl(self) -> float:
        """절대 손익"""
        if self.side == "BUY":
            return (self.current_price - self.entry_price) * self.quantity
        return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def pnl_pct(self) -> float:
        """손익률"""
        if self.entry_price == 0:
            return 0.0
        if self.side == "BUY":
            return (self.current_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - self.current_price) / self.entry_price * 100


@dataclass
class EntryContext:
    """진입 판단 컨텍스트"""
    symbol: str
    market_data: dict
    indicators: dict
    current_positions: list[Position]
    timestamp: datetime
    asset_class: AssetClass


@dataclass
class ExitContext:
    """청산 판단 컨텍스트"""
    position: Position
    market_data: dict
    indicators: dict
    timestamp: datetime


@dataclass
class ExitSignal:
    """청산 시그널"""
    should_exit: bool
    reason: str
    exit_price: float | None = None
    metadata: dict = field(default_factory=dict)


# =============================================================================
# 4. 전략 인터페이스 (ABC)
# =============================================================================

TConfig = TypeVar('TConfig')


class EntrySignalGenerator(ABC, Generic[TConfig]):
    """
    진입 시그널 생성기 추상 클래스
    
    모든 진입 로직은 이 인터페이스를 구현해야 함
    """
    
    CONFIG_CLASS: Type[TConfig] = dict  # 서브클래스에서 오버라이드
    
    def __init__(self, config: TConfig | dict):
        if isinstance(config, dict) and self.CONFIG_CLASS != dict:
            self.config = self.CONFIG_CLASS(**config)
        else:
            self.config = config
        self._validate_config()
    
    def _validate_config(self):
        """설정 유효성 검증 - 필요시 오버라이드"""
        pass
    
    @property
    @abstractmethod
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록"""
        pass
    
    @abstractmethod
    async def generate(self, context: EntryContext) -> Signal | None:
        """진입 시그널 생성"""
        pass


class ExitSignalGenerator(ABC, Generic[TConfig]):
    """
    청산 시그널 생성기 추상 클래스
    
    모든 청산 로직은 이 인터페이스를 구현해야 함
    """
    
    CONFIG_CLASS: Type[TConfig] = dict
    
    def __init__(self, config: TConfig | dict):
        if isinstance(config, dict) and self.CONFIG_CLASS != dict:
            self.config = self.CONFIG_CLASS(**config)
        else:
            self.config = config
        self._validate_config()
    
    def _validate_config(self):
        """설정 유효성 검증"""
        pass
    
    @abstractmethod
    async def check_exit(self, context: ExitContext) -> ExitSignal:
        """청산 여부 판단"""
        pass
    
    @abstractmethod
    def update_state(self, position: Position, current_price: float):
        """포지션 상태 업데이트"""
        pass
    
    def cleanup(self, position_id: str):
        """포지션 종료 시 정리"""
        pass


class PositionSizer(ABC, Generic[TConfig]):
    """포지션 사이징 추상 클래스"""
    
    CONFIG_CLASS: Type[TConfig] = dict
    
    def __init__(self, config: TConfig | dict):
        if isinstance(config, dict) and self.CONFIG_CLASS != dict:
            self.config = self.CONFIG_CLASS(**config)
        else:
            self.config = config
    
    @abstractmethod
    def calculate(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position]
    ) -> int:
        """포지션 크기 계산"""
        pass


# =============================================================================
# 5. 레지스트리 패턴
# =============================================================================

class ComponentRegistry:
    """컴포넌트 레지스트리 기본 클래스"""
    
    _components: dict[str, Type] = {}
    
    @classmethod
    def register(cls, name: str) -> Callable:
        """데코레이터로 컴포넌트 등록"""
        def decorator(component_class: Type) -> Type:
            cls._components[name] = component_class
            return component_class
        return decorator
    
    @classmethod
    def create(cls, name: str, params: dict) -> Any:
        """이름으로 컴포넌트 생성"""
        if name not in cls._components:
            available = list(cls._components.keys())
            raise ValueError(f"Unknown: {name}. Available: {available}")
        
        return cls._components[name](params)
    
    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._components.keys())


class EntryRegistry(ComponentRegistry):
    """진입 로직 레지스트리"""
    _components = {}


class ExitRegistry(ComponentRegistry):
    """청산 로직 레지스트리"""
    _components = {}


class SizerRegistry(ComponentRegistry):
    """포지션 사이저 레지스트리"""
    _components = {}


# =============================================================================
# 6. 구체적 구현체 - Entry
# =============================================================================

@EntryRegistry.register("bb_lower_reentry")
class BBLowerReentryEntry(EntrySignalGenerator[BBEntryParams]):
    """볼린저 밴드 하단 재진입 전략"""
    
    CONFIG_CLASS = BBEntryParams
    
    @property
    def required_indicators(self) -> list[str]:
        c = self.config
        return [
            f"BB_{c.bb_period}_{c.bb_std}",
            f"RSI_{c.rsi_period}",
            f"VOLUME_MA_{c.volume_ma_period}" if c.volume_confirm else None,
        ]
    
    async def generate(self, context: EntryContext) -> Signal | None:
        c = self.config
        indicators = context.indicators
        data = context.market_data
        
        # 지표 가져오기
        bb_key = f"BB_{c.bb_period}_{c.bb_std}"
        rsi_key = f"RSI_{c.rsi_period}"
        
        bb = indicators.get(bb_key)
        rsi = indicators.get(rsi_key)
        
        if bb is None or rsi is None:
            return None
        
        close = data.get('close', 0)
        prev_close = data.get('prev_close', 0)
        
        # 조건 1: BB 하단 이탈 후 재진입
        bb_lower = bb.get('lower', 0)
        reentry_condition = prev_close < bb_lower and close > bb_lower
        
        # 조건 2: RSI 과매도
        rsi_condition = rsi < c.rsi_oversold
        
        # 조건 3: 거래량 확인 (선택)
        volume_condition = True
        if c.volume_confirm:
            vol_ma_key = f"VOLUME_MA_{c.volume_ma_period}"
            vol_ma = indicators.get(vol_ma_key, 0)
            current_volume = data.get('volume', 0)
            volume_condition = current_volume > vol_ma * c.volume_threshold
        
        # 모든 조건 충족 시 시그널 생성
        if reentry_condition and rsi_condition and volume_condition:
            strength = self._calculate_strength(rsi, bb, close)
            
            return Signal(
                symbol=context.symbol,
                direction=SignalDirection.BUY,
                strength=strength,
                strategy_name="bb_reversion",
                timestamp=context.timestamp,
                asset_class=context.asset_class,
                entry_type="bb_lower_reentry",
                metadata={
                    "rsi": rsi,
                    "bb_lower": bb_lower,
                    "close": close,
                }
            )
        
        return None
    
    def _calculate_strength(self, rsi: float, bb: dict, close: float) -> float:
        """시그널 강도 계산"""
        c = self.config
        
        # RSI 강도 (낮을수록 강함)
        rsi_score = max(0, (c.rsi_oversold - rsi) / c.rsi_oversold)
        
        # BB 이탈 강도
        bb_lower = bb.get('lower', close)
        bb_middle = bb.get('middle', close)
        if bb_middle != bb_lower:
            bb_score = max(0, min(1, (bb_lower - close) / (bb_middle - bb_lower)))
        else:
            bb_score = 0.5
        
        return min(1.0, (rsi_score + bb_score) / 2)


@EntryRegistry.register("ofi_imbalance")
class OFIImbalanceEntry(EntrySignalGenerator[OFIEntryParams]):
    """OFI 기반 호가 불균형 진입 전략"""
    
    CONFIG_CLASS = OFIEntryParams
    
    @property
    def required_indicators(self) -> list[str]:
        return ["OFI", "ORDERBOOK_IMBALANCE", "LIQUIDITY_SCORE"]
    
    async def generate(self, context: EntryContext) -> Signal | None:
        c = self.config
        indicators = context.indicators
        
        ofi = indicators.get("OFI", {})
        imbalance = indicators.get("ORDERBOOK_IMBALANCE", 0)
        liquidity = indicators.get("LIQUIDITY_SCORE", 0)
        
        ofi_z = ofi.get("z_score", 0)
        
        # 유동성 조건
        if liquidity < c.liquidity_min:
            return None
        
        # 매수 시그널
        if ofi_z > c.ofi_threshold and imbalance > c.imbalance_threshold:
            return Signal(
                symbol=context.symbol,
                direction=SignalDirection.BUY,
                strength=min(abs(ofi_z) / 3.0, 1.0),
                strategy_name="pure_micro",
                timestamp=context.timestamp,
                asset_class=context.asset_class,
                entry_type="ofi_imbalance",
                metadata={"ofi_z": ofi_z, "imbalance": imbalance}
            )
        
        # 매도 시그널
        if ofi_z < -c.ofi_threshold and imbalance < -c.imbalance_threshold:
            return Signal(
                symbol=context.symbol,
                direction=SignalDirection.SELL,
                strength=min(abs(ofi_z) / 3.0, 1.0),
                strategy_name="pure_micro",
                timestamp=context.timestamp,
                asset_class=context.asset_class,
                entry_type="ofi_imbalance",
                metadata={"ofi_z": ofi_z, "imbalance": imbalance}
            )
        
        return None


# =============================================================================
# 7. 구체적 구현체 - Exit
# =============================================================================

@ExitRegistry.register("three_stage")
class ThreeStageExit(ExitSignalGenerator[ThreeStageExitParams]):
    """
    3-Stage Dynamic Exit Strategy
    
    모든 임계값은 설정에서 로드 - 하드코딩 절대 금지!
    """
    
    CONFIG_CLASS = ThreeStageExitParams
    
    def __init__(self, config: ThreeStageExitParams | dict):
        super().__init__(config)
        self._states: dict[str, ExitState] = {}
        self._highest_prices: dict[str, float] = {}
    
    def _validate_config(self):
        c = self.config
        assert c.hard_stop_pct > 0
        assert c.breakeven_threshold_pct > 0
        assert c.maximize_threshold_pct > c.breakeven_threshold_pct
        assert c.trailing_stop_pct > 0
        assert c.tight_trailing_pct < c.trailing_stop_pct
    
    async def check_exit(self, context: ExitContext) -> ExitSignal:
        position = context.position
        current_price = context.market_data.get('close', position.current_price)
        
        # 현재 가격 업데이트
        position.current_price = current_price
        pnl_pct = position.pnl_pct
        
        state = self._states.get(position.id, ExitState.SURVIVAL)
        
        # 상태별 처리
        if state == ExitState.SURVIVAL:
            return self._check_survival(position, pnl_pct)
        elif state == ExitState.BREAKEVEN:
            return self._check_breakeven(position, pnl_pct, current_price)
        else:  # MAXIMIZE
            return self._check_maximize(position, pnl_pct, current_price)
    
    def _check_survival(self, position: Position, pnl_pct: float) -> ExitSignal:
        """Stage 1: Survival - Hard Stop"""
        c = self.config
        
        if pnl_pct <= -c.hard_stop_pct:
            return ExitSignal(
                should_exit=True,
                reason=f"HARD_STOP (-{c.hard_stop_pct}%)",
                exit_price=position.current_price,
                metadata={"pnl_pct": pnl_pct, "state": "SURVIVAL"}
            )
        
        # 상태 전환 체크
        if pnl_pct >= c.breakeven_threshold_pct:
            self._states[position.id] = ExitState.BREAKEVEN
        
        return ExitSignal(should_exit=False, reason="HOLDING")
    
    def _check_breakeven(self, position: Position, pnl_pct: float, current_price: float) -> ExitSignal:
        """Stage 2: Breakeven - 본전 보장"""
        c = self.config
        
        if pnl_pct <= c.breakeven_buffer_pct:
            return ExitSignal(
                should_exit=True,
                reason=f"BREAKEVEN_STOP (+{c.breakeven_buffer_pct}%)",
                exit_price=current_price,
                metadata={"pnl_pct": pnl_pct, "state": "BREAKEVEN"}
            )
        
        # 상태 전환 체크
        if pnl_pct >= c.maximize_threshold_pct:
            self._states[position.id] = ExitState.MAXIMIZE
            self._highest_prices[position.id] = current_price
        
        return ExitSignal(should_exit=False, reason="HOLDING")
    
    def _check_maximize(self, position: Position, pnl_pct: float, current_price: float) -> ExitSignal:
        """Stage 3: Maximize - Trailing Stop"""
        c = self.config
        
        # 고점 갱신
        highest = self._highest_prices.get(position.id, current_price)
        if current_price > highest:
            self._highest_prices[position.id] = current_price
            highest = current_price
        
        # 동적 트레일링 폭
        trailing_pct = c.trailing_stop_pct
        if pnl_pct >= c.tight_trailing_trigger_pct:
            trailing_pct = c.tight_trailing_pct
        
        # 고점 대비 하락률
        drop_pct = (highest - current_price) / highest * 100
        
        if drop_pct >= trailing_pct:
            return ExitSignal(
                should_exit=True,
                reason=f"TRAILING_STOP (drop: {drop_pct:.1f}%, trail: {trailing_pct}%)",
                exit_price=current_price,
                metadata={
                    "pnl_pct": pnl_pct,
                    "highest": highest,
                    "drop_pct": drop_pct,
                    "state": "MAXIMIZE"
                }
            )
        
        return ExitSignal(should_exit=False, reason="HOLDING")
    
    def update_state(self, position: Position, current_price: float):
        """상태 업데이트 (외부 호출용)"""
        position.current_price = current_price
        
        # 고점/저점 업데이트
        if current_price > position.highest_price:
            position.highest_price = current_price
        if current_price < position.lowest_price:
            position.lowest_price = current_price
    
    def cleanup(self, position_id: str):
        """포지션 종료 시 정리"""
        self._states.pop(position_id, None)
        self._highest_prices.pop(position_id, None)


@ExitRegistry.register("scalping")
class ScalpingExit(ExitSignalGenerator[ScalpingExitParams]):
    """스캘핑 청산 전략 (선물용)"""
    
    CONFIG_CLASS = ScalpingExitParams
    
    def __init__(self, config: ScalpingExitParams | dict):
        super().__init__(config)
        self._entry_times: dict[str, datetime] = {}
    
    async def check_exit(self, context: ExitContext) -> ExitSignal:
        c = self.config
        position = context.position
        current_price = context.market_data.get('close', 0)
        
        # 틱 손익 계산 (선물 기준)
        tick_size = context.market_data.get('tick_size', 0.05)
        tick_pnl = (current_price - position.entry_price) / tick_size
        if position.side == "SELL":
            tick_pnl = -tick_pnl
        
        # Stop Loss
        if tick_pnl <= -c.stop_ticks:
            return ExitSignal(
                should_exit=True,
                reason=f"TICK_STOP ({tick_pnl:.0f} ticks)",
                exit_price=current_price
            )
        
        # Take Profit
        if tick_pnl >= c.target_ticks:
            return ExitSignal(
                should_exit=True,
                reason=f"TICK_TARGET ({tick_pnl:.0f} ticks)",
                exit_price=current_price
            )
        
        # Time Stop
        entry_time = self._entry_times.get(position.id, position.entry_time)
        elapsed = (context.timestamp - entry_time).total_seconds()
        if elapsed >= c.max_hold_seconds:
            return ExitSignal(
                should_exit=True,
                reason=f"TIME_STOP ({elapsed:.0f}s)",
                exit_price=current_price
            )
        
        # OFI 반전 청산
        if c.ofi_reversal_exit:
            ofi = context.indicators.get("OFI", {})
            ofi_z = ofi.get("z_score", 0)
            
            if position.side == "BUY" and ofi_z < -1.0:
                return ExitSignal(
                    should_exit=True,
                    reason=f"OFI_REVERSAL ({ofi_z:.2f})",
                    exit_price=current_price
                )
            if position.side == "SELL" and ofi_z > 1.0:
                return ExitSignal(
                    should_exit=True,
                    reason=f"OFI_REVERSAL ({ofi_z:.2f})",
                    exit_price=current_price
                )
        
        return ExitSignal(should_exit=False, reason="HOLDING")
    
    def update_state(self, position: Position, current_price: float):
        position.current_price = current_price
        if position.id not in self._entry_times:
            self._entry_times[position.id] = position.entry_time
    
    def cleanup(self, position_id: str):
        self._entry_times.pop(position_id, None)


# =============================================================================
# 8. 구체적 구현체 - Position Sizer
# =============================================================================

@SizerRegistry.register("risk_based")
class RiskBasedSizer(PositionSizer[RiskBasedSizerParams]):
    """리스크 기반 포지션 사이징"""
    
    CONFIG_CLASS = RiskBasedSizerParams
    
    def calculate(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position]
    ) -> int:
        c = self.config
        
        # 최대 포지션 수 체크
        if len(current_positions) >= c.max_positions:
            return 0
        
        # 이미 해당 종목 포지션이 있는지 체크
        existing = [p for p in current_positions if p.symbol == signal.symbol]
        if existing:
            return 0
        
        # 리스크 금액 계산
        risk_amount = account_balance * (c.risk_per_trade_pct / 100)
        
        # 최대 포지션 금액
        max_position_amount = account_balance * (c.max_position_pct / 100)
        
        # 가격 정보로 수량 계산 (signal metadata에서)
        price = signal.metadata.get('close', 0)
        if price <= 0:
            return 0
        
        # 손절폭 기준 수량 (예: 2% 손절 기준)
        stop_pct = signal.metadata.get('stop_pct', 2.0)
        quantity_by_risk = int(risk_amount / (price * stop_pct / 100))
        
        # 최대 금액 기준 수량
        quantity_by_max = int(max_position_amount / price)
        
        return min(quantity_by_risk, quantity_by_max)


@SizerRegistry.register("fixed")
class FixedSizer(PositionSizer[FixedSizerParams]):
    """고정 수량 포지션 사이징 (선물용)"""
    
    CONFIG_CLASS = FixedSizerParams
    
    def calculate(
        self,
        signal: Signal,
        _account_balance: float,
        current_positions: list[Position]
    ) -> int:
        c = self.config
        
        # 현재 포지션 합계
        current_contracts = sum(
            p.quantity for p in current_positions 
            if p.symbol == signal.symbol
        )
        
        # 최대 계약 수 체크
        if current_contracts >= c.max_contracts:
            return 0
        
        return min(c.contracts, c.max_contracts - current_contracts)


# =============================================================================
# 9. 전략 팩토리 & 조합
# =============================================================================

class TradingStrategy:
    """
    트레이딩 전략 - 진입/청산/사이징 조합
    
    구체적 로직 없이 주입받은 컴포넌트만 사용
    """
    
    def __init__(
        self,
        name: str,
        asset_class: AssetClass,
        entry: EntrySignalGenerator,
        exit: ExitSignalGenerator,
        position_sizer: PositionSizer,
    ):
        self.name = name
        self.asset_class = asset_class
        self.entry = entry
        self.exit = exit
        self.position_sizer = position_sizer
    
    @property
    def required_indicators(self) -> list[str]:
        """필요한 모든 지표"""
        indicators = self.entry.required_indicators
        return [i for i in indicators if i is not None]
    
    async def check_entry(self, context: EntryContext) -> Signal | None:
        """진입 조건 확인"""
        return await self.entry.generate(context)
    
    async def check_exit(self, context: ExitContext) -> ExitSignal:
        """청산 조건 확인"""
        return await self.exit.check_exit(context)
    
    def calculate_size(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position]
    ) -> int:
        """포지션 크기 계산"""
        return self.position_sizer.calculate(signal, account_balance, current_positions)


class StrategyFactory:
    """
    설정 파일 → 전략 객체 생성
    
    이 팩토리를 통해 YAML 설정만으로 전략이 생성됨
    """
    
    @classmethod
    def create(cls, config: StrategyConfig) -> TradingStrategy:
        """설정으로부터 전략 생성"""
        s = config.strategy
        
        entry = EntryRegistry.create(s.entry.type, s.entry.params)
        exit = ExitRegistry.create(s.exit.type, s.exit.params)
        sizer = SizerRegistry.create(s.position.type, s.position.params)
        
        return TradingStrategy(
            name=s.name,
            asset_class=AssetClass(s.asset_class),
            entry=entry,
            exit=exit,
            position_sizer=sizer,
        )
    
    @classmethod
    def create_from_file(cls, asset_class: str, strategy_name: str) -> TradingStrategy:
        """파일로부터 전략 생성"""
        config = ConfigLoader.load_strategy(asset_class, strategy_name)
        return cls.create(config)
    
    @classmethod
    def create_all(cls, asset_class: str = None) -> list[TradingStrategy]:
        """모든 활성화된 전략 생성"""
        configs = ConfigLoader.load_all_strategies(asset_class)
        return [cls.create(c) for c in configs]


# =============================================================================
# 10. 사용 예시
# =============================================================================

async def example_usage():
    """사용 예시"""
    
    # 1. 설정 기반 전략 생성
    config_data = {
        "strategy": {
            "name": "bb_reversion",
            "asset_class": "stock",
            "enabled": True,
            "entry": {
                "type": "bb_lower_reentry",
                "params": {
                    "bb_period": 20,
                    "bb_std": 2.0,
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                }
            },
            "exit": {
                "type": "three_stage",
                "params": {
                    "hard_stop_pct": 2.0,
                    "breakeven_threshold_pct": 2.0,
                    "breakeven_buffer_pct": 0.1,
                    "maximize_threshold_pct": 5.0,
                    "trailing_stop_pct": 3.0,
                    "tight_trailing_pct": 1.5,
                    "tight_trailing_trigger_pct": 10.0,
                }
            },
            "position": {
                "type": "risk_based",
                "params": {
                    "max_position_pct": 10.0,
                    "max_positions": 5,
                    "risk_per_trade_pct": 1.0,
                }
            }
        }
    }
    
    config = StrategyConfig(**config_data)
    strategy = StrategyFactory.create(config)
    
    print(f"Strategy: {strategy.name}")
    print(f"Asset Class: {strategy.asset_class}")
    print(f"Required Indicators: {strategy.required_indicators}")
    
    # 2. 진입 시그널 체크
    context = EntryContext(
        symbol="005930",
        market_data={
            "close": 65000,
            "prev_close": 64000,
            "volume": 1500000,
        },
        indicators={
            "BB_20_2.0": {"lower": 64500, "middle": 66000, "upper": 67500},
            "RSI_14": 25,
            "VOLUME_MA_20": 1000000,
        },
        current_positions=[],
        timestamp=datetime.now(),
        asset_class=AssetClass.STOCK,
    )
    
    signal = await strategy.check_entry(context)
    if signal:
        print(f"\n🎯 Entry Signal: {signal}")
        
        # 3. 포지션 사이즈 계산
        size = strategy.calculate_size(signal, 10_000_000, [])
        print(f"Position Size: {size} shares")
    
    # 4. 청산 체크 (포지션이 있다고 가정)
    position = Position(
        id="pos_001",
        symbol="005930",
        side="BUY",
        quantity=10,
        entry_price=65000,
        entry_time=datetime.now(),
        asset_class=AssetClass.STOCK,
        strategy_name="bb_reversion",
        current_price=67000,  # +3%
        highest_price=67000,
    )
    
    exit_context = ExitContext(
        position=position,
        market_data={"close": 67000},
        indicators={},
        timestamp=datetime.now(),
    )
    
    exit_signal = await strategy.check_exit(exit_context)
    print(f"\n📊 Exit Check: {exit_signal}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
