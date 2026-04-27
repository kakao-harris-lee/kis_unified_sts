"""Order execution result returned by the execution layer.

Phase 4 Task 2 — frozen dataclass + state enum used by every execution-layer
method (passive maker, force-close, OCO, etc.) so callers can branch on
:class:`OrderState` instead of parsing dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OrderState(str, Enum):
    FILLED = "filled"
    MISSED = "missed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class OrderResult:
    state: OrderState
    order_id: str | None = None
    filled_price: float | None = None
    slippage_ticks: float | None = None
    reason: str | None = None

    @classmethod
    def filled(cls, fill: Any, *, slippage_ticks: float) -> OrderResult:
        return cls(
            state=OrderState.FILLED,
            order_id=getattr(fill, "order_id", None),
            filled_price=float(fill.price),
            slippage_ticks=float(slippage_ticks),
        )

    @classmethod
    def missed(cls, *, reason: str, order_id: str | None = None) -> OrderResult:
        return cls(state=OrderState.MISSED, order_id=order_id, reason=reason)

    @classmethod
    def cancelled(cls, *, reason: str, order_id: str | None = None) -> OrderResult:
        return cls(state=OrderState.CANCELLED, order_id=order_id, reason=reason)

    @classmethod
    def error(cls, *, reason: str, order_id: str | None = None) -> OrderResult:
        return cls(state=OrderState.ERROR, order_id=order_id, reason=reason)

    @property
    def is_filled(self) -> bool:
        return self.state is OrderState.FILLED

    @property
    def is_missed(self) -> bool:
        return self.state is OrderState.MISSED

    @property
    def is_cancelled(self) -> bool:
        return self.state is OrderState.CANCELLED

    @property
    def is_error(self) -> bool:
        return self.state is OrderState.ERROR
