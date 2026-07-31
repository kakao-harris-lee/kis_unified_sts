"""Order execution models."""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OrderSide(StrEnum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Order type enumeration.

    KIS API order type codes:
    - 00: 지정가
    - 01: 시장가
    - 02: 조건부지정가
    """
    LIMIT = "00"      # 지정가
    MARKET = "01"     # 시장가
    CONDITIONAL = "02"  # 조건부지정가


class ExecutionVenue(StrEnum):
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
    price: float | None = Field(default=None, description="Limit price (required for LIMIT orders)")
    venue: ExecutionVenue = Field(default=ExecutionVenue.KRX, description="Execution venue")


class OrderResponse(BaseModel):
    """Order response model."""

    success: bool = Field(..., description="Whether order was successful")
    order_no: str | None = Field(default=None, description="Order number if successful")
    message: str = Field(default="", description="Response message")
    filled_qty: int = Field(default=0, description="Filled quantity")
    filled_price: float = Field(default=0.0, description="Average fill price")
    venue: ExecutionVenue = Field(default=ExecutionVenue.KRX, description="Execution venue")
    broker_msg_cd: str = Field(
        default="",
        description=(
            "Broker message code (KIS ``msg_cd``) carried verbatim from a "
            "rejected request. Empty when the broker returned none. Callers "
            "branch on this instead of substring-matching ``message``."
        ),
    )
    fill_state_unknown: bool = Field(
        default=False,
        description=(
            "True when the executed quantity could NOT be established (the "
            "fill-status query failed, or the broker's book contradicts our "
            "belief). ``filled_qty`` is then a lower bound, not a measurement: "
            "never read 0 as 'no fill' while this flag is set."
        ),
    )
