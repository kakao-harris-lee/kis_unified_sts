"""Trading Orchestrator

통합 트레이딩 오케스트레이터.

주식/선물 모두 지원하는 통합 트레이딩 시스템 관리.

Usage:
    config = TradingConfig(
        asset_class="stock",
        strategy_name="bb_reversion",
        initial_capital=10_000_000,
    )

    orchestrator = TradingOrchestrator(config)
    await orchestrator.start()

    # 상태 조회
    status = orchestrator.get_status()

    # 종료
    await orchestrator.stop()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from datetime import time as dt_time
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

import yaml

from services.trading.pipeline import TradingPipeline
from services.trading.data_provider import MarketDataProvider, DataProviderConfig
from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig
from services.monitoring.metrics import get_metrics_collector
from shared.models.position import PositionSide
from shared.models.signal import Signal, ExitSignal
from shared.config.loader import ConfigLoader
from shared.strategy.base import EntryContext
from shared.utils.calc import calc_order_quantity

try:
    # Optional: only used when paper_trading=True
    from shared.paper.models import OrderSide as PaperOrderSide
except Exception:  # pragma: no cover
    PaperOrderSide = None  # type: ignore

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Validation constants
MIN_INITIAL_CAPITAL = 100_000  # 10만원 minimum
MAX_INITIAL_CAPITAL = 100_000_000_000  # 1000억원 maximum
MIN_ORDER_AMOUNT = 10_000  # 1만원 minimum per trade
MAX_ORDER_AMOUNT = 100_000_000  # 1억원 maximum per trade
MAX_ORDER_QUANTITY = 1_000_000  # Safety cap for quantity
MAX_YAML_FILE_SIZE = 1_024 * 1_024  # 1MB max for YAML config files


class HolidayLoader(Protocol):
    """Protocol for holiday data loading (allows injection for testing)."""

    def __call__(self, config_path: str) -> set[date]:
        """Load holidays from config file."""
        ...


def default_holiday_loader(config_path: str = "config/market_schedule.yaml") -> set[date]:
    """Default implementation for loading holidays from config file.

    Args:
        config_path: Path to market schedule YAML config

    Returns:
        Set of holiday dates
    """
    holidays: set[date] = set()
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Holiday config not found: {config_path}, using empty set")
        return holidays

    try:
        # Security: Check file size before parsing to prevent DoS via large files
        file_size = path.stat().st_size
        if file_size > MAX_YAML_FILE_SIZE:
            logger.error(
                f"Holiday config file too large: {file_size} bytes > {MAX_YAML_FILE_SIZE} bytes"
            )
            return holidays

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            logger.warning(f"Invalid holiday config format in {config_path}")
            return holidays

        for holiday_str in data.get("holidays", []):
            try:
                if isinstance(holiday_str, str):
                    holidays.add(date.fromisoformat(holiday_str))
                elif isinstance(holiday_str, date):
                    holidays.add(holiday_str)
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping invalid holiday entry: {holiday_str} - {e}")
    except Exception as e:
        logger.error(f"Failed to load holidays: {e}", exc_info=True)

    return holidays


class HolidayCache:
    """Thread-safe holiday cache with injectable loader.

    NOTE: This is a legacy sync version. For async contexts, use
    AsyncHolidayCache from services.trading.holiday_cache instead.

    Usage:
        # Default usage
        cache = HolidayCache()
        holidays = cache.get()

        # With custom loader (for testing)
        cache = HolidayCache(loader=lambda path: {date(2024, 1, 1)})
    """

    def __init__(
        self,
        loader: Callable[[str], set[date]] | None = None,
        config_path: str = "config/market_schedule.yaml",
    ):
        self._loader = loader or default_holiday_loader
        self._config_path = config_path
        self._cache: set[date] | None = None
        self._lock = asyncio.Lock()

    def get(self) -> set[date]:
        """Get holidays (loads on first access)."""
        if self._cache is None:
            self._cache = self._loader(self._config_path)
        return self._cache

    def reload(self):
        """Force reload of holidays (sync version, not thread-safe for concurrent use)."""
        self._cache = None

    async def reload_async(self):
        """Force reload of holidays with async lock for thread-safety."""
        async with self._lock:
            self._cache = None

    async def get_async(self) -> set[date]:
        """Get holidays with async lock for concurrent access."""
        async with self._lock:
            return self.get()


# Global holiday cache (can be replaced for testing)
_holiday_cache = HolidayCache()


def _get_holidays() -> set[date]:
    """공휴일 가져오기 (캐시 사용)"""
    return _holiday_cache.get()


def reload_holidays():
    """공휴일 다시 로드 (설정 변경 시)"""
    _holiday_cache.reload()


def set_holiday_cache(cache: HolidayCache):
    """Replace global holiday cache (for testing)."""
    global _holiday_cache
    _holiday_cache = cache


class TradingState(Enum):
    """트레이딩 상태"""

    IDLE = "idle"  # 대기 중
    WAITING = "waiting"  # 장 시작 대기
    RUNNING = "running"  # 거래 중
    PAUSED = "paused"  # 일시 정지
    STOPPED = "stopped"  # 종료됨
    ERROR = "error"  # 오류 발생


@dataclass
class MarketSchedule:
    """장 시간 설정"""

    # 주식
    stock_open: dt_time = field(default_factory=lambda: dt_time(9, 0))
    stock_close: dt_time = field(default_factory=lambda: dt_time(15, 30))

    # 선물
    futures_open: dt_time = field(default_factory=lambda: dt_time(9, 0))
    futures_close: dt_time = field(default_factory=lambda: dt_time(15, 45))

    # 서비스 시작/종료 (장 시작 전/후 여유)
    service_start_offset_minutes: int = 5
    service_end_offset_minutes: int = 5

    def get_open_time(self, asset_class: str) -> dt_time:
        return self.stock_open if asset_class == "stock" else self.futures_open

    def get_close_time(self, asset_class: str) -> dt_time:
        return self.stock_close if asset_class == "stock" else self.futures_close


def is_trading_day(d: date | None = None, holidays: set[date] | None = None) -> bool:
    """거래일 여부 확인

    Args:
        d: 확인할 날짜 (None이면 오늘)
        holidays: 공휴일 set (None이면 설정 파일에서 로드)

    Returns:
        거래일이면 True
    """
    if d is None:
        d = date.today()

    # 주말
    if d.weekday() >= 5:
        return False

    # 공휴일
    if holidays is None:
        holidays = _get_holidays()

    if d in holidays:
        return False

    return True


@dataclass
class TradingConfig:
    """트레이딩 설정"""

    # 기본 설정
    asset_class: str = "stock"  # "stock" or "futures"
    strategy_name: str | None = None  # None = load all enabled strategies
    initial_capital: float = 10_000_000

    # 거래 대상
    symbols: list[str] = field(default_factory=list)  # 주식 종목 코드들

    # 스케줄
    schedule: MarketSchedule = field(default_factory=MarketSchedule)

    # 모드
    paper_trading: bool = True  # 모의투자 여부
    auto_start: bool = True  # 장 시작 시 자동 시작

    # Optional execution mode override (PAPER/MOCK/REAL).
    # If empty, inferred from paper_trading (PAPER if True, else MOCK).
    execution_mode: str = ""

    # 알림
    enable_telegram: bool = True
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # Redis (선택)
    redis_url: str | None = None

    # Order sizing (previously hardcoded)
    order_amount_per_trade: float = 1_000_000  # 종목당 주문 금액

    # Order execution concurrency
    max_concurrent_orders: int = 5

    # Market data refresh cadence (seconds)
    market_data_refresh_seconds: float = 0.5

    # Per-symbol metadata (e.g. watchlist baseline volumes).
    symbol_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Error recovery
    error_retry_delay_seconds: float = 60.0  # Retry delay after errors (default 1 min)

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if self.asset_class not in ("stock", "futures"):
            raise ValueError(
                f"asset_class must be 'stock' or 'futures', got {self.asset_class}"
            )

        if not (MIN_INITIAL_CAPITAL <= self.initial_capital <= MAX_INITIAL_CAPITAL):
            raise ValueError(
                f"initial_capital must be between {MIN_INITIAL_CAPITAL:,} "
                f"and {MAX_INITIAL_CAPITAL:,}, got {self.initial_capital:,}"
            )

        if not (MIN_ORDER_AMOUNT <= self.order_amount_per_trade <= MAX_ORDER_AMOUNT):
            raise ValueError(
                f"order_amount_per_trade must be between {MIN_ORDER_AMOUNT:,} "
                f"and {MAX_ORDER_AMOUNT:,}, got {self.order_amount_per_trade:,}"
            )

        if self.strategy_name is not None and (
            not isinstance(self.strategy_name, str) or not self.strategy_name
        ):
            raise ValueError("strategy_name must be a non-empty string or None")

        if not isinstance(self.symbols, list):
            raise TypeError(f"symbols must be a list, got {type(self.symbols)}")

        if not isinstance(self.paper_trading, bool):
            raise TypeError(f"paper_trading must be bool, got {type(self.paper_trading)}")

        if not isinstance(self.max_concurrent_orders, int) or self.max_concurrent_orders < 1:
            raise ValueError(
                f"max_concurrent_orders must be int >= 1, got {self.max_concurrent_orders}"
            )

        if not isinstance(self.market_data_refresh_seconds, (int, float)):
            raise TypeError(
                "market_data_refresh_seconds must be numeric, "
                f"got {type(self.market_data_refresh_seconds)}"
            )
        if not (0.5 <= float(self.market_data_refresh_seconds) <= 5.0):
            raise ValueError(
                "market_data_refresh_seconds must be between 0.5 and 5.0, "
                f"got {self.market_data_refresh_seconds}"
            )

    @classmethod
    def stock(
        cls,
        strategy_name: str | None = None,
        symbols: list[str] | None = None,
        initial_capital: float = 10_000_000,
        order_amount: float = 1_000_000,
        paper_trading: bool = True,
        execution_mode: str = "",
        symbol_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> TradingConfig:
        """주식용 설정"""
        return cls(
            asset_class="stock",
            strategy_name=strategy_name,
            symbols=symbols or [],
            initial_capital=initial_capital,
            order_amount_per_trade=order_amount,
            paper_trading=paper_trading,
            execution_mode=execution_mode,
            symbol_metadata=symbol_metadata or {},
            # Slower refresh for stock (40-50 symbols with retention)
            # avoids KIS API rate limiting
            market_data_refresh_seconds=2.0,
        )

    @classmethod
    def futures(
        cls,
        strategy_name: str | None = None,
        initial_capital: float = 10_000_000,
        order_amount: float = 1_000_000,
        symbols: list[str] | None = None,
    ) -> TradingConfig:
        """선물용 설정"""
        # Auto-detect KOSPI200 mini futures front-month code
        symbols = symbols or cls._get_futures_default_symbols()
        return cls(
            asset_class="futures",
            strategy_name=strategy_name,
            initial_capital=initial_capital,
            order_amount_per_trade=order_amount,
            symbols=symbols,
        )

    @staticmethod
    def _get_futures_default_symbols() -> list[str]:
        """Get default KOSPI200 mini futures front-month symbol.

        KIS mini futures code format: A056{month_code}000
        Month codes: 1=Jan..9=Sep, A=Oct, B=Nov, C=Dec
        """
        from datetime import date as _date
        today = _date.today()
        y, m = today.year, today.month
        # Futures expire 2nd Thursday of contract month.
        # If past ~15th, roll to next month.
        if today.day >= 15:
            m += 1
            if m > 12:
                m = 1
                y += 1
        month_codes = "123456789ABC"
        mc = month_codes[m - 1]
        code = f"A056{mc}000"
        logger.info(f"Futures default symbol: {code} ({y}-{m:02d})")
        return [code]


class TradingOrchestrator:
    """트레이딩 오케스트레이터

    트레이딩 시스템의 전체 생명주기 관리:
    - 장 시간 감지 및 자동 시작/종료
    - 파이프라인 관리
    - 상태 모니터링
    - 알림 전송

    Usage:
        orchestrator = TradingOrchestrator(config)
        await orchestrator.run()  # 데몬 모드 (매일 반복)
        # 또는
        await orchestrator.run_session()  # 오늘만 실행
    """

    def __init__(
        self,
        config: TradingConfig,
        holiday_cache: HolidayCache | None = None,
        order_executor: Any | None = None,
    ):
        """
        Args:
            config: 트레이딩 설정
            holiday_cache: Optional custom holiday cache (for testing)
        """
        self.config = config
        self.state = TradingState.IDLE
        self.pipeline: TradingPipeline | None = None

        # Holiday cache (injectable for testing)
        self._holiday_cache = holiday_cache or _holiday_cache

        # 통계
        self.start_time: datetime | None = None
        self.session_count = 0
        self.total_trades = 0
        self.total_pnl = 0.0

        # 에러 추적
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None

        # 내부 상태
        self._running = False
        self._main_task: asyncio.Task | None = None

        # Per-symbol locks and order concurrency control
        self._symbol_locks: dict[str, asyncio.Lock] = {}
        self._order_semaphore = asyncio.Semaphore(config.max_concurrent_orders)
        self._order_queue_depth = 0
        self._order_queue_lock = asyncio.Lock()

        # Trading components (initialized in start())
        self._data_provider: MarketDataProvider | None = None
        self._strategy_manager: StrategyManager | None = None
        self._position_tracker: PositionTracker | None = None
        self._paper_broker: Any | None = None
        self._kis_client: Any | None = None
        self._order_executor: Any | None = None

        # Market regime
        self._current_regime: str | None = None

        # Market data loop state
        self._market_data_task: asyncio.Task | None = None
        self._market_data_running = False
        self._market_data_lock = asyncio.Lock()
        self._market_data_snapshot: dict[str, dict[str, Any]] = {}
        self._market_data_updated_at: datetime | None = None
        self._metrics = get_metrics_collector()
        self._order_executor = order_executor

        # Streaming indicator engine (initialized in _initialize_components)
        self._indicator_engine: Any | None = None

        # WebSocket stock price feed (initialized in _initialize_components)
        self._stock_price_feed: Any | None = None

        # Redis state publisher (initialized in _initialize_components)
        self._state_publisher: Any | None = None

        # Universe refresh from screener
        self._universe_refresh_task: asyncio.Task | None = None
        self._universe_refresh_interval = 30.0  # seconds
        self._symbol_names: dict[str, str] = {}  # code -> name mapping
        self._symbol_metadata_cache: dict[str, dict[str, Any]] = {}
        self._trade_targets_latest_key = os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
        )
        self._universe_latest_key = os.environ.get(
            "UNIVERSE_LATEST_KEY", "system:universe:latest"
        )

        # Universe stability: retain symbols for a window after they leave
        # the screener top-N, so the indicator engine can warm up.
        self._symbol_last_seen: dict[str, datetime] = {}
        self._universe_retention_seconds = 600.0  # 10 minutes
        self._max_universe_size = 50
        self._llm_training_data_dir = os.environ.get(
            "LLM_TRAINING_DATA_DIR", "output/llm"
        )

        logger.info(
            f"TradingOrchestrator initialized: "
            f"{config.asset_class}/{config.strategy_name}"
        )

    def set_order_executor(self, executor: Any | None) -> None:
        """Attach an order executor (optional).

        If provided and paper_trading is False, execution will use this
        executor instead of mock fills.
        """
        self._order_executor = executor

    @property
    def is_running(self) -> bool:
        return self._running and self.state in (TradingState.RUNNING, TradingState.WAITING)

    async def start(self):
        """거래 시작"""
        if self.state == TradingState.RUNNING:
            logger.warning("Already running")
            return

        self.state = TradingState.RUNNING
        self.start_time = datetime.now()

        logger.info("Starting trading...")

        # Initialize components
        await self._initialize_components()

        # Start shared market data loop before pipeline
        await self._start_market_data_loop()

        # 파이프라인 생성 및 시작
        self.pipeline = self._create_pipeline()
        await self.pipeline.start()

        # Publish initial status + start Prometheus
        if self._state_publisher:
            self._state_publisher.publish_status(self.get_status())
        prom_port = 9092 if self.config.asset_class == "futures" else 9091
        self._metrics.start_prometheus_server(port=prom_port)

        await self._notify(
            f"🚀 Trading Started\n"
            f"Asset: {self.config.asset_class}\n"
            f"Strategy: {self.config.strategy_name}\n"
            f"Capital: {self.config.initial_capital:,.0f}"
        )

    async def _initialize_components(self):
        """Initialize trading components"""
        # Initialize KIS Client (REST API — used for prewarm + fallback)
        try:
            from shared.kis.auth import KISAuthConfig
            from shared.kis.client import KISClient

            if self.config.asset_class == "futures":
                app_key = os.getenv("KIS_FUTURES_APP_KEY", os.getenv("KIS_APP_KEY", ""))
                app_secret = os.getenv("KIS_FUTURES_APP_SECRET", os.getenv("KIS_APP_SECRET", ""))
            else:
                app_key = os.getenv("KIS_APP_KEY", "")
                app_secret = os.getenv("KIS_APP_SECRET", "")
            kis_config = KISAuthConfig(app_key=app_key, app_secret=app_secret, is_real=True)
            self._kis_client = KISClient(kis_config)
            logger.info("KIS Client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize KIS Client: {e}")
            self._kis_client = None

        # WebSocket price feed for stock (replaces REST polling)
        self._stock_price_feed = None
        data_source = None
        if self.config.asset_class == "stock" and self._kis_client:
            try:
                from shared.kis.stock_feed import KISStockPriceFeed

                self._stock_price_feed = KISStockPriceFeed(
                    config=kis_config,
                    fallback_client=self._kis_client,
                )
                data_source = self._stock_price_feed
                logger.info("Stock WebSocket price feed initialized")
            except Exception as e:
                logger.warning(f"Stock WebSocket feed init failed: {e}")

        # Data provider
        # With WebSocket: cache_ttl can be short (data is push-based, instant)
        # Without WebSocket (futures/fallback): keep original TTL
        try:
            dp_cfg = ConfigLoader.load("streaming.yaml").get("data_provider", {})
        except Exception:
            dp_cfg = {}
        if data_source:
            cache_ttl = float(dp_cfg.get("cache_ttl_websocket", 2.0))
        else:
            if self.config.asset_class == "stock":
                cache_ttl = float(dp_cfg.get("cache_ttl_stock", 30.0))
            else:
                cache_ttl = float(dp_cfg.get("cache_ttl_futures", 5.0))
        stagger_delay = float(dp_cfg.get("stagger_delay", 0.1))
        self._data_provider = MarketDataProvider(
            symbols=self.config.symbols,
            config=DataProviderConfig(
                cache_ttl_seconds=cache_ttl,
                stagger_delay_seconds=stagger_delay,
            ),
            kis_client=self._kis_client if not data_source else None,
            data_source=data_source,
        )

        # Strategy manager
        strategy_names = (
            [self.config.strategy_name] if self.config.strategy_name else None
        )
        self._strategy_manager = StrategyManager(
            asset_class=self.config.asset_class,
            strategy_names=strategy_names,
            config=StrategyManagerConfig(),
        )

        # Position tracker
        self._position_tracker = PositionTracker(
            config=PositionTrackerConfig(max_positions=10)
        )

        # Streaming indicator engine for live BB/RSI
        try:
            from services.trading.indicator_engine import StreamingIndicatorEngine

            # Read BB/RSI params from strategy entry config if available
            bb_period, bb_std, rsi_period = 20, 2.0, 14
            if self._strategy_manager:
                for strategy in self._strategy_manager.strategies.values():
                    entry = getattr(strategy, "entry", None)
                    if entry is not None:
                        cfg = entry.get_config()
                        bb_period = cfg.get("bb_period", bb_period)
                        bb_std = cfg.get("bb_std", bb_std)
                        rsi_period = cfg.get("rsi_period", rsi_period)
                        break

            self._indicator_engine = StreamingIndicatorEngine(
                bb_period=bb_period,
                bb_std=bb_std,
                rsi_period=rsi_period,
            )
            logger.info(
                f"Indicator engine initialized (bb={bb_period}, "
                f"std={bb_std}, rsi={rsi_period})"
            )
        except Exception as e:
            logger.warning(f"Indicator engine init failed: {e}")
            self._indicator_engine = None

        # Paper broker (if paper trading)
        if self.config.paper_trading:
            try:
                from shared.paper import VirtualBroker

                self._paper_broker = VirtualBroker(
                    initial_balance=self.config.initial_capital,
                )
                logger.info("Paper broker (VirtualBroker) initialized")
            except Exception as e:
                logger.warning(f"Paper broker init failed, using mock execution: {e}")
        else:
            # KIS execution via shared.execution.OrderExecutor (MOCK/REAL).
            # NOTE: Will fail closed (no orders) if credentials are missing.
            try:
                from shared.execution.config import ExecutionConfig
                from shared.execution.executor import OrderExecutor

                mode = (self.config.execution_mode or os.getenv("TRADING_MODE", "MOCK")).upper()
                if mode not in ("MOCK", "REAL"):
                    raise ValueError(f"execution_mode must be MOCK or REAL for live execution, got {mode!r}")

                exec_cfg = ExecutionConfig(
                    trading_mode=mode,
                    account_no=(
                        os.getenv("KIS_FUTURES_ACCOUNT_NO", os.getenv("KIS_ACCOUNT_NO", ""))
                        if self.config.asset_class == "futures"
                        else os.getenv("KIS_ACCOUNT_NO", "")
                    ),
                    redis_url=os.getenv("REDIS_URL", ""),
                    rate_limit_key=self.config.asset_class,
                )

                auth_manager = getattr(self._kis_client, "auth_manager", None) if self._kis_client else None
                self._order_executor = OrderExecutor(config=exec_cfg, auth_manager=auth_manager)
                await self._order_executor.initialize()
                logger.info(f"OrderExecutor initialized (mode={mode})")
            except Exception as e:
                logger.warning(f"OrderExecutor init failed; orders will be mocked: {e}")
                self._order_executor = None

        # Load swing positions from DB (for swing strategies)
        if self._position_tracker and self.config.strategy_name in ("volume_accumulation",):
            await self._position_tracker.load_from_db()

        # Load accumulation candidates from Redis
        self._accumulation_candidates: dict[str, int] = {}
        self._refresh_accumulation_candidates()

        # Redis state publisher
        try:
            from shared.streaming.trading_state import TradingStatePublisher
            self._state_publisher = TradingStatePublisher(self.config.asset_class)
            logger.info("Trading state publisher initialized")
        except Exception as e:
            logger.warning(f"Trading state publisher init failed: {e}")

        # Bootstrap symbols from screener if none configured
        if not self.config.symbols and self.config.asset_class == "stock":
            self._refresh_universe_from_screener()

        logger.info(
            f"Components initialized: "
            f"{len(self._strategy_manager.strategies)} strategies, "
            f"{len(self.config.symbols)} symbols"
        )

    ACCUMULATION_REDIS_KEY = "system:accumulation:latest"

    def _refresh_accumulation_candidates(self) -> bool:
        """Load accumulation candidates from Redis (published by overnight scanner)."""
        try:
            from shared.streaming.client import RedisClient
            redis_client = RedisClient.get_client()
            raw = redis_client.get(self.ACCUMULATION_REDIS_KEY)
            if not raw:
                return False

            payload = json.loads(raw)
            if not isinstance(payload, dict):
                logger.warning("Accumulation candidates: invalid payload type")
                return False

            candidates = payload.get("candidates", [])
            if not isinstance(candidates, list):
                logger.warning("Accumulation candidates: 'candidates' is not a list")
                return False

            validated = {}
            for c in candidates:
                if not isinstance(c, dict):
                    continue
                code = c.get("code")
                score = c.get("score")
                if isinstance(code, str) and code.isalnum() and isinstance(score, (int, float)):
                    validated[code] = int(score)

            self._accumulation_candidates = validated
            logger.info(f"Loaded {len(self._accumulation_candidates)} accumulation candidates")
            return True
        except Exception as e:
            logger.debug(f"Accumulation candidates not available: {e}")
            return False

    def _load_ranked_targets(self, redis) -> tuple[list[str], dict[str, str], dict[str, dict[str, Any]]]:
        """Load ranked symbols from fusion targets first, then screener fallback."""
        keys = [
            ("fusion", self._trade_targets_latest_key),
            ("screener", self._universe_latest_key),
        ]

        for source, key in keys:
            raw = redis.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
                codes_raw = payload.get("codes", [])
                if not isinstance(codes_raw, list):
                    continue
                codes = [str(c).strip() for c in codes_raw if str(c).strip()]
                if not codes:
                    continue

                names_raw = payload.get("names", {})
                names = (
                    {str(k): str(v) for k, v in names_raw.items() if isinstance(k, str)}
                    if isinstance(names_raw, dict)
                    else {}
                )

                metadata_raw = payload.get("metadata", {})
                metadata = (
                    {
                        str(k): dict(v)
                        for k, v in metadata_raw.items()
                        if isinstance(k, str) and isinstance(v, dict)
                    }
                    if isinstance(metadata_raw, dict)
                    else {}
                )
                logger.debug(f"Loaded {len(codes)} symbols from {source} key: {key}")
                return codes, names, metadata
            except Exception as e:
                logger.debug(f"Failed parsing ranked target payload ({key}): {e}")

        return [], {}, {}

    def _refresh_universe_from_screener(self) -> bool:
        """Read ranked universe from Redis and update symbols.

        Uses a retention window so symbols persist after leaving the screener
        top-N.  This allows the indicator engine to warm up (needs ~20 min of
        1-minute candles) even though the screener ranking is volatile.
        """
        try:
            from shared.streaming.client import RedisClient
            redis = RedisClient.get_client()
            codes, names, metadata = self._load_ranked_targets(redis)

            if not codes:
                return False

            now = datetime.now()

            # Update last-seen timestamps for current screener symbols
            for code in codes:
                self._symbol_last_seen[code] = now
                code_meta = dict(metadata.get(code, {}))
                code_name = names.get(code)
                if code_name:
                    code_meta["name"] = code_name
                if code_meta:
                    self._symbol_metadata_cache[code] = code_meta
            self._symbol_names.update(names)

            # Build stable universe: all symbols seen within retention window
            retention_cutoff = now - timedelta(seconds=self._universe_retention_seconds)
            stable_symbols: set[str] = set()
            expired: list[str] = []
            for code, last_seen in self._symbol_last_seen.items():
                if last_seen >= retention_cutoff:
                    stable_symbols.add(code)
                else:
                    expired.append(code)

            # Clean up expired symbols
            for code in expired:
                del self._symbol_last_seen[code]
                self._symbol_metadata_cache.pop(code, None)

            # Cap universe size — keep most recently seen
            if len(stable_symbols) > self._max_universe_size:
                by_recency = sorted(
                    stable_symbols,
                    key=lambda c: self._symbol_last_seen.get(c, datetime.min),
                    reverse=True,
                )
                stable_symbols = set(by_recency[: self._max_universe_size])

            # Keep symbol-level metadata fresh even when universe membership is unchanged.
            self.config.symbol_metadata = {
                code: dict(self._symbol_metadata_cache.get(code, {}))
                for code in stable_symbols
            }
            for code, name in self._symbol_names.items():
                if code in self.config.symbol_metadata and name:
                    self.config.symbol_metadata[code]["name"] = name

            old_set = set(self.config.symbols)

            if stable_symbols != old_set:
                added = stable_symbols - old_set
                removed = old_set - stable_symbols
                self.config.symbols = list(stable_symbols)

                if self._data_provider:
                    self._data_provider.symbols = list(stable_symbols)

                if added or removed:
                    logger.info(
                        f"Universe refreshed: {len(stable_symbols)} symbols "
                        f"(+{len(added)} -{len(removed)}, "
                        f"retained {len(stable_symbols) - len(added)})"
                    )
                return True
        except Exception as e:
            logger.warning(f"Universe refresh failed: {e}")
        return False

    async def _universe_refresh_loop(self) -> None:
        """Periodically refresh symbols from screener."""
        while self._market_data_running:
            try:
                old_symbols = set(self.config.symbols)
                self._refresh_universe_from_screener()
                new_symbols = set(self.config.symbols) - old_symbols

                # Update WebSocket subscriptions to match new universe
                if self._stock_price_feed:
                    self._stock_price_feed.update_symbols(self.config.symbols)

                # Pre-warm new symbols (fire-and-forget to not block refresh)
                if new_symbols and self._indicator_engine and self._kis_client:
                    asyncio.create_task(
                        self._prewarm_symbols(list(new_symbols)),
                        name="prewarm_symbols",
                    )
            except Exception as e:
                logger.warning(f"Universe refresh loop error: {e}")
            await asyncio.sleep(self._universe_refresh_interval)

    async def _prewarm_symbols(self, symbols: list[str]) -> None:
        """Fetch recent 1-min bars from KIS and seed the indicator engine."""
        logger.info(f"Prewarm starting for {len(symbols)} symbols")
        for symbol in symbols:
            if self._indicator_engine.is_warm(symbol):
                continue
            try:
                candles = await asyncio.wait_for(
                    self._kis_client.get_minute_bars(symbol, count=25),
                    timeout=5.0,
                )
                if candles:
                    self._indicator_engine.seed_candles(symbol, candles)
                    logger.info(f"Prewarm {symbol}: {len(candles)} candles seeded")
                else:
                    logger.debug(f"Prewarm {symbol}: no candles returned")
                await asyncio.sleep(0.3)  # rate-limit protection
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Prewarm failed for {symbol}: {e}")
        logger.info("Prewarm complete")

    async def stop(self):
        """거래 종료"""
        if self.state == TradingState.STOPPED:
            return

        logger.info("Stopping trading...")

        await self._stop_market_data_loop()

        # For swing strategies: persist positions instead of closing
        is_swing = self.config.strategy_name in ("volume_accumulation",)
        if self._position_tracker and self._data_provider:
            if is_swing and self._position_tracker.position_count > 0:
                await self._position_tracker.save_to_db()
                logger.info(
                    f"Swing positions saved ({self._position_tracker.position_count} open)"
                )
            else:
                data = await self._data_provider.get_data()
                closed = self._position_tracker.close_all(data, reason="EOD_CLOSE")
                for pos in closed:
                    self.total_pnl += pos.unrealized_pnl

        if self.pipeline:
            await self.pipeline.stop()
            self.pipeline = None

        # Cleanup components
        if self._order_executor is not None:
            try:
                await self._order_executor.cleanup()
            except Exception as e:
                logger.warning(f"OrderExecutor cleanup failed: {e}")
            self._order_executor = None
        self._data_provider = None
        self._strategy_manager = None
        self._position_tracker = None

        self.state = TradingState.STOPPED
        self._running = False

        # Publish final status to Redis
        if self._state_publisher:
            self._state_publisher.publish_status(self.get_status())

        await self._notify(
            f"🛑 Trading Stopped\n"
            f"Session: {self.session_count}\n"
            f"Trades: {self.total_trades}\n"
            f"PnL: {self.total_pnl:+,.0f}"
        )

    async def pause(self):
        """일시 정지"""
        if self.state != TradingState.RUNNING:
            return

        logger.info("Pausing trading...")
        self.state = TradingState.PAUSED

        if self.pipeline:
            await self.pipeline.stop()

        await self._notify("⏸️ Trading Paused")

    async def resume(self):
        """재개"""
        if self.state != TradingState.PAUSED:
            return

        logger.info("Resuming trading...")
        self.state = TradingState.RUNNING

        if self.pipeline:
            await self.pipeline.start()

        await self._notify("▶️ Trading Resumed")

    async def run_session(self):
        """단일 세션 실행 (오늘만)"""
        today = date.today()

        # 거래일 체크 (use injected holiday cache)
        holidays = self._holiday_cache.get()
        if not is_trading_day(today, holidays):
            reason = "주말" if today.weekday() >= 5 else "공휴일"
            logger.info(f"Not a trading day: {reason}")
            await self._notify(f"🏖️ 휴장일: {reason}")
            return

        now = datetime.now()
        schedule = self.config.schedule
        open_time = schedule.get_open_time(self.config.asset_class)
        close_time = schedule.get_close_time(self.config.asset_class)

        # 장 시작 대기
        open_dt = datetime.combine(today, open_time)
        if now < open_dt:
            wait_seconds = (open_dt - now).total_seconds()
            logger.info(f"Waiting for market open: {wait_seconds:.0f}s")
            self.state = TradingState.WAITING
            await asyncio.sleep(wait_seconds)

        # 거래 시작
        await self.start()
        self.session_count += 1

        # 장 종료까지 대기
        close_dt = datetime.combine(today, close_time)
        now = datetime.now()

        if now < close_dt:
            wait_seconds = (close_dt - now).total_seconds()
            logger.info(f"Trading until market close: {wait_seconds:.0f}s")

            try:
                await asyncio.sleep(wait_seconds)
            except asyncio.CancelledError:
                pass

        # 거래 종료
        await self.stop()

    async def run(self):
        """데몬 모드 실행 (매일 반복)"""
        logger.info("Starting trading orchestrator (daemon mode)")
        self._running = True

        await self._notify(
            f"🤖 Trading Orchestrator Started\n"
            f"Mode: {'Paper' if self.config.paper_trading else 'Live'}\n"
            f"Asset: {self.config.asset_class}\n"
            f"Strategy: {self.config.strategy_name}"
        )

        while self._running:
            try:
                await self.run_session()

                # 다음 날까지 대기
                now = datetime.now()
                tomorrow = (now + timedelta(days=1)).replace(
                    hour=8,
                    minute=55,
                    second=0,
                    microsecond=0,
                )

                wait_seconds = (tomorrow - now).total_seconds()
                logger.info(f"Next session in {wait_seconds / 3600:.1f} hours")

                self.state = TradingState.IDLE
                await asyncio.sleep(wait_seconds)

            except asyncio.CancelledError:
                logger.info("Orchestrator cancelled")
                break
            except Exception as e:
                logger.error(f"Session error: {e}")
                await self._notify(f"⚠️ Error: {e}")
                await asyncio.sleep(self.config.error_retry_delay_seconds)

        await self.stop()

    def _create_pipeline(self) -> TradingPipeline:
        """파이프라인 생성 with real handlers"""
        return TradingPipeline(
            regime_handler=self._handle_regime,
            entry_handler=self._handle_entry,
            monitoring_handler=self._handle_monitoring,
            exit_handler=self._handle_exit,
        )

    def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        lock = self._symbol_locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self._symbol_locks[symbol] = lock
        return lock

    def _get_market_data_staleness_seconds(self) -> float | None:
        if not self._market_data_updated_at:
            return None
        return (datetime.now() - self._market_data_updated_at).total_seconds()

    async def _increment_order_queue(self) -> None:
        async with self._order_queue_lock:
            self._order_queue_depth += 1
            self._metrics.record_order_queue_depth(self._order_queue_depth)

    async def _decrement_order_queue(self) -> None:
        async with self._order_queue_lock:
            self._order_queue_depth = max(0, self._order_queue_depth - 1)
            self._metrics.record_order_queue_depth(self._order_queue_depth)

    def _get_market_symbols(self) -> list[str]:
        symbols = set(self.config.symbols or [])
        if self._position_tracker:
            for position in self._position_tracker.positions:
                symbols.add(position.code)
        return list(symbols)

    async def _refresh_market_data_once(self) -> dict[str, dict[str, Any]]:
        if not self._data_provider:
            return {}
        symbols = self._get_market_symbols()
        if not symbols:
            return {}
        # Use cache TTL (1s) instead of force_refresh to avoid API rate limits
        # when tracking many symbols. Each symbol refreshes at most once per TTL.
        return await self._data_provider.get_data(symbols=symbols)

    async def _start_market_data_loop(self) -> None:
        if self._market_data_running:
            return

        self._market_data_running = True

        # Start WebSocket price feed (if available)
        if self._stock_price_feed:
            try:
                await self._stock_price_feed.start()
                self._stock_price_feed.update_symbols(self.config.symbols)
                logger.info(
                    f"Stock WebSocket feed started, "
                    f"{self._stock_price_feed.symbol_count} symbols subscribed"
                )
            except Exception as e:
                logger.warning(f"Stock WebSocket feed start failed: {e}")
                self._stock_price_feed = None

        # Pre-warm indicators FIRST (exclusive API access, no rate conflicts)
        if self._indicator_engine and self._kis_client and self.config.symbols:
            await self._prewarm_symbols(self.config.symbols[:20])

        # Initial price refresh (some may be rate-limited; the data loop will catch up)
        try:
            data = await self._refresh_market_data_once()
            async with self._market_data_lock:
                self._market_data_snapshot = data
                self._market_data_updated_at = datetime.now()
        except Exception as e:
            logger.warning(f"Initial market data refresh failed: {e}")

        interval = float(self.config.market_data_refresh_seconds)
        if self.pipeline:
            interval = max(interval, min(self.pipeline.intervals.values()))

        self._market_data_task = asyncio.create_task(
            self._market_data_loop(interval),
            name="market_data_loop",
        )

        # Start universe refresh loop for stock trading
        if self.config.asset_class == "stock":
            self._universe_refresh_task = asyncio.create_task(
                self._universe_refresh_loop(),
                name="universe_refresh_loop",
            )

    async def _stop_market_data_loop(self) -> None:
        if not self._market_data_running:
            return

        self._market_data_running = False

        # Stop WebSocket price feed
        if self._stock_price_feed:
            try:
                await self._stock_price_feed.stop()
            except Exception as e:
                logger.warning(f"Stock price feed stop error: {e}")

        if self._universe_refresh_task:
            self._universe_refresh_task.cancel()
            await asyncio.gather(self._universe_refresh_task, return_exceptions=True)
            self._universe_refresh_task = None
        if self._market_data_task:
            self._market_data_task.cancel()
            await asyncio.gather(self._market_data_task, return_exceptions=True)
            self._market_data_task = None

    async def _market_data_loop(self, interval: float) -> None:
        logger.info(
            f"Market data loop started (interval={interval}s, "
            f"symbols={len(self._get_market_symbols())})"
        )
        next_tick = time.monotonic()
        _tick_count = 0
        _diag_interval = 30  # log diagnostics every 30 ticks (~60s at 2s interval)

        while self._market_data_running:
            try:
                t0 = time.monotonic()
                data = await self._refresh_market_data_once()
                fetch_ms = (time.monotonic() - t0) * 1000
                _tick_count += 1

                # Log first few ticks and then periodically
                if _tick_count <= 3 or _tick_count % _diag_interval == 0:
                    n_syms = len(data) if data else 0
                    logger.info(
                        f"[tick {_tick_count}] fetched {n_syms} symbols "
                        f"in {fetch_ms:.0f}ms"
                    )

                if data:
                    now_ts = datetime.now()
                    async with self._market_data_lock:
                        self._market_data_snapshot = data
                        self._market_data_updated_at = now_ts

                    # Feed ticks to streaming indicator engine
                    if self._indicator_engine:
                        for sym, sym_data in data.items():
                            if isinstance(sym_data, dict):
                                self._indicator_engine.on_tick(sym, sym_data, now_ts)

                    # Periodic diagnostic log
                    if _tick_count % _diag_interval == 0 and self._indicator_engine:
                        warm_count = sum(
                            1 for s in self._indicator_engine._accumulators
                            if self._indicator_engine.is_warm(s)
                        )
                        sample_sym = next(iter(self._indicator_engine._accumulators), None)
                        sample_candles = 0
                        if sample_sym:
                            sample_candles = len(self._indicator_engine._accumulators[sample_sym].candles)
                        logger.info(
                            f"Market data: {len(data)} symbols fetched, "
                            f"{len(self._indicator_engine._accumulators)} tracked, "
                            f"{warm_count} warm, "
                            f"sample {sample_sym}={sample_candles} candles"
                        )

                    staleness = self._get_market_data_staleness_seconds()
                    if staleness is not None:
                        self._metrics.record_market_data_staleness(staleness)
            except Exception as e:
                logger.warning(f"Market data refresh failed: {e}")

            next_tick += interval
            sleep_time = next_tick - time.monotonic()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # Yield to event loop even when behind schedule,
                # so other tasks (universe refresh, prewarm) can run.
                await asyncio.sleep(0)
                if -sleep_time > interval * 3:
                    next_tick = time.monotonic()

        logger.info("Market data loop stopped")

    async def _get_market_data_snapshot(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        async with self._market_data_lock:
            snapshot = dict(self._market_data_snapshot)

        if symbols:
            return {symbol: snapshot[symbol] for symbol in symbols if symbol in snapshot}
        return snapshot

    # -------------------------------------------------------------------------
    # Pipeline Handlers
    # -------------------------------------------------------------------------

    async def _handle_regime(self) -> dict[str, Any] | None:
        """Regime detection handler (runs every 5 min)

        Uses MarketClassifier with MFI computed from streaming indicator engine.
        Falls back to simple avg-change classification when MFI is unavailable.
        """
        if not self._data_provider:
            return None

        try:
            data = await self._get_market_data_snapshot()
            if not data:
                return None

            regime = self._classify_market(data)
            self._current_regime = regime

            logger.debug(f"Market regime: {regime}")

            return {
                "regime": regime,
                "timestamp": datetime.now().isoformat(),
                "symbols_checked": len(data),
            }

        except Exception as e:
            logger.error(f"Regime detection failed: {e}", exc_info=True)
            return None

    # Market classification thresholds
    MARKET_BULL_THRESHOLD = 0.02  # +2% = BULL
    MARKET_BEAR_THRESHOLD = -0.02  # -2% = BEAR

    def _classify_market(self, market_data: dict[str, Any]) -> str:
        """Market classification using MarketClassifier with MFI from indicator engine.

        Falls back to simple avg-change heuristic when MFI is not yet available
        (during warmup period).
        """
        if not market_data:
            return "UNKNOWN"

        # Try MFI-based classification via MarketClassifier
        if self._indicator_engine:
            mfi = self._indicator_engine.get_market_mfi()
            if mfi is not None:
                try:
                    from shared.strategy.market_classifier import MarketClassifier
                    classifier = MarketClassifier()
                    state = classifier.classify(mfi=mfi, adx=0.0)
                    return state.value
                except Exception as e:
                    logger.debug(f"MarketClassifier failed: {e}")

        # Fallback: simple avg-change heuristic (used during warmup)
        changes = []
        for symbol, data in market_data.items():
            if isinstance(data, dict):
                change = data.get("change", 0)
                if change:
                    changes.append(change)

        if not changes:
            return "SIDEWAYS_FLAT"

        avg_change = sum(changes) / len(changes)

        if avg_change > self.MARKET_BULL_THRESHOLD:
            return "BULL"
        elif avg_change < self.MARKET_BEAR_THRESHOLD:
            return "BEAR"
        elif avg_change > 0:
            return "SIDEWAYS_UP"
        elif avg_change < 0:
            return "SIDEWAYS_DOWN"
        else:
            return "SIDEWAYS_FLAT"

    async def _handle_entry(self) -> list[Signal]:
        """Entry signal handler (runs every 1 sec)

        Checks entry conditions across all strategies.
        """
        if not self._strategy_manager or not self._data_provider:
            return []

        if not self._position_tracker:
            return []

        # Skip entries in BEAR market (covers both old "BEAR" and new MarketState values)
        if self._current_regime and "BEAR" in self._current_regime:
            return []

        # Check position limit
        if not self._position_tracker.can_open_position():
            return []

        try:
            # Fetch market data
            data = await self._get_market_data_snapshot()
            if not data:
                return []

            now = datetime.now()

            # Check entries per symbol (Entry strategies expect single-symbol market_data).
            async def check_symbol(symbol: str) -> list[Signal]:
                symbol_data = data.get(symbol)
                if not isinstance(symbol_data, dict):
                    return []

                # Enrich with watchlist/baseline metadata (if present).
                meta = (self.config.symbol_metadata or {}).get(symbol, {})
                enriched = dict(symbol_data)
                enriched["code"] = symbol
                if meta.get("name"):
                    enriched["name"] = meta["name"]
                enriched.update(meta)

                # Inject streaming indicators (BB, RSI)
                indicators: dict[str, Any] = {}
                if self._indicator_engine:
                    indicators = self._indicator_engine.get_indicators(symbol)
                    if "ohlcv" in self._strategy_manager.required_indicators:
                        ohlcv = self._indicator_engine.get_recent_candles(symbol, limit=240)
                        if ohlcv:
                            indicators["ohlcv"] = ohlcv
                    if indicators:
                        enriched.update(indicators)

                context = EntryContext(
                    market_data=enriched,
                    indicators=indicators,
                    current_positions=self._position_tracker.positions,
                    timestamp=now,
                    metadata={
                        "regime": self._current_regime,
                        "market_state": self._current_regime,
                        "symbol_metadata": meta,
                        "accumulation_candidates": getattr(self, "_accumulation_candidates", {}),
                    },
                )
                return await self._strategy_manager.check_entries(context)

            symbols = list(data.keys())
            # Bound concurrency to avoid stampeding (data may have many symbols).
            sem = asyncio.Semaphore(20)

            async def check_symbol_limited(symbol: str) -> list[Signal]:
                async with sem:
                    return await check_symbol(symbol)

            results = await asyncio.gather(*(check_symbol_limited(s) for s in symbols))
            signals: list[Signal] = []
            for r in results:
                if r:
                    signals.extend(r)

            # Execute orders for valid signals (bounded parallelism)
            async def run_entry(signal: Signal) -> None:
                queued = getattr(self._order_semaphore, "_value", 0) <= 0
                acquired = False
                if queued:
                    await self._increment_order_queue()
                try:
                    async with self._order_semaphore:
                        acquired = True
                        if queued:
                            await self._decrement_order_queue()
                        await self._execute_entry(signal)
                finally:
                    if queued and not acquired:
                        await self._decrement_order_queue()

            await asyncio.gather(*(run_entry(signal) for signal in signals))

            return signals

        except Exception as e:
            logger.error(f"Entry handler failed: {e}", exc_info=True)
            return []

    async def _handle_monitoring(self) -> dict[str, Any] | None:
        """Position monitoring handler (runs every 0.1 sec)

        Updates position prices and state transitions.
        """
        if not self._position_tracker or not self._data_provider:
            return None

        positions = self._position_tracker.positions
        if not positions:
            return None

        try:
            # Fetch latest prices
            symbols = list({p.code for p in positions})
            data = await self._get_market_data_snapshot(symbols)

            # Update prices
            self._position_tracker.update_prices(data)

            # Update states (SURVIVAL → BREAKEVEN → MAXIMIZE)
            transitions = self._position_tracker.update_states()

            if transitions:
                for position, old_state, new_state in transitions:
                    logger.info(
                        f"Position state: {position.code} "
                        f"{old_state.value} → {new_state.value}"
                    )

            # Publish position updates to Redis (throttled to 2s)
            if self._state_publisher and positions:
                self._state_publisher.publish_positions_update(positions, throttle=2.0)

            # Publish status periodically (throttled to 5s)
            if self._state_publisher:
                import time as _time_mod
                now = _time_mod.monotonic()
                if now - self._state_publisher._last_status_publish >= 5.0:
                    self._state_publisher._last_status_publish = now
                    self._state_publisher.publish_status(self.get_status())

            return {
                "positions_updated": len(positions),
                "transitions": len(transitions),
            }

        except Exception as e:
            logger.error(f"Monitoring handler failed: {e}", exc_info=True)
            return None

    async def _handle_exit(self) -> list[ExitSignal]:
        """Exit signal handler (runs every 0.5 sec)

        Checks exit conditions for all positions.
        """
        if not self._strategy_manager or not self._position_tracker:
            return []

        if not self._data_provider:
            return []

        positions = self._position_tracker.positions
        if not positions:
            return []

        try:
            # Fetch market data
            symbols = list({p.code for p in positions})
            data = await self._get_market_data_snapshot(symbols)

            # Check exits
            signals = await self._strategy_manager.check_exits(
                positions=positions,
                market_data=data,
                market_state=self._current_regime,
            )

            # Execute exit orders (bounded parallelism)
            async def run_exit(signal: ExitSignal) -> None:
                queued = getattr(self._order_semaphore, "_value", 0) <= 0
                acquired = False
                if queued:
                    await self._increment_order_queue()
                try:
                    async with self._order_semaphore:
                        acquired = True
                        if queued:
                            await self._decrement_order_queue()
                        await self._execute_exit(signal)
                finally:
                    if queued and not acquired:
                        await self._decrement_order_queue()

            await asyncio.gather(*(run_exit(signal) for signal in signals))

            return signals

        except Exception as e:
            logger.error(f"Exit handler failed: {e}", exc_info=True)
            return []

    # -------------------------------------------------------------------------
    # Order Execution
    # -------------------------------------------------------------------------

    async def _execute_entry(self, signal: Signal):
        """Execute entry order with lock for thread-safety."""
        if not self._position_tracker:
            return

        # Calculate quantity
        quantity = self._calculate_quantity(signal)
        if quantity <= 0:
            logger.warning(f"Invalid quantity for {signal.code}: {quantity}")
            return

        # Per-symbol lock to prevent race conditions on the same symbol
        async with self._get_symbol_lock(signal.code):
            # Re-check position limit under lock
            if not self._position_tracker.can_open_position(signal.code):
                logger.debug(f"Position limit reached, skipping entry for {signal.code}")
                return

            try:
                direction = self._get_signal_direction(signal)
                is_short = direction == "short"
                if self.config.paper_trading and self._paper_broker:
                    # Paper trading execution
                    if PaperOrderSide is None:
                        raise RuntimeError("PaperOrderSide not available (paper trading dependencies missing)")
                    order = await self._paper_broker.submit_order(
                        symbol=signal.code,
                        side=PaperOrderSide.SELL if is_short else PaperOrderSide.BUY,
                        quantity=quantity,
                        price=signal.price,
                    )
                    is_filled = bool(getattr(order, "filled", True))
                    fill_price = float(getattr(order, "fill_price", signal.price) or signal.price)
                elif self._order_executor is not None:
                    # Live/mock execution via KIS API
                    from shared.execution.models import OrderRequest, OrderSide, OrderType

                    resp = await self._order_executor.execute_order(
                        OrderRequest(
                            code=signal.code,
                            side=OrderSide.SELL if is_short else OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                            price=None,
                        )
                    )
                    is_filled = bool(resp.success)
                    fill_price = float(resp.filled_price or signal.price)
                else:
                    # Mock execution (for testing without paper broker)
                    is_filled = True
                    fill_price = signal.price

                if is_filled:
                    symbol_meta = (self.config.symbol_metadata or {}).get(signal.code, {})
                    # Track position
                    position = self._position_tracker.add_position(
                        code=signal.code,
                        name=signal.name,
                        entry_price=fill_price,
                        quantity=quantity,
                        strategy=signal.strategy,
                        side=PositionSide.SHORT if is_short else PositionSide.LONG,
                        metadata={
                            "snapshot_id": str(symbol_meta.get("llm_snapshot_id", "")),
                            "llm_quality": symbol_meta.get("llm_quality"),
                            "realtime_score": symbol_meta.get("realtime_score"),
                            "risk_flags": symbol_meta.get("risk_flags", []),
                            "entry_signal_confidence": signal.confidence,
                            "signal_direction": direction,
                        },
                    )

                    if position:
                        self.total_trades += 1
                        name = signal.name or self._symbol_names.get(signal.code, "")
                        logger.info(
                            f"Entry executed: {name} ({signal.code}) @ {fill_price:,.0f} x {quantity}"
                        )
                        amount = fill_price * quantity
                        entry_label = "숏 진입" if is_short else "롱 진입"
                        await self._notify(
                            f"🟢 <b>{entry_label}</b>\n"
                            f"종목: {name} ({signal.code})\n"
                            f"가격: {fill_price:,.0f}원 x {quantity}주\n"
                            f"금액: {amount:,.0f}원\n"
                            f"전략: {signal.strategy}\n"
                            f"신뢰도: {signal.confidence:.1%}"
                        )
                        self._append_training_trade_event(
                            {
                                "event": "entry",
                                "timestamp": datetime.now().isoformat(),
                                "position_id": position.id,
                                "snapshot_id": position.metadata.get("snapshot_id", ""),
                                "code": signal.code,
                                "name": name,
                                "strategy": signal.strategy,
                                "entry_price": fill_price,
                                "quantity": quantity,
                                "signal_confidence": signal.confidence,
                                "metadata": position.metadata,
                            }
                        )
                        # Publish to Redis
                        if self._state_publisher:
                            self._state_publisher.publish_position_opened(position)
                            self._state_publisher.publish_signal(signal, "entry", True)
                            self._metrics.record_signal("entry", strategy=signal.strategy)

            except Exception as e:
                logger.error(f"Entry execution failed for {signal.code}: {e}", exc_info=True)

    async def _execute_exit(self, signal: ExitSignal):
        """Execute exit order with lock for thread-safety."""
        if not self._position_tracker:
            return

        # Per-symbol lock to prevent race conditions on the same symbol
        async with self._get_symbol_lock(signal.code):
            # Verify position still exists under lock
            position = self._position_tracker.get_position(signal.position_id)
            if not position:
                logger.debug(f"Position already closed: {signal.position_id}")
                return

            try:
                close_is_buy = position.side == PositionSide.SHORT
                exit_quantity = signal.quantity if signal.quantity > 0 else position.quantity
                if self.config.paper_trading and self._paper_broker:
                    # Paper trading execution
                    if PaperOrderSide is None:
                        raise RuntimeError("PaperOrderSide not available (paper trading dependencies missing)")
                    order = await self._paper_broker.submit_order(
                        symbol=signal.code,
                        side=PaperOrderSide.BUY if close_is_buy else PaperOrderSide.SELL,
                        quantity=exit_quantity,
                        price=signal.exit_price,
                    )
                    is_filled = bool(getattr(order, "filled", True))
                    fill_price = float(getattr(order, "fill_price", signal.exit_price) or signal.exit_price)
                elif self._order_executor is not None:
                    from shared.execution.models import OrderRequest, OrderSide, OrderType

                    resp = await self._order_executor.execute_order(
                        OrderRequest(
                            code=signal.code,
                            side=OrderSide.BUY if close_is_buy else OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=exit_quantity,
                            price=None,
                        )
                    )
                    is_filled = bool(resp.success)
                    fill_price = float(resp.filled_price or signal.exit_price)
                else:
                    # Mock execution
                    is_filled = True
                    fill_price = signal.exit_price

                if is_filled:
                    # Close position
                    closed = self._position_tracker.close_position(
                        position_id=signal.position_id,
                        exit_price=fill_price,
                        reason=signal.reason.value if hasattr(signal.reason, "value") else str(signal.reason),
                    )

                    if closed:
                        self.total_pnl += closed.unrealized_pnl
                        name = getattr(closed, "name", "") or self._symbol_names.get(signal.code, "")
                        reason_str = signal.reason.value if hasattr(signal.reason, "value") else str(signal.reason)
                        pnl = closed.unrealized_pnl
                        pnl_pct = closed.profit_pct
                        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                        logger.info(
                            f"Exit executed: {name} ({signal.code}) @ {fill_price:,.0f} "
                            f"(reason={reason_str}, pnl={pnl_pct:+.2f}%)"
                        )
                        await self._notify(
                            f"{pnl_emoji} <b>{'숏 청산' if close_is_buy else '롱 청산'}</b>\n"
                            f"종목: {name} ({signal.code})\n"
                            f"가격: {fill_price:,.0f}원 x {exit_quantity}주\n"
                            f"사유: {reason_str}\n"
                            f"손익: {pnl:+,.0f}원 ({pnl_pct:+.2f}%)"
                        )
                        self._append_training_trade_event(
                            {
                                "event": "exit",
                                "timestamp": datetime.now().isoformat(),
                                "position_id": closed.id,
                                "snapshot_id": (
                                    closed.metadata.get("snapshot_id", "")
                                    if isinstance(closed.metadata, dict)
                                    else ""
                                ),
                                "code": signal.code,
                                "name": name,
                                "exit_price": fill_price,
                                "quantity": exit_quantity,
                                "reason": reason_str,
                                "trade_pnl": pnl,
                                "trade_pnl_pct": pnl_pct,
                                "hold_seconds": (
                                    (closed.exit_time - closed.entry_time).total_seconds()
                                    if closed.exit_time and closed.entry_time
                                    else None
                                ),
                                "metadata": closed.metadata if isinstance(closed.metadata, dict) else {},
                            }
                        )
                        # Publish to Redis
                        if self._state_publisher:
                            self._state_publisher.publish_position_closed(closed)
                            self._state_publisher.publish_signal(signal, "exit", True)
                            self._metrics.record_trade(pnl=pnl, win=(pnl >= 0), strategy=getattr(signal, "strategy", "default"))

            except Exception as e:
                logger.error(f"Exit execution failed for {signal.code}: {e}", exc_info=True)

    @staticmethod
    def _get_signal_direction(signal: Signal) -> str:
        """Extract normalized signal direction from metadata."""
        metadata = getattr(signal, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return "long"
        direction = metadata.get("signal_direction") or metadata.get("direction") or "long"
        direction = str(direction).strip().lower()
        return "short" if direction == "short" else "long"

    def _calculate_quantity(self, signal: Signal) -> int:
        """Calculate order quantity based on config.

        Args:
            signal: Entry signal with price info

        Returns:
            Order quantity (capped at MAX_ORDER_QUANTITY)
        """
        # Use signal quantity if explicitly set
        if signal.quantity > 0:
            return min(signal.quantity, MAX_ORDER_QUANTITY)

        # Prefer strategy-defined sizer (YAML position config), fallback to fixed amount.
        if self._strategy_manager and signal.strategy in self._strategy_manager.strategies:
            try:
                strategy = self._strategy_manager.strategies[signal.strategy]
                balance = self._get_account_balance()
                qty = strategy.calculate_position_size(
                    signal=signal,
                    account_balance=balance,
                    current_positions=self._position_tracker.positions if self._position_tracker else [],
                )
                if qty > 0:
                    return min(qty, MAX_ORDER_QUANTITY)
            except Exception as e:
                logger.warning(f"Strategy sizer failed for {signal.code}: {e}")

        # Fallback: config-based fixed order amount.
        order_amount = float(self.config.order_amount_per_trade)
        return calc_order_quantity(order_amount=order_amount, price=signal.price, max_quantity=MAX_ORDER_QUANTITY)

    def _get_account_balance(self) -> float:
        """Best-effort account balance/equity for sizing."""
        if self._paper_broker is not None:
            # VirtualBroker exposes balance and get_equity().
            if hasattr(self._paper_broker, "get_equity"):
                try:
                    return float(self._paper_broker.get_equity())
                except Exception:
                    pass
            if hasattr(self._paper_broker, "balance"):
                try:
                    return float(self._paper_broker.balance)
                except Exception:
                    pass
        return float(self.config.initial_capital)

    def _append_training_trade_event(self, row: dict[str, Any]) -> None:
        try:
            os.makedirs(self._llm_training_data_dir, exist_ok=True)
            path = os.path.join(self._llm_training_data_dir, "trade_outcomes.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.debug(f"Failed to append training trade event: {e}")

    async def _notify(self, message: str):
        """알림 전송"""
        if not self.config.enable_telegram:
            logger.info(f"Notification (telegram disabled): {message}")
            return

        try:
            from services.monitoring.notifier import TelegramConfig, TelegramNotifier

            # 환경변수 또는 config에서 토큰 로드
            config = TelegramConfig.from_env()

            # config에 토큰이 있으면 우선 사용
            if self.config.telegram_token and self.config.telegram_chat_id:
                config = TelegramConfig(
                    token=self.config.telegram_token,
                    chat_id=self.config.telegram_chat_id,
                )

            if not config.is_configured:
                logger.warning("Telegram not configured, skipping notification")
                return

            notifier = TelegramNotifier(config)
            try:
                success = await notifier.send(message)
                if not success:
                    logger.warning(f"Failed to send telegram notification: {message[:50]}...")
            finally:
                await notifier.close()

        except ImportError:
            logger.debug("TelegramNotifier not available")
        except Exception as e:
            logger.error(f"Notification error: {e}")

    def get_status(self) -> dict[str, Any]:
        """상태 조회"""
        pipeline_status = self.pipeline.get_status() if self.pipeline else {}
        position_stats = (
            self._position_tracker.get_stats() if self._position_tracker else {}
        )
        strategy_info = (
            self._strategy_manager.get_stats() if self._strategy_manager else {}
        )
        data_stats = (
            self._data_provider.get_cache_stats() if self._data_provider else {}
        )

        return {
            "state": self.state.value,
            "regime": self._current_regime,
            "config": {
                "asset_class": self.config.asset_class,
                "strategy": self.config.strategy_name,
                "capital": self.config.initial_capital,
                "paper_trading": self.config.paper_trading,
                "symbols": len(self.config.symbols),
            },
            "stats": {
                "session_count": self.session_count,
                "total_trades": self.total_trades,
                "total_pnl": self.total_pnl,
                "start_time": self.start_time.isoformat() if self.start_time else None,
            },
            "positions": position_stats,
            "strategies": strategy_info,
            "data_provider": data_stats,
            "pipeline": pipeline_status,
        }

    def get_metrics(self) -> dict[str, Any]:
        """메트릭 조회"""
        # Keep init-time behavior stable: if the trading pipeline hasn't been
        # started yet, expose no metrics.
        if not self.pipeline:
            return {}

        staleness = self._get_market_data_staleness_seconds()
        if staleness is not None:
            self._metrics.record_market_data_staleness(staleness)
        self._metrics.record_order_queue_depth(self._order_queue_depth)

        if not self.pipeline:
            return {}

        metrics = self.pipeline.metrics.to_dict()
        metrics["market_data_staleness_seconds"] = staleness
        metrics["order_queue_depth"] = self._order_queue_depth
        metrics["market_data_updated_at"] = (
            self._market_data_updated_at.isoformat()
            if self._market_data_updated_at
            else None
        )
        return metrics


# 편의 함수
async def run_stock_trading(
    strategy: str | None = None,
    symbols: list[str] | None = None,
    capital: float = 10_000_000,
    paper_trading: bool = True,
    execution_mode: str = "",
    symbol_metadata: dict[str, dict[str, Any]] | None = None,
    daemon: bool = False,
):
    """주식 트레이딩 실행"""
    config = TradingConfig.stock(
        strategy_name=strategy,
        symbols=symbols,
        initial_capital=capital,
        paper_trading=paper_trading,
        execution_mode=execution_mode,
        symbol_metadata=symbol_metadata or {},
    )

    orchestrator = TradingOrchestrator(config)

    if daemon:
        await orchestrator.run()
    else:
        await orchestrator.run_session()


async def run_futures_trading(
    strategy: str | None = None,
    capital: float = 10_000_000,
    symbols: list[str] | None = None,
    daemon: bool = False,
):
    """선물 트레이딩 실행"""
    config = TradingConfig.futures(
        strategy_name=strategy,
        initial_capital=capital,
        symbols=symbols,
    )

    orchestrator = TradingOrchestrator(config)

    if daemon:
        await orchestrator.run()
    else:
        await orchestrator.run_session()
