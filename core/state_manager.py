"""State manager for stock real-time pipeline.

Responsibilities:
  - Subscribe to Redis Streams:
      - `market:ticks` (TickData-like payloads)
      - `system:universe` (list of candidate symbols)
  - When new symbols appear in universe:
      - Warm-up historical minute candles from ClickHouse
  - Merge incoming ticks into per-symbol OHLCV minute bars
  - Maintain per-symbol Polars DataFrames for strategy engines
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.config.loader import ConfigLoader
from shared.db.config import ClickHouseConfig
from shared.streaming.client import RedisClient
from shared.streaming.consumer import MultiStreamConsumer
from shared.streaming.message import StreamMessage
from shared.trading.minute_bar import MinuteBar
from shared.utils.parsing import parse_float, parse_int

logger = logging.getLogger(__name__)


def _require_polars():
    try:
        import polars as pl  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "polars is required for core.state_manager. Install it first."
        ) from e
    return pl


@dataclass(frozen=True)
class StateManagerConfig:
    tick_stream: str = os.environ.get("TICK_STREAM", "market:ticks")
    universe_stream: str = os.environ.get("UNIVERSE_STREAM", "system:universe")
    universe_latest_key: str = os.environ.get(
        "UNIVERSE_LATEST_KEY", "system:universe:latest"
    )

    consumer_group: str = os.environ.get("STATE_MANAGER_GROUP", "stock_state_manager")
    consumer_name: str | None = os.environ.get("STATE_MANAGER_CONSUMER", None)
    component_name: str | None = os.environ.get(
        "STATE_MANAGER_COMPONENT", "state_manager"
    )

    warmup_minutes: int = int(os.environ.get("STATE_WARMUP_MINUTES", "240"))
    max_bars: int = int(os.environ.get("STATE_MAX_BARS", "600"))
    timezone: str = os.environ.get("STATE_TIMEZONE", "Asia/Seoul")
    cleanup_removed_symbols: bool = (
        os.environ.get("STATE_CLEANUP_REMOVED", "true").lower() == "true"
    )

    # ConfigLoader path (relative to config dir)
    clickhouse_config_path: str = os.environ.get(
        "CLICKHOUSE_CONFIG_PATH", "clickhouse.yaml"
    )


class StateManager(MultiStreamConsumer):
    """Subscribes to universe + ticks, maintains per-symbol OHLCV frames."""

    def __init__(self, config: StateManagerConfig | None = None):
        self.config = config or StateManagerConfig()

        # MultiStreamConsumer requires same group for all streams.
        streams = {
            self.config.tick_stream: self.config.consumer_group,
            self.config.universe_stream: self.config.consumer_group,
        }
        super().__init__(
            streams=streams,
            consumer_name=self.config.consumer_name
            or f"{self.config.consumer_group}_1",
            component_name=self.config.component_name,
        )

        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None

        try:
            self._tz = ZoneInfo(self.config.timezone)
        except Exception:
            logger.warning(
                f"Unknown timezone '{self.config.timezone}', falling back to UTC"
            )
            self._tz = ZoneInfo("UTC")

        self._active_codes: set[str] = set()
        self._frames: dict[str, Any] = {}
        self._builders: dict[str, MinuteBar] = {}

        self._clickhouse_config: ClickHouseConfig | None = None

        # Bootstrap from latest universe snapshot if present (fast start)
        self._bootstrap_universe_from_latest_key()

    # ---------------------------------------------------------------------
    # Lifecycle helpers
    # ---------------------------------------------------------------------
    def start(self, *, daemon: bool = True) -> None:
        """Run the consumer loop in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self.run,
            name="state_manager",
            daemon=daemon,
        )
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    # ---------------------------------------------------------------------
    # Public API for strategy engines
    # ---------------------------------------------------------------------
    def get_active_codes(self) -> list[str]:
        with self._lock:
            return sorted(self._active_codes)

    def get_frame(self, code: str):
        with self._lock:
            return self._frames.get(code)

    def get_frames(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._frames)

    # ---------------------------------------------------------------------
    # Stream processing
    # ---------------------------------------------------------------------
    def process_message(self, message: StreamMessage) -> bool:
        if message.stream == self.config.universe_stream:
            self._handle_universe_message(message)
            return True

        if message.stream == self.config.tick_stream:
            self._handle_tick_message(message)
            return True

        return True

    def _bootstrap_universe_from_latest_key(self) -> None:
        try:
            raw = RedisClient.get_client().get(self.config.universe_latest_key)
            if not raw:
                return
            payload = json.loads(raw)
            codes = payload.get("codes", [])
            if isinstance(codes, list) and codes:
                self._apply_new_universe([str(c) for c in codes])
        except Exception as e:
            logger.debug(f"Universe bootstrap skipped: {e}")

    def _handle_universe_message(self, message: StreamMessage) -> None:
        payload = message.data
        codes = payload.get("codes", [])
        if not isinstance(codes, list):
            return
        self._apply_new_universe([str(c) for c in codes])

    def _apply_new_universe(self, codes: list[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for c in codes:
            s = (c or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            cleaned.append(s)

        if not cleaned:
            return

        with self._lock:
            prev = set(self._active_codes)
            new = set(cleaned)
            added = sorted(new - prev)
            removed = sorted(prev - new)
            self._active_codes = new

            if removed and self.config.cleanup_removed_symbols:
                for code in removed:
                    self._frames.pop(code, None)
                    self._builders.pop(code, None)

        if added:
            logger.info(f"Universe updated: +{len(added)} / -{len(removed)}")
            self._warmup_codes(added)

    def _handle_tick_message(self, message: StreamMessage) -> None:
        payload = message.data
        code = (payload.get("symbol") or payload.get("code") or "").strip()
        if not code:
            return

        with self._lock:
            if code not in self._active_codes:
                return

        price = parse_float(payload.get("current_price") or payload.get("price"))
        if price <= 0:
            return

        ts = parse_float(payload.get("timestamp") or message.timestamp)
        minute = datetime.fromtimestamp(ts, tz=self._tz).replace(
            second=0, microsecond=0, tzinfo=None
        )

        vol = parse_int(payload.get("tick_volume"))

        with self._lock:
            bar = self._builders.get(code)
            if bar is None:
                self._builders[code] = MinuteBar(
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

            # Minute advanced → flush previous bar and start a new one
            self._append_bar_row(bar.to_row())
            self._builders[code] = MinuteBar(
                code=code,
                datetime=minute,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=max(0, vol),
                value=int(price * max(0, vol)),
            )

    # ---------------------------------------------------------------------
    # ClickHouse warm-up
    # ---------------------------------------------------------------------
    def _get_clickhouse_config(self) -> ClickHouseConfig:
        if self._clickhouse_config is not None:
            return self._clickhouse_config

        raw = ConfigLoader.load(self.config.clickhouse_config_path)
        if isinstance(raw, dict) and isinstance(raw.get("clickhouse"), dict):
            data = raw["clickhouse"]
        else:
            data = raw if isinstance(raw, dict) else {}

        cfg = ClickHouseConfig(**data)
        self._clickhouse_config = cfg
        return cfg

    def _warmup_codes(self, codes: list[str]) -> None:
        for code in codes:
            try:
                df = self._warmup_code(code)
                if df is None:
                    continue
                with self._lock:
                    self._frames[code] = df
            except Exception as e:
                logger.warning(f"Warm-up failed for {code}: {e}")

    def _warmup_code(self, code: str):
        pl = _require_polars()

        now = datetime.now(self._tz).replace(tzinfo=None)
        start = now - timedelta(minutes=max(1, int(self.config.warmup_minutes)))

        cfg = self._get_clickhouse_config()

        try:
            # Import lazily to avoid import-time dependency failures in minimal envs.
            from shared.storage import create_clickhouse_client_wrapper

            client = create_clickhouse_client_wrapper(cfg)
            candles = client.get_minute_candles(code, start=start, end=now)
        except Exception as e:
            logger.debug(f"ClickHouse warm-up unavailable: {e}")
            candles = []

        rows = [
            {
                "code": c.code,
                "datetime": c.datetime,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": int(c.volume),
                "value": int(c.value),
            }
            for c in candles
        ]

        if rows:
            df = pl.DataFrame(rows).sort("datetime")
            return df.tail(self.config.max_bars)

        # Empty frame with stable schema (strategy engines rely on columns)
        return pl.DataFrame(
            {
                "code": pl.Series([], dtype=pl.Utf8),
                "datetime": pl.Series([], dtype=pl.Datetime),
                "open": pl.Series([], dtype=pl.Float64),
                "high": pl.Series([], dtype=pl.Float64),
                "low": pl.Series([], dtype=pl.Float64),
                "close": pl.Series([], dtype=pl.Float64),
                "volume": pl.Series([], dtype=pl.Int64),
                "value": pl.Series([], dtype=pl.Int64),
            }
        )

    # ---------------------------------------------------------------------
    # Frame updates
    # ---------------------------------------------------------------------
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
