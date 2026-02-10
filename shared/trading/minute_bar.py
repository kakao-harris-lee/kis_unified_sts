"""Shared minute bar model for tick aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MinuteBar:
    code: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    value: int

    def update(self, price: float, volume: int) -> None:
        self.close = price
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        if volume > 0:
            self.volume += volume
            self.value += int(price * volume)

    def to_row(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "datetime": self.datetime,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": int(self.volume),
            "value": int(self.value),
        }