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
import contextlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd
import yaml

from services.monitoring.metrics import get_metrics_collector
from services.trading.data_provider import DataProviderConfig, MarketDataProvider
from services.trading.pipeline import TradingPipeline
from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig
from shared.config.loader import ConfigLoader
from shared.db.config import ClickHouseConfig
from shared.exceptions import (
    APIError,
    ConfigurationError,
    InfrastructureError,
    InvalidConfigError,
    MissingConfigError,
    NetworkError,
    ValidationError,
    WebSocketDisconnectError,
)
from shared.execution.config import ATSRoutingConfig
from shared.execution.models import ExecutionVenue
from shared.execution.venue_router import VenueRouter
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason, ExitSignal, Signal
from shared.regime.performance_tracker import (
    RegimePerformanceConfig,
    RegimePerformanceTracker,
)
from shared.risk.config import RiskConfig
from shared.risk.manager import RiskManager
from shared.risk.models import DrawdownLevel
from shared.strategy.base import EntryContext, MarketStateAdapter
from shared.utils.calc import calc_order_quantity

try:
    # Optional: only used when paper_trading=True
    from shared.paper.models import OrderSide as PaperOrderSide
except Exception:  # pragma: no cover
    PaperOrderSide = None  # type: ignore

if TYPE_CHECKING:
    from shared.config.schema import PipelineConfig

logger = logging.getLogger(__name__)


# Validation constants
MIN_INITIAL_CAPITAL = 100_000  # 10만원 minimum
MAX_INITIAL_CAPITAL = 100_000_000_000  # 1000억원 maximum
MIN_ORDER_AMOUNT = 10_000  # 1만원 minimum per trade
MAX_ORDER_AMOUNT = 100_000_000  # 1억원 maximum per trade
MAX_ORDER_QUANTITY = 1_000_000  # Safety cap for quantity
MAX_YAML_FILE_SIZE = 1_024 * 1_024  # 1MB max for YAML config files
REENTRY_GUARD_SCOPES = {"symbol", "symbol_strategy"}


@dataclass(frozen=True)
class EntryReentryGuardConfig:
    """Post-exit entry guard configuration.

    The guard prevents immediate churn after a position closes, especially
    stop-loss followed by same-symbol re-entry during noisy intraday moves.
    """

    enabled: bool = True
    scope: str = "symbol_strategy"
    default_cooldown_seconds: float = 900.0
    reason_cooldown_seconds: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EntryReentryGuardConfig:
        raw = data or {}
        raw_reasons = raw.get("reason_cooldown_seconds", {})
        reasons: dict[str, float] = {}
        if isinstance(raw_reasons, dict):
            for reason, seconds in raw_reasons.items():
                if not isinstance(seconds, (int, float)):
                    raise TypeError(
                        "entry_reentry_guard.reason_cooldown_seconds values "
                        f"must be numeric, got {type(seconds)} for {reason}"
                    )
                if float(seconds) < 0:
                    raise ValueError(
                        "entry_reentry_guard.reason_cooldown_seconds values "
                        f"must be non-negative, got {seconds} for {reason}"
                    )
                reasons[str(reason).lower()] = float(seconds)

        default_cooldown = raw.get("default_cooldown_seconds", 900.0)
        if not isinstance(default_cooldown, (int, float)):
            raise TypeError(
                "entry_reentry_guard.default_cooldown_seconds must be numeric"
            )
        if float(default_cooldown) < 0:
            raise ValueError(
                "entry_reentry_guard.default_cooldown_seconds must be non-negative"
            )

        scope = str(raw.get("scope", "symbol_strategy"))
        if scope not in REENTRY_GUARD_SCOPES:
            raise ValueError(
                "entry_reentry_guard.scope must be one of "
                f"{sorted(REENTRY_GUARD_SCOPES)}, got {scope}"
            )

        return cls(
            enabled=bool(raw.get("enabled", True)),
            scope=scope,
            default_cooldown_seconds=float(default_cooldown),
            reason_cooldown_seconds=reasons,
        )

    def cooldown_for(self, reason: str | None) -> float:
        if not reason:
            return self.default_cooldown_seconds
        return self.reason_cooldown_seconds.get(
            str(reason).lower(),
            self.default_cooldown_seconds,
        )


class HolidayLoader(Protocol):
    """Protocol for holiday data loading (allows injection for testing)."""

    def __call__(self, config_path: str) -> set[date]:
        """Load holidays from config file."""
        ...


def default_holiday_loader(
    config_path: str = "config/market_schedule.yaml",
) -> set[date]:
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

        with open(path, encoding="utf-8") as f:
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
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Failed to load holidays from config file: {e}", exc_info=True)
    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Invalid holiday config format: {e}", exc_info=True)

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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _risk_params_for_runtime_capital(
    risk_params: dict[str, Any], runtime_initial_capital: float
) -> dict[str, Any]:
    """Return risk params aligned with the active orchestrator capital.

    ``risk_management.yaml`` is shared across runtime modes and has a conservative
    standalone fallback. In orchestrator runs, the CLI/config ``initial_capital``
    is the account baseline unless an operator explicitly sets
    ``RISK_INITIAL_CAPITAL``.
    """
    params = dict(risk_params)
    explicit_risk_capital = os.getenv("RISK_INITIAL_CAPITAL")
    if explicit_risk_capital is None or not explicit_risk_capital.strip():
        params["initial_capital"] = int(runtime_initial_capital)
    elif "initial_capital" not in params:
        params["initial_capital"] = int(runtime_initial_capital)
    return params


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

    # Paper trading simulation fees (round-trip 기준 0.3% = 편도 0.15%)
    paper_commission_rate: float = 0.0015  # 편도 수수료 0.15%
    paper_slippage_rate: float = 0.001  # 슬리피지 0.1%

    # Position recovery
    swing_recovery_max_age_days: int = (
        7  # Max age for swing position recovery from Redis
    )

    # Error recovery
    error_retry_delay_seconds: float = 60.0  # Retry delay after errors (default 1 min)

    # Candle cache persistence interval (seconds)
    candle_cache_save_interval: float = 60.0

    # Universe mode: "dynamic" (screener-driven, default) or "static" (daily watchlist)
    universe_mode: str = "dynamic"
    require_daily_indicators_for_dynamic_universe: bool = True

    # Regime performance tracking
    regime_performance_tracking_enabled: bool = False

    # Regime detection mode: 'simple' (MFI+ADX), 'adaptive' (multi-metric), or 'hmm' (future)
    regime_detection_mode: str = "simple"

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if self.asset_class not in ("stock", "futures"):
            raise ValueError(
                f"asset_class must be 'stock' or 'futures', got {self.asset_class}"
            )

        if self.universe_mode not in ("dynamic", "static"):
            raise ValueError(
                f"universe_mode must be 'dynamic' or 'static', got {self.universe_mode}"
            )
        if not isinstance(self.require_daily_indicators_for_dynamic_universe, bool):
            raise TypeError(
                "require_daily_indicators_for_dynamic_universe must be bool, "
                f"got {type(self.require_daily_indicators_for_dynamic_universe)}"
            )

        if self.regime_detection_mode not in ("simple", "adaptive", "hmm"):
            raise ValueError(
                f"regime_detection_mode must be 'simple', 'adaptive', or 'hmm', "
                f"got {self.regime_detection_mode}"
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
            raise TypeError(
                f"paper_trading must be bool, got {type(self.paper_trading)}"
            )

        if (
            not isinstance(self.max_concurrent_orders, int)
            or self.max_concurrent_orders < 1
        ):
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
        require_daily_indicators_for_dynamic_universe: bool | None = None,
    ) -> TradingConfig:
        """주식용 설정"""
        require_daily_indicators = (
            _env_bool("STOCK_REQUIRE_DAILY_INDICATORS_FOR_DYNAMIC_UNIVERSE", True)
            if require_daily_indicators_for_dynamic_universe is None
            else require_daily_indicators_for_dynamic_universe
        )
        return cls(
            asset_class="stock",
            strategy_name=strategy_name,
            symbols=symbols or [],
            initial_capital=initial_capital,
            order_amount_per_trade=order_amount,
            paper_trading=paper_trading,
            execution_mode=execution_mode,
            symbol_metadata=symbol_metadata or {},
            require_daily_indicators_for_dynamic_universe=require_daily_indicators,
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
            telegram_token=os.getenv("TELEGRAM_FUTURES_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_FUTURES_CHAT_ID", ""),
        )

    @staticmethod
    def _get_futures_default_symbols() -> list[str]:
        """Get default KOSPI200 mini futures front-month symbol."""
        from shared.collector.historical.futures import get_front_month_code

        code = get_front_month_code(product="mini")
        logger.info(f"Futures default symbol (auto-detected): {code}")
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
        self._stop_requested = False
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
        self._risk_manager: RiskManager | None = None
        self._risk_block_alert_sent: bool = (
            False  # Track if risk block alert has been sent
        )
        self._last_risk_save_time: float = (
            0.0  # Track last Redis save time for risk state
        )
        self._paper_broker: Any | None = None
        self._kis_client: Any | None = None
        self._order_executor: Any | None = None
        self._mock_mirror: Any | None = None

        # Market regime
        self._current_regime: str | None = None
        self._current_regime_confidence: float | None = None

        # Adaptive regime detector (optional, controlled by config)
        self._adaptive_regime_detector: Any | None = None
        if config.regime_detection_mode == "adaptive":
            try:
                from shared.regime.adaptive_detector import (
                    AdaptiveRegimeConfig,
                    AdaptiveRegimeDetector,
                )

                # Load adaptive regime config
                regime_cfg_dict = ConfigLoader.load("ml/regime_adaptive.yaml")

                # Build AdaptiveRegimeConfig from nested YAML structure
                adaptive_config = AdaptiveRegimeConfig.from_yaml_dict(regime_cfg_dict)
                self._adaptive_regime_detector = AdaptiveRegimeDetector(adaptive_config)
                logger.info(
                    f"Adaptive regime detection enabled (mode={config.regime_detection_mode})"
                )
            except (ConfigurationError, MissingConfigError, InvalidConfigError) as e:
                logger.error(
                    f"Failed to initialize adaptive regime detector: {e}", exc_info=True
                )
                self._adaptive_regime_detector = None
            except Exception as e:
                logger.error(
                    f"Unexpected error initializing adaptive regime detector: {e}",
                    exc_info=True,
                )
                self._adaptive_regime_detector = None

        # Regime performance tracker (optional, controlled by config)
        self._regime_tracker: RegimePerformanceTracker | None = None
        if config.regime_performance_tracking_enabled:
            regime_config = RegimePerformanceConfig(
                redis_enabled=False,  # Start with in-memory, can enable later
            )
            self._regime_tracker = RegimePerformanceTracker(regime_config)
            logger.info("Regime performance tracking enabled")

        # Adaptive position sizing (initialized in _init_components)
        self._adaptive_sizing: Any | None = None

        # ATS Venue Router (initialized from execution.yaml)
        self._venue_router: VenueRouter | None = None
        try:
            execution_cfg = ConfigLoader.load("execution.yaml")
            ats_routing_dict = execution_cfg.get("ats_routing", {})
            ats_config = ATSRoutingConfig(**ats_routing_dict)
            self._venue_router = VenueRouter(ats_config)
            logger.info(f"VenueRouter initialized: enabled={ats_config.enabled}")
        except (ConfigurationError, MissingConfigError, InvalidConfigError) as e:
            logger.warning(f"Failed to load ATS routing config: {e}")
            self._venue_router = None
        except Exception as e:
            logger.error(
                f"Unexpected error initializing VenueRouter: {e}", exc_info=True
            )
            self._venue_router = None

        # Market data loop state
        self._market_data_task: asyncio.Task | None = None
        self._market_data_running = False
        self._market_data_lock = asyncio.Lock()
        self._market_data_snapshot: dict[str, dict[str, Any]] = {}
        self._market_data_updated_at: datetime | None = None
        self._data_provider_failover_enabled = False
        self._metrics = get_metrics_collector()
        self._order_executor = order_executor

        # Streaming indicator engine + indicator resolver (initialized in _initialize_components)
        self._indicator_engine: Any | None = None
        self._indicator_resolver: Any | None = None

        # WebSocket stock price feed (initialized in _initialize_components)
        self._stock_price_feed: Any | None = None

        # Fire-and-forget notification tasks (tracked for cleanup)
        self._pending_notify_tasks: set[asyncio.Task] = set()
        self._prewarm_task: asyncio.Task | None = None

        # WebSocket futures price feed (initialized in _initialize_components)
        self._futures_price_feed: Any | None = None
        self._futures_slippage_controller: Any | None = None
        self._futures_slippage_aux_symbols: list[str] = []
        self._entry_slippage_stats: dict[str, float] = {
            "count": 0.0,
            "adverse_ticks_sum": 0.0,
            "avg_adverse_ticks": 0.0,
        }
        self._entry_reentry_guard = self._load_entry_reentry_guard_config()
        self._recent_exit_cooldowns: dict[str, dict[str, Any]] = {}

        # Optional tick mirroring to Redis streams for monitoring exporter
        self._tick_stream_publisher: Any | None = None

        # Redis state publisher (initialized in _initialize_components)
        self._state_publisher: Any | None = None

        # Universe refresh from screener
        self._universe_refresh_task: asyncio.Task | None = None
        self._universe_refresh_interval = 30.0  # seconds
        self._symbol_names: dict[str, str] = {}  # code -> name mapping
        self._symbol_name_lookup_attempted: set[str] = set()
        self._krx_symbol_name_cache: dict[str, str] = {}
        self._krx_symbol_name_cache_date: str = ""
        self._krx_open_api_client: Any | None = None
        self._krx_name_hydration_warned: bool = False
        self._symbol_metadata_cache: dict[str, dict[str, Any]] = {}
        self._enriched_metadata_cache: dict[str, dict[str, Any]] = {}
        self._cached_symbol_meta: dict[str, dict[str, Any]] = {}  # pure symbol_metadata
        self._cached_daily_indicators: dict[str, dict[str, Any]] = (
            {}
        )  # pure daily indicators
        self._prev_day_volume_warned: bool = False

        # Redis keys namespaced by asset class to prevent collision
        # Stock uses legacy keys (system:...) for compatibility with Screener
        # Futures/others use namespaced keys (system:{asset}:...)
        default_target_key = "system:trade_targets:latest"
        if config.asset_class != "stock":
            default_target_key = f"system:{config.asset_class}:trade_targets:latest"

        self._trade_targets_latest_key = os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", default_target_key
        )

        default_universe_key = "system:universe:latest"
        if config.asset_class != "stock":
            default_universe_key = f"system:{config.asset_class}:universe:latest"

        self._universe_latest_key = os.environ.get(
            "UNIVERSE_LATEST_KEY", default_universe_key
        )

        # Universe stability: retain symbols for a window after they leave
        # the screener top-N, so the indicator engine can warm up.
        self._symbol_last_seen: dict[str, datetime] = {}
        self._universe_retention_seconds = 1500.0  # 25 min (> 20min warmup)
        # Cap universe to WebSocket max_symbols (streaming.yaml) so every
        # symbol in the universe actually receives tick data.
        try:
            _sf_cfg = ConfigLoader.load("streaming.yaml").get("stock_feed", {})
            self._max_universe_size = int(_sf_cfg.get("max_symbols", 40))
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
            ValueError,
        ):
            self._max_universe_size = 40
        # Daily watchlist for static universe mode (populated from DailyScanner)
        self._daily_watchlist: dict[str, Any] = (
            {}
        )  # {strategies: {name: [codes]}, codes: [...]}
        self._daily_watchlist_key = "system:daily_watchlist:latest"
        # Daily indicators from pre-market scanner (scalars + series for daily strategies)
        self._daily_indicators: dict[str, dict[str, Any]] = {}

        # LLM Context Publisher (initialized in _initialize_components)
        self._llm_context_publisher: Any | None = None
        self._llm_context_task: asyncio.Task | None = None

        self._llm_training_data_dir = os.environ.get(
            "LLM_TRAINING_DATA_DIR", "output/llm"
        )
        self._last_candle_cache_save: float = 0.0

        # Kill-switch consumer loop (Phase 0.2-c).
        # Polls Redis sentinel key and calls PositionTracker.close_all() on trip.
        self._kill_switch_consumer_task: asyncio.Task | None = None
        # Last kill-switch events stream entry-id seen by this process.
        # Initialised at startup to the current stream tip so pre-existing
        # events from prior sessions do NOT re-trigger flatten on restart.
        self._ks_last_seen_event_id: str | None = None

        # Shadow-loggers flush loop (Phase 2 — LLM-primary RL-minimization plan).
        # Periodically drains shared.strategy.rl_shadow_logger and
        # shared.strategy.llm_veto_logger buffers into ClickHouse.
        self._shadow_loggers_flush_task: asyncio.Task | None = None
        # Reusable ClickHouse client for the flush loop (created at task start).
        self._shadow_loggers_ch_client: Any | None = None

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
        return self._running and self.state in (
            TradingState.RUNNING,
            TradingState.WAITING,
        )

    async def start(self):
        """거래 시작"""
        if self.state == TradingState.RUNNING:
            logger.warning("Already running")
            return

        self._stop_requested = False
        self.state = TradingState.RUNNING
        self.start_time = datetime.now()

        logger.info("Starting trading...")

        # Initialize components
        await self._initialize_components()

        # Start shared market data loop before pipeline
        await self._start_market_data_loop()

        # Start LLM context publisher loop (if enabled)
        await self._start_llm_context_publisher()

        # Start kill-switch consumer loop (Phase 0.2-c)
        await self._start_kill_switch_consumer()

        # Start shadow-loggers periodic flush loop (Phase 2)
        await self._start_shadow_loggers_flush()

        # Start KIS API error-rate publish loop (§10.3-A) — singleton tracker
        # publishes to Redis kill_switch:metrics:api_error_rate_5min so the
        # kill-switch consumer's ApiErrorRateCondition reads real data
        # instead of the 0.0 stub fallback.
        try:
            from shared.kis.error_rate import KISApiErrorRateTracker

            await KISApiErrorRateTracker.get_instance().start()
        except Exception as e:
            logger.warning(
                "kis_api_error_rate tracker start failed (%s) — "
                "kill_switch ApiErrorRateCondition will read 0.0 fallback",
                e,
                exc_info=True,
            )

        # 파이프라인 생성 및 시작
        self.pipeline = self._create_pipeline()
        await self.pipeline.start()

        # Publish initial status + start Prometheus
        if self._state_publisher:
            self._state_publisher.publish_status(self.get_status())
        default_prom_port = 9092 if self.config.asset_class == "futures" else 9091
        prom_port = int(os.getenv("PROMETHEUS_PORT", str(default_prom_port)))
        self._metrics.start_prometheus_server(port=prom_port)

        await self._notify(
            f"🚀 Trading Started\n"
            f"Asset: {self.config.asset_class}\n"
            f"Strategy: {self.config.strategy_name}\n"
            f"Capital: {self.config.initial_capital:,.0f}"
        )

    async def _initialize_components(self):
        """Initialize trading components"""
        # 1. Initialize KIS Client & Config
        kis_config = self._init_kis_client()

        # 2. Initialize futures slippage controller (if enabled)
        self._init_futures_slippage_controller()

        # 3. Initialize Price Feeds (WebSocket)
        data_source = self._init_price_feeds(kis_config)

        # 4. Initialize Data Provider
        self._init_data_provider(data_source)

        # 5. Initialize optional tick stream publisher (monitoring only)
        self._init_tick_stream_publisher()

        # 6. Initialize Strategy Infra
        self._init_strategy_infrastructure()

        # 7. Initialize Indicator Engine + feed callbacks
        self._init_indicator_engine()

        # 8. Initialize Execution Layer
        await self._init_execution_layer()

        # 9. Load Swing Positions
        await self._load_swing_positions()

        # 10. Initialize LLM Context Publisher
        self._init_llm_context_publisher()

    @staticmethod
    def _deep_merge_config_dict(
        base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Recursively merge two config dictionaries without mutating inputs."""
        merged: dict[str, Any] = dict(base)
        for key, value in override.items():
            current = merged.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged[key] = TradingOrchestrator._deep_merge_config_dict(
                    current, value
                )
            else:
                merged[key] = value
        return merged

    def _load_entry_reentry_guard_config(self) -> EntryReentryGuardConfig:
        """Load post-exit re-entry guard config from execution.yaml."""
        try:
            raw = ConfigLoader.load("execution.yaml").get("entry_reentry_guard", {})
            return EntryReentryGuardConfig.from_dict(raw)
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
            ValueError,
        ) as e:
            logger.warning("Entry re-entry guard config invalid; disabled: %s", e)
            return EntryReentryGuardConfig(enabled=False)

    def _init_futures_slippage_controller(self) -> None:
        """Initialize futures slippage controller from YAML config."""
        self._futures_slippage_controller = None
        self._futures_slippage_aux_symbols = []

        if self.config.asset_class != "futures":
            return

        try:
            exec_cfg = ConfigLoader.load("execution.yaml")
            raw = exec_cfg.get("futures_slippage_control", {})
            if not isinstance(raw, dict):
                raw = {}
            else:
                raw = dict(raw)

            paper_override = raw.pop("paper_override", None)
            if self.config.paper_trading and isinstance(paper_override, dict):
                if bool(paper_override.get("enabled", False)):
                    override_payload = {
                        k: v for k, v in paper_override.items() if k != "enabled"
                    }
                    raw = self._deep_merge_config_dict(raw, override_payload)
                    logger.info(
                        "Applied paper override for futures slippage control: %s",
                        ",".join(sorted(override_payload.keys())),
                    )
        except (InvalidConfigError, MissingConfigError, OSError, yaml.YAMLError) as e:
            logger.warning(f"Failed to load futures slippage config: {e}")
            raw = {}

        try:
            from shared.execution.slippage_control import (
                FuturesSlippageController,
                SlippageControlConfig,
            )

            cfg = SlippageControlConfig.from_dict(raw)
            if not cfg.enabled:
                logger.info("Futures slippage control disabled")
                return

            self._futures_slippage_controller = FuturesSlippageController(cfg)
            if cfg.cross_asset_enabled and cfg.cross_asset_symbol:
                if cfg.cross_asset_symbol not in (self.config.symbols or []):
                    self._futures_slippage_aux_symbols = [cfg.cross_asset_symbol]

            logger.info(
                "Futures slippage control enabled (%s): spread<=%st, depth>=%.1fx, "
                "deviation<=%st, cooldown=%.2fs, retry=%s, cross_asset=%s",
                "paper" if self.config.paper_trading else "live",
                cfg.max_spread_ticks,
                cfg.min_depth_multiplier,
                cfg.max_price_deviation_ticks,
                cfg.volatility_cooldown_seconds,
                cfg.retry_policy.value,
                cfg.cross_asset_symbol if cfg.cross_asset_enabled else "off",
            )
        except (ConfigurationError, ValidationError, ValueError, TypeError) as e:
            logger.warning(f"Futures slippage controller init failed: {e}")
            self._futures_slippage_controller = None
            self._futures_slippage_aux_symbols = []

    def _init_kis_client(self):
        """Initialize KIS REST API Client"""
        try:
            from shared.kis.auth import KISAuthConfig
            from shared.kis.client import KISClient

            if self.config.asset_class == "futures":
                app_key = os.getenv("KIS_FUTURES_APP_KEY", os.getenv("KIS_APP_KEY", ""))
                app_secret = os.getenv(
                    "KIS_FUTURES_APP_SECRET", os.getenv("KIS_APP_SECRET", "")
                )
                # 선물은 항상 실서버 사용 (모의서버는 선물 시세 미지원)
                is_real = True
            else:
                app_key = os.getenv("KIS_APP_KEY", "")
                app_secret = os.getenv("KIS_APP_SECRET", "")
                market = os.getenv("KIS_STOCK_MARKET", "real")
                is_real = market.lower() == "real"
            kis_config = KISAuthConfig(
                app_key=app_key, app_secret=app_secret, is_real=is_real
            )
            self._kis_client = KISClient(kis_config)
            logger.info("KIS Client initialized")
            return kis_config
        except (ConfigurationError, APIError, NetworkError) as e:
            logger.warning(f"Failed to initialize KIS Client: {e}")
            self._kis_client = None
            return None

    def _init_price_feeds(self, kis_config) -> Any | None:
        """Initialize WebSocket Price Feeds"""
        self._stock_price_feed = None
        self._futures_price_feed = None
        data_source = None

        if not self._kis_client or not kis_config:
            return None

        if self.config.asset_class == "stock":
            try:
                from shared.kis.stock_feed import KISStockPriceFeed

                self._stock_price_feed = KISStockPriceFeed(
                    config=kis_config,
                )
                data_source = self._stock_price_feed
                logger.info("Stock WebSocket price feed initialized")
            except (NetworkError, WebSocketDisconnectError, ConfigurationError) as e:
                logger.warning(f"Stock WebSocket feed init failed: {e}")
        elif self.config.asset_class == "futures":
            try:
                from shared.kis.futures_feed import KISFuturesPriceFeed

                self._futures_price_feed = KISFuturesPriceFeed(
                    config=kis_config,
                )
                data_source = self._futures_price_feed
                logger.info("Futures WebSocket price feed initialized")
            except (NetworkError, WebSocketDisconnectError, ConfigurationError) as e:
                logger.warning(f"Futures WebSocket feed init failed: {e}")

        return data_source

    def _init_data_provider(self, data_source):
        """Initialize Market Data Provider"""
        try:
            streaming_cfg = ConfigLoader.load("streaming.yaml")
            dp_cfg = streaming_cfg.get("data_provider", {})
            failover_cfg = streaming_cfg.get("failover", {})
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
        ):
            dp_cfg = {}
            failover_cfg = {}

        if data_source:
            cache_ttl = float(dp_cfg.get("cache_ttl_websocket", 2.0))
        else:
            if self.config.asset_class == "stock":
                cache_ttl = float(dp_cfg.get("cache_ttl_stock", 30.0))
            else:
                cache_ttl = float(dp_cfg.get("cache_ttl_futures", 5.0))

        stagger_delay = float(dp_cfg.get("stagger_delay", 0.1))

        telegram_notifier = None
        send_telegram_alerts = bool(failover_cfg.get("send_telegram_alerts", True))
        if self.config.enable_telegram and send_telegram_alerts:
            try:
                from shared.notification.telegram import (
                    TelegramNotifier,
                    resolve_domain_credentials,
                )

                domain = (
                    self.config.asset_class
                    if self.config.asset_class in ("stock", "futures")
                    else None
                )
                # Use resolve_domain_credentials (NOT SecretsManager.telegram_token)
                # to avoid the silent legacy fallback to TELEGRAM_BOT_TOKEN.
                # If futures env is empty for any reason, the legacy fallback
                # would route futures alerts to the stock channel because
                # `.env` aliases TELEGRAM_BOT_TOKEN=${TELEGRAM_STOCK_BOT_TOKEN}.
                env_token, env_chat = resolve_domain_credentials(domain)
                bot_token = self.config.telegram_token or env_token
                chat_id = self.config.telegram_chat_id or env_chat
                if bot_token and chat_id:
                    telegram_notifier = TelegramNotifier(
                        bot_token=bot_token,
                        chat_id=chat_id,
                    )
            except Exception as e:
                logger.warning("Failed to initialize failover telegram notifier: %s", e)

        self._data_provider_failover_enabled = bool(failover_cfg.get("enabled", False))

        self._data_provider = MarketDataProvider(
            symbols=self.config.symbols,
            config=DataProviderConfig(
                cache_ttl_seconds=cache_ttl,
                batch_size=int(dp_cfg.get("batch_size", 20)),
                fetch_timeout_seconds=float(dp_cfg.get("fetch_timeout_seconds", 5.0)),
                stagger_delay_seconds=stagger_delay,
                health_check_interval_seconds=float(
                    failover_cfg.get("health_check_interval_seconds", 5.0)
                ),
                rest_poll_interval_seconds=float(
                    failover_cfg.get("rest_poll_interval_seconds", 5.0)
                ),
                staleness_threshold_seconds=float(
                    failover_cfg.get("staleness_threshold_seconds", 10.0)
                ),
                min_fresh_ratio=float(failover_cfg.get("min_fresh_ratio", 0.5)),
                startup_grace_seconds=float(
                    failover_cfg.get("startup_grace_seconds", 60.0)
                ),
                rest_fallback_max_symbols=failover_cfg.get("rest_fallback_max_symbols"),
                send_telegram_alerts=send_telegram_alerts,
            ),
            kis_client=self._kis_client,
            data_source=data_source,
            telegram_notifier=telegram_notifier,
        )

    def _init_tick_stream_publisher(self) -> None:
        """Initialize optional Redis tick mirroring for monitoring."""
        try:
            from services.monitoring.tick_stream_publisher import (
                TickStreamPublisher,
                TickStreamPublisherConfig,
            )

            cfg = TickStreamPublisherConfig.from_env()
            if not cfg.enabled:
                self._tick_stream_publisher = None
                logger.info("Tick stream publisher disabled by env")
                return

            self._tick_stream_publisher = TickStreamPublisher(cfg)
            logger.info(
                "Tick stream publisher enabled "
                "(async=%s, stock_stream=%s, futures_stream=%s, "
                "stock_interval=%.2fs, futures_interval=%.2fs, queue=%d, batch=%d)",
                cfg.async_publish,
                cfg.stock_stream,
                cfg.futures_stream,
                cfg.stock_min_interval_seconds,
                cfg.futures_min_interval_seconds,
                cfg.queue_maxsize,
                cfg.flush_batch_size,
            )
        except (ConfigurationError, InfrastructureError) as e:
            self._tick_stream_publisher = None
            logger.warning(f"Tick stream publisher init failed: {e}")

    def _init_llm_context_publisher(self) -> None:
        """Initialize LLM Context Publisher for market analysis integration."""
        try:
            # Load LLM config (includes market_context_publisher section)
            llm_yaml = ConfigLoader.load("llm.yaml")
            publisher_config = llm_yaml.get("market_context_publisher", {})

            # Check if enabled
            if not publisher_config.get("enabled", False):
                self._llm_context_publisher = None
                logger.info("LLM context publisher disabled by config")
                return

            # Initialize publisher
            from services.trading.llm_context_publisher import LLMContextPublisher

            self._llm_context_publisher = LLMContextPublisher(
                asset_class=self.config.asset_class
            )
            logger.info(
                "LLM context publisher initialized "
                "(interval=%d min, redis_ttl=%d sec)",
                publisher_config.get("analysis_interval_minutes", 60),
                publisher_config.get("redis_ttl_seconds", 7200),
            )
        except (ConfigurationError, InvalidConfigError, MissingConfigError) as e:
            self._llm_context_publisher = None
            logger.warning(f"LLM context publisher init failed: {e}")

    def _init_strategy_infrastructure(self):
        """Initialize Strategy Manager and Position Tracker"""
        # Strategy manager
        strategy_names = (
            [self.config.strategy_name] if self.config.strategy_name else None
        )
        # Disable cost filter for futures — RL strategies manage entry quality
        # via confidence thresholds; mini futures low ATR causes false rejections
        cost_filter = self.config.asset_class != "futures"
        self._strategy_manager = StrategyManager(
            asset_class=self.config.asset_class,
            strategy_names=strategy_names,
            config=StrategyManagerConfig(cost_filter_enabled=cost_filter),
        )

        # Pre-register strategy names for Prometheus metric discovery
        self._metrics.register_strategies(self._strategy_manager.strategy_names)

        # Position tracker (route to asset-specific ClickHouse database)
        try:
            from shared.config.secrets import SecretsManager

            db_name = SecretsManager.clickhouse_database(self.config.asset_class)
        except (ConfigurationError, KeyError, AttributeError):
            db_name = ""
        # Derive global max_positions from sum of per-strategy limits
        global_max = 10
        if self._strategy_manager:
            strategy_limits = []
            for strategy in self._strategy_manager.strategies.values():
                sizer_config = getattr(strategy.position_sizer, "config", None)
                limit = getattr(sizer_config, "max_positions", 5)
                strategy_limits.append(limit)
            if strategy_limits:
                global_max = sum(strategy_limits)
        # Load batch insert settings from YAML config
        try:
            pt_cfg = ConfigLoader.load("execution.yaml").get("position_tracker", {})
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
        ):
            pt_cfg = {}
        self._position_tracker = PositionTracker(
            config=PositionTrackerConfig(
                max_positions=global_max,
                database=db_name,
                batch_size=int(pt_cfg.get("batch_size", 50)),
                flush_interval_seconds=float(pt_cfg.get("flush_interval_seconds", 5.0)),
                asset_class=self.config.asset_class,
            )
        )

        # Risk manager (portfolio-level cross-asset risk management)
        try:
            risk_config_data = ConfigLoader.load("risk_management.yaml")
            risk_params = risk_config_data.get("risk_management", {})
            risk_params = _risk_params_for_runtime_capital(
                risk_params, self.config.initial_capital
            )
            risk_config = RiskConfig.from_dict(risk_params)
            self._risk_manager = RiskManager(risk_config)
            logger.info(
                "Risk manager initialized: daily_loss_limit=%.1f%%, max_positions=%d",
                risk_config.daily_loss_limit_pct,
                risk_config.max_total_positions,
            )
        except (
            InvalidConfigError,
            MissingConfigError,
            ConfigurationError,
            ValidationError,
        ) as e:
            logger.warning(
                f"Risk manager init failed: {e}, continuing without risk management"
            )
            self._risk_manager = None

        # Adaptive position sizing based on strategy win rate
        try:
            from shared.strategy.adaptive_sizing import (
                AdaptiveSizingConfig,
                AdaptiveSizingManager,
            )

            sizing_raw = ConfigLoader.load("execution.yaml").get("adaptive_sizing", {})
            sizing_config = AdaptiveSizingConfig.from_dict(sizing_raw)
            self._adaptive_sizing = AdaptiveSizingManager(
                sizing_config, self.config.asset_class
            )
            self._adaptive_sizing.refresh()
        except (ConfigurationError, InfrastructureError) as e:
            logger.warning(f"Adaptive sizing init failed: {e}")

    def _init_indicator_engine(self):
        """Initialize Streaming Indicator Engine"""
        self._indicator_resolver = None
        try:
            from services.trading.indicator_engine import StreamingIndicatorEngine

            # Read indicator params from strategy entry configs
            bb_period, bb_std, rsi_period, high_period = 20, 2.0, 14, 5
            ema_periods_set: set[int] = set()
            if self._strategy_manager:
                for strategy in self._strategy_manager.strategies.values():
                    entry = getattr(strategy, "entry", None)
                    if entry is not None:
                        cfg = entry.get_config()
                        bb_period = cfg.get("bb_period", bb_period)
                        bb_std = cfg.get("bb_std", bb_std)
                        rsi_period = cfg.get("rsi_period", rsi_period)
                        high_period = cfg.get("breakout_period", high_period)
                        # Collect EMA periods from trend mode config
                        for ema_key in (
                            "trend_ema_fast",
                            "trend_ema_mid",
                            "trend_ema_slow",
                        ):
                            val = cfg.get(ema_key)
                            if val is not None:
                                ema_periods_set.add(int(val))
            ema_periods = sorted(ema_periods_set) if ema_periods_set else [5, 20, 60]

            # Read staleness threshold from streaming config
            try:
                _ie_cfg = ConfigLoader.load("streaming.yaml").get(
                    "indicator_engine", {}
                )
                staleness_seconds = float(_ie_cfg.get("staleness_seconds", 180.0))
                mtf_timeframes = _ie_cfg.get("mtf_timeframes", None)
                mtf_maxlen = int(_ie_cfg.get("mtf_maxlen", 250))
            except (
                InvalidConfigError,
                MissingConfigError,
                OSError,
                yaml.YAMLError,
                KeyError,
                TypeError,
                ValueError,
            ):
                staleness_seconds = 180.0
                mtf_timeframes = None
                mtf_maxlen = 250

            self._indicator_engine = StreamingIndicatorEngine(
                bb_period=bb_period,
                bb_std=bb_std,
                rsi_period=rsi_period,
                high_period=high_period,
                staleness_seconds=staleness_seconds,
                ema_periods=ema_periods,
                mtf_timeframes=mtf_timeframes,
                mtf_maxlen=mtf_maxlen,
            )
            logger.info(
                f"Indicator engine initialized (bb={bb_period}, "
                f"std={bb_std}, rsi={rsi_period}, high_n={high_period}, "
                f"mtf_timeframes={mtf_timeframes}, mtf_maxlen={mtf_maxlen})"
            )
        except (ValidationError, ValueError, TypeError) as e:
            logger.warning(f"Indicator engine init failed: {e}")
            self._indicator_engine = None

        # Always instantiate resolver (even if engine is None) to avoid hot path fallback
        try:
            from shared.indicators.resolver import StreamingIndicatorResolver

            required_keys = (
                tuple(self._strategy_manager.required_indicators)
                if self._strategy_manager
                else tuple()
            )
            self._indicator_resolver = StreamingIndicatorResolver(
                engine=self._indicator_engine,  # Can be None
                required_keys=required_keys,
            )
            logger.info(
                f"Indicator resolver initialized (required={len(required_keys)}, "
                f"momentum_tf={list(self._indicator_resolver.timeframes)})"
            )
        except (ValidationError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Indicator resolver init failed: {e}")
            self._indicator_resolver = None

        # Hook futures WebSocket ticks into indicator engine and monitoring stream.
        if self._futures_price_feed:

            def _on_futures_tick(
                symbol: str, data: dict[str, Any], ts: datetime
            ) -> None:
                if self._indicator_engine:
                    # Initialize baseline for new symbols (same logic as _feed_indicators)
                    if symbol not in self._indicator_engine._last_cumulative_volume:
                        if data.get("volume_is_cumulative") is not False:
                            raw_vol = float(data.get("volume", 0))
                            if raw_vol > 0:
                                self._indicator_engine.set_volume_baseline(
                                    symbol, raw_vol
                                )
                    self._indicator_engine.on_tick(symbol, data, ts)

                if self._paper_broker is not None:
                    try:
                        tick_price = float(data.get("close", 0.0) or 0.0)
                        if tick_price > 0:
                            self._paper_broker.record_price_observation(
                                symbol=symbol,
                                price=tick_price,
                                ts=(
                                    ts
                                    if ts.tzinfo is not None
                                    else ts.replace(tzinfo=UTC)
                                ),
                            )
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(
                            "record_price_observation skipped (futures): %s", e
                        )

                if self._futures_slippage_controller:
                    try:
                        price = float(data.get("close", 0.0) or 0.0)
                        if price > 0:
                            self._futures_slippage_controller.register_trade_tick(
                                symbol, price, timestamp=ts
                            )
                    except (
                        Exception
                    ):  # Graceful degradation: silently skip tick registration failures
                        pass

                if self._tick_stream_publisher:
                    monitor_data = dict(data)
                    if not str(monitor_data.get("name", "")).strip():
                        fallback_name = self._symbol_names.get(symbol, "")
                        if fallback_name:
                            monitor_data["name"] = fallback_name
                    self._tick_stream_publisher.publish("futures", symbol, monitor_data)

            self._futures_price_feed.set_tick_callback(_on_futures_tick)

        # Hook stock WebSocket ticks into indicator engine and monitoring stream.
        if self._stock_price_feed:

            def _on_stock_tick(symbol: str, data: dict[str, Any], ts: datetime) -> None:
                if self._indicator_engine:
                    if symbol not in self._indicator_engine._last_cumulative_volume:
                        raw_vol = float(data.get("volume", 0))
                        if raw_vol > 0:
                            self._indicator_engine.set_volume_baseline(symbol, raw_vol)
                    self._indicator_engine.on_tick(symbol, data, ts)

                if self._paper_broker is not None:
                    try:
                        tick_price = float(data.get("close", 0.0) or 0.0)
                        if tick_price > 0:
                            self._paper_broker.record_price_observation(
                                symbol=symbol,
                                price=tick_price,
                                ts=(
                                    ts
                                    if ts.tzinfo is not None
                                    else ts.replace(tzinfo=UTC)
                                ),
                            )
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug("record_price_observation skipped (stock): %s", e)

                if self._tick_stream_publisher:
                    monitor_data = dict(data)
                    if not str(monitor_data.get("name", "")).strip():
                        fallback_name = self._symbol_names.get(symbol, "")
                        if fallback_name:
                            monitor_data["name"] = fallback_name
                    self._tick_stream_publisher.publish("stock", symbol, monitor_data)

            self._stock_price_feed.set_tick_callback(_on_stock_tick)

    async def _init_execution_layer(self):
        """Initialize Execution Layer (Paper or Real)"""
        # Paper broker (if paper trading)
        if self.config.paper_trading:
            try:
                from shared.config.loader import ConfigLoader
                from shared.paper import VirtualBroker
                from shared.paper.config import PaperTradingConfig

                # Load paper broker guard parameters from execution.yaml
                exec_cfg = ConfigLoader.load("execution.yaml") or {}
                paper_broker_cfg = exec_cfg.get("paper_broker", {}) or {}

                paper_config = PaperTradingConfig(
                    initial_balance=self.config.initial_capital,
                    commission_rate=self.config.paper_commission_rate,
                    slippage_rate=self.config.paper_slippage_rate,
                    max_price_staleness_seconds=float(
                        paper_broker_cfg.get("max_price_staleness_seconds", 30.0)
                    ),
                    max_price_deviation_pct=float(
                        paper_broker_cfg.get("max_price_deviation_pct", 0.10)
                    ),
                    reference_price_lookback_minutes=int(
                        paper_broker_cfg.get("reference_price_lookback_minutes", 5)
                    ),
                )
                self._paper_broker = VirtualBroker(
                    initial_balance=self.config.initial_capital,
                    commission_rate=self.config.paper_commission_rate,
                    slippage_rate=self.config.paper_slippage_rate,
                    config=paper_config,
                )
                logger.info("Paper broker (VirtualBroker) initialized")
            except (ValidationError, ValueError, TypeError) as e:
                logger.warning(f"Paper broker init failed, using mock execution: {e}")

            # Mock mirror: additionally record paper trades in KIS mock account
            if os.getenv("MOCK_MIRROR_ENABLED", "").lower() == "true":
                try:
                    from shared.execution.mock_mirror import MockAccountMirror

                    self._mock_mirror = MockAccountMirror(
                        asset_class=self.config.asset_class
                    )
                    ok = await self._mock_mirror.initialize()
                    if ok:
                        logger.info(
                            "MockAccountMirror initialized — trades will be mirrored"
                        )
                    else:
                        self._mock_mirror = None
                except (
                    ConfigurationError,
                    APIError,
                    NetworkError,
                    InfrastructureError,
                ) as e:
                    logger.warning(f"MockAccountMirror init failed (ignored): {e}")
                    self._mock_mirror = None
        else:
            # KIS execution via shared.execution.OrderExecutor (MOCK/REAL).
            try:
                from shared.execution.config import ExecutionConfig
                from shared.execution.executor import OrderExecutor

                mode = (
                    self.config.execution_mode or os.getenv("TRADING_MODE", "MOCK")
                ).upper()
                if mode not in ("MOCK", "REAL"):
                    raise ValueError(
                        f"execution_mode must be MOCK or REAL for live execution, got {mode!r}"
                    )

                try:
                    raw_exec_cfg = ConfigLoader.load("execution.yaml").get(
                        "execution", {}
                    )
                except (
                    InvalidConfigError,
                    MissingConfigError,
                    OSError,
                    yaml.YAMLError,
                    KeyError,
                    TypeError,
                ):
                    raw_exec_cfg = {}

                exec_kwargs: dict[str, Any] = {}
                if isinstance(raw_exec_cfg, dict):
                    if "max_retries" in raw_exec_cfg:
                        exec_kwargs["max_retries"] = raw_exec_cfg["max_retries"]
                    if "retry_delay" in raw_exec_cfg:
                        exec_kwargs["retry_delay"] = raw_exec_cfg["retry_delay"]
                    if "order_request_timeout_seconds" in raw_exec_cfg:
                        exec_kwargs["order_request_timeout_seconds"] = raw_exec_cfg[
                            "order_request_timeout_seconds"
                        ]
                    # Backward compatibility: execution.yaml used orders_per_second key.
                    if "orders_per_second" in raw_exec_cfg:
                        exec_kwargs["requests_per_second"] = raw_exec_cfg[
                            "orders_per_second"
                        ]
                    elif "requests_per_second" in raw_exec_cfg:
                        exec_kwargs["requests_per_second"] = raw_exec_cfg[
                            "requests_per_second"
                        ]
                    if "futures_fill_check_enabled" in raw_exec_cfg:
                        exec_kwargs["futures_fill_check_enabled"] = raw_exec_cfg[
                            "futures_fill_check_enabled"
                        ]
                    if "futures_fill_check_poll_interval_seconds" in raw_exec_cfg:
                        exec_kwargs["futures_fill_check_poll_interval_seconds"] = (
                            raw_exec_cfg["futures_fill_check_poll_interval_seconds"]
                        )
                    if "futures_fill_check_timeout_seconds" in raw_exec_cfg:
                        exec_kwargs["futures_fill_check_timeout_seconds"] = (
                            raw_exec_cfg["futures_fill_check_timeout_seconds"]
                        )
                    if "futures_auto_cancel_unfilled" in raw_exec_cfg:
                        exec_kwargs["futures_auto_cancel_unfilled"] = raw_exec_cfg[
                            "futures_auto_cancel_unfilled"
                        ]

                exec_cfg = ExecutionConfig(
                    trading_mode=mode,
                    account_no=(
                        os.getenv(
                            "KIS_FUTURES_ACCOUNT_NO", os.getenv("KIS_ACCOUNT_NO", "")
                        )
                        if self.config.asset_class == "futures"
                        else os.getenv("KIS_ACCOUNT_NO", "")
                    ),
                    redis_url=os.getenv("REDIS_URL", ""),
                    rate_limit_key=self.config.asset_class,
                    **exec_kwargs,
                )

                auth_manager = (
                    getattr(self._kis_client, "auth_manager", None)
                    if self._kis_client
                    else None
                )
                self._order_executor = OrderExecutor(
                    config=exec_cfg, auth_manager=auth_manager
                )
                await self._order_executor.initialize()
                logger.info(f"OrderExecutor initialized (mode={mode})")
            except (
                ConfigurationError,
                APIError,
                NetworkError,
                InfrastructureError,
                ValidationError,
                ValueError,
            ) as e:
                logger.warning(f"OrderExecutor init failed; orders will be mocked: {e}")
                self._order_executor = None

    async def _load_swing_positions(self):
        """Recover open positions from Redis and initialize state publishers."""
        # --- Position recovery from Redis ---
        recovery_disabled = str(
            os.getenv("STS_DISABLE_POSITION_RECOVERY", "")
        ).strip().lower() in {"1", "true", "yes", "on"}
        if recovery_disabled:
            logger.info(
                "Position recovery disabled by env (STS_DISABLE_POSITION_RECOVERY)"
            )
        elif self._position_tracker:
            await self._recover_positions_from_redis()

        # --- Risk state recovery from Redis ---
        if self._risk_manager:
            if recovery_disabled:
                logger.info(
                    "Risk recovery disabled by env (STS_DISABLE_POSITION_RECOVERY)"
                )
            else:
                recovered = await self._risk_manager.load_from_redis()
                if recovered:
                    logger.info(
                        f"Risk state recovered: "
                        f"daily_pnl={self._risk_manager.state.daily_pnl:.2f}, "
                        f"positions={self._risk_manager.metrics.total_positions}, "
                        f"blocked={self._risk_manager.state.is_blocked}"
                    )
                else:
                    logger.info("No risk state to recover (fresh start)")

        # --- Broker position verification ---
        await self._verify_positions_with_broker()

        # Load accumulation candidates from Redis
        self._accumulation_candidates: dict[str, int] = {}
        self._refresh_accumulation_candidates()

        # Load dip candidates from Redis (for bb_reversion)
        self._dip_candidates: dict[str, dict[str, Any]] = {}
        self._refresh_dip_candidates()

        # Overnight macro snapshot for Setup A (gap reversion). Cached and
        # refreshed lazily — Setup A hard-requires ctx.macro_overnight, and
        # the orchestrator EntryContext previously never injected it (root
        # cause of "Signal cycle: 0 signals" since 2026-05-11 cutover).
        self._macro_snapshot: Any = None
        self._macro_snapshot_monotonic: float = 0.0
        try:
            _macro_cfg = ConfigLoader.load("macro_sources.yaml")
            self._macro_stream: str = _macro_cfg.get(
                "macro_overnight_collector", {}
            ).get("redis_stream", "stream:macro.overnight")
        except Exception:  # noqa: BLE001 — config optional; use canonical default
            self._macro_stream = "stream:macro.overnight"

        # Macro event calendar for Setup C (event reaction). Same wiring-gap
        # class as macro_overnight: Setup C's find_recent_event saw an empty
        # list every cycle because EntryContext.metadata never carried it.
        # Static monthly-maintained file → long (1h) refresh so an operator
        # mid-month edit propagates without a restart.
        self._scheduled_events: list[Any] = []
        self._scheduled_events_monotonic: float = 0.0

        # Load daily indicators from Redis (for daily_pullback + chandelier_exit)
        self._refresh_daily_indicators()

        # Redis state publisher
        try:
            from shared.streaming.trading_state import TradingStatePublisher

            self._state_publisher = TradingStatePublisher(self.config.asset_class)
            logger.info("Trading state publisher initialized")
        except (ConfigurationError, InfrastructureError) as e:
            logger.warning(f"Trading state publisher init failed: {e}")

        # Bootstrap symbols from screener if none configured
        if not self.config.symbols and self.config.asset_class == "stock":
            self._refresh_universe_from_screener()

        self._sync_open_positions_metric()

        # Ensure enriched metadata cache is built before hot path execution
        # Cache may already be built via _refresh_daily_indicators() or
        # _refresh_universe_from_screener(), but call explicitly to guarantee
        # it's populated for futures or when Redis data isn't available yet
        self._build_enriched_metadata_cache()

        logger.info(
            f"Components initialized: "
            f"{len(self._strategy_manager.strategies)} strategies, "
            f"{len(self.config.symbols)} symbols"
        )

    async def _recover_positions_from_redis(self) -> int:
        """Recover open positions from Redis on startup.

        Applies strategy-based freshness filter:
        - Swing strategies (SWING_STRATEGIES): recover up to 7 days
        - Intraday strategies: recover same-day only
        Stale positions are removed from Redis with logging.
        """
        try:
            from shared.streaming.trading_state import TradingStateReader

            reader = TradingStateReader(self.config.asset_class)
        except (ConfigurationError, InfrastructureError) as e:
            logger.warning(f"Cannot initialize TradingStateReader for recovery: {e}")
            return 0

        positions = reader.get_positions()
        if not positions:
            logger.info("No positions to recover from Redis")
            return 0

        today = datetime.now().date()
        max_age_days = self.config.swing_recovery_max_age_days
        recovered = 0
        stale = 0

        for pos_data in positions:
            pos_id = pos_data.get("id", "")
            strategy = pos_data.get("strategy", "")

            # Parse entry_time
            try:
                entry_time_str = pos_data.get("entry_time", "")
                entry_time = datetime.fromisoformat(entry_time_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid entry_time in Redis position: {pos_id[:8]}")
                reader.remove_position(pos_id)
                stale += 1
                continue

            # Freshness filter
            age_days = (today - entry_time.date()).days
            if strategy in self.SWING_STRATEGIES:
                if age_days > max_age_days:
                    logger.debug(
                        f"Stale swing position: {pos_data.get('code')} (age={age_days}d)"
                    )
                    reader.remove_position(pos_id)
                    stale += 1
                    continue
            else:
                # Intraday strategies: same-day only
                if entry_time.date() != today:
                    logger.debug(
                        f"Stale intraday position: {pos_data.get('code')} (age={age_days}d)"
                    )
                    reader.remove_position(pos_id)
                    stale += 1
                    continue

            # Reconstruct Position
            try:
                side_str = pos_data.get("side", "long")
                side = PositionSide(side_str)
                entry_price = float(pos_data["entry_price"])
                current_price = float(pos_data.get("current_price", entry_price))

                pos_code = pos_data["code"]
                position = Position(
                    id=pos_id,
                    code=pos_code,
                    name=pos_data.get("name", "")
                    or self._symbol_names.get(pos_code, pos_code),
                    side=side,
                    quantity=int(pos_data["quantity"]),
                    entry_price=entry_price,
                    entry_time=entry_time,
                    current_price=current_price,
                    highest_price=float(
                        pos_data.get("highest_price", max(entry_price, current_price))
                    ),
                    lowest_price=float(
                        pos_data.get("lowest_price", min(entry_price, current_price))
                    ),
                    state=PositionState(pos_data.get("state", "survival").lower()),
                    strategy=strategy,
                    fee_rate=float(pos_data.get("fee_rate", 0.003)),
                )

                stop_price = pos_data.get("stop_price")
                if stop_price is not None:
                    position.stop_price = float(stop_price)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to reconstruct position {pos_id[:8]}: {e}")
                reader.remove_position(pos_id)
                stale += 1
                continue

            if self._position_tracker.add_recovered_position(position):
                recovered += 1
                # Ensure symbol receives WebSocket ticks
                current_symbols = set(self.config.symbols or [])
                if position.code not in current_symbols:
                    if self.config.symbols is None:
                        self.config.symbols = []
                    self.config.symbols.append(position.code)
                    self._symbol_last_seen[position.code] = datetime.now()

        if stale > 0:
            logger.info(f"Cleaned {stale} stale positions from Redis")
        if recovered > 0:
            logger.info(
                f"Recovered {recovered} positions from Redis ({self.config.asset_class})"
            )
        return recovered

    async def _verify_positions_with_broker(self) -> None:
        """Redis 복구 포지션과 브로커 실제 잔고 비교.

        기본적으로 실행하되, futures paper 모드에서는 건너뛴다.
        (선물 paper는 VirtualBroker 상태가 기준이며 브로커 잔고조회 노이즈 방지)
        """
        # Load broker_verification config
        try:
            exec_cfg = ConfigLoader.load("execution.yaml")
            bv_cfg = exec_cfg.get("broker_verification", {})
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
        ):
            bv_cfg = {}

        if not bv_cfg.get("enabled", True):
            return

        if not self._kis_client:
            logger.debug("KIS client not available; skipping broker verification")
            return

        # Futures paper trading uses VirtualBroker state as source-of-truth.
        # Skip broker inquiry to avoid account-mapping noise and startup latency.
        if self.config.asset_class == "futures" and self.config.paper_trading:
            logger.info("Futures paper mode: skipping broker verification")
            return

        # Futures mock server doesn't support balance inquiry
        if self.config.asset_class == "futures" and not self._kis_client.config.is_real:
            logger.debug("Futures mock server: skipping broker verification")
            return

        try:
            if self.config.asset_class == "stock":
                broker_positions = await self._kis_client.get_stock_balance()
            else:
                broker_positions = await self._kis_client.get_futures_balance()
        except (APIError, NetworkError) as e:
            logger.warning(f"Broker balance inquiry failed: {e}")
            return

        if not broker_positions and not self._position_tracker.positions:
            logger.info("Broker verification: no positions on either side")
            return

        redis_by_code: dict[str, Position] = {}
        for pos in self._position_tracker.positions:
            redis_by_code[pos.code] = pos

        broker_by_code: dict[str, dict] = {}
        for bp in broker_positions:
            broker_by_code[bp["code"]] = bp

        redis_codes = set(redis_by_code)
        broker_codes = set(broker_by_code)
        matched = redis_codes & broker_codes
        redis_only = redis_codes - broker_codes
        broker_only = broker_codes - redis_codes

        reconcile_qty = bv_cfg.get("reconcile_quantity", True)
        notify = bv_cfg.get("notify_on_mismatch", True)
        auto_track = bv_cfg.get("auto_track_external", False)
        alerts: list[str] = []

        # 1. Matched — verify quantity and side
        for code in matched:
            rp = redis_by_code[code]
            bp = broker_by_code[code]
            broker_side = PositionSide(bp["side"])

            if rp.side != broker_side:
                msg = (
                    f"[{code}] SIDE MISMATCH: Redis={rp.side.value}, "
                    f"Broker={broker_side.value}"
                )
                logger.error(msg)
                alerts.append(msg)

            if rp.quantity != bp["quantity"]:
                msg = (
                    f"[{code}] Quantity mismatch: "
                    f"Redis={rp.quantity}, Broker={bp['quantity']}"
                )
                logger.warning(msg)
                if reconcile_qty:
                    rp.quantity = bp["quantity"]
                    logger.info(
                        f"[{code}] Quantity reconciled to broker value: {bp['quantity']}"
                    )
                else:
                    alerts.append(msg)

        # 2. Redis-only — position may have been closed externally
        for code in redis_only:
            rp = redis_by_code[code]
            msg = (
                f"[{code}] Redis-only position (not in broker). "
                f"qty={rp.quantity}, entry={rp.entry_price:,.0f}"
            )
            logger.warning(msg)
            alerts.append(msg)

        # 3. Broker-only — external position not tracked by system
        for code in broker_only:
            bp = broker_by_code[code]
            msg = (
                f"[{code}] Broker-only position (not in Redis). "
                f"qty={bp['quantity']}, avg_price={bp['avg_price']:,.0f}"
            )
            logger.warning(msg)
            if auto_track:
                try:
                    new_pos = Position(
                        id=f"broker_{code}_{datetime.now().strftime('%H%M%S')}",
                        code=code,
                        name=bp.get("name", ""),
                        side=PositionSide(bp["side"]),
                        quantity=bp["quantity"],
                        entry_price=bp["avg_price"],
                        current_price=bp.get("current_price", bp["avg_price"]),
                        strategy="external",
                    )
                    if self._position_tracker.add_recovered_position(new_pos):
                        logger.info(f"[{code}] Auto-tracked broker position")
                        if code not in (self.config.symbols or []):
                            if self.config.symbols is None:
                                self.config.symbols = []
                            self.config.symbols.append(code)
                except (
                    ValidationError,
                    InfrastructureError,
                    ValueError,
                    KeyError,
                ) as e:
                    logger.warning(f"[{code}] Failed to auto-track: {e}")
            else:
                alerts.append(msg)

        # Summary
        total = len(matched) + len(redis_only) + len(broker_only)
        if total > 0:
            logger.info(
                f"Broker verification: {len(matched)} matched, "
                f"{len(redis_only)} Redis-only, {len(broker_only)} broker-only"
            )

        # Telegram alert for mismatches
        if alerts and notify:
            alert_text = (
                f"⚠️ Broker Position Verification ({self.config.asset_class})\n\n"
                + "\n".join(alerts)
            )
            await self._notify(alert_text)

    async def _ensure_db_schema(self):
        """Ensure ClickHouse persistence tables exist."""
        try:
            from shared.db.client import SCHEMAS, SyncClient

            if not self._position_tracker:
                return

            ch, database = self._position_tracker._get_db_client()

            def _sync_init():
                # Create database if needed
                temp_client = SyncClient(
                    host=ch.config.host,
                    port=ch.config.port,
                    user=ch.config.user,
                    password=ch.config.password,
                )
                temp_client.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
                temp_client.disconnect()

                # Create persistence tables used by orchestrator.
                client = ch.get_sync_client()
                for table_name in ("swing_positions", "rl_trades"):
                    schema = SCHEMAS.get(table_name)
                    if schema:
                        client.execute(schema.format(database=database))

            await asyncio.to_thread(_sync_init)
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.warning(f"Failed to ensure DB schema: {e}")

    async def _persist_closed_position(self, closed, strategy: str):
        """Persist a closed position to ClickHouse with asset-class routing.

        - asset_class='stock' → market.stock_trades (모든 주식 전략)
                             + market.swing_positions (SWING_STRATEGIES만, state 추적용)
        - asset_class='futures' + strategy.startswith('rl_') → kospi.rl_trades
        - 그 외 → no-op (로그만)
        """
        try:
            if not self._position_tracker:
                return
            strategy = str(strategy or "")
            if self.config.asset_class == "stock":
                await self._position_tracker.save_stock_trade_to_db(closed)
                if strategy in self.SWING_STRATEGIES:
                    await self._position_tracker.save_closed_to_db(closed)
            elif self.config.asset_class == "futures" and strategy.startswith("rl_"):
                await self._position_tracker.save_rl_trade_to_db(
                    closed, self.config.asset_class
                )
            else:
                logger.debug(
                    "persist skipped: asset_class=%s strategy=%s",
                    self.config.asset_class,
                    strategy,
                )
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.warning(
                f"Failed to persist closed position {getattr(closed, 'id', '?')[:8]}: {e}"
            )

    def _record_running_totals(self, closed_position) -> None:
        """Publish cross-session cumulative counters on each close.

        Idempotent per close event (increments only; no session reset).
        """
        if self._state_publisher is None:
            return
        try:
            pnl = getattr(closed_position, "unrealized_pnl", 0.0) or 0.0
            self._state_publisher.increment_running_totals(
                pnl=float(pnl),
                trades=1,
                win=bool(pnl > 0),
            )
        except (AttributeError, ValueError, TypeError) as e:
            logger.debug("record_running_totals skipped: %s", e)

    async def _record_risk_realized_pnl(self, pnl: float) -> None:
        """Feed closed-trade P&L into the entry risk gate immediately."""
        if self._risk_manager is None:
            return
        try:
            self._risk_manager.record_realized_pnl(float(pnl))
            await self._risk_manager.save_to_redis()
        except (InfrastructureError, ValidationError, ValueError, TypeError) as e:
            logger.warning("risk realized P&L update skipped: %s", e)

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
                if (
                    isinstance(code, str)
                    and code.isalnum()
                    and isinstance(score, (int, float))
                ):
                    validated[code] = int(score)

            self._accumulation_candidates = validated
            logger.info(
                f"Loaded {len(self._accumulation_candidates)} accumulation candidates"
            )
            return True
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.debug(f"Accumulation candidates not available: {e}")
            return False

    SWING_STRATEGIES = frozenset(
        {"volume_accumulation", "bb_reversion", "daily_pullback", "vr_composite"}
    )
    DIP_CANDIDATES_REDIS_KEY = "system:dip_candidates:latest"
    LLM_QUALITY_REDIS_KEY = "system:llm_quality:latest"

    def _get_macro_overnight(self) -> Any:
        """Latest overnight :class:`MacroSnapshot` for Setup A gap-reversion.

        Setup A hard-requires ``ctx.macro_overnight`` (``gap_reversion.py``
        returns None when absent). Cached with a 60 s refresh — the collector
        updates fx every 15 min / US at 06:30 KST, so per-cycle Redis reads
        would be wasteful. Freshness guard: a snapshot older than 24 h is
        treated as absent (stale multi-day macro must not drive today's
        gap-reversion; Setup A then correctly no-ops instead of acting on
        stale data). Never raises — observability/decision input only.
        """
        now_mono = time.monotonic()
        if (
            self._macro_snapshot is not None
            and now_mono - self._macro_snapshot_monotonic < 60.0
        ):
            return self._macro_snapshot
        try:
            from shared.macro.base import read_latest_macro_snapshot
            from shared.streaming.client import RedisClient

            snap = read_latest_macro_snapshot(
                RedisClient.get_client(), self._macro_stream
            )
        except Exception as exc:  # noqa: BLE001 — never break the entry loop
            logger.debug("macro snapshot fetch failed: %s", exc)
            snap = None

        if snap is not None:
            age_ms = (time.time() * 1000.0) - float(getattr(snap, "ts_ms", 0))
            if age_ms > 86_400_000.0:  # > 24h → stale overnight data
                logger.debug(
                    "macro snapshot stale (%.1fh) — treating as absent",
                    age_ms / 3_600_000.0,
                )
                snap = None

        self._macro_snapshot = snap
        self._macro_snapshot_monotonic = now_mono
        return snap

    def _get_scheduled_events(self) -> list[Any]:
        """Macro event calendar for Setup C (event reaction).

        Setup C's ``find_recent_event`` needs ``ctx.scheduled_events``; the
        orchestrator never injected it (root cause of Setup C 0 signals
        since cutover). Cached with a 1 h refresh — the calendar is a
        static, manually monthly-maintained file, so per-cycle reloads are
        wasteful but a long TTL still picks up a mid-month operator edit
        without a process restart. ``find_recent_event`` does its own
        now/window filtering, so injecting the full parsed list is correct.
        Never raises.
        """
        now_mono = time.monotonic()
        if (
            self._scheduled_events
            and now_mono - self._scheduled_events_monotonic < 3600.0
        ):
            return self._scheduled_events
        try:
            from shared.config.loader import ConfigLoader
            from shared.decision.context import load_scheduled_events

            path = str(ConfigLoader.get_config_dir() / "scheduled_events.yaml")
            events = load_scheduled_events(path)
        except Exception as exc:  # noqa: BLE001 — never break the entry loop
            logger.debug("scheduled_events load failed: %s", exc)
            events = []
        # Keep the previous good list if a reload transiently returns empty.
        if events:
            self._scheduled_events = events
        self._scheduled_events_monotonic = now_mono
        return self._scheduled_events

    def _refresh_dip_candidates(self) -> bool:
        """Load dip (sharp-drop) candidates from Redis for mean-reversion strategies.

        Cross-checks with LLM quality scores to exclude structurally broken stocks.
        """
        try:
            from shared.streaming.client import RedisClient

            redis_client = RedisClient.get_client()
            raw = redis_client.get(self.DIP_CANDIDATES_REDIS_KEY)
            if not raw:
                return False

            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return False

            codes = payload.get("codes", [])
            info = payload.get("info", {})
            if not isinstance(codes, list):
                return False

            # Load LLM quality scores for filtering
            # LLM payload schema: {excluded: {code: [reasons]}, raw_scores: {code: score}}
            llm_blacklist: set[str] = set()
            llm_raw = redis_client.get(self.LLM_QUALITY_REDIS_KEY)
            if llm_raw:
                try:
                    llm_payload = json.loads(llm_raw)
                    # Codes explicitly excluded by LLM analysis
                    excluded = llm_payload.get("excluded", {})
                    if isinstance(excluded, dict):
                        llm_blacklist.update(excluded.keys())
                    # Codes with negative raw scores
                    raw_scores = llm_payload.get("raw_scores", {})
                    if isinstance(raw_scores, dict):
                        for code, score in raw_scores.items():
                            if isinstance(score, (int, float)) and score < 0:
                                llm_blacklist.add(code)
                except (KeyError, TypeError, ValueError, AttributeError):
                    # Silently skip if LLM quality data is malformed
                    pass

            validated: dict[str, dict[str, Any]] = {}
            for code in codes:
                code = str(code).strip()
                if not code:
                    continue
                if code in llm_blacklist:
                    logger.debug(f"Dip candidate {code} blocked by LLM blacklist")
                    continue
                code_info = info.get(code, {})
                validated[code] = {
                    "name": code_info.get("name", ""),
                    "price": code_info.get("price", 0),
                    "change_pct": code_info.get("change_pct", 0),
                }

            self._dip_candidates = validated
            if validated:
                logger.info(
                    f"Loaded {len(validated)} dip candidates (filtered {len(llm_blacklist)} by LLM)"
                )
            return bool(validated)
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.debug(f"Dip candidates not available: {e}")
            return False

    DAILY_INDICATORS_REDIS_KEY = "system:daily_indicators:latest"

    def _refresh_daily_indicators(self) -> bool:
        """Load pre-computed daily indicators from Redis (published by daily_indicator_scanner).

        Used by daily_pullback entry and chandelier_exit strategies.
        """
        try:
            from shared.streaming.client import RedisClient

            redis_client = RedisClient.get_client()
            raw = redis_client.get(self.DAILY_INDICATORS_REDIS_KEY)
            if not raw:
                return False

            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return False

            indicators = payload.get("indicators", {})
            if not isinstance(indicators, dict):
                return False

            self._daily_indicators = indicators

            # Invalidate enriched metadata cache after daily indicators update
            self._invalidate_enriched_metadata_cache()

            if indicators:
                logger.info(f"Loaded daily indicators for {len(indicators)} symbols")
            return True
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.debug(f"Daily indicators not available: {e}")
            return False

    def _build_enriched_metadata_cache(self):
        """Build pre-merged metadata cache to avoid repeated dict operations in hot path.

        Merges symbol_metadata + daily_indicators per symbol into _enriched_metadata_cache
        for market_data enrichment. Also stores them separately for targeted use:
        - _cached_symbol_meta: pure symbol_metadata (for context.metadata)
        - _cached_daily_indicators: pure daily indicators (for indicators dict)

        This cache is rebuilt whenever symbol_metadata or _daily_indicators change.
        Pattern follows MarketDataCache from services/trading/data_provider.py.
        """
        self._enriched_metadata_cache.clear()
        self._cached_symbol_meta.clear()
        self._cached_daily_indicators.clear()

        # Get all symbols from both metadata sources
        metadata_symbols = set((self.config.symbol_metadata or {}).keys())
        daily_symbols = set(self._daily_indicators.keys())
        all_symbols = metadata_symbols | daily_symbols

        for symbol in all_symbols:
            # Start with symbol_metadata (static watchlist metadata)
            meta = (self.config.symbol_metadata or {}).get(symbol, {})
            enriched = dict(meta) if meta else {}

            # Ensure code is always present
            enriched["code"] = symbol

            # Merge daily indicators (pre-market scanner data)
            daily_ind = self._daily_indicators.get(symbol, {})
            if daily_ind:
                enriched.update(daily_ind)

            # Store merged cache for market_data enrichment
            self._enriched_metadata_cache[symbol] = enriched

            # Store separated caches for targeted use
            if meta:
                self._cached_symbol_meta[symbol] = meta
            if daily_ind:
                self._cached_daily_indicators[symbol] = daily_ind

        logger.debug(
            f"Built enriched metadata cache: {len(self._enriched_metadata_cache)} symbols "
            f"(metadata={len(metadata_symbols)}, daily={len(daily_symbols)})"
        )

    def _invalidate_enriched_metadata_cache(self):
        """Invalidate and rebuild enriched metadata cache.

        Called whenever symbol_metadata or _daily_indicators are updated to ensure
        the pre-merged cache stays synchronized. This triggers a full cache rebuild
        by calling _build_enriched_metadata_cache().

        Usage:
            - After _apply_universe_changes() updates symbol_metadata
            - After _refresh_daily_indicators() updates _daily_indicators
        """
        logger.debug("Invalidating enriched metadata cache")
        self._build_enriched_metadata_cache()

    def _load_ranked_targets(
        self, redis
    ) -> tuple[list[str], dict[str, str], dict[str, dict[str, Any]]]:
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
            except (
                ValidationError,
                KeyError,
                TypeError,
                ValueError,
                AttributeError,
            ) as e:
                logger.debug(f"Failed parsing ranked target payload ({key}): {e}")

        return [], {}, {}

    def _filter_dynamic_universe_coverage(
        self,
        codes: list[str],
        names: dict[str, str],
        metadata: dict[str, dict[str, Any]],
    ) -> tuple[list[str], dict[str, str], dict[str, dict[str, Any]]]:
        """Reject dynamic stock candidates that lack daily indicator coverage."""
        if (
            self.config.asset_class != "stock"
            or self.config.universe_mode != "dynamic"
            or not self.config.require_daily_indicators_for_dynamic_universe
        ):
            return codes, names, metadata

        covered = set(self._daily_indicators.keys())
        if not covered:
            if codes:
                logger.warning(
                    "Dynamic universe coverage guard rejected %s candidates: "
                    "daily indicators unavailable",
                    len(codes),
                )
            return [], {}, {}

        filtered_codes = [code for code in codes if code in covered]
        if len(filtered_codes) == len(codes):
            return codes, names, metadata

        filtered_set = set(filtered_codes)
        removed = [code for code in codes if code not in filtered_set]
        logger.warning(
            "Dynamic universe coverage guard removed %s/%s candidates without "
            "daily indicators: %s",
            len(removed),
            len(codes),
            ",".join(removed[:10]),
        )
        return (
            filtered_codes,
            {code: name for code, name in names.items() if code in filtered_set},
            {
                code: dict(meta)
                for code, meta in metadata.items()
                if code in filtered_set
            },
        )

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
            codes, names, metadata = self._filter_dynamic_universe_coverage(
                codes, names, metadata
            )
            if not codes:
                stable_symbols = self._get_stable_universe()
                if stable_symbols:
                    self._apply_universe_changes(stable_symbols)
                    self._check_strategy_warnings()
                    return True
                return False

            # Update internal caches with new screen results
            self._update_symbol_cache(codes, names, metadata)

            # Determine surviving universe based on retention & size limits
            stable_symbols = self._get_stable_universe()

            # Apply changes to config and data provider
            self._apply_universe_changes(stable_symbols)

            # Monitor for strategy capability issues
            self._check_strategy_warnings()

            return True

        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.warning(f"Universe refresh failed: {e}")
        return False

    def _load_static_watchlist(self) -> bool:
        """Load static universe from daily watchlist (Redis).

        In static mode, the universe is fixed for the trading day based on
        the DailyScanner's pre-market analysis of daily candles.
        """
        try:
            from shared.streaming.client import RedisClient

            redis = RedisClient.get_client()
            raw = redis.get(self._daily_watchlist_key)
            if not raw:
                logger.warning(
                    "Static watchlist not found in Redis "
                    f"(key={self._daily_watchlist_key}). "
                    "Falling back to dynamic screener mode."
                )
                return False

            payload = json.loads(raw)
            strategies = payload.get("strategies", {})
            symbol_metadata = payload.get("symbol_metadata", {})
            all_codes: set[str] = set()
            for strat_codes in strategies.values():
                if isinstance(strat_codes, list):
                    all_codes.update(
                        str(c).strip() for c in strat_codes if str(c).strip()
                    )

            if not all_codes:
                logger.warning(
                    "Static watchlist is empty, falling back to dynamic mode."
                )
                return False

            # Store full watchlist for injection into entry context
            self._daily_watchlist = payload

            if isinstance(symbol_metadata, dict):
                for code in all_codes:
                    raw_meta = symbol_metadata.get(code, {})
                    if not isinstance(raw_meta, dict):
                        continue
                    meta = dict(raw_meta)
                    name = str(meta.get("name", "")).strip()
                    if name:
                        self._symbol_names[code] = name
                    if meta:
                        self._symbol_metadata_cache[code] = meta

            # Best-effort name hydration for static watchlists that only provide codes.
            self._hydrate_missing_symbol_names(all_codes)

            # Set universe
            now = datetime.now()
            for code in all_codes:
                self._symbol_last_seen[code] = now
            self.config.symbols = list(all_codes)

            if self._data_provider:
                self._data_provider.symbols = list(all_codes)

            if self._stock_price_feed:
                self._stock_price_feed.update_symbols(list(all_codes))

            logger.info(
                f"Static watchlist loaded: {len(all_codes)} symbols "
                f"(strategies: {', '.join(f'{k}={len(v)}' for k, v in strategies.items())})"
            )
            return True

        except (InfrastructureError, OSError, ConnectionError, ValidationError) as e:
            logger.warning(f"Failed to load static watchlist: {e}")
            return False

    def _hydrate_missing_symbol_names(self, codes: list[str] | set[str]) -> None:
        """Fill missing stock names using KRX Open API as a best-effort fallback."""
        if self.config.asset_class != "stock":
            return

        pending = []
        for raw_code in codes:
            code = str(raw_code).strip()
            if not code:
                continue
            if code in self._symbol_names:
                continue
            if code in self._symbol_name_lookup_attempted:
                continue
            pending.append(code)

        if not pending:
            return

        krx_name_map = self._load_krx_open_api_symbol_names()
        if not krx_name_map:
            if not self._krx_name_hydration_warned:
                logger.warning(
                    "KRX Open API symbol-name hydration unavailable; "
                    "stock names may remain as raw codes"
                )
                self._krx_name_hydration_warned = True
            return

        resolved = 0
        for code in pending:
            name = str(krx_name_map.get(code, "")).strip()
            self._symbol_name_lookup_attempted.add(code)
            if not name or name == code:
                continue
            self._symbol_names[code] = name
            meta = dict(self._symbol_metadata_cache.get(code, {}))
            meta["name"] = name
            self._symbol_metadata_cache[code] = meta
            resolved += 1

        if resolved > 0:
            logger.info(
                "Hydrated missing stock names: resolved=%d pending=%d",
                resolved,
                len(pending),
            )

    def _load_krx_open_api_symbol_names(self) -> dict[str, str]:
        """Load full stock code→name map from KRX Open API daily snapshots."""
        if self.config.asset_class != "stock":
            return {}

        api_key = str(os.environ.get("KRX_API_KEY", "")).strip()
        if not api_key:
            return {}

        try:
            if self._krx_open_api_client is None:
                from shared.llm.config import LLMConfig
                from shared.llm.krx_api_client import KRXOpenAPIClient

                llm_cfg = LLMConfig.from_env()
                if not llm_cfg.krx_api_key:
                    llm_cfg.krx_api_key = api_key
                self._krx_open_api_client = KRXOpenAPIClient(llm_cfg)

            client = self._krx_open_api_client
            target_date = client._get_last_trading_date()
            if (
                self._krx_symbol_name_cache
                and self._krx_symbol_name_cache_date == target_date
            ):
                return self._krx_symbol_name_cache

            names: dict[str, str] = {}
            for market in ("KOSPI", "KOSDAQ"):
                rows = client.get_stock_daily(market=market, base_date=target_date)
                for item in rows:
                    code = str(item.get("ISU_CD", "")).strip()
                    name = str(item.get("ISU_NM", "")).strip()
                    if code and name:
                        names[code] = name

            if names:
                self._krx_symbol_name_cache = names
                self._krx_symbol_name_cache_date = target_date
                logger.info(
                    "Loaded KRX Open API symbol-name map: date=%s symbols=%d",
                    target_date,
                    len(names),
                )

            return self._krx_symbol_name_cache
        except (APIError, NetworkError, OSError, ConnectionError) as e:
            logger.warning("KRX Open API symbol-name map load failed: %s", e)
            return self._krx_symbol_name_cache

    def _update_symbol_cache(self, codes, names, metadata):
        """Update last-seen timestamps and metadata cache."""
        now = datetime.now()
        for code in codes:
            self._symbol_last_seen[code] = now
            code_meta = dict(metadata.get(code, {}))
            code_name = names.get(code)
            if code_name:
                code_meta["name"] = code_name
            if code_meta:
                self._symbol_metadata_cache[code] = code_meta
        self._symbol_names.update(names)
        self._hydrate_missing_symbol_names(set(codes))

    def _get_stable_universe(self) -> set[str]:
        """Filter expired symbols and enforce max universe size."""
        now = datetime.now()
        retention_cutoff = now - timedelta(seconds=self._universe_retention_seconds)
        stable_symbols = set()
        expired = []

        # Filter by retention time
        for code, last_seen in self._symbol_last_seen.items():
            if last_seen >= retention_cutoff:
                stable_symbols.add(code)
            else:
                expired.append(code)

        # Cleanup expired
        for code in expired:
            del self._symbol_last_seen[code]
            self._symbol_metadata_cache.pop(code, None)

        # Always include symbols with open positions — they must stay in
        # the WebSocket subscription to receive price ticks for exit evaluation.
        position_codes: set[str] = set()
        if self._position_tracker:
            position_codes = {p.code for p in self._position_tracker.positions}
            stable_symbols |= position_codes

        # Cap size — protect warm and near-warm symbols from eviction.
        # Near-warm symbols (>=50% warmup progress) have accumulated significant
        # candle data; evicting them wastes minutes of indicator warmup.
        if len(stable_symbols) > self._max_universe_size:
            warm_set: set[str] = set()
            warming_set: set[str] = set()
            if self._indicator_engine:
                for s in stable_symbols:
                    if self._indicator_engine.is_warm(s):
                        warm_set.add(s)
                    elif self._indicator_engine.warmup_progress(s) >= 0.5:
                        warming_set.add(s)
            protected = warm_set | warming_set | position_codes
            cold = stable_symbols - protected
            by_recency = sorted(
                cold,
                key=lambda c: self._symbol_last_seen.get(c, datetime.min),
                reverse=True,
            )
            remaining_slots = self._max_universe_size - len(protected)
            if remaining_slots >= 0:
                stable_symbols = protected | set(by_recency[:remaining_slots])
            else:
                # More protected than max — keep all protected, drop nothing
                stable_symbols = protected

        return stable_symbols

    def _apply_universe_changes(self, stable_symbols: set[str]):
        """Update configuration and data provider with new universe."""
        # Refresh metadata config for all stable symbols
        self.config.symbol_metadata = {
            code: dict(self._symbol_metadata_cache.get(code, {}))
            for code in stable_symbols
        }

        # Ensure names are synced
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

            # Clean up indicator engine state for removed symbols to prevent
            # stale candle data from contaminating indicators on re-entry.
            if removed and self._indicator_engine:
                for code in removed:
                    self._indicator_engine.remove_symbol(code)

            # Safety net: clean up orphan accumulators not in the new universe.
            # Prevents unbounded growth from stale prewarm tasks or dip churn.
            if self._indicator_engine:
                current_set = set(self.config.symbols)
                orphans = self._indicator_engine.cleanup_orphans(current_set)
                if orphans:
                    logger.info(f"Cleaned up {orphans} orphan accumulators")

            if added or removed:
                warm_n = sum(
                    1
                    for s in stable_symbols
                    if self._indicator_engine and self._indicator_engine.is_warm(s)
                )
                warming_n = sum(
                    1
                    for s in stable_symbols
                    if self._indicator_engine
                    and not self._indicator_engine.is_warm(s)
                    and self._indicator_engine.warmup_progress(s) >= 0.5
                )
                logger.info(
                    f"Universe refreshed: {len(stable_symbols)} symbols "
                    f"(+{len(added)} -{len(removed)}, "
                    f"retained {len(stable_symbols) - len(added)}, "
                    f"warm {warm_n}, warming {warming_n})"
                )

        # Invalidate enriched metadata cache after universe changes
        self._invalidate_enriched_metadata_cache()

    def _check_strategy_warnings(self):
        """Warn if strategy prerequisites (like prev_day_volume) are missing."""
        if not self._prev_day_volume_warned and self._strategy_manager:
            has_ovs = "opening_volume_surge" in self._strategy_manager.strategy_names
            if has_ovs:
                has_pvol = any(
                    "prev_day_volume" in meta
                    for meta in self._symbol_metadata_cache.values()
                )
                if not has_pvol:
                    logger.warning(
                        "opening_volume_surge is active but no symbols have "
                        "prev_day_volume metadata — strategy will produce zero signals. "
                        "Check screener metadata pipeline / KRX Open API availability."
                    )
                    self._prev_day_volume_warned = True

    async def _universe_refresh_loop(self) -> None:
        """Periodically refresh symbols from screener or static watchlist."""
        # Static mode: load daily watchlist once, then idle
        if self.config.universe_mode == "static":
            await self._static_universe_refresh()
            return

        # Dynamic mode: original screener-driven refresh
        while self._market_data_running:
            try:
                old_symbols = set(self.config.symbols)
                self._refresh_universe_from_screener()

                # Merge dip candidates into universe so bb_reversion can evaluate them
                self._refresh_dip_candidates()
                if self._dip_candidates:
                    dip_codes = set(self._dip_candidates.keys())
                    missing = dip_codes - set(self.config.symbols)
                    if missing:
                        now = datetime.now()
                        for code in missing:
                            self._symbol_last_seen[code] = now
                            dip_info = self._dip_candidates.get(code, {})
                            meta = {"name": dip_info.get("name", ""), "source": "dip"}
                            self._symbol_metadata_cache[code] = meta
                            if dip_info.get("name"):
                                self._symbol_names[code] = dip_info["name"]
                        self.config.symbols = list(set(self.config.symbols) | missing)
                        if self._data_provider:
                            self._data_provider.symbols = list(self.config.symbols)
                        logger.info(f"Added {len(missing)} dip candidates to universe")

                new_symbols = set(self.config.symbols) - old_symbols

                # Update WebSocket subscriptions to match new universe
                if self._stock_price_feed:
                    self._stock_price_feed.update_symbols(self.config.symbols)

                # Pre-warm new symbols (tracked to catch errors).
                # Cancel any previous prewarm task to prevent stale tasks
                # from creating accumulators for already-evicted symbols.
                if new_symbols and self._indicator_engine and self._kis_client:
                    if self._prewarm_task and not self._prewarm_task.done():
                        self._prewarm_task.cancel()
                    task = asyncio.create_task(
                        self._prewarm_symbols(list(new_symbols)),
                        name="prewarm_symbols",
                    )
                    self._prewarm_task = task
                    self._pending_notify_tasks.add(task)
                    task.add_done_callback(self._on_notify_done)
            except (InfrastructureError, NetworkError, OSError, ConnectionError) as e:
                logger.warning(f"Universe refresh loop error: {e}")
            await asyncio.sleep(self._universe_refresh_interval)

    async def _static_universe_refresh(self) -> None:
        """Load static watchlist once and prewarm all symbols.

        Falls back to dynamic screener mode if the watchlist is unavailable.
        """
        loaded = self._load_static_watchlist()
        if not loaded:
            logger.info("Static watchlist unavailable, switching to dynamic mode.")
            self.config.universe_mode = "dynamic"
            # Re-enter loop in dynamic mode
            while self._market_data_running:
                try:
                    self._refresh_universe_from_screener()
                except (
                    InfrastructureError,
                    NetworkError,
                    OSError,
                    ConnectionError,
                ) as e:
                    logger.warning(f"Dynamic fallback refresh error: {e}")
                await asyncio.sleep(self._universe_refresh_interval)
            return

        # Pre-warm all watchlist symbols
        if self.config.symbols and self._indicator_engine and self._kis_client:
            task = asyncio.create_task(
                self._prewarm_symbols(list(self.config.symbols)),
                name="prewarm_static_symbols",
            )
            self._prewarm_task = task
            self._pending_notify_tasks.add(task)
            task.add_done_callback(self._on_notify_done)

        # In static mode, keep loop alive but sleep long (no refresh needed).
        # This allows graceful cancellation on shutdown.
        while self._market_data_running:
            await asyncio.sleep(300)  # 5-minute heartbeat

    async def _fetch_candles_from_clickhouse(
        self, symbol: str, limit: int = 120
    ) -> list[dict]:
        """Fetch recent candles from ClickHouse for pre-market warmup.

        limit=120 covers all indicator warmup needs:
        SMA(120), BB(20), RSI(14), MACD(26+9), Stochastic(14).

        Stock data is in `market.minute_candles` (from stock_backfill.sh).
        Futures have no usable minute candle table in ClickHouse.
        """
        # Futures: no minute candle data in ClickHouse
        if self.config.asset_class == "futures":
            return []

        try:
            from clickhouse_driver import Client as CHSyncClient

            # Reuse the shared env parsing so the native driver does not
            # accidentally point at the HTTP port (8123).
            ch_cfg = ClickHouseConfig.from_env(
                database=os.getenv("CLICKHOUSE_STOCK_DATABASE", "market")
            )

            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(
                None,
                lambda: CHSyncClient(
                    host=ch_cfg.host,
                    port=ch_cfg.port,
                    user=ch_cfg.user,
                    password=ch_cfg.password,
                    database=ch_cfg.database,
                ).execute(
                    "SELECT code, datetime, open, high, low, close, volume "
                    "FROM minute_candles "
                    "WHERE code = %(code)s "
                    "ORDER BY datetime DESC LIMIT %(limit)s",
                    {"code": symbol, "limit": limit},
                ),
            )
            candles = []
            for row in reversed(rows):  # oldest first
                candles.append(
                    {
                        "datetime": row[1],
                        "open": float(row[2]),
                        "high": float(row[3]),
                        "low": float(row[4]),
                        "close": float(row[5]),
                        "volume": int(row[6]),
                    }
                )
            return candles
        except (
            InfrastructureError,
            OSError,
            ConnectionError,
            ValueError,
            IndexError,
        ) as e:
            logger.debug(f"ClickHouse prewarm failed for {symbol}: {e}")
            return []

    async def _fetch_daily_candles_from_clickhouse(
        self, symbol: str, limit: int = 252
    ) -> list[dict]:
        """Fetch recent daily candles from ClickHouse.

        Used for multi-timeframe strategies that need daily context.

        Args:
            symbol: Stock/futures code
            limit: Number of daily candles (default 252 = ~1 year trading days)

        Returns:
            List of daily candle dicts with keys: date, open, high, low, close, volume
        """
        try:
            from clickhouse_driver import Client as CHSyncClient
            import pandas as pd

            from shared.collector.historical.daily_quality import (
                clean_daily_candle_frame,
                load_daily_quality_config,
                quality_fetch_limit,
            )

            ch_cfg = ClickHouseConfig.from_env(
                database=os.getenv("CLICKHOUSE_STOCK_DATABASE", "market")
            )
            quality_config = load_daily_quality_config()
            fetch_limit = quality_fetch_limit(limit, quality_config)

            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(
                None,
                lambda: CHSyncClient(
                    host=ch_cfg.host,
                    port=ch_cfg.port,
                    user=ch_cfg.user,
                    password=ch_cfg.password,
                    database=ch_cfg.database,
                ).execute(
                    "SELECT "
                    "code, date, "
                    "argMax(open, created_at) AS open, "
                    "argMax(high, created_at) AS high, "
                    "argMax(low, created_at) AS low, "
                    "argMax(close, created_at) AS close, "
                    "argMax(volume, created_at) AS volume "
                    "FROM daily_candles "
                    "WHERE code = %(code)s "
                    "GROUP BY code, date "
                    "ORDER BY date DESC LIMIT %(limit)s",
                    {"code": symbol, "limit": fetch_limit},
                ),
            )
            if not rows:
                return []

            frame = pd.DataFrame(
                rows,
                columns=["code", "date", "open", "high", "low", "close", "volume"],
            )
            frame = clean_daily_candle_frame(
                frame,
                config=quality_config,
                limit=limit,
            )
            candles = []
            for row in frame.itertuples(index=False):
                candles.append(
                    {
                        "date": row.date,
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": int(row.volume),
                    }
                )
            return candles
        except (
            InfrastructureError,
            OSError,
            ConnectionError,
            ValueError,
            IndexError,
        ) as e:
            logger.debug(f"ClickHouse daily candle fetch failed for {symbol}: {e}")
            return []

    async def _prewarm_symbols(self, symbols: list[str]) -> None:
        """Seed indicator engine with historical candles.

        Priority: Redis candle cache → ClickHouse → KIS REST API.
        """
        logger.info(f"Prewarm starting for {len(symbols)} symbols")

        # 1st priority: Redis candle cache (instant, works for all assets)
        redis_hits = await self._load_candle_cache_from_redis()

        ch_hits = 0
        kis_hits = 0
        daily_ch_hits = 0
        for symbol in symbols:
            if self._indicator_engine.is_warm(symbol):
                continue
            # Skip if symbol was evicted during prewarm
            if symbol not in set(self.config.symbols):
                continue
            try:
                # ClickHouse first (no rate limit, faster)
                candles = await self._fetch_candles_from_clickhouse(symbol, limit=120)
                if candles:
                    ch_hits += 1
                elif self._kis_client.is_rate_limited:
                    # Skip KIS REST when rate limiter is in penalty/cooldown
                    logger.debug(f"Prewarm {symbol}: skipping KIS REST (rate limited)")
                    continue
                else:
                    # Fallback to KIS REST
                    candles = await asyncio.wait_for(
                        self._kis_client.get_minute_bars(symbol, count=120),
                        timeout=5.0,
                    )
                    if candles:
                        kis_hits += 1
                    await asyncio.sleep(0.3)  # rate-limit protection
                if candles:
                    self._indicator_engine.seed_candles(symbol, candles)
                    logger.info(f"Prewarm {symbol}: {len(candles)} candles seeded")
                else:
                    logger.debug(f"Prewarm {symbol}: no candles returned")

                # Fetch and seed daily candles from ClickHouse (for multi-timeframe strategies)
                daily_candles = await self._fetch_daily_candles_from_clickhouse(
                    symbol, limit=252
                )
                if daily_candles:
                    daily_ch_hits += 1
                    self._indicator_engine.seed_daily_candles(symbol, daily_candles)
                    logger.info(
                        f"Prewarm {symbol}: {len(daily_candles)} daily candles seeded"
                    )
            except (TimeoutError, Exception) as e:
                logger.warning(f"Prewarm failed for {symbol}: {e}")
        logger.info(
            f"Prewarm complete: {redis_hits} from Redis, "
            f"{ch_hits} from ClickHouse, {kis_hits} from KIS REST, "
            f"{daily_ch_hits} daily candles from ClickHouse"
        )

    def _save_candle_cache_to_redis(self) -> None:
        """Serialize indicator engine candles to Redis for restart recovery."""
        if not self._state_publisher or not self._indicator_engine:
            return
        candle_data: dict[str, list[dict]] = {}
        for symbol, acc in self._indicator_engine._accumulators.items():
            if not acc.candles:
                continue
            candle_data[symbol] = [
                {
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "minute": c.minute,
                }
                for c in acc.candles
            ]
        if candle_data:
            self._state_publisher.publish_candle_cache(candle_data)
            logger.info(
                f"Candle cache saved: {len(candle_data)} symbols, "
                f"{sum(len(v) for v in candle_data.values())} total candles"
            )

    async def _load_candle_cache_from_redis(self) -> int:
        """Load cached candles from Redis to pre-warm indicators."""
        try:
            from shared.streaming.trading_state import TradingStateReader

            reader = TradingStateReader(self.config.asset_class)
            cache = reader.get_candle_cache()
            if not cache:
                return 0
            loaded = 0
            for symbol, candles in cache.items():
                if self._indicator_engine.is_warm(symbol):
                    continue
                self._indicator_engine.seed_candles(symbol, candles)
                loaded += 1
            logger.info(f"Candle cache loaded: {loaded} symbols from Redis")
            return loaded
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.warning(f"Candle cache load failed: {e}")
            return 0

    async def _flush_positions_with_retry(self, max_retries: int = 3) -> bool:
        """Flush positions to Redis with exponential backoff (100ms base, 1s cap)."""
        if not self._position_tracker or not self._state_publisher:
            return False

        positions = list(self._position_tracker.positions)
        if not positions:
            return True  # Nothing to flush

        for attempt in range(max_retries):
            try:
                self._state_publisher.publish_positions_update(positions, throttle=0)
                if attempt > 0:
                    logger.info(
                        f"Redis flush succeeded on attempt {attempt + 1}/{max_retries}"
                    )
                return True

            except (ConnectionError, TimeoutError, OSError) as e:
                # Transient network/connection errors - retry with backoff
                if attempt < max_retries - 1:
                    delay = min(0.1 * (2**attempt), 1.0)
                    logger.warning(
                        f"Redis flush failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay*1000:.0f}ms..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Redis flush failed after {max_retries} attempts: {e}"
                    )
                    return False

            except (ValidationError, TypeError, ValueError, AttributeError) as e:
                # Non-retryable errors (e.g., serialization errors, data validation)
                logger.error(f"Redis flush failed with non-retryable error: {e}")
                return False

        return False

    async def stop(self, timeout: float = 10.0):
        """거래 종료 (타임아웃 포함)

        Args:
            timeout: Maximum time in seconds to wait for graceful shutdown.
                     Cron scripts wait 5s before SIGKILL, so pass timeout=4.0
                     when called from cron contexts for a 1s safety margin.
        """
        self._stop_requested = True
        self._running = False

        if self.state == TradingState.STOPPED:
            return

        try:
            await asyncio.wait_for(self._stop_impl(), timeout=timeout)
        except TimeoutError:
            logger.error(f"Graceful shutdown timed out after {timeout}s, forcing...")
            # Force Redis flush as last resort with retry
            await self._flush_positions_with_retry(max_retries=3)
            self.state = TradingState.STOPPED
            self._running = False

    async def _stop_impl(self):
        """Internal stop implementation."""
        logger.info("Stopping trading...")

        await self._stop_market_data_loop()

        # Shutdown: close intraday positions, persist swing positions
        if self._position_tracker and self._data_provider:
            try:
                data = await self._data_provider.get_data()
                await self._close_intraday_positions(data)

                # Flush remaining open positions to Redis for recovery (with retry)
                if self._position_tracker.position_count > 0:
                    success = await self._flush_positions_with_retry(max_retries=3)
                    if success:
                        logger.info(
                            f"Positions flushed to Redis ({self._position_tracker.position_count} open)"
                        )
                    else:
                        logger.error(
                            f"Failed to flush {self._position_tracker.position_count} positions to Redis after retries"
                        )
            except (InfrastructureError, OSError, ConnectionError) as e:
                logger.error(f"Error during position shutdown: {e}")

        # Stop auto-flush task and flush any pending batched positions to DB
        if self._position_tracker:
            try:
                await self._position_tracker.stop_auto_flush()
                logger.info(
                    "Position tracker auto-flush stopped and final batch flushed"
                )
            except (InfrastructureError, OSError, ConnectionError) as e:
                logger.error(f"Error stopping position tracker auto-flush: {e}")

        # Save candle cache for fast restart recovery
        try:
            self._save_candle_cache_to_redis()
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.warning(f"Candle cache save on shutdown failed: {e}")

        # Final flush of shadow-logger buffers to ClickHouse (Phase 2).
        # Must run before _cleanup_resources() so the CH client is still valid.
        await self._shadow_loggers_final_flush()

        # Stop KIS API error-rate tracker (§10.3-A) — cancels publish loop
        # and writes the final rate to Redis before cleanup.
        try:
            from shared.kis.error_rate import KISApiErrorRateTracker

            await KISApiErrorRateTracker.get_instance().stop()
        except Exception as e:
            logger.warning(
                "kis_api_error_rate tracker stop failed (%s) — proceeding with cleanup",
                e,
            )

        await self._cleanup_resources()

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

    async def _close_intraday_positions(self, data):
        """Force close non-swing positions at EOD.

        Policy (CLAUDE.md):
        - asset_class='stock': EOD 전량 청산 금지. 전략 시그널 기반 청산만 허용.
          → no-op.
        - asset_class='futures': RL 전략은 자체 EOD 안전장치(rl_mppo_exit)를 가지므로
          여기서는 그 외 legacy intraday 전략만 청산.
        """
        if self.config.asset_class == "stock":
            logger.debug(
                "EOD intraday force-close skipped: asset_class=stock policy forbids it"
            )
            return

        intraday_positions = [
            pos
            for pos in self._position_tracker.positions
            if pos.strategy not in self.SWING_STRATEGIES
            and not pos.strategy.startswith("rl_")
        ]
        for pos in intraday_positions:
            price_data = data.get(pos.code, {})
            if isinstance(price_data, dict):
                price = price_data.get("close") or pos.current_price
            else:
                price = price_data or pos.current_price

            closed = self._position_tracker.close_position(
                pos.id, price, reason="EOD_CLOSE"
            )
            if closed:
                pnl = closed.unrealized_pnl
                self.total_pnl += pnl
                await self._record_risk_realized_pnl(pnl)
                if self._state_publisher:
                    self._state_publisher.publish_position_closed(closed)
                    self._record_running_totals(closed)
        self._sync_open_positions_metric()

    async def _cleanup_resources(self):
        """Shutdown pipelines and release components."""
        # Await pending fire-and-forget tasks before teardown
        if self._pending_notify_tasks:
            await asyncio.gather(*self._pending_notify_tasks, return_exceptions=True)
            self._pending_notify_tasks.clear()

        if self._tick_stream_publisher is not None:
            try:
                self._tick_stream_publisher.close()
            except (InfrastructureError, OSError, ConnectionError) as e:
                logger.warning(f"TickStreamPublisher cleanup failed: {e}")
            self._tick_stream_publisher = None

        if self.pipeline:
            await self.pipeline.stop()
            self.pipeline = None

        if self._order_executor is not None:
            try:
                await self._order_executor.cleanup()
            except (
                InfrastructureError,
                APIError,
                NetworkError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"OrderExecutor cleanup failed: {e}")
            self._order_executor = None

        if self._mock_mirror is not None:
            try:
                await self._mock_mirror.cleanup()
            except (
                APIError,
                NetworkError,
                InfrastructureError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"MockAccountMirror cleanup failed: {e}")
            self._mock_mirror = None

        self._data_provider = None
        self._strategy_manager = None
        self._position_tracker = None
        self._indicator_engine = None
        self._indicator_resolver = None

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
            await self._sleep_unless_stop_requested(wait_seconds)
            if self._stop_requested:
                return

        # 거래 시작
        await self.start()
        self.session_count += 1

        # 장 종료까지 대기
        close_dt = datetime.combine(today, close_time)
        now = datetime.now()

        if now < close_dt:
            wait_seconds = (close_dt - now).total_seconds()
            logger.info(f"Trading until market close: {wait_seconds:.0f}s")

            with contextlib.suppress(asyncio.CancelledError):
                await self._sleep_unless_stop_requested(wait_seconds)

        # 거래 종료
        await self.stop()

    async def _sleep_unless_stop_requested(self, wait_seconds: float) -> None:
        """Sleep in short slices so shutdown signals can interrupt long waits."""
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while not self._stop_requested:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 1.0))

    async def run(self):
        """데몬 모드 실행 (매일 반복)"""
        logger.info("Starting trading orchestrator (daemon mode)")
        self._running = True
        self._stop_requested = False

        await self._notify(
            f"🤖 Trading Orchestrator Started\n"
            f"Mode: {'Paper' if self.config.paper_trading else 'Live'}\n"
            f"Asset: {self.config.asset_class}\n"
            f"Strategy: {self.config.strategy_name}"
        )

        while self._running:
            try:
                await self.run_session()
                if self._stop_requested or not self._running:
                    break

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
                await self._sleep_unless_stop_requested(wait_seconds)

            except asyncio.CancelledError:
                logger.info("Orchestrator cancelled")
                break
            except (InfrastructureError, NetworkError, APIError, ValidationError) as e:
                logger.error(f"Session error: {e}")
                await self._notify(f"⚠️ Error: {e}")
                await asyncio.sleep(self.config.error_retry_delay_seconds)
            except Exception as e:
                logger.error(
                    f"Unexpected session error (not in custom hierarchy): {type(e).__name__}: {e}",
                    exc_info=True,
                )
                await self._notify(f"⚠️ Unexpected error: {type(e).__name__}: {e}")
                await asyncio.sleep(self.config.error_retry_delay_seconds)

        await self.stop()

    def _load_pipeline_config(self) -> PipelineConfig | None:
        """Load pipeline configuration from pipeline.yaml.

        Returns ``None`` on any parse/validation failure so TradingPipeline falls
        back to its built-in defaults.
        """
        try:
            from shared.config.schema import PipelineConfig

            raw = ConfigLoader.load("pipeline.yaml")
            raw_pipeline = raw.get("pipeline", raw) if isinstance(raw, dict) else raw
            if not isinstance(raw_pipeline, dict):
                raise ValueError("pipeline config must be a mapping")
            return PipelineConfig.model_validate(raw_pipeline)
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            ValueError,
            TypeError,
            ValidationError,
        ) as e:
            logger.warning(f"Failed to load pipeline config (using defaults): {e}")
            return None

    def _create_pipeline(self) -> TradingPipeline:
        """파이프라인 생성 with real handlers"""
        return TradingPipeline(
            regime_handler=self._handle_regime,
            entry_handler=self._handle_entry,
            monitoring_handler=self._handle_monitoring,
            exit_handler=self._handle_exit,
            config=self._load_pipeline_config(),
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
            except (
                NetworkError,
                WebSocketDisconnectError,
                APIError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"Stock WebSocket feed start failed: {e}")
                self._stock_price_feed = None
        if self._futures_price_feed:
            try:
                feed_symbols = list(self.config.symbols or [])
                self._futures_price_feed.update_symbols(
                    feed_symbols,
                    auxiliary_symbols=self._futures_slippage_aux_symbols,
                )
                await self._futures_price_feed.start()
                logger.info(
                    f"Futures WebSocket feed started, "
                    f"{self._futures_price_feed.symbol_count} symbols subscribed "
                    f"(trade={len(feed_symbols)}, aux={len(self._futures_slippage_aux_symbols)})"
                )
            except (
                NetworkError,
                WebSocketDisconnectError,
                APIError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"Futures WebSocket feed start failed: {e}")
                self._futures_price_feed = None

        if self._data_provider and self._data_provider_failover_enabled:
            try:
                await self._data_provider.start_background_tasks()
            except Exception as e:
                logger.warning(
                    f"Failed to start data provider failover monitoring: {e}"
                )

        # Pre-warm indicators FIRST (exclusive API access, no rate conflicts)
        if self._indicator_engine and self._kis_client and self.config.symbols:
            await self._prewarm_symbols(self.config.symbols)

        # Initial price refresh (some may be rate-limited; the data loop will catch up)
        try:
            data = await self._refresh_market_data_once()
            async with self._market_data_lock:
                self._market_data_snapshot = data
                self._market_data_updated_at = datetime.now()
        except (NetworkError, APIError, OSError, ConnectionError) as e:
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

        if self._data_provider:
            try:
                await self._data_provider.stop_background_tasks()
            except Exception as e:
                logger.warning(f"Data provider background task stop error: {e}")

        # Stop WebSocket price feed
        if self._stock_price_feed:
            try:
                await self._stock_price_feed.stop()
            except (
                NetworkError,
                WebSocketDisconnectError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"Stock price feed stop error: {e}")
        if self._futures_price_feed:
            try:
                await self._futures_price_feed.stop()
            except (
                NetworkError,
                WebSocketDisconnectError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"Futures price feed stop error: {e}")

        if self._universe_refresh_task:
            self._universe_refresh_task.cancel()
            await asyncio.gather(self._universe_refresh_task, return_exceptions=True)
            self._universe_refresh_task = None
        if self._market_data_task:
            self._market_data_task.cancel()
            await asyncio.gather(self._market_data_task, return_exceptions=True)
            self._market_data_task = None

        # Stop LLM context publisher task
        if self._llm_context_task:
            self._llm_context_task.cancel()
            await asyncio.gather(self._llm_context_task, return_exceptions=True)
            self._llm_context_task = None

        # Stop kill-switch consumer task (Phase 0.2-c)
        if self._kill_switch_consumer_task:
            self._kill_switch_consumer_task.cancel()
            await asyncio.gather(
                self._kill_switch_consumer_task, return_exceptions=True
            )
            self._kill_switch_consumer_task = None

        # Stop shadow-loggers flush task (Phase 2).
        # The final buffer drain happens in _shadow_loggers_final_flush()
        # called from _stop_impl() after this method returns.
        if self._shadow_loggers_flush_task:
            self._shadow_loggers_flush_task.cancel()
            await asyncio.gather(
                self._shadow_loggers_flush_task, return_exceptions=True
            )
            self._shadow_loggers_flush_task = None

    # ------------------------------------------------------------------
    # Kill-switch consumer loop (Phase 0.2-c)
    # ------------------------------------------------------------------

    async def _start_kill_switch_consumer(self) -> None:
        """Start the background kill-switch sentinel polling loop.

        Loads config from ``kill_switch_consumer`` section of
        ``config/kill_switch.yaml`` and spawns :meth:`_kill_switch_consumer_loop`
        as an asyncio task.

        On startup the loop optionally records the current tip of the
        ``kill_switch:events`` stream so that a sentinel written *before* this
        process started does NOT trigger a flatten (``ignore_pre_startup_events``).
        """
        try:
            from services.kill_switch.config import KillSwitchConsumerConfig

            ks_cfg = KillSwitchConsumerConfig.from_yaml()
        except (InvalidConfigError, MissingConfigError, OSError) as e:
            logger.warning(
                "kill_switch_consumer config not loaded (%s) — using defaults", e
            )
            from services.kill_switch.config import KillSwitchConsumerConfig

            ks_cfg = KillSwitchConsumerConfig()
        except Exception as e:
            logger.error(
                "Unexpected error loading kill_switch_consumer config: %s",
                e,
                exc_info=True,
            )
            from services.kill_switch.config import KillSwitchConsumerConfig

            ks_cfg = KillSwitchConsumerConfig()

        # Initialise last-seen event id at the current stream tip so a
        # pre-existing event does not trigger flatten on restart.
        if ks_cfg.ignore_pre_startup_events:
            try:
                from shared.streaming.client import RedisClient

                redis_client = RedisClient.get_client()
                entries = redis_client.xrevrange(ks_cfg.events_stream, count=1)
                if entries:
                    self._ks_last_seen_event_id = entries[0][0]
                    logger.info(
                        "kill_switch consumer startup: last-seen event id=%s "
                        "(pre-startup events ignored)",
                        self._ks_last_seen_event_id,
                    )
                else:
                    # Stream empty; initialise to sentinel "0-0" so any future
                    # event id will compare as newer.
                    self._ks_last_seen_event_id = "0-0"
                    logger.info(
                        "kill_switch consumer startup: events stream empty; "
                        "last-seen initialised to 0-0"
                    )
            except (InfrastructureError, OSError, ConnectionError) as e:
                logger.warning(
                    "kill_switch consumer: failed to read startup event id (%s); "
                    "last-seen remains None — pre-startup events WILL trigger flatten",
                    e,
                )
                self._ks_last_seen_event_id = None
        else:
            # Deliberately include pre-startup events (testing / forced re-check).
            self._ks_last_seen_event_id = None

        self._kill_switch_consumer_task = asyncio.create_task(
            self._kill_switch_consumer_loop(ks_cfg),
            name="kill_switch_consumer_loop",
        )
        logger.info(
            "kill_switch consumer loop started (poll=%.1fs, sentinel=%s)",
            ks_cfg.poll_interval_seconds,
            ks_cfg.sentinel_key,
        )

    async def _kill_switch_consumer_loop(self, ks_cfg: Any) -> None:  # noqa: ANN401
        """Poll Redis for the kill-switch sentinel and flatten positions on detection.

        Idempotency design:
        - Reads the latest entry id from ``ks_cfg.events_stream``.
        - Compares it with ``self._ks_last_seen_event_id`` (set at startup to
          the stream tip, so pre-startup events are skipped when
          ``ignore_pre_startup_events=True``).
        - Only if a *new* event id is found, in this order:
            1. Calls :meth:`_kill_switch_flatten_all` which iterates open
               positions and submits broker exits via
               :meth:`_submit_exit_order` (paper VirtualBroker or live
               OrderExecutor — handles LONG→SELL and SHORT→BUY-to-cover).
               Note: this does NOT call ``PositionTracker.close_all()``
               directly because that helper has no broker integration.
            2. Updates ``_ks_last_seen_event_id`` *before* DEL so that if
               the DEL fails we still won't re-trigger on the next tick
               (DEL failure is acceptable; the sentinel TTL will reap it).
            3. DELs the sentinel key (best-effort cleanup within TTL window).
            4. Sends a Telegram alert.
        - Redis errors are logged and silently retried on the next tick;
          they do NOT crash the orchestrator. ``redis.exceptions.ConnectionError``
          is also caught explicitly because it does NOT inherit from the
          builtin ``ConnectionError``.

        Args:
            ks_cfg: :class:`services.kill_switch.config.KillSwitchConsumerConfig`
                instance supplying poll_interval_seconds, sentinel_key, and
                events_stream.
        """
        logger.info("kill_switch consumer loop running")

        while self._market_data_running:
            try:
                await asyncio.sleep(ks_cfg.poll_interval_seconds)

                from shared.streaming.client import RedisClient

                redis_client = RedisClient.get_client()

                # Fast path: check sentinel key presence first.
                sentinel_val = redis_client.get(ks_cfg.sentinel_key)
                if not sentinel_val:
                    # No sentinel — nothing to do on this tick.
                    continue

                # Sentinel present.  Now check the events stream to enforce
                # the idempotency / pre-startup filter.
                entries = redis_client.xrevrange(ks_cfg.events_stream, count=1)
                if not entries:
                    # Stream empty but sentinel exists — edge case (sentinel
                    # written without a stream entry, e.g. in tests).  Treat
                    # the sentinel itself as a trigger if last-seen is None.
                    if self._ks_last_seen_event_id is not None:
                        logger.debug(
                            "kill_switch sentinel present but events stream empty "
                            "and last-seen is set — skipping (pre-startup guard)"
                        )
                        continue
                    latest_event_id = None
                else:
                    latest_event_id = entries[0][0]

                # Idempotency / pre-startup check.
                if latest_event_id is not None and (
                    self._ks_last_seen_event_id is not None
                    and latest_event_id <= self._ks_last_seen_event_id
                ):
                    # No new event since last time we handled (or since startup).
                    logger.debug(
                        "kill_switch sentinel present but no new event "
                        "(latest=%s, last_seen=%s) — skipping",
                        latest_event_id,
                        self._ks_last_seen_event_id,
                    )
                    continue

                # --- New event detected: execute flatten ---
                logger.critical(
                    "KILL-SWITCH CONSUMER TRIGGERED: sentinel=%s event_id=%s — "
                    "flattening all open positions",
                    ks_cfg.sentinel_key,
                    latest_event_id,
                )

                flat_count = await self._kill_switch_flatten_all()

                # Update last-seen *before* DEL so that if DEL fails we still
                # won't re-trigger on the next tick.
                self._ks_last_seen_event_id = latest_event_id

                # DEL sentinel key (best-effort cleanup within TTL window).
                try:
                    redis_client.delete(ks_cfg.sentinel_key)
                    logger.info(
                        "kill_switch consumer: sentinel key deleted (key=%s)",
                        ks_cfg.sentinel_key,
                    )
                except (InfrastructureError, OSError, ConnectionError) as del_err:
                    logger.warning(
                        "kill_switch consumer: failed to DEL sentinel key: %s",
                        del_err,
                    )

                # Telegram alert (fire-and-forget, same pattern as existing notifications).
                await self._notify(
                    f"KILL-SWITCH FLATTEN EXECUTED\n"
                    f"Asset: {self.config.asset_class}\n"
                    f"Positions flattened: {flat_count}\n"
                    f"Event id: {latest_event_id}\n"
                    f"Sentinel: {sentinel_val}"
                )

            except asyncio.CancelledError:
                logger.info("kill_switch consumer loop cancelled")
                break
            except (InfrastructureError, OSError, ConnectionError) as e:
                # Redis transient error — log and retry on next tick.
                logger.warning(
                    "kill_switch consumer: Redis error (%s) — retrying on next tick",
                    e,
                )
            except Exception as e:
                # `redis.exceptions.ConnectionError` does NOT inherit from the
                # builtin `ConnectionError`, so we catch it here by name and
                # downgrade to a warning instead of treating it as an unexpected
                # crash. Other unexpected exceptions still log at ERROR with
                # full traceback so operators can investigate.
                if e.__class__.__module__.startswith("redis"):
                    logger.warning(
                        "kill_switch consumer: redis-client error (%s.%s: %s) — "
                        "retrying on next tick",
                        e.__class__.__module__,
                        e.__class__.__name__,
                        e,
                    )
                else:
                    logger.error(
                        "kill_switch consumer: unexpected error (%s) — "
                        "retrying on next tick",
                        e,
                        exc_info=True,
                    )

        logger.info("kill_switch consumer loop exited")

    async def _kill_switch_flatten_all(self) -> int:
        """Submit market exit orders for every open position and update tracking.

        This is the execution side of the kill-switch consumer. It mirrors the
        logic used in :meth:`_execute_exit` / :meth:`_process_filled_exit` but
        operates on ALL open positions simultaneously without requiring an
        :class:`~shared.models.signal.ExitSignal` from the strategy pipeline.

        Handles both LONG (SELL) and SHORT (BUY-to-cover) positions.

        Returns:
            Number of positions for which exit orders were submitted (or mock-
            filled if no broker is configured).
        """
        if not self._position_tracker:
            logger.warning(
                "kill_switch flatten_all: no position tracker — cannot submit orders"
            )
            return 0

        async with self._market_data_lock:
            market_data = dict(self._market_data_snapshot)

        positions_snapshot = list(self._position_tracker.positions)
        if not positions_snapshot:
            logger.info("kill_switch flatten_all: no open positions")
            return 0

        flat_count = 0
        for position in positions_snapshot:
            # Determine exit price from latest market snapshot.
            price_data = market_data.get(position.code, {})
            if isinstance(price_data, dict):
                exit_price = float(price_data.get("close") or position.current_price)
            elif price_data:
                exit_price = float(price_data)
            else:
                exit_price = float(position.current_price)

            if exit_price <= 0:
                logger.warning(
                    "kill_switch flatten_all: %s — invalid price %.2f, "
                    "using last known price %.2f",
                    position.code,
                    exit_price,
                    position.current_price,
                )
                exit_price = float(position.current_price) or 1.0

            # SHORT position → BUY to cover; LONG position → SELL.
            close_is_buy = position.side == PositionSide.SHORT

            try:
                is_filled, fill_price = await self._submit_exit_order(
                    position.code,
                    close_is_buy,
                    position.quantity,
                    exit_price,
                )
            except Exception as exc:
                logger.error(
                    "kill_switch flatten_all: order submission failed for %s: %s",
                    position.code,
                    exc,
                    exc_info=True,
                )
                # PHANTOM-RISK fallback: tracker-side close prevents the local
                # state from showing a stale position, but if the broker truly
                # rejected the exit the broker may still hold the position
                # open — creating a tracker-vs-broker mismatch ("phantom").
                # This is a deliberate trade-off: in an emergency we prefer a
                # clean tracker over a dangling local entry, on the assumption
                # that the operator will reconcile via the daily Edge Review
                # script (`scripts/analysis/recover_positions.py`) and the
                # critical-level alert below. If you're in this branch on
                # live, MANUALLY VERIFY the broker side immediately.
                is_filled, fill_price = True, exit_price

            if is_filled:
                closed = self._position_tracker.close_position(
                    position_id=position.id,
                    exit_price=fill_price,
                    reason="KILL_SWITCH",
                )
                if closed:
                    flat_count += 1
                    pnl = getattr(closed, "unrealized_pnl", 0.0) or 0.0
                    self.total_pnl += pnl
                    await self._record_risk_realized_pnl(pnl)
                    self.total_trades += 1
                    if self._state_publisher:
                        self._state_publisher.publish_position_closed(closed)
                        self._record_running_totals(closed)
                    strategy = getattr(closed, "strategy", "") or ""
                    asyncio.create_task(
                        self._persist_closed_position(closed, strategy),
                        name=f"ks_persist_{getattr(closed, 'id', 'x')[:8]}",
                    )
                    logger.info(
                        "kill_switch flatten_all: closed %s %s qty=%d @ %.4f "
                        "(side=%s close_is_buy=%s pnl=%+.0f)",
                        position.code,
                        position.id[:8],
                        position.quantity,
                        fill_price,
                        position.side.value,
                        close_is_buy,
                        pnl,
                    )
            else:
                logger.error(
                    "kill_switch flatten_all: exit order NOT filled for %s — "
                    "position may still be open; operator verification required",
                    position.code,
                )

        self._sync_open_positions_metric()
        logger.critical(
            "kill_switch flatten_all: complete — %d/%d positions flattened",
            flat_count,
            len(positions_snapshot),
        )
        return flat_count

    async def _start_llm_context_publisher(self) -> None:
        """Start LLM context publisher background task."""
        if not self._llm_context_publisher:
            return

        try:
            # Load publisher config
            llm_yaml = ConfigLoader.load("llm.yaml")
            publisher_config = llm_yaml.get("market_context_publisher", {})

            run_on_startup = publisher_config.get("run_on_startup", True)
            interval_minutes = publisher_config.get("analysis_interval_minutes", 60)

            # Run initial analysis on startup if configured
            if run_on_startup:
                logger.info("Running initial LLM market analysis on startup...")
                try:
                    market_context = await self._llm_context_publisher.run_analysis()
                    if market_context:
                        self._llm_context_publisher.publish_to_redis(market_context)
                        logger.info(
                            f"Initial LLM market context published: regime={market_context.regime}, "
                            f"confidence={market_context.confidence:.2f}"
                        )
                except Exception as e:
                    logger.warning(f"Initial LLM analysis failed: {e}", exc_info=True)

            # Start periodic refresh task
            self._llm_context_task = asyncio.create_task(
                self._llm_context_publisher_loop(interval_minutes),
                name="llm_context_publisher_loop",
            )
            logger.info(
                f"LLM context publisher task started (interval={interval_minutes} min)"
            )

        except (InvalidConfigError, MissingConfigError, OSError, yaml.YAMLError) as e:
            logger.warning(f"LLM context publisher start failed: {e}")

    async def _llm_context_publisher_loop(self, interval_minutes: float) -> None:
        """Background loop for periodic LLM market analysis.

        Args:
            interval_minutes: Interval between analysis runs in minutes
        """
        interval_seconds = interval_minutes * 60
        logger.info(
            f"LLM context publisher loop started (interval={interval_minutes} min)"
        )

        while True:
            try:
                await asyncio.sleep(interval_seconds)

                # Run analysis
                market_context = await self._llm_context_publisher.run_analysis()
                if market_context:
                    self._llm_context_publisher.publish_to_redis(market_context)
                    logger.info(
                        f"LLM market context updated: regime={market_context.regime}, "
                        f"confidence={market_context.confidence:.2f}"
                    )
                else:
                    logger.debug(
                        "LLM analysis returned None (analysis may have failed)"
                    )

            except asyncio.CancelledError:
                logger.info("LLM context publisher loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in LLM context publisher loop: {e}", exc_info=True)
                # Continue loop despite errors (fire-and-forget pattern)
                await asyncio.sleep(60)  # Wait 1 minute before retry on error

    # ------------------------------------------------------------------
    # Shadow-loggers periodic flush (Phase 2 — LLM-primary RL minimization)
    # ------------------------------------------------------------------

    async def _start_shadow_loggers_flush(self) -> None:
        """Start the background periodic flush task for shadow-mode loggers.

        Loads ``config/shadow_loggers.yaml`` for ``flush_interval_seconds``.
        Builds a reusable ClickHouse sync client (one per process, reused
        across flush cycles to avoid connection overhead).  Spawns
        :meth:`_shadow_loggers_flush_loop` as an asyncio task.

        If the config file is absent or malformed, falls back to the default
        60-second interval with a WARNING rather than crashing the orchestrator.
        """
        try:
            sl_yaml = ConfigLoader.load("shadow_loggers.yaml")
            sl_cfg = sl_yaml.get("shadow_loggers", {})
        except (InvalidConfigError, MissingConfigError, OSError) as e:
            logger.warning("shadow_loggers config not loaded (%s) — using defaults", e)
            sl_cfg = {}

        flush_interval = float(sl_cfg.get("flush_interval_seconds", 60.0))
        # Cache final_flush_on_stop at startup so shutdown does NOT re-read
        # the YAML (file may be unreachable mid-shutdown, and re-reading is
        # wasted I/O when the value was already known at start time).
        self._shadow_loggers_final_flush_enabled = bool(
            sl_cfg.get("final_flush_on_stop", True)
        )

        # Build a reusable ClickHouse client (mirroring the pattern used in
        # _fetch_candles_from_clickhouse — Native driver, DB=kospi).
        try:
            from clickhouse_driver import Client as CHSyncClient

            ch_cfg = ClickHouseConfig.from_env(
                database=os.getenv("CLICKHOUSE_FUTURES_DATABASE", "kospi")
            )
            self._shadow_loggers_ch_client = CHSyncClient(
                host=ch_cfg.host,
                port=ch_cfg.port,
                user=ch_cfg.user,
                password=ch_cfg.password,
                database=ch_cfg.database,
            )
        except Exception as e:
            logger.warning(
                "shadow_loggers: ClickHouse client init failed (%s) — "
                "flush loop will not start; shadow data will remain in buffer",
                e,
                exc_info=True,
            )
            return

        self._shadow_loggers_flush_task = asyncio.create_task(
            self._shadow_loggers_flush_loop(flush_interval),
            name="shadow_loggers_flush_loop",
        )
        logger.info(
            "shadow_loggers flush loop started (interval=%.1fs)", flush_interval
        )

    async def _shadow_loggers_flush_loop(self, interval_seconds: float) -> None:
        """Periodically drain both shadow-logger in-memory buffers to ClickHouse.

        Called by :meth:`_start_shadow_loggers_flush`.  Runs until cancelled
        by :meth:`_stop_market_data_loop`.  The final in-flight buffer drain
        is handled separately by :meth:`_shadow_loggers_final_flush` which
        runs after this task is cancelled (in :meth:`_stop_impl`).

        **Independence invariant**: each logger's flush runs in its own
        try/except block so a failure in one does NOT skip the other on
        the same tick. Without this, an `rl_shadow` flush exception would
        silently leave the LLM veto buffer growing until shutdown.

        Args:
            interval_seconds: How often to flush (loaded from
                ``config/shadow_loggers.yaml`` ``flush_interval_seconds``).
        """
        from shared.strategy import llm_veto_logger as veto_mod
        from shared.strategy import rl_shadow_logger as rl_mod
        from shared.strategy.llm_veto_logger import flush_llm_veto_events
        from shared.strategy.rl_shadow_logger import flush_rl_shadow_predictions

        logger.info(
            "shadow_loggers flush loop running (interval=%.1fs)", interval_seconds
        )

        while True:
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("shadow_loggers flush loop cancelled")
                break

            # Independent try/except per logger so one failure does not
            # cascade into skipping the other (best-effort + observable).
            rl_count = 0
            veto_count = 0

            try:
                rl_count = await flush_rl_shadow_predictions(
                    self._shadow_loggers_ch_client
                )
            except asyncio.CancelledError:
                logger.info("shadow_loggers flush loop cancelled mid-rl-flush")
                break
            except Exception as e:
                logger.warning(
                    "shadow_loggers rl_shadow flush error (%s) — retrying on next tick",
                    e,
                    exc_info=True,
                )

            try:
                veto_count = await flush_llm_veto_events(self._shadow_loggers_ch_client)
            except asyncio.CancelledError:
                logger.info("shadow_loggers flush loop cancelled mid-veto-flush")
                break
            except Exception as e:
                logger.warning(
                    "shadow_loggers llm_veto flush error (%s) — retrying on next tick",
                    e,
                    exc_info=True,
                )

            # Publish per-logger health to Prometheus (always, not just on
            # success) so a stuck flush loop is visible via the
            # last_flush_unix gauge staleness alert.
            now_unix = time.time()
            try:
                rl_dropped_batches, rl_dropped_rows = rl_mod.dropped_counts()
                self._metrics.record_shadow_logger_state(
                    logger="rl_shadow",
                    pending_rows=rl_mod.pending_count(),
                    dropped_batches=rl_dropped_batches,
                    dropped_rows=rl_dropped_rows,
                    last_flush_rows=rl_count,
                    last_flush_unix=now_unix,
                )
                veto_dropped_batches, veto_dropped_rows = veto_mod.dropped_counts()
                self._metrics.record_shadow_logger_state(
                    logger="llm_veto",
                    pending_rows=veto_mod.pending_count(),
                    dropped_batches=veto_dropped_batches,
                    dropped_rows=veto_dropped_rows,
                    last_flush_rows=veto_count,
                    last_flush_unix=now_unix,
                )
            except Exception as e:
                # Metric publishing is best-effort — never let it kill the
                # flush loop.
                logger.debug("shadow_loggers metric publish failed: %s", e)

            if rl_count or veto_count:
                logger.info(
                    "shadow_loggers flush: rl_shadow=%d veto=%d rows",
                    rl_count,
                    veto_count,
                )
            else:
                logger.debug(
                    "shadow_loggers flush: no pending rows (rl_shadow=0 veto=0)"
                )

    async def _shadow_loggers_final_flush(self) -> None:
        """Drain remaining shadow-logger buffer rows to ClickHouse on shutdown.

        Called from :meth:`_stop_impl` **after** the periodic flush task is
        cancelled by :meth:`_stop_market_data_loop`.  Respects the cached
        ``_shadow_loggers_final_flush_enabled`` flag (set at startup from
        ``config/shadow_loggers.yaml::final_flush_on_stop``); if the flag is
        false or the CH client was never initialised, this is a no-op.

        **Independence invariant**: the rl_shadow and llm_veto final
        flushes run in independent try/except blocks so a failure in one
        does NOT lose the other's buffer at shutdown.
        """
        if not getattr(self, "_shadow_loggers_final_flush_enabled", True):
            logger.debug(
                "shadow_loggers final flush skipped (final_flush_on_stop=false)"
            )
            return

        if self._shadow_loggers_ch_client is None:
            logger.debug(
                "shadow_loggers final flush skipped (CH client not initialised)"
            )
            return

        rl_count = 0
        veto_count = 0
        try:
            from shared.strategy.rl_shadow_logger import flush_rl_shadow_predictions

            try:
                rl_count = await flush_rl_shadow_predictions(
                    self._shadow_loggers_ch_client
                )
            except Exception as e:
                logger.warning(
                    "shadow_loggers final flush rl_shadow failed (%s) — "
                    "some rl_shadow rows may be lost",
                    e,
                    exc_info=True,
                )

            from shared.strategy.llm_veto_logger import flush_llm_veto_events

            try:
                veto_count = await flush_llm_veto_events(self._shadow_loggers_ch_client)
            except Exception as e:
                logger.warning(
                    "shadow_loggers final flush llm_veto failed (%s) — "
                    "some veto rows may be lost",
                    e,
                    exc_info=True,
                )

            logger.info(
                "shadow_loggers final flush on stop: rl_shadow=%d veto=%d rows",
                rl_count,
                veto_count,
            )
        finally:
            # Close the CH client cleanly (mirrors the disconnect pattern at
            # _fetch_candles_from_clickhouse) so socket/connection resources
            # are released before resource cleanup.
            client = self._shadow_loggers_ch_client
            self._shadow_loggers_ch_client = None
            if client is not None:
                try:
                    client.disconnect()
                except Exception as e:
                    logger.debug(
                        "shadow_loggers final flush: CH client disconnect error (%s) — ignoring",
                        e,
                    )

    async def _market_data_loop(self, interval: float) -> None:
        logger.info(
            f"Market data loop started (interval={interval}s, "
            f"symbols={len(self._get_market_symbols())})"
        )
        next_tick = time.monotonic()
        tick_count = 0
        diag_interval = 30  # log diagnostics every 30 ticks (~60s at 2s interval)

        while self._market_data_running:
            try:
                t0 = time.monotonic()
                data = await self._refresh_market_data_once()
                fetch_ms = (time.monotonic() - t0) * 1000
                tick_count += 1

                self._log_fetch_diagnostics(tick_count, diag_interval, data, fetch_ms)

                if data:
                    await self._update_market_snapshot(data)
                    self._feed_indicators(data)
                    self._log_indicator_diagnostics(tick_count, diag_interval, data)

                # Update risk manager with current positions
                await self._update_risk_state(tick_count, diag_interval)

                self._record_market_metrics()

            except (
                NetworkError,
                APIError,
                InfrastructureError,
                OSError,
                ConnectionError,
            ) as e:
                logger.warning(f"Market data refresh failed: {e}")

            next_tick += interval
            sleep_time = next_tick - time.monotonic()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # Yield to event loop even when behind schedule
                await asyncio.sleep(0)
                if -sleep_time > interval * 3:
                    next_tick = time.monotonic()

        logger.info("Market data loop stopped")

    def _log_fetch_diagnostics(self, tick_count, diag_interval, data, fetch_ms):
        """Log initial and periodic fetch statistics."""
        if tick_count <= 3 or tick_count % diag_interval == 0:
            n_syms = len(data) if data else 0
            logger.info(
                f"[tick {tick_count}] fetched {n_syms} symbols " f"in {fetch_ms:.0f}ms"
            )

    async def _update_market_snapshot(self, data):
        """Update shared market data state with lock."""
        async with self._market_data_lock:
            self._market_data_snapshot = data
            self._market_data_updated_at = datetime.now()

    def _feed_indicators(self, data):
        """Feed ticks to indicator engine.

        No-op when WebSocket callback feeds indicators directly
        (stock and futures both use per-tick callbacks now).
        """
        if not self._indicator_engine:
            return
        if self._stock_price_feed or self._futures_price_feed:
            return
        # Fallback: non-WebSocket data sources (if any future use)
        now_ts = datetime.now()
        for sym, sym_data in data.items():
            if isinstance(sym_data, dict):
                if sym not in self._indicator_engine._last_cumulative_volume:
                    raw_vol = float(sym_data.get("volume", 0))
                    if raw_vol > 0:
                        self._indicator_engine.set_volume_baseline(sym, raw_vol)
                self._indicator_engine.on_tick(sym, sym_data, now_ts)

    def _log_indicator_diagnostics(self, tick_count, diag_interval, data):
        """Periodically log indicator engine status."""
        if tick_count % diag_interval == 0 and self._indicator_engine:
            warm_count = sum(
                1
                for s in self._indicator_engine._accumulators
                if self._indicator_engine.is_warm(s)
            )
            # Safe access to complex internal structure for diagnostics
            acc = self._indicator_engine._accumulators
            sample_sym = next(iter(acc), None)
            sample_candles = len(acc[sample_sym].candles) if sample_sym else 0

            logger.info(
                f"Market data: {len(data)} symbols fetched, "
                f"{len(acc)} tracked, "
                f"{warm_count} warm, "
                f"sample {sample_sym}={sample_candles} candles"
            )

    async def _update_risk_state(self, tick_count: int, diag_interval: int):
        """Update risk manager with current positions and save periodically to Redis.

        Args:
            tick_count: Current tick counter
            diag_interval: Diagnostic logging interval
        """
        if not self._risk_manager or not self._position_tracker:
            return

        try:
            # Update portfolio metrics from current positions
            positions_by_asset = {
                self.config.asset_class: list(self._position_tracker.positions)
            }
            self._risk_manager.update_positions(positions_by_asset)

            # Periodic save to Redis (every 60 seconds)
            current_time = time.monotonic()
            if current_time - self._last_risk_save_time >= 60.0:
                await self._risk_manager.save_to_redis()
                self._last_risk_save_time = current_time

                # Log risk state on save
                if tick_count % diag_interval == 0:
                    state = self._risk_manager.get_risk_state()
                    metrics = self._risk_manager.get_portfolio_metrics()
                    logger.info(
                        f"Risk state: positions={metrics.total_positions}, "
                        f"daily_pnl={state.daily_pnl_pct:.2f}%, "
                        f"drawdown={state.drawdown_pct:.2f}% ({state.drawdown_level.value}), "
                        f"blocked={state.is_blocked}"
                    )

            # Check for drawdown alerts and send if threshold crossed
            state = self._risk_manager.get_risk_state()
            if state.drawdown_level in (DrawdownLevel.DANGER, DrawdownLevel.CRITICAL):
                # Only alert once per level
                alert_key = f"drawdown_{state.drawdown_level.value}"
                if alert_key not in state.alerts_sent:
                    try:
                        metrics = self._risk_manager.get_portfolio_metrics()
                        message = (
                            f"🚨 RISK ALERT - DRAWDOWN_{state.drawdown_level.value.upper()}\n"
                            f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            f"<b>포트폴리오 드로다운 경고</b>\n\n"
                            f"레벨: {state.drawdown_level.value.upper()}\n"
                            f"현재 드로다운: {state.drawdown_pct:.2f}%\n"
                            f"포지션 수: {metrics.total_positions}\n"
                            f"일간 손익: {state.daily_pnl_pct:.2f}%\n"
                            f"총 노출: {metrics.total_exposure_pct:.1f}%"
                        )
                        await self._notify(message)
                        state.alerts_sent.add(alert_key)
                    except (NetworkError, OSError, ConnectionError, TimeoutError) as e:
                        logger.warning(f"Failed to send drawdown alert: {e}")

        except (InfrastructureError, ValidationError) as e:
            logger.error(f"Risk state update failed: {e}", exc_info=True)

    def _record_market_metrics(self):
        """Record staleness metrics."""
        # Report REST-sourced staleness. For futures the snapshot is populated
        # from WebSocket cache, so this metric reflects WebSocket freshness.
        if self._market_data_snapshot:
            staleness = self._get_market_data_staleness_seconds()
            if staleness is not None:
                self._metrics.record_market_data_staleness(staleness)

        if self._stock_price_feed:
            ws_staleness = self._stock_price_feed.get_staleness_seconds()
            if ws_staleness is not None:
                self._metrics.record_websocket_staleness("stock", ws_staleness)
        if self._futures_price_feed:
            ws_staleness = self._futures_price_feed.get_staleness_seconds()
            if ws_staleness is not None:
                self._metrics.record_websocket_staleness("futures", ws_staleness)

        # Universe / indicator health
        if self._indicator_engine:
            stats = self._indicator_engine.get_stats()
            self._metrics.record_universe_health(
                universe_size=len(self.config.symbols) if self.config.symbols else 0,
                warm_symbols=stats["warm_symbols"],
                tracked=stats["total_symbols"],
            )
        if self._market_data_snapshot:
            self._metrics.record_data_fetch(len(self._market_data_snapshot))

        self._sync_open_positions_metric()

    def _sync_open_positions_metric(self) -> None:
        """Synchronize open position gauge with current tracker state."""
        open_positions = 0
        if self._position_tracker:
            count = getattr(self._position_tracker, "position_count", None)
            if isinstance(count, int):
                open_positions = count
            else:
                positions = getattr(self._position_tracker, "positions", None)
                if positions is not None:
                    try:
                        open_positions = len(positions)
                    except TypeError:
                        open_positions = 0
        self._metrics.record_position_change(max(0, open_positions))

    async def _get_market_data_snapshot(
        self, symbols: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        async with self._market_data_lock:
            snapshot = dict(self._market_data_snapshot)

        if symbols:
            return {
                symbol: snapshot[symbol] for symbol in symbols if symbol in snapshot
            }
        return snapshot

    async def _get_quote_payload(self, symbol: str) -> dict[str, Any]:
        """Get best-effort real-time payload for a symbol."""
        snapshot = await self._get_market_data_snapshot([symbol])
        payload = snapshot.get(symbol, {})
        if payload and payload.get("bid_price_1") and payload.get("ask_price_1"):
            return payload

        if self._futures_price_feed and hasattr(
            self._futures_price_feed, "get_orderbook_snapshot"
        ):
            try:
                ob = self._futures_price_feed.get_orderbook_snapshot(symbol)
                if ob:
                    merged = dict(payload)
                    merged.update(ob)
                    return merged
            except (NetworkError, ValidationError, KeyError, AttributeError):
                # Silently skip if orderbook snapshot is unavailable
                pass
        return payload

    @staticmethod
    def _serialize_state_transitions(transitions: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in transitions:
            state = getattr(item, "state", None)
            at = getattr(item, "at", None)
            reason = getattr(item, "reason", "")
            result.append(
                {
                    "state": getattr(state, "value", str(state)),
                    "at": at.isoformat() if isinstance(at, datetime) else str(at),
                    "reason": reason,
                }
            )
        return result

    @staticmethod
    def _normalize_entry_order_result(result: Any) -> tuple[bool, float, int, str]:
        """Normalize legacy/new entry-order return tuples."""
        if not isinstance(result, tuple):
            raise ValueError(f"Unexpected entry order result type: {type(result)}")
        if len(result) == 4:
            is_filled, fill_price, filled_qty, venue = result
            return bool(is_filled), float(fill_price), int(filled_qty), str(venue)
        if len(result) == 3:
            is_filled, fill_price, filled_qty = result
            return bool(is_filled), float(fill_price), int(filled_qty), "KRX"
        raise ValueError(f"Unexpected entry order result length: {len(result)}")

    def _update_entry_slippage_stats(self, adverse_ticks: float) -> None:
        stats = self._entry_slippage_stats
        count = int(stats.get("count", 0.0)) + 1
        total = float(stats.get("adverse_ticks_sum", 0.0)) + adverse_ticks
        stats["count"] = float(count)
        stats["adverse_ticks_sum"] = total
        stats["avg_adverse_ticks"] = total / count if count > 0 else 0.0

    # -------------------------------------------------------------------------
    # Pipeline Handlers
    # -------------------------------------------------------------------------

    async def _handle_regime(self) -> dict[str, Any] | None:
        """Regime detection handler (runs every 5 min)

        Uses MarketClassifier with MFI computed from streaming indicator engine.
        Falls back to simple avg-change classification when MFI is unavailable.

        If config.regime_detection_mode == 'adaptive', delegates to _handle_adaptive_regime().
        """
        # Delegate to adaptive regime handler if enabled
        if (
            self.config.regime_detection_mode == "adaptive"
            and self._adaptive_regime_detector
        ):
            return await self._handle_adaptive_regime()

        # Otherwise, use simple regime detection (legacy behavior)
        if not self._data_provider:
            return None

        try:
            data = await self._get_market_data_snapshot()
            if not data:
                logger.debug(
                    "Market data snapshot empty, regime from indicator engine only"
                )
            regime = self._classify_market(data)
            self._current_regime = regime
            self._current_regime_confidence = (
                None  # Simple mode doesn't provide confidence
            )

            # Periodic refresh of daily indicators (for daily_pullback)
            self._refresh_daily_indicators()

            # Refresh adaptive sizing multipliers
            if self._adaptive_sizing:
                try:
                    self._adaptive_sizing.refresh()
                except (InfrastructureError, OSError, ConnectionError) as e:
                    logger.debug(f"Adaptive sizing refresh failed: {e}")

            logger.info(f"Market regime: {regime}")

            return {
                "regime": regime,
                "timestamp": datetime.now().isoformat(),
                "symbols_checked": len(data) if data else 0,
            }

        except (NetworkError, APIError, InfrastructureError, ValidationError) as e:
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
        # Try MFI-based classification via MarketClassifier (works even without market_data)
        if self._indicator_engine:
            active = set(self.config.symbols) if self.config.symbols else None
            mfi = self._indicator_engine.get_market_mfi(active)
            if mfi is not None:
                try:
                    from shared.strategy.market_classifier import MarketClassifier

                    classifier = MarketClassifier()
                    state = classifier.classify(mfi=mfi, adx=0.0)
                    return state.value
                except (ValidationError, ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"MarketClassifier failed: {e}")

        # Fallback: simple avg-change heuristic (used during warmup)
        changes = []
        for symbol, data in market_data.items():
            if isinstance(data, dict):
                change = data.get("change", 0)
                if change:
                    changes.append(change)

        if not market_data:
            return "UNKNOWN"

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

    async def _handle_adaptive_regime(self) -> dict[str, Any] | None:
        """Adaptive regime detection handler using AdaptiveRegimeDetector.

        Uses multi-metric classification (MFI, ADX, volatility, trend) to detect
        enhanced regime states (TRENDING_BULL, TRENDING_BEAR, VOLATILE_SIDEWAYS, etc.).

        Returns:
            Dict with regime, confidence, and timestamp, or None if detection failed
        """
        if not self._adaptive_regime_detector:
            logger.warning(
                "Adaptive regime detector not initialized, falling back to simple mode"
            )
            return None

        if not self._indicator_engine:
            logger.debug("Indicator engine not available for adaptive regime detection")
            return None

        try:
            # Get recent OHLCV data from indicator engine for regime detection
            # AdaptiveRegimeDetector.detect() expects a DataFrame with OHLCV + volume
            recent_bars = self._get_recent_bars_for_regime()

            if recent_bars is None or recent_bars.empty:
                logger.debug("No recent bars available for adaptive regime detection")
                return None

            # Detect regime using multi-metric classification
            regime_signal = self._adaptive_regime_detector.detect(recent_bars)

            if not regime_signal:
                logger.debug("AdaptiveRegimeDetector returned None")
                return None

            # Update current regime state
            self._current_regime = regime_signal.state.value
            self._current_regime_confidence = regime_signal.confidence

            # Periodic refresh of daily indicators (for daily_pullback)
            self._refresh_daily_indicators()

            # Refresh adaptive sizing multipliers
            if self._adaptive_sizing:
                try:
                    self._adaptive_sizing.refresh()
                except (InfrastructureError, OSError, ConnectionError) as e:
                    logger.debug(f"Adaptive sizing refresh failed: {e}")

            logger.info(
                f"AdaptiveRegime: {regime_signal.state.value} "
                f"(confidence: {regime_signal.confidence:.2f})"
            )

            return {
                "regime": regime_signal.state.value,
                "confidence": regime_signal.confidence,
                "timestamp": regime_signal.timestamp.isoformat(),
                "indicators": regime_signal.indicators,  # MFI, ADX, volatility, trend values
            }

        except (ValidationError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Adaptive regime detection failed: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error in adaptive regime detection: {e}",
                exc_info=True,
            )
            return None

    def _get_recent_bars_for_regime(self) -> Any:
        """Get recent OHLCV bars for regime detection.

        Returns:
            DataFrame with columns: open, high, low, close, volume
            or None if data not available
        """
        if not self._indicator_engine:
            return None

        try:
            # For stock mode: get bars for primary symbol (or first symbol in list)
            # For futures mode: get bars for the futures contract
            symbol = None
            if self.config.asset_class == "futures":
                # Get the primary futures symbol (should be tracked by indicator engine)
                if self.config.symbols:
                    symbol = self.config.symbols[0]
            else:
                # For stocks, we need aggregated market data across symbols
                # Use first symbol as proxy for now (AdaptiveRegimeDetector works on market-level)
                if self.config.symbols:
                    symbol = self.config.symbols[0]

            if not symbol:
                logger.debug("No symbol available for regime detection")
                return None

            # Get recent bars from indicator engine (need at least 50+ bars for SMA calculation)
            # IndicatorEngine stores minute bars, fetch last 100 bars
            candles = self._indicator_engine.get_recent_candles(symbol, limit=100)
            if not candles:
                return None

            # Convert list[dict] to DataFrame for AdaptiveRegimeDetector.detect()
            bars_df = pd.DataFrame(candles)

            return bars_df

        except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as e:
            logger.debug(f"Failed to get recent bars for regime detection: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error getting recent bars for regime: {e}",
                exc_info=True,
            )
            return None

    def _entry_reentry_guard_key(self, code: str, strategy: str | None) -> str:
        cfg = getattr(
            self,
            "_entry_reentry_guard",
            EntryReentryGuardConfig(enabled=False),
        )
        if cfg.scope == "symbol":
            return str(code)
        return f"{code}:{strategy or ''}"

    def _record_recent_exit_for_reentry_guard(
        self,
        closed: Any,
        signal: ExitSignal,
        reason: str,
    ) -> None:
        """Record a filled exit so near-term re-entry can be blocked."""
        cfg = getattr(
            self,
            "_entry_reentry_guard",
            EntryReentryGuardConfig(enabled=False),
        )
        if not cfg.enabled or self.config.asset_class != "stock":
            return

        cooldown_seconds = cfg.cooldown_for(reason)
        if cooldown_seconds <= 0:
            return

        code = str(getattr(signal, "code", "") or getattr(closed, "code", "") or "")
        if not code:
            return
        strategy = str(
            getattr(signal, "strategy", "") or getattr(closed, "strategy", "") or ""
        )
        key = self._entry_reentry_guard_key(code, strategy)

        recent = getattr(self, "_recent_exit_cooldowns", None)
        if recent is None:
            recent = {}
            self._recent_exit_cooldowns = recent

        recent[key] = {
            "code": code,
            "strategy": strategy,
            "reason": str(reason).lower(),
            "exit_time": datetime.now(UTC),
            "cooldown_seconds": float(cooldown_seconds),
        }

    def _reentry_guard_block(
        self,
        signal: Signal,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Return block metadata when a signal violates post-exit cooldown."""
        cfg = getattr(
            self,
            "_entry_reentry_guard",
            EntryReentryGuardConfig(enabled=False),
        )
        if not cfg.enabled or self.config.asset_class != "stock":
            return None

        recent = getattr(self, "_recent_exit_cooldowns", {})
        if not recent:
            return None

        now_utc = now or datetime.now(UTC)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)
        else:
            now_utc = now_utc.astimezone(UTC)

        key = self._entry_reentry_guard_key(signal.code, signal.strategy)
        record = recent.get(key)
        if not record:
            return None

        exit_time = record.get("exit_time")
        if not isinstance(exit_time, datetime):
            recent.pop(key, None)
            return None
        if exit_time.tzinfo is None:
            exit_time = exit_time.replace(tzinfo=UTC)
        else:
            exit_time = exit_time.astimezone(UTC)

        cooldown_seconds = float(record.get("cooldown_seconds", 0.0) or 0.0)
        elapsed = max(0.0, (now_utc - exit_time).total_seconds())
        remaining = cooldown_seconds - elapsed
        if remaining <= 0:
            recent.pop(key, None)
            return None

        return {
            **record,
            "remaining_seconds": remaining,
            "elapsed_seconds": elapsed,
        }

    def _filter_reentry_guarded_signals(self, signals: list[Signal]) -> list[Signal]:
        if not signals:
            return signals

        filtered: list[Signal] = []
        now = datetime.now(UTC)
        for signal in signals:
            block = self._reentry_guard_block(signal, now=now)
            if block:
                logger.info(
                    "Entry blocked by post-exit cooldown: code=%s strategy=%s "
                    "reason=%s remaining=%.0fs",
                    signal.code,
                    signal.strategy,
                    block.get("reason", ""),
                    float(block.get("remaining_seconds", 0.0) or 0.0),
                )
                continue
            filtered.append(signal)

        return filtered

    async def _handle_entry(self) -> list[Signal]:
        """Entry signal handler (runs every 1 sec)

        Checks entry conditions across all strategies.
        """
        if not self._strategy_manager or not self._data_provider:
            return []

        if not self._position_tracker:
            return []

        # Skip entries when regime is unknown or BEAR for long-only strategies (stocks).
        # Futures (bidirectional) can profit from short entries in BEAR.
        if self.config.asset_class != "futures":
            if not self._current_regime:
                logger.info("Entry blocked: regime not yet classified")
                return []
            if "BEAR" in self._current_regime:
                logger.info(f"Entry blocked: regime={self._current_regime}")
                return []

        # Check position limit
        if not self._position_tracker.can_open_position():
            return []

        try:
            # Fetch market data
            data = await self._get_market_data_snapshot()
            if not data:
                return []

            self._metrics.record_signal_evaluation()

            # tz-aware UTC. EntryContext.timestamp flows into signal.timestamp
            # and downstream slippage / dedupe / pipeline retry comparisons.
            now = datetime.now(UTC)

            # Check entries per symbol (Entry strategies expect single-symbol market_data).
            async def check_symbol(symbol: str) -> list[Signal]:
                symbol_data = data.get(symbol)
                if not isinstance(symbol_data, dict):
                    return []

                # Skip entry if indicator engine hasn't warmed up for this symbol
                if self._indicator_engine and not self._indicator_engine.is_warm(
                    symbol
                ):
                    return []

                # Use pre-computed enriched metadata cache (includes symbol_metadata + daily_indicators)
                cached_meta = self._enriched_metadata_cache.get(symbol, {})
                enriched = {**symbol_data, **cached_meta, "code": symbol}

                # Preserve pure symbol_metadata for context (without daily indicators)
                meta = self._cached_symbol_meta.get(symbol, {})

                # Inject streaming indicators (BB/RSI/RL/momentum)
                indicators: dict[str, Any] = {}
                if self._indicator_engine:
                    resolver = getattr(self, "_indicator_resolver", None)
                    if resolver:
                        indicators = resolver.collect_entry_indicators(symbol)
                    else:
                        # Backward-safe fallback (resolve from required keys without hardcoded timeframes).
                        logger.warning(
                            "Indicator resolver not initialized; using fallback instantiation in hot path"
                        )
                        try:
                            from shared.indicators.resolver import (
                                StreamingIndicatorResolver,
                            )

                            fallback_resolver = StreamingIndicatorResolver(
                                engine=self._indicator_engine,
                                required_keys=tuple(
                                    self._strategy_manager.required_indicators
                                ),
                            )
                            indicators = fallback_resolver.collect_entry_indicators(
                                symbol
                            )
                        except (ValidationError, KeyError, AttributeError):
                            # Fallback to basic indicators if resolver fails
                            indicators = self._indicator_engine.get_indicators(symbol)
                    if indicators:
                        enriched.update(indicators)

                # Add daily indicators to indicators dict (kept separate from symbol metadata)
                daily_ind = self._cached_daily_indicators.get(symbol, {})
                if daily_ind:
                    indicators.update(daily_ind)

                # Fetch daily indicators from engine (SMA/EMA/RSI on daily timeframe)
                if self._indicator_engine:
                    try:
                        daily_indicators = self._indicator_engine.get_daily_indicators(
                            symbol
                        )
                        # Add with daily_ prefix for multi-timeframe clarity
                        for key, value in daily_indicators.items():
                            indicators[f"daily_{key}"] = value
                    except (ValidationError, KeyError, AttributeError) as e:
                        logger.debug(
                            f"Failed to fetch daily indicators for {symbol}: {e}"
                        )

                context = EntryContext(
                    market_data=enriched,
                    indicators=indicators,
                    current_positions=self._position_tracker.positions,
                    timestamp=now,
                    metadata={
                        "paper_trading": self.config.paper_trading,
                        "regime": self._current_regime,
                        "regime_confidence": self._current_regime_confidence,
                        "market_state": self._current_regime,
                        "symbol_metadata": meta,
                        "accumulation_candidates": getattr(
                            self, "_accumulation_candidates", {}
                        ),
                        "dip_candidates": getattr(self, "_dip_candidates", {}),
                        "daily_watchlist": self._daily_watchlist,
                        # Setup A (gap reversion) hard-requires this; absence
                        # was the root cause of 0 signals since cutover.
                        "macro_overnight": self._get_macro_overnight(),
                        # Setup C (event reaction) find_recent_event needs
                        # this; same wiring-gap root cause.
                        "scheduled_events": self._get_scheduled_events(),
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
            signals = self._filter_reentry_guarded_signals(signals)

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

        except (NetworkError, APIError, InfrastructureError, ValidationError) as e:
            logger.error(f"Entry handler failed: {e}", exc_info=True)
            return []

    async def _handle_monitoring(self) -> dict[str, Any] | None:
        """Position monitoring handler (runs every 0.1 sec)

        Updates position prices and state transitions.
        """
        if not self._position_tracker or not self._data_provider:
            return None

        # Always publish status periodically, even with no positions
        if self._state_publisher:
            import time as _time_mod

            now = _time_mod.monotonic()
            if now - self._state_publisher._last_status_publish >= 5.0:
                self._state_publisher._last_status_publish = now
                self._state_publisher.publish_status(self.get_status())

            # Save candle cache periodically for crash recovery
            if (
                now - self._last_candle_cache_save
                >= self.config.candle_cache_save_interval
            ):
                self._last_candle_cache_save = now
                try:
                    self._save_candle_cache_to_redis()
                except (InfrastructureError, OSError, ConnectionError):
                    # Silently skip if Redis is unavailable
                    pass

        positions = self._position_tracker.positions
        if not positions:
            # Publish empty snapshot so stale Redis positions are cleared.
            if self._state_publisher:
                self._state_publisher.publish_positions_update([], throttle=2.0)
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

                # Immediate flush for state transitions (no throttle)
                if self._state_publisher:
                    self._state_publisher.publish_positions_update(
                        positions, throttle=0
                    )

            # Publish position updates to Redis (throttled to 2s)
            if self._state_publisher and positions:
                self._state_publisher.publish_positions_update(positions, throttle=2.0)

            return {
                "positions_updated": len(positions),
                "transitions": len(transitions),
            }

        except (NetworkError, APIError, InfrastructureError, ValidationError) as e:
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

            # Enrich exit data with streaming indicators (volume_velocity, vwap, RL, momentum)
            if self._indicator_engine:
                resolver = getattr(self, "_indicator_resolver", None)
                for symbol in symbols:
                    if symbol in data and isinstance(data[symbol], dict):
                        if resolver:
                            indicators = resolver.collect_exit_indicators(symbol)
                        else:
                            # Backward-safe fallback (resolve from required keys without hardcoded timeframes).
                            logger.warning(
                                "Indicator resolver not initialized; using fallback instantiation in exit hot path"
                            )
                            try:
                                from shared.indicators.resolver import (
                                    StreamingIndicatorResolver,
                                )

                                fallback_resolver = StreamingIndicatorResolver(
                                    engine=self._indicator_engine,
                                    required_keys=tuple(
                                        self._strategy_manager.required_indicators
                                    ),
                                )
                                indicators = fallback_resolver.collect_exit_indicators(
                                    symbol
                                )
                            except (ValidationError, KeyError, AttributeError):
                                # Fallback to basic indicators if resolver fails
                                indicators = self._indicator_engine.get_indicators(
                                    symbol
                                )
                        if indicators:
                            data[symbol] = {**data[symbol], **indicators}

            # Inject daily indicators for exit (chandelier_exit needs daily ATR/HH)
            # Use pre-computed daily indicators cache (without symbol metadata)
            for symbol in symbols:
                if symbol in data and isinstance(data[symbol], dict):
                    daily_ind = self._cached_daily_indicators.get(symbol, {})
                    if daily_ind:
                        data[symbol] = {**data[symbol], **daily_ind}

            # Check exits
            signals = await self._strategy_manager.check_exits(
                positions=positions,
                market_data=data,
                market_state=(
                    MarketStateAdapter(self._current_regime)
                    if self._current_regime
                    else None
                ),
            )

            # Stale-timeout liquidation: force-close positions with no tick data
            stale_signals = self._check_stale_position_exits(positions, data)
            if stale_signals:
                # Only add stale signals for positions not already scheduled for exit
                exiting_ids = {s.position_id for s in signals}
                signals = signals + [
                    s for s in stale_signals if s.position_id not in exiting_ids
                ]

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

        except (NetworkError, APIError, InfrastructureError, ValidationError) as e:
            logger.error(f"Exit handler failed: {e}", exc_info=True)
            return []

    def _check_stale_position_exits(
        self,
        positions: list,
        market_data: dict,
    ) -> list[ExitSignal]:
        """유동성 부족으로 틱이 없는 포지션을 강제 청산.

        execution.yaml::stale_position 설정 기반.
        IndicatorEngine의 last_tick_ts 를 통해 마지막 틱 수신 시각을 조회하고,
        timeout_seconds 초과 시 STALE_TIMEOUT 사유로 ExitSignal 생성.
        """
        if not self._indicator_engine:
            return []

        try:
            cfg = ConfigLoader.load("execution.yaml").get("stale_position", {})
        except Exception:
            cfg = {}

        if not cfg.get("enabled", True):
            return []

        timeout_sec: float = float(cfg.get("timeout_seconds", 600))
        min_holding_sec: float = float(cfg.get("min_holding_seconds", 120))
        asset_classes: list = cfg.get("asset_classes", ["stock"])

        if self.config.asset_class not in asset_classes:
            return []

        now = datetime.now(UTC)
        signals: list[ExitSignal] = []

        for position in positions:
            code = position.code

            # 최소 보유 시간 미충족 시 스킵
            try:
                holding_sec = (
                    (now - position.entry_time).total_seconds()
                    if position.entry_time
                    else 0.0
                )
                if holding_sec < min_holding_sec:
                    continue
            except (TypeError, AttributeError):
                continue

            tick_age = self._indicator_engine.get_tick_age_seconds(code, now=now)
            if tick_age is None or tick_age < timeout_sec:
                continue

            # 마지막 알려진 가격 사용 (시장가 제출 — 브로커가 체결가 결정)
            last_price = market_data.get(code, {}).get("close", position.current_price)

            logger.warning(
                f"Stale timeout: {code} ({position.name}) — "
                f"no tick for {tick_age:.0f}s (threshold={timeout_sec:.0f}s), "
                f"forcing liquidation at ~{last_price:.0f}"
            )

            signals.append(
                ExitSignal(
                    code=code,
                    name=position.name,
                    position_id=position.id,
                    reason=ExitReason.STALE_TIMEOUT,
                    strategy=position.strategy,
                    current_price=last_price,
                    exit_price=last_price,
                    entry_price=position.entry_price,
                    confidence=1.0,
                    priority=1,  # 최우선 청산
                    timestamp=now,
                    quantity=position.quantity,
                    metadata={
                        "tick_age_seconds": tick_age,
                        "timeout_seconds": timeout_sec,
                    },
                )
            )

        return signals

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
            # Re-check global position limit under lock
            if not self._position_tracker.can_open_position(signal.code):
                logger.debug(
                    f"Position limit reached, skipping entry for {signal.code}"
                )
                return

            # Risk management check - portfolio-level limits
            if self._risk_manager and not self._risk_manager.can_open_position(
                self.config.asset_class
            ):
                logger.warning(
                    f"Risk manager blocked entry for {signal.code} "
                    f"(asset_class={self.config.asset_class})"
                )

                # Send Telegram alert on first block (avoid spam)
                if not self._risk_block_alert_sent:
                    self._risk_block_alert_sent = True
                    try:
                        risk_state = self._risk_manager.get_risk_state()
                        portfolio_metrics = self._risk_manager.get_portfolio_metrics()
                        alert_message = (
                            f"🚨 RISK ALERT - POSITION_ENTRY_BLOCKED\n"
                            f"종목: {signal.code}\n"
                            f"자산군: {self.config.asset_class}\n\n"
                            f"<b>포트폴리오 현황:</b>\n"
                            f"총 포지션: {portfolio_metrics.total_positions}/{self._risk_manager.config.max_total_positions}\n"
                            f"일일 손익: {risk_state.daily_pnl_pct:.2f}%\n"
                        )
                        if risk_state.is_blocked:
                            alert_message += (
                                f"차단 사유: {risk_state.block_reason.name}\n"
                            )
                        await self._notify(alert_message)
                    except (NetworkError, OSError, ConnectionError, TimeoutError) as e:
                        logger.error(f"Failed to send risk block alert: {e}")

                return

            # Per-strategy position limit check
            strategy_name = signal.strategy
            if self._strategy_manager and strategy_name:
                strategy = self._strategy_manager.strategies.get(strategy_name)
                if strategy:
                    sizer_config = getattr(strategy.position_sizer, "config", None)
                    strategy_max = getattr(sizer_config, "max_positions", None)
                    if strategy_max is not None:
                        current_count = len(
                            self._position_tracker.get_positions_by_strategy(
                                strategy_name
                            )
                        )
                        if current_count >= strategy_max:
                            logger.info(
                                f"Strategy {strategy_name} position limit reached "
                                f"({current_count}/{strategy_max}), skipping {signal.code}"
                            )
                            return

            try:
                direction = self._get_signal_direction(signal)
                is_short = direction == "short"

                is_filled, fill_price, execution_meta = await self._submit_entry_order(
                    signal.code,
                    is_short,
                    quantity,
                    signal.price,
                    signal=signal,
                    price_source_time=getattr(signal, "timestamp", None),
                )
                execution_meta = execution_meta or {}
                filled_qty = int(execution_meta.get("filled_qty", quantity) or 0)

                if is_filled and filled_qty > 0:
                    await self._process_filled_entry(
                        signal,
                        fill_price,
                        filled_qty,
                        is_short,
                        direction,
                        execution_meta=execution_meta,
                    )
                elif is_filled:
                    logger.warning(
                        "Entry fill acknowledged but filled quantity is zero: %s",
                        signal.code,
                    )
                elif execution_meta.get("blocked_reason"):
                    blocked_reason = str(
                        execution_meta.get("blocked_reason") or "unknown"
                    )
                    if self._metrics:
                        self._metrics.record_signal(
                            "rejected",
                            strategy=signal.strategy,
                        )
                        self._metrics.record_entry_block(
                            strategy=signal.strategy,
                            reason=blocked_reason,
                        )
                    logger.info(
                        "Entry blocked by execution guard: %s %s",
                        signal.code,
                        blocked_reason,
                    )

            except (APIError, NetworkError, InfrastructureError, ValidationError) as e:
                logger.error(
                    f"Entry execution failed for {signal.code}: {e}", exc_info=True
                )

    async def _submit_entry_order(
        self,
        code: str,
        is_short: bool,
        quantity: int,
        price: float,
        signal: Signal | None = None,
        price_source_time: datetime | None = None,
    ) -> tuple[bool, float, dict[str, Any]]:
        """Submit entry order to broker."""
        if (
            self.config.asset_class == "futures"
            and self._futures_slippage_controller is not None
            and signal is not None
        ):
            return await self._submit_futures_entry_with_slippage_control(
                signal=signal,
                is_short=is_short,
                quantity=quantity,
            )

        is_filled, fill_price, filled_qty, venue = await self._place_entry_order(
            code=code,
            is_short=is_short,
            quantity=quantity,
            order_type="market",
            limit_price=None,
            market_price=price,
            price_source_time=price_source_time,
        )
        return (
            is_filled,
            fill_price,
            {
                "mode": "default_market",
                "submit_price": price,
                "filled_qty": int(filled_qty),
                "blocked_reason": "",
                "transitions": [],
                "venue": venue,
            },
        )

    async def _submit_futures_entry_with_slippage_control(
        self,
        *,
        signal: Signal,
        is_short: bool,
        quantity: int,
    ) -> tuple[bool, float, dict[str, Any]]:
        controller = self._futures_slippage_controller
        if controller is None:
            return (
                False,
                0.0,
                {"mode": "slippage_guard", "blocked_reason": "controller_missing"},
            )

        is_buy = not is_short
        code = signal.code
        signal_price = float(signal.price)
        signal_ts = (
            signal.timestamp
            if isinstance(signal.timestamp, datetime)
            else datetime.now(UTC)
        )

        quote_payload = await self._get_quote_payload(code)
        cross_payload: dict[str, Any] | None = None
        cross_symbol = ""
        if controller.config.cross_asset_enabled:
            cross_symbol = controller.config.cross_asset_symbol
            cross_payload = await self._get_quote_payload(cross_symbol)

        decision = controller.evaluate_entry(
            symbol=code,
            is_buy=is_buy,
            quantity=quantity,
            signal_price=signal_price,
            signal_timestamp=signal_ts,
            quote_payload=quote_payload,
            cross_asset_payload=cross_payload,
            now=datetime.now(UTC),
        )
        execution_meta: dict[str, Any] = {
            "mode": "slippage_guard",
            "signal_price": signal_price,
            "requested_qty": int(quantity),
            "cross_asset_symbol": cross_symbol,
            "blocked_reason": "",
            "state": decision.state.value,
            "transitions": self._serialize_state_transitions(decision.transitions),
            "submit_price": decision.target_price,
        }

        if getattr(decision.action, "value", "") == "block":
            execution_meta["blocked_reason"] = decision.reason
            return False, 0.0, execution_meta

        # Passive entry: limit at opposite best quote.
        passive_price = float(decision.target_price or signal_price)
        latest_quote = await self._get_quote_payload(code)
        current_touch_price = float(
            latest_quote.get("ask_price_1" if is_buy else "bid_price_1", passive_price)
        )
        is_filled, fill_price, filled_qty, venue = self._normalize_entry_order_result(
            await self._place_entry_order(
                code=code,
                is_short=is_short,
                quantity=quantity,
                order_type="limit",
                limit_price=passive_price,
                market_price=current_touch_price,
                price_source_time=signal_ts,
            )
        )
        execution_meta["submit_price"] = passive_price
        execution_meta["filled_qty"] = int(filled_qty)
        execution_meta["venue"] = venue
        if is_filled:
            execution_meta["state"] = "filled"
            if 0 < int(filled_qty) < int(quantity):
                execution_meta["execution_path"] = "passive_limit_partial"
                execution_meta["partial_fill"] = True
            else:
                execution_meta["execution_path"] = "passive_limit"
            return True, fill_price, execution_meta

        # Passive order timed out (paper mode unfilled). Evaluate retry/cancel.
        wait_seconds = max(0.05, float(controller.config.passive_timeout_seconds))
        # Live futures path already waits in OrderExecutor (fill inquiry + cancel),
        # so only enforce local delay for paper/mock fallback paths.
        should_wait = self.config.paper_trading or self._order_executor is None
        if should_wait:
            await asyncio.sleep(wait_seconds)

        retry_payload = await self._get_quote_payload(code)
        retry_decision = controller.evaluate_retry(
            symbol=code,
            is_buy=is_buy,
            signal_price=signal_price,
            quote_payload=retry_payload,
            now=datetime.now(UTC),
        )
        execution_meta["transitions"] += self._serialize_state_transitions(
            retry_decision.transitions
        )

        if getattr(retry_decision.action, "value", "") != "retry_market":
            execution_meta["blocked_reason"] = retry_decision.reason
            execution_meta["state"] = retry_decision.state.value
            return False, 0.0, execution_meta

        retry_market_price = float(retry_decision.target_price or signal_price)
        filled_retry, fill_retry, retry_filled_qty, retry_venue = (
            self._normalize_entry_order_result(
                await self._place_entry_order(
                    code=code,
                    is_short=is_short,
                    quantity=quantity,
                    order_type="market",
                    limit_price=None,
                    market_price=retry_market_price,
                    price_source_time=signal_ts,
                )
            )
        )
        execution_meta["filled_qty"] = int(retry_filled_qty)
        execution_meta["submit_price"] = retry_market_price
        execution_meta["venue"] = retry_venue
        execution_meta["state"] = retry_decision.state.value
        execution_meta["execution_path"] = "retry_market_once"
        if filled_retry:
            execution_meta["state"] = "filled"
            if 0 < int(retry_filled_qty) < int(quantity):
                execution_meta["execution_path"] = "retry_market_partial"
                execution_meta["partial_fill"] = True
            return True, fill_retry, execution_meta

        execution_meta["blocked_reason"] = "retry_unfilled"
        execution_meta["state"] = "cancelled"
        return False, 0.0, execution_meta

    def _select_execution_venue(
        self,
        code: str,
        side: Any,
        order_type: Any,
        quantity: int,
        price: float | None = None,
    ) -> ExecutionVenue:
        """Select execution venue using VenueRouter (stock only).

        Falls back to KRX if routing fails or is unavailable.
        """
        if not (self._venue_router and self.config.asset_class == "stock"):
            return ExecutionVenue.KRX

        try:
            from shared.execution.models import OrderRequest

            order_request = OrderRequest(
                code=code,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )
            routing_decision = self._venue_router.select_venue(
                order=order_request,
                market_data=None,
                current_time=datetime.now(),
            )
            logger.info(
                f"Venue routing decision: {routing_decision.venue.value} - {routing_decision.reason}"
            )
            return ExecutionVenue(routing_decision.venue)
        except Exception as e:
            logger.warning(f"Venue routing failed, using default KRX: {e}")
            return ExecutionVenue.KRX

    async def _place_entry_order(
        self,
        *,
        code: str,
        is_short: bool,
        quantity: int,
        order_type: str,
        limit_price: float | None,
        market_price: float,
        price_source_time: datetime | None = None,
    ) -> tuple[bool, float, int, str]:
        if self.config.paper_trading and self._paper_broker:
            try:
                from shared.paper import OrderSide as PaperOrderSide
                from shared.paper import OrderType as PaperOrderType
            except ImportError:
                return False, 0.0, 0, "KRX"

            side = PaperOrderSide.SELL if is_short else PaperOrderSide.BUY
            if order_type == "limit":
                order = await self._paper_broker.submit_order(
                    symbol=code,
                    side=side,
                    quantity=quantity,
                    price=float(limit_price or market_price),
                    order_type=PaperOrderType.LIMIT,
                    market_price=market_price,
                    price_source_time=price_source_time,
                )
                is_filled = bool(getattr(order, "filled", False))
                fill_price = float(getattr(order, "fill_price", 0.0) or 0.0)
                venue = getattr(order, "venue", "KRX")
                return is_filled, fill_price, (quantity if is_filled else 0), venue

            order = await self._paper_broker.submit_order(
                symbol=code,
                side=side,
                quantity=quantity,
                price=market_price,
                order_type=PaperOrderType.MARKET,
                price_source_time=price_source_time,
            )
            is_filled = bool(getattr(order, "filled", True))
            fill_price = float(
                getattr(order, "fill_price", market_price) or market_price
            )
            venue = getattr(order, "venue", "KRX")
            return is_filled, fill_price, (quantity if is_filled else 0), venue

        if self._order_executor is not None:
            from shared.execution.models import OrderRequest, OrderSide, OrderType

            side = OrderSide.SELL if is_short else OrderSide.BUY
            req_type = OrderType.LIMIT if order_type == "limit" else OrderType.MARKET
            req_price = (
                float(limit_price)
                if (req_type == OrderType.LIMIT and limit_price)
                else None
            )

            # Select execution venue using VenueRouter
            selected_venue = self._select_execution_venue(
                code=code,
                side=side,
                order_type=req_type,
                quantity=quantity,
                price=req_price,
            )

            resp = await self._order_executor.execute_order(
                OrderRequest(
                    code=code,
                    side=side,
                    order_type=req_type,
                    quantity=quantity,
                    price=req_price,
                    venue=selected_venue,
                )
            )
            fallback_price = float(limit_price or market_price)
            filled_qty = int(getattr(resp, "filled_qty", 0) or 0)
            filled_price = float(getattr(resp, "filled_price", 0.0) or 0.0)
            venue_attr = getattr(resp, "venue", selected_venue)
            resp_venue = (
                venue_attr.value if hasattr(venue_attr, "value") else str(venue_attr)
            )

            # Partial fills must be tracked even when broker final status is
            # timeout/cancel to avoid orphan live positions.
            if filled_qty > 0:
                return (
                    True,
                    float(filled_price or fallback_price),
                    max(0, filled_qty),
                    resp_venue,
                )

            if bool(resp.success):
                if req_type == OrderType.MARKET:
                    return (
                        True,
                        float(filled_price or fallback_price),
                        quantity,
                        resp_venue,
                    )
                if self.config.asset_class != "futures":
                    return (
                        True,
                        float(filled_price or fallback_price),
                        quantity,
                        resp_venue,
                    )
                if filled_price > 0:
                    return True, float(filled_price), quantity, resp_venue

            return False, 0.0, 0, resp_venue

        return True, float(limit_price or market_price), quantity, "KRX"

    async def _process_filled_entry(
        self,
        signal,
        fill_price,
        quantity,
        is_short,
        direction,
        execution_meta: dict[str, Any] | None = None,
    ):
        """Handle post-entry logic."""
        exec_meta = self._finalize_entry_execution_meta(
            signal=signal,
            fill_price=fill_price,
            is_short=is_short,
            execution_meta=execution_meta or {},
        )

        symbol_meta = (self.config.symbol_metadata or {}).get(signal.code, {})
        pos_metadata = {
            "snapshot_id": str(symbol_meta.get("llm_snapshot_id", "")),
            "llm_quality": symbol_meta.get("llm_quality"),
            "realtime_score": symbol_meta.get("realtime_score"),
            "risk_flags": symbol_meta.get("risk_flags", []),
            "entry_signal_confidence": signal.confidence,
            "signal_direction": direction,
            "execution": exec_meta,
            "entry_regime": self._current_regime,  # Store regime at entry for performance tracking
        }
        # Forward exit parameter overrides from signal.metadata (e.g. trend mode)
        signal_meta = getattr(signal, "metadata", None) or {}
        for key in (
            "exit_stop_atr_multiplier",
            "exit_trail_activation_atr",
            "exit_trail_atr_multiplier",
            "exit_max_hold_days",
            "obs",  # RL obs vector for live-vs-train drift diagnostics
        ):
            if key in signal_meta:
                pos_metadata[key] = signal_meta[key]
        # Extract execution venue from execution metadata
        execution_venue = exec_meta.get("venue", "KRX")
        position = self._position_tracker.add_position(
            code=signal.code,
            name=signal.name or self._symbol_names.get(signal.code, signal.code),
            entry_price=fill_price,
            quantity=quantity,
            strategy=signal.strategy,
            side=PositionSide.SHORT if is_short else PositionSide.LONG,
            metadata=pos_metadata,
            execution_venue=execution_venue,
        )

        if not position:
            return

        # Record entry in regime performance tracker
        if self._regime_tracker and self._current_regime:
            try:
                self._regime_tracker.record_entry(
                    regime=self._current_regime,
                    code=signal.code,
                    price=fill_price,
                    timestamp=datetime.now(),
                    model_name=signal.strategy,
                    metadata={
                        "signal_confidence": signal.confidence,
                        "direction": direction,
                    },
                )
                logger.debug(
                    f"Recorded entry in regime tracker: regime={self._current_regime}, "
                    f"code={signal.code}, strategy={signal.strategy}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to record entry in regime tracker: {e}", exc_info=True
                )

        self.total_trades += 1
        self._sync_open_positions_metric()
        name = signal.name or self._symbol_names.get(signal.code, "")

        self._log_entry(
            name,
            signal.code,
            fill_price,
            quantity,
            signal.strategy,
            signal.confidence,
            is_short,
            execution_meta=exec_meta,
        )

        # Collect snapshot
        indicators = self._collect_indicator_snapshot(signal.code, fill_price)

        # Telemetry
        self._record_entry_telemetry(
            position,
            signal,
            fill_price,
            quantity,
            name,
            indicators,
            execution_meta=exec_meta,
        )

        # Publish
        if self._state_publisher:
            self._state_publisher.publish_position_opened(position)
            self._state_publisher.publish_signal(signal, "entry", True)
            self._metrics.record_signal("entry", strategy=signal.strategy)

        # Mock mirror (fire-and-forget)
        if self._mock_mirror:
            side = "SELL" if is_short else "BUY"
            task = asyncio.create_task(
                self._mock_mirror.mirror_entry(signal.code, side, quantity, fill_price),
                name="mock_mirror_entry",
            )
            self._pending_notify_tasks.add(task)
            task.add_done_callback(self._on_notify_done)

    def _finalize_entry_execution_meta(
        self,
        *,
        signal: Signal,
        fill_price: float,
        is_short: bool,
        execution_meta: dict[str, Any],
    ) -> dict[str, Any]:
        meta = dict(execution_meta)
        signal_price = float(signal.price)
        submit_price = float(meta.get("submit_price", signal_price) or signal_price)

        meta["signal_price"] = signal_price
        meta["submit_price"] = submit_price
        meta["fill_price"] = float(fill_price)

        try:
            from shared.execution.slippage_control import compute_adverse_slippage_ticks

            tick_size = 0.02
            if (
                self._futures_slippage_controller is not None
                and getattr(self._futures_slippage_controller, "config", None)
                is not None
            ):
                tick_size = float(self._futures_slippage_controller.config.tick_size)

            slippage_ticks = compute_adverse_slippage_ticks(
                signal_price=signal_price,
                fill_price=float(fill_price),
                is_buy=(not is_short),
                tick_size=tick_size,
            )
            meta["slippage_ticks"] = float(slippage_ticks)
            meta["slippage_tick_size"] = tick_size

            self._update_entry_slippage_stats(max(0.0, float(slippage_ticks)))
            logger.info(
                "Entry execution prices: code=%s signal=%.2f submit=%.2f fill=%.2f "
                "slippage=%.2ft",
                signal.code,
                signal_price,
                submit_price,
                float(fill_price),
                float(slippage_ticks),
            )
        except ImportError:
            logger.debug("slippage_control not available, skipping slippage telemetry")

        return meta

    def _log_entry(
        self,
        name,
        code,
        price,
        qty,
        strategy,
        confidence,
        is_short,
        execution_meta: dict[str, Any] | None = None,
    ):
        """Log and notify entry."""
        direction = "SHORT" if is_short else "LONG"
        regime_str = self._current_regime or "unknown"
        if execution_meta:
            logger.info(
                "Entry executed: %s (%s) @ %.2f x %s "
                "[strategy=%s, direction=%s, confidence=%.2f, regime=%s, mode=%s, slippage=%+.2ft]",
                name,
                code,
                float(price),
                qty,
                strategy,
                direction,
                confidence,
                regime_str,
                execution_meta.get("mode", "default"),
                float(execution_meta.get("slippage_ticks", 0.0)),
            )
        else:
            logger.info(
                "Entry executed: %s (%s) @ %s x %s "
                "[strategy=%s, direction=%s, confidence=%.2f, regime=%s]",
                name,
                code,
                f"{price:,.0f}",
                qty,
                strategy,
                direction,
                confidence,
                regime_str,
            )
        amount = price * qty
        entry_label = "숏 진입" if is_short else "롱 진입"
        slippage_line = ""
        if execution_meta and execution_meta.get("slippage_ticks") is not None:
            slippage_line = (
                f"\n슬리피지: {float(execution_meta.get('slippage_ticks', 0.0)):+.2f}틱"
            )
        self._schedule_notify(
            f"🟢 <b>{entry_label}</b>\n"
            f"종목: {name} ({code})\n"
            f"가격: {price:,.0f}원 x {qty}주\n"
            f"금액: {amount:,.0f}원\n"
            f"전략: {strategy}\n"
            f"신뢰도: {confidence:.1%}"
            f"{slippage_line}"
        )

    def _collect_indicator_snapshot(self, code, price):
        """Get indicator snapshot at execution time."""
        snapshot = {}
        if self._indicator_engine:
            raw = self._indicator_engine.get_indicators(code)
            if raw:
                snapshot = {
                    "bb_lower": raw.get("bb_lower"),
                    "bb_upper": raw.get("bb_upper"),
                    "bb_middle": raw.get("bb_middle"),
                    "rsi": raw.get("rsi"),
                    "mfi": raw.get("mfi"),
                }
                bl, bu = raw.get("bb_lower", 0), raw.get("bb_upper", 0)
                if bu and bl and bu > bl:
                    snapshot["bb_position"] = (price - bl) / (bu - bl)
        return snapshot

    def _record_entry_telemetry(
        self,
        position,
        signal,
        price,
        qty,
        name,
        indicators,
        execution_meta: dict[str, Any] | None = None,
    ):
        """Append entry event to training data."""
        self._append_training_trade_event(
            {
                "event": "entry",
                "timestamp": datetime.now().isoformat(),
                "position_id": position.id,
                "snapshot_id": position.metadata.get("snapshot_id", ""),
                "code": signal.code,
                "name": name,
                "strategy": signal.strategy,
                "entry_price": price,
                "quantity": qty,
                "signal_confidence": signal.confidence,
                "indicators": indicators,
                "regime": self._current_regime,
                "metadata": position.metadata,
                "execution": execution_meta or {},
            }
        )

    # Replaces _collect_exit_indicators with generic one
    def _collect_exit_indicators(self, code, price):
        return self._collect_indicator_snapshot(code, price)

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
                exit_quantity = (
                    signal.quantity if signal.quantity > 0 else position.quantity
                )

                is_filled, fill_price = await self._submit_exit_order(
                    signal.code, close_is_buy, exit_quantity, signal.exit_price
                )

                if is_filled:
                    await self._process_filled_exit(
                        position, signal, fill_price, exit_quantity, close_is_buy
                    )

            except (APIError, NetworkError, InfrastructureError, ValidationError) as e:
                logger.error(
                    f"Exit execution failed for {signal.code}: {e}", exc_info=True
                )

    async def _submit_exit_order(
        self, code: str, is_buy: bool, quantity: int, price: float
    ) -> tuple[bool, float]:
        """Submit exit order to appropriate broker.

        Exit orders use wall-clock UTC as price_source_time because the exit
        price is the current market quote at signal time (not a cached snapshot).
        """
        if self.config.paper_trading and self._paper_broker:
            # Paper trading
            try:
                from shared.paper import OrderSide as PaperOrderSide
            except ImportError:
                # If imports fail inside method (unlikely as it's top level usually), fallback
                return False, 0.0

            order = await self._paper_broker.submit_order(
                symbol=code,
                side=PaperOrderSide.BUY if is_buy else PaperOrderSide.SELL,
                quantity=quantity,
                price=price,
                price_source_time=datetime.now(UTC),
            )
            is_filled = bool(getattr(order, "filled", True))
            fill_price = float(getattr(order, "fill_price", price) or price)
            return is_filled, fill_price

        elif self._order_executor is not None:
            # Real execution
            from shared.execution.models import OrderRequest, OrderSide, OrderType

            side = OrderSide.BUY if is_buy else OrderSide.SELL

            # Select execution venue using VenueRouter
            selected_venue = self._select_execution_venue(
                code=code,
                side=side,
                order_type=OrderType.MARKET,
                quantity=quantity,
            )

            resp = await self._order_executor.execute_order(
                OrderRequest(
                    code=code,
                    side=side,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                    price=None,
                    venue=selected_venue,
                )
            )
            return bool(resp.success), float(resp.filled_price or price)

        else:
            # Mock execution
            return True, price

    async def _process_filled_exit(
        self, position, signal, fill_price, exit_quantity, close_is_buy
    ):
        """Handle post-exit logic: tracker update, logging, telemetry."""
        reason_str = (
            signal.reason.value
            if hasattr(signal.reason, "value")
            else str(signal.reason)
        )

        # Close position
        closed = self._position_tracker.close_position(
            position_id=signal.position_id,
            exit_price=fill_price,
            reason=reason_str,
            quantity=exit_quantity,
        )

        if not closed:
            return

        self._record_recent_exit_for_reentry_guard(closed, signal, reason_str)

        # Record exit in regime performance tracker
        if self._regime_tracker:
            try:
                # Extract entry regime from position metadata
                entry_regime = (
                    closed.metadata.get("entry_regime") if closed.metadata else None
                )
                if entry_regime:
                    self._regime_tracker.record_exit(
                        regime=entry_regime,
                        code=signal.code,
                        price=fill_price,
                        timestamp=datetime.now(),
                        pnl=closed.unrealized_pnl,
                        model_name=closed.strategy,
                    )
                    logger.debug(
                        f"Recorded exit in regime tracker: regime={entry_regime}, "
                        f"code={signal.code}, pnl={closed.unrealized_pnl:.2f}"
                    )
                else:
                    logger.debug(
                        f"No entry_regime in position metadata for {signal.code}, "
                        "skipping regime performance tracking"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to record exit in regime tracker: {e}", exc_info=True
                )

        name = getattr(closed, "name", "") or self._symbol_names.get(signal.code, "")
        pnl = closed.unrealized_pnl
        pnl_pct = closed.profit_pct
        # Position.current_price is set to exit_price on close,
        # so unrealized_pnl effectively equals realized PnL.
        self.total_pnl += pnl
        await self._record_risk_realized_pnl(pnl)
        self._sync_open_positions_metric()

        strategy_name = signal.strategy or closed.strategy or ""
        holding_mins = getattr(signal, "holding_minutes", None) or 0
        self._log_exit(
            name,
            signal.code,
            fill_price,
            exit_quantity,
            reason_str,
            pnl,
            pnl_pct,
            close_is_buy,
            strategy_name,
            holding_mins,
        )

        # Collect snapshot
        indicators = self._collect_exit_indicators(signal.code, fill_price)

        # Telemetry
        self._record_exit_telemetry(
            closed,
            signal,
            fill_price,
            exit_quantity,
            reason_str,
            pnl,
            pnl_pct,
            indicators,
        )

        # Publish
        if self._state_publisher:
            self._state_publisher.publish_position_closed(closed)
            self._record_running_totals(closed)
            self._state_publisher.publish_signal(signal, "exit", True)
            self._metrics.record_trade(
                pnl=pnl, win=(pnl >= 0), strategy=getattr(signal, "strategy", "default")
            )

        # Persist to ClickHouse (asset-class routed; details in _persist_closed_position)
        strategy = getattr(signal, "strategy", getattr(closed, "strategy", ""))
        if self.config.asset_class == "stock" or (
            self.config.asset_class == "futures" and strategy.startswith("rl_")
        ):
            task = asyncio.create_task(
                self._persist_closed_position(closed, strategy), name="persist_closed"
            )
            self._pending_notify_tasks.add(task)
            task.add_done_callback(self._on_notify_done)

        # Mock mirror (fire-and-forget)
        if self._mock_mirror:
            side = "BUY" if close_is_buy else "SELL"
            task = asyncio.create_task(
                self._mock_mirror.mirror_exit(
                    signal.code, side, exit_quantity, fill_price
                ),
                name="mock_mirror_exit",
            )
            self._pending_notify_tasks.add(task)
            task.add_done_callback(self._on_notify_done)

    def _log_exit(
        self,
        name,
        code,
        price,
        qty,
        reason,
        pnl,
        pnl_pct,
        is_buy,
        strategy="",
        holding_minutes=0,
    ):
        """Log and notify exit."""
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        side_str = "숏 청산" if is_buy else "롱 청산"

        held_str = f", held={holding_minutes}min" if holding_minutes else ""
        strategy_str = f", strategy={strategy}" if strategy else ""
        logger.info(
            f"Exit executed: {name} ({code}) @ {price:,.0f} "
            f"(reason={reason}{strategy_str}, pnl={pnl_pct:+.2f}%{held_str})"
        )
        self._schedule_notify(
            f"{pnl_emoji} <b>{side_str}</b>\n"
            f"종목: {name} ({code})\n"
            f"가격: {price:,.0f}원 x {qty}주\n"
            f"사유: {reason}\n"
            f"손익: {pnl:+,.0f}원 ({pnl_pct:+.2f}%)"
        )

    def _collect_exit_indicators(self, code, price):
        """Get indicator snapshot at exit."""
        snapshot = {}
        if self._indicator_engine:
            raw = self._indicator_engine.get_indicators(code)
            if raw:
                snapshot = {
                    "bb_lower": raw.get("bb_lower"),
                    "bb_upper": raw.get("bb_upper"),
                    "bb_middle": raw.get("bb_middle"),
                    "rsi": raw.get("rsi"),
                    "mfi": raw.get("mfi"),
                }
                bl, bu = raw.get("bb_lower", 0), raw.get("bb_upper", 0)
                if bu and bl and bu > bl:
                    snapshot["bb_position"] = (price - bl) / (bu - bl)
        return snapshot

    def _record_exit_telemetry(
        self, closed, signal, price, qty, reason, pnl, pnl_pct, indicators
    ):
        """Append trade event to training data."""
        peak_pnl_pct = 0.0
        if signal.high_since_entry and closed.entry_price:
            peak_pnl_pct = (
                (signal.high_since_entry - closed.entry_price)
                / closed.entry_price
                * 100
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
                "name": getattr(closed, "name", ""),
                "entry_price": closed.entry_price,
                "exit_price": price,
                "quantity": qty,
                "reason": reason,
                "trade_pnl": pnl,
                "trade_pnl_pct": pnl_pct,
                "hold_seconds": (
                    (closed.exit_time - closed.entry_time).total_seconds()
                    if closed.exit_time and closed.entry_time
                    else None
                ),
                "indicators": indicators,
                "regime": self._current_regime,
                "exit_stage": signal.stage,
                "high_since_entry": signal.high_since_entry,
                "holding_minutes": signal.holding_minutes,
                "peak_pnl_pct": peak_pnl_pct,
                "metadata": (
                    closed.metadata if isinstance(closed.metadata, dict) else {}
                ),
            }
        )

    @staticmethod
    def _get_signal_direction(signal: Signal) -> str:
        """Extract normalized signal direction from metadata."""
        metadata = getattr(signal, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return "long"
        direction = (
            metadata.get("signal_direction") or metadata.get("direction") or "long"
        )
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
        if (
            self._strategy_manager
            and signal.strategy in self._strategy_manager.strategies
        ):
            try:
                strategy = self._strategy_manager.strategies[signal.strategy]
                balance = self._get_account_balance()

                # Apply adaptive sizing multiplier (temporarily scale fixed_amount)
                multiplier = 1.0
                original_amount = None
                sizer_cfg = getattr(strategy.position_sizer, "config", None)
                if (
                    self._adaptive_sizing
                    and sizer_cfg
                    and hasattr(sizer_cfg, "fixed_amount")
                ):
                    multiplier = self._adaptive_sizing.get_multiplier(signal.strategy)
                    if multiplier != 1.0:
                        original_amount = sizer_cfg.fixed_amount
                        sizer_cfg.fixed_amount = original_amount * multiplier

                try:
                    qty = strategy.calculate_position_size(
                        signal=signal,
                        account_balance=balance,
                        current_positions=(
                            self._position_tracker.positions
                            if self._position_tracker
                            else []
                        ),
                    )
                finally:
                    # Restore original amount
                    if original_amount is not None:
                        sizer_cfg.fixed_amount = original_amount

                if qty > 0:
                    if multiplier != 1.0:
                        logger.info(
                            f"Adaptive sizing: {signal.strategy} {signal.code} "
                            f"qty={qty} (x{multiplier:.2f})"
                        )
                    return min(qty, MAX_ORDER_QUANTITY)
            except (ValidationError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Strategy sizer failed for {signal.code}: {e}")

        # Fallback: config-based fixed order amount.
        order_amount = float(self.config.order_amount_per_trade)
        return calc_order_quantity(
            order_amount=order_amount,
            price=signal.price,
            max_quantity=MAX_ORDER_QUANTITY,
        )

    def _get_account_balance(self) -> float:
        """Best-effort account balance/equity for sizing."""
        if self._paper_broker is not None:
            # VirtualBroker exposes balance and get_equity().
            if hasattr(self._paper_broker, "get_equity"):
                try:
                    return float(self._paper_broker.get_equity())
                except (TypeError, ValueError, AttributeError):
                    pass
            if hasattr(self._paper_broker, "balance"):
                try:
                    return float(self._paper_broker.balance)
                except (TypeError, ValueError, AttributeError):
                    pass
        return float(self.config.initial_capital)

    def _append_training_trade_event(self, row: dict[str, Any]) -> None:
        try:
            os.makedirs(self._llm_training_data_dir, exist_ok=True)
            path = os.path.join(self._llm_training_data_dir, "trade_outcomes.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except (OSError, TypeError, ValueError) as e:
            logger.debug(f"Failed to append training trade event: {e}")

    def _schedule_notify(self, message: str) -> None:
        """Fire-and-forget notification with task tracking.

        Creates an asyncio task for the notification and tracks it
        so exceptions are not silently swallowed.
        """
        task = asyncio.create_task(self._notify(message), name="notify")
        self._pending_notify_tasks.add(task)
        task.add_done_callback(self._on_notify_done)

    def _on_notify_done(self, task: asyncio.Task) -> None:
        """Callback to clean up completed notify tasks and log errors."""
        self._pending_notify_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.warning(f"Notification task failed: {exc}")

    async def _notify(self, message: str):
        """알림 전송

        도메인(asset_class)별 채널로 라우팅한다:
        - 우선순위: config.telegram_token/chat_id (TradingConfig factory 주입값)
          → SecretsManager.telegram_token(domain)
        - 도메인 토큰이 전혀 없으면 알림을 건너뛴다. generic TELEGRAM_BOT_TOKEN으로
          silent fallback 하지 않는다(선물 메시지가 주식 채널로 새는 것을 방지).
        """
        if not self.config.enable_telegram:
            logger.info(f"Notification (telegram disabled): {message}")
            return

        try:
            from services.monitoring.notifier import TelegramConfig, TelegramNotifier
            from shared.notification.telegram import resolve_domain_credentials

            domain = (
                self.config.asset_class
                if self.config.asset_class in ("stock", "futures")
                else None
            )

            # 1) TradingConfig factory 주입값이 최우선
            token = self.config.telegram_token
            chat_id = self.config.telegram_chat_id

            # 2) 주입값이 없으면 도메인별 env에서 strict 조회 (legacy fallback 없음)
            if not token or not chat_id:
                env_token, env_chat = resolve_domain_credentials(domain)
                token = token or env_token
                chat_id = chat_id or env_chat

            if not token or not chat_id:
                logger.warning(
                    "Telegram not configured for domain=%s, skipping notification",
                    domain,
                )
                return

            config = TelegramConfig(token=token, chat_id=chat_id)
            notifier = TelegramNotifier(config)
            try:
                success = await notifier.send(message)
                if not success:
                    logger.warning(
                        f"Failed to send telegram notification: {message[:50]}..."
                    )
            finally:
                await notifier.close()

        except ImportError:
            logger.debug("TelegramNotifier not available")
        except (
            NetworkError,
            OSError,
            ConnectionError,
            TimeoutError,
            ConfigurationError,
        ) as e:
            logger.error(f"Notification error: {e}")

    def _get_account_summary(self) -> dict[str, Any] | None:
        """Paper broker의 현금/equity/실현손익을 status 응답용으로 묶는다.

        Live 모드 또는 broker 미연결 시 None.  KIS 선물 모의서버는 잔고조회
        (CTFO6118R) 미지원이므로 이 헬퍼는 paper engine 전용이다.

        ``get_status()``는 observability path라 broker 측 일시 오류로 status
        전체를 깨면 안 된다 — broker 호출에서 어떤 예외가 발생해도 흡수하고
        ``None``을 돌려준다 (status 응답에 ``account`` 키가 빠지는 형태).
        """
        broker = self._paper_broker
        if broker is None:
            return None

        summary: dict[str, Any] = {}
        if hasattr(broker, "get_summary"):
            try:
                raw = broker.get_summary() or {}
                summary["initial_balance"] = float(raw.get("initial_balance", 0.0))
                summary["balance"] = float(raw.get("balance", 0.0))
                summary["equity"] = float(raw.get("equity", summary["balance"]))
                summary["realized_pnl"] = float(raw.get("total_pnl", 0.0))
                summary["open_positions"] = int(raw.get("open_positions", 0))
            except Exception as exc:
                logger.warning(f"paper broker get_summary() failed: {exc}")
                summary = {}

        if not summary:
            try:
                balance = getattr(broker, "balance", None)
                initial = getattr(broker, "initial_balance", None)
                equity_fn = getattr(broker, "get_equity", None)
                summary["initial_balance"] = (
                    float(initial)
                    if initial is not None
                    else float(self.config.initial_capital)
                )
                summary["balance"] = (
                    float(balance)
                    if balance is not None
                    else summary["initial_balance"]
                )
                summary["equity"] = (
                    float(equity_fn()) if callable(equity_fn) else summary["balance"]
                )
                summary["realized_pnl"] = (
                    summary["balance"] - summary["initial_balance"]
                )
                summary["open_positions"] = len(getattr(broker, "positions", {}) or {})
            except Exception as exc:
                logger.warning(f"paper broker fallback summary failed: {exc}")
                return None

        summary["unrealized_pnl"] = summary["equity"] - summary["balance"]
        return summary

    def _get_risk_summary(self) -> dict[str, Any] | None:
        """RiskManager status for Redis/dashboard verification."""
        manager = self._risk_manager
        if manager is None:
            return None
        try:
            state = manager.get_risk_state()
            metrics = manager.get_portfolio_metrics()
            return {
                "initial_capital": float(manager.config.initial_capital),
                "daily_loss_limit_pct": float(manager.config.daily_loss_limit_pct),
                "max_total_positions": int(manager.config.max_total_positions),
                "state": state.to_dict(),
                "metrics": metrics.to_dict(),
            }
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning("risk summary unavailable: %s", exc)
            return None

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
        tick_stream_stats = (
            self._tick_stream_publisher.get_stats()
            if self._tick_stream_publisher
            else {}
        )

        status: dict[str, Any] = {
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
                "entry_slippage_count": int(
                    self._entry_slippage_stats.get("count", 0.0)
                ),
                "entry_avg_adverse_ticks": float(
                    self._entry_slippage_stats.get("avg_adverse_ticks", 0.0)
                ),
                "start_time": self.start_time.isoformat() if self.start_time else None,
            },
            "positions": position_stats,
            "strategies": strategy_info,
            "data_provider": data_stats,
            "tick_stream_publisher": tick_stream_stats,
            "pipeline": pipeline_status,
        }

        account = self._get_account_summary()
        if account is not None:
            status["account"] = account

        risk = self._get_risk_summary()
        if risk is not None:
            status["risk"] = risk

        return status

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
