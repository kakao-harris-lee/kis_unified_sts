"""Indicator request contracts for multi-timeframe composition.

This module provides a small typed layer that normalizes legacy indicator
strings (e.g. ``momentum_5m``) into explicit request objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# Required-key pattern for the post-event trading-range high/low (Setup C's
# 15-minute breakout range). The minutes are encoded in the key itself
# (``last_15min_high`` → 15) so the window stays self-describing and config /
# contract-driven rather than a hardcoded constant in the resolver.
_RECENT_RANGE_KEY_RE = re.compile(r"^last_(\d+)min_(high|low)$")


class IndicatorKind(StrEnum):
    """High-level indicator families."""

    BASE = "base"
    MOMENTUM = "momentum"
    OHLCV = "ohlcv"


@dataclass(frozen=True)
class Timeframe:
    """Normalized timeframe representation.

    Values are stored in minutes for simple ordering and conversion.
    """

    minutes: int

    @classmethod
    def from_token(cls, token: str) -> Timeframe:
        text = token.strip().lower()
        if not text:
            raise ValueError("timeframe token is empty")
        if text.endswith("m"):
            return cls(minutes=int(text[:-1]))
        if text.endswith("h"):
            return cls(minutes=int(text[:-1]) * 60)
        if text.endswith("d"):
            return cls(minutes=int(text[:-1]) * 1440)
        raise ValueError(f"unsupported timeframe token: {token!r}")

    def to_token(self) -> str:
        if self.minutes % 1440 == 0:
            return f"{self.minutes // 1440}d"
        if self.minutes % 60 == 0:
            return f"{self.minutes // 60}h"
        return f"{self.minutes}m"


@dataclass(frozen=True)
class IndicatorRequest:
    """A concrete indicator request."""

    kind: IndicatorKind
    name: str
    timeframe: Timeframe | None = None
    source_key: str = ""

    @property
    def key(self) -> str:
        if self.timeframe is None:
            return self.name
        return f"{self.name}_{self.timeframe.to_token()}"


@dataclass(frozen=True)
class IndicatorContract:
    """Normalized view of required indicators."""

    required_keys: tuple[str, ...]
    requests: tuple[IndicatorRequest, ...]

    @property
    def needs_ohlcv(self) -> bool:
        return any(req.kind == IndicatorKind.OHLCV for req in self.requests)

    @property
    def momentum_requests(self) -> tuple[IndicatorRequest, ...]:
        return tuple(req for req in self.requests if req.kind == IndicatorKind.MOMENTUM)

    @property
    def mtf_base_requests(self) -> tuple[IndicatorRequest, ...]:
        return tuple(
            req
            for req in self.requests
            if req.kind == IndicatorKind.BASE and req.timeframe is not None
        )

    @property
    def mtf_timeframes(self) -> tuple[int, ...]:
        """Sorted distinct timeframes (in minutes) required across momentum + mtf_base."""
        return tuple(
            sorted(
                {
                    req.timeframe.minutes
                    for req in (*self.momentum_requests, *self.mtf_base_requests)
                    if req.timeframe is not None
                }
            )
        )

    @property
    def recent_range_minutes(self) -> int | None:
        """Window (minutes) for the post-event trading-range high/low, or None.

        Setup C declares ``last_15min_high`` / ``last_15min_low`` in its
        ``required_indicators``; the window is encoded in the key name so the
        resolver can fulfil it from the live candle history via
        ``engine.get_recent_range(symbol, minutes)`` — matching the causal
        ``[i-N, i-1]`` (current bar excluded) window the backtest replay uses.

        Returns the largest declared window when several are present (defensive;
        in practice a strategy declares a single high/low pair). Returns ``None``
        when no range key is required.
        """
        windows = [
            int(m.group(1))
            for key in self.required_keys
            if (m := _RECENT_RANGE_KEY_RE.match(str(key or "").strip()))
        ]
        return max(windows) if windows else None

    @property
    def warmth_timeframe(self) -> int | None:
        """Deepest intraday timeframe (minutes) used to judge warmth.

        Daily (>= 1440 min) is excluded: it is seeded from a separate Parquet
        daily store, not from intraday 1m accumulation, so it must not gate is_warm.
        Returns None when the strategy needs no intraday MTF accumulation.
        """
        intraday = [tf for tf in self.mtf_timeframes if tf < 1440]
        return max(intraday) if intraday else None

    @classmethod
    def from_required_keys(cls, keys: list[str] | tuple[str, ...]) -> IndicatorContract:
        requests: list[IndicatorRequest] = []
        for raw in keys:
            key = str(raw or "").strip()
            if not key:
                continue
            if key == "ohlcv":
                requests.append(
                    IndicatorRequest(
                        kind=IndicatorKind.OHLCV,
                        name="ohlcv",
                        source_key=key,
                    )
                )
                continue
            if key.startswith("momentum_"):
                token = key[len("momentum_") :]
                try:
                    tf = Timeframe.from_token(token)
                except ValueError:
                    # Keep malformed keys as base indicators for backward safety.
                    requests.append(
                        IndicatorRequest(
                            kind=IndicatorKind.BASE,
                            name=key,
                            source_key=key,
                        )
                    )
                    continue
                requests.append(
                    IndicatorRequest(
                        kind=IndicatorKind.MOMENTUM,
                        name="momentum",
                        timeframe=tf,
                        source_key=key,
                    )
                )
                continue
            if key.startswith("mtf_base_"):
                token = key[len("mtf_base_") :]
                try:
                    tf = Timeframe.from_token(token)
                except ValueError:
                    # Keep malformed keys as base indicators for backward safety.
                    requests.append(
                        IndicatorRequest(
                            kind=IndicatorKind.BASE,
                            name=key,
                            source_key=key,
                        )
                    )
                    continue
                requests.append(
                    IndicatorRequest(
                        kind=IndicatorKind.BASE,
                        name="mtf_base",
                        timeframe=tf,
                        source_key=key,
                    )
                )
                continue
            requests.append(
                IndicatorRequest(
                    kind=IndicatorKind.BASE,
                    name=key,
                    source_key=key,
                )
            )
        return cls(required_keys=tuple(keys), requests=tuple(requests))
