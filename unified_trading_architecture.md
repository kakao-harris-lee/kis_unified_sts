# KIS Unified Trading Platform - 통합 아키텍처 설계서

## 1. Executive Summary

### 1.1 프로젝트 개요
두 개의 KIS OpenAPI 기반 트레이딩 시스템을 통합하여 **주식(Stock)**과 **선물(Futures)**을 
동시에 운영할 수 있는 확장 가능한 플랫폼을 구축합니다.

| 구분 | quant_moment_sts | kospi_mini_sts |
|------|------------------|----------------|
| **대상** | 주식 (Stock) | KOSPI Mini 선물 (Futures) |
| **전략** | BB Mean Reversion, Volume Momentum | OFI, 마이크로스트럭처 |
| **데이터 저장** | In-Memory (deque) | Redis Streams + ClickHouse |
| **모니터링** | Telegram + Custom Dashboard | Prometheus + Grafana |
| **백테스트** | ✅ MLflow 기반 히스토리 관리 | 자체 백테스트 엔진 |
| **실험 추적** | MLflow (파라미터, 메트릭, 아티팩트) | 없음 |

### 1.2 통합 목표
1. **공통 인프라 통합**: API 인증, 네트워크, 알림 시스템 공유
2. **도메인 분리**: 주식/선물 비즈니스 로직 명확히 분리
3. **확장성 확보**: 새로운 자산 클래스/전략 추가 용이
4. **리스크 통합 관리**: 전체 포트폴리오 관점의 리스크 관리

---

## 2. 현행 시스템 분석

### 2.1 quant_moment_sts (주식 시스템)
```
quant_moment_sts/
├── core/                      # 핵심 비즈니스 로직
│   ├── auth.py               # KIS API 인증
│   ├── websocket.py          # 실시간 시세 (H0STCNT0)
│   ├── market_data.py        # Tick/Candle 버퍼
│   ├── universe_loader.py    # 종목 마스터
│   ├── risk_filter.py        # Negative Screening
│   ├── indicators.py         # BB, RSI, Volume MA
│   ├── signal_scanner.py     # 시그널 스캐너
│   ├── position_manager.py   # 3-Stage Exit
│   ├── order_executor.py     # 주문 실행
│   └── orchestrator.py       # 통합 관리
├── config/                    # 환경 설정
├── dashboard/                 # 백엔드 대시보드
├── dashboard-frontend/        # React 프론트엔드
├── database/                  # DB 스키마
└── services/                  # 서비스 레이어
```

**핵심 특징:**
- asyncio 기반 비동기 처리
- State Machine 기반 3-Stage Exit
- 메모리 기반 실시간 데이터 처리
- 모놀리식 아키텍처

### 2.2 kospi_mini_sts (선물 시스템)
```
kospi_mini_sts/
├── src/
│   ├── collector/            # 데이터 수집
│   ├── processor/            # Feature 처리
│   ├── db_logger/            # ClickHouse 로거
│   ├── prediction/           # 예측 엔진
│   ├── strategy/             # 전략 관리
│   ├── backtest/             # 백테스트 엔진
│   └── cli/                  # CLI 명령어
├── common/                    # 공통 유틸리티
├── config/                    # 설정
├── monitoring/                # Grafana 대시보드
└── models/                    # ML 모델
```

**핵심 특징:**
- Redis Streams 기반 메시지 파이프라인
- ClickHouse 시계열 데이터 저장
- Prometheus + Grafana 모니터링
- 마이크로서비스 지향 아키텍처

---

## 3. 통합 아키텍처 설계

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KIS Unified Trading Platform                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Presentation Layer                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │   Web UI    │  │  Grafana    │  │  Telegram   │  │    CLI     │  │    │
│  │  │  (React)    │  │ Dashboard   │  │    Bot      │  │   (sts)    │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         API Gateway Layer                            │    │
│  │  ┌───────────────────────────────────────────────────────────────┐  │    │
│  │  │                      FastAPI Gateway                           │  │    │
│  │  │  • REST API  • WebSocket  • Authentication  • Rate Limiting   │  │    │
│  │  └───────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌──────────────────────────┬────────────────────────────────────────┐     │
│  │     Stock Domain         │         Futures Domain                  │     │
│  │  ┌────────────────────┐  │  ┌────────────────────────────────┐   │     │
│  │  │  Stock Strategies  │  │  │      Futures Strategies         │   │     │
│  │  │  • BB Reversion    │  │  │  • OFI Momentum                 │   │     │
│  │  │  • Volume Momentum │  │  │  • Pure Micro                   │   │     │
│  │  │  • Custom Strategy │  │  │  • Adaptive Micro               │   │     │
│  │  └────────────────────┘  │  └────────────────────────────────┘   │     │
│  │  ┌────────────────────┐  │  ┌────────────────────────────────┐   │     │
│  │  │  Stock Execution   │  │  │      Futures Execution          │   │     │
│  │  │  • 3-Stage Exit    │  │  │  • Scalping Exit               │   │     │
│  │  │  • Position Mgmt   │  │  │  • Position Mgmt               │   │     │
│  │  └────────────────────┘  │  └────────────────────────────────┘   │     │
│  └──────────────────────────┴────────────────────────────────────────┘     │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Shared Core Layer                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │  KIS API    │  │   Signal    │  │    Risk     │  │  Backtest  │  │    │
│  │  │  Adapter    │  │   Engine    │  │   Manager   │  │   Engine   │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │ Indicator   │  │   Order     │  │  Portfolio  │  │  Notifier  │  │    │
│  │  │ Calculator  │  │  Executor   │  │   Tracker   │  │  Service   │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       Infrastructure Layer                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │   Redis     │  │ ClickHouse  │  │ Prometheus  │  │   Docker   │  │    │
│  │  │  Streams    │  │   (TSDB)    │  │  + Grafana  │  │  Compose   │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 통합 디렉토리 구조

```
kis-unified-trading/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── Makefile
│
├── config/                           # 📁 통합 설정
│   ├── __init__.py
│   ├── base.py                      # 기본 설정 (Pydantic BaseSettings)
│   ├── stock.py                     # 주식 전용 설정
│   ├── futures.py                   # 선물 전용 설정
│   └── logging.yaml                 # 로깅 설정
│
├── shared/                           # 📁 공유 모듈 (Core)
│   ├── __init__.py
│   ├── kis/                         # KIS API 어댑터
│   │   ├── __init__.py
│   │   ├── auth.py                  # 토큰 관리 (통합)
│   │   ├── client.py                # HTTP 클라이언트
│   │   ├── websocket.py             # WebSocket 클라이언트
│   │   └── constants.py             # API 상수 (TR Code 등)
│   │
│   ├── messaging/                   # Redis Streams 추상화
│   │   ├── __init__.py
│   │   ├── publisher.py
│   │   ├── consumer.py
│   │   └── streams.py               # Stream 정의
│   │
│   ├── storage/                     # 데이터 저장소
│   │   ├── __init__.py
│   │   ├── clickhouse.py            # ClickHouse 클라이언트
│   │   ├── redis_cache.py           # Redis 캐시
│   │   └── memory_store.py          # In-Memory Store
│   │
│   ├── indicators/                  # 기술적 지표 (공용)
│   │   ├── __init__.py
│   │   ├── base.py                  # Indicator ABC
│   │   ├── trend.py                 # MA, EMA, MACD
│   │   ├── volatility.py            # BB, ATR
│   │   ├── momentum.py              # RSI, Stochastic
│   │   └── microstructure.py        # OFI, VPIN (선물용)
│   │
│   ├── risk/                        # 리스크 관리
│   │   ├── __init__.py
│   │   ├── position_sizer.py        # 포지션 사이징
│   │   ├── risk_filter.py           # Negative Screening
│   │   └── portfolio_risk.py        # 포트폴리오 리스크
│   │
│   ├── execution/                   # 주문 실행
│   │   ├── __init__.py
│   │   ├── order_executor.py        # 주문 실행 인터페이스
│   │   ├── order_types.py           # 주문 타입 정의
│   │   └── fills.py                 # 체결 처리
│   │
│   ├── notification/                # 알림 서비스
│   │   ├── __init__.py
│   │   ├── telegram.py
│   │   ├── slack.py
│   │   └── notifier.py              # 통합 Notifier
│   │
│   └── models/                      # 공통 데이터 모델
│       ├── __init__.py
│       ├── market.py                # Tick, OHLCV, Quote
│       ├── order.py                 # Order, Fill
│       ├── position.py              # Position
│       └── signal.py                # Signal
│
├── domains/                          # 📁 도메인별 비즈니스 로직
│   ├── __init__.py
│   │
│   ├── stock/                       # 🔷 주식 도메인
│   │   ├── __init__.py
│   │   ├── universe/                # 종목 관리
│   │   │   ├── __init__.py
│   │   │   ├── loader.py            # 유니버스 로더
│   │   │   └── screener.py          # 스크리너
│   │   │
│   │   ├── strategies/              # 주식 전략
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # StockStrategy ABC
│   │   │   ├── bb_reversion.py      # 볼린저 밴드 리버전
│   │   │   ├── volume_momentum.py   # 볼륨 모멘텀
│   │   │   └── registry.py          # 전략 레지스트리
│   │   │
│   │   ├── execution/               # 주식 실행
│   │   │   ├── __init__.py
│   │   │   ├── position_manager.py  # 3-Stage Exit
│   │   │   └── state_machine.py     # 상태 머신
│   │   │
│   │   ├── collector/               # 데이터 수집
│   │   │   ├── __init__.py
│   │   │   └── realtime.py
│   │   │
│   │   └── config.py                # 주식 도메인 설정
│   │
│   └── futures/                     # 🔶 선물 도메인
│       ├── __init__.py
│       ├── universe/                # 선물 종목 관리
│       │   ├── __init__.py
│       │   ├── contract.py          # 선물 계약 관리
│       │   └── rollover.py          # 롤오버 처리
│       │
│       ├── strategies/              # 선물 전략
│       │   ├── __init__.py
│       │   ├── base.py              # FuturesStrategy ABC
│       │   ├── pure_micro.py        # 순수 마이크로스트럭처
│       │   ├── adaptive_micro.py    # 적응형
│       │   ├── ofi_momentum.py      # OFI 모멘텀
│       │   └── registry.py          # 전략 레지스트리
│       │
│       ├── execution/               # 선물 실행
│       │   ├── __init__.py
│       │   ├── position_manager.py
│       │   └── scalping_exit.py
│       │
│       ├── collector/               # 데이터 수집
│       │   ├── __init__.py
│       │   ├── tick_collector.py
│       │   └── historical.py        # 과거 데이터 백필
│       │
│       ├── processor/               # Feature 처리
│       │   ├── __init__.py
│       │   └── feature_processor.py
│       │
│       └── config.py                # 선물 도메인 설정
│
├── services/                         # 📁 애플리케이션 서비스
│   ├── __init__.py
│   │
│   ├── trading/                     # 트레이딩 서비스
│   │   ├── __init__.py
│   │   ├── orchestrator.py          # 통합 오케스트레이터
│   │   ├── stock_service.py         # 주식 트레이딩 서비스
│   │   └── futures_service.py       # 선물 트레이딩 서비스
│   │
│   ├── backtest/                    # 백테스트 서비스 (MLflow 통합)
│   │   ├── __init__.py
│   │   ├── engine.py                # 백테스트 엔진 (통합)
│   │   ├── mlflow_tracker.py        # MLflow 실험 추적 ⭐ (quant_moment_sts에서 이관)
│   │   ├── data_loader.py           # 데이터 로더
│   │   ├── simulator.py             # 시뮬레이터
│   │   ├── reporter.py              # 결과 리포터
│   │   └── worker.py                # 백테스트 워커 (비동기 실행)
│   │
│   ├── monitoring/                  # 모니터링 서비스
│   │   ├── __init__.py
│   │   ├── metrics.py               # Prometheus 메트릭
│   │   └── health.py                # 헬스 체크
│   │
│   └── db_logger/                   # DB 로거
│       ├── __init__.py
│       └── batch_writer.py
│
├── api/                              # 📁 API 레이어
│   ├── __init__.py
│   ├── main.py                      # FastAPI 앱
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── stock.py                 # 주식 API
│   │   ├── futures.py               # 선물 API
│   │   ├── backtest.py              # 백테스트 API
│   │   └── monitoring.py            # 모니터링 API
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── handlers.py              # WebSocket 핸들러
│   └── deps.py                      # 의존성
│
├── cli/                              # 📁 CLI
│   ├── __init__.py
│   ├── main.py                      # typer 기반 CLI
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── stock.py
│   │   ├── futures.py
│   │   ├── backtest.py
│   │   └── paper.py
│   └── utils.py
│
├── dashboard/                        # 📁 대시보드
│   ├── frontend/                    # React 프론트엔드
│   │   ├── src/
│   │   ├── package.json
│   │   └── ...
│   └── grafana/                     # Grafana 대시보드
│       └── dashboards/
│
├── deploy/                           # 📁 배포
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.collector
│   ├── kubernetes/
│   └── scripts/
│
├── monitoring/                       # 📁 모니터링 설정
│   ├── prometheus/
│   └── grafana/
│
├── tests/                            # 📁 테스트
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── shared/
│   │   ├── domains/
│   │   └── services/
│   ├── integration/
│   └── e2e/
│
├── scripts/                          # 📁 운영 스크립트
│   ├── run_stock_trading.py
│   ├── run_futures_trading.py
│   ├── run_backtest.py
│   └── backfill_data.py
│
└── docs/                             # 📁 문서
    ├── architecture.md
    ├── api.md
    ├── strategies.md
    └── deployment.md
```

---

## 4. 핵심 컴포넌트 상세 설계

### 4.1 Strategy Pattern - 전략 추상화

```python
# shared/strategies/base.py
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Generic, TypeVar

class AssetClass(Enum):
    STOCK = "stock"
    FUTURES = "futures"
    OPTION = "option"

@dataclass
class Signal:
    symbol: str
    direction: str  # "BUY", "SELL", "HOLD"
    strength: float  # 0.0 ~ 1.0
    strategy_name: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)

T = TypeVar('T')  # Market Data Type

class BaseStrategy(ABC, Generic[T]):
    """전략 기본 추상 클래스"""
    
    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__
        
    @property
    @abstractmethod
    def asset_class(self) -> AssetClass:
        """대상 자산 클래스"""
        pass
    
    @property
    @abstractmethod
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록"""
        pass
    
    @abstractmethod
    async def generate_signal(self, data: T) -> Signal | None:
        """시그널 생성"""
        pass
    
    @abstractmethod
    def validate_entry(self, signal: Signal) -> bool:
        """진입 조건 검증"""
        pass
```

```python
# domains/stock/strategies/bb_reversion.py
class BBReversionStrategy(BaseStrategy[StockMarketData]):
    """볼린저 밴드 평균회귀 전략"""
    
    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.STOCK
    
    @property
    def required_indicators(self) -> list[str]:
        return ["BB_20_2", "RSI_14", "VOLUME_MA_20"]
    
    async def generate_signal(self, data: StockMarketData) -> Signal | None:
        bb = data.indicators["BB_20_2"]
        rsi = data.indicators["RSI_14"]
        
        # 볼린저 밴드 하단 이탈 후 재진입
        if data.prev_close < bb.lower and data.close > bb.lower:
            if rsi < 30:  # 과매도 확인
                return Signal(
                    symbol=data.symbol,
                    direction="BUY",
                    strength=self._calc_strength(rsi, bb),
                    strategy_name=self.name,
                    timestamp=data.timestamp,
                    metadata={"bb_position": "lower_reentry", "rsi": rsi}
                )
        return None
```

```python
# domains/futures/strategies/pure_micro.py
class PureMicroStrategy(BaseStrategy[FuturesMarketData]):
    """순수 마이크로스트럭처 전략"""
    
    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.FUTURES
    
    @property
    def required_indicators(self) -> list[str]:
        return ["OFI", "LIQUIDITY_SCORE", "ORDERBOOK_IMBALANCE"]
    
    async def generate_signal(self, data: FuturesMarketData) -> Signal | None:
        ofi_z = data.indicators["OFI"].z_score
        imbalance = data.indicators["ORDERBOOK_IMBALANCE"]
        
        if ofi_z > self.config["ofi_threshold"]:
            if imbalance > self.config["imbalance_threshold"]:
                return Signal(
                    symbol=data.symbol,
                    direction="BUY",
                    strength=min(ofi_z / 3.0, 1.0),
                    strategy_name=self.name,
                    timestamp=data.timestamp,
                    metadata={"ofi_z": ofi_z, "imbalance": imbalance}
                )
        return None
```

### 4.2 Strategy Registry - 전략 등록/관리

```python
# shared/strategies/registry.py
from typing import Type

class StrategyRegistry:
    """전략 레지스트리 - Singleton"""
    
    _instance = None
    _strategies: dict[str, Type[BaseStrategy]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, name: str = None):
        """데코레이터로 전략 등록"""
        def decorator(strategy_class: Type[BaseStrategy]):
            key = name or strategy_class.__name__
            cls._strategies[key] = strategy_class
            return strategy_class
        return decorator
    
    @classmethod
    def get(cls, name: str, config: dict) -> BaseStrategy:
        """전략 인스턴스 생성"""
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name](config)
    
    @classmethod
    def list_by_asset(cls, asset_class: AssetClass) -> list[str]:
        """자산 클래스별 전략 목록"""
        return [
            name for name, strategy in cls._strategies.items()
            if strategy.asset_class == asset_class
        ]

# 사용 예시
@StrategyRegistry.register("bb_reversion")
class BBReversionStrategy(BaseStrategy):
    ...

@StrategyRegistry.register("pure_micro")
class PureMicroStrategy(BaseStrategy):
    ...
```

### 4.3 KIS API Adapter - 통합 API 클라이언트

```python
# shared/kis/client.py
from abc import ABC, abstractmethod
from enum import Enum

class TradingMode(Enum):
    PAPER = "paper"    # 모의투자
    REAL = "real"      # 실전투자

class MarketType(Enum):
    STOCK = "stock"
    FUTURES = "futures"

class KISClient:
    """KIS API 통합 클라이언트"""
    
    def __init__(self, config: KISConfig):
        self.config = config
        self.auth = KISAuth(config)
        self._session: aiohttp.ClientSession | None = None
        
        # 마켓 타입별 베이스 URL
        self._base_urls = {
            (TradingMode.PAPER, MarketType.STOCK): "https://openapivts.koreainvestment.com:29443",
            (TradingMode.REAL, MarketType.STOCK): "https://openapi.koreainvestment.com:9443",
            (TradingMode.PAPER, MarketType.FUTURES): "https://openapivts.koreainvestment.com:29443",
            (TradingMode.REAL, MarketType.FUTURES): "https://openapi.koreainvestment.com:9443",
        }
    
    def get_base_url(self, market: MarketType) -> str:
        return self._base_urls[(self.config.mode, market)]
    
    async def request(
        self,
        tr_id: str,
        path: str,
        market: MarketType,
        params: dict = None,
        body: dict = None,
        method: str = "GET"
    ) -> dict:
        """API 요청 공통 메서드"""
        url = f"{self.get_base_url(market)}{path}"
        headers = await self._build_headers(tr_id)
        
        async with self._session.request(method, url, headers=headers, params=params, json=body) as resp:
            return await resp.json()

# 도메인별 확장
class StockAPIClient(KISClient):
    """주식 전용 API 클라이언트"""
    
    async def get_price(self, symbol: str) -> dict:
        return await self.request(
            tr_id="FHKST01010100",
            path="/uapi/domestic-stock/v1/quotations/inquire-price",
            market=MarketType.STOCK,
            params={"FID_INPUT_ISCD": symbol}
        )
    
    async def place_order(self, order: StockOrder) -> dict:
        tr_id = "VTTC0802U" if self.config.mode == TradingMode.PAPER else "TTTC0802U"
        return await self.request(
            tr_id=tr_id,
            path="/uapi/domestic-stock/v1/trading/order-cash",
            market=MarketType.STOCK,
            body=order.to_dict(),
            method="POST"
        )

class FuturesAPIClient(KISClient):
    """선물 전용 API 클라이언트"""
    
    async def get_price(self, symbol: str) -> dict:
        return await self.request(
            tr_id="FHKIF03010100",
            path="/uapi/domestic-futureoption/v1/quotations/inquire-price",
            market=MarketType.FUTURES,
            params={"FID_INPUT_ISCD": symbol}
        )
    
    async def place_order(self, order: FuturesOrder) -> dict:
        tr_id = "VTTO1101U" if self.config.mode == TradingMode.PAPER else "TTTO1101U"
        return await self.request(
            tr_id=tr_id,
            path="/uapi/domestic-futureoption/v1/trading/order",
            market=MarketType.FUTURES,
            body=order.to_dict(),
            method="POST"
        )
```

### 4.4 Redis Streams 메시지 파이프라인

```python
# shared/messaging/streams.py
from enum import Enum

class StreamName(Enum):
    # 주식 스트림
    STOCK_RAW_DATA = "stock:raw_data"
    STOCK_FEATURES = "stock:features"
    STOCK_SIGNALS = "stock:signals"
    STOCK_ORDERS = "stock:orders"
    
    # 선물 스트림
    FUTURES_RAW_DATA = "futures:raw_data"
    FUTURES_FEATURES = "futures:features"
    FUTURES_SIGNALS = "futures:signals"
    FUTURES_ORDERS = "futures:orders"
    
    # 공통 스트림
    SYSTEM_EVENTS = "system:events"
    NOTIFICATIONS = "system:notifications"

# shared/messaging/publisher.py
class StreamPublisher:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def publish(self, stream: StreamName, data: dict, max_len: int = 10000):
        """스트림에 메시지 발행"""
        return await self.redis.xadd(
            stream.value,
            data,
            maxlen=max_len,
            approximate=True
        )

# shared/messaging/consumer.py
class StreamConsumer:
    def __init__(self, redis_client: Redis, group: str, consumer: str):
        self.redis = redis_client
        self.group = group
        self.consumer = consumer
    
    async def consume(
        self,
        streams: list[StreamName],
        handler: Callable,
        batch_size: int = 10
    ):
        """스트림에서 메시지 소비"""
        stream_keys = {s.value: ">" for s in streams}
        
        while True:
            messages = await self.redis.xreadgroup(
                groupname=self.group,
                consumername=self.consumer,
                streams=stream_keys,
                count=batch_size,
                block=1000
            )
            
            for stream_name, entries in messages:
                for entry_id, data in entries:
                    await handler(stream_name, data)
                    await self.redis.xack(stream_name, self.group, entry_id)
```

### 4.5 Position Manager - 도메인별 Exit 전략

```python
# domains/stock/execution/position_manager.py
from enum import Enum
from dataclasses import dataclass

class PositionState(Enum):
    SURVIVAL = "survival"      # 생존 모드: -2% 하드 스탑
    BREAKEVEN = "breakeven"    # 안도 모드: 본전 스탑
    MAXIMIZE = "maximize"      # 추세 모드: 트레일링 스탑

@dataclass
class StockPosition:
    symbol: str
    entry_price: float
    quantity: int
    state: PositionState = PositionState.SURVIVAL
    highest_price: float = 0.0
    stop_price: float = 0.0

class StockPositionManager:
    """주식 3-Stage Exit 포지션 관리자"""
    
    def __init__(self, config: StockExitConfig):
        self.config = config
        self.positions: dict[str, StockPosition] = {}
    
    def update_state(self, position: StockPosition, current_price: float):
        """상태 머신 업데이트"""
        pnl_pct = (current_price - position.entry_price) / position.entry_price * 100
        
        match position.state:
            case PositionState.SURVIVAL:
                if pnl_pct >= self.config.breakeven_threshold:  # +2%
                    position.state = PositionState.BREAKEVEN
                    position.stop_price = position.entry_price * 1.001  # 본전 + 수수료
                elif pnl_pct <= -self.config.hard_stop:  # -2%
                    return self._create_exit_signal(position, "HARD_STOP")
                    
            case PositionState.BREAKEVEN:
                if pnl_pct >= self.config.maximize_threshold:  # +5%
                    position.state = PositionState.MAXIMIZE
                    position.highest_price = current_price
                elif current_price <= position.stop_price:
                    return self._create_exit_signal(position, "BREAKEVEN_STOP")
                    
            case PositionState.MAXIMIZE:
                position.highest_price = max(position.highest_price, current_price)
                trail_pct = self.config.trailing_stop  # 고점 대비 -3%
                
                # 급등 시 감시폭 축소
                if pnl_pct >= 10:
                    trail_pct = self.config.tight_trailing_stop  # -1.5%
                
                position.stop_price = position.highest_price * (1 - trail_pct / 100)
                
                if current_price <= position.stop_price:
                    return self._create_exit_signal(position, "TRAILING_STOP")
        
        return None
```

```python
# domains/futures/execution/position_manager.py
class FuturesPositionManager:
    """선물 스캘핑 포지션 관리자"""
    
    def __init__(self, config: FuturesExitConfig):
        self.config = config
        self.positions: dict[str, FuturesPosition] = {}
    
    def update(self, position: FuturesPosition, current_price: float, ofi: float):
        """선물 포지션 업데이트 - 마이크로스트럭처 기반"""
        tick_pnl = self._calc_tick_pnl(position, current_price)
        
        # OFI 반전 감지
        if self._detect_ofi_reversal(position, ofi):
            return self._create_exit_signal(position, "OFI_REVERSAL")
        
        # 틱 기반 손절
        if tick_pnl <= -self.config.stop_ticks:
            return self._create_exit_signal(position, "TICK_STOP")
        
        # 목표 수익 도달
        if tick_pnl >= self.config.target_ticks:
            return self._create_exit_signal(position, "TARGET_REACHED")
        
        return None
```

### 4.6 Backtest Engine + MLflow 통합 - 실험 추적 & 히스토리 관리

quant_moment_sts의 MLflow 기반 백테스팅 히스토리 관리를 통합 플랫폼의 핵심 기능으로 확장합니다.

```python
# services/backtest/mlflow_tracker.py
"""
MLflow 기반 백테스팅 히스토리 관리
- 전략 파라미터, 성능 메트릭, 아티팩트 추적
- 실험 비교 및 모델 레지스트리
"""
import mlflow
from mlflow.tracking import MlflowClient
from dataclasses import dataclass, asdict
from typing import Any
import pandas as pd
import json


@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float
    commission_rate: float
    slippage_ticks: int
    strategy_name: str
    strategy_params: dict
    asset_class: str  # "stock" or "futures"


@dataclass
class BacktestResult:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trades: list
    equity_curve: pd.DataFrame


class MLflowBacktestTracker:
    """
    MLflow를 사용한 백테스트 실험 추적
    
    Features:
    - 전략 파라미터 로깅
    - 성능 메트릭 추적
    - Equity Curve, Trade Log 아티팩트 저장
    - 실험 비교 및 최적 파라미터 탐색
    """
    
    def __init__(self, tracking_uri: str = None, experiment_name: str = "backtest"):
        self.tracking_uri = tracking_uri or "mlruns"
        mlflow.set_tracking_uri(self.tracking_uri)
        self.experiment_name = experiment_name
        self.client = MlflowClient()
        
        # 실험 생성 또는 가져오기
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            self.experiment_id = mlflow.create_experiment(experiment_name)
        else:
            self.experiment_id = experiment.experiment_id
    
    def start_run(self, config: BacktestConfig, run_name: str = None) -> str:
        """백테스트 실행 시작 - MLflow Run 생성"""
        mlflow.set_experiment(self.experiment_name)
        
        run = mlflow.start_run(run_name=run_name or f"{config.strategy_name}_{config.asset_class}")
        
        # 설정 파라미터 로깅
        mlflow.log_params({
            "strategy_name": config.strategy_name,
            "asset_class": config.asset_class,
            "start_date": str(config.start_date),
            "end_date": str(config.end_date),
            "initial_capital": config.initial_capital,
            "commission_rate": config.commission_rate,
            "slippage_ticks": config.slippage_ticks,
        })
        
        # 전략 파라미터 개별 로깅
        for key, value in config.strategy_params.items():
            mlflow.log_param(f"strategy.{key}", value)
        
        return run.info.run_id
    
    def log_result(self, result: BacktestResult):
        """백테스트 결과 메트릭 로깅"""
        mlflow.log_metrics({
            "total_return": result.total_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "total_trades": result.total_trades,
        })
    
    def log_artifacts(self, result: BacktestResult, output_dir: str = "artifacts"):
        """아티팩트 저장 (Equity Curve, Trade Log 등)"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Equity Curve CSV
        equity_path = f"{output_dir}/equity_curve.csv"
        result.equity_curve.to_csv(equity_path, index=False)
        mlflow.log_artifact(equity_path)
        
        # Trade Log JSON
        trades_path = f"{output_dir}/trades.json"
        with open(trades_path, "w") as f:
            json.dump([asdict(t) if hasattr(t, '__dataclass_fields__') else t 
                      for t in result.trades], f, default=str, indent=2)
        mlflow.log_artifact(trades_path)
        
        # Equity Curve 시각화
        self._log_equity_chart(result.equity_curve, output_dir)
    
    def _log_equity_chart(self, equity_df: pd.DataFrame, output_dir: str):
        """Equity Curve 차트 생성 및 저장"""
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(equity_df['timestamp'], equity_df['equity'], linewidth=1.5)
        ax.set_title('Equity Curve')
        ax.set_xlabel('Date')
        ax.set_ylabel('Equity')
        ax.grid(True, alpha=0.3)
        
        chart_path = f"{output_dir}/equity_curve.png"
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        mlflow.log_artifact(chart_path)
    
    def end_run(self, status: str = "FINISHED"):
        """백테스트 실행 종료"""
        mlflow.end_run(status=status)
    
    def compare_runs(self, metric: str = "sharpe_ratio", top_n: int = 10) -> pd.DataFrame:
        """최근 실행들의 성능 비교"""
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id],
            order_by=[f"metrics.{metric} DESC"],
            max_results=top_n
        )
        return runs[['run_id', 'params.strategy_name', 'params.asset_class', 
                     f'metrics.{metric}', 'metrics.total_return', 'metrics.max_drawdown']]
    
    def get_best_params(self, strategy_name: str, asset_class: str) -> dict:
        """특정 전략의 최적 파라미터 조회"""
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=f"params.strategy_name = '{strategy_name}' and params.asset_class = '{asset_class}'",
            order_by=["metrics.sharpe_ratio DESC"],
            max_results=1
        )
        
        if runs.empty:
            return {}
        
        # 파라미터 추출
        best_run = runs.iloc[0]
        params = {k.replace("params.strategy.", ""): v 
                  for k, v in best_run.items() 
                  if k.startswith("params.strategy.")}
        return params


class BacktestEngine:
    """통합 백테스트 엔진 - MLflow 통합"""
    
    def __init__(self, config: BacktestConfig, mlflow_tracking_uri: str = None):
        self.config = config
        self.data_loader = BacktestDataLoader()
        self.simulator = TradeSimulator(config)
        self.reporter = BacktestReporter()
        self.tracker = MLflowBacktestTracker(
            tracking_uri=mlflow_tracking_uri,
            experiment_name=f"backtest_{config.asset_class}"
        )
    
    async def run(self, track: bool = True) -> BacktestResult:
        """백테스트 실행 (MLflow 추적 포함)"""
        run_id = None
        
        try:
            # 1. MLflow Run 시작
            if track:
                run_id = self.tracker.start_run(self.config)
            
            # 2. 전략 로드
            strategy = StrategyRegistry.get(
                self.config.strategy_name,
                self.config.strategy_params
            )
            
            # 3. 데이터 로드
            data = await self.data_loader.load(
                asset_class=AssetClass(self.config.asset_class),
                start=self.config.start_date,
                end=self.config.end_date
            )
            
            # 4. 시뮬레이션 실행
            result = await self.simulator.run(strategy, data)
            
            # 5. 결과 로깅
            if track:
                self.tracker.log_result(result)
                self.tracker.log_artifacts(result)
                self.tracker.end_run("FINISHED")
            
            return result
            
        except Exception as e:
            if track and run_id:
                self.tracker.end_run("FAILED")
            raise


class BacktestDataLoader:
    """백테스트 데이터 로더"""
    
    def __init__(self):
        self.clickhouse = ClickHouseClient()
    
    async def load(
        self,
        asset_class: AssetClass,
        start: date,
        end: date
    ) -> pd.DataFrame:
        """ClickHouse에서 과거 데이터 로드"""
        table = f"{asset_class.value}_ohlcv_1m"
        
        query = f"""
        SELECT 
            timestamp, symbol, open, high, low, close, volume
        FROM {table}
        WHERE timestamp >= '{start}' AND timestamp <= '{end}'
        ORDER BY timestamp
        """
        
        return await self.clickhouse.query_df(query)


# =============================================================================
# 백테스트 CLI 통합 (MLflow 대시보드 연동)
# =============================================================================

# cli/commands/backtest.py
import typer
from typing import Optional

app = typer.Typer(help="Backtest commands with MLflow tracking")


@app.command()
def run(
    strategy: str = typer.Option(..., help="Strategy name"),
    asset: str = typer.Option("stock", help="Asset class: stock or futures"),
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., help="End date (YYYY-MM-DD)"),
    capital: float = typer.Option(10_000_000, help="Initial capital"),
    track: bool = typer.Option(True, help="Enable MLflow tracking"),
):
    """Run backtest with MLflow tracking"""
    import asyncio
    from datetime import datetime
    
    config = BacktestConfig(
        start_date=datetime.strptime(start, "%Y-%m-%d").date(),
        end_date=datetime.strptime(end, "%Y-%m-%d").date(),
        initial_capital=capital,
        commission_rate=0.00015,
        slippage_ticks=1,
        strategy_name=strategy,
        strategy_params={},  # 기본 파라미터 사용
        asset_class=asset,
    )
    
    engine = BacktestEngine(config)
    result = asyncio.run(engine.run(track=track))
    
    typer.echo(f"✅ Backtest completed: {strategy} on {asset}")
    typer.echo(f"   Total Return: {result.total_return:.2%}")
    typer.echo(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
    typer.echo(f"   Max Drawdown: {result.max_drawdown:.2%}")


@app.command()
def compare(
    metric: str = typer.Option("sharpe_ratio", help="Metric to compare"),
    top: int = typer.Option(10, help="Top N results"),
):
    """Compare recent backtest runs"""
    tracker = MLflowBacktestTracker()
    results = tracker.compare_runs(metric=metric, top_n=top)
    
    typer.echo(f"\n📊 Top {top} runs by {metric}:")
    typer.echo(results.to_string())


@app.command()
def ui():
    """Launch MLflow UI"""
    import subprocess
    typer.echo("🚀 Starting MLflow UI at http://localhost:5000")
    subprocess.run(["mlflow", "ui", "--port", "5000"])
```

### MLflow 통합 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MLflow Backtest Tracking System                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐  │
│   │  Backtest   │────►│   MLflow    │────►│    Tracking Server      │  │
│   │   Engine    │     │   Tracker   │     │    (Local/Remote)       │  │
│   └─────────────┘     └─────────────┘     └─────────────────────────┘  │
│         │                    │                        │                 │
│         │                    │                        ▼                 │
│         │                    │            ┌─────────────────────────┐  │
│         │                    │            │      MLflow Store       │  │
│         │                    │            │  ┌─────────────────┐    │  │
│         │                    │            │  │   Experiments   │    │  │
│         ▼                    ▼            │  │   - backtest_stock   │ │
│   ┌─────────────┐     ┌─────────────┐    │  │   - backtest_futures │ │
│   │  Strategy   │     │  Artifacts  │    │  └─────────────────┘    │  │
│   │  Registry   │     │  Storage    │    │  ┌─────────────────┐    │  │
│   └─────────────┘     └─────────────┘    │  │      Runs       │    │  │
│                              │            │  │   - params      │    │  │
│                              ▼            │  │   - metrics     │    │  │
│                       ┌─────────────┐    │  │   - artifacts   │    │  │
│                       │ - equity.csv│    │  └─────────────────┘    │  │
│                       │ - trades.json│   └─────────────────────────┘  │
│                       │ - chart.png │                                  │
│                       └─────────────┘                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### MLflow 저장 데이터 구조

| 카테고리 | 항목 | 설명 |
|---------|------|------|
| **Parameters** | strategy_name | 전략 이름 |
| | asset_class | 자산 클래스 (stock/futures) |
| | start_date, end_date | 백테스트 기간 |
| | strategy.* | 전략별 하이퍼파라미터 |
| **Metrics** | total_return | 총 수익률 |
| | sharpe_ratio | 샤프 비율 |
| | max_drawdown | 최대 낙폭 |
| | win_rate | 승률 |
| | profit_factor | 손익비 |
| **Artifacts** | equity_curve.csv | 자산 곡선 데이터 |
| | trades.json | 거래 내역 |
| | equity_curve.png | 시각화 차트 |

---

## 5. 데이터 흐름 설계

### 5.1 실시간 트레이딩 파이프라인

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        Real-time Trading Pipeline                          │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   [KIS WebSocket]                                                          │
│        │                                                                   │
│        ▼                                                                   │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│   │  Collector  │────►│ RAW_DATA    │────►│  Processor  │                │
│   │   (async)   │     │   STREAM    │     │  (Features) │                │
│   └─────────────┘     └─────────────┘     └─────────────┘                │
│                                                  │                         │
│                                                  ▼                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│   │  Position   │◄────│   SIGNAL    │◄────│  Strategy   │                │
│   │   Manager   │     │   STREAM    │     │   Engine    │                │
│   └─────────────┘     └─────────────┘     └─────────────┘                │
│        │                                                                   │
│        ▼                                                                   │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│   │   Order     │────►│   ORDER     │────►│  KIS API    │                │
│   │  Executor   │     │   STREAM    │     │  (Trading)  │                │
│   └─────────────┘     └─────────────┘     └─────────────┘                │
│                                                  │                         │
│                                                  ▼                         │
│                            ┌─────────────────────────────┐                │
│                            │      ClickHouse (TSDB)      │                │
│                            │  • tick_data  • ohlcv_1m    │                │
│                            │  • trades     • positions   │                │
│                            └─────────────────────────────┘                │
│                                                                            │
└───────────────────────────────────────────────────────────────────────────┘
```

### 5.2 데이터베이스 스키마 (ClickHouse)

```sql
-- 주식 OHLCV
CREATE TABLE stock_ohlcv_1m (
    timestamp DateTime64(3) CODEC(DoubleDelta, ZSTD),
    symbol LowCardinality(String),
    open Decimal(18, 2),
    high Decimal(18, 2),
    low Decimal(18, 2),
    close Decimal(18, 2),
    volume UInt64,
    value UInt64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp);

-- 선물 OHLCV
CREATE TABLE futures_ohlcv_1m (
    timestamp DateTime64(3) CODEC(DoubleDelta, ZSTD),
    symbol LowCardinality(String),
    open Decimal(18, 2),
    high Decimal(18, 2),
    low Decimal(18, 2),
    close Decimal(18, 2),
    volume UInt64,
    open_interest UInt64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp);

-- 거래 내역
CREATE TABLE trades (
    id UUID,
    timestamp DateTime64(3),
    asset_class Enum8('stock' = 1, 'futures' = 2),
    symbol LowCardinality(String),
    side Enum8('buy' = 1, 'sell' = 2),
    quantity UInt32,
    price Decimal(18, 2),
    commission Decimal(18, 4),
    strategy LowCardinality(String),
    pnl Decimal(18, 2),
    metadata String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, symbol);

-- Feature 로그 (선물)
CREATE TABLE futures_features (
    timestamp DateTime64(3) CODEC(DoubleDelta, ZSTD),
    symbol LowCardinality(String),
    ofi Float64,
    ofi_z_score Float64,
    liquidity_score Float64,
    orderbook_imbalance Float64,
    spread Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp)
TTL timestamp + INTERVAL 30 DAY;
```

---

## 6. 모니터링 & 대시보드

### 6.1 Prometheus 메트릭

```python
# services/monitoring/metrics.py
from prometheus_client import Counter, Gauge, Histogram

# 시스템 메트릭
SYSTEM_UP = Gauge('trading_system_up', 'System status', ['domain'])
WEBSOCKET_CONNECTED = Gauge('websocket_connected', 'WebSocket connection status')

# 트레이딩 메트릭
SIGNALS_GENERATED = Counter(
    'signals_generated_total',
    'Total signals generated',
    ['domain', 'strategy', 'direction']
)

ORDERS_EXECUTED = Counter(
    'orders_executed_total',
    'Total orders executed',
    ['domain', 'side', 'status']
)

POSITION_PNL = Gauge(
    'position_pnl',
    'Current position PnL',
    ['domain', 'symbol']
)

TRADE_DURATION = Histogram(
    'trade_duration_seconds',
    'Trade holding duration',
    ['domain', 'strategy'],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400]
)

# API 메트릭
API_LATENCY = Histogram(
    'kis_api_latency_seconds',
    'KIS API latency',
    ['endpoint', 'method']
)

API_ERRORS = Counter(
    'kis_api_errors_total',
    'KIS API errors',
    ['endpoint', 'error_code']
)
```

### 6.2 Grafana Dashboard 구성

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     KIS Unified Trading Dashboard                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐ │
│  │   System Status     │  │   Today's P&L       │  │  Active Trades  │ │
│  │   🟢 Stock: UP      │  │   Stock: +1.2%      │  │   Stock: 3      │ │
│  │   🟢 Futures: UP    │  │   Futures: +0.8%    │  │   Futures: 1    │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────┘ │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        Equity Curve (7D)                          │  │
│  │   📈 _______________/\___/\___/\_____/\________________________   │  │
│  │                                                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────┐  ┌────────────────────────────────┐    │
│  │     Stock Strategies       │  │     Futures Strategies          │    │
│  │  ┌─────────────────────┐  │  │  ┌─────────────────────────┐   │    │
│  │  │ BB Reversion        │  │  │  │ Pure Micro              │   │    │
│  │  │ Signals: 5 | Win: 3 │  │  │  │ Signals: 12 | Win: 8   │   │    │
│  │  └─────────────────────┘  │  │  └─────────────────────────┘   │    │
│  │  ┌─────────────────────┐  │  │  ┌─────────────────────────┐   │    │
│  │  │ Volume Momentum     │  │  │  │ OFI Momentum            │   │    │
│  │  │ Signals: 2 | Win: 1 │  │  │  │ Signals: 5 | Win: 3    │   │    │
│  │  └─────────────────────┘  │  │  └─────────────────────────┘   │    │
│  └────────────────────────────┘  └────────────────────────────────┘    │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                       Recent Trades                                │  │
│  │  Time    | Asset   | Symbol  | Side | P&L   | Strategy            │  │
│  │  09:15   | Stock   | 005930  | SELL | +1.2% | BB Reversion        │  │
│  │  09:32   | Futures | 101S6   | SELL | +0.5% | Pure Micro          │  │
│  │  10:05   | Stock   | 000660  | BUY  | -     | Volume Momentum     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 마이그레이션 계획

### 7.1 Phase 1: 공통 인프라 구축 (2주)

```
Week 1:
├── [ ] 프로젝트 초기 설정 (pyproject.toml, 디렉토리 구조)
├── [ ] shared/kis/ - KIS API 어댑터 통합
├── [ ] shared/messaging/ - Redis Streams 추상화
├── [ ] shared/storage/ - ClickHouse, Redis 클라이언트
└── [ ] config/ - 설정 관리 통합

Week 2:
├── [ ] shared/models/ - 공통 데이터 모델
├── [ ] shared/indicators/ - 기술적 지표 통합
├── [ ] shared/notification/ - 알림 서비스
├── [ ] shared/risk/ - 리스크 관리
└── [ ] 단위 테스트 작성
```

### 7.2 Phase 2: 도메인 분리 (2주)

```
Week 3:
├── [ ] domains/stock/ - 주식 도메인 마이그레이션
│   ├── [ ] universe/ - 종목 관리
│   ├── [ ] strategies/ - 전략 마이그레이션
│   └── [ ] execution/ - 3-Stage Exit
└── [ ] 주식 도메인 통합 테스트

Week 4:
├── [ ] domains/futures/ - 선물 도메인 마이그레이션
│   ├── [ ] universe/ - 선물 계약 관리
│   ├── [ ] strategies/ - 전략 마이그레이션
│   └── [ ] processor/ - Feature 처리
└── [ ] 선물 도메인 통합 테스트
```

### 7.3 Phase 3: 서비스 통합 (2주)

```
Week 5:
├── [ ] services/trading/ - 트레이딩 오케스트레이터
├── [ ] services/backtest/ - 백테스트 엔진 통합
├── [ ] api/ - FastAPI 게이트웨이
└── [ ] cli/ - CLI 통합

Week 6:
├── [ ] services/monitoring/ - 모니터링 서비스
├── [ ] dashboard/ - 대시보드 통합
├── [ ] E2E 테스트
└── [ ] 문서화
```

### 7.4 Phase 4: 배포 & 안정화 (1주)

```
Week 7:
├── [ ] Docker Compose 설정
├── [ ] 모의투자 환경 검증
├── [ ] 성능 튜닝
└── [ ] 운영 문서 작성
```

---

## 8. 설정 예시

### 8.1 환경 변수 (.env)

```bash
# KIS API
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NO=your_account_no
KIS_TRADING_MODE=PAPER  # PAPER | REAL

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DATABASE=trading

# MLflow (백테스팅 히스토리 관리)
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_EXPERIMENT_NAME=backtest
MLFLOW_ARTIFACT_ROOT=./mlflow/artifacts

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# Logging
LOG_LEVEL=INFO
```

### 8.2 전략 설정 (config/strategies.yaml)

```yaml
# 주식 전략 설정
stock:
  bb_reversion:
    enabled: true
    params:
      bb_period: 20
      bb_std: 2.0
      rsi_period: 14
      rsi_oversold: 30
    exit:
      hard_stop: 2.0          # -2%
      breakeven_threshold: 2.0 # +2%
      maximize_threshold: 5.0  # +5%
      trailing_stop: 3.0       # 고점 -3%
      tight_trailing_stop: 1.5 # 급등 시 -1.5%
    position:
      max_position_pct: 10     # 계좌의 10%
      max_positions: 5
  
  volume_momentum:
    enabled: true
    params:
      volume_ma_period: 20
      volume_threshold: 3.0    # 평균 대비 3배
      sector_confirm: true
    exit:
      hard_stop: 3.0
      trailing_stop: 5.0

# 선물 전략 설정
futures:
  pure_micro:
    enabled: true
    params:
      ofi_threshold: 1.5
      imbalance_threshold: 0.3
      liquidity_threshold: 0.5
    exit:
      stop_ticks: 5
      target_ticks: 10
    position:
      max_contracts: 2
  
  ofi_momentum:
    enabled: true
    params:
      ofi_lookback: 20
      momentum_threshold: 2.0
```

### 8.3 docker-compose.yml

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  clickhouse:
    image: clickhouse/clickhouse-server:latest
    ports:
      - "8123:8123"
      - "9000:9000"
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    environment:
      CLICKHOUSE_DB: trading

  # MLflow Tracking Server (quant_moment_sts의 핵심 기능)
  mlflow:
    image: python:3.11-slim
    ports:
      - "5000:5000"
    volumes:
      - mlflow_data:/mlflow
      - mlflow_artifacts:/mlflow/artifacts
    environment:
      - MLFLOW_BACKEND_STORE_URI=sqlite:///mlflow/mlflow.db
      - MLFLOW_DEFAULT_ARTIFACT_ROOT=/mlflow/artifacts
    command: >
      bash -c "pip install mlflow && 
               mlflow server 
               --host 0.0.0.0 
               --port 5000 
               --backend-store-uri sqlite:///mlflow/mlflow.db 
               --default-artifact-root /mlflow/artifacts"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # PostgreSQL (MLflow 프로덕션 백엔드 - 선택사항)
  mlflow_db:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: mlflow
      POSTGRES_PASSWORD: mlflow_password
      POSTGRES_DB: mlflow
    volumes:
      - postgres_data:/var/lib/postgresql/data
    profiles:
      - production

  # MLflow Production (PostgreSQL 백엔드)
  mlflow_prod:
    image: python:3.11-slim
    ports:
      - "5000:5000"
    environment:
      - MLFLOW_BACKEND_STORE_URI=postgresql://mlflow:mlflow_password@mlflow_db:5432/mlflow
      - MLFLOW_DEFAULT_ARTIFACT_ROOT=/mlflow/artifacts
    volumes:
      - mlflow_artifacts:/mlflow/artifacts
    command: >
      bash -c "pip install mlflow psycopg2-binary && 
               mlflow server 
               --host 0.0.0.0 
               --port 5000 
               --backend-store-uri postgresql://mlflow:mlflow_password@mlflow_db:5432/mlflow 
               --default-artifact-root /mlflow/artifacts"
    depends_on:
      - mlflow_db
    profiles:
      - production

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards

  api:
    build:
      context: .
      dockerfile: deploy/docker/Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - CLICKHOUSE_HOST=clickhouse
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    depends_on:
      - redis
      - clickhouse
      - mlflow

  stock_collector:
    build:
      context: .
      dockerfile: deploy/docker/Dockerfile.worker
    command: python -m services.trading.stock_service --mode collector
    environment:
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    depends_on:
      - redis
      - mlflow

  futures_collector:
    build:
      context: .
      dockerfile: deploy/docker/Dockerfile.worker
    command: python -m services.trading.futures_service --mode collector
    environment:
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    depends_on:
      - redis
      - mlflow

  backtest_worker:
    build:
      context: .
      dockerfile: deploy/docker/Dockerfile.worker
    command: python -m services.backtest.worker
    environment:
      - MLFLOW_TRACKING_URI=http://mlflow:5000
      - CLICKHOUSE_HOST=clickhouse
    depends_on:
      - clickhouse
      - mlflow

volumes:
  redis_data:
  clickhouse_data:
  grafana_data:
  mlflow_data:
  mlflow_artifacts:
  postgres_data:
```

---

## 9. 주요 설계 원칙

### 9.1 DRY (Don't Repeat Yourself)
- 공통 로직은 `shared/` 모듈로 추출
- 설정은 YAML/환경변수로 외부화
- 전략은 Registry 패턴으로 동적 로딩

### 9.2 Interface Segregation
- 도메인별 명확한 인터페이스 분리
- `BaseStrategy` → `StockStrategy`, `FuturesStrategy`
- `KISClient` → `StockAPIClient`, `FuturesAPIClient`

### 9.3 Dependency Injection
- 설정과 의존성을 주입 방식으로 관리
- 테스트 용이성 확보
- Mock 객체 교체 가능

### 9.4 Event-Driven Architecture
- Redis Streams 기반 비동기 메시지 처리
- 모듈 간 느슨한 결합
- 확장성 및 내결함성

---

## 10. 리스크 및 고려사항

### 10.1 기술적 리스크
| 리스크 | 영향도 | 대응방안 |
|--------|--------|----------|
| KIS API 변경 | 높음 | 어댑터 패턴으로 변경 영향 최소화 |
| Redis 장애 | 높음 | 센티널/클러스터 구성, 로컬 폴백 |
| 네트워크 지연 | 중간 | 재시도 로직, Circuit Breaker |
| 데이터 유실 | 높음 | Redis AOF, ClickHouse 복제 |

### 10.2 운영 리스크
| 리스크 | 영향도 | 대응방안 |
|--------|--------|----------|
| 시스템 과부하 | 중간 | 메트릭 기반 오토스케일링 |
| 주문 오류 | 높음 | Paper Trading 충분히 검증 |
| 토큰 만료 | 중간 | 자동 갱신, 알림 |
| 시장 휴장 | 낮음 | 스케줄러 기반 자동 on/off |

---

## 11. 결론

이 통합 아키텍처는 두 프로젝트의 장점을 결합하여:

1. **공통 인프라 재사용**: KIS API, 알림, 모니터링 통합
2. **도메인 분리**: 주식/선물 비즈니스 로직 독립적 관리
3. **확장성**: 새로운 자산/전략 추가 용이
4. **운영 효율**: 단일 플랫폼에서 통합 관리

를 달성할 수 있습니다.

마이그레이션은 7주 계획으로 단계적으로 진행하며, 각 Phase 완료 시 충분한 테스트를 통해 안정성을 확보합니다.
