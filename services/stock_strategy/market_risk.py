"""M4-P consumer-side wiring for the shared market-risk ENTRY gate.

The gate itself (mode / reaction matrix / staleness / Redis key) lives in
``shared/risk/market_risk_gate.py`` + ``config/market_risk_gate.yaml`` — that
file's ``mode`` is the single off/shadow/enforce switch. There is deliberately
NO M4-P-side on/off duplicate (Phase 2C contract): an unwired daemon (missing
config object) simply behaves as before, and every gate failure fails open
inside the shared evaluator.

This module owns only what the shared gate delegates to its callers:

* mapping the reaction-matrix ``min_confidence`` LABEL (e.g. ``"HIGH"`` at
  stock/ELEVATED) onto the numeric ``Signal.confidence`` scale (0.0–1.0) that
  stock entry signals carry, and
* the throttle interval for shadow-mode would-block logging (the shadow
  verdict repeats every eval cycle for hours; the setup-eval logging pattern
  throttles it).

Loaded once at daemon startup from ``config/stock_market_risk_gate.yaml``;
the hot path never re-parses YAML.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_market_risk_gate.yaml"
_CONFIG_SECTION = "stock_market_risk_gate"

# Mirror of the shipped config/stock_market_risk_gate.yaml (fallback when the
# YAML is absent/malformed), not an alternative source of truth.
_DEFAULT_CONFIDENCE_LEVELS: dict[str, float] = {
    "LOW": 0.3,
    "MEDIUM": 0.5,
    "HIGH": 0.7,
}

__all__ = ["MarketRiskGateWiringConfig"]


@dataclass(frozen=True)
class MarketRiskGateWiringConfig:
    """Signal-confidence interpretation of the gate's ``min_confidence`` labels.

    ``confidence_levels`` maps an UPPERCASE matrix label to the minimum
    ``Signal.confidence`` (0.0–1.0) required for admission when the gate is in
    enforce mode. Unknown labels resolve to ``None`` → the caller admits the
    signal (fail-open, mirroring the shared gate's contract).
    """

    confidence_levels: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_CONFIDENCE_LEVELS)
    )
    # Shadow-mode would-block observations repeat every eval cycle (~60s) for
    # as long as the band holds; log at most once per interval per reason.
    would_block_log_interval_seconds: float = 300.0

    @classmethod
    def load(cls) -> MarketRiskGateWiringConfig:
        """Load from ``config/stock_market_risk_gate.yaml`` (defaults on failure).

        Same graceful-degradation pattern as ``StockSignalEvalConfig.load``:
        any read/parse problem logs a warning and returns code defaults so the
        daemon never fails to start over consumer-side wiring config.
        """
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            levels_raw = raw.get("confidence_levels", _DEFAULT_CONFIDENCE_LEVELS)
            levels = {
                str(label).strip().upper(): float(value)
                for label, value in dict(levels_raw).items()
            }
            for label, value in levels.items():
                if not 0.0 <= value <= 1.0:
                    raise ValueError(
                        f"confidence_levels[{label!r}]={value} outside [0, 1]"
                    )
            return cls(
                confidence_levels=levels,
                would_block_log_interval_seconds=float(
                    raw.get(
                        "would_block_log_interval_seconds",
                        cls.would_block_log_interval_seconds,
                    )
                ),
            )
        except Exception:
            logger.warning("stock_market_risk_gate.yaml load failed; using defaults")
            return cls()

    def min_confidence_threshold(self, label: str | None) -> float | None:
        """Numeric threshold for a matrix ``min_confidence`` label.

        ``None``/empty labels mean "no confidence gate" and unknown labels are
        fail-open by contract — both return ``None`` so the caller admits.
        """
        if not label:
            return None
        return self.confidence_levels.get(str(label).strip().upper())
