"""Unit + golden tests for ``shared.risk.primitives.stops``.

Test contract (post P4-b): every stop primitive is pinned to **independent
golden values** — the expected result is restated from the documented formula
or written as a literal, never read back from an exit class.

    Why not differential vs the legacy call sites? P4-b rewired
    ``momentum_decay._stop_hit`` / ``three_stage._stop_hit`` /
    ``setup_target._price_crossed(trigger="stop")`` → :func:`abs_stop_hit`,
    ``track_a_exit.trail_stop_price`` → :func:`atr_stop_level`, and
    ``three_stage._calculate_trailing_stop`` → :func:`pct_trailing_stop_level`
    (gap selection stays at the call site). Comparing a primitive against a
    method that now *delegates* to it is a tautology (``f(x) == f(x)``) with no
    independent cross-check, so the grids below compare against the hand-derived
    formula instead — same input width, real regression protection.
"""

from __future__ import annotations

import pytest

from shared.models.position import PositionSide
from shared.risk.primitives.stops import (
    abs_stop_hit,
    atr_stop_level,
    pct_stop_hit,
    pct_trailing_stop_level,
    trailing_stop_hit,
)
from tests.unit.risk.primitives.helpers import make_position

SIDES = [PositionSide.LONG, PositionSide.SHORT]
PRICES = [95.0, 99.999, 100.0, 100.001, 105.0]
STOPS = [98.0, 100.0, 102.0]


class TestAbsStopHitUnit:
    """Direct behavior of abs_stop_hit."""

    @pytest.mark.parametrize(
        ("side", "current", "stop", "expected"),
        [
            (PositionSide.LONG, 97.0, 98.0, True),
            (PositionSide.LONG, 98.0, 98.0, True),
            (PositionSide.LONG, 99.0, 98.0, False),
            (PositionSide.SHORT, 103.0, 102.0, True),
            (PositionSide.SHORT, 102.0, 102.0, True),
            (PositionSide.SHORT, 101.0, 102.0, False),
        ],
    )
    def test_inclusive(
        self, side: PositionSide, current: float, stop: float, expected: bool
    ) -> None:
        assert abs_stop_hit(side, current, stop) is expected

    @pytest.mark.parametrize("side", SIDES)
    def test_strict_excludes_touch(self, side: PositionSide) -> None:
        """inclusive=False: touching the level does not fire (chandelier)."""
        assert abs_stop_hit(side, 100.0, 100.0, inclusive=False) is False
        assert abs_stop_hit(side, 100.0, 100.0, inclusive=True) is True

    @pytest.mark.parametrize("offset", [0.5, 2.0, 10.0])
    def test_long_short_mirror_symmetry(self, offset: float) -> None:
        """LONG stop below entry mirrors SHORT stop above (futures symmetry)."""
        entry = 100.0
        assert abs_stop_hit(
            PositionSide.LONG, entry - offset, entry - offset
        ) == abs_stop_hit(PositionSide.SHORT, entry + offset, entry + offset)
        assert abs_stop_hit(
            PositionSide.LONG, entry - offset - 1, entry - offset
        ) == abs_stop_hit(PositionSide.SHORT, entry + offset + 1, entry + offset)


class TestAbsStopHitGolden:
    """abs_stop_hit pinned to the direction-aware inclusive-cross formula.

    Golden: LONG fires when ``current <= stop``; SHORT fires when
    ``current >= stop``. This single golden subsumes the former differential
    tests against ``momentum_decay._stop_hit`` / ``three_stage._stop_hit`` /
    ``setup_target._price_crossed(trigger="stop")`` — all of which delegate to
    ``abs_stop_hit`` after P4-b, so those comparisons were tautological.
    """

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("current", PRICES)
    @pytest.mark.parametrize("stop", STOPS)
    def test_grid_golden(self, side: PositionSide, current: float, stop: float) -> None:
        expected = current <= stop if side == PositionSide.LONG else current >= stop
        assert abs_stop_hit(side, current, stop) is expected


class TestPctStopHit:
    """pct_stop_hit unit + golden against the independent profit formula."""

    def test_long_stop_fires_at_threshold(self) -> None:
        pos = make_position(PositionSide.LONG, 100.0)
        assert pct_stop_hit(pos, 98.0, -0.02) is True
        assert pct_stop_hit(pos, 98.5, -0.02) is False

    def test_short_stop_fires_at_threshold(self) -> None:
        pos = make_position(PositionSide.SHORT, 100.0)
        assert pct_stop_hit(pos, 102.0, -0.02) is True
        assert pct_stop_hit(pos, 101.5, -0.02) is False

    def test_zero_entry_guard(self) -> None:
        """entry <= 0 → profit 0.0: fires only for non-negative thresholds."""
        pos = make_position(PositionSide.LONG, 0.0)
        assert pct_stop_hit(pos, 100.0, -0.02) is False
        assert pct_stop_hit(pos, 100.0, 0.0) is True

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("factor", [0.9, 0.97, 0.98, 1.0, 1.02, 1.03, 1.1])
    @pytest.mark.parametrize("threshold", [-0.03, -0.02, 0.0])
    def test_grid_golden(
        self, side: PositionSide, factor: float, threshold: float
    ) -> None:
        """Fires iff the side-aware profit ratio <= threshold.

        Golden profit is restated from the spec (``(current - entry) / entry``
        for LONG, mirror for SHORT) using the same ``current`` the primitive
        sees, so the boolean is float-stable at the -0.02/-0.03 boundaries and
        independent of the primitive's own arithmetic (the old
        ``_calc_profit_pct(...) <= threshold`` derivation delegated to
        ``profit_pct`` after P4-b and was tautological).
        """
        entry = 100.0
        pos = make_position(side, entry)
        current = entry * factor
        if side == PositionSide.LONG:
            expected_profit = (current - entry) / entry
        else:
            expected_profit = (entry - current) / entry
        expected = expected_profit <= threshold
        assert pct_stop_hit(pos, current, threshold) is expected


class TestAtrStopLevel:
    """atr_stop_level unit + golden."""

    def test_long_level_below_reference(self) -> None:
        assert atr_stop_level(100.0, 2.0, 1.5, PositionSide.LONG) == 97.0

    def test_short_level_above_reference(self) -> None:
        assert atr_stop_level(100.0, 2.0, 1.5, PositionSide.SHORT) == 103.0

    @pytest.mark.parametrize("atr", [0.5, 2.0, 35.0])
    @pytest.mark.parametrize("mult", [1.0, 2.5, 3.0])
    def test_long_short_mirror_symmetry(self, atr: float, mult: float) -> None:
        ref = 250.5
        long_level = atr_stop_level(ref, atr, mult, PositionSide.LONG)
        short_level = atr_stop_level(ref, atr, mult, PositionSide.SHORT)
        assert ref - long_level == pytest.approx(short_level - ref)

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("extreme", [95.0, 100.0, 351.25])
    @pytest.mark.parametrize("atr", [0.4, 2.0, 12.5])
    @pytest.mark.parametrize("mult", [1.0, 2.0, 3.5])
    def test_grid_golden(
        self, side: PositionSide, extreme: float, atr: float, mult: float
    ) -> None:
        """LONG: ``extreme - mult*atr`` ; SHORT: ``extreme + mult*atr``.

        Independent formula (formerly compared against
        ``track_a_exit.trail_stop_price``, which delegates to this primitive
        after P4-b — a tautology).
        """
        offset = mult * atr
        expected = extreme - offset if side == PositionSide.LONG else extreme + offset
        assert atr_stop_level(extreme, atr, mult, side) == expected

    @pytest.mark.parametrize("highest_high", [100.0, 351.25, 70000.0])
    @pytest.mark.parametrize("atr", [0.4, 2.0, 350.0])
    @pytest.mark.parametrize("mult", [2.0, 3.0])
    def test_chandelier_level_golden(
        self, highest_high: float, atr: float, mult: float
    ) -> None:
        """chandelier_stop = highest_high - atr * multiplier (LONG-shaped).

        The reference level is computed inline (independent), and the strict
        ``close < chandelier_stop`` cross semantics are pinned directly.
        """
        chandelier_stop = highest_high - atr * mult
        assert atr_stop_level(highest_high, atr, mult, PositionSide.LONG) == (
            chandelier_stop
        )
        # Strict cross semantics: close < chandelier_stop.
        for close in (chandelier_stop - 0.01, chandelier_stop, chandelier_stop + 0.01):
            assert abs_stop_hit(
                PositionSide.LONG, close, chandelier_stop, inclusive=False
            ) == (close < chandelier_stop)


class TestPctTrailingStopLevel:
    """pct_trailing_stop_level unit + golden."""

    def test_long_level(self) -> None:
        assert pct_trailing_stop_level(110.0, 0.03, PositionSide.LONG) == pytest.approx(
            106.7
        )

    def test_short_level(self) -> None:
        assert pct_trailing_stop_level(90.0, 0.03, PositionSide.SHORT) == pytest.approx(
            92.7
        )

    @pytest.mark.parametrize("retrace", [-0.03, 0.03])
    def test_sign_of_retrace_ignored(self, retrace: float) -> None:
        """Legacy sites configure negative gaps and abs() them."""
        assert pct_trailing_stop_level(
            110.0, retrace, PositionSide.LONG
        ) == pytest.approx(106.7)

    @pytest.mark.parametrize("extreme", [104.0, 110.0, 351.25])
    @pytest.mark.parametrize("gap", [-0.05, -0.03, -0.015])
    @pytest.mark.parametrize("side", SIDES)
    def test_grid_golden(self, extreme: float, gap: float, side: PositionSide) -> None:
        """LONG: ``extreme*(1-|gap|)`` ; SHORT: ``extreme*(1+|gap|)``.

        Independent formula (formerly compared against
        ``three_stage._calculate_trailing_stop`` with the overshoot branch off,
        which delegates the level math to this primitive after P4-b).
        """
        g = abs(gap)
        if side == PositionSide.LONG:
            expected = extreme * (1 - g)
        else:
            expected = extreme * (1 + g)
        assert pct_trailing_stop_level(extreme, gap, side) == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("side", "extreme", "expected"),
        [
            (PositionSide.LONG, 110.0, 108.35),  # 110 * (1 - 0.015)
            (PositionSide.SHORT, 90.0, 91.35),  # 90 * (1 + 0.015)
        ],
    )
    def test_overshoot_gap_level_golden(
        self, side: PositionSide, extreme: float, expected: float
    ) -> None:
        """Primitive level for the tightened overshoot gap (0.015).

        WHICH gap ``three_stage`` selects under overshoot (``trailing_stop_pct``
        vs ``overshoot_trailing_pct``) is exit-generator logic covered by
        ``three_stage``'s own tests; here we only pin the primitive level math
        for the tightened gap value with an independent golden.
        """
        assert pct_trailing_stop_level(extreme, -0.015, side) == pytest.approx(expected)


class TestTrailingStopHit:
    """trailing_stop_hit composition and form validation."""

    def test_pct_form_long(self) -> None:
        assert (
            trailing_stop_hit(PositionSide.LONG, 106.0, 110.0, retrace_pct=0.03) is True
        )
        assert (
            trailing_stop_hit(PositionSide.LONG, 107.0, 110.0, retrace_pct=0.03)
            is False
        )

    def test_atr_form_short(self) -> None:
        # SHORT extreme 90, trail level 90 + 2*1.5 = 93.
        assert (
            trailing_stop_hit(
                PositionSide.SHORT, 93.0, 90.0, atr=1.5, atr_multiplier=2.0
            )
            is True
        )
        assert (
            trailing_stop_hit(
                PositionSide.SHORT, 92.9, 90.0, atr=1.5, atr_multiplier=2.0
            )
            is False
        )

    def test_strict_cross_excludes_touch(self) -> None:
        """chandelier semantics: touching the level does not fire."""
        assert (
            trailing_stop_hit(
                PositionSide.LONG,
                104.0,
                110.0,
                atr=2.0,
                atr_multiplier=3.0,
                inclusive=False,
            )
            is False
        )

    def test_rejects_both_forms(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            trailing_stop_hit(
                PositionSide.LONG,
                100.0,
                110.0,
                retrace_pct=0.03,
                atr=2.0,
                atr_multiplier=3.0,
            )

    def test_rejects_no_form(self) -> None:
        with pytest.raises(ValueError, match="pass retrace_pct"):
            trailing_stop_hit(PositionSide.LONG, 100.0, 110.0)

    def test_rejects_partial_atr_form(self) -> None:
        with pytest.raises(ValueError, match="pass retrace_pct"):
            trailing_stop_hit(PositionSide.LONG, 100.0, 110.0, atr=2.0)

    @pytest.mark.parametrize("delta_pct", [0.01, 0.03, 0.1])
    def test_long_short_mirror_symmetry(self, delta_pct: float) -> None:
        """Mirrored SHORT scenario decides identically (futures symmetry)."""
        entry = 100.0
        long_extreme = entry * (1 + 0.08)
        short_extreme = entry * (1 - 0.08)
        long_current = long_extreme * (1 - delta_pct)
        short_current = short_extreme * (1 + delta_pct)
        assert trailing_stop_hit(
            PositionSide.LONG, long_current, long_extreme, retrace_pct=0.03
        ) == trailing_stop_hit(
            PositionSide.SHORT, short_current, short_extreme, retrace_pct=0.03
        )
