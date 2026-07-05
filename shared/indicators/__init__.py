"""공통 지표 계산기 모듈.

Usage:
    from shared.indicators import (
        OrderBookAnalyzer,
        VolumeAccelerationCalculator,
        VWAPCalculator,
    )

    # 호가 불균형
    ob = OrderBookAnalyzer()
    imbalance = ob.calculate(bid_prices, ask_prices, bid_volumes, ask_volumes)
"""

from shared.indicators.contracts import (
    IndicatorContract,
    IndicatorKind,
    IndicatorRequest,
    Timeframe,
)
from shared.indicators.momentum import (
    CCICalculator,
    DivergenceDetector,
    MACDCalculator,
    OBVDataFrameCalculator,
    RSICalculator,
    StochasticCalculator,
    TRIXCalculator,
    calculate_all_momentum,
)
from shared.indicators.orderbook import (
    OrderBookAnalyzer,
    OrderBookImbalance,
)
from shared.indicators.resolver import StreamingIndicatorResolver
from shared.indicators.volume import (
    VolumeAcceleration,
    VolumeAccelerationCalculator,
    VWAPCalculator,
    VWAPData,
)

__all__ = [
    # OrderBook
    "OrderBookAnalyzer",
    "OrderBookImbalance",
    # Volume
    "VolumeAccelerationCalculator",
    "VolumeAcceleration",
    "VWAPCalculator",
    "VWAPData",
    # Momentum
    "TRIXCalculator",
    "CCICalculator",
    "MACDCalculator",
    "StochasticCalculator",
    "RSICalculator",
    "OBVDataFrameCalculator",
    "DivergenceDetector",
    "calculate_all_momentum",
    # Contracts / resolver
    "IndicatorKind",
    "Timeframe",
    "IndicatorRequest",
    "IndicatorContract",
    "StreamingIndicatorResolver",
]
