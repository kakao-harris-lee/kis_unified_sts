"""Per-symbol bear-gate override contract (M4-P → Redis → M4-X).

Mirrors shared/streaming/stock_regime.py: M4-P computes the set of individually
strong symbols and publishes it; M4-P's entry skip and M4-X's BEAR_EXIT both
consume it with staleness gating. Stale/missing/malformed/NaN → empty set, so
the system fails safe to normal blanket-bear behavior (never exempt on bad data).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from shared.strategy.symbol_strength import StrengthCriteria

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_bear_override.yaml"
_CONFIG_SECTION = "stock_bear_override"


@dataclass(frozen=True)
class BearOverrideConfig:
    """Shared publisher/consumer settings for the per-symbol bear-gate override."""

    enabled: bool = False
    redis_key: str = "stock:daemon:bear_override"
    publish_ttl_seconds: int = 900
    max_age_seconds: float = 300.0
    max_override_positions: int = 3
    daily_indicators_key: str = "system:daily_indicators:latest"
    rsi_min: float = 55.0
    require_above_sma20: bool = True
    require_rsi_rising: bool = True
    require_macd_positive: bool = True

    @property
    def criteria(self) -> StrengthCriteria:
        """Return a ``StrengthCriteria`` built from this config's threshold fields."""
        return StrengthCriteria(
            rsi_min=self.rsi_min,
            require_above_sma20=self.require_above_sma20,
            require_rsi_rising=self.require_rsi_rising,
            require_macd_positive=self.require_macd_positive,
        )

    @classmethod
    def load(cls) -> BearOverrideConfig:
        """Load from ``config/stock_bear_override.yaml`` (defaults on any failure)."""
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            return cls(
                enabled=bool(raw.get("enabled", cls.enabled)),
                redis_key=str(raw.get("redis_key", cls.redis_key)),
                publish_ttl_seconds=int(
                    raw.get("publish_ttl_seconds", cls.publish_ttl_seconds)
                ),
                max_age_seconds=float(raw.get("max_age_seconds", cls.max_age_seconds)),
                max_override_positions=int(
                    raw.get("max_override_positions", cls.max_override_positions)
                ),
                daily_indicators_key=str(
                    raw.get("daily_indicators_key", cls.daily_indicators_key)
                ),
                rsi_min=float(raw.get("rsi_min", cls.rsi_min)),
                require_above_sma20=bool(
                    raw.get("require_above_sma20", cls.require_above_sma20)
                ),
                require_rsi_rising=bool(
                    raw.get("require_rsi_rising", cls.require_rsi_rising)
                ),
                require_macd_positive=bool(
                    raw.get("require_macd_positive", cls.require_macd_positive)
                ),
            )
        except Exception:
            logger.warning("stock_bear_override.yaml load failed; using defaults")
            return cls()


def compute_override_payload(strong: set[str], *, now_ms: int) -> dict[str, Any]:
    """Build the Redis payload for a set of strong symbols.

    Payload schema::

        {"strong": ["A", "B"], "count": 2, "computed_at_ms": 1_000_000}
    """
    codes = sorted(strong)
    return {"strong": codes, "count": len(codes), "computed_at_ms": now_ms}


def parse_strong_set(raw: Any, *, config: BearOverrideConfig, now_ms: int) -> set[str]:
    """Decode a published payload to a strong-symbol set, or ∅ on any problem.

    Positive-form staleness bound rejects NaN, stale, and future timestamps.
    NaN compares False to everything, so ``not 0.0 <= NaN <= max`` is True →
    empty set returned. Missing/malformed inputs also return the empty set —
    the consumer never exempts symbols on bad data.
    """
    if raw is None:
        return set()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return set()
    if not isinstance(payload, dict):
        return set()
    computed_at_ms = payload.get("computed_at_ms")
    strong = payload.get("strong")
    if not isinstance(computed_at_ms, (int, float)) or not isinstance(strong, list):
        return set()
    age_seconds = (now_ms - float(computed_at_ms)) / 1000.0
    # Positive-form bound: json.loads accepts the NaN literal, and NaN
    # compares False to everything — so NaN is rejected here along with
    # stale and future (negative-age) timestamps.
    if not 0.0 <= age_seconds <= config.max_age_seconds:
        return set()
    return {str(c) for c in strong}
