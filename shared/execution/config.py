"""Order execution configuration."""
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TradingMode(str, Enum):
    """Trading mode enumeration."""
    PAPER = "PAPER"   # Local simulation (no API calls)
    MOCK = "MOCK"     # KIS 모의투자 API
    REAL = "REAL"     # KIS 실전투자 API


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
        """Validate account number format."""
        if not v:
            return v  # Empty is allowed (for PAPER mode)
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

    # KIS TR codes for order types
    tr_code_buy_mock: str = Field(default="VTTC0802U", description="TR code for mock buy order")
    tr_code_buy_real: str = Field(default="TTTC0802U", description="TR code for real buy order")
    tr_code_sell_mock: str = Field(default="VTTC0801U", description="TR code for mock sell order")
    tr_code_sell_real: str = Field(default="TTTC0801U", description="TR code for real sell order")
