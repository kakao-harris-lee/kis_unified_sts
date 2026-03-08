"""Order execution models."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration.

    KIS API order type codes:
    - 00: 지정가
    - 01: 시장가
    - 02: 조건부지정가
    """
    LIMIT = "00"      # 지정가
    MARKET = "01"     # 시장가
    CONDITIONAL = "02"  # 조건부지정가


class ExecutionVenue(str, Enum):
    """Execution venue enumeration.

    Trading venues:
    - KRX: Korean Exchange (traditional exchange)
    - ATS: Alternative Trading System
    """
    KRX = "KRX"
    ATS = "ATS"


class OrderRequest(BaseModel):
    """Order request model."""

    model_config = ConfigDict(use_enum_values=True)

    code: str = Field(..., description="Stock/futures code")
    side: OrderSide = Field(..., description="BUY or SELL")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    quantity: int = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(default=None, description="Limit price (required for LIMIT orders)")
    venue: ExecutionVenue = Field(default=ExecutionVenue.KRX, description="Execution venue")


class OrderResponse(BaseModel):
    """Order response model."""

    success: bool = Field(..., description="Whether order was successful")
    order_no: Optional[str] = Field(default=None, description="Order number if successful")
    message: str = Field(default="", description="Response message")
    filled_qty: int = Field(default=0, description="Filled quantity")
    filled_price: float = Field(default=0.0, description="Average fill price")
    venue: ExecutionVenue = Field(default=ExecutionVenue.KRX, description="Execution venue")
