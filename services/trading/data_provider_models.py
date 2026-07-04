"""Small data-provider model types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class DataSourceMode(Enum):
    """Data source operational mode for failover state machine"""

    WEBSOCKET = "websocket"
    REST_FALLBACK = "rest_fallback"


@runtime_checkable
class MarketDataSource(Protocol):
    """Protocol for market data sources (KIS, mock, etc.)

    Implement this protocol to create custom data sources.

    Example:
        class CustomDataSource:
            async def get_current_price(self, symbol: str) -> dict[str, Any]:
                return {"close": 50000, "volume": 1000}

        provider = MarketDataProvider(
            symbols=["005930"],
            data_source=CustomDataSource(),
        )
    """

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a symbol."""
        ...


@dataclass
class MarketDataCache:
    """Cached market data for a symbol"""

    symbol: str
    data: dict[str, Any]
    fetched_at: datetime
    indicators: dict[str, float] = field(default_factory=dict)

    def is_stale(self, ttl_seconds: float) -> bool:
        """Check if cache is stale (tz-aware-safe)."""
        fetched = self.fetched_at
        if fetched.tzinfo is None:
            now = datetime.now()
        else:
            now = datetime.now(UTC)
            fetched = fetched.astimezone(UTC)
        age = (now - fetched).total_seconds()
        return age > ttl_seconds
