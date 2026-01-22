"""Order execution configuration."""
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


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

    # Account info (loaded from environment)
    account_no: str = Field(default="", description="Account number")

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
