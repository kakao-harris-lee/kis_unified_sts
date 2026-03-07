"""ClickHouse data models."""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class DailyCandle:
    """일봉 데이터"""
    code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    value: int  # 거래대금
    change_rate: float  # 등락률


@dataclass
class MinuteCandle:
    """분봉 데이터"""
    code: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    value: int


@dataclass
class TickData:
    """틱 데이터"""
    code: str
    datetime: datetime
    price: float
    volume: int
    bid_price: float
    ask_price: float
    cumulative_volume: int


@dataclass
class DriftMetrics:
    """RL model drift detection metrics"""
    timestamp: datetime
    code: str
    strategy: str
    kl_divergence: float
    psi_score: float
    confidence_mean: float
    confidence_std: float
    sharpe_5d: float = None
    sharpe_20d: float = None
    win_rate_5d: float = None
    win_rate_20d: float = None
