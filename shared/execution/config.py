"""Order execution configuration."""
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .tr_ids import tr_id


class TradingMode(str, Enum):
    """Trading mode enumeration."""
    PAPER = "PAPER"   # Local simulation (no API calls)
    MOCK = "MOCK"     # KIS 모의투자 API
    REAL = "REAL"     # KIS 실전투자 API


class ExecutionVenuePreference(str, Enum):
    """Execution venue preference for time-of-day routing."""
    KRX = "KRX"       # Prefer KRX
    ATS = "ATS"       # Prefer ATS (넥스트레이드)
    AUTO = "AUTO"     # Auto-select based on routing rules


class ATSSimulationConfig(BaseModel):
    """ATS simulation parameters for backtest/paper trading."""

    model_config = ConfigDict(use_enum_values=True)

    ats_fill_rate: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="ATS average fill rate (default: 65%)"
    )
    price_improvement_mean_bps: float = Field(
        default=3.0,
        ge=0.0,
        le=50.0,
        description="Mean price improvement in basis points"
    )
    price_improvement_std_bps: float = Field(
        default=2.0,
        ge=0.0,
        le=20.0,
        description="Standard deviation of price improvement"
    )
    latency_penalty_ms: float = Field(
        default=15.0,
        ge=0.0,
        le=1000.0,
        description="Additional latency penalty for ATS execution (milliseconds)"
    )


class ATSRoutingConfig(BaseModel):
    """Korean ATS (넥스트레이드) routing configuration."""

    model_config = ConfigDict(use_enum_values=True)

    enabled: bool = Field(
        default=False,
        description="Enable ATS routing (default: disabled)"
    )
    default_venue: str = Field(
        default="KRX",
        description="Default execution venue (KRX | ATS)"
    )

    # Rule 1: Price improvement threshold
    price_improvement_threshold_bps: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Minimum price improvement for ATS selection (basis points)"
    )

    # Rule 2: Liquidity requirements
    min_liquidity_depth: float = Field(
        default=100.0,
        ge=0.0,
        description="Minimum quote depth (shares)"
    )
    min_depth_multiplier: float = Field(
        default=2.0,
        ge=0.0,
        le=100.0,
        description="Minimum depth as multiple of order size"
    )

    # Rule 3: Spread limits
    max_spread_bps: float = Field(
        default=30.0,
        ge=0.0,
        le=1000.0,
        description="Maximum spread for ATS usage (basis points)"
    )
    spread_comparison_enabled: bool = Field(
        default=True,
        description="Enable KRX vs ATS spread comparison"
    )
    spread_comparison_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=10.0,
        description="ATS spread must be within this multiple of KRX spread"
    )

    # Rule 4: Fill rate model
    ats_fill_rate_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum fill probability threshold"
    )
    prefer_certainty: bool = Field(
        default=True,
        description="Prefer KRX when fill uncertainty is high"
    )

    # Rule 5: Time-of-day preferences
    time_of_day_preferences: dict[str, str] = Field(
        default_factory=dict,
        description="Time window preferences (HH:MM-HH:MM -> KRX|ATS|AUTO)"
    )

    # Rule 6: Stock filters
    min_market_cap: float = Field(
        default=1_000_000_000_000,  # 1 trillion KRW
        ge=0.0,
        description="Minimum market cap for ATS routing"
    )
    excluded_sectors: list[str] = Field(
        default_factory=list,
        description="Excluded sectors (e.g. ['금융', '보험'])"
    )

    # Simulation parameters
    simulation: ATSSimulationConfig = Field(
        default_factory=ATSSimulationConfig,
        description="Simulation parameters for backtest/paper trading"
    )

    @field_validator("default_venue")
    @classmethod
    def validate_default_venue(cls, v: str) -> str:
        """Validate default venue is KRX or ATS."""
        if v not in ("KRX", "ATS"):
            raise ValueError(
                f"Default venue must be 'KRX' or 'ATS', got: {v!r}"
            )
        return v

    @field_validator("time_of_day_preferences")
    @classmethod
    def validate_time_preferences(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate time window format and venue values."""
        import re as regex_module

        time_window_pattern = r"^\d{2}:\d{2}-\d{2}:\d{2}$"
        valid_venues = {"KRX", "ATS", "AUTO"}

        for window, venue in v.items():
            if not regex_module.match(time_window_pattern, window):
                raise ValueError(
                    f"Time window must be in HH:MM-HH:MM format, got: {window!r}"
                )
            if venue not in valid_venues:
                raise ValueError(
                    f"Venue preference must be KRX, ATS, or AUTO, got: {venue!r}"
                )
        return v


class ExecutionConfig(BaseModel):
    """Order execution configuration."""

    model_config = ConfigDict(use_enum_values=True)

    trading_mode: str = Field(
        default="PAPER",
        description="Trading mode: PAPER, MOCK, or REAL"
    )

    # Retry settings
    max_retries: int = Field(default=3, description="Max retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retries (seconds)")

    # Order request timeout
    order_request_timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        le=60.0,
        description="Timeout for order requests (seconds)"
    )

    # Futures fill monitoring/cancel (live-safe execution)
    futures_fill_check_enabled: bool = Field(
        default=True,
        description="Enable futures fill inquiry loop after order submission"
    )
    futures_fill_check_poll_interval_seconds: float = Field(
        default=0.2,
        ge=0.05,
        le=5.0,
        description="Polling interval for futures fill inquiry (seconds)"
    )
    futures_fill_check_timeout_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Timeout waiting for futures fill before cancel (seconds)"
    )
    futures_auto_cancel_unfilled: bool = Field(
        default=True,
        description="Cancel unfilled futures order when timeout is reached"
    )

    # Rate limiting (Redis-based distributed limiter)
    redis_url: str = Field(
        default="",
        description="Redis URL for distributed rate limiting (empty = no rate limiting)"
    )
    rate_limit_key: str = Field(
        default="default",
        description="Rate limit key prefix: 'stock', 'futures', or custom"
    )
    requests_per_second: float = Field(
        default=20.0,
        description="Max API requests per second (KIS limit)"
    )
    rate_limit_timeout: float = Field(
        default=5.0,
        description="Max wait time when rate limited (seconds)"
    )

    # Rate limit retry behavior (configurable backoff)
    rate_limit_initial_delay: float = Field(
        default=0.05,
        ge=0.01,
        le=1.0,
        description="Initial retry delay when rate limited (seconds)"
    )
    rate_limit_max_delay: float = Field(
        default=0.2,
        ge=0.05,
        le=5.0,
        description="Maximum retry delay cap (seconds)"
    )
    rate_limit_backoff_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=3.0,
        description="Backoff multiplier for retry delays"
    )

    # Metrics caching
    metrics_cache_ttl: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="TTL for cached metrics (seconds)"
    )

    # Account info (loaded from environment)
    account_no: str = Field(default="", description="Account number (10 digits)")

    # Circuit breaker settings
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of consecutive failures before opening circuit"
    )
    circuit_breaker_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Time to wait before attempting to close circuit (seconds)"
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v:
            return v  # Empty is allowed (disables rate limiting)
        # Accept redis:// or rediss:// (TLS) schemes
        if not re.match(r"^rediss?://", v):
            raise ValueError(
                f"Redis URL must start with 'redis://' or 'rediss://', got: {v!r}"
            )
        return v

    @field_validator("account_no")
    @classmethod
    def validate_account_no(cls, v: str) -> str:
        """Validate account number format (auto-strips dashes)."""
        if not v:
            return v  # Empty is allowed (for PAPER mode)
        v = v.replace("-", "")
        if not re.match(r"^\d{10}$", v):
            raise ValueError(
                f"Account number must be exactly 10 digits, got: {v!r}"
            )
        return v

    @field_validator("rate_limit_key")
    @classmethod
    def validate_rate_limit_key(cls, v: str) -> str:
        """Validate rate limit key contains only safe characters."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                f"Rate limit key must contain only alphanumeric, underscore, "
                f"or dash characters, got: {v!r}"
            )
        return v

    # KIS API endpoints (configurable for testing/environment flexibility)
    kis_mock_base_url: str = Field(
        default="https://openapivts.koreainvestment.com:29443",
        description="KIS 모의투자 API base URL"
    )
    kis_real_base_url: str = Field(
        default="https://openapi.koreainvestment.com:9443",
        description="KIS 실전투자 API base URL"
    )

    # KIS TR codes (single source of truth: config/kis/tr_ids.yaml).
    # default_factory loads the YAML-merged value at instance construction;
    # missing keys fall back to the baked _DEFAULTS in shared/execution/tr_ids.py.
    # See docs/runbooks/futures-legal-review.md §3 for the operator audit.
    tr_code_buy_mock: str = Field(
        default_factory=lambda: tr_id("stock_krx_buy_mock"),
        description="TR code for mock buy order",
    )
    tr_code_buy_real: str = Field(
        default_factory=lambda: tr_id("stock_krx_buy_real"),
        description="TR code for real buy order",
    )
    tr_code_sell_mock: str = Field(
        default_factory=lambda: tr_id("stock_krx_sell_mock"),
        description="TR code for mock sell order",
    )
    tr_code_sell_real: str = Field(
        default_factory=lambda: tr_id("stock_krx_sell_real"),
        description="TR code for real sell order",
    )

    # KIS TR codes for ATS orders
    tr_code_ats_buy_mock: str = Field(
        default_factory=lambda: tr_id("stock_ats_buy_mock"),
        description="TR code for ATS mock buy order",
    )
    tr_code_ats_buy_real: str = Field(
        default_factory=lambda: tr_id("stock_ats_buy_real"),
        description="TR code for ATS real buy order",
    )
    tr_code_ats_sell_mock: str = Field(
        default_factory=lambda: tr_id("stock_ats_sell_mock"),
        description="TR code for ATS mock sell order",
    )
    tr_code_ats_sell_real: str = Field(
        default_factory=lambda: tr_id("stock_ats_sell_real"),
        description="TR code for ATS real sell order",
    )

    # Futures order TR IDs (KIS [국내선물옵션] 주문/계좌 기준)
    futures_tr_code_order_day_mock: str = Field(
        default_factory=lambda: tr_id("futures_order_day_mock"),
        description="Futures day order TR code for mock",
    )
    futures_tr_code_order_day_real: str = Field(
        default_factory=lambda: tr_id("futures_order_day_real"),
        description="Futures day order TR code for real",
    )
    futures_tr_code_order_night_real: str = Field(
        default_factory=lambda: tr_id("futures_order_night_real"),
        description="Futures night order TR code for real",
    )

    futures_tr_code_cancel_day_mock: str = Field(
        default_factory=lambda: tr_id("futures_cancel_day_mock"),
        description="Futures day cancel TR code for mock",
    )
    futures_tr_code_cancel_day_real: str = Field(
        default_factory=lambda: tr_id("futures_cancel_day_real"),
        description="Futures day cancel TR code for real",
    )
    futures_tr_code_cancel_night_real: str = Field(
        default_factory=lambda: tr_id("futures_cancel_night_real"),
        description="Futures night cancel TR code for real",
    )

    futures_tr_code_inquire_day_mock: str = Field(
        default_factory=lambda: tr_id("futures_inquire_day_mock"),
        description="Futures day fill inquiry TR code for mock",
    )
    futures_tr_code_inquire_day_real: str = Field(
        default_factory=lambda: tr_id("futures_inquire_day_real"),
        description="Futures day fill inquiry TR code for real",
    )
    futures_tr_code_inquire_night_real: str = Field(
        default_factory=lambda: tr_id("futures_inquire_night_real"),
        description="Futures night fill inquiry TR code for real",
    )
