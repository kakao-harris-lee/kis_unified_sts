"""Tick math utilities — Phase 4 Task 4."""

import pytest

from shared.execution.tick_math import _compute_slippage_ticks, _round_to_tick


class TestRoundToTick:
    def test_exactly_on_tick_unchanged(self):
        assert _round_to_tick(331.20, tick_size=0.02) == 331.20
        assert _round_to_tick(331.05, tick_size=0.05) == 331.05

    def test_rounds_to_nearest_tick_mini(self):
        # mini tick_size = 0.02
        assert _round_to_tick(331.211, tick_size=0.02) == 331.22
        assert _round_to_tick(331.219, tick_size=0.02) == 331.22
        assert _round_to_tick(331.209, tick_size=0.02) == 331.20

    def test_rounds_to_nearest_tick_f200(self):
        # F200 tick_size = 0.05
        assert _round_to_tick(331.27, tick_size=0.05) == 331.25
        assert _round_to_tick(331.28, tick_size=0.05) == 331.30

    def test_handles_floating_point_quirks(self):
        # 0.1 + 0.2 != 0.3 in float — verify the double-round absorbs it
        result = _round_to_tick(0.1 + 0.2, tick_size=0.02)
        assert result == 0.30

    def test_negative_prices_rounded(self):
        # Defensive — futures don't go negative but the math should be robust
        assert _round_to_tick(-100.011, tick_size=0.02) == -100.02


class TestComputeSlippageTicks:
    def test_long_filled_higher_is_positive_slip(self):
        # long pays more than requested → +slip
        slip = _compute_slippage_ticks(
            requested=331.20, filled=331.24, direction="long", tick_size=0.02
        )
        assert slip == pytest.approx(2.0)

    def test_long_filled_lower_is_negative_slip(self):
        # long pays less than requested → -slip (price improvement)
        slip = _compute_slippage_ticks(
            requested=331.20, filled=331.16, direction="long", tick_size=0.02
        )
        assert slip == pytest.approx(-2.0)

    def test_short_filled_lower_is_positive_slip(self):
        # short receives less than requested → +slip
        slip = _compute_slippage_ticks(
            requested=331.20, filled=331.16, direction="short", tick_size=0.02
        )
        assert slip == pytest.approx(2.0)

    def test_short_filled_higher_is_negative_slip(self):
        slip = _compute_slippage_ticks(
            requested=331.20, filled=331.24, direction="short", tick_size=0.02
        )
        assert slip == pytest.approx(-2.0)

    def test_zero_slip(self):
        slip = _compute_slippage_ticks(
            requested=331.20, filled=331.20, direction="long", tick_size=0.02
        )
        assert slip == pytest.approx(0.0)

    def test_unknown_direction_raises(self):
        with pytest.raises(ValueError, match="direction"):
            _compute_slippage_ticks(
                requested=1.0, filled=1.0, direction="sideways", tick_size=0.02
            )

    def test_zero_tick_size_raises(self):
        with pytest.raises(ValueError, match="tick_size"):
            _compute_slippage_ticks(
                requested=1.0, filled=1.0, direction="long", tick_size=0.0
            )
