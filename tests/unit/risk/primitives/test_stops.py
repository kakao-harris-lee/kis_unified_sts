"""Unit + differential tests for ``shared.risk.primitives.stops``.

Differential contracts (read-only legacy imports):
- ``abs_stop_hit`` == ``momentum_decay._stop_hit`` / ``three_stage._stop_hit``
  / ``setup_target_exit._price_crossed(trigger="stop")`` (inclusive) and the
  ``chandelier_exit`` strict-``<`` cross (``inclusive=False``).
- ``atr_stop_level`` == ``track_a_exit.trail_stop_price`` and the chandelier
  level formula (``highest_high - atr * multiplier``).
- ``pct_trailing_stop_level`` == ``three_stage._calculate_trailing_stop``
  (clamping via ``position.stop_price`` stays at the call site; tested with
  ``stop_price == 0`` where the legacy clamp is inert).
- ``pct_stop_hit`` == the legacy ``profit_pct <= stop_loss_pct`` condition.
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
from shared.strategy.exit.momentum_decay import MomentumDecayExit
from shared.strategy.exit.setup_target_exit import SetupTargetExit
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig
from shared.strategy.exit.track_a_exit import trail_stop_price
from tests.unit.risk.primitives.helpers import make_position

SIDES = [PositionSide.LONG, PositionSide.SHORT]
STOP_HIT_LEGACY = [MomentumDecayExit, ThreeStageExit]
PRICES = [95.0, 99.999, 100.0, 100.001, 105.0]
STOPS = [98.0, 100.0, 102.0]


def _three_stage_trailing_stop(
    config: ThreeStageExitConfig, position, high_since_entry: float
) -> float:
    """Call the legacy instance method without running heavy __init__."""
    exit_obj = object.__new__(ThreeStageExit)
    exit_obj.config = config
    return exit_obj._calculate_trailing_stop(position, high_since_entry)


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


class TestDifferentialAbsStopHit:
    """abs_stop_hit == legacy _stop_hit / _price_crossed(trigger='stop')."""

    @pytest.mark.parametrize("legacy_cls", STOP_HIT_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("current", PRICES)
    @pytest.mark.parametrize("stop", STOPS)
    def test_stop_hit_grid_equivalence(
        self, legacy_cls: type, side: PositionSide, current: float, stop: float
    ) -> None:
        pos = make_position(side, 100.0)
        assert abs_stop_hit(side, current, stop) == legacy_cls._stop_hit(
            pos, current, stop
        )

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("current", PRICES)
    @pytest.mark.parametrize("stop", STOPS)
    def test_setup_target_price_crossed_equivalence(
        self, side: PositionSide, current: float, stop: float
    ) -> None:
        assert abs_stop_hit(side, current, stop) == SetupTargetExit._price_crossed(
            side=side, current_price=current, trigger_price=stop, trigger="stop"
        )


class TestPctStopHit:
    """pct_stop_hit unit + differential against the legacy condition."""

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
    def test_differential_vs_legacy_condition(
        self, side: PositionSide, factor: float, threshold: float
    ) -> None:
        """Matches ``_calc_profit_pct(...) <= stop_loss_pct`` (momentum_decay/three_stage Stage-1)."""
        pos = make_position(side, 100.0)
        current = 100.0 * factor
        legacy_fires = MomentumDecayExit._calc_profit_pct(pos, current) <= threshold
        assert pct_stop_hit(pos, current, threshold) == legacy_fires


class TestAtrStopLevel:
    """atr_stop_level unit + differential against track_a / chandelier."""

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
    def test_differential_vs_track_a_trail_stop_price(
        self, side: PositionSide, extreme: float, atr: float, mult: float
    ) -> None:
        assert atr_stop_level(extreme, atr, mult, side) == trail_stop_price(
            side, extreme, atr, mult
        )

    @pytest.mark.parametrize("highest_high", [100.0, 351.25, 70000.0])
    @pytest.mark.parametrize("atr", [0.4, 2.0, 350.0])
    @pytest.mark.parametrize("mult", [2.0, 3.0])
    def test_differential_vs_chandelier_level_formula(
        self, highest_high: float, atr: float, mult: float
    ) -> None:
        """chandelier_stop = highest_high - atr * multiplier (LONG-shaped)."""
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
    """pct_trailing_stop_level unit + differential against three_stage."""

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
    def test_differential_vs_three_stage_normal_gap(
        self, extreme: float, gap: float, side: PositionSide
    ) -> None:
        """Matches _calculate_trailing_stop with the overshoot branch off.

        stop_price == 0 keeps the legacy ``position.stop_price`` clamp inert
        (clamping is call-site state, not primitive math).
        """
        config = ThreeStageExitConfig(
            trailing_stop_pct=gap, overshoot_threshold_pct=10.0
        )
        pos = make_position(side, 100.0)
        assert pos.stop_price == 0.0
        expected = _three_stage_trailing_stop(config, pos, extreme)
        assert pct_trailing_stop_level(extreme, gap, side) == pytest.approx(expected)

    @pytest.mark.parametrize("side", SIDES)
    def test_differential_vs_three_stage_overshoot_gap(
        self, side: PositionSide
    ) -> None:
        """Overshoot branch: legacy switches to overshoot_trailing_pct."""
        config = ThreeStageExitConfig(
            trailing_stop_pct=-0.03,
            overshoot_threshold_pct=0.05,
            overshoot_trailing_pct=-0.015,
        )
        pos = make_position(side, 100.0)
        # 10% favorable move → overshoot branch active.
        extreme = 110.0 if side == PositionSide.LONG else 90.0
        expected = _three_stage_trailing_stop(config, pos, extreme)
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
