"""Data engine: merge ClickHouse history with real-time ticks into Polars windows."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def _require_polars():
    try:
        import polars as pl  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("polars is required for core.data_engine") from e
    return pl


def _parse_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


@dataclass
class _MinuteBar:
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


@dataclass(frozen=True)
class DataEngineConfig:
    max_bars: int = int(os.environ.get("DATA_ENGINE_MAX_BARS", "600"))
    timezone: str = os.environ.get("DATA_ENGINE_TIMEZONE", "Asia/Seoul")


class DataEngine:
    """Maintain per-symbol Polars windows and merge real-time ticks."""

    def __init__(self, config: DataEngineConfig | None = None):
        self.config = config or DataEngineConfig()
        self._lock = threading.RLock()
        self._frames: dict[str, Any] = {}
        self._builders: dict[str, _MinuteBar] = {}

        try:
            self._tz = ZoneInfo(self.config.timezone)
        except Exception:
            logger.warning(f"Unknown timezone '{self.config.timezone}', using UTC")
            self._tz = ZoneInfo("UTC")

    def load_history(self, code: str, rows: list[dict[str, Any]]) -> None:
        pl = _require_polars()
        if not code:
            return
        if not rows:
            return
        df = pl.DataFrame(rows).sort("datetime")
        with self._lock:
            self._frames[code] = df.tail(self.config.max_bars)

    def ingest_tick(self, payload: dict[str, Any]) -> None:
        code = (payload.get("symbol") or payload.get("code") or "").strip()
        if not code:
            return

        price = _parse_float(payload.get("current_price") or payload.get("price"))
        if price <= 0:
            return

        ts = _parse_float(payload.get("timestamp"))
        if ts <= 0:
            ts = datetime.now().timestamp()

        minute = (
            datetime.fromtimestamp(ts, tz=self._tz)
            .replace(second=0, microsecond=0, tzinfo=None)
        )

        vol = _parse_int(payload.get("tick_volume"))

        with self._lock:
            bar = self._builders.get(code)
            if bar is None:
                self._builders[code] = _MinuteBar(
                    code=code,
                    datetime=minute,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=max(0, vol),
                    value=int(price * max(0, vol)),
                )
                return

            if bar.datetime == minute:
                bar.update(price, vol)
                return

            self._append_bar_row(bar.to_row())
            self._builders[code] = _MinuteBar(
                code=code,
                datetime=minute,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=max(0, vol),
                value=int(price * max(0, vol)),
            )

    def _append_bar_row(self, row: dict[str, Any]) -> None:
        pl = _require_polars()
        code = str(row.get("code", "")).strip()
        if not code:
            return
        df = self._frames.get(code)
        if df is None:
            df = pl.DataFrame([row])
        else:
            df = pl.concat([df, pl.DataFrame([row])], how="vertical")
            df = (
                df.unique(subset=["datetime"], keep="last")
                .sort("datetime")
                .tail(self.config.max_bars)
            )
        self._frames[code] = df

    def get_frame(self, code: str):
        with self._lock:
            return self._frames.get(code)

    def get_frames(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._frames)

