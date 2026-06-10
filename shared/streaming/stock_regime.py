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
     "low_confidence": false, "computed_at_ms": 1781136000000}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from shared.strategy.base import MarketStateAdapter
from shared.strategy.market_classifier import MarketClassifier

logger = logging.getLogger(__name__)

# Regime values ThreeStageExit._is_bear_market treats as bear.
BEAR_REGIMES = ("BEAR", "BEAR_STRONG", "BEAR_MODERATE")

_CONFIG_FILE = "stock_regime.yaml"
_CONFIG_SECTION = "stock_regime"


def is_bear_regime(regime: str | None) -> bool:
    """Return True when ``regime`` is one of the bear classifications."""
    return regime in BEAR_REGIMES


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
            )
        except Exception:
            logger.warning("stock_regime.yaml load failed; using defaults")
            return cls()


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    if n % 2 == 0:
        return (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    return ordered[n // 2]


def compute_regime_payload(
    mfi_by_symbol: dict[str, float],
    *,
    config: StockRegimeConfig,
    now_ms: int,
    classifier: MarketClassifier | None = None,
) -> dict[str, Any]:
    """Classify the market from per-symbol MFI values into a publishable payload.

    Insufficient coverage (``len(mfi_by_symbol) < min_mfi_symbols``) publishes
    ``low_confidence_regime`` with ``low_confidence=true`` — the raw
    classification is preserved in ``raw_regime`` for observability.
    """
    classifier = classifier or MarketClassifier()
    mfi = _median(list(mfi_by_symbol.values()))
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
    }


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
    if age_seconds > config.max_age_seconds or age_seconds < 0:
        return None
    return MarketStateAdapter(regime)
