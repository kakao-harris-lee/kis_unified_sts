"""공통 지표 계산기 모듈

두 프로젝트의 지표 계산기 통합:
- quant_moment_sts: OrderBook, VolumeAcceleration, VWAP, CompositeScore
- kospi_mini_sts: TechnicalCalculator (SMA, ATR, Ichimoku)

Usage:
    from shared.indicators import (
        TechnicalCalculator,
        OrderBookAnalyzer,
        VolumeAccelerationCalculator,
        VWAPCalculator,
    )

    # 기술적 지표
    tech = TechnicalCalculator(ma_fast_period=20, ma_slow_period=60)
    data = tech.update(high=100, low=99, close=99.5)

    # 호가 불균형
    ob = OrderBookAnalyzer()
    imbalance = ob.calculate(bid_prices, ask_prices, bid_volumes, ask_volumes)
"""

from shared.indicators.technical import (
    BarInput,
    TechnicalCalculator,
    TechnicalData,
)
from shared.indicators.orderbook import (
    OrderBookAnalyzer,
    OrderBookImbalance,
)
from shared.indicators.volume import (
    VolumeAcceleration,
    VolumeAccelerationCalculator,
    VWAPCalculator,
    VWAPData,
)
from shared.indicators.composite import (
    CompositeScoreCalculator,
    IndicatorConfig,
    ScoreResult,
)
from shared.indicators.momentum import (
    TRIXCalculator,
    CCICalculator,
    MACDCalculator,
    StochasticCalculator,
    RSICalculator,
    OBVDataFrameCalculator,
    DivergenceDetector,
    calculate_all_momentum,
)

__all__ = [
    # Technical
    "TechnicalCalculator",
    "TechnicalData",
    "BarInput",
    # OrderBook
    "OrderBookAnalyzer",
    "OrderBookImbalance",
    # Volume
    "VolumeAccelerationCalculator",
    "VolumeAcceleration",
    "VWAPCalculator",
    "VWAPData",
    # Composite
    "CompositeScoreCalculator",
    "ScoreResult",
    "IndicatorConfig",
    # Momentum
    "TRIXCalculator",
    "CCICalculator",
    "MACDCalculator",
    "StochasticCalculator",
    "RSICalculator",
    "OBVDataFrameCalculator",
    "DivergenceDetector",
    "calculate_all_momentum",
]
