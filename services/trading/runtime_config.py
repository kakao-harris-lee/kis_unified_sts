"""Runtime configuration models for the trading orchestrator."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from services.trading.session_calendar import MarketSchedule

logger = logging.getLogger(__name__)

# Validation constants
MIN_INITIAL_CAPITAL = 100_000  # 10만원 minimum
MAX_INITIAL_CAPITAL = 100_000_000_000  # 1000억원 maximum
MIN_ORDER_AMOUNT = 10_000  # 1만원 minimum per trade
MAX_ORDER_AMOUNT = 100_000_000  # 1억원 maximum per trade
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
                # Coerce numeric strings — env-interpolated YAML (``${VAR:180}``)
                # arrives as a string, so a strict isinstance check would disable
                # the whole guard on any env-overridable cooldown.
                try:
                    value = float(seconds)
                except (TypeError, ValueError):
                    raise TypeError(
                        "entry_reentry_guard.reason_cooldown_seconds values "
                        f"must be numeric, got {type(seconds)} for {reason}"
                    ) from None
                if value < 0:
                    raise ValueError(
                        "entry_reentry_guard.reason_cooldown_seconds values "
                        f"must be non-negative, got {seconds} for {reason}"
                    )
                reasons[str(reason).lower()] = value

        raw_default = raw.get("default_cooldown_seconds", 900.0)
        try:
            default_cooldown = float(raw_default)
        except (TypeError, ValueError):
            raise TypeError(
                "entry_reentry_guard.default_cooldown_seconds must be numeric"
            ) from None
        if default_cooldown < 0:
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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def risk_params_for_runtime_capital(
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
    if (
        explicit_risk_capital is None
        or not explicit_risk_capital.strip()
        or "initial_capital" not in params
    ):
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
    swing_recovery_max_age_days: int = 7

    # Error recovery
    error_retry_delay_seconds: float = 60.0  # Retry delay after errors (default 1 min)

    # Candle cache persistence interval (seconds)
    candle_cache_save_interval: float = 60.0

    # Universe mode: "dynamic" (screener-driven, default) or "static" (daily watchlist)
    universe_mode: str = "dynamic"
    require_daily_indicators_for_dynamic_universe: bool = True
    include_daily_watchlist_in_dynamic_universe: bool = True
    allow_daily_watchlist_entry_before_intraday_warmup: bool = True
    prioritize_stock_entry_execution: bool = True
    regime_exclude_dip_candidates: bool = True
    regime_exclude_position_only_symbols: bool = True
    regime_require_daily_indicators: bool = True
    regime_require_mfi_symbols: bool = True
    regime_min_mfi_symbols: int = 8
    regime_min_mfi_coverage_ratio: float = 0.5
    regime_low_confidence_bear_fallback: str = "SIDEWAYS_DOWN"

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
        if not isinstance(self.include_daily_watchlist_in_dynamic_universe, bool):
            raise TypeError(
                "include_daily_watchlist_in_dynamic_universe must be bool, "
                f"got {type(self.include_daily_watchlist_in_dynamic_universe)}"
            )
        if not isinstance(
            self.allow_daily_watchlist_entry_before_intraday_warmup, bool
        ):
            raise TypeError(
                "allow_daily_watchlist_entry_before_intraday_warmup must be bool, "
                f"got {type(self.allow_daily_watchlist_entry_before_intraday_warmup)}"
            )
        if not isinstance(self.prioritize_stock_entry_execution, bool):
            raise TypeError(
                "prioritize_stock_entry_execution must be bool, "
                f"got {type(self.prioritize_stock_entry_execution)}"
            )
        for attr_name in (
            "regime_exclude_dip_candidates",
            "regime_exclude_position_only_symbols",
            "regime_require_daily_indicators",
            "regime_require_mfi_symbols",
        ):
            if not isinstance(getattr(self, attr_name), bool):
                raise TypeError(
                    f"{attr_name} must be bool, got {type(getattr(self, attr_name))}"
                )
        if self.regime_min_mfi_symbols < 1:
            raise ValueError("regime_min_mfi_symbols must be >= 1")
        if not (0.0 <= self.regime_min_mfi_coverage_ratio <= 1.0):
            raise ValueError("regime_min_mfi_coverage_ratio must be in [0, 1]")
        if not self.regime_low_confidence_bear_fallback:
            raise ValueError("regime_low_confidence_bear_fallback must be non-empty")

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
        include_daily_watchlist_in_dynamic_universe: bool | None = None,
        allow_daily_watchlist_entry_before_intraday_warmup: bool | None = None,
        prioritize_stock_entry_execution: bool | None = None,
        regime_exclude_dip_candidates: bool | None = None,
        regime_exclude_position_only_symbols: bool | None = None,
        regime_require_daily_indicators: bool | None = None,
        regime_require_mfi_symbols: bool | None = None,
        regime_min_mfi_symbols: int | None = None,
        regime_min_mfi_coverage_ratio: float | None = None,
        regime_low_confidence_bear_fallback: str | None = None,
    ) -> TradingConfig:
        """주식용 설정"""
        require_daily_indicators = (
            _env_bool("STOCK_REQUIRE_DAILY_INDICATORS_FOR_DYNAMIC_UNIVERSE", True)
            if require_daily_indicators_for_dynamic_universe is None
            else require_daily_indicators_for_dynamic_universe
        )
        include_daily_watchlist = (
            _env_bool("STOCK_INCLUDE_DAILY_WATCHLIST_IN_DYNAMIC_UNIVERSE", True)
            if include_daily_watchlist_in_dynamic_universe is None
            else include_daily_watchlist_in_dynamic_universe
        )
        allow_daily_warmup_bypass = (
            _env_bool("STOCK_ALLOW_DAILY_WATCHLIST_ENTRY_BEFORE_INTRADAY_WARMUP", True)
            if allow_daily_watchlist_entry_before_intraday_warmup is None
            else allow_daily_watchlist_entry_before_intraday_warmup
        )
        prioritize_entries = (
            _env_bool("STOCK_PRIORITIZE_ENTRY_EXECUTION", True)
            if prioritize_stock_entry_execution is None
            else prioritize_stock_entry_execution
        )
        exclude_dip_from_regime = (
            _env_bool("STOCK_REGIME_EXCLUDE_DIP_CANDIDATES", True)
            if regime_exclude_dip_candidates is None
            else regime_exclude_dip_candidates
        )
        exclude_position_only_from_regime = (
            _env_bool("STOCK_REGIME_EXCLUDE_POSITION_ONLY_SYMBOLS", True)
            if regime_exclude_position_only_symbols is None
            else regime_exclude_position_only_symbols
        )
        require_daily_for_regime = (
            _env_bool("STOCK_REGIME_REQUIRE_DAILY_INDICATORS", True)
            if regime_require_daily_indicators is None
            else regime_require_daily_indicators
        )
        require_mfi_for_regime = (
            _env_bool("STOCK_REGIME_REQUIRE_MFI_SYMBOLS", True)
            if regime_require_mfi_symbols is None
            else regime_require_mfi_symbols
        )
        min_mfi_symbols = (
            _env_int("STOCK_REGIME_MIN_MFI_SYMBOLS", 8)
            if regime_min_mfi_symbols is None
            else regime_min_mfi_symbols
        )
        min_mfi_coverage_ratio = (
            _env_float("STOCK_REGIME_MIN_MFI_COVERAGE_RATIO", 0.5)
            if regime_min_mfi_coverage_ratio is None
            else regime_min_mfi_coverage_ratio
        )
        low_confidence_bear_fallback = (
            os.getenv("STOCK_REGIME_LOW_CONFIDENCE_BEAR_FALLBACK", "SIDEWAYS_DOWN")
            if regime_low_confidence_bear_fallback is None
            else regime_low_confidence_bear_fallback
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
            include_daily_watchlist_in_dynamic_universe=include_daily_watchlist,
            allow_daily_watchlist_entry_before_intraday_warmup=allow_daily_warmup_bypass,
            prioritize_stock_entry_execution=prioritize_entries,
            regime_exclude_dip_candidates=exclude_dip_from_regime,
            regime_exclude_position_only_symbols=exclude_position_only_from_regime,
            regime_require_daily_indicators=require_daily_for_regime,
            regime_require_mfi_symbols=require_mfi_for_regime,
            regime_min_mfi_symbols=min_mfi_symbols,
            regime_min_mfi_coverage_ratio=min_mfi_coverage_ratio,
            regime_low_confidence_bear_fallback=low_confidence_bear_fallback,
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
        # Load the market schedule from config so that the session open/close
        # anchors (including the 08:45 futures open) reflect the YAML source of
        # truth rather than the old hardcoded 09:00 default.
        schedule = MarketSchedule.load_from_yaml()
        return cls(
            asset_class="futures",
            strategy_name=strategy_name,
            initial_capital=initial_capital,
            order_amount_per_trade=order_amount,
            symbols=symbols,
            telegram_token=os.getenv("TELEGRAM_FUTURES_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_FUTURES_CHAT_ID", ""),
            schedule=schedule,
        )

    @staticmethod
    def _get_futures_default_symbols() -> list[str]:
        """Get default KOSPI200 futures front-month symbol.

        Product is env-selectable via ``FUTURES_TRADING_PRODUCT``:
        - ``mini`` (default): KOSPI200 mini front-month (A05...) - the live product.
        - ``kospi200``: full-size F200 front-month (A01...) - tighter spread, used
          for paper signal validation (the mini's low liquidity blocks most
          entries on the wide-spread guard).
        """
        from shared.execution.futures_instrument import (
            resolve_futures_instrument_from_env,
        )

        instrument = resolve_futures_instrument_from_env()
        logger.info(
            "Futures default symbol (resolved): %s (product=%s source=%s)",
            instrument.symbol,
            instrument.product,
            instrument.source,
        )
        return [instrument.symbol]
