"""Unit + golden tests for ``shared.risk.primitives.extremes``."""

from __future__ import annotations

import pytest

from shared.models.position import PositionSide
from shared.risk.primitives.extremes import extreme_since_entry
from tests.unit.risk.primitives.helpers import make_position

ENTRIES = [70.0, 100.0, 250.5, 70000.0]
MOVE_FACTORS = [0.85, 0.95, 1.0, 1.001, 1.12]


class TestExtremeSinceEntryUnit:
    """Direct behavior of extreme_since_entry."""

    def test_long_tracked_high_wins(self) -> None:
        pos = make_position(PositionSide.LONG, 100.0, highest_price=110.0)
        assert extreme_since_entry(pos, 105.0) == 110.0

    def test_long_current_price_folds_in(self) -> None:
        pos = make_position(PositionSide.LONG, 100.0, highest_price=110.0)
        assert extreme_since_entry(pos, 115.0) == 115.0

    def test_long_unset_high_falls_back_to_entry(self) -> None:
        """highest_price == 0.0 (legacy unset) → entry_price fallback."""
        pos = make_position(PositionSide.LONG, 100.0, highest_price=0.0)
        assert extreme_since_entry(pos, 99.0) == 100.0

    def test_short_tracked_low_wins(self) -> None:
        pos = make_position(PositionSide.SHORT, 100.0, lowest_price=90.0)
        assert extreme_since_entry(pos, 95.0) == 90.0

    def test_short_current_price_folds_in(self) -> None:
        pos = make_position(PositionSide.SHORT, 100.0, lowest_price=90.0)
        assert extreme_since_entry(pos, 88.0) == 88.0

    def test_short_unset_low_falls_back_to_entry(self) -> None:
        """lowest_price == inf (legacy unset) → entry_price fallback."""
        pos = make_position(PositionSide.SHORT, 100.0, lowest_price=float("inf"))
        assert extreme_since_entry(pos, 101.0) == 100.0

    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("delta_pct", [0.001, 0.02, 0.1])
    def test_long_short_mirror_symmetry(self, entry: float, delta_pct: float) -> None:
        """Favorable extremes mirror around entry (futures symmetry)."""
        up = entry * (1 + delta_pct)
        down = entry * (1 - delta_pct)
        long_pos = make_position(PositionSide.LONG, entry, highest_price=up)
        short_pos = make_position(PositionSide.SHORT, entry, lowest_price=down)
        long_extreme = extreme_since_entry(long_pos, entry)
        short_extreme = extreme_since_entry(short_pos, entry)
        assert long_extreme - entry == pytest.approx(entry - short_extreme)


class TestExtremeSinceEntryGolden:
    """extreme_since_entry pinned to the independent min/max formula."""

    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("high_factor", [1.0, 1.03, 1.15])
    @pytest.mark.parametrize("current_factor", MOVE_FACTORS)
    def test_long_grid_golden(
        self,
        entry: float,
        high_factor: float,
        current_factor: float,
    ) -> None:
        """LONG favorable extreme == ``max(tracked_high, current)``."""
        high = entry * high_factor
        current = entry * current_factor
        pos = make_position(PositionSide.LONG, entry, highest_price=high)
        assert extreme_since_entry(pos, current) == max(high, current)

    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("low_factor", [0.85, 0.97, 1.0])
    @pytest.mark.parametrize("current_factor", MOVE_FACTORS)
    def test_short_grid_golden(
        self,
        entry: float,
        low_factor: float,
        current_factor: float,
    ) -> None:
        """SHORT favorable extreme == ``min(tracked_low, current)``."""
        low = entry * low_factor
        current = entry * current_factor
        pos = make_position(PositionSide.SHORT, entry, lowest_price=low)
        assert extreme_since_entry(pos, current) == min(low, current)

    def test_unset_extremes_golden(self) -> None:
        """Unset sentinels (0.0 high / inf low) fall back to entry_price."""
        long_pos = make_position(PositionSide.LONG, 100.0, highest_price=0.0)
        short_pos = make_position(PositionSide.SHORT, 100.0, lowest_price=float("inf"))
        cases = [
            (95.0, 100.0, 95.0),
            (100.0, 100.0, 100.0),
            (105.0, 105.0, 100.0),
        ]
        for current, long_expected, short_expected in cases:
            assert extreme_since_entry(long_pos, current) == long_expected
            assert extreme_since_entry(short_pos, current) == short_expected
