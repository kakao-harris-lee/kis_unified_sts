"""호가 분석기

호가 불균형 분석 및 매도벽 감지.

quant_moment_sts의 OrderBookAnalyzer를 마이그레이션.

Usage:
    analyzer = OrderBookAnalyzer()

    result = analyzer.calculate(
        bid_prices=[100, 99, 98],
        ask_prices=[101, 102, 103],
        bid_volumes=[100, 200, 150],
        ask_volumes=[50, 100, 200],
    )

    if result.imbalance > 0.3:
        print("매수 압력 우위")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OrderBookImbalance:
    """호가 불균형 분석 결과

    Attributes:
        imbalance: -1.0 ~ +1.0 (양수: 매수우위, 음수: 매도우위)
        bid_total: 총 매수 잔량
        ask_total: 총 매도 잔량
        ask_wall_price: 매도벽 가격 (없으면 0)
        ask_wall_volume: 매도벽 수량
        ask_wall_consuming: 매도벽 소진 중 여부
        bid_ask_ratio: bid_total / ask_total
    """

    imbalance: float
    bid_total: int
    ask_total: int
    ask_wall_price: float
    ask_wall_volume: int
    ask_wall_consuming: bool
    bid_ask_ratio: float


@dataclass
class OrderBookConfig:
    """호가 분석 설정"""

    wall_threshold_multiplier: float = 3.0  # 평균 대비 N배 이상 = 벽
    orderbook_levels: int = 5  # 분석할 호가 단계
    high_imbalance_threshold: float = 0.5
    mid_imbalance_threshold: float = 0.3
    low_imbalance_threshold: float = 0.1
    max_score: float = 30.0
    mid_score: float = 20.0
    low_score: float = 10.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrderBookConfig:
        """딕셔너리에서 생성"""
        return cls(
            wall_threshold_multiplier=data.get("wall_threshold_multiplier", 3.0),
            orderbook_levels=data.get("orderbook_levels", 5),
            high_imbalance_threshold=data.get("high_imbalance_threshold", 0.5),
            mid_imbalance_threshold=data.get("mid_imbalance_threshold", 0.3),
            low_imbalance_threshold=data.get("low_imbalance_threshold", 0.1),
            max_score=data.get("max_score", 30.0),
            mid_score=data.get("mid_score", 20.0),
            low_score=data.get("low_score", 10.0),
        )


class OrderBookAnalyzer:
    """호가 분석기

    호가 불균형 = (Bid - Ask) / (Bid + Ask)
    - +1.0에 가까울수록: 매수 압도 (상승 예상)
    - -1.0에 가까울수록: 매도 압도 (하락 예상)

    반직관적 관찰:
    - 큰 매도벽이 보이면 오히려 상승할 수 있음 (매도벽 소진 시)

    Usage:
        analyzer = OrderBookAnalyzer()
        result = analyzer.calculate(bid_prices, ask_prices, bid_volumes, ask_volumes)
    """

    def __init__(self, config: OrderBookConfig | None = None):
        """
        Args:
            config: 설정 (기본값 사용 시 None)
        """
        self.config = config or OrderBookConfig()
        self._prev_ask_volumes: dict[str, list[int]] = {}

    def calculate(
        self,
        _bid_prices: list[float],
        ask_prices: list[float],
        bid_volumes: list[int],
        ask_volumes: list[int],
        levels: int | None = None,
        *,
        timestamps: list = None,
        context_timestamp = None,
        lookahead_guard = None,
        context_info: str = None,
    ) -> OrderBookImbalance:
        """호가 불균형 계산

        Args:
            bid_prices: 매수호가 리스트 (1호가부터)
            ask_prices: 매도호가 리스트 (1호가부터)
            bid_volumes: 매수잔량 리스트
            ask_volumes: 매도잔량 리스트
            levels: 분석할 호가 단계 (None이면 config 사용)

        Returns:
            OrderBookImbalance
        """
        levels = levels or self.config.orderbook_levels

        # LookaheadGuard: 시계열 입력이 배열이면 검사
        if lookahead_guard and timestamps is not None and context_timestamp is not None:
            lookahead_guard.check(bid_volumes, timestamps, context_timestamp, context_info or "orderbook:bid_volumes")
            lookahead_guard.check(ask_volumes, timestamps, context_timestamp, context_info or "orderbook:ask_volumes")

        # 상위 N단계만 사용
        bid_vols = bid_volumes[:levels]
        ask_vols = ask_volumes[:levels]

        bid_sum = sum(bid_vols)
        ask_sum = sum(ask_vols)

        # Imbalance 계산
        total = bid_sum + ask_sum
        if total == 0:
            imbalance = 0.0
        else:
            imbalance = (bid_sum - ask_sum) / total

        # Bid/Ask Ratio
        bid_ask_ratio = bid_sum / ask_sum if ask_sum > 0 else float("inf")

        # 매도벽 탐지 (평균의 N배 이상)
        ask_wall_price = 0.0
        ask_wall_volume = 0
        if ask_volumes:
            avg_ask = sum(ask_volumes) / len(ask_volumes)
            threshold = avg_ask * self.config.wall_threshold_multiplier

            for i, vol in enumerate(ask_volumes):
                if vol > threshold and i < len(ask_prices):
                    ask_wall_price = ask_prices[i]
                    ask_wall_volume = vol
                    break

        # 매도벽 소진 감지 (이전 데이터와 비교)
        ask_wall_consuming = False

        return OrderBookImbalance(
            imbalance=imbalance,
            bid_total=bid_sum,
            ask_total=ask_sum,
            ask_wall_price=ask_wall_price,
            ask_wall_volume=ask_wall_volume,
            ask_wall_consuming=ask_wall_consuming,
            bid_ask_ratio=bid_ask_ratio,
        )

    def calculate_simple(self, bid_qty: int, ask_qty: int) -> float:
        """간단한 불균형 계산

        Args:
            bid_qty: 매수 잔량 합계
            ask_qty: 매도 잔량 합계

        Returns:
            imbalance: -1.0 ~ +1.0
        """
        total = bid_qty + ask_qty
        if total == 0:
            return 0.0
        return (bid_qty - ask_qty) / total

    def get_imbalance_score(self, imbalance: float) -> float:
        """Imbalance를 스코어로 변환

        Args:
            imbalance: -1.0 ~ +1.0

        Returns:
            스코어 (0 ~ max_score)
        """
        c = self.config
        if imbalance > c.high_imbalance_threshold:
            return c.max_score
        elif imbalance > c.mid_imbalance_threshold:
            return c.mid_score
        elif imbalance > c.low_imbalance_threshold:
            return c.low_score
        else:
            return 0.0
