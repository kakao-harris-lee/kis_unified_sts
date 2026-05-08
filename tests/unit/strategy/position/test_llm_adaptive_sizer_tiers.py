"""Tests for LLMAdaptiveSizer — Phase 1.3 multi-tier scaling extension.

Covers:
    (a) Tier boundary correctness with base_quantity=5 (non-trivial scaling)
    (b) Entry-skip semantics when risk_score > 80 (scale=0.0 → quantity=0)
    (c) tiers=[] falls through to legacy single-threshold behavior unchanged
    (d) max_quantity_cap clamps even when LLM scaling produces a larger result
    (e) market_context=None → returns base_quantity (graceful degradation)
    (f) Backward compat: stock single-threshold path still works correctly
    (g) Tier fallback: risk_score exceeds all upper_bounds → 0 (entry skip)
    (h) confidence / risk_mode modifiers applied on top of tier scale
"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from typing import Any

import pytest

from shared.models.signal import Signal, SignalType
from shared.strategy.position.llm_adaptive_sizer import (
    LLMAdaptiveSizer,
    LLMAdaptiveSizerConfig,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

# Standard futures tiers per Phase 1.3 operator spec
FUTURES_TIERS = [[30, 1.0], [60, 0.7], [80, 0.4], [100, 0.0]]


class _RiskMode(Enum):
    """Lightweight RiskMode stand-in — avoids importing the LLM module."""

    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


def _make_ctx(
    risk_score: float = 50.0,
    confidence: float = 0.55,
    risk_mode_name: str = "NEUTRAL",
) -> SimpleNamespace:
    """Return a duck-typed MarketContext with the given values.

    Uses SimpleNamespace to avoid importing the real MarketContext class
    (which pulls in optional heavy dependencies like OpenAI/httpx).

    Args:
        risk_score: LLM risk score (0-100).
        confidence: LLM confidence (0.0-1.0).
        risk_mode_name: One of RISK_ON, NEUTRAL, RISK_OFF.

    Returns:
        A namespace object compatible with LLMAdaptiveSizer duck-typing.
    """
    return SimpleNamespace(
        risk_score=risk_score,
        confidence=confidence,
        risk_mode=_RiskMode[risk_mode_name],
    )


def _make_signal(price: float = 300.0) -> Signal:
    """Return a minimal entry Signal.

    Args:
        price: Signal price.

    Returns:
        Signal instance.
    """
    return Signal(
        code="A05603",
        name="KOSPI200 Mini",
        signal_type=SignalType.ENTRY,
        strategy="test",
        price=price,
    )


def _make_sizer(
    base_quantity: int = 5,
    max_quantity_cap: int | None = None,
    tiers: list[list[float]] | None = None,
    **extra: Any,
) -> LLMAdaptiveSizer:
    """Create an LLMAdaptiveSizer with tier-mode config.

    Args:
        base_quantity: Pre-scaling contract count.
        max_quantity_cap: Hard cap on final quantity (None = no cap).
        tiers: List of [upper_bound, scale] pairs. Defaults to FUTURES_TIERS.
        **extra: Additional config fields passed to from_dict.

    Returns:
        Configured LLMAdaptiveSizer.
    """
    if tiers is None:
        tiers = FUTURES_TIERS
    params: dict[str, Any] = {
        "base_quantity": base_quantity,
        "tiers": tiers,
    }
    if max_quantity_cap is not None:
        params["max_quantity_cap"] = max_quantity_cap
    params.update(extra)
    cfg = LLMAdaptiveSizerConfig.from_dict(params)
    return LLMAdaptiveSizer(cfg)


_SIGNAL = _make_signal()
_BALANCE = 100_000_000.0
_NO_POSITIONS: list = []


# ---------------------------------------------------------------------------
# (a) Tier boundary correctness
# ---------------------------------------------------------------------------


class TestTierBoundaries:
    """Verify each boundary value of the 4-tier ladder with base_quantity=5."""

    def test_risk_score_30_full_size(self) -> None:
        """risk_score=30 hits tier [30, 1.0] → ×1.0 → 5 contracts."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(30.0))
        assert qty == 5

    def test_risk_score_31_reduced(self) -> None:
        """risk_score=31 hits tier [60, 0.7] → ×0.7 → int(5×0.7)=3 contracts."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(31.0))
        assert qty == 3

    def test_risk_score_60_at_upper_bound(self) -> None:
        """risk_score=60 hits tier [60, 0.7] (inclusive upper bound) → 3 contracts."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(60.0))
        assert qty == 3

    def test_risk_score_61_further_reduced(self) -> None:
        """risk_score=61 hits tier [80, 0.4] → ×0.4 → int(5×0.4)=2 contracts."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(61.0))
        assert qty == 2

    def test_risk_score_80_at_upper_bound(self) -> None:
        """risk_score=80 hits tier [80, 0.4] (inclusive upper bound) → 2 contracts."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(80.0))
        assert qty == 2

    def test_risk_score_81_entry_skip(self) -> None:
        """risk_score=81 hits tier [100, 0.0] → ×0.0 → 0 (entry skip)."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(81.0))
        assert qty == 0


# ---------------------------------------------------------------------------
# (b) Entry-skip semantics for risk_score > 80
# ---------------------------------------------------------------------------


class TestEntrySkip:
    """risk_score > 80 must produce quantity=0 (entry skip)."""

    def test_risk_score_90_entry_skip(self) -> None:
        """risk_score=90 → scale=0.0 → entry skip."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(90.0))
        assert qty == 0

    def test_risk_score_100_entry_skip(self) -> None:
        """risk_score=100 (max) → scale=0.0 → entry skip."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(100.0))
        assert qty == 0

    def test_entry_skip_logs_but_does_not_raise(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify entry skip is logged and no exception is raised."""
        import logging

        sizer = _make_sizer(base_quantity=5)
        with caplog.at_level(logging.DEBUG, logger="shared.strategy.position.llm_adaptive_sizer"):
            qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(85.0))
        assert qty == 0
        assert "entry skip" in caplog.text.lower()


# ---------------------------------------------------------------------------
# (c) tiers=[] falls through to legacy single-threshold mode
# ---------------------------------------------------------------------------


class TestLegacyFallback:
    """When tiers=[], the sizer must behave exactly like the old code."""

    def _make_legacy_sizer(self, **kwargs: Any) -> LLMAdaptiveSizer:
        """Build a sizer with tiers=[] (stock mode)."""
        params: dict[str, Any] = {
            "tiers": [],
            "risk_per_trade_pct": 1.0,
            "stop_loss_pct": 2.0,
            "max_positions": 10,
            "min_quantity": 1,
            "max_quantity": 10_000,
        }
        params.update(kwargs)
        cfg = LLMAdaptiveSizerConfig.from_dict(params)
        return LLMAdaptiveSizer(cfg)

    def test_tiers_empty_activates_legacy_path(self) -> None:
        """With tiers=[], risk_score below threshold → no risk_score penalty."""
        sizer = self._make_legacy_sizer(
            risk_score_threshold_high=70.0,
            risk_score_penalty_high=0.6,
            enable_confidence_scaling=False,
            enable_risk_mode_scaling=False,
        )
        # risk_score=50 < threshold=70 → no penalty → full size
        ctx = _make_ctx(risk_score=50.0, confidence=0.5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        # RiskBasedSizer will compute from risk_per_trade_pct / stop_loss_pct
        # risk_amount = 100M * 1% = 1M, loss_per_share = 300 * 2% = 6, qty = 166_666
        assert qty > 0
        assert isinstance(qty, int)

    def test_tiers_empty_high_risk_score_penalty_applies(self) -> None:
        """With tiers=[], risk_score above threshold → single-threshold penalty applies."""
        sizer = self._make_legacy_sizer(
            risk_score_threshold_high=70.0,
            risk_score_penalty_high=0.6,
            enable_confidence_scaling=False,
            enable_risk_mode_scaling=False,
        )
        ctx_low = _make_ctx(risk_score=50.0, confidence=0.5)
        ctx_high = _make_ctx(risk_score=75.0, confidence=0.5)
        qty_low = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx_low)
        qty_high = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx_high)
        # High-risk path applies 0.6x penalty so qty_high < qty_low
        assert qty_high < qty_low
        assert qty_high == int(qty_low * 0.6)

    def test_tiers_empty_no_context_returns_base(self) -> None:
        """With tiers=[], market_context=None → falls back to RiskBasedSizer."""
        sizer = self._make_legacy_sizer()
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, None)
        assert qty > 0


# ---------------------------------------------------------------------------
# (d) max_quantity_cap clamps output
# ---------------------------------------------------------------------------


class TestMaxQuantityCap:
    """max_quantity_cap must clamp even when tier scaling produces more."""

    def test_cap_clamps_above_threshold(self) -> None:
        """base=5, scale=1.0, cap=1 → result=1 (clamped from 5)."""
        sizer = _make_sizer(base_quantity=5, max_quantity_cap=1)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(25.0))
        assert qty == 1

    def test_cap_does_not_inflate(self) -> None:
        """base=1, scale=1.0, cap=5 → result=1 (cap is upper bound only)."""
        sizer = _make_sizer(base_quantity=1, max_quantity_cap=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(25.0))
        assert qty == 1

    def test_cap_none_no_clamping(self) -> None:
        """max_quantity_cap=None → no clamping applied."""
        sizer = _make_sizer(base_quantity=5, max_quantity_cap=None)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(25.0))
        assert qty == 5

    def test_cap_with_confidence_boost(self) -> None:
        """Even with confidence boost the cap is enforced."""
        sizer = _make_sizer(
            base_quantity=5,
            max_quantity_cap=3,
            confidence_boost_high=2.0,  # Would multiply by 2x without cap
            confidence_threshold_high=0.5,
        )
        # base=5, tier_scale=1.0 (score=20), conf_mult=2.0 → 10 → clamped to 3
        ctx = _make_ctx(risk_score=20.0, confidence=0.9)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        assert qty == 3


# ---------------------------------------------------------------------------
# (e) market_context=None → graceful degradation
# ---------------------------------------------------------------------------


class TestNoMarketContext:
    """When market_context is None, the sizer must return base_quantity (tier mode)."""

    def test_no_context_returns_base_quantity(self) -> None:
        """tier mode: market_context=None → base_quantity returned (no scaling)."""
        sizer = _make_sizer(base_quantity=2)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, None)
        assert qty == 2

    def test_no_context_cap_still_applies(self) -> None:
        """Even without context, max_quantity_cap clamps base_quantity."""
        sizer = _make_sizer(base_quantity=5, max_quantity_cap=2)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, None)
        assert qty == 2


# ---------------------------------------------------------------------------
# (f) Backward compat: existing stock single-threshold tests still pass
# ---------------------------------------------------------------------------


class TestBackwardCompatStock:
    """Existing stock behavior is preserved when tiers is empty (default)."""

    def test_high_confidence_boost(self) -> None:
        """Confidence >= threshold → boost applied.

        max_quantity is set large enough that the 1.5x boost fits without
        hitting the upper cap.
        """
        cfg = LLMAdaptiveSizerConfig.from_dict(
            {
                "tiers": [],
                "confidence_boost_high": 1.5,
                "confidence_threshold_high": 0.7,
                "enable_risk_score_scaling": False,
                "enable_risk_mode_scaling": False,
                "max_quantity": 1_000_000,  # no cap interference
            }
        )
        sizer = LLMAdaptiveSizer(cfg)
        ctx = _make_ctx(confidence=0.9)
        qty_with_ctx = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        qty_no_ctx = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, None)
        assert qty_with_ctx == int(qty_no_ctx * 1.5)

    def test_low_confidence_penalty(self) -> None:
        """Confidence < threshold → penalty applied."""
        cfg = LLMAdaptiveSizerConfig.from_dict(
            {
                "tiers": [],
                "confidence_penalty_low": 0.5,
                "confidence_threshold_low": 0.4,
                "enable_risk_score_scaling": False,
                "enable_risk_mode_scaling": False,
            }
        )
        sizer = LLMAdaptiveSizer(cfg)
        ctx = _make_ctx(confidence=0.2)
        qty_with_ctx = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        qty_no_ctx = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, None)
        assert qty_with_ctx == int(qty_no_ctx * 0.5)

    def test_risk_mode_risk_off_penalty(self) -> None:
        """RISK_OFF mode applies penalty in legacy mode."""
        cfg = LLMAdaptiveSizerConfig.from_dict(
            {
                "tiers": [],
                "risk_mode_scaling": {"RISK_ON": 1.2, "NEUTRAL": 1.0, "RISK_OFF": 0.5},
                "enable_risk_score_scaling": False,
                "enable_confidence_scaling": False,
            }
        )
        sizer = LLMAdaptiveSizer(cfg)
        ctx_neutral = _make_ctx(risk_mode_name="NEUTRAL")
        ctx_risk_off = _make_ctx(risk_mode_name="RISK_OFF")
        qty_neutral = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx_neutral)
        qty_risk_off = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx_risk_off)
        assert qty_risk_off == int(qty_neutral * 0.5)


# ---------------------------------------------------------------------------
# (g) Tier fallback: risk_score exceeds all upper_bounds
# ---------------------------------------------------------------------------


class TestTierFallback:
    """When risk_score exceeds all tier upper_bounds, fall back to 0.0 (entry skip)."""

    def test_risk_score_above_all_tiers_skips_entry(self) -> None:
        """risk_score=200 > max tier upper_bound=100 → 0 (entry skip)."""
        sizer = _make_sizer(base_quantity=5)
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, _make_ctx(200.0))
        assert qty == 0


# ---------------------------------------------------------------------------
# (h) Confidence and risk_mode modifiers applied on top of tier scale
# ---------------------------------------------------------------------------


class TestTierPlusModifiers:
    """Confidence and risk_mode multipliers stack on top of the tier scale."""

    def test_tier_scale_with_neutral_mode_no_change(self) -> None:
        """NEUTRAL mode (×1.0) and mid confidence (×1.0) → pure tier result."""
        sizer = _make_sizer(base_quantity=10)
        ctx = _make_ctx(risk_score=40.0, confidence=0.5, risk_mode_name="NEUTRAL")
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        # tier=0.7, conf=1.0, mode=1.0 → int(10 * 0.7) = 7
        assert qty == 7

    def test_tier_scale_with_risk_on_boost(self) -> None:
        """RISK_ON (×1.2) applied on top of tier 0.7 → int(10 * 0.7 * 1.2) = 8."""
        sizer = _make_sizer(
            base_quantity=10,
            risk_mode_scaling={"RISK_ON": 1.2, "NEUTRAL": 1.0, "RISK_OFF": 0.5},
        )
        ctx = _make_ctx(risk_score=40.0, confidence=0.5, risk_mode_name="RISK_ON")
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        assert qty == int(10 * 0.7 * 1.2)  # = 8

    def test_tier_scale_with_high_confidence_boost(self) -> None:
        """High confidence boost (×1.2) stacks on top of tier 1.0 → int(5*1.0*1.2)=6."""
        sizer = _make_sizer(
            base_quantity=5,
            confidence_boost_high=1.2,
            confidence_threshold_high=0.7,
        )
        ctx = _make_ctx(risk_score=20.0, confidence=0.9, risk_mode_name="NEUTRAL")
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        assert qty == int(5 * 1.0 * 1.2)  # = 6

    def test_entry_skip_ignores_modifiers(self) -> None:
        """Once tier scale = 0.0, no modifier can rescue the entry."""
        sizer = _make_sizer(
            base_quantity=5,
            confidence_boost_high=100.0,  # extreme boost, should be irrelevant
        )
        ctx = _make_ctx(risk_score=90.0, confidence=0.99, risk_mode_name="RISK_ON")
        qty = sizer.calculate(_SIGNAL, _BALANCE, _NO_POSITIONS, ctx)
        assert qty == 0


# ---------------------------------------------------------------------------
# LLMAdaptiveSizerConfig.from_dict — parsing validation
# ---------------------------------------------------------------------------


class TestConfigParsing:
    """Verify from_dict handles both list-of-lists and empty tiers correctly."""

    def test_from_dict_parses_list_of_lists(self) -> None:
        """YAML-style [[upper, scale], ...] parsed into list of tuples."""
        cfg = LLMAdaptiveSizerConfig.from_dict(
            {"tiers": [[30, 1.0], [60, 0.7], [80, 0.4], [100, 0.0]]}
        )
        assert len(cfg.tiers) == 4
        assert cfg.tiers[0] == (30.0, 1.0)
        assert cfg.tiers[3] == (100.0, 0.0)

    def test_from_dict_empty_tiers_is_empty_list(self) -> None:
        """tiers: [] yields an empty list → activates legacy mode."""
        cfg = LLMAdaptiveSizerConfig.from_dict({"tiers": []})
        assert cfg.tiers == []

    def test_from_dict_max_quantity_cap_none_by_default(self) -> None:
        """max_quantity_cap defaults to None when not provided."""
        cfg = LLMAdaptiveSizerConfig.from_dict({})
        assert cfg.max_quantity_cap is None

    def test_from_dict_max_quantity_cap_parsed(self) -> None:
        """max_quantity_cap is parsed as int from YAML int."""
        cfg = LLMAdaptiveSizerConfig.from_dict({"max_quantity_cap": 1})
        assert cfg.max_quantity_cap == 1
        assert isinstance(cfg.max_quantity_cap, int)

    def test_from_dict_base_quantity_default(self) -> None:
        """base_quantity defaults to 0 (use RiskBasedSizer calc)."""
        cfg = LLMAdaptiveSizerConfig.from_dict({})
        assert cfg.base_quantity == 0
