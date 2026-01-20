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

    # Rate limiting
    orders_per_second: float = Field(default=5.0, description="Max orders per second")

    # Account info (loaded from environment)
    account_no: str = Field(default="", description="Account number")
