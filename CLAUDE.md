# CLAUDE.md - KIS Unified Trading Platform

## 🎯 프로젝트 핵심 목표

**"진입/청산 타이밍 최적화"** - 모든 설계와 구현은 이 목표에 집중한다.

```
전략 구성 → 백테스트 → MLflow 추적 → 파라미터 최적화 → 실전 적용
    ↑                                                      │
    └──────────────── 피드백 루프 ─────────────────────────┘
```

---

## 📋 프로젝트 개요

### 통합 대상

| 프로젝트 | 대상 | 핵심 기능 | GitHub |
|---------|------|----------|--------|
| quant_moment_sts | 주식 | 3-Stage Exit, MLflow 백테스팅 | kakao-harris-lee/quant_moment_sts |
| kospi_mini_sts | 선물 | OFI 마이크로스트럭처, Redis Streams | kakao-harris-lee/kospi_mini_sts |

### 통합 원칙

1. **DRY (Don't Repeat Yourself)**: 중복 코드 절대 금지
2. **No Hardcoding**: 모든 값은 설정 파일에서 로드
3. **Strategy Pattern**: 진입/청산 로직의 완전한 추상화
4. **Configuration-Driven**: 코드 수정 없이 전략 변경 가능

---

## 🏗️ 아키텍처 원칙

### 1. 설정 기반 아키텍처 (Configuration-Driven)

**절대 규칙**: 코드에 숫자, 문자열 리터럴 직접 작성 금지

```python
# ❌ 금지 - 하드코딩
if pnl_pct >= 2.0:  # 하드코딩된 임계값
    state = "BREAKEVEN"

# ✅ 권장 - 설정 기반
if pnl_pct >= self.config.exit.breakeven_threshold:
    state = PositionState.BREAKEVEN
```

### 2. 전략 추상화 계층

```
┌─────────────────────────────────────────────────────────────┐
│                    Strategy Interface                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ EntrySignal │  │ ExitSignal  │  │ PositionSizing      │ │
│  │ Generator   │  │ Generator   │  │ Calculator          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Implementations                           │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │ Stock Strategies    │  │ Futures Strategies          │  │
│  │ - BB Reversion      │  │ - Pure Micro                │  │
│  │ - Volume Momentum   │  │ - OFI Momentum              │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3. 진입/청산 로직 분리

진입과 청산은 **독립적인 컴포넌트**로 분리하여 조합 가능하게 설계:

```python
# 진입 전략과 청산 전략을 독립적으로 조합
strategy = TradingStrategy(
    entry=BBReversionEntry(config.entry),      # 진입 로직
    exit=ThreeStageExit(config.exit),          # 청산 로직
    position_sizer=RiskBasedSizer(config.risk) # 포지션 사이징
)
```

### 4. 핵심 추상화 (Key Abstractions)

| 컴포넌트 | 역할 | 구현 파일 |
|---------|------|----------|
| **TradingOrchestrator** | 트레이딩 전체 수명주기 및 메인 루프 관리 | `services/trading/orchestrator.py` |
| **StrategyManager** | 다중 전략 관리, 진입/청산 시그널 집계 | `services/trading/strategy_manager.py` |
| **EntrySignalGenerator** | 진입 시그널 생성 (Strategy Pattern) | `shared/strategy/base.py` |
| **ExitSignalGenerator** | 청산 시그널 생성 (Strategy Pattern) | `shared/strategy/base.py` |
| **PositionSizer** | 포지션 크기 및 리스크 계산 | `shared/strategy/base.py` |

---

## 📁 디렉토리 구조

```
kis-unified-trading/
├── CLAUDE.md                        # 이 파일 - Claude Code 가이드
├── pyproject.toml                   # 프로젝트 설정
├── docker-compose.yml               # 프로덕션 Docker 오케스트레이션
├── docker-compose.dev.yml           # 개발 환경 오버라이드
├── Dockerfile                       # 기본 Docker 이미지
├── Dockerfile.prod                  # 프로덕션 최적화 이미지
├── prometheus.yml                   # Prometheus 설정
├── .env.example                     # 환경 변수 템플릿
│
├── .github/workflows/               # 📁 CI/CD 파이프라인
│   ├── test.yml                     # 테스트 자동화
│   └── docker.yml                   # Docker 빌드/배포
│
├── scripts/                         # 📁 운영 스크립트
│   ├── docker-start.sh              # Docker 시작
│   ├── docker-stop.sh               # Docker 중지
│   └── docker-health.sh             # 헬스 체크
│
├── docs/                            # 📁 문서
│   ├── deployment.md                # 배포 가이드
│   ├── api.md                       # API 문서
│   └── strategies.md                # 전략 가이드
│
├── grafana/                         # 📁 Grafana 설정
│   ├── dashboards/                  # 대시보드 JSON
│   └── provisioning/                # 자동 설정
│
├── config/                          # 📁 모든 설정 파일
│   ├── base.yaml                    # 기본 설정
│   ├── llm.yaml                     # LLM/KRX API 설정
│   ├── strategies/                  # 전략별 설정
│   │   ├── stock/
│   │   │   ├── bb_reversion.yaml
│   │   │   └── volume_momentum.yaml
│   │   └── futures/
│   │       ├── pure_micro.yaml
│   │       └── ofi_momentum.yaml
│   ├── exit/                        # 청산 전략 설정
│   │   ├── three_stage.yaml         # 3-Stage Exit (주식용)
│   │   └── scalping.yaml            # 스캘핑 Exit (선물용)
│   └── risk/                        # 리스크 설정
│       ├── stock.yaml
│       └── futures.yaml
│
├── shared/                          # 📁 공유 모듈 (중복 제거의 핵심)
│   ├── __init__.py
│   ├── config/                      # 설정 로더
│   │   ├── __init__.py
│   │   ├── loader.py                # YAML 설정 로더
│   │   └── schema.py                # Pydantic 스키마
│   │
│   ├── strategy/                    # 전략 프레임워크
│   │   ├── __init__.py
│   │   ├── base.py                  # 추상 클래스
│   │   ├── entry/                   # 진입 시그널
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # EntrySignal ABC
│   │   │   ├── technical.py         # 기술적 지표 기반
│   │   │   └── microstructure.py    # 마이크로스트럭처 기반
│   │   ├── exit/                    # 청산 시그널
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # ExitSignal ABC
│   │   │   ├── three_stage.py       # 3-Stage Exit
│   │   │   ├── trailing.py          # 트레일링 스탑
│   │   │   └── time_based.py        # 시간 기반
│   │   ├── position/                # 포지션 사이징
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── risk_based.py
│   │   └── registry.py              # 전략 레지스트리
│   │
│   ├── backtest/                    # 백테스트 엔진
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── simulator.py
│   │   └── mlflow_tracker.py        # MLflow 통합
│   │
│   ├── indicators/                  # 기술적 지표
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── trend.py
│   │   ├── volatility.py
│   │   ├── momentum.py
│   │   └── microstructure.py        # OFI, VPIN 등
│   │
│   ├── kis/                         # KIS API 어댑터
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── client.py
│   │   └── websocket.py
│   │
│   ├── paper/                       # 모의투자 엔진
│   │   ├── __init__.py
│   │   ├── broker.py                # 가상 브로커
│   │   ├── engine.py                # 모의투자 엔진
│   │   ├── models.py                # 가상 주문 모델
│   │   ├── config.py                # 모의투자 설정
│   │   └── report.py                # 거래 리포트
│   │
│   ├── llm/                         # LLM 시장 분석
│   │   ├── __init__.py
│   │   ├── config.py                # LLMConfig (YAML/환경변수)
│   │   ├── data_classes.py          # 데이터 클래스/Enum
│   │   ├── krx_api_client.py        # KRX Open API 클라이언트
│   │   ├── market_analyzers.py      # ETF/선물/옵션/채권 분석기
│   │   ├── unified_market_analyzer.py # 통합 시장 분석 오케스트레이터
│   │   └── llm_analyzer.py          # LLM 기반 종목 분석
│   │
│   ├── ensemble/                    # 앙상블 모델
│   │   ├── __init__.py
│   │   ├── voting.py                # 투표 기반 앙상블
│   │   └── stacking.py              # 스태킹 앙상블
│   │
│   ├── resilience/                  # 장애 복구
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py       # 서킷 브레이커
│   │   └── retry.py                 # 재시도 로직
│   │
│   └── models/                      # 데이터 모델
│       ├── __init__.py
│       ├── market.py
│       ├── signal.py
│       ├── order.py
│       └── position.py
│
├── domains/                         # 📁 도메인별 구현
│   ├── stock/                       # 주식 도메인
│   │   ├── __init__.py
│   │   ├── strategies/              # 주식 전략 구현체
│   │   ├── universe.py
│   │   └── service.py
│   │
│   └── futures/                     # 선물 도메인
│       ├── __init__.py
│       ├── strategies/              # 선물 전략 구현체
│       ├── contract.py
│       └── service.py
│
├── services/                        # 📁 애플리케이션 서비스
│   ├── trading/                     # 트레이딩 엔진
│   │   ├── orchestrator.py          # 중앙 오케스트레이터
│   │   ├── strategy_manager.py      # 전략 관리자
│   │   └── pipeline.py              # 데이터 파이프라인
│   ├── backtest/                    # 백테스트 실행기
│   ├── dashboard/                   # 대시보드 백엔드
│   └── monitoring/                  # 모니터링 서비스
│
├── cli/                             # 📁 CLI 명령어
│   └── commands/
│
└── tests/
```

---

## 🔧 핵심 구현 가이드

### 1. 설정 스키마 (모든 값의 출처)

```yaml
# config/strategies/stock/bb_reversion.yaml
strategy:
  name: bb_reversion
  asset_class: stock
  enabled: true

  entry:
    type: bb_lower_reentry
    params:
      bb_period: 20
      bb_std: 2.0
      rsi_period: 14
      rsi_oversold: 30
      volume_confirm: true
      volume_ma_period: 20
      volume_threshold: 1.5

  exit:
    type: three_stage
    params:
      # Stage 1: Survival
      hard_stop_pct: 2.0

      # Stage 2: Breakeven
      breakeven_threshold_pct: 2.0
      breakeven_buffer_pct: 0.1

      # Stage 3: Maximize
      maximize_threshold_pct: 5.0
      trailing_stop_pct: 3.0
      tight_trailing_pct: 1.5
      tight_trailing_trigger_pct: 10.0

  position:
    type: risk_based
    params:
      max_position_pct: 10.0
      max_positions: 5
      risk_per_trade_pct: 1.0
```

```yaml
# config/strategies/futures/pure_micro.yaml
strategy:
  name: pure_micro
  asset_class: futures
  enabled: true

  entry:
    type: ofi_imbalance
    params:
      ofi_threshold: 1.5
      ofi_lookback: 20
      imbalance_threshold: 0.3
      liquidity_min: 0.5

  exit:
    type: scalping
    params:
      stop_ticks: 5
      target_ticks: 10
      max_hold_seconds: 300
      ofi_reversal_exit: true

  position:
    type: fixed
    params:
      contracts: 1
      max_contracts: 2
```

### 2. 설정 로더 구현

```python
# shared/config/loader.py
from pathlib import Path
from typing import TypeVar, Type
import yaml
from pydantic import BaseModel
from functools import lru_cache

T = TypeVar('T', bound=BaseModel)

class ConfigLoader:
    """설정 파일 로더 - 모든 설정의 단일 진입점"""

    _instance = None
    _config_dir: Path = Path("config")
    _cache: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_config_dir(cls, path: str | Path):
        """설정 디렉토리 변경 (테스트용)"""
        cls._config_dir = Path(path)
        cls._cache.clear()

    @classmethod
    def load(cls, path: str, schema: Type[T] = None) -> T | dict:
        """
        YAML 설정 파일 로드

        Usage:
            config = ConfigLoader.load("strategies/stock/bb_reversion.yaml", StrategyConfig)
        """
        cache_key = str(path)

        if cache_key not in cls._cache:
            full_path = cls._config_dir / path

            if not full_path.exists():
                raise FileNotFoundError(f"Config file not found: {full_path}")

            with open(full_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            cls._cache[cache_key] = data

        data = cls._cache[cache_key]

        if schema:
            return schema(**data)
        return data

    @classmethod
    def load_strategy(cls, asset_class: str, strategy_name: str) -> "StrategyConfig":
        """전략 설정 로드 헬퍼"""
        from shared.config.schema import StrategyConfig
        path = f"strategies/{asset_class}/{strategy_name}.yaml"
        return cls.load(path, StrategyConfig)

    @classmethod
    def load_all_strategies(cls, asset_class: str = None) -> list["StrategyConfig"]:
        """모든 활성화된 전략 로드"""
        from shared.config.schema import StrategyConfig
        strategies = []

        search_dirs = []
        if asset_class:
            search_dirs.append(cls._config_dir / "strategies" / asset_class)
        else:
            search_dirs.extend([
                cls._config_dir / "strategies" / "stock",
                cls._config_dir / "strategies" / "futures",
            ])

        for dir_path in search_dirs:
            if dir_path.exists():
                for yaml_file in dir_path.glob("*.yaml"):
                    config = cls.load(yaml_file.relative_to(cls._config_dir), StrategyConfig)
                    if config.strategy.enabled:
                        strategies.append(config)

        return strategies
```

### 3. 전략 인터페이스 (추상화의 핵심)

```python
# shared/strategy/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar
from shared.models.signal import Signal
from shared.models.position import Position

TMarketData = TypeVar('TMarketData')
TConfig = TypeVar('TConfig')


@dataclass
class EntryContext:
    """진입 판단에 필요한 컨텍스트"""
    market_data: dict
    indicators: dict
    current_positions: list[Position]
    timestamp: datetime


@dataclass
class ExitContext:
    """청산 판단에 필요한 컨텍스트"""
    position: Position
    market_data: dict
    indicators: dict
    timestamp: datetime


class EntrySignalGenerator(ABC, Generic[TConfig]):
    """
    진입 시그널 생성기 추상 클래스

    모든 진입 로직은 이 인터페이스를 구현해야 함
    """

    def __init__(self, config: TConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self):
        """설정 유효성 검증"""
        pass

    @property
    @abstractmethod
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록 반환"""
        pass

    @abstractmethod
    async def generate(self, context: EntryContext) -> Signal | None:
        """
        진입 시그널 생성

        Returns:
            Signal if entry condition met, None otherwise
        """
        pass


class ExitSignalGenerator(ABC, Generic[TConfig]):
    """
    청산 시그널 생성기 추상 클래스

    모든 청산 로직은 이 인터페이스를 구현해야 함
    """

    def __init__(self, config: TConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self):
        """설정 유효성 검증"""
        pass

    @abstractmethod
    async def should_exit(self, context: ExitContext) -> tuple[bool, str]:
        """
        청산 여부 판단

        Returns:
            (should_exit: bool, reason: str)
        """
        pass

    @abstractmethod
    def update_state(self, context: ExitContext):
        """포지션 상태 업데이트 (트레일링 등)"""
        pass


class PositionSizer(ABC, Generic[TConfig]):
    """포지션 사이징 추상 클래스"""

    def __init__(self, config: TConfig):
        self.config = config

    @abstractmethod
    def calculate(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position]
    ) -> int:
        """
        포지션 크기 계산

        Returns:
            quantity: 매매 수량
        """
        pass


class TradingStrategy:
    """
    트레이딩 전략 - 진입/청산/사이징 조합

    이 클래스는 구체적인 로직을 포함하지 않고,
    주입받은 컴포넌트들을 조합하여 사용
    """

    def __init__(
        self,
        name: str,
        entry: EntrySignalGenerator,
        exit: ExitSignalGenerator,
        position_sizer: PositionSizer,
    ):
        self.name = name
        self.entry = entry
        self.exit = exit
        self.position_sizer = position_sizer

    @property
    def required_indicators(self) -> list[str]:
        """필요한 모든 지표"""
        return self.entry.required_indicators

    async def check_entry(self, context: EntryContext) -> Signal | None:
        """진입 조건 확인"""
        return await self.entry.generate(context)

    async def check_exit(self, context: ExitContext) -> tuple[bool, str]:
        """청산 조건 확인"""
        return await self.exit.should_exit(context)

    def calculate_position_size(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position]
    ) -> int:
        """포지션 크기 계산"""
        return self.position_sizer.calculate(signal, account_balance, current_positions)
```

### 4. 3-Stage Exit 구현 (설정 기반)

```python
# shared/strategy/exit/three_stage.py
from enum import Enum
from dataclasses import dataclass
from shared.strategy.base import ExitSignalGenerator, ExitContext


class ExitState(Enum):
    SURVIVAL = "survival"
    BREAKEVEN = "breakeven"
    MAXIMIZE = "maximize"


@dataclass
class ThreeStageConfig:
    """3-Stage Exit 설정 - YAML에서 로드"""
    hard_stop_pct: float
    breakeven_threshold_pct: float
    breakeven_buffer_pct: float
    maximize_threshold_pct: float
    trailing_stop_pct: float
    tight_trailing_pct: float
    tight_trailing_trigger_pct: float


class ThreeStageExit(ExitSignalGenerator[ThreeStageConfig]):
    """
    3-Stage Dynamic Exit Strategy

    Stage 1 (Survival): Hard stop loss
    Stage 2 (Breakeven): Move stop to entry price
    Stage 3 (Maximize): Trailing stop with dynamic width

    모든 임계값은 설정에서 로드 - 하드코딩 없음
    """

    def __init__(self, config: ThreeStageConfig):
        super().__init__(config)
        self._states: dict[str, ExitState] = {}
        self._highest_prices: dict[str, float] = {}

    def _validate_config(self):
        """설정 유효성 검증"""
        c = self.config
        assert c.hard_stop_pct > 0, "hard_stop_pct must be positive"
        assert c.breakeven_threshold_pct > 0, "breakeven_threshold_pct must be positive"
        assert c.maximize_threshold_pct > c.breakeven_threshold_pct, \
            "maximize_threshold_pct must be greater than breakeven_threshold_pct"
        assert c.trailing_stop_pct > 0, "trailing_stop_pct must be positive"
        assert c.tight_trailing_pct < c.trailing_stop_pct, \
            "tight_trailing_pct must be less than trailing_stop_pct"

    def _get_state(self, position_id: str) -> ExitState:
        return self._states.get(position_id, ExitState.SURVIVAL)

    def _set_state(self, position_id: str, state: ExitState):
        self._states[position_id] = state

    async def should_exit(self, context: ExitContext) -> tuple[bool, str]:
        """청산 여부 판단"""
        position = context.position
        current_price = context.market_data['close']

        pnl_pct = self._calc_pnl_pct(position, current_price)
        state = self._get_state(position.id)

        # State Machine 처리
        if state == ExitState.SURVIVAL:
            return self._handle_survival(position, pnl_pct)
        elif state == ExitState.BREAKEVEN:
            return self._handle_breakeven(position, pnl_pct, current_price)
        elif state == ExitState.MAXIMIZE:
            return self._handle_maximize(position, pnl_pct, current_price)

        return False, ""

    def _handle_survival(self, position, pnl_pct: float) -> tuple[bool, str]:
        """Stage 1: Survival Mode"""
        c = self.config

        # Hard Stop
        if pnl_pct <= -c.hard_stop_pct:
            return True, f"HARD_STOP (pnl: {pnl_pct:.2f}%)"

        # State Transition: SURVIVAL -> BREAKEVEN
        if pnl_pct >= c.breakeven_threshold_pct:
            self._set_state(position.id, ExitState.BREAKEVEN)

        return False, ""

    def _handle_breakeven(self, position, pnl_pct: float, current_price: float) -> tuple[bool, str]:
        """Stage 2: Breakeven Mode"""
        c = self.config

        # Breakeven Stop
        if pnl_pct <= c.breakeven_buffer_pct:
            return True, f"BREAKEVEN_STOP (pnl: {pnl_pct:.2f}%)"

        # State Transition: BREAKEVEN -> MAXIMIZE
        if pnl_pct >= c.maximize_threshold_pct:
            self._set_state(position.id, ExitState.MAXIMIZE)
            self._highest_prices[position.id] = current_price

        return False, ""

    def _handle_maximize(self, position, pnl_pct: float, current_price: float) -> tuple[bool, str]:
        """Stage 3: Maximize Mode"""
        c = self.config

        # Update highest price
        highest = self._highest_prices.get(position.id, current_price)
        if current_price > highest:
            self._highest_prices[position.id] = current_price
            highest = current_price

        # Dynamic trailing stop width
        trailing_pct = c.trailing_stop_pct
        if pnl_pct >= c.tight_trailing_trigger_pct:
            trailing_pct = c.tight_trailing_pct

        # Calculate drop from high
        drop_from_high = (highest - current_price) / highest * 100

        if drop_from_high >= trailing_pct:
            return True, f"TRAILING_STOP (drop: {drop_from_high:.2f}%, trail: {trailing_pct}%)"

        return False, ""

    def _calc_pnl_pct(self, position, current_price: float) -> float:
        """PnL 퍼센트 계산"""
        if position.side == "BUY":
            return (current_price - position.entry_price) / position.entry_price * 100
        else:
            return (position.entry_price - current_price) / position.entry_price * 100

    def update_state(self, context: ExitContext):
        """외부에서 상태 업데이트 호출"""
        # should_exit에서 이미 상태 업데이트가 이루어짐
        pass

    def cleanup(self, position_id: str):
        """포지션 종료 시 상태 정리"""
        self._states.pop(position_id, None)
        self._highest_prices.pop(position_id, None)
```

### 5. 전략 팩토리 (설정 → 객체)

```python
# shared/strategy/factory.py
from shared.config.loader import ConfigLoader
from shared.config.schema import StrategyConfig
from shared.strategy.base import TradingStrategy, EntrySignalGenerator, ExitSignalGenerator, PositionSizer
from shared.strategy.registry import EntryRegistry, ExitRegistry, SizerRegistry


class StrategyFactory:
    """
    설정 파일로부터 전략 객체 생성

    이 팩토리를 통해 YAML 설정만으로 전략이 생성됨
    코드 수정 없이 전략 변경 가능
    """

    @classmethod
    def create(cls, config: StrategyConfig) -> TradingStrategy:
        """설정으로부터 전략 생성"""
        strategy_cfg = config.strategy

        # 진입 로직 생성
        entry = EntryRegistry.create(
            strategy_cfg.entry.type,
            strategy_cfg.entry.params
        )

        # 청산 로직 생성
        exit = ExitRegistry.create(
            strategy_cfg.exit.type,
            strategy_cfg.exit.params
        )

        # 포지션 사이저 생성
        sizer = SizerRegistry.create(
            strategy_cfg.position.type,
            strategy_cfg.position.params
        )

        return TradingStrategy(
            name=strategy_cfg.name,
            entry=entry,
            exit=exit,
            position_sizer=sizer,
        )

    @classmethod
    def create_from_file(cls, asset_class: str, strategy_name: str) -> TradingStrategy:
        """파일 경로로부터 전략 생성"""
        config = ConfigLoader.load_strategy(asset_class, strategy_name)
        return cls.create(config)

    @classmethod
    def create_all(cls, asset_class: str = None) -> list[TradingStrategy]:
        """모든 활성화된 전략 생성"""
        configs = ConfigLoader.load_all_strategies(asset_class)
        return [cls.create(config) for config in configs]
```

### 6. 레지스트리 패턴 (동적 등록)

```python
# shared/strategy/registry.py
from typing import Type, Callable, Any


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
            raise ValueError(f"Unknown component: {name}. Available: {available}")

        component_class = cls._components[name]

        # params dict를 config 객체로 변환 (있는 경우)
        if hasattr(component_class, 'CONFIG_CLASS'):
            config = component_class.CONFIG_CLASS(**params)
            return component_class(config)

        return component_class(params)

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


# 사용 예시 - 데코레이터로 자동 등록
@EntryRegistry.register("bb_lower_reentry")
class BBLowerReentryEntry(EntrySignalGenerator):
    CONFIG_CLASS = BBEntryConfig
    ...

@ExitRegistry.register("three_stage")
class ThreeStageExit(ExitSignalGenerator):
    CONFIG_CLASS = ThreeStageConfig
    ...
```

---

## 📈 LLM 시장 분석 모듈

`shared/llm/` 모듈은 KRX Open API와 OpenAI를 활용한 통합 시장 분석을 제공한다.

### 주요 컴포넌트

| 컴포넌트 | 설명 |
|---------|------|
| `LLMConfig` | YAML/환경변수 기반 설정 (config/llm.yaml) |
| `KRXOpenAPIClient` | KRX Open API 클라이언트 (지수/ETF/선물/옵션/채권) |
| `UnifiedMarketAnalyzer` | 통합 시장 분석 오케스트레이터 |
| `ETFFlowAnalyzer` | ETF 자금 흐름 분석 |
| `FuturesAnalyzer` | KOSPI200 선물 분석 |
| `OptionsAnalyzer` | 옵션 풋콜비율 분석 |

### 사용 예시

```python
from shared.llm import UnifiedMarketAnalyzer, LLMConfig

# 설정 로드 (config/llm.yaml + 환경변수)
config = LLMConfig.from_yaml("config/llm.yaml")

# 분석 실행
analyzer = UnifiedMarketAnalyzer(config)
result = analyzer.run_analysis(mode="all", verbose=True)

# 리포트 생성
report = analyzer.generate_report(result)
```

### 환경 변수

```bash
# .env
KRX_API_KEY=your-krx-api-key      # data.krx.co.kr에서 발급
OPENAI_API_KEY=your-openai-key
LLM_MODEL=gpt-4o-mini
```

---

## 📊 백테스트 & MLflow 통합

### 백테스트 실행 플로우

```
1. 설정 로드 (YAML)
       ↓
2. 전략 생성 (Factory)
       ↓
3. 데이터 로드 (ClickHouse)
       ↓
4. 시뮬레이션 실행
       ↓
5. MLflow 로깅
   - Parameters: 전략 설정 전체
   - Metrics: 수익률, 샤프, MDD 등
   - Artifacts: 거래 내역, 차트
       ↓
6. 결과 비교 & 최적화
```

### CLI 명령어

```bash
# 백테스트 실행
sts backtest run --strategy bb_reversion --asset stock --start 2024-01-01 --end 2024-12-31

# 파라미터 최적화 (Optuna 통합)
sts optimize --strategy bb_reversion --asset stock --metric sharpe_ratio --trials 100

# 데이터 수집 (Data Collection)
sts collect --source kis --asset stock --symbols 005930,000660 --days 30

# 트레이딩 시스템 헬스 체크
sts health

# MLflow UI 실행
sts mlflow ui

# 최적 파라미터 조회
sts backtest best --strategy bb_reversion --asset stock

# 최적 파라미터로 설정 파일 업데이트
sts backtest apply --run-id <mlflow_run_id>
```

---

## ⚠️ 개발 규칙 (Claude Code 필수 준수)

### 1. 하드코딩 금지

```python
# ❌ 절대 금지
HARD_STOP_PCT = 2.0
if rsi < 30:
    ...

# ✅ 반드시 설정에서 로드
if rsi < self.config.entry.rsi_oversold:
    ...
```

### 2. 중복 코드 금지

```python
# ❌ 각 도메인에서 동일 로직 반복 금지
# domains/stock/exit.py
def calc_pnl(entry, current):
    return (current - entry) / entry * 100

# domains/futures/exit.py
def calc_pnl(entry, current):  # 동일 코드!
    return (current - entry) / entry * 100

# ✅ shared 모듈로 추출
# shared/utils/calc.py
def calc_pnl_pct(entry_price: float, current_price: float, side: str) -> float:
    if side == "BUY":
        return (current_price - entry_price) / entry_price * 100
    return (entry_price - current_price) / entry_price * 100
```

### 3. 새 전략 추가 절차

1. `config/strategies/{asset}/{name}.yaml` 작성
2. 필요시 새 Entry/Exit 클래스 구현 (shared/strategy/)
3. 레지스트리에 등록 (`@EntryRegistry.register("name")`)
4. 테스트 작성
5. **코드 수정 없이 설정만으로 활성화**

### 4. 테스트 필수

```bash
# 모든 PR 전 실행
pytest tests/ -v
pytest tests/unit/strategy/ -v  # 전략 단위 테스트
pytest tests/integration/ -v     # 통합 테스트
```

---

## 📝 코드 스타일

- Python 3.11+
- Type hints 필수
- Docstring (Google style)
- Black + Ruff 포맷팅
- pytest 테스트

```bash
# 포맷팅
black .
ruff check --fix .

# 타입 체크
mypy shared/ domains/

# 테스트
pytest tests/ -v --cov=shared --cov=domains
```

---

## 🚀 Quick Commands

```bash
# 개발 환경 설정
make setup

# 테스트
make test

# 백테스트 실행
make backtest STRATEGY=bb_reversion ASSET=stock

# MLflow UI
make mlflow-ui

# Docker 실행
make docker-up
```
