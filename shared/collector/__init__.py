"""Data collector module for real-time market data ingestion.

This module provides:
    - TickData: Data model for tick/orderbook data
    - BaseAPIAdapter: Abstract adapter interface
    - MockAPIAdapter: Mock adapter for testing
    - DataCollector: Main collector class with Redis publishing

Usage:
    >>> from shared.collector import DataCollector, TickData
    >>> from shared.kis.websocket import KISWebSocketAdapter, create_websocket_adapter
    >>>
    >>> adapter = create_websocket_adapter(is_real=True)
    >>> collector = DataCollector(adapter)
    >>> collector.start(["101V01"])  # KOSPI200 Mini
"""

from shared.collector.adapter import BaseAPIAdapter, MockAPIAdapter
from shared.collector.collector import DataCollector
from shared.collector.models import TickData

__all__ = [
    "TickData",
    "BaseAPIAdapter",
    "MockAPIAdapter",
    "DataCollector",
]
