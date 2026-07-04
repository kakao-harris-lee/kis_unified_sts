"""Compatibility facade for futures collectors."""

from __future__ import annotations

from .futures_event_collector import FuturesEventCollector
from .futures_flow_collector import FuturesFlowCollector
from .futures_global_collector import FuturesGlobalCollector

__all__ = [
    "FuturesGlobalCollector",
    "FuturesFlowCollector",
    "FuturesEventCollector",
]
