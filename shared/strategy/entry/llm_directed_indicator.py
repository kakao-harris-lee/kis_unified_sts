"""LLM-directed indicator composite entry (futures) — succeeds RL_mppo.

Design: docs/superpowers/specs/2026-05-16-llm-directed-indicator-futures-design.md
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from shared.config.mixins import ConfigMixin

logger = logging.getLogger(__name__)


@dataclass
class LLMDirectedIndicatorConfig(ConfigMixin):
    """Config for LLMDirectedIndicatorEntry."""

    # Bias mapper
    bias_confidence_min: float = 0.6  # LLM confidence below -> FLAT
    # Evolution hook (spec section 7 Path B). "hard" = directional mask
    # (Approach A, the only behavior implemented here). "soft" is reserved
    # for the future soft-modulation path and is NOT implemented in this
    # plan -- the switch is shipped so Path B needs no schema change later.
    mask_mode: str = "hard"

    # Ensemble weights (3 directional families)
    w_momentum: float = 0.34
    w_trend: float = 0.33
    w_volume: float = 0.33
    entry_threshold: float = 0.30          # |ensemble| floor
    vol_threshold_mult: float = 0.5        # eff_thr = thr*(1+mult*vol_mag)

    # Market-hours (futures, KST)
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 45
    skip_market_open_minutes: int = 15
    skip_market_close_minutes: int = 30
    signal_cooldown_seconds: int = 180

    # Risk
    stop_loss_pct: float = 3.0


def _map_llm_bias(
    market_context: Any | None, config: LLMDirectedIndicatorConfig
) -> str:
    """Map LLM MarketContext -> 'LONG_BIAS' | 'SHORT_BIAS' | 'FLAT'.

    None / low-confidence / non-directional -> FLAT (indicators run
    standalone -- NEVER no-trade; design spec section 2 decision #2).
    """
    if market_context is None:
        return "FLAT"
    try:
        conf = float(getattr(market_context, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return "FLAT"
    if conf < config.bias_confidence_min:
        return "FLAT"
    is_bull = getattr(market_context, "is_bullish", None)
    is_bear = getattr(market_context, "is_bearish", None)
    if callable(is_bull) and is_bull():
        return "LONG_BIAS"
    if callable(is_bear) and is_bear():
        return "SHORT_BIAS"
    return "FLAT"
