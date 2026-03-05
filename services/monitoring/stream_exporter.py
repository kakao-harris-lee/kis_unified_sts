"""Redis Stream -> Prometheus exporter for lightweight realtime monitoring.

Design goals:
- No write-path impact on trading (read-only XREAD from Redis Stream)
- Minimal CPU/memory overhead
- Prometheus-friendly aggregation (avoid raw tick cardinality explosion)

This exporter reads tick-like events from Redis streams (e.g. `market:ticks`,
`raw_data`) and publishes:
- latest price per symbol
- per-minute OHLCV gauges (latest closed/current minute state)
- stream/message health metrics

Run:
    python -m services.monitoring.stream_exporter
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from prometheus_client import Counter, Gauge, start_http_server

from shared.streaming.client import RedisClient
from shared.streaming.message import StreamMessage

logger = logging.getLogger(__name__)


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
    return None


def _parse_msg_id_ms(message_id: str) -> float | None:
    """Return stream message timestamp seconds from Redis message id."""
    if "-" not in message_id:
        return None
    head, _tail = message_id.split("-", 1)
    try:
        return int(head) / 1000.0
    except ValueError:
        return None


def _extract_symbol_name(payload: dict[str, Any], symbol: str) -> str:
    for key in (
        "name",
        "stock_name",
        "symbol_name",
        "item_name",
        "prdt_name",
        "hts_kor_isnm",
    ):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return symbol


def detect_asset(symbol: str, stream_name: str) -> str:
    """Best-effort asset classifier with low-cost heuristics."""
    sym = symbol.strip()
    sname = stream_name.lower()

    if sym.isdigit() and len(sym) == 6:
        return "stock"
    if "stock" in sname:
        return "stock"
    if "futures" in sname:
        return "futures"
    return "futures"


@dataclass
class ExporterConfig:
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = int(os.getenv("REDIS_DB", "1"))

    port: int = int(os.getenv("STREAM_EXPORTER_PORT", "9093"))
    streams: tuple[str, ...] = tuple(
        s.strip()
        for s in os.getenv("STREAM_EXPORTER_STREAMS", "market:ticks,raw_data").split(
            ","
        )
        if s.strip()
    )
    read_count: int = int(os.getenv("STREAM_EXPORTER_READ_COUNT", "200"))
    block_ms: int = int(os.getenv("STREAM_EXPORTER_BLOCK_MS", "1000"))
    housekeeping_seconds: float = float(
        os.getenv("STREAM_EXPORTER_HOUSEKEEPING_SECONDS", "5")
    )
    symbol_ttl_seconds: float = float(
        os.getenv("STREAM_EXPORTER_SYMBOL_TTL_SECONDS", "1800")
    )
    max_symbols_per_asset: int = int(
        os.getenv("STREAM_EXPORTER_MAX_SYMBOLS_PER_ASSET", "60")
    )


@dataclass
class MinuteBarState:
    minute_epoch: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    published: bool = False


class StreamExporter:
    """Read Redis Streams and expose low-cardinality monitoring metrics."""

    def __init__(self, config: ExporterConfig) -> None:
        self.config = config
        self.client = RedisClient.get_client()
        self.offsets: dict[str, str] = {stream: "$" for stream in config.streams}

        self._bars: dict[tuple[str, str], MinuteBarState] = {}
        self._last_seen: dict[tuple[str, str], float] = {}
        self._last_cumulative_volume: dict[tuple[str, str], float] = {}
        self._symbol_names: dict[tuple[str, str], str] = {}
        self._symbol_set: dict[str, set[str]] = {"stock": set(), "futures": set()}
        self._last_housekeeping = 0.0

        # Stream/message health
        self.messages_total = Counter(
            "redis_stream_messages_total",
            "Total consumed Redis stream messages",
            ["stream", "asset"],
        )
        self.parse_errors_total = Counter(
            "redis_stream_parse_errors_total",
            "Total parse failures while consuming Redis streams",
            ["stream"],
        )
        self.symbol_dropped_total = Counter(
            "redis_stream_symbol_dropped_total",
            "Total symbol drops due to cardinality/guardrails",
            ["asset", "reason"],
        )
        self.stream_length = Gauge(
            "redis_stream_length",
            "Redis stream length by stream name",
            ["stream"],
        )
        self.last_message_age_seconds = Gauge(
            "redis_stream_last_message_age_seconds",
            "Age of last processed message by stream/asset",
            ["stream", "asset"],
        )
        self.last_message_timestamp_seconds = Gauge(
            "redis_stream_last_message_timestamp_seconds",
            "Last processed message timestamp from Redis stream id",
            ["stream"],
        )
        self.active_symbols = Gauge(
            "redis_stream_active_symbols",
            "Active symbol count currently tracked by exporter",
            ["asset"],
        )

        # Lightweight market metrics
        self.last_price_krw = Gauge(
            "redis_stream_last_price_krw",
            "Latest traded price from Redis stream",
            ["asset", "symbol", "name"],
        )
        self.last_tick_timestamp_seconds = Gauge(
            "redis_stream_last_tick_timestamp_seconds",
            "Last tick event timestamp (epoch seconds) by symbol",
            ["asset", "symbol", "name"],
        )
        self.bar_1m_open_krw = Gauge(
            "redis_stream_bar_1m_open_krw",
            "1-minute bar open price from Redis stream aggregation",
            ["asset", "symbol", "name"],
        )
        self.bar_1m_high_krw = Gauge(
            "redis_stream_bar_1m_high_krw",
            "1-minute bar high price from Redis stream aggregation",
            ["asset", "symbol", "name"],
        )
        self.bar_1m_low_krw = Gauge(
            "redis_stream_bar_1m_low_krw",
            "1-minute bar low price from Redis stream aggregation",
            ["asset", "symbol", "name"],
        )
        self.bar_1m_close_krw = Gauge(
            "redis_stream_bar_1m_close_krw",
            "1-minute bar close price from Redis stream aggregation",
            ["asset", "symbol", "name"],
        )
        self.bar_1m_volume = Gauge(
            "redis_stream_bar_1m_volume",
            "1-minute bar volume from Redis stream aggregation",
            ["asset", "symbol", "name"],
        )
        self.bar_1m_timestamp_seconds = Gauge(
            "redis_stream_bar_1m_timestamp_seconds",
            "Timestamp (epoch seconds) of the latest emitted 1-minute bar",
            ["asset", "symbol", "name"],
        )

    def run_forever(self) -> None:
        if not self.config.streams:
            raise ValueError("No streams configured for stream exporter")

        logger.info(
            "Starting stream exporter: streams=%s port=%d redis=%s:%d/%d",
            ",".join(self.config.streams),
            self.config.port,
            self.config.redis_host,
            self.config.redis_port,
            self.config.redis_db,
        )

        start_http_server(self.config.port)
        logger.info("Prometheus metrics server started on port %d", self.config.port)

        while True:
            try:
                events = self.client.xread(
                    self.offsets,
                    count=self.config.read_count,
                    block=self.config.block_ms,
                )

                now = time.time()
                if events:
                    self._process_events(events, now)

                if now - self._last_housekeeping >= self.config.housekeeping_seconds:
                    self._housekeeping(now)
                    self._last_housekeeping = now
            except KeyboardInterrupt:
                logger.info("Stream exporter stopped by user")
                return
            except Exception as e:
                logger.error("Stream exporter loop error: %s", e, exc_info=True)
                time.sleep(1.0)

    def _process_events(
        self, events: list[tuple[str, list[tuple[str, dict[str, str]]]]], now: float
    ) -> None:
        for stream_name, messages in events:
            for message_id, raw_fields in messages:
                self.offsets[stream_name] = message_id
                msg_ts = _parse_msg_id_ms(message_id) or now
                self.last_message_timestamp_seconds.labels(stream=stream_name).set(
                    msg_ts
                )
                self._process_one(stream_name, message_id, raw_fields, now, msg_ts)

    def _process_one(
        self,
        stream_name: str,
        message_id: str,
        raw_fields: dict[str, str],
        now: float,
        msg_ts: float,
    ) -> None:
        try:
            msg = StreamMessage.from_raw(stream_name, message_id, dict(raw_fields))
            payload = msg.data
        except Exception:
            self.parse_errors_total.labels(stream=stream_name).inc()
            return

        symbol = str(payload.get("symbol") or payload.get("code") or "").strip()
        if not symbol:
            self.parse_errors_total.labels(stream=stream_name).inc()
            return

        asset = str(payload.get("asset") or "").strip().lower()
        if asset not in {"stock", "futures"}:
            asset = detect_asset(symbol, stream_name)
        if not self._accept_symbol(asset, symbol):
            return

        event_ts = _parse_float(payload.get("timestamp")) or msg_ts
        price = (
            _parse_float(payload.get("current_price"))
            or _parse_float(payload.get("close"))
            or _parse_float(payload.get("price"))
        )
        symbol_name = _extract_symbol_name(payload, symbol)
        self._sync_symbol_name(asset, symbol, symbol_name)

        self.messages_total.labels(stream=stream_name, asset=asset).inc()
        self.last_message_age_seconds.labels(stream=stream_name, asset=asset).set(
            max(0.0, now - event_ts)
        )
        self._last_seen[(asset, symbol)] = now
        self.last_tick_timestamp_seconds.labels(
            asset=asset,
            symbol=symbol,
            name=self._symbol_names[(asset, symbol)],
        ).set(event_ts)

        if price is None or price <= 0:
            return

        self.last_price_krw.labels(
            asset=asset,
            symbol=symbol,
            name=self._symbol_names[(asset, symbol)],
        ).set(price)
        self._update_bar(asset, symbol, price, payload, event_ts)

    def _accept_symbol(self, asset: str, symbol: str) -> bool:
        tracked = self._symbol_set[asset]
        if symbol in tracked:
            return True
        if len(tracked) >= self.config.max_symbols_per_asset:
            self.symbol_dropped_total.labels(asset=asset, reason="cap").inc()
            return False
        tracked.add(symbol)
        return True

    def _update_bar(
        self,
        asset: str,
        symbol: str,
        price: float,
        payload: dict[str, Any],
        event_ts: float,
    ) -> None:
        minute_epoch = int(event_ts // 60) * 60
        key = (asset, symbol)
        state = self._bars.get(key)

        if state is None:
            self._bars[key] = MinuteBarState(
                minute_epoch=minute_epoch,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=0.0,
            )
            state = self._bars[key]
        elif minute_epoch > state.minute_epoch:
            self._publish_bar(key, state)
            self._bars[key] = MinuteBarState(
                minute_epoch=minute_epoch,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=0.0,
            )
            state = self._bars[key]
        elif minute_epoch < state.minute_epoch:
            # Out-of-order old tick; ignore to keep exporter cheap.
            return

        if price > state.high:
            state.high = price
        if price < state.low:
            state.low = price
        state.close = price
        state.published = False

        delta_vol = self._extract_volume_delta(key, payload)
        if delta_vol > 0:
            state.volume += delta_vol

    def _extract_volume_delta(
        self, key: tuple[str, str], payload: dict[str, Any]
    ) -> float:
        """Estimate per-tick volume delta with cumulative fallback support."""
        volume_is_cumulative = _parse_bool(payload.get("volume_is_cumulative"))
        cumulative_volume = _parse_float(payload.get("cumulative_volume"))
        raw_volume = _parse_float(payload.get("volume"))
        tick_volume = _parse_float(payload.get("tick_volume"))

        # If source explicitly marks non-cumulative, use tick/raw volume directly.
        if volume_is_cumulative is False:
            return max(0.0, tick_volume or raw_volume or 0.0)

        # Stock feed commonly sends cumulative volume via `volume`.
        if cumulative_volume is None and raw_volume is not None:
            cumulative_volume = raw_volume

        if cumulative_volume is not None:
            prev = self._last_cumulative_volume.get(key)
            self._last_cumulative_volume[key] = cumulative_volume
            if prev is None:
                return 0.0
            delta = cumulative_volume - prev
            if delta < 0:
                # Session rollover/reset
                return 0.0
            return delta

        return max(0.0, tick_volume or 0.0)

    def _publish_bar(self, key: tuple[str, str], state: MinuteBarState) -> None:
        if state.published:
            return
        asset, symbol = key
        symbol_name = self._symbol_names.get((asset, symbol), symbol)
        self.bar_1m_open_krw.labels(asset=asset, symbol=symbol, name=symbol_name).set(
            state.open
        )
        self.bar_1m_high_krw.labels(asset=asset, symbol=symbol, name=symbol_name).set(
            state.high
        )
        self.bar_1m_low_krw.labels(asset=asset, symbol=symbol, name=symbol_name).set(
            state.low
        )
        self.bar_1m_close_krw.labels(
            asset=asset, symbol=symbol, name=symbol_name
        ).set(state.close)
        self.bar_1m_volume.labels(asset=asset, symbol=symbol, name=symbol_name).set(
            state.volume
        )
        self.bar_1m_timestamp_seconds.labels(
            asset=asset, symbol=symbol, name=symbol_name
        ).set(
            float(state.minute_epoch)
        )
        state.published = True

    def _housekeeping(self, now: float) -> None:
        current_minute = int(now // 60) * 60

        for stream in self.config.streams:
            try:
                self.stream_length.labels(stream=stream).set(self.client.xlen(stream))
            except Exception:
                logger.debug("xlen failed for stream=%s", stream, exc_info=True)

        # Flush finished minute bars even when there is no tick in next minute.
        for key, state in list(self._bars.items()):
            if state.minute_epoch < current_minute:
                self._publish_bar(key, state)

        # Prune stale symbols to keep metric cardinality bounded.
        stale_keys: list[tuple[str, str]] = []
        for key, seen_at in self._last_seen.items():
            if now - seen_at > self.config.symbol_ttl_seconds:
                stale_keys.append(key)

        for asset, symbol in stale_keys:
            key = (asset, symbol)
            self._last_seen.pop(key, None)
            self._bars.pop(key, None)
            self._last_cumulative_volume.pop(key, None)
            self._symbol_set[asset].discard(symbol)
            self.symbol_dropped_total.labels(asset=asset, reason="ttl").inc()
            self._remove_symbol_labels(asset, symbol)
            self._symbol_names.pop(key, None)

        for asset in ("stock", "futures"):
            self.active_symbols.labels(asset=asset).set(len(self._symbol_set[asset]))

    def _sync_symbol_name(self, asset: str, symbol: str, symbol_name: str) -> None:
        key = (asset, symbol)
        current = self._symbol_names.get(key)
        if current == symbol_name:
            return
        if current is not None:
            self._remove_symbol_labels(asset, symbol, current)
        self._symbol_names[key] = symbol_name

    def _remove_symbol_labels(
        self, asset: str, symbol: str, symbol_name: str | None = None
    ) -> None:
        label_name = symbol_name or self._symbol_names.get((asset, symbol), symbol)
        for metric in (
            self.last_price_krw,
            self.last_tick_timestamp_seconds,
            self.bar_1m_open_krw,
            self.bar_1m_high_krw,
            self.bar_1m_low_krw,
            self.bar_1m_close_krw,
            self.bar_1m_volume,
            self.bar_1m_timestamp_seconds,
        ):
            try:
                metric.remove(asset, symbol, label_name)
            except KeyError:
                continue


def _setup_logging() -> None:
    level_name = os.getenv("STREAM_EXPORTER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    _setup_logging()
    config = ExporterConfig()

    # Build Redis client instance with configured env.
    os.environ["REDIS_HOST"] = config.redis_host
    os.environ["REDIS_PORT"] = str(config.redis_port)
    os.environ["REDIS_DB"] = str(config.redis_db)
    os.environ["REDIS_PASSWORD"] = config.redis_password

    exporter = StreamExporter(config)
    exporter.run_forever()


if __name__ == "__main__":
    main()
