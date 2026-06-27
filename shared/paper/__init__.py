"""Paper trading module.

This module provides virtual/paper trading capabilities for
strategy testing without real money.

Key components:
- VirtualBroker: Simulates order execution with realistic costs
- PaperTradingEngine: Full trading simulation with strategy support
- PaperTradingReport: Performance reporting and analytics
"""
from .broker import VirtualBroker
from .engine import PaperTradingEngine
from .models import (
    InsufficientBalanceError,
    OrderSide,
    OrderType,
    PositionSide,
    TradeRecord,
    VirtualOrder,
    VirtualPosition,
)
from .report import PaperTradingReport, create_report_from_broker

__all__ = [
    "VirtualBroker",
    "PaperTradingEngine",
    "PaperTradingReport",
    "create_report_from_broker",
    "VirtualOrder",
    "VirtualPosition",
    "TradeRecord",
    "OrderSide",
    "OrderType",
    "PositionSide",
    "InsufficientBalanceError",
]
