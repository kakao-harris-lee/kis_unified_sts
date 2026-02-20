"""브로커 잔고 데이터 모델

KIS API에서 조회한 실제 브로커 포지션.
Redis 복구 포지션과 교차 검증할 때 사용.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.position import PositionSide


@dataclass
class BrokerPosition:
    """KIS 브로커에서 조회한 실제 잔고.

    Attributes:
        code: 종목코드
        name: 종목명
        side: 포지션 방향 (LONG/SHORT)
        quantity: 보유수량
        avg_price: 매입평균가
        current_price: 현재가
        unrealized_pnl: 평가손익
    """

    code: str
    name: str
    side: PositionSide
    quantity: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
