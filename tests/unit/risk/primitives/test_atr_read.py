"""Unit + differential tests for ``shared.risk.primitives.atr_read``.

Differential contracts (read-only legacy imports; dict extraction stays at
the call sites, so the legacy methods are fed single-key dicts):
- ``atr_dynamic._get_atr``: threshold 0.5, reference == current_price.
- ``mean_reversion_exit._get_atr``: threshold 0.5 (its docstring says "< 1.0"
  but the code compares against 0.5), reference == close.
- ``track_a_exit._get_atr``: no normalization → ``normalized_below=None``.
"""

from __future__ import annotations

import pytest

from shared.models.position import PositionSide
from shared.risk.primitives.atr_read import normalize_atr
from shared.strategy.exit.atr_dynamic import ATRDynamicExit
from shared.strategy.exit.mean_reversion_exit import MeanReversionExit
from shared.strategy.exit.track_a_exit import TrackAExit
from tests.unit.risk.primitives.helpers import make_position

# Raw readings spanning normalized-ratio and absolute forms, plus the
# 0.5-threshold boundary itself.
RAW_ATRS = [0.001, 0.02, 0.4999, 0.5, 0.75, 1.0, 2.5, 350.0]
REFERENCE_PRICES = [70.0, 100.0, 70000.0]


class TestNormalizeAtrUnit:
    """Direct behavior of normalize_atr."""

    def test_normalized_reading_is_scaled(self) -> None:
        assert normalize_atr(0.02, 100.0, normalized_below=0.5) == pytest.approx(2.0)

    def test_absolute_reading_passes_through(self) -> None:
        assert normalize_atr(2.5, 100.0, normalized_below=0.5) == 2.5

    def test_threshold_is_exclusive(self) -> None:
        """Readings exactly at the threshold are treated as absolute."""
        assert normalize_atr(0.5, 100.0, normalized_below=0.5) == 0.5

    def test_none_threshold_disables_normalization(self) -> None:
        assert normalize_atr(0.02, 100.0, normalized_below=None) == 0.02

    @pytest.mark.parametrize("raw", [0.0, -1.0])
    def test_non_positive_reading_returns_zero(self, raw: float) -> None:
        assert normalize_atr(raw, 100.0, normalized_below=0.5) == 0.0

    def test_non_positive_reference_passes_through(self) -> None:
        """No reference price to de-normalize with → raw pass-through."""
        assert normalize_atr(0.02, 0.0, normalized_below=0.5) == 0.02


class TestDifferentialAtrDynamic:
    """normalize_atr(threshold 0.5, ref current_price) == atr_dynamic._get_atr."""

    @pytest.mark.parametrize("raw", RAW_ATRS)
    @pytest.mark.parametrize("price", REFERENCE_PRICES)
    def test_grid_equivalence(self, raw: float, price: float) -> None:
        assert normalize_atr(raw, price, normalized_below=0.5) == (
            ATRDynamicExit._get_atr({"atr": raw}, price)
        )

    @pytest.mark.parametrize("raw", [0.0, -1.0])
    def test_non_positive_equivalence(self, raw: float) -> None:
        assert normalize_atr(raw, 100.0, normalized_below=0.5) == (
            ATRDynamicExit._get_atr({"atr": raw}, 100.0)
        )

    def test_zero_price_equivalence(self) -> None:
        assert normalize_atr(0.02, 0.0, normalized_below=0.5) == (
            ATRDynamicExit._get_atr({"atr": 0.02}, 0.0)
        )


class TestDifferentialMeanReversion:
    """normalize_atr(threshold 0.5, ref close) == mean_reversion._get_atr."""

    @pytest.mark.parametrize("raw", RAW_ATRS)
    @pytest.mark.parametrize("close", REFERENCE_PRICES)
    def test_grid_equivalence(self, raw: float, close: float) -> None:
        assert normalize_atr(raw, close, normalized_below=0.5) == (
            MeanReversionExit._get_atr({"atr": raw}, {"close": close})
        )

    def test_missing_close_passes_through(self) -> None:
        """No close available → legacy leaves the ratio as-is; so do we."""
        assert normalize_atr(0.02, 0.0, normalized_below=0.5) == (
            MeanReversionExit._get_atr({"atr": 0.02}, {})
        )


class TestDifferentialTrackA:
    """normalized_below=None == track_a pass-through (no normalization)."""

    @pytest.mark.parametrize("raw", RAW_ATRS)
    @pytest.mark.parametrize("price", REFERENCE_PRICES)
    def test_grid_equivalence(self, raw: float, price: float) -> None:
        pos = make_position(PositionSide.LONG, price)
        # _get_atr does not use ``self``; unbound call keeps this read-only.
        legacy = TrackAExit._get_atr(None, {"atr": raw}, pos)
        assert normalize_atr(raw, price, normalized_below=None) == legacy

    def test_small_ratio_not_scaled_unlike_atr_dynamic(self) -> None:
        """Pins the intentional per-site difference the threshold argument encodes."""
        pos = make_position(PositionSide.LONG, 100.0)
        assert TrackAExit._get_atr(None, {"atr": 0.02}, pos) == 0.02
        assert ATRDynamicExit._get_atr({"atr": 0.02}, 100.0) == pytest.approx(2.0)
        assert normalize_atr(0.02, 100.0, normalized_below=None) == 0.02
        assert normalize_atr(0.02, 100.0, normalized_below=0.5) == pytest.approx(2.0)
