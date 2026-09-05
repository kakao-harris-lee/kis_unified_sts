"""Market-regime contract for the decoupled stock pipeline (M4-P → M4-X).

M4-P (``StockStrategyDaemon``) owns the only ``StreamingIndicatorEngine`` in
the decoupled chain, so it computes the market-wide regime — median MFI over
the watchlist universe → ``MarketClassifier`` — and publishes a JSON payload
to a Redis key. Consumers apply staleness gating and treat anything
missing/stale/malformed as "no regime" (never triggers bear logic):

  * M4-X (``StockExitDaemon``) — passes the regime as ``market_state`` to
    ``ThreeStageExit.scan_positions`` so ``enable_bear_exit`` can liquidate
    on BEAR_* regimes.
  * M4-P itself — skips ``check_entries`` while the regime is BEAR_*
    (mirrors ``MarketClassifier.should_trade``; long-only entries in a bear
    market would be liquidated by M4-X immediately — fee churn).

Mirrors ``TradingOrchestrator._classify_market`` + ``_effective_stock_regime``
(median MFI, min-symbol confidence gate) without the avg-change warmup
fallback: insufficient MFI coverage publishes ``low_confidence_regime``
(default UNKNOWN) instead.

Payload schema (JSON string at ``redis_key``)::

    {"regime": "BEAR_STRONG", "mfi": 31.2, "mfi_symbols": 12,
     "low_confidence": false, "computed_at_ms": 1781136000000,
     "last_tick_ts_ms": 1781135998000}

``last_tick_ts_ms`` (issue #460) is the most recent tick timestamp feeding
the publisher's candle accumulators (null when unknown). The staleness gate
validates *publish* time only — ``computed_at_ms - last_tick_ts_ms``
(``indicator_lag_seconds``) is the observability signal for "publishing
fresh payloads computed from stale candles" (e.g. a tick-stream stall).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from statistics import median
from typing import Any

from shared.strategy.base import MarketStateAdapter
from shared.strategy.market_classifier import (
    BEAR_REGIMES,
    MarketClassifier,
    is_bear_regime,
)

__all__ = [
    "BEAR_REGIMES",
    "StockRegimeConfig",
    "compute_regime_payload",
    "indicator_lag_seconds",
    "is_bear_regime",
    "parse_market_state",
]

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_regime.yaml"
_CONFIG_SECTION = "stock_regime"


@dataclass(frozen=True)
class StockRegimeConfig:
    """Shared publisher/consumer settings for the stock regime contract."""

    enabled: bool = True
    redis_key: str = "stock:daemon:market_regime"
    publish_ttl_seconds: int = 900
    min_mfi_symbols: int = 8
    low_confidence_regime: str = "UNKNOWN"
    block_entries_in_bear: bool = True
    max_age_seconds: float = 300.0
    warn_indicator_lag_seconds: float = 180.0

    def __post_init__(self) -> None:
        # Low-confidence classification must never trigger liquidation —
        # enforce the invariant in code, not just in the YAML comment.
        # ``load()`` catches this and falls back to safe defaults.
        if is_bear_regime(self.low_confidence_regime):
            raise ValueError(
                "low_confidence_regime must not be a bear value: "
                f"{self.low_confidence_regime!r}"
            )

    @classmethod
    def load(cls) -> StockRegimeConfig:
        """Load from ``config/stock_regime.yaml`` (defaults on any failure)."""
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            return cls(
                enabled=bool(raw.get("enabled", cls.enabled)),
                redis_key=str(raw.get("redis_key", cls.redis_key)),
                publish_ttl_seconds=int(
                    raw.get("publish_ttl_seconds", cls.publish_ttl_seconds)
                ),
                min_mfi_symbols=int(raw.get("min_mfi_symbols", cls.min_mfi_symbols)),
                low_confidence_regime=str(
                    raw.get("low_confidence_regime", cls.low_confidence_regime)
                ),
                block_entries_in_bear=bool(
                    raw.get("block_entries_in_bear", cls.block_entries_in_bear)
                ),
                max_age_seconds=float(raw.get("max_age_seconds", cls.max_age_seconds)),
                warn_indicator_lag_seconds=float(
                    raw.get(
                        "warn_indicator_lag_seconds", cls.warn_indicator_lag_seconds
                    )
                ),
            )
        except Exception:
            logger.warning("stock_regime.yaml load failed; using defaults")
            return cls()


def compute_regime_payload(
    mfi_by_symbol: dict[str, float],
    *,
    config: StockRegimeConfig,
    now_ms: int,
    classifier: MarketClassifier | None = None,
    last_tick_ts_ms: int | None = None,
) -> dict[str, Any]:
    """Classify the market from per-symbol MFI values into a publishable payload.

    Insufficient coverage (``len(mfi_by_symbol) < min_mfi_symbols``) publishes
    ``low_confidence_regime`` with ``low_confidence=true`` — the raw
    classification is preserved in ``raw_regime`` for observability.

    ``last_tick_ts_ms`` is the freshest tick timestamp feeding the MFI
    candles (None when the engine cannot provide one) — see module docstring.
    """
    classifier = classifier or MarketClassifier()
    mfi = float(median(mfi_by_symbol.values())) if mfi_by_symbol else None
    # classify() is MFI-only (adx is accepted but ignored) — pass a literal 0.
    raw_regime = (
        classifier.classify(mfi=mfi, adx=0.0).value if mfi is not None else "UNKNOWN"
    )
    low_confidence = len(mfi_by_symbol) < config.min_mfi_symbols
    return {
        "regime": config.low_confidence_regime if low_confidence else raw_regime,
        "raw_regime": raw_regime,
        "mfi": mfi,
        "mfi_symbols": len(mfi_by_symbol),
        "low_confidence": low_confidence,
        "computed_at_ms": now_ms,
        "last_tick_ts_ms": last_tick_ts_ms,
    }


def indicator_lag_seconds(payload: dict[str, Any]) -> float | None:
    """Seconds between payload compute time and its freshest candle tick.

    ``(computed_at_ms - last_tick_ts_ms) / 1000`` — the "publishing fresh
    payloads from stale candles" signal (issue #460). Returns None when either
    field is missing or non-finite (old-schema payloads carry no
    ``last_tick_ts_ms``; JSON ``NaN`` literals parse but compare False to
    every bound — reject via ``isfinite``, never a magnitude comparison).
    Sub-second negative lag (a tick landing between the engine read and the
    ``now_ms`` capture) clamps to 0.
    """
    computed_at = payload.get("computed_at_ms")
    last_tick = payload.get("last_tick_ts_ms")
    if not isinstance(computed_at, (int, float)) or not isinstance(
        last_tick, (int, float)
    ):
        return None
    lag = (float(computed_at) - float(last_tick)) / 1000.0
    if not math.isfinite(lag):
        return None
    return max(0.0, lag)


def parse_market_state(
    raw: Any,
    *,
    config: StockRegimeConfig,
    now_ms: int,
) -> MarketStateAdapter | None:
    """Decode a published payload into a ``MarketStateProtocol`` object.

    Returns None (→ no bear logic) for missing, malformed, or stale payloads —
    the consumer must never liquidate on outdated regime information.
    """
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    regime = payload.get("regime")
    computed_at_ms = payload.get("computed_at_ms")
    if not isinstance(regime, str) or not isinstance(computed_at_ms, (int, float)):
        return None
    age_seconds = (now_ms - float(computed_at_ms)) / 1000.0
    # Positive-form bound: json.loads accepts the NaN literal, and NaN
    # compares False to everything — so NaN is rejected here along with
    # stale and future (negative-age) timestamps.
    if not 0.0 <= age_seconds <= config.max_age_seconds:
        return None
    return MarketStateAdapter(regime)
