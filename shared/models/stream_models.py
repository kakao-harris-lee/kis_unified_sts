"""Pydantic contracts for Redis Stream payloads."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field_text(fields: Mapping[str, Any], key: str) -> str | None:
    return _coerce_text(fields.get(key))


def _first_text(fields: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _field_text(fields, key)
        if value is not None:
            return value
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _coerce_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first_float(fields: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _parse_float(fields.get(key))
        if value is not None:
            return value
    return None


#: Redis Stream the futures tick producers write and every futures consumer
#: reads. Producers select it with ``MONITOR_FUTURES_TICK_STREAM`` and consumers
#: with ``FUTURES_TICK_STREAM`` — two env names, one stream — so the DEFAULTS
#: have to come from one place. Drifting them apart has no error path at all:
#: the consumer simply reads an empty stream forever.
DEFAULT_FUTURES_TICK_STREAM = "raw_data"

#: Best-bid/best-ask fields an orderbook-bearing tick carries.
#:
#: The price/quantity set is what ``KISFuturesPriceFeed`` caches per orderbook
#: tick, so a consumer can rebuild an orderbook snapshot from a stream entry
#: without a second data path. ``quote_ts`` carries that orderbook tick's OWN
#: time: an entry's ``timestamp`` belongs to the trade tick it was published
#: for, and a book can be frozen while trades keep printing, so anything
#: bounding quote freshness must read ``quote_ts`` and not ``timestamp``.
ORDERBOOK_FIELDS: tuple[str, ...] = (
    "bid_price_1",
    "bid_qty_1",
    "ask_price_1",
    "ask_qty_1",
    "spread",
    "quote_ts",
)


def _parse_non_negative_float(value: Any) -> float | None:
    """Parse a float and discard negatives instead of raising.

    The orderbook fields are declared ``ge=0``. A garbled/crossed quote must
    drop the offending field, not the tick: ``TickStreamPublisher._build_fields``
    treats a ``ValueError`` (pydantic's ``ValidationError`` is one) as "this
    tick is unpublishable", so raising here would silently delete a perfectly
    good trade tick from the stream.
    """
    parsed = _parse_float(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _coerce_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"true", "1", "yes", "y", "on"}:
        return True
    if lowered in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _infer_asset(symbol: str) -> Literal["stock", "futures"]:
    if symbol.isdigit() and len(symbol) == 6:
        return "stock"
    return "futures"


class StreamMessage(BaseModel):
    """Base Redis Stream message with explicit schema versioning."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1


class MarketTickMessage(StreamMessage):
    """Canonical market tick stream payload.

    Producer compatibility aliases such as ``code``/``close``/``current_price``
    are rollout fields, not canonical schema fields.
    """

    model_config = ConfigDict(extra="ignore")

    asset: Literal["stock", "futures"]
    symbol: str = Field(min_length=1)
    price: float = Field(gt=0)
    timestamp: float
    name: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = Field(default=None, ge=0)
    cumulative_volume: float | None = Field(default=None, ge=0)
    tick_volume: float | None = Field(default=None, ge=0)
    volume_is_cumulative: bool | None = None
    # Best bid/ask of the same instrument at tick time. Optional and additive:
    # producers that publish trade-only ticks omit them, and pre-existing
    # entries decode unchanged (no schema_version bump). Present so a stream
    # consumer can serve `get_orderbook_snapshot` with the same contract as
    # the KIS WS feed — see shared/streaming/consumer_feed.py.
    bid_price_1: float | None = Field(default=None, ge=0)
    bid_qty_1: float | None = Field(default=None, ge=0)
    ask_price_1: float | None = Field(default=None, ge=0)
    ask_qty_1: float | None = Field(default=None, ge=0)
    spread: float | None = Field(default=None, ge=0)
    # Event time of the orderbook tick these four prices came from — NOT this
    # entry's `timestamp`, which is the trade tick's. Absent on entries written
    # before this field existed; a consumer falls back to `timestamp` there.
    quote_ts: float | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _fill_read_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("asset") is None:
            symbol = _coerce_text(data.get("symbol") or data.get("code"))
            if symbol is not None:
                data["asset"] = _infer_asset(symbol)
        if data.get("timestamp") is None:
            data["timestamp"] = time.time()
        return data

    @field_validator("symbol")
    @classmethod
    def _strip_symbol(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("symbol must not be blank")
        return text

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @classmethod
    def from_source_payload(
        cls,
        *,
        asset: str,
        symbol: str,
        payload: Mapping[str, Any],
        now: float,
    ) -> MarketTickMessage:
        """Normalize a KIS tick payload before publishing to Redis."""

        price = _first_float(payload, ("current_price", "close", "price"))
        if price is None or price <= 0:
            raise ValueError("market tick missing positive price")

        event_ts = _parse_float(payload.get("timestamp")) or now
        name = _first_text(
            payload,
            (
                "name",
                "stock_name",
                "symbol_name",
                "item_name",
                "prdt_name",
                "hts_kor_isnm",
            ),
        )
        return cls(
            asset=asset,
            symbol=symbol,
            price=price,
            timestamp=event_ts,
            name=name,
            open=_parse_float(payload.get("open")),
            high=_parse_float(payload.get("high")),
            low=_parse_float(payload.get("low")),
            volume=_parse_float(payload.get("volume")),
            cumulative_volume=_parse_float(payload.get("cumulative_volume")),
            tick_volume=_parse_float(payload.get("tick_volume")),
            volume_is_cumulative=_parse_bool(payload.get("volume_is_cumulative")),
            bid_price_1=_parse_non_negative_float(payload.get("bid_price_1")),
            bid_qty_1=_parse_non_negative_float(payload.get("bid_qty_1")),
            ask_price_1=_parse_non_negative_float(payload.get("ask_price_1")),
            ask_qty_1=_parse_non_negative_float(payload.get("ask_qty_1")),
            spread=_parse_non_negative_float(payload.get("spread")),
            quote_ts=_parse_non_negative_float(payload.get("quote_ts")),
        )

    @classmethod
    def from_legacy_fields(
        cls,
        fields: Mapping[str, Any],
        *,
        default_timestamp: float | None = None,
        price_keys: tuple[str, ...] = ("close", "current_price", "price"),
    ) -> MarketTickMessage:
        """Decode pre-v1 tick stream fields during the compatibility window."""

        symbol = _first_text(fields, ("symbol", "code"))
        if symbol is None:
            raise ValueError("market tick missing symbol")

        price = _first_float(fields, price_keys)
        if price is None or price <= 0:
            raise ValueError("market tick missing positive price")

        asset_text = _field_text(fields, "asset")
        asset = (
            asset_text if asset_text in {"stock", "futures"} else _infer_asset(symbol)
        )
        event_ts = (
            _parse_float(fields.get("timestamp")) or default_timestamp or time.time()
        )
        name = _first_text(
            fields,
            (
                "name",
                "stock_name",
                "symbol_name",
                "item_name",
                "prdt_name",
                "hts_kor_isnm",
            ),
        )
        return cls(
            asset=asset,
            symbol=symbol,
            price=price,
            timestamp=event_ts,
            name=name,
            open=_parse_float(fields.get("open")),
            high=_parse_float(fields.get("high")),
            low=_parse_float(fields.get("low")),
            volume=_parse_float(fields.get("volume")),
            cumulative_volume=_parse_float(fields.get("cumulative_volume")),
            tick_volume=_parse_float(fields.get("tick_volume")),
            volume_is_cumulative=_parse_bool(fields.get("volume_is_cumulative")),
            bid_price_1=_parse_non_negative_float(fields.get("bid_price_1")),
            bid_qty_1=_parse_non_negative_float(fields.get("bid_qty_1")),
            ask_price_1=_parse_non_negative_float(fields.get("ask_price_1")),
            ask_qty_1=_parse_non_negative_float(fields.get("ask_qty_1")),
            spread=_parse_non_negative_float(fields.get("spread")),
            quote_ts=_parse_non_negative_float(fields.get("quote_ts")),
        )

    def to_price_dict(self) -> dict[str, Any]:
        """Return the price dict shape consumed by trading data sources."""

        data: dict[str, Any] = {
            "code": self.symbol,
            "close": self.price,
            "timestamp": self.timestamp,
        }
        for key in ("open", "high", "low", "volume", "volume_is_cumulative"):
            value = getattr(self, key)
            if value is not None:
                data[key] = int(value) if key == "volume" else value
        for key in ORDERBOOK_FIELDS:
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data
