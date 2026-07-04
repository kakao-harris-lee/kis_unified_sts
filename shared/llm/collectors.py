"""Korean Financial Data Collectors.

This module is kept as the public compatibility facade. Implementation lives in
smaller collector modules grouped by data-source family so callers can inspect a
single responsibility without loading the entire collector stack.
"""

from __future__ import annotations

from datetime import datetime as datetime  # noqa: F401 - compatibility monkeypatch hook

from .collector_base import DataCollector
from .futures_collectors import (
    FuturesEventCollector,
    FuturesFlowCollector,
    FuturesGlobalCollector,
)
from .krx_data_collector import KRXDataCollector
from .market_data_collectors import (
    DARTDataCollector,
    KOFIADataCollector,
    KSDDataCollector,
    SEIBRODataCollector,
)
from .news_collectors import MKStockNewsCollector, NaverFinanceNewsCollector
from .stock_data_collector import StockDataCollector

__all__ = [
    "DataCollector",
    "StockDataCollector",
    "KRXDataCollector",
    "SEIBRODataCollector",
    "DARTDataCollector",
    "KSDDataCollector",
    "KOFIADataCollector",
    "MKStockNewsCollector",
    "NaverFinanceNewsCollector",
    "FuturesGlobalCollector",
    "FuturesFlowCollector",
    "FuturesEventCollector",
    "collect_krx_data",
    "collect_seibro_data",
    "collect_dart_data",
    "collect_ksd_data",
    "collect_kofia_data",
    "collect_mk_news",
]


def collect_krx_data() -> dict:
    """KRX 데이터 수집 헬퍼"""
    collector = KRXDataCollector()
    return collector.collect()


def collect_seibro_data(code: str = None) -> dict:
    """SEIBRO 데이터 수집 헬퍼"""
    collector = SEIBRODataCollector()
    return collector.collect(code)


def collect_dart_data(corp_code: str = None, api_key: str = None) -> dict:
    """DART 데이터 수집 헬퍼"""
    collector = DARTDataCollector(api_key)
    return collector.collect(corp_code)


def collect_ksd_data(code: str = None) -> dict:
    """KSD 데이터 수집 헬퍼"""
    collector = KSDDataCollector()
    return collector.collect(code)


def collect_kofia_data() -> dict:
    """KOFIA 데이터 수집 헬퍼"""
    collector = KOFIADataCollector()
    return collector.collect()


def collect_mk_news(code: str = None) -> dict:
    """MK Stock 뉴스 수집 헬퍼"""
    collector = MKStockNewsCollector()
    return collector.collect(code)
